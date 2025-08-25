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

# Adjust this import to match your app name if not 'library'
from library.models import NptReason, ProcessedNPT, RotationStatus

import paho.mqtt.client as mqtt

LOG = logging.getLogger("mqtt_ingestor")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)

# Timezone set
BD_TZ = ZoneInfo("Asia/Dhaka")

# Topics
TOPIC_MC_STATUS = "npt/mc-status"
TOPIC_ROTATION = "npt/rotation-data"

# Ingestion tuning
DEFAULT_QOS = 1
QUEUE_MAXSIZE = 100_000  # internal buffer; adjust for your RAM
BATCH_SIZE_ROTATION = 50  # how many rotation rows to insert per flush
BATCH_SIZE_OFF = 50  # how many 'off' rows to insert per flush
FLUSH_INTERVAL_SEC = 5.0  # force flush every X seconds
REASON_REFRESH_SEC = 3600  # reload reason map every X seconds
STATS_INTERVAL_SEC = 5  # print ingestion stats interval


# --------- Helpers ---------
def epoch_ms_to_dt(ts_ms: int) -> datetime:
    """Convert device epoch milliseconds to a datetime."""
    try:
        dt = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc)
    except Exception:
        # Fallback if a device sends seconds instead of ms
        if ts_ms < 20_000_000_000:
            dt = datetime.fromtimestamp(ts_ms, tz=timezone.utc)
        else:
            raise
    # Convert to Asia/Dhaka, then drop tzinfo (since USE_TZ=False)
    return dt.astimezone(BD_TZ).replace(tzinfo=None)


# Dataclasses used for queues
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


