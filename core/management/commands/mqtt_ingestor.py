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

# Adjust imports to your app
from core.models import NptReason, ProcessedNPT, RotationStatus, Machine

import paho.mqtt.client as mqtt

# ---------- Logging ----------
LOG = logging.getLogger("mqtt_ingestor")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# ---------- Constants ----------
BD_TZ = ZoneInfo("Asia/Dhaka")
TOPIC_MC_STATUS = "npt/mc-status"
TOPIC_ROTATION = "npt/rotation-data"

DEFAULT_QOS = 1
QUEUE_MAXSIZE = 10_000
BATCH_SIZE_ROTATION = 50
BATCH_SIZE_OFF = 50
BATCH_SIZE_ON = 50
FLUSH_INTERVAL_SEC = 5.0
REASON_REFRESH_SEC = 3600
MC_REFRESH_SEC = 3600
STATS_INTERVAL_SEC = 5
BUFFER_DIR = "/var/www/ilife/mqtt_buffer"


# ---------- Helpers ----------
def epoch_ms_to_dt(ts_ms: int) -> datetime:
    """Convert milliseconds timestamp to local datetime (naive)."""
    try:
        dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
    except Exception:
        if ts_ms < 20_000_000_000:
            dt = datetime.fromtimestamp(ts_ms, tz=timezone.utc)
        else:
            dt = datetime.now(timezone.utc)
    local_dt = dt.astimezone(BD_TZ)
    if local_dt.year < 2000:
        LOG.warning("Received invalid timestamp %s, replacing with now", local_dt.isoformat())
        local_dt = datetime.now(BD_TZ)
    return local_dt.replace(tzinfo=None)


