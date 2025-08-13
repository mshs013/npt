import os
import django
from datetime import datetime, timezone
from dateutil import parser
from influxdb_client import InfluxDBClient
from dotenv import load_dotenv

# -------------------- Debug Setup --------------------
DEBUG = True  # Set False to disable debug prints

# -------------------- Load env --------------------
load_dotenv()

INFLUX_URL = os.getenv("INFLUX_URL")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN")
INFLUX_ORG = os.getenv("INFLUX_ORG")
INFLUX_BUCKET = os.getenv("INFLUX_BUCKET")

# -------------------- Django Setup --------------------
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'npt.settings')
django.setup()

from library.models import ProcessedNPT, RotationStatus, NptReason, ProcessorCursor

# -------------------- InfluxDB Setup --------------------
client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
query_api = client.query_api()

# -------------------- Helpers --------------------
def parse_ts(ts):
    """Parse ISO timestamps to datetime."""
    if isinstance(ts, datetime):
        return ts
    try:
        return parser.isoparse(ts)
    except Exception as e:
        print_entry("WARN", f"Failed to parse timestamp {ts}: {e}")
        return datetime.now()

def to_naive(dt):
    """Convert aware datetime to naive UTC if USE_TZ=False."""
    if dt is None:
        return None
    if dt.tzinfo is not None:
        return dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt

def print_entry(level, message):
    """Print messages depending on level and DEBUG flag."""
    if level.upper() == "DEBUG" and not DEBUG:
        return
    print(f"[{level.upper()}] {message}")

def get_cursor(measurement):
    obj = ProcessorCursor.objects.filter(measurement=measurement).first()
    return obj.last_timestamp if obj else None

def set_cursor(measurement, ts):
    obj, _ = ProcessorCursor.objects.get_or_create(measurement=measurement)
    obj.last_timestamp = ts
    obj.save()

# -------------------- NPT Processing --------------------
def process_npt():
    print_entry("INFO", "Starting NPT processing...")

    cursor_ts = get_cursor('npt')
    query = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -2m)
      |> filter(fn: (r) => r._measurement == "npt")
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
    '''
    tables = query_api.query(org=INFLUX_ORG, query=query)

    npt_data = []
    for table in tables:
        for record in table.records:
            raw_ts = record['_time']
            ts = to_naive(parse_ts(raw_ts))
            if cursor_ts and ts <= cursor_ts:
                continue
            npt_data.append({
                "mc_no": record.get('mc_no'),
                "status": record.get('status'),
                "reason_id": record.get('btn'),
                "timestamp": ts
            })

    npt_data.sort(key=lambda x: x["timestamp"] or datetime.min)

    last_ts = cursor_ts
    reasons = {r.remote_num: r for r in NptReason.objects.filter(is_deleted=False)}

    for entry in npt_data:
        mc_no = entry["mc_no"]
        status = (entry["status"] or "").lower()
        reason_id = entry["reason_id"]
        ts = entry["timestamp"]

        if ts and (last_ts is None or ts > last_ts):
            last_ts = ts

        try:
            reason_id = int(reason_id) if reason_id is not None else None
        except Exception:
            reason_id = None
        reason = reasons.get(reason_id)

        if status.lower() == "off":
            obj, created = ProcessedNPT.objects.get_or_create(
                mc_no=mc_no,
                off_time=ts,
                defaults={"reason": None}
            )
            print_entry("NPT OFF", {"mc_no": mc_no, "ts": ts, "created": created})

        elif status.lower() == "on":
            obj = ProcessedNPT.objects.filter(
                mc_no=mc_no, on_time__isnull=True, off_time__lte=ts
            ).order_by("-off_time").first()
            if obj and obj.on_time is None:
                obj.on_time = ts
                obj.save()
                print_entry("NPT ON", {"mc_no": mc_no, "ts": ts})

        elif status.lower() == "btn":
            obj = ProcessedNPT.objects.filter(
                mc_no=mc_no, reason__isnull=True, off_time__lte=ts
            ).order_by("-off_time").first()
            if obj:
                obj.reason = reason
                obj.save()
                print_entry("NPT BUTTON", {"mc_no": mc_no, "reason": reason, "reason_id": reason_id})

    if last_ts:
        set_cursor('npt', last_ts)

    print_entry("INFO", "NPT processing completed.")

# -------------------- Rotation Processing --------------------
def process_rotation():
    print_entry("INFO", "Starting rotation processing...")

    cursor_ts = get_cursor('rotation')
    query = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -2m)
      |> filter(fn: (r) => r._measurement == "rotation")
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
    '''
    tables = query_api.query(org=INFLUX_ORG, query=query)

    last_ts = cursor_ts
    for table in tables:
        for record in table.records:
            if 'rotation' not in record.values or record['rotation'] is None:
                continue
            mc_no = record.get('mc_no')
            ts = to_naive(parse_ts(record['_time']))
            if cursor_ts and ts <= cursor_ts:
                continue
            count = int(record['rotation'])

            obj, created = RotationStatus.objects.get_or_create(
                mc_no=mc_no,
                count_time=ts,
                defaults={"count": count}
            )
            print_entry("ROTATION", {"mc_no": mc_no, "ts": ts, "count": count, "created": created})

            if last_ts is None or ts > last_ts:
                last_ts = ts

    if last_ts:
        set_cursor('rotation', last_ts)

    print_entry("INFO", "Rotation processing completed.")

# -------------------- Print all InfluxDB records --------------------
def print_all_records():
    print_entry("INFO", "Fetching NPT records...")
    npt_query = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -2d)
      |> filter(fn: (r) => r._measurement == "npt")
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
    '''
    npt_tables = query_api.query(org=INFLUX_ORG, query=npt_query)
    for table in npt_tables:
        for record in table.records:
            print_entry("NPT RECORD", {
                "mc_no": record['mc_no'],
                "status": record['status'] if 'status' in record.values else None,
                "reason_id": record['btn'] if 'btn' in record.values else None,
                "timestamp": record['_time']
            })

    print_entry("INFO", "Fetching Rotation records...")
    rot_query = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -2d)
      |> filter(fn: (r) => r._measurement == "rotation")
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
    '''
    rot_tables = query_api.query(org=INFLUX_ORG, query=rot_query)
    for table in rot_tables:
        for record in table.records:
            print_entry("ROTATION RECORD", {
                "mc_no": record['mc_no'],
                "count": record['rotation'] if 'rotation' in record.values else None,
                "timestamp": record['_time']
            })

# -------------------- Main --------------------
if __name__ == "__main__":
    #print("[INFO] Printing all InfluxDB records for debug")
    #print_all_records()
    print("[INFO] Starting InfluxDB to Django processing script")
    process_npt()
    process_rotation()
    print("[INFO] Processing finished successfully")
