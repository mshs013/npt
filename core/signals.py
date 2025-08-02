import os
import sys
from datetime import datetime

from django.db.models.signals import (
    Signal, post_save, post_delete, pre_save, m2m_changed
)
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.contrib.sessions.models import Session
from django.contrib.contenttypes.models import ContentType
from django.contrib.admin.models import LogEntry
from django.conf import settings
from django.db import connection
from django.apps import apps

from core.utils.utils import get_client_ip, get_object_data
from core.middleware import get_current_user

# Custom signals for soft delete
post_soft_delete = Signal()
post_hard_delete = Signal()
post_restore = Signal()

MENU_CACHE_DIR = os.path.join(settings.BASE_DIR, 'menu_cache')
os.makedirs(MENU_CACHE_DIR, exist_ok=True)

def get_activity_log_model():
    return apps.get_model('core', 'ActivityLog')

def get_profile_model():
    return apps.get_model('core', 'Profile')

def is_migration_running():
    return 'makemigrations' in sys.argv or 'migrate' in sys.argv

def activitylog_table_exists():
    try:
        return 'core_activitylog' in connection.introspection.table_names()
    except Exception:
        return False

def log_activity(**kwargs):
    ActivityLog = get_activity_log_model()
    if activitylog_table_exists() and not is_migration_running():
        ActivityLog.objects.create(**kwargs)

@receiver(post_soft_delete)
def handle_post_soft_delete(sender, instance, **kwargs):
    print(f"Soft deleted: {instance} at {datetime.now()}")

@receiver(post_hard_delete)
def handle_post_hard_delete(sender, instance, **kwargs):
    print(f"Hard deleted: {instance} at {datetime.now()}")

@receiver(post_restore)
def handle_post_restore(sender, instance, **kwargs):
    print(f"Restored: {instance} at {datetime.now()}")

@receiver(pre_save)
def capture_old_instance(sender, instance, **kwargs):
    ActivityLog = get_activity_log_model()
    if sender in [ActivityLog, LogEntry, Session] or is_migration_running():
        return
    if instance.pk:
        try:
            instance._pre_save_instance = sender.objects.get(pk=instance.pk)
        except sender.DoesNotExist:
            instance._pre_save_instance = None
    else:
        instance._pre_save_instance = None

@receiver(post_save)
def log_model_save(sender, instance, created, **kwargs):
    ActivityLog = get_activity_log_model()
    if sender in [ActivityLog, LogEntry, Session] or is_migration_running():
        return

    actor = get_current_user()
    content_type = ContentType.objects.get_for_model(sender)
    action_type = 'CREATE' if created else 'UPDATE'
    old_data = {}

    if not created:
        old_instance = getattr(instance, '_pre_save_instance', None)
        old_data = get_object_data(old_instance) if old_instance else {}

    new_data = get_object_data(instance)

    if actor:
        log_activity(
            actor=actor,
            action_type=action_type,
            data={'old': old_data, 'new': new_data},
            content_type=content_type,
            object_id=str(instance.pk) if instance.pk else None,
        )

@receiver(post_soft_delete)
@receiver(post_delete)
def log_model_delete(sender, instance, **kwargs):
    ActivityLog = get_activity_log_model()
    if sender in [ActivityLog, LogEntry, Session] or is_migration_running():
        return

    log_activity(
        actor=get_current_user(),
        action_type='DELETE',
        data={'old': get_object_data(instance)},
        content_type=ContentType.objects.get_for_model(sender),
        object_id=str(instance.pk) if instance.pk else None,
    )

@receiver(post_restore)
def log_model_restore(sender, instance, **kwargs):
    ActivityLog = get_activity_log_model()
    if sender in [ActivityLog, LogEntry, Session] or is_migration_running():
        return

    log_activity(
        actor=get_current_user(),
        action_type='RESTORE',
        data={'old': get_object_data(instance)},
        content_type=ContentType.objects.get_for_model(sender),
        object_id=str(instance.pk) if instance.pk else None,
    )

@receiver(user_logged_in)
def log_user_login(request, user, **kwargs):
    if is_migration_running():
        return
    log_activity(
        actor=user,
        action_type='LOGIN',
        remarks=f"{user.get_full_name()} logged in with IP: {get_client_ip(request)}"
    )

@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request, **kwargs):
    if is_migration_running():
        return
    email = credentials.get('email', 'unknown email')
    log_activity(
        action_type='LOGIN_FAILED',
        remarks=f"Login Attempt Failed for email {email} with IP: {get_client_ip(request)}"
    )

@receiver(post_save)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    User = apps.get_model('core', 'User')
    if sender != User:
        return
    Profile = get_profile_model()
    if created and not is_migration_running():
        Profile.objects.create(user=instance)

def clear_user_menu_cache(user_id):
    menu_file_path = os.path.join(MENU_CACHE_DIR, f"menu_for_user_{user_id}.html")
    if os.path.exists(menu_file_path):
        os.remove(menu_file_path)

def clear_all_user_menus_cache():
    User = apps.get_model('core', 'User')
    for user in User.objects.all():
        clear_user_menu_cache(user.id)

@receiver(m2m_changed)
def handle_user_permission_change(sender, instance, action, **kwargs):
    User = apps.get_model('core', 'User')
    if sender != User.user_permissions.through:
        return
    if action in ['post_add', 'post_remove', 'post_clear']:
        clear_user_menu_cache(instance.id)

@receiver(post_save)
def handle_permission_change(sender, instance, **kwargs):
    User = apps.get_model('core', 'User')
    if sender != User:
        return
    clear_user_menu_cache(instance.id)

def handle_menu_update(sender, instance, **kwargs):
    if instance.pk:
        clear_all_user_menus_cache()

def connect_signals():
    User = apps.get_model('core', 'User')
    Menu = apps.get_model('core', 'Menu')

    post_save.connect(handle_permission_change, sender=User)
    post_save.connect(create_or_update_user_profile, sender=User)
    m2m_changed.connect(handle_user_permission_change, sender=User.user_permissions.through)
    post_save.connect(handle_menu_update, sender=Menu)