# --------- Ingestor ---------
class Ingestor:
    def __init__(
        self,
        broker_host: str,
        broker_port: int,
        username: str,
        password: str,
        qos: int = DEFAULT_QOS,
        client_id: Optional[str] = None,
    ) -> None:
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.username = username
        self.password = password
        self.qos = qos
        self.client_id = client_id or f"mqtt-ingestor-{int(time.time())}"
        self.shutdown = ShutdownFlag()

        # Queues
        self.q_rotation: "Queue[RotationMsg]" = Queue(maxsize=QUEUE_MAXSIZE)
        self.q_off: "Queue[ProcessedNPT]" = Queue(maxsize=QUEUE_MAXSIZE)
        self.q_on: "Queue[McStatusMsg]" = Queue(maxsize=QUEUE_MAXSIZE)

        # State / stats
        self.reason_map: Dict[int, int] = {}
        self.stats = defaultdict(int)
        self.last_stats_time = time.time()

        # MQTT client
        self.client = mqtt.Client(
            client_id=self.client_id, clean_session=False, protocol=mqtt.MQTTv311
        )
        self.client.username_pw_set(self.username, self.password)
        self.client.enable_logger(logging.getLogger("paho.mqtt.client"))
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        self.client.on_disconnect = self.on_disconnect

        # Throughput tuning
        try:
            self.client.max_inflight_messages_set(2000)
            self.client.max_queued_messages_set(50000)
        except Exception:
            pass
        self.client.reconnect_delay_set(min_delay=1, max_delay=30)
        self.keepalive = 60

    # ----- MQTT callbacks -----
    def on_connect(self, client, userdata, flags, rc, properties=None):
        if rc == 0:
            LOG.info(
                "Connected to MQTT %s:%s as %s", self.broker_host, self.broker_port, self.client_id
            )
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

    # ----- Handlers -----
    def handle_mc_status(self, data: Dict[str, Any]) -> None:
        try:
            mc = str(data["mc"]).strip()
            status = str(data["status"]).strip().lower()
            ts_ms = int(data["timestamp"])
            ts = epoch_ms_to_dt(ts_ms)
        except Exception as e:
            LOG.error("Invalid mc-status payload: %s (data=%s)", e, data)
            self.stats["mc_status_bad"] += 1
            return

        if status == "off":
            # Always create a new row with off_time
            obj = ProcessedNPT(mc_no=mc, off_time=ts)
            try:
                self.q_off.put_nowait(obj)
                self.stats["off_enqueued"] += 1
            except Full:
                LOG.error("Queue full: dropping OFF event mc=%s ts=%s", mc, ts.isoformat())
                self.stats["off_dropped"] += 1
            return

        if status in ("on", "btn"):
            # Wrap in transaction to safely use select_for_update
            try:
                with transaction.atomic():
                    last_row = (
                        ProcessedNPT.objects
                        .select_for_update(skip_locked=True)
                        .filter(mc_no=mc)
                        .order_by("-off_time")
                        .first()
                    )

                    if status == "on":
                        if last_row and last_row.on_time is None:
                            last_row.on_time = ts
                            last_row.save(update_fields=["on_time"])
                            self.stats["on_closed"] += 1
                        else:
                            # ON without prior OFF → create row
                            obj = ProcessedNPT(mc_no=mc, on_time=ts, off_time=None)
                            self.q_off.put_nowait(obj)
                            self.stats["on_created"] += 1

                    elif status == "btn":
                        try:
                            btn = int(data["btn"])
                        except Exception:
                            LOG.error("Btn status missing/invalid btn (data=%s)", data)
                            self.stats["btn_bad"] += 1
                            return

                        reason_id = self.reason_map.get(btn)
                        if reason_id is None:
                            LOG.warning("Btn %s not mapped to reason (mc=%s)", btn, mc)
                            self.stats["btn_unmapped"] += 1

                        if last_row:
                            if last_row.reason_id is None:
                                last_row.reason_id = reason_id
                                last_row.save(update_fields=["reason_id"])
                                self.stats["btn_applied"] += 1
                            else:
                                self.stats["btn_skipped"] += 1
                        else:
                            # BTN without prior OFF → create row with reason_id
                            obj = ProcessedNPT(mc_no=mc, reason_id=reason_id, off_time=None)
                            self.q_off.put_nowait(obj)
                            self.stats["btn_created"] += 1
            except Exception as e:
                LOG.exception("Error handling ON/BTN event: %s", e)

    def handle_rotation(self, data: Dict[str, Any]) -> None:
        try:
            mc = str(data["mc"]).strip()
            rotation = int(data["rotation"])
            ts_ms = int(data["timestamp"])
            ts = epoch_ms_to_dt(ts_ms)
        except Exception as e:
            LOG.error("Invalid rotation payload: %s (data=%s)", e, data)
            self.stats["rotation_bad"] += 1
            return

        msg = RotationMsg(mc=mc, rotation=rotation, ts=ts)
        try:
            self.q_rotation.put_nowait(msg)
            self.stats["rotation_enqueued"] += 1
        except Full:
            LOG.error("Queue full: dropping ROTATION mc=%s ts=%s", mc, ts.isoformat())
            self.stats["rotation_dropped"] += 1

    # ----- DB workers -----
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

    def worker_flush_rotation(self):
        batch: List[RotationMsg] = []
        last_flush = time.time()
        while not self.shutdown.is_set():
            timeout = max(0.0, FLUSH_INTERVAL_SEC - (time.time() - last_flush))
            try:
                item = self.q_rotation.get(timeout=timeout)
                batch.append(item)
            except Empty:
                pass

            if len(batch) >= BATCH_SIZE_ROTATION or (batch and time.time() - last_flush >= FLUSH_INTERVAL_SEC):
                try:
                    objs = [RotationStatus(mc_no=x.mc, count=x.rotation, count_time=x.ts) for x in batch]
                    RotationStatus.objects.bulk_create(objs, ignore_conflicts=True, batch_size=1000)
                    self.stats["rotation_flushed"] += len(objs)
                except Exception as e:
                    LOG.error("Rotation bulk_create failed: %s", e)
                batch.clear()
                last_flush = time.time()

        if batch:
            try:
                objs = [RotationStatus(mc_no=x.mc, count=x.rotation, count_time=x.ts) for x in batch]
                RotationStatus.objects.bulk_create(objs, ignore_conflicts=True, batch_size=1000)
                self.stats["rotation_flushed"] += len(objs)
            except Exception as e:
                LOG.error("Rotation final flush failed: %s", e)

    def worker_flush_off(self):
        batch: List[ProcessedNPT] = []
        last_flush = time.time()
        while not self.shutdown.is_set():
            timeout = max(0.0, FLUSH_INTERVAL_SEC - (time.time() - last_flush))
            try:
                item = self.q_off.get(timeout=timeout)
                batch.append(item)
            except Empty:
                pass

            if len(batch) >= BATCH_SIZE_OFF or (batch and time.time() - last_flush >= FLUSH_INTERVAL_SEC):
                try:
                    ProcessedNPT.objects.bulk_create(batch, ignore_conflicts=True, batch_size=500)
                    self.stats["off_flushed"] += len(batch)
                except Exception as e:
                    LOG.error("OFF bulk_create failed: %s", e)
                batch.clear()
                last_flush = time.time()

        if batch:
            try:
                ProcessedNPT.objects.bulk_create(batch, ignore_conflicts=True, batch_size=500)
                self.stats["off_flushed"] += len(batch)
            except Exception as e:
                LOG.error("OFF final flush failed: %s", e)

    def worker_apply_on(self):
        while not self.shutdown.is_set():
            try:
                msg = self.q_on.get(timeout=0.2)
            except Empty:
                continue
            try:
                with transaction.atomic():
                    rec = (
                        ProcessedNPT.objects
                        .select_for_update(skip_locked=True)
                        .filter(mc_no=msg.mc, on_time__isnull=True)
                        .order_by("-off_time")
                        .first()
                    )
                    if rec:
                        if msg.ts >= rec.off_time:
                            rec.on_time = msg.ts
                            if getattr(msg, "reason_id", None) is not None:
                                rec.reason_id = msg.reason_id
                                rec.save(update_fields=["on_time", "reason_id"])
                            else:
                                rec.save(update_fields=["on_time"])
                            self.stats["on_closed"] += 1
                        else:
                            self.stats["on_out_of_order"] += 1
                    else:
                        self.stats["on_no_open"] += 1
            except Exception as e:
                LOG.error("Applying ON failed for mc=%s: %s", msg.mc, e)
                self.stats["on_failed"] += 1

    # ----- Final flush helpers -----
    def flush(self):
        LOG.info("Starting final flush of queues...")

        batch_rot: List[RotationMsg] = []
        while True:
            try:
                batch_rot.append(self.q_rotation.get_nowait())
            except Empty:
                break
        if batch_rot:
            objs = [RotationStatus(mc_no=x.mc, count=x.rotation, count_time=x.ts) for x in batch_rot]
            try:
                RotationStatus.objects.bulk_create(objs, ignore_conflicts=True, batch_size=1000)
                self.stats["rotation_flushed"] += len(objs)
            except Exception as e:
                LOG.exception("Rotation flush failed: %s", e)

        batch_off: List[ProcessedNPT] = []
        while True:
            try:
                batch_off.append(self.q_off.get_nowait())
            except Empty:
                break
        if batch_off:
            try:
                ProcessedNPT.objects.bulk_create(batch_off, ignore_conflicts=True, batch_size=500)
                self.stats["off_flushed"] += len(batch_off)
            except Exception as e:
                LOG.exception("OFF flush failed: %s", e)

        while True:
            try:
                msg = self.q_on.get_nowait()
            except Empty:
                break
            try:
                with transaction.atomic():
                    rec = (
                        ProcessedNPT.objects
                        .select_for_update(skip_locked=True)
                        .filter(mc_no=msg.mc, on_time__isnull=True)
                        .order_by("-off_time")
                        .first()
                    )
                    if rec and msg.ts >= rec.off_time:
                        rec.on_time = msg.ts
                        if getattr(msg, "reason_id", None) is not None:
                            rec.reason_id = msg.reason_id
                            rec.save(update_fields=["on_time", "reason_id"])
                        else:
                            rec.save(update_fields=["on_time"])
                        self.stats["on_closed"] += 1
            except Exception as e:
                LOG.exception("Failed applying ON during final flush: %s", e)

        LOG.info("Final flush complete.")

    # ----- Stats -----
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

    # ----- Lifecycle -----
    def start(self):
        self.t_reason = threading.Thread(target=self.refresh_reason_map, name="reason-map", daemon=True)
        self.t_rot = threading.Thread(target=self.worker_flush_rotation, name="rot-worker", daemon=True)
        self.t_off = threading.Thread(target=self.worker_flush_off, name="off-worker", daemon=True)
        self.t_on = threading.Thread(target=self.worker_apply_on, name="on-worker", daemon=True)
        self.t_reason.start()
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

        for tname in ("t_rot", "t_off", "t_on", "t_reason"):
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