@dataclass
class McStatusMsg:
    machine: Machine
    status: str  # "on", "off", "btn"
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
    def __init__(self, broker_host: str, broker_port: int, username: str, password: str, qos: int = DEFAULT_QOS, client_id: Optional[str] = None):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.username = username
        self.password = password
        self.qos = qos
        self.client_id = client_id or f"mqtt-ingestor-{int(time.time())}"
        self.shutdown = ShutdownFlag()

        # Queues
        self.q_rotation: "Queue[RotationMsg]" = Queue(maxsize=QUEUE_MAXSIZE)
        self.q_off: "Queue[McStatusMsg]" = Queue(maxsize=QUEUE_MAXSIZE)
        self.q_on: "Queue[McStatusMsg]" = Queue(maxsize=QUEUE_MAXSIZE)
        self.q_btn: "Queue[McStatusMsg]" = Queue(maxsize=QUEUE_MAXSIZE)

        # Maps
        self.reason_map: Dict[int, int] = {}
        self.machine_map: Dict[str, Machine] = {}

        # Stats
        self.stats = defaultdict(int)
        self.last_stats_time = time.time()

        # MQTT client
        self.client = mqtt.Client(client_id=self.client_id, clean_session=False, protocol=mqtt.MQTTv311)
        self.client.username_pw_set(self.username, self.password)
        self.client.enable_logger(logging.getLogger("paho.mqtt.client"))
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect
        try:
            self.client.max_inflight_messages_set(2000)
            self.client.max_queued_messages_set(50000)
        except Exception:
            pass
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        self.keepalive = 60

        # Ensure buffer directory exists
        os.makedirs(BUFFER_DIR, exist_ok=True)

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
            LOG.warning("Unexpected MQTT disconnect (rc=%s). Will auto-reconnect.", rc)
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
            self.enqueue_mc_status(data)
        elif msg.topic == TOPIC_ROTATION:
            self.enqueue_rotation(data)
        else:
            self.stats["unexpected_topic"] += 1

        self._maybe_log_stats()

    # ---------- Queue enqueuing ----------
    def enqueue_mc_status(self, data: Dict[str, Any]):
        try:
            mc_raw = str(data["mc"]).strip().lower()
            status = str(data["status"]).strip().lower()
            ts = epoch_ms_to_dt(int(data["timestamp"]))
        except Exception as e:
            LOG.error("Invalid MC payload: %s, data=%s", e, data)
            self.stats["mc_status_bad"] += 1
            self._append_to_buffer("on" if data.get("status")=="on" else "off", data)
            return

        machine = self.machine_map.get(mc_raw)
        if not machine:
            LOG.warning("MC %s not found", mc_raw)
            self.stats["mc_unknown"] += 1
            self._append_to_buffer("on" if status=="on" else "off", data)
            return

        msg = McStatusMsg(machine=machine, status=status, ts=ts)
        if status == "btn":
            try:
                btn = int(data["btn"])
                reason_id = self.reason_map.get(btn)
                msg.btn = btn
                msg.reason_id = reason_id
            except Exception:
                LOG.error("Invalid/missing btn: %s", data)
                self._append_to_buffer("btn", data)
                return
            queue = self.q_btn
        elif status == "off":
            queue = self.q_off
        else:
            queue = self.q_on

        try:
            queue.put_nowait(msg)
            self.stats[f"{status}_enqueued"] += 1
        except Full:
            LOG.error("Queue full, saving to buffer: mc=%s status=%s", mc_raw, status)
            self.stats[f"{status}_dropped"] += 1
            self._append_to_buffer(status, data)

    def enqueue_rotation(self, data: Dict[str, Any]):
        try:
            mc_raw = str(data["mc"]).strip().lower()
            rotation = int(data["rotation"])
            ts = epoch_ms_to_dt(int(data["timestamp"]))
        except Exception as e:
            LOG.error("Invalid rotation payload: %s, data=%s", e, data)
            self.stats["rotation_bad"] += 1
            self._append_to_buffer("rotation", data)
            return

        machine = self.machine_map.get(mc_raw)
        if not machine:
            LOG.warning("Rotation MC %s not found", mc_raw)
            self.stats["rotation_unknown"] += 1
            self._append_to_buffer("rotation", data)
            return

        try:
            self.q_rotation.put_nowait(RotationMsg(machine=machine, rotation=rotation, ts=ts))
            self.stats["rotation_enqueued"] += 1
        except Full:
            LOG.error("Rotation queue full, saving to buffer mc=%s", mc_raw)
            self.stats["rotation_dropped"] += 1
            self._append_to_buffer("rotation", data)

    # ---------- Buffer ----------
    def _append_to_buffer(self, prefix: str, data: Dict[str, Any]):
        try:
            path = os.path.join(BUFFER_DIR, f"{prefix}_buffer.jsonl")
            with open(path, "a") as f:
                f.write(json.dumps(data) + "\n")
        except Exception as e:
            LOG.error("Failed writing buffer: %s", e)

    def flush_all_buffers(self):
        for fname in os.listdir(BUFFER_DIR):
            path = os.path.join(BUFFER_DIR, fname)
            if fname.endswith(".jsonl"):
                try:
                    with open(path) as f:
                        for line in f:
                            data = json.loads(line)
                            if fname.startswith("rotation"):
                                self.enqueue_rotation(data)
                            elif fname.startswith("btn"):
                                self.enqueue_mc_status({**data, "status":"btn"})
                            elif fname.startswith("off"):
                                self.enqueue_mc_status({**data, "status":"off"})
                            else:
                                self.enqueue_mc_status({**data, "status":"on"})
                    os.remove(path)
                except Exception as e:
                    LOG.error("Failed flushing buffer %s: %s", path, e)

    # ---------- Worker threads ----------
    def worker_flush_rotation(self):
        while not self.shutdown.is_set():
            batch: List[RotationStatus] = []
            try:
                while len(batch) < BATCH_SIZE_ROTATION:
                    msg = self.q_rotation.get(timeout=FLUSH_INTERVAL_SEC)
                    batch.append(RotationStatus(machine=msg.machine, rotation=msg.rotation, timestamp=msg.ts))
            except Empty:
                pass

            if batch:
                try:
                    RotationStatus.objects.bulk_create(batch, ignore_conflicts=True)
                    self.stats["rotation_flushed"] += len(batch)
                except Exception as e:
                    LOG.error("Failed flush rotation batch: %s", e)
                    for msg in batch:
                        self._append_to_buffer("rotation", {"mc": msg.machine.device_mc, "rotation": msg.rotation, "timestamp": int(msg.ts.timestamp()*1000)})

    def worker_flush_off(self):
        while not self.shutdown.is_set():
            batch: List[ProcessedNPT] = []
            try:
                while len(batch) < BATCH_SIZE_OFF:
                    msg: McStatusMsg = self.q_off.get(timeout=FLUSH_INTERVAL_SEC)
                    batch.append(ProcessedNPT(machine=msg.machine, off_time=msg.ts))
            except Empty:
                pass

            if batch:
                try:
                    ProcessedNPT.objects.bulk_create(batch, ignore_conflicts=True)
                    self.stats["off_flushed"] += len(batch)
                except Exception as e:
                    LOG.error("Failed flush OFF batch: %s", e)
                    for msg in batch:
                        self._append_to_buffer("off", {"mc": msg.machine.device_mc, "status": "off", "timestamp": int(msg.off_time.timestamp()*1000)})

    def worker_apply_on(self):
        while not self.shutdown.is_set():
            try:
                batch: List[McStatusMsg] = []
                while len(batch) < BATCH_SIZE_ON:
                    msg: McStatusMsg = self.q_on.get(timeout=FLUSH_INTERVAL_SEC)
                    batch.append(msg)
            except Empty:
                pass

            for msg in batch:
                try:
                    with transaction.atomic():
                        last_row = ProcessedNPT.objects.select_for_update(skip_locked=True).filter(machine=msg.machine).order_by("-off_time").first()
                        if last_row and last_row.on_time is None:
                            last_row.on_time = msg.ts
                            last_row.save(update_fields=["on_time"])
                            self.stats["on_closed"] += 1
                        else:
                            self.stats["on_no_open"] += 1
                except Exception as e:
                    LOG.error("Failed apply ON msg: %s", e)
                    self._append_to_buffer("on", {"mc": msg.machine.device_mc, "status":"on", "timestamp": int(msg.ts.timestamp()*1000)})

    def worker_apply_btn(self):
        while not self.shutdown.is_set():
            try:
                msg: McStatusMsg = self.q_btn.get(timeout=FLUSH_INTERVAL_SEC)
            except Empty:
                continue

            if msg.reason_id is None:
                LOG.warning("BTN %s not mapped to reason for mc=%s", msg.btn, msg.machine.device_mc)
                self._append_to_buffer("btn", {"mc": msg.machine.device_mc, "btn": msg.btn, "timestamp": int(msg.ts.timestamp()*1000)})
                continue

            try:
                with transaction.atomic():
                    last_row = ProcessedNPT.objects.select_for_update(skip_locked=True).filter(machine=msg.machine).order_by("-off_time").first()
                    if last_row and last_row.reason_id is None:
                        last_row.reason_id = msg.reason_id
                        last_row.save(update_fields=["reason_id"])
                        self.stats["btn_applied"] += 1
                    else:
                        self.stats["btn_skipped"] += 1
            except Exception as e:
                LOG.error("Failed apply BTN msg: %s", e)
                self._append_to_buffer("btn", {"mc": msg.machine.device_mc, "btn": msg.btn, "timestamp": int(msg.ts.timestamp()*1000)})

    # ---------- Maps refresh ----------
    def refresh_machine_map(self):
        while not self.shutdown.is_set():
            try:
                with transaction.atomic():
                    rows = list(Machine.objects.filter(is_deleted=False).values("id", "device_mc"))
                    self.machine_map = {r["device_mc"].lower(): Machine.objects.get(id=r["id"]) for r in rows}
                LOG.info("Refreshed machine map: %d machines", len(self.machine_map))
            except Exception as e:
                LOG.error("Failed refreshing machine map: %s", e)
            for _ in range(MC_REFRESH_SEC * 10):
                if self.shutdown.is_set():
                    return
                time.sleep(0.1)

    def refresh_reason_map(self):
        while not self.shutdown.is_set():
            try:
                with transaction.atomic():
                    rows = list(NptReason.objects.filter(is_deleted=False).values("id", "remote_num"))
                    self.reason_map = {int(r["remote_num"]): int(r["id"]) for r in rows}
                LOG.info("Refreshed reason map: %d entries", len(self.reason_map))
            except Exception as e:
                LOG.error("Failed refreshing reason map: %s", e)
            for _ in range(REASON_REFRESH_SEC * 10):
                if self.shutdown.is_set():
                    return
                time.sleep(0.1)

    # ---------- Stats ----------
    def _maybe_log_stats(self):
        now = time.time()
        if now - self.last_stats_time >= STATS_INTERVAL_SEC:
            self.last_stats_time = now
            LOG.info(
                "stats rotation_enq=%d flushed=%d off_enq=%d flushed=%d on_enq=%d closed=%d "
                "btn_enq=%d btn_applied=%d btn_skipped=%d bad_json=%d mc_bad=%d rot_bad=%d on_no_open=%d",
                self.stats["rotation_enqueued"],
                self.stats["rotation_flushed"],
                self.stats["off_enqueued"],
                self.stats["off_flushed"],
                self.stats["on_enqueued"],
                self.stats["on_closed"],
                self.stats["btn_enqueued"],
                self.stats["btn_applied"],
                self.stats["btn_skipped"],
                self.stats["bad_json"],
                self.stats["mc_status_bad"],
                self.stats["rotation_bad"],
                self.stats["on_no_open"],
            )

    # ---------- Lifecycle ----------
    def start(self):
        threads = []

        # Map refresh threads
        t_mc = threading.Thread(target=self.refresh_machine_map, daemon=True)
        t_mc.start()
        threads.append(t_mc)

        t_reason = threading.Thread(target=self.refresh_reason_map, daemon=True)
        t_reason.start()
        threads.append(t_reason)

        # Worker threads
        t_rot = threading.Thread(target=self.worker_flush_rotation, daemon=True)
        t_rot.start()
        threads.append(t_rot)

        t_off = threading.Thread(target=self.worker_flush_off, daemon=True)
        t_off.start()
        threads.append(t_off)

        t_on = threading.Thread(target=self.worker_apply_on, daemon=True)
        t_on.start()
        threads.append(t_on)

        t_btn = threading.Thread(target=self.worker_apply_btn, daemon=True)
        t_btn.start()
        threads.append(t_btn)

        # Flush buffers on startup
        self.flush_all_buffers()

        def handle_sig(signum, frame):
            LOG.info("Received shutdown signal %s", signum)
            self.stop()

        signal.signal(signal.SIGINT, handle_sig)
        signal.signal(signal.SIGTERM, handle_sig)

        self.client.connect(self.broker_host, self.broker_port, keepalive=self.keepalive)
        self.client.loop_start()

        while not self.shutdown.is_set():
            time.sleep(0.5)

        self.client.loop_stop()
        for t in threads:
            t.join()

    def stop(self):
        self.shutdown.set()
        self.flush()

    def flush(self):
        LOG.info("Starting final flush of queues and buffers...")
        self.flush_all_buffers()


# ---------- Management command ----------
class Command(BaseCommand):
    help = "Subscribe to MQTT and insert into Django/PostgreSQL (NPT + Rotation)."

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
        ingestor.start()
