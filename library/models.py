from django.db import models
from django.conf import settings
from core.mixins import CreatedInfoModel, UpdatedInfoModel, SoftDeleteModel
from django.db.models import Q

User = settings.AUTH_USER_MODEL

class NptReason(CreatedInfoModel, UpdatedInfoModel, SoftDeleteModel):
    name = models.CharField(max_length=100)
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
