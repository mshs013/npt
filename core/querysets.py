# ocmscore/querysets.py
from django.db import models
from django.utils import timezone
from .signals import post_soft_delete, post_hard_delete, post_restore

class SoftDeleteQuerySet(models.QuerySet):
    def delete(self, user=None, soft=True):
        if soft:
            count = self.update(is_deleted=True, deleted_by=user, deleted_at=timezone.now())
            for obj in self:
                post_soft_delete.send(sender=obj.__class__, instance=obj, user=user)
            return count
        else:
            count = super().delete()
            for obj in self:
                post_hard_delete.send(sender=obj.__class__, instance=obj, user=user)
            return count

    def hard_delete(self, user=None):
        """
        Perform a hard delete on all objects in the queryset.
        """
        return self.delete(user=user, soft=False)

    def restore(self, user=None):
        """
        Restore all soft-deleted objects in the queryset.
        """
        count = self.update(is_deleted=False, deleted_by=None, deleted_at=None)
        for obj in self:
            post_restore.send(sender=obj.__class__, instance=obj, user=user)
        return count
