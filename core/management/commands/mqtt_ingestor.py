# core/management/commands/mqtt_ingestor.py

import json
import logging
import signal
import sys
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

LOG = logging.getLogger("mqtt_ingestor")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

BD_TZ = ZoneInfo("Asia/Dhaka")

TOPIC_MC_STATUS = "npt/mc-status"
TOPIC_ROTATION = "npt/rotation-data"

DEFAULT_QOS = 1
QUEUE_MAXSIZE = 100_000
BATCH_SIZE_ROTATION = 50
BATCH_SIZE_OFF = 50
FLUSH_INTERVAL_SEC = 5.0
REASON_REFRESH_SEC = 3600
MC_REFRESH_SEC = 3600
STATS_INTERVAL_SEC = 5
BUFFER_DIR = "/var/www/ilife/mqtt_buffer"


def epoch_ms_to_dt(ts_ms: int) -> datetime:
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
    machine: str
    status: str
    ts: datetime
    btn: Optional[int] = None
    reason_id: Optional[int] = None


@dataclass
class RotationMsg:
    machine: str
    rotation: int
    ts: datetime


class ShutdownFlag:
    def __init__(self) -> None:
        self._flag = threading.Event()

    def set(self) -> None:
        self._flag.set()

    def is_set(self) -> bool:
        return self._flag.is_set()


