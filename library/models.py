from django.db import models
from django.conf import settings
from core.mixins import CreatedInfoModel, UpdatedInfoModel, SoftDeleteModel
from django.db.models import Q
from datetime import datetime

User = settings.AUTH_USER_MODEL

class NptReason(CreatedInfoModel, UpdatedInfoModel, SoftDeleteModel):
    name = models.CharField(max_length=150)
    min_time = models.PositiveIntegerField(default=1)
    remote_num = models.PositiveIntegerField()

    class Meta: 
        verbose_name = "NPT Reason"
        verbose_name_plural = "NPT Reasons"
        constraints = [
            models.UniqueConstraint(
                fields=['remote_num'],
                condition=Q(is_deleted=False),
                name='unique_remote_num_not_deleted'
            )
        ]
        permissions = [
            ("trashed_nptreason", "Can view trashed NPT Reasons"),
        ]

    def __str__(self):
        return self.name

class ProcessedNPT(models.Model):
    mc_no = models.CharField(max_length=50)
    reason = models.ForeignKey(
        NptReason,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    off_time = models.DateTimeField()
    on_time = models.DateTimeField(null=True, blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['mc_no', 'off_time'], name='unique_mc_off_time')
        ]

    def get_duration(self):
        """
        Returns duration as timedelta:
        - If on_time exists: on_time - off_time
        - Else: current time - off_time
        """
        now = datetime.now()  # naive
        if self.on_time:
            return self.on_time - self.off_time
        return now - self.off_time

    def __str__(self):
        return f"{self.mc_no}"

class RotationStatus(models.Model):
    mc_no = models.CharField(max_length=50)
    count = models.IntegerField()
    count_time = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['mc_no', 'count_time'], name='unique_mc_count_time')
        ]

class ProcessorCursor(models.Model):
    """
    Stores the last processed timestamp for each Influx measurement
    to prevent reprocessing the same records.
    """
    measurement = models.CharField(max_length=50, unique=True)
    last_timestamp = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.measurement} → {self.last_timestamp}"
    
class Company(CreatedInfoModel, UpdatedInfoModel, SoftDeleteModel):
    name = models.CharField(max_length=150, unique=True)

    def __str__(self):
        return f"{self.name}"
    
class Building(CreatedInfoModel, UpdatedInfoModel, SoftDeleteModel):
    name = models.CharField(max_length=150, unique=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="building_company")

    def __str__(self):
        return f"{self.name}"
    
class Floor(CreatedInfoModel, UpdatedInfoModel, SoftDeleteModel):
    name = models.CharField(max_length=150, unique=True)
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name="floor_building")

    def __str__(self):
        return f"{self.name}"
    
class Block(CreatedInfoModel, UpdatedInfoModel, SoftDeleteModel):
    name = models.CharField(max_length=150, unique=True)
    floor = models.ForeignKey(Floor, on_delete=models.CASCADE, related_name="block_floor")

    def __str__(self):
        return f"{self.name}"
    
class MachineType(CreatedInfoModel, UpdatedInfoModel, SoftDeleteModel):
    name = models.CharField(max_length=150, unique=True)

    class Meta: 
        verbose_name = "Machine Type"
        verbose_name_plural = "Machine Types"

    def __str__(self):
        return f"{self.name}"
    
class Shift(CreatedInfoModel, UpdatedInfoModel, SoftDeleteModel):
    name = models.CharField(max_length=150, unique=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="shift_company")

    def __str__(self):
        return f"{self.name}"