from django.db import models
from django.conf import settings
from core.mixins import CreatedInfoModel, UpdatedInfoModel, SoftDeleteModel
from django.db.models import Q
from datetime import datetime, timezone

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

    def get_duration(self):
        """
        Returns duration as timedelta:
        - If on_time exists: on_time - off_time
        - Else: current time - off_time
        """
        if self.on_time:
            return self.on_time - self.off_time
        return datetime.now(timezone.utc) - self.off_time

    def __str__(self):
        return f"{self.mc_no}"

class RotationStatus(models.Model):
    mc_no = models.CharField(max_length=50)
    count = models.IntegerField()
    count_time = models.DateTimeField()