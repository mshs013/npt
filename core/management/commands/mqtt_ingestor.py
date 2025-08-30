# core/management/commands/mqtt_ingestor.py

import json
import logging
import signal
import sys
import threading
import time
from zoneinfo import ZoneInfo
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from queue import Queue, Full, Empty
from typing import Optional, Dict, Any, List

from django.core.management.base import BaseCommand
from django.db import transaction
from django.conf import settings

# Adjust these imports to match your app
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
    mc: str
    status: str
    ts: datetime
    btn: Optional[int] = None
    reason_id: Optional[int] = None


@dataclass
class RotationMsg:
    mc: str
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

        self.reason_map: Dict[int, int] = {}  # btn -> reason_id
        self.machine_map: Dict[str, Machine] = {}  # lowercase_mac -> Machine instance
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

    # ---------- Machine map ----------
    def refresh_machine_map(self):
        while not self.shutdown.is_set():
            try:
                with transaction.atomic():
                    rows = list(Machine.objects.filter(is_deleted=False).values("id", "mac_address"))
                    self.machine_map = {
                        r["mac_address"].lower(): Machine.objects.get(id=r["id"])
                        for r in rows
                    }
                LOG.info("Refreshed machine map: %d machines", len(self.machine_map))
            except Exception as e:
                LOG.error("Failed refreshing machine map: %s", e)
            for _ in range(MC_REFRESH_SEC * 10):  # refresh every 60 seconds in 0.1s increments
                if self.shutdown.is_set():
                    return
                time.sleep(0.1)

    # ---------- Reason map ----------
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

    # ---------- Handlers ----------
    def handle_mc_status(self, data: Dict[str, Any]) -> None:
        try:
            mc = str(data["mc"]).strip().lower()
            status = str(data["status"]).strip().lower()
            ts = epoch_ms_to_dt(int(data["timestamp"]))
        except Exception as e:
            LOG.error("Invalid mc-status payload: %s (data=%s)", e, data)
            self.stats["mc_status_bad"] += 1
            return

        machine = self.machine_map.get(mc)
        if not machine:
            LOG.warning("MC %s not found in machine map", mc)
            self.stats["mc_unknown"] += 1
            return

        try:
            with transaction.atomic():
                last_row = (
                    ProcessedNPT.objects.select_for_update(skip_locked=True)
                    .filter(mc_no=machine)
                    .order_by("-off_time")
                    .first()
                )

                if status == "off":
                    if not last_row or last_row.on_time is not None:
                        obj = ProcessedNPT(mc_no=machine, off_time=ts)
                        try:
                            self.q_off.put_nowait(obj)
                            self.stats["off_enqueued"] += 1
                        except Full:
                            LOG.error("Queue full: dropping OFF event mc=%s ts=%s", mc, ts.isoformat())
                            self.stats["off_dropped"] += 1
                    else:
                        LOG.info("Skipping OFF enqueue: last ON not closed for mc=%s", mc)

                elif status == "on":
                    if last_row and last_row.on_time is None:
                        last_row.on_time = ts
                        last_row.save(update_fields=["on_time"])
                        self.stats["on_closed"] += 1
                    else:
                        LOG.info("Skipping ON update: no row to update or on_time already set for mc=%s", mc)

                elif status == "btn":
                    try:
                        btn = int(data["btn"])
                    except Exception:
                        LOG.error("Invalid/missing btn in data: %s", data)
                        self.stats["btn_bad"] += 1
                        return

                    reason_id = self.reason_map.get(btn)
                    if reason_id is None:
                        LOG.warning("Btn %s not mapped to reason (mc=%s)", btn, mc)
                        self.stats["btn_unmapped"] += 1
                        return

                    if last_row and last_row.reason_id is None:
                        last_row.reason_id = reason_id
                        last_row.save(update_fields=["reason_id"])
                        self.stats["btn_applied"] += 1
                    else:
                        LOG.info("Skipping BTN update: no row or reason_id already set for mc=%s", mc)

        except Exception as e:
            LOG.exception("Error handling MC status event: %s", e)

    def handle_rotation(self, data: Dict[str, Any]) -> None:
        try:
            mc = str(data["mc"]).strip().lower()
            rotation = int(data["rotation"])
            ts = epoch_ms_to_dt(int(data["timestamp"]))
        except Exception as e:
            LOG.error("Invalid rotation payload: %s (data=%s)", e, data)
            self.stats["rotation_bad"] += 1
            return

        machine = self.machine_map.get(mc)
        if not machine:
            LOG.warning("Rotation MC %s not found in machine map", mc)
            self.stats["rotation_unknown"] += 1
            return

        msg = RotationMsg(mc=machine, rotation=rotation, ts=ts)
        try:
            self.q_rotation.put_nowait(msg)
            self.stats["rotation_enqueued"] += 1
        except Full:
            LOG.error("Queue full: dropping ROTATION mc=%s ts=%s", mc, ts.isoformat())
            self.stats["rotation_dropped"] += 1

    # ---------- Workers (flush & apply ON) ----------
    # Keep your previous worker_flush_off, worker_flush_rotation, worker_apply_on, flush, and stats code
    # unchanged, except ensure `mc_no` uses Machine instance

    # ---------- Lifecycle ----------
    def start(self):
        self.t_reason = threading.Thread(target=self.refresh_reason_map, name="reason-map", daemon=True)
        self.t_machine = threading.Thread(target=self.refresh_machine_map, name="machine-map", daemon=True)
        self.t_rot = threading.Thread(target=self.worker_flush_rotation, name="rot-worker", daemon=True)
        self.t_off = threading.Thread(target=self.worker_flush_off, name="off-worker", daemon=True)
        self.t_on = threading.Thread(target=self.worker_apply_on, name="on-worker", daemon=True)

        self.t_reason.start()
        self.t_machine.start()
        self.t_rot.start()
        self.t_off.start()
        self.t_on.start()

        def handle_sigterm(signum, frame):
            LOG.info("Received signal %s: shutting down...", signum)
            try:
                self.stop()
            except Exception:
                LOG.exception("Error while stopping on signal")
            try:
                sys.exit(0)
            except SystemExit:
                pass

        signal.signal(signal.SIGINT, handle_sigterm)
        signal.signal(signal.SIGTERM, handle_sigterm)

        self.client.connect(self.broker_host, self.broker_port, keepalive=self.keepalive)
        self.client.loop_forever(retry_first_connection=True)

    def stop(self):
        LOG.info("Stopping ingestor...")
        self.shutdown.set()
        try:
            self.client.loop_stop()
            self.client.disconnect()
        except Exception:
            LOG.exception("Error stopping MQTT client")

        for tname in ("t_rot", "t_off", "t_on", "t_reason", "t_machine"):
            t = getattr(self, tname, None)
            if t and isinstance(t, threading.Thread) and t.is_alive():
                try:
                    t.join(timeout=5.0)
                except Exception:
                    pass

        try:
            self.flush()
        except Exception:
            LOG.exception("Error during final flush")

        LOG.info("Ingestor stopped.")


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
