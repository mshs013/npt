# core/management/commands/mqtt_ingestor.py
import json
import logging
import signal
import threading
import time
import os
from zoneinfo import ZoneInfo
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from queue import Queue, Full, Empty
from typing import Optional, Dict, Any, List

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import NptReason, MachineStatus, RotationStatus, Machine

import paho.mqtt.client as mqtt
from concurrent.futures import ThreadPoolExecutor

# ---------- Logging ----------
LOG = logging.getLogger("mqtt_ingestor")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# ---------- Constants ----------
BD_TZ = ZoneInfo("Asia/Dhaka")
TOPIC_MC_STATUS = "npt/mc-data"
TOPIC_ROTATION = "npt/rot-data"

DEFAULT_QOS = 1
QUEUE_MAX_ROTATION = 100_000
QUEUE_MAX_STATUS = 100_000
BATCH_SIZE_ROTATION = 2000
BATCH_SIZE_STATUS = 2000
FLUSH_INTERVAL_SEC = 0.5
REASON_REFRESH_SEC = 3600
MC_REFRESH_SEC = 3600
STATS_INTERVAL_SEC = 5
BUFFER_DIR = "/home/sazzad/python/npt/mqtt_buffer"
DB_WORKER_COUNT = 4  # Number of threads for parallel DB inserts

os.makedirs(BUFFER_DIR, exist_ok=True)

# ---------- Helpers ----------
def epoch_ms_to_dt(ts_ms: int) -> datetime:
    try:
        dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
    except Exception:
        dt = datetime.now(timezone.utc)
    local_dt = dt.astimezone(BD_TZ)
    if local_dt.year < 2000:
        LOG.warning("Invalid timestamp %s, replacing with now", local_dt.isoformat())
        local_dt = datetime.now(BD_TZ)
    return local_dt.replace(tzinfo=None)

def buffer_file_path(prefix: str) -> str:
    date_str = datetime.now().strftime("%Y%m%d")
    return os.path.join(BUFFER_DIR, f"{prefix}_{date_str}.jsonl")

@dataclass
class MachineMsg:
    machine: Machine
    status: str
    ts: datetime
    btn: Optional[int] = None
    reason_id: Optional[int] = None

@dataclass
class RotationMsg:
    machine: Machine
    rotation: int
    ts: datetime

class ShutdownFlag:
    def __init__(self) -> None:
        self._flag = threading.Event()
    def set(self) -> None:
        self._flag.set()
    def is_set(self) -> bool:
        return self._flag.is_set()

