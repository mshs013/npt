from django.db import models
from core.models import Company
from core.mixins import CreatedInfoModel, UpdatedInfoModel, SoftDeleteModel
    
class Shift(CreatedInfoModel, UpdatedInfoModel, SoftDeleteModel):
    name = models.CharField(max_length=150, unique=True)
    start_time = models.TimeField()
    end_time = models.TimeField()
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="shift_company")

    class Meta:
        verbose_name = "Shift"
        verbose_name_plural = "Shifts"
        permissions = [
            ("trashed_shift", "Can view trashed Shift"),
            ("restore_shift", "Can view restore Shift"),
        ]

    def __str__(self):
        return f"{self.name}"