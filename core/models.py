from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, Permission
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models.signals import post_save
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.html import mark_safe
from django.urls import reverse
from django.conf import settings
from django.core.mail import send_mail
from core.mixins import CreatedInfoModel, UpdatedInfoModel, SoftDeleteModel

from core.managers import UserManager
User = settings.AUTH_USER_MODEL

ACTION_TYPES = [
    ('CREATE', 'Create'),
    ('UPDATE', 'Update'),
    ('DELETE', 'Delete'),
    ('RESTORE', 'Restore'),
    ('LOGIN', 'Login'),
    ('LOGIN_FAILED', 'Login Failed'),
]

ACTION_STATUS = [
    ('SUCCESS', 'Success'),
    ('FAILURE', 'Failure'),
]

class User(AbstractBaseUser, PermissionsMixin):
    first_name = models.CharField(_("First Name"), max_length=150, blank=True)
    last_name = models.CharField(_("Last Name"), max_length=150, blank=True)
    email = models.EmailField(_("Email Address"), unique=True)
    is_staff = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    date_joined = models.DateTimeField(default=timezone.now)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name"]

    objects = UserManager()

    class Meta: 
        verbose_name = "User"
        verbose_name_plural = "Users"
        permissions = [
            ("detail_User", "Can view custom user detail"),
        ]

    def get_full_name(self):
        '''
        Returns the first_name plus the last_name, with a space in between.
        '''
        full_name = '%s %s' % (self.first_name, self.last_name)
        return full_name.strip()

    def get_short_name(self):
        '''
        Returns the short name for the user.
        '''
        return self.first_name

    def email_user(self, subject, message, from_email=None, **kwargs):
        '''
        Sends an email to this User.
        '''
        send_mail(subject, message, from_email, [self.email], **kwargs)

    def __str__(self):
        if self.first_name and self.last_name:
            full_name = '%s %s' % (self.first_name, self.last_name)
            return full_name.strip()
        return self.email

class ActivityLog(models.Model):
    actor = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    action_type = models.CharField(choices=ACTION_TYPES, max_length=15)
    action_time = models.DateTimeField(auto_now_add=True)
    remarks = models.TextField(blank=True, null=True)
    status = models.CharField(choices=ACTION_STATUS, max_length=7, default='SUCCESS')
    data = models.JSONField(default=dict)
    content_type = models.ForeignKey(ContentType, models.SET_NULL, blank=True, null=True)
    object_id = models.CharField(max_length=36, blank=True, null=True)  # Adjusted to CharField
    content_object = GenericForeignKey()

    class Meta: 
        verbose_name = "Activity Log"
        verbose_name_plural = "Activity Logs"
        permissions = [
            ("detail_activitylog", "Can view activity log detail"),
        ]

    def __str__(self) -> str:
        return f"{self.action_type} by {self.actor} on {self.action_time}"

class Menu(models.Model):
    name = models.CharField(max_length=100)
    url = models.CharField(max_length=100, blank=True, null=True)
    icon = models.CharField(max_length=100, blank=True, null=True)
    order = models.PositiveIntegerField(default=1)
    parent = models.ForeignKey('self', on_delete=models.CASCADE, blank=True, null=True, related_name='children')
    permission = models.ForeignKey(Permission, on_delete=models.CASCADE, blank=True, null=True) 

    class Meta:
        ordering = ['order']

    def __str__(self):
        return self.name

    def get_absolute_url(self):
        return reverse(self.url) if self.url else "#"

    def has_children(self):
        return self.children.exists()

class Department(CreatedInfoModel, UpdatedInfoModel, SoftDeleteModel):
    name = models.CharField(max_length=150)

    class Meta: 
        permissions = [
            ("trashed_department", "Can view trashed Departments"),
        ]

    def __str__(self):
        return self.name

class Designation(CreatedInfoModel, UpdatedInfoModel, SoftDeleteModel):
    name = models.CharField(max_length=150)

    class Meta: 
        permissions = [
            ("trashed_designation", "Can view trashed Designations"),
        ]

    def __str__(self):
        return self.name

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    official_id = models.CharField(max_length=10, null=True, blank=True)
    contact_no = models.CharField(max_length=15, null=True, blank=True)
    department = models.OneToOneField(Department, on_delete=models.CASCADE, null=True, blank=True, related_name='department')
    designation = models.OneToOneField(Designation, on_delete=models.CASCADE, null=True, blank=True, related_name='designation')
    user_img = models.ImageField(upload_to='user/img/', null=True, blank=True)
    user_sign = models.ImageField(upload_to='user/sign/', null=True, blank=True)

    class Meta: 
        verbose_name = "Profile"
        verbose_name_plural = "Profiles"

    def profile_image(self):
        if self.user_img != '':
            return mark_safe('<img src="%s%s" width="100" />' % (f'{settings.MEDIA_URL}', self.user_img))

    def signature(self):
        if self.user_sign != '':
            return mark_safe('<img src="%s%s" width="100" />' % (f'{settings.MEDIA_URL}', self.user_sign))

    def __str__(self):
        if self.user.get_full_name() != '':
            return self.user.get_full_name()
        else:
            return self.official_id