# ---------- Ingestor ----------
class Ingestor:
    def __init__(self, broker_host, broker_port, username, password, qos=DEFAULT_QOS, client_id=None):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.username = username
        self.password = password
        self.qos = qos
        self.client_id = client_id or f"mqtt-ingestor-{int(time.time())}"
        self.shutdown = ShutdownFlag()

        # Queues
        self.q_rotation: Queue[RotationMsg] = Queue(maxsize=QUEUE_MAX_ROTATION)
        self.q_status: Queue[MachineMsg] = Queue(maxsize=QUEUE_MAX_STATUS)

        # Maps + locks
        self.reason_map: Dict[int, int] = {}
        self.machine_map: Dict[str, Machine] = {}
        self.map_lock = threading.Lock()

        # Stats
        self.stats = defaultdict(int)
        self.last_stats_time = time.time()

        # ---------- STATE-BASED DUPLICATE PREVENTION ----------
        self.last_status: Dict[int, str] = {}     # machine_id -> last status
        self.last_rotation: Dict[int, int] = {}   # machine_id -> last rotation
        self.state_lock = threading.Lock()

        # MQTT client
        self.client = mqtt.Client(client_id=self.client_id, clean_session=False, protocol=mqtt.MQTTv311)
        self.client.username_pw_set(self.username, self.password)
        self.client.enable_logger(logging.getLogger("paho.mqtt.client"))
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        try:
            self.client.max_inflight_messages_set(20_000)
            self.client.max_queued_messages_set(500_000)
        except Exception:
            pass
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        self.keepalive = 60

        # Thread pool for DB workers
        self.db_executor = ThreadPoolExecutor(max_workers=DB_WORKER_COUNT * 2)  # for rotation + status
        self.buffer_flush_interval = 5.0
        self.last_buffer_flush = time.time()

    # ---------- MQTT callbacks ----------
    def on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            LOG.info("Connected to MQTT %s:%s as %s", self.broker_host, self.broker_port, self.client_id)
            client.subscribe(TOPIC_MC_STATUS, qos=self.qos)
            client.subscribe(TOPIC_ROTATION, qos=self.qos)
        else:
            LOG.error("MQTT connect failed rc=%s", rc)

    def on_disconnect(self, client, userdata, rc):
        if rc != 0:
            LOG.warning("Unexpected MQTT disconnect (rc=%s). Auto-reconnect.", rc)
        else:
            LOG.info("MQTT disconnected cleanly.")

    def on_message(self, client, userdata, msg):
        try:
            data = json.loads(msg.payload.decode("utf-8"))
        except Exception as e:
            LOG.error("Bad JSON on %s: %s", msg.topic, e)
            self.stats["bad_json"] += 1
            return

        if msg.topic == TOPIC_MC_STATUS:
            self.enqueue_status(data)
        elif msg.topic == TOPIC_ROTATION:
            self.enqueue_rotation(data)
        else:
            self.stats["unexpected_topic"] += 1

        self._maybe_log_stats()

    # ---------- Enqueue with duplicate check ----------
    def enqueue_status(self, data: Dict[str, Any]):
        try:
            mc_raw = str(data["mc"]).strip().lower()
            status = str(data["status"]).strip().lower()
            ts = epoch_ms_to_dt(int(data["timestamp"]))
        except Exception:
            self._append_to_buffer("status", data)
            self.stats["status_bad"] += 1
            return

        with self.map_lock:
            machine = self.machine_map.get(mc_raw)
            reason_map_copy = self.reason_map.copy()

        if not machine:
            self._append_to_buffer("status_overflow", data)
            self.stats["status_unknown"] += 1
            return

        # Ignore same status repeats
        with self.state_lock:
            if self.last_status.get(machine.id) == status:
                self.stats["status_dup_state"] += 1
                return
            self.last_status[machine.id] = status

        msg = MachineMsg(machine=machine, status=status, ts=ts)
        if status == "btn":
            try:
                btn = int(data.get("btn", -1))
                msg.btn = btn
                msg.reason_id = reason_map_copy.get(btn)
            except Exception:
                self._append_to_buffer("status_overflow", data)
                return

        try:
            self.q_status.put_nowait(msg)
            self.stats[f"{status}_enqueued"] += 1
        except Full:
            self._append_to_buffer("status_overflow", data)
            self.stats[f"{status}_overflow"] += 1

    def enqueue_rotation(self, data: Dict[str, Any]):
        try:
            mc_raw = str(data["mc"]).strip().lower()
            rotation = int(data["rotation"])
            ts = epoch_ms_to_dt(int(data["timestamp"]))
        except Exception:
            self._append_to_buffer("rotation_overflow", data)
            self.stats["rotation_bad"] += 1
            return

        with self.map_lock:
            machine = self.machine_map.get(mc_raw)

        if not machine:
            self._append_to_buffer("rotation_overflow", data)
            self.stats["rotation_unknown"] += 1
            return

        # Ignore same rotation repeats
        with self.state_lock:
            if self.last_rotation.get(machine.id) == rotation:
                self.stats["rotation_dup_state"] += 1
                return
            self.last_rotation[machine.id] = rotation

        try:
            self.q_rotation.put_nowait(RotationMsg(machine=machine, rotation=rotation, ts=ts))
            self.stats["rotation_enqueued"] += 1
        except Full:
            self._append_to_buffer("rotation_overflow", data)
            self.stats["rotation_overflow"] += 1

    # ---------- Buffer ----------
    def _append_to_buffer(self, prefix: str, data: Dict[str, Any]):
        try:
            path = buffer_file_path(prefix)
            with open(path, "a") as f:
                f.write(json.dumps(data) + "\n")
        except Exception as e:
            LOG.error("Buffer write failed: %s", e)

    def flush_all_buffers(self):
        files = [f for f in os.listdir(BUFFER_DIR) if f.endswith(".jsonl")]
        for fname in files:
            path = os.path.join(BUFFER_DIR, fname)
            try:
                with open(path) as f:
                    for line in f:
                        data = json.loads(line)
                        if "rotation" in fname:
                            self.enqueue_rotation(data)
                        else:
                            self.enqueue_status(data)
                os.remove(path)
            except Exception as e:
                LOG.error("Failed flushing buffer %s: %s", path, e)

    # ---------- Load last known state from DB ----------
    def load_last_known_state(self):
        try:
            # Load last status per machine
            latest_status = (
                MachineStatus.objects.order_by("machine_id", "-status_time")
                .distinct("machine_id")
            )
            for row in latest_status:
                self.last_status[row.machine_id] = row.status

            # Load last rotation per machine
            latest_rotation = (
                RotationStatus.objects.order_by("machine_id", "-count_time")
                .distinct("machine_id")
            )
            for row in latest_rotation:
                self.last_rotation[row.machine_id] = row.count

            LOG.info(
                "Loaded last known state: %d statuses, %d rotations",
                len(self.last_status), len(self.last_rotation),
            )
        except Exception as e:
            LOG.error("Failed loading last known state: %s", e)

    # ---------- Worker Threads ----------
    def worker_flush_rotation(self):
        while not self.shutdown.is_set():
            batch: List[RotationStatus] = []
            try:
                while len(batch) < BATCH_SIZE_ROTATION:
                    msg: RotationMsg = self.q_rotation.get(timeout=FLUSH_INTERVAL_SEC)
                    batch.append(RotationStatus(machine=msg.machine, count=msg.rotation, count_time=msg.ts))
            except Empty:
                pass

            if batch:
                self.db_executor.submit(self._flush_rotation_batch, batch)

    def _flush_rotation_batch(self, batch: List[RotationStatus]):
        try:
            RotationStatus.objects.bulk_create(batch, ignore_conflicts=True)
            self.stats["rotation_flushed"] += len(batch)
        except Exception as e:
            LOG.error("Rotation flush failed: %s", e)
            for msg in batch:
                self._append_to_buffer("rotation_overflow", {
                    "mc": msg.machine.device_mc,
                    "rotation": msg.count,
                    "timestamp": int(msg.count_time.timestamp() * 1000)
                })

    def worker_flush_status(self):
        while not self.shutdown.is_set():
            batch: List[MachineStatus] = []
            try:
                while len(batch) < BATCH_SIZE_STATUS:
                    msg: MachineMsg = self.q_status.get(timeout=FLUSH_INTERVAL_SEC)
                    batch.append(MachineStatus(
                        machine=msg.machine,
                        status=msg.status,
                        status_time=msg.ts,
                        reason_id=msg.reason_id
                    ))
            except Empty:
                pass

            if batch:
                self.db_executor.submit(self._flush_status_batch, batch)

    def _flush_status_batch(self, batch: List[MachineStatus]):
        try:
            MachineStatus.objects.bulk_create(batch, ignore_conflicts=True)
            self.stats["status_flushed"] += len(batch)
        except Exception as e:
            LOG.error("Status flush failed: %s", e)
            for msg in batch:
                self._append_to_buffer("status_overflow", {
                    "mc": msg.machine.device_mc,
                    "status": msg.status,
                    "btn": msg.btn,
                    "timestamp": int(msg.ts.timestamp() * 1000)
                })

    def worker_disk_overflow(self):
        while not self.shutdown.is_set():
            self.flush_all_buffers()
            time.sleep(self.buffer_flush_interval)

    def refresh_machine_map(self):
        while not self.shutdown.is_set():
            try:
                with transaction.atomic():
                    rows = list(Machine.objects.filter(is_deleted=False).values("id", "device_mc"))
                    with self.map_lock:
                        self.machine_map = {r["device_mc"].lower(): Machine.objects.get(id=r["id"]) for r in rows}
                LOG.info("Refreshed machine map: %d machines", len(self.machine_map))
            except Exception as e:
                LOG.error("Failed refreshing machine map: %s", e)
            time.sleep(MC_REFRESH_SEC)

    def refresh_reason_map(self):
        while not self.shutdown.is_set():
            try:
                with transaction.atomic():
                    rows = list(NptReason.objects.filter(is_deleted=False).values("id", "remote_num"))
                    with self.map_lock:
                        self.reason_map = {int(r["remote_num"]): int(r["id"]) for r in rows}
                LOG.info("Refreshed reason map: %d entries", len(self.reason_map))
            except Exception as e:
                LOG.error("Failed refreshing reason map: %s", e)
            time.sleep(REASON_REFRESH_SEC)

    def _maybe_log_stats(self):
        now = time.time()
        if now - self.last_stats_time >= STATS_INTERVAL_SEC:
            self.last_stats_time = now
            rotation_overflow_size = self.q_rotation.qsize()
            status_overflow_size = self.q_status.qsize()
            LOG.info("Stats: rotation_enq=%d flushed=%d overflow=%d | status_enq=%d flushed=%d overflow=%d | bad_json=%d",
                     self.stats["rotation_enqueued"], self.stats.get("rotation_flushed",0), rotation_overflow_size,
                     self.stats.get("on_enqueued",0)+self.stats.get("off_enqueued",0)+self.stats.get("btn_enqueued",0),
                     self.stats.get("status_flushed",0), status_overflow_size,
                     self.stats.get("bad_json",0))

    def start(self):
        threads = []

        # Map refresh
        t_mc = threading.Thread(target=self.refresh_machine_map, daemon=True)
        t_mc.start(); threads.append(t_mc)
        t_reason = threading.Thread(target=self.refresh_reason_map, daemon=True)
        t_reason.start(); threads.append(t_reason)

        # Workers
        for _ in range(DB_WORKER_COUNT):
            t_rot = threading.Thread(target=self.worker_flush_rotation, daemon=True)
            t_rot.start(); threads.append(t_rot)
            t_status = threading.Thread(target=self.worker_flush_status, daemon=True)
            t_status.start(); threads.append(t_status)

        t_overflow = threading.Thread(target=self.worker_disk_overflow, daemon=True)
        t_overflow.start(); threads.append(t_overflow)

        # Flush buffers on startup
        self.flush_all_buffers()

        # Load last known DB state
        self.load_last_known_state()

        def handle_sig(signum, frame):
            LOG.info("Shutdown signal %s received", signum)
            self.stop()

        signal.signal(signal.SIGINT, handle_sig)
        signal.signal(signal.SIGTERM, handle_sig)

        self.client.connect(self.broker_host, self.broker_port, keepalive=self.keepalive)
        self.client.loop_start()

        try:
            while not self.shutdown.is_set():
                time.sleep(0.5)
        finally:
            self.client.loop_stop()
            for t in threads:
                t.join()
            if hasattr(self, "db_executor"):
                self.db_executor.shutdown(wait=True)
            self.flush_all_buffers()
            print("\nMQTT ingestor stopped. Shell prompt restored.")

    def stop(self):
        self.shutdown.set()
        LOG.info("Flushing all buffers before shutdown...")
        self.flush_all_buffers()
        LOG.info("Shutdown complete.")

# ---------- Management Command ----------
class Command(BaseCommand):
    help = "Subscribe to MQTT and insert into Django/PostgreSQL (MachineStatus + Rotation)."

    def add_arguments(self, parser):
        parser.add_argument("--broker", default="192.168.10.252")
        parser.add_argument("--port", type=int, default=1883)
        parser.add_argument("--username", default="ocmsiot")
        parser.add_argument("--password", default="ocmsERP2016")

    def handle(self, *args, **options):
        ingestor = Ingestor(
            broker_host=options["broker"],
            broker_port=options["port"],
            username=options["username"],
            password=options["password"],
        )
        try:
            ingestor.start()
        except KeyboardInterrupt:
            LOG.info("KeyboardInterrupt received, shutting down...")
            ingestor.stop()
        finally:
            LOG.info("MQTT ingestor command exiting cleanly.")
