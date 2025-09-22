import logging
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core.models import MachineStatus, ProcessedNPT, Machine, ProcessorCursor

LOG = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Process new MachineStatus logs into ProcessedNPT handling btn placement"

    def add_arguments(self, parser):
        parser.add_argument("--machine", type=int, help="Process only one machine.")

    def handle(self, *args, **options):
        machine_id = options.get("machine")
        machines = Machine.objects.filter(id=machine_id) if machine_id else Machine.objects.all()
        if not machines.exists():
            self.stdout.write(self.style.ERROR("No machines found."))
            return

        for machine in machines:
            self.stdout.write(f"Processing machine {machine.id} ({machine})...")
            self.process_machine(machine)

    @transaction.atomic
    def process_machine(self, machine):
        measurement = f"machine_status_{machine.id}"
        cursor, _ = ProcessorCursor.objects.get_or_create(
            measurement=measurement, defaults={"last_timestamp": None}
        )

        qs = MachineStatus.objects.filter(machine=machine)
        if cursor.last_timestamp:
            qs = qs.filter(status_time__gt=cursor.last_timestamp)

        logs = list(qs.order_by("status_time"))
        if not logs:
            LOG.debug("No new logs for machine=%s", machine.id)
            return

        # Get the last open downtime if exists
        try:
            last_processed = ProcessedNPT.objects.filter(machine=machine).latest("off_time")
            open_off = None if last_processed.on_time else last_processed.off_time
            reason = last_processed.reason if open_off else None
        except ProcessedNPT.DoesNotExist:
            open_off = None
            reason = None

        for log in logs:
            if log.status == "off":
                open_off = log.status_time
                reason = None

            elif log.status == "btn":
                if open_off:
                    # During downtime: always use as reason
                    reason = log.reason
                else:
                    # After downtime: only use if previous downtime has no reason
                    last_downtime = ProcessedNPT.objects.filter(machine=machine).order_by("-off_time").first()
                    if last_downtime and not last_downtime.reason:
                        last_downtime.reason = log.reason
                        last_downtime.save(update_fields=["reason"])
                        LOG.info(
                            "Updated previous downtime reason: machine=%s off=%s reason=%s",
                            machine.id,
                            last_downtime.off_time,
                            log.reason.id,
                        )

            elif log.status == "on":
                if open_off:
                    # Close downtime
                    ProcessedNPT.objects.update_or_create(
                        machine=machine,
                        off_time=open_off,
                        defaults={"on_time": log.status_time, "reason": reason},
                    )
                    LOG.info(
                        "Processed downtime: machine=%s off=%s on=%s reason=%s",
                        machine.id,
                        open_off,
                        log.status_time,
                        reason.id if reason else None,
                    )
                    open_off = None
                    reason = None

            # Advance cursor every log
            cursor.last_timestamp = log.status_time

        # If downtime still open, create/update without on_time
        if open_off:
            ProcessedNPT.objects.update_or_create(
                machine=machine,
                off_time=open_off,
                defaults={"on_time": None, "reason": reason},
            )
            LOG.info(
                "Open downtime active: machine=%s off=%s reason=%s",
                machine.id,
                open_off,
                reason.id if reason else None,
            )

        cursor.save(update_fields=["last_timestamp", "updated_at"])
