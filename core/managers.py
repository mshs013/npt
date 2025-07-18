from django.contrib.auth.base_user import BaseUserManager
from django.utils.translation import gettext_lazy as _
from django.db import models
from datetime import datetime


class UserManager(BaseUserManager):
    """
    Custom user model manager where email is the unique identifiers
    for authentication instead of usernames.
    """
    def create_user(self, email, password, **extra_fields):
        """
        Create and save a user with the given email and password.
        """
        if not email:
            raise ValueError(_("The Email must be set"))
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save()
        return user

    def create_superuser(self, email, password, **extra_fields):
        """
        Create and save a SuperUser with the given email and password.
        """
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)

        if extra_fields.get("is_staff") is not True:
            raise ValueError(_("Superuser must have is_staff=True."))
        if extra_fields.get("is_superuser") is not True:
            raise ValueError(_("Superuser must have is_superuser=True."))
        return self.create_user(email, password, **extra_fields)


class SoftDeleteManager(models.Manager):
    """
    Manager for soft-deleted models. Excludes soft-deleted objects by default.
    """
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)

    def delete(self, user=None, soft=True):
        """
        Soft delete or hard delete objects in the queryset.
        """
        if soft:
            count = self.get_queryset().update(is_deleted=True, deleted_by=user, deleted_at=datetime.now())
            return count
        else:
            count = super().get_queryset().delete()
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
        count = self.get_queryset().update(is_deleted=False, deleted_by=None, deleted_at=None)
        return count

class DeletedManager(models.Manager):
    """
    Manager for accessing soft-deleted objects.
    """
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=True)

class GlobalManager(models.Manager):
    """
    Manager for accessing all objects, including soft-deleted ones.
    """
    def get_queryset(self):
        return super().get_queryset()