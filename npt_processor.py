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

from library.models import ProcessedNPT, RotationStatus, NptReason

# -------------------- InfluxDB Setup --------------------
client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG)
query_api = client.query_api()

# -------------------- Helpers --------------------
def parse_ts(ts):
    if isinstance(ts, datetime):
        return ts
    try:
        return parser.isoparse(ts)
    except Exception as e:
        print_entry("WARN", f"Failed to parse timestamp {ts}: {e}")
        return datetime.now(timezone.utc)

def print_entry(level, message):
    """Print messages depending on level and DEBUG flag."""
    if level.upper() == "DEBUG" and not DEBUG:
        return
    print(f"[{level.upper()}] {message}")

# -------------------- NPT Processing --------------------
def process_npt():
    print_entry("INFO", "Starting NPT processing...")
    query = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -2d)
      |> filter(fn: (r) => r._measurement == "npt")
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
    '''
    tables = query_api.query(org=INFLUX_ORG, query=query)
    print_entry("INFO", f"Fetched {len(tables)} NPT tables from InfluxDB")

    reasons = {r.remote_num: r for r in NptReason.objects.filter(is_deleted=False)}
    print_entry("INFO", f"Loaded {len(reasons)} active NptReason records")

    for remote_num, reason in reasons.items():
        print_entry("INFO", f"remote_num={remote_num}, id={reason.id}, name={reason.name}, min_time={reason.min_time}")

    npt_data = []
    for table in tables:
        for record in table.records:
            entry = {
                "mc_no": record['mc_no'],
                "status": record['status'] if 'status' in record.values else None,
                "reason_id": record['btn'] if 'btn' in record.values else None,
                "timestamp": record['_time']
            }
            print_entry("DEBUG", entry)
            npt_data.append(entry)

    npt_data.sort(key=lambda x: x["timestamp"])

    for entry in npt_data:
        mc_no = entry["mc_no"]
        status = entry["status"]
        reason_id = entry["reason_id"]
        ts = parse_ts(entry["timestamp"])

        if reason_id is not None:
            try:
                reason_id = int(reason_id)  # cast to int
            except ValueError:
                reason_id = None
        reason = reasons.get(reason_id)

        if status.lower() == "off":
            obj, created = ProcessedNPT.objects.update_or_create(
                mc_no=mc_no,
                on_time__isnull=True,
                defaults={"off_time": ts, "reason": None}
            )
            print_entry("NPT OFF", {"mc_no": mc_no, "ts": ts, "created": created})
        elif status.lower() == "on":
            obj = ProcessedNPT.objects.filter(mc_no=mc_no, on_time__isnull=True).order_by("-off_time").first()
            if obj:
                obj.on_time = ts
                obj.save()
                print_entry("NPT ON", {"mc_no": mc_no, "ts": ts})
        elif status.lower() in ["button pressed", "btn"]:
            obj = ProcessedNPT.objects.filter(mc_no=mc_no, reason__isnull=True).order_by("-off_time").first()
            if obj:
                obj.reason = reason
                obj.save()
                print_entry("NPT BUTTON", {"mc_no": mc_no, "reason": reason, "reason_id": reason_id})

    print_entry("INFO", "NPT processing completed.")

# -------------------- Rotation Processing --------------------
def process_rotation():
    print_entry("INFO", "Starting rotation processing...")
    query = f'''
    from(bucket: "{INFLUX_BUCKET}")
      |> range(start: -2d)
      |> filter(fn: (r) => r._measurement == "rotation")
      |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")
    '''
    tables = query_api.query(org=INFLUX_ORG, query=query)
    print_entry("INFO", f"Fetched {len(tables)} rotation tables from InfluxDB")

    for table in tables:
        for record in table.records:
            if 'rotation' not in record.values or record['rotation'] is None:
                print_entry("SKIP ROTATION", {"mc_no": record['mc_no'], "timestamp": record['_time'], "reason": "rotation is null"})
                continue

            mc_no = record['mc_no']
            ts = parse_ts(record['_time'])
            count = record['rotation']

            obj, created = RotationStatus.objects.update_or_create(
                mc_no=mc_no,
                count_time=ts,
                defaults={"count": count}
            )
            print_entry("ROTATION", {"mc_no": mc_no, "ts": ts, "count": count, "created": created})

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
