from django.db import models
from core.mixins import CompanyScopedModel, CreatedInfoModel, UpdatedInfoModel, SoftDeleteModel
    
class Shift(CompanyScopedModel, CreatedInfoModel, UpdatedInfoModel, SoftDeleteModel):
    name = models.CharField(max_length=150, unique=True)
    start_time = models.TimeField()
    end_time = models.TimeField()

    class Meta:
        verbose_name = "Shift"
        verbose_name_plural = "Shifts"
        permissions = [
            ("trashed_shift", "Can view trashed Shift"),
            ("restore_shift", "Can view restore Shift"),
        ]

    def __str__(self):
        return f"{self.name}"