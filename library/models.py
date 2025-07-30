from django.db import models
from django.conf import settings
from core.mixins import CreatedInfoModel, UpdatedInfoModel, SoftDeleteModel

User = settings.AUTH_USER_MODEL

class NptReason(CreatedInfoModel, UpdatedInfoModel, SoftDeleteModel):
    name = models.CharField(max_length=100)
    min_time = models.PositiveIntegerField(default=1)
    remote_num = models.PositiveIntegerField(default=1, unique=True)

    class Meta: 
        verbose_name = "NPT Reason"
        verbose_name_plural = "NPT Reasons"

    def __str__(self):
        return self.name