class Ingestor:
    def __init__(self, broker_host: str, broker_port: int, username: str, password: str, qos: int = DEFAULT_QOS, client_id: Optional[str] = None):
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.username = username
        self.password = password
        self.qos = qos
        self.client_id = client_id or f"mqtt-ingestor-{int(time.time())}"
        self.shutdown = ShutdownFlag()

        self.q_rotation: "Queue[RotationMsg]" = Queue(maxsize=QUEUE_MAXSIZE)
        self.q_off: "Queue[ProcessedNPT]" = Queue(maxsize=QUEUE_MAXSIZE)
        self.q_on: "Queue[McStatusMsg]" = Queue(maxsize=QUEUE_MAXSIZE)

        self.reason_map: Dict[int, int] = {}
        self.machine_map: Dict[str, Machine] = {}
        self.stats = defaultdict(int)
        self.last_stats_time = time.time()

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
        topic = msg.topic
        payload = msg.payload
        try:
            data = json.loads(payload.decode("utf-8"))
        except Exception as e:
            LOG.error("Bad JSON on %s: %s", topic, e)
            self.stats["bad_json"] += 1
            return

        if topic == TOPIC_MC_STATUS:
            self.handle_mc_status(data)
        elif topic == TOPIC_ROTATION:
            self.handle_rotation(data)
        else:
            self.stats["unexpected_topic"] += 1

        self._maybe_log_stats()

    # ---------- Machine & Reason map refresh ----------
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

    # ---------- Disk buffer helpers ----------
    def _buffer_file_path(self, prefix: str) -> str:
        timestamp = int(time.time() * 1000)
        return os.path.join(BUFFER_DIR, f"{prefix}_{timestamp}.json")

    def _append_to_buffer(self, prefix: str, data: Dict[str, Any]) -> None:
        try:
            path = self._buffer_file_path(prefix)
            with open(path, "w") as f:
                json.dump(data, f)
        except Exception as e:
            LOG.error("Failed writing buffer file: %s", e)

    def _flush_buffer_file(self, filepath: str) -> None:
        try:
            with open(filepath) as f:
                data = json.load(f)
            if os.path.basename(filepath).startswith("rotation_"):
                self.handle_rotation(data)
            else:
                self.handle_mc_status(data)
            os.remove(filepath)
        except Exception as e:
            LOG.error("Failed flushing buffer file %s: %s", filepath, e)

    def flush_all_buffers(self):
        for fname in os.listdir(BUFFER_DIR):
            path = os.path.join(BUFFER_DIR, fname)
            self._flush_buffer_file(path)

    # ---------- Handlers ----------
    def handle_mc_status(self, data: Dict[str, Any]) -> None:
        try:
            mc_raw = str(data["mc"]).strip().lower()
            status = str(data["status"]).strip().lower()
            ts = epoch_ms_to_dt(int(data["timestamp"]))
        except Exception as e:
            LOG.error("Invalid mc-status payload: %s (data=%s)", e, data)
            self.stats["mc_status_bad"] += 1
            self._append_to_buffer("on" if data.get("status")=="on" else "off", data)
            return

        machine = self.machine_map.get(mc_raw)
        if not machine:
            LOG.warning("MC %s not found in machine map", mc_raw)
            self.stats["mc_unknown"] += 1
            self._append_to_buffer("on" if status=="on" else "off", data)
            return

        try:
            with transaction.atomic():
                last_row = (
                    ProcessedNPT.objects.select_for_update(skip_locked=True)
                    .filter(machine=machine)
                    .order_by("-off_time")
                    .first()
                )

                if status == "off":
                    if not last_row or last_row.on_time is not None:
                        obj = ProcessedNPT(machine=machine, off_time=ts)
                        try:
                            self.q_off.put_nowait(obj)
                            self.stats["off_enqueued"] += 1
                        except Full:
                            LOG.error("Queue full: dropping OFF event mc=%s ts=%s, saving to buffer", mc_raw, ts.isoformat())
                            self.stats["off_dropped"] += 1
                            self._append_to_buffer("off", data)
                    else:
                        LOG.info("Skipping OFF enqueue: last ON not closed for mc=%s", mc_raw)

                elif status == "on":
                    if last_row and last_row.on_time is None:
                        try:
                            last_row.on_time = ts
                            last_row.save(update_fields=["on_time"])
                            self.stats["on_closed"] += 1
                        except Exception as e:
                            LOG.error("ON update failed for mc=%s, saving to buffer: %s", mc_raw, e)
                            self.stats["on_failed"] += 1
                            self._append_to_buffer("on", data)
                    else:
                        LOG.info("Skipping ON update: no row to update or on_time already set for mc=%s", mc_raw)

                elif status == "btn":
                    try:
                        btn = int(data["btn"])
                    except Exception:
                        LOG.error("Invalid/missing btn in data: %s", data)
                        self.stats["btn_bad"] += 1
                        self._append_to_buffer("btn", data)
                        return

                    reason_id = self.reason_map.get(btn)
                    if reason_id is None:
                        LOG.warning("Btn %s not mapped to reason (mc=%s)", btn, mc_raw)
                        self.stats["btn_unmapped"] += 1
                        self._append_to_buffer("btn", data)
                        return

                    if last_row and last_row.reason_id is None:
                        try:
                            last_row.reason_id = reason_id
                            last_row.save(update_fields=["reason_id"])
                            self.stats["btn_applied"] += 1
                        except Exception as e:
                            LOG.error("BTN update failed for mc=%s, saving to buffer: %s", mc_raw, e)
                            self.stats["btn_failed"] += 1
                            self._append_to_buffer("btn", data)
                    else:
                        LOG.info("Skipping BTN update: no row or reason_id already set for mc=%s", mc_raw)

        except Exception as e:
            LOG.exception("Error handling MC status event: %s", e)
            self._append_to_buffer("on" if status=="on" else "off", data)

    def handle_rotation(self, data: Dict[str, Any]) -> None:
        try:
            mc_raw = str(data["mc"]).strip().lower()
            rotation = int(data["rotation"])
            ts = epoch_ms_to_dt(int(data["timestamp"]))
        except Exception as e:
            LOG.error("Invalid rotation payload: %s (data=%s)", e, data)
            self.stats["rotation_bad"] += 1
            self._append_to_buffer("rotation", data)
            return

        machine = self.machine_map.get(mc_raw)
        if not machine:
            LOG.warning("Rotation MC %s not found in machine map", mc_raw)
            self.stats["rotation_unknown"] += 1
            self._append_to_buffer("rotation", data)
            return

        msg = RotationMsg(machine=machine, rotation=rotation, ts=ts)
        try:
            self.q_rotation.put_nowait(msg)
            self.stats["rotation_enqueued"] += 1
        except Full:
            LOG.error("Queue full: dropping ROTATION mc=%s ts=%s, saving to buffer", mc_raw, ts.isoformat())
            self.stats["rotation_dropped"] += 1
            self._append_to_buffer("rotation", data)

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
                    RotationStatus.objects.bulk_create(batch)
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
                    obj = self.q_off.get(timeout=FLUSH_INTERVAL_SEC)
                    batch.append(obj)
            except Empty:
                pass

            if batch:
                try:
                    ProcessedNPT.objects.bulk_create(batch)
                    self.stats["off_flushed"] += len(batch)
                except Exception as e:
                    LOG.error("Failed flush OFF batch: %s", e)
                    for obj in batch:
                        self._append_to_buffer("off", {"mc": obj.machine.device_mc, "status": "off", "timestamp": int(obj.off_time.timestamp()*1000)})

    def worker_apply_on(self):
        while not self.shutdown.is_set():
            try:
                msg: McStatusMsg = self.q_on.get(timeout=FLUSH_INTERVAL_SEC)
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
                    self._append_to_buffer("on", {"mc": msg.machine.device_mc, "status": "on", "timestamp": int(msg.ts.timestamp()*1000)})
            except Empty:
                continue

    # ---------- Stats ----------
    def _maybe_log_stats(self):
        now = time.time()
        if now - self.last_stats_time >= STATS_INTERVAL_SEC:
            self.last_stats_time = now
            LOG.info(
                "stats rotation_enq=%d flushed=%d off_enq=%d flushed=%d on_enq=%d closed=%d "
                "bad_json=%d mc_bad=%d rot_bad=%d btn_unmapped=%d on_no_open=%d",
                self.stats["rotation_enqueued"],
                self.stats["rotation_flushed"],
                self.stats["off_enqueued"],
                self.stats["off_flushed"],
                self.stats["on_enqueued"],
                self.stats["on_closed"],
                self.stats["bad_json"],
                self.stats["mc_status_bad"],
                self.stats["rotation_bad"],
                self.stats["btn_unmapped"],
                self.stats["on_no_open"],
            )

    # ---------- Lifecycle ----------
    def start(self):
        threads = []

        t_mc = threading.Thread(target=self.refresh_machine_map, daemon=True)
        t_mc.start()
        threads.append(t_mc)

        t_reason = threading.Thread(target=self.refresh_reason_map, daemon=True)
        t_reason.start()
        threads.append(t_reason)

        t_rot = threading.Thread(target=self.worker_flush_rotation, daemon=True)
        t_rot.start()
        threads.append(t_rot)

        t_off = threading.Thread(target=self.worker_flush_off, daemon=True)
        t_off.start()
        threads.append(t_off)

        t_on = threading.Thread(target=self.worker_apply_on, daemon=True)
        t_on.start()
        threads.append(t_on)

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

        # Flush rotation
        batch_rot = []
        while not self.q_rotation.empty():
            msg = self.q_rotation.get()
            batch_rot.append(RotationStatus(machine=msg.machine, rotation=msg.rotation, timestamp=msg.ts))
        if batch_rot:
            try:
                RotationStatus.objects.bulk_create(batch_rot)
                self.stats["rotation_flushed"] += len(batch_rot)
            except Exception as e:
                LOG.error("Failed flush final rotation batch: %s", e)
                for msg in batch_rot:
                    self._append_to_buffer("rotation", {"mc": msg.machine.device_mc, "rotation": msg.rotation, "timestamp": int(msg.ts.timestamp()*1000)})

        # Flush OFF
        batch_off = []
        while not self.q_off.empty():
            obj = self.q_off.get()
            batch_off.append(obj)
        if batch_off:
            try:
                ProcessedNPT.objects.bulk_create(batch_off)
                self.stats["off_flushed"] += len(batch_off)
            except Exception as e:
                LOG.error("Failed flush final OFF batch: %s", e)
                for obj in batch_off:
                    self._append_to_buffer("off", {"mc": obj.machine.device_mc, "status": "off", "timestamp": int(obj.off_time.timestamp()*1000)})

        # Flush ON
        while not self.q_on.empty():
            msg: McStatusMsg = self.q_on.get()
            try:
                with transaction.atomic():
                    last_row = ProcessedNPT.objects.select_for_update(skip_locked=True).filter(machine=msg.machine).order_by("-off_time").first()
                    if last_row and last_row.on_time is None:
                        last_row.on_time = msg.ts
                        last_row.save(update_fields=["on_time"])
            except Exception as e:
                LOG.error("Failed flush final ON msg: %s", e)
                self._append_to_buffer("on", {"mc": msg.machine.device_mc, "status": "on", "timestamp": int(msg.ts.timestamp()*1000)})


# --------- Management command ---------
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
