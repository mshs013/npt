from django.db import models
from django.conf import settings
from core.mixins import SoftDeleteModel
from django.utils import timezone

User = settings.AUTH_USER_MODEL

class NptReason(SoftDeleteModel):
    name = models.CharField(max_length=100)
    min_time = models.PositiveIntegerField(default=1)
    created_by = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_by')
    created_at = models.DateTimeField(default=timezone.now)
    updated_by = models.ForeignKey(User, on_delete=models.CASCADE, blank=True, null=True, related_name='updated_by')
    updated_at = models.DateTimeField(blank=True, null=True)

    class Meta: 
        verbose_name = "NPT Reason"
        verbose_name_plural = "NPT Reasons"

    def __str__(self):
        return self.name
