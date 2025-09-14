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
    

class CompanyScopedQuerySet(models.QuerySet):
    def for_companies(self, companies):
        """
        Accepts:
          - single Company instance or id,
          - iterable of instances/ids,
          - QuerySet/Manager of companies.
        Returns queryset filtered by company pk(s).
        """
        if companies is None:
            return self.none()

        # Normalize manager/queryset -> iterable
        if hasattr(companies, "all") and not isinstance(companies, (list, tuple, set)):
            companies_iter = companies.all()
        else:
            companies_iter = companies

        if not hasattr(companies_iter, "__iter__") or isinstance(companies_iter, (str, bytes)):
            companies_iter = [companies_iter]

        pks = []
        for c in companies_iter:
            if c is None:
                continue
            if hasattr(c, "pk"):
                pks.append(c.pk)
            else:
                try:
                    pks.append(int(c))
                except Exception:
                    continue

        if not pks:
            return self.none()

        return self.filter(company__pk__in=pks)

    def for_company(self, company):
        return self.for_companies(company)

    def for_user(self, user, allow_superuser=True):
        if user is None or not getattr(user, "is_authenticated", False):
            return self.none()

        if allow_superuser and getattr(user, "is_superuser", False):
            return self

        companies = None
        profile = getattr(user, "profile", None)
        if profile is not None and hasattr(profile, "company"):
            companies = profile.company.all()  # <--- use `company` not `companies`
        elif hasattr(user, "companies"):
            try:
                companies = user.companies.all()
            except Exception:
                companies = None

        if companies is None:
            from .models import Company
            companies = Company.objects.filter(members=user)

        if not companies:
            return self.none()

        return self.for_companies(companies)

class CompanyScopedManager(models.Manager):
    def get_queryset(self):
        return CompanyScopedQuerySet(self.model, using=self._db)

    def for_companies(self, companies):
        return self.get_queryset().for_companies(companies)

    def for_company(self, company):
        return self.get_queryset().for_company(company)

    def for_user(self, user, allow_superuser=True):
        return self.get_queryset().for_user(user, allow_superuser=allow_superuser)

    def for_request(self, request, allow_superuser=True):
        """
        Preference order:
        1) request.active_company if middleware set it
        2) request.session['active_company_id']
        3) fallback to user's memberships (for_user)
        """
        # 1) middleware-provided attribute (fast, avoids extra DB hit)
        active = getattr(request, "active_company", None)
        if active is not None:
            return self.for_company(active)

        # 2) session
        session = getattr(request, "session", None)
        if session is not None:
            cid = session.get("active_company_id")
            if cid:
                return self.for_companies(cid)

        # 3) fallback to user membership
        user = getattr(request, "user", None)
        return self.for_user(user, allow_superuser=allow_superuser)