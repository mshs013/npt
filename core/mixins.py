# core/mixins.py
from django.db import models
from django.utils import timezone
from django.conf import settings
from django.dispatch import Signal, receiver
from django.db.models.signals import post_save
from core.managers import SoftDeleteManager, DeletedManager, GlobalManager
from core.signals import post_soft_delete, post_hard_delete, post_restore
from core.middleware import get_current_user

User = settings.AUTH_USER_MODEL

class SoftDeleteModel(models.Model):
    """
    Abstract model providing soft delete functionality.
    """
    is_deleted = models.BooleanField(default=False)
    deleted_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='%(class)s_deleted')
    deleted_at = models.DateTimeField(null=True, blank=True)

    objects = SoftDeleteManager()  # Manager for active objects
    deleted_objects = DeletedManager()  # Manager for soft-deleted objects
    global_objects = GlobalManager()  # Manager for all objects

    class Meta:
        abstract = True


    def delete(self, using=None, keep_parents=False, soft=True):
        """
        Soft delete or hard delete the object.
        """
        if soft:
            self.is_deleted = True
            self.deleted_by = get_current_user()  # Retrieve current user
            self.deleted_at = timezone.now()
            Signal.disconnect(post_save, sender=self.__class__)
            self.save()
            Signal.connect(post_save, receiver=receiver, sender=self.__class__)
            post_soft_delete.send(sender=self.__class__, instance=self)
        else:
            super().delete(using=using, keep_parents=keep_parents)
            post_hard_delete.send(sender=self.__class__, instance=self)

    def hard_delete(self, using=None, keep_parents=False):
        """
        Hard delete the object.
        """
        super().delete(using=using, keep_parents=keep_parents)
        post_hard_delete.send(sender=self.__class__, instance=self)

    def restore(self):
        """
        Restore the soft-deleted object.
        """
        self.is_deleted = False
        self.deleted_by = get_current_user()  # Retrieve current user
        self.deleted_at = None
        self.save()
        post_restore.send(sender=self.__class__, instance=self)

class CreatedInfoModel(models.Model):
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="%(class)s_created_by")
    created_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        abstract = True

class UpdatedInfoModel(models.Model):
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, editable=False, related_name="%(class)s_updated_by")
    updated_at = models.DateTimeField(null=True, blank=True, editable=False)

    class Meta:
        abstract = True