from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, Permission
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q
from django.db.models.signals import post_save
from django.utils import timezone
from django.utils.translation import gettext_lazy as _
from django.utils.html import mark_safe
from django.urls import reverse
from django.conf import settings
from django.core.mail import send_mail
from core.mixins import CreatedInfoModel, UpdatedInfoModel, SoftDeleteModel
from datetime import datetime
from core.fields import MACAddressField

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
            ("restore_department", "Can view restore Departments"),
        ]

    def __str__(self):
        return self.name

class Designation(CreatedInfoModel, UpdatedInfoModel, SoftDeleteModel):
    name = models.CharField(max_length=150)

    class Meta: 
        permissions = [
            ("trashed_designation", "Can view trashed Designations"),
            ("restore_designation", "Can view restore Designations"),
        ]

    def __str__(self):
        return self.name

class Profile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    official_id = models.CharField(max_length=10, null=True, blank=True)
    contact_no = models.CharField(max_length=15, null=True, blank=True)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True, related_name='profiles')
    designation = models.ForeignKey(Designation, on_delete=models.SET_NULL, null=True, blank=True, related_name='profiles')
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

class NptReason(CreatedInfoModel, UpdatedInfoModel, SoftDeleteModel):
    name = models.CharField(max_length=150)
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
            ("restore_nptreason", "Can view restore NPT Reasons"),
        ]

    def __str__(self):
        return self.name

class ProcessedNPT(models.Model):
    mc_no = models.CharField(max_length=50)
    reason = models.ForeignKey(
        NptReason,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    off_time = models.DateTimeField()
    on_time = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Processed NPT"
        verbose_name_plural = "Processed NPT"
        constraints = [
            models.UniqueConstraint(fields=['mc_no', 'off_time'], name='unique_mc_off_time')
        ]

    def get_duration(self):
        """
        Returns duration as timedelta:
        - If on_time exists: on_time - off_time
        - Else: current time - off_time
        """
        now = datetime.now()  # naive
        if self.on_time:
            return self.on_time - self.off_time
        return now - self.off_time

    def __str__(self):
        return f"{self.mc_no}"

class RotationStatus(models.Model):
    mc_no = models.CharField(max_length=50)
    count = models.IntegerField()
    count_time = models.DateTimeField()

    class Meta:
        verbose_name = "Rotation Status"
        verbose_name_plural = "Rotation Status"
        constraints = [
            models.UniqueConstraint(fields=['mc_no', 'count_time'], name='unique_mc_count_time')
        ]

class ProcessorCursor(models.Model):
    """
    Stores the last processed timestamp for each Influx measurement
    to prevent reprocessing the same records.
    """
    measurement = models.CharField(max_length=50, unique=True)
    last_timestamp = models.DateTimeField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.measurement} → {self.last_timestamp}"
    
class Company(CreatedInfoModel, UpdatedInfoModel, SoftDeleteModel):
    name = models.CharField(max_length=150, unique=True)

    class Meta:
        verbose_name = "Company"
        verbose_name_plural = "Companies"
        permissions = [
            ("trashed_company", "Can view trashed Company"),
            ("restore_company", "Can view restore Company"),
        ]

    def __str__(self):
        return f"{self.name}"
    
class Building(CreatedInfoModel, UpdatedInfoModel, SoftDeleteModel):
    name = models.CharField(max_length=150, unique=True)
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name="building_company")

    class Meta:
        verbose_name = "Building"
        verbose_name_plural = "Buildings"
        permissions = [
            ("trashed_building", "Can view trashed Building"),
            ("restore_building", "Can view restore Building"),
        ]

    def __str__(self):
        return f"{self.name}"
    
class Floor(CreatedInfoModel, UpdatedInfoModel, SoftDeleteModel):
    name = models.CharField(max_length=150, unique=True)
    building = models.ForeignKey(Building, on_delete=models.CASCADE, related_name="floor_building")

    class Meta:
        verbose_name = "Floor"
        verbose_name_plural = "Floors"
        permissions = [
            ("trashed_floor", "Can view trashed Floor"),
            ("restore_floor", "Can view restore Floor"),
        ]

    def __str__(self):
        return f"{self.name}"
    
class Block(CreatedInfoModel, UpdatedInfoModel, SoftDeleteModel):
    name = models.CharField(max_length=150, unique=True)
    floor = models.ForeignKey(Floor, on_delete=models.CASCADE, related_name="block_floor")

    class Meta:
        verbose_name = "Block"
        verbose_name_plural = "Blocks"
        permissions = [
            ("trashed_block", "Can view trashed Block"),
            ("restore_block", "Can view restore Block"),
        ]

    def __str__(self):
        return f"{self.name}"
    
class MachineType(CreatedInfoModel, UpdatedInfoModel, SoftDeleteModel):
    name = models.CharField(max_length=150, unique=True)

    class Meta: 
        verbose_name = "Machine Type"
        verbose_name_plural = "Machine Types"
        permissions = [
            ("trashed_machinetype", "Can view trashed Machine Type"),
            ("restore_machinetype", "Can view restore Machine Type"),
        ]

    def __str__(self):
        return f"{self.name}"

class Machine(CreatedInfoModel, UpdatedInfoModel, SoftDeleteModel):
    MC_CATEGORY = [
        ('C', 'Circular'),
        ('F', 'Flat'),
    ]

    mc_no = models.CharField(max_length=50, unique=True)
    device_mc = MACAddressField(null=True, blank=True)
    brand = models.CharField(max_length=100)
    model = models.CharField(max_length=100)
    category = models.CharField(max_length=1, choices=MC_CATEGORY, default="C")
    dia = models.IntegerField(null=True, blank=True)
    feeder = models.IntegerField(null=True, blank=True)
    shinker = models.IntegerField(null=True, blank=True)
    track = models.IntegerField(null=True, blank=True)
    max_rpm = models.IntegerField(null=True, blank=True)
    gg = models.IntegerField(null=True, blank=True)
    speed_factor = models.IntegerField(null=True, blank=True)
    extra_cylinder = models.BooleanField(default=False)
    lycra_attach = models.BooleanField(default=False)
    block = models.ForeignKey(Block, on_delete=models.CASCADE)
    mc_types = models.ManyToManyField(MachineType, related_name="machine_types", blank=True)

    class Meta:
        verbose_name = 'Machine'
        verbose_name_plural = 'Machines'
        permissions = [
            ("trashed_machine", "Can view trashed Machine"),
            ("restore_machine", "Can view restore Machine"),
        ]

    def __str__(self):
        return f"{self.brand} - {self.model} - {self.mc_no}"

# Object-level user permissions
class UserBlockPermission(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    blocks = models.ManyToManyField(Block, blank=True)

class UserMachinePermission(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE)
    machines = models.ManyToManyField(Machine, blank=True)

