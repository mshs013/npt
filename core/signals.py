# core/signals.py
import os
from django.db.models.signals import Signal, post_save, post_delete, pre_save, m2m_changed
from django.dispatch import receiver
from django.contrib.auth.signals import user_logged_in, user_login_failed
from django.contrib.sessions.models import Session 
from django.contrib.contenttypes.models import ContentType
from django.contrib.admin.models import LogEntry
from core.models import ActivityLog, User, Profile, Menu
from core.utils.utils import get_client_ip, get_object_data
from core.middleware import get_current_user
from datetime import datetime
from django.conf import settings

# Custom signals for soft delete functionality
post_soft_delete = Signal()
post_hard_delete = Signal()
post_restore = Signal()

# Directory to store cached menus
MENU_CACHE_DIR = os.path.join(settings.BASE_DIR, 'menu_cache')
if not os.path.exists(MENU_CACHE_DIR):
    os.makedirs(MENU_CACHE_DIR)

@receiver(post_soft_delete)
def handle_post_soft_delete(sender, instance, **kwargs):
    """
    Handle actions after a soft delete.
    """
    print(f"Soft deleted: {instance} at {datetime.now()}")

@receiver(post_hard_delete)
def handle_post_hard_delete(sender, instance, **kwargs):
    """
    Handle actions after a hard delete.
    """
    print(f"Hard deleted: {instance} at {datetime.now()}")

@receiver(post_restore)
def handle_post_restore(sender, instance, **kwargs):
    """
    Handle actions after restoring an object.
    """
    print(f"Restored: {instance} at {datetime.now()}")

@receiver(pre_save)
def capture_old_instance(sender, instance, **kwargs):
    """Capture the old instance data before it is updated."""
    if sender in [ActivityLog, LogEntry, Session]:  # Avoid recursive logging for both models
        return  # Avoid logging ActivityLog changes
    if instance.pk:
        try:
            instance._pre_save_instance = sender.objects.get(pk=instance.pk)
        except sender.DoesNotExist:
            instance._pre_save_instance = None
    else:
        instance._pre_save_instance = None

@receiver(post_save)
def log_model_save(sender, instance, created, **kwargs):
    if sender in [ActivityLog, LogEntry, Session]:  # Avoid recursive logging for both models  # Avoid recursive logging
        return
    action_type = 'CREATE' if created else 'UPDATE'
    
    actor = get_current_user()

    #print(f'Sender: {sender.__name__}')
    content_type = ContentType.objects.get_for_model(sender)
    #print(f'ContentType: {content_type}')

    if not created:
        old_instance = getattr(instance, '_pre_save_instance', None)
        old_data = get_object_data(old_instance) if old_instance else {}
    else:
        old_data = {}

    new_data = get_object_data(instance)
    if actor:
        ActivityLog.objects.create(
            actor=actor,
            action_type=action_type,
            data={
                'old': old_data,
                'new': new_data
            },
            content_type=content_type,
            object_id=str(instance.pk) if instance.pk else None,
        )

@receiver(post_soft_delete)
def log_model_soft_delete(sender, instance, **kwargs):
    if sender in [ActivityLog, LogEntry, Session]:  # Avoid recursive logging for both models  # Avoid recursive logging
        return
    
    old_data = get_object_data(instance)
    ActivityLog.objects.create(
        actor=get_current_user(),  # Adjust based on your user field
        action_type='DELETE',
        data={'old': old_data},
        content_type=ContentType.objects.get_for_model(sender),
        object_id=str(instance.pk) if instance.pk else None,
    )
    
@receiver(post_delete)
def log_model_delete(sender, instance, **kwargs):
    if sender in [ActivityLog, LogEntry, Session]:  # Avoid recursive logging
        return
    
    old_data = get_object_data(instance)
    ActivityLog.objects.create(
        actor=get_current_user(),  # Adjust based on your user field
        action_type='DELETE',
        data={'old': old_data},
        content_type=ContentType.objects.get_for_model(sender),
        object_id=str(instance.pk) if instance.pk else None,
    )

@receiver(post_restore)
def log_model_restore(sender, instance, **kwargs):
    if sender in [ActivityLog, LogEntry, Session]:  # Avoid recursive logging for both models  # Avoid recursive logging
        return
    
    old_data = get_object_data(instance)
    ActivityLog.objects.create(
        actor=get_current_user(),  # Adjust based on your user field
        action_type='RESTORE',
        data={'old': old_data},
        content_type=ContentType.objects.get_for_model(sender),
        object_id=str(instance.pk) if instance.pk else None,
    )

@receiver(user_logged_in)
def log_user_login(request, user, **kwargs):
    message = f"{user.get_full_name()} logged in with IP: {get_client_ip(request)}"
    ActivityLog.objects.create(
        actor=user,
        action_type='LOGIN',
        remarks=message,
    )

@receiver(user_login_failed)
def log_user_login_failed(sender, credentials, request, **kwargs):
    email = credentials.get('email', 'unknown email')
    message = f"Login Attempt Failed for email {email} with IP: {get_client_ip(request)}"
    ActivityLog.objects.create(
        action_type='LOGIN_FAILED',
        remarks=message,
    )

@receiver(post_save, sender=User)
def create_or_update_user_profile(sender, instance, created, **kwargs):
    if created:
        Profile.objects.create(user=instance)

# Clear cached menu file when user permissions change
def clear_user_menu_cache(user_id):
    menu_file_path = os.path.join(MENU_CACHE_DIR, f"menu_for_user_{user_id}.html")
    if os.path.exists(menu_file_path):
        os.remove(menu_file_path)

# Clear the cache for all users
def clear_all_user_menus_cache():
    users = User.objects.all()
    for user in users:
        clear_user_menu_cache(user.id)

# Signal handler for user-specific permission changes
@receiver(m2m_changed, sender=User.user_permissions.through)
def handle_user_permission_change(sender, instance, action, **kwargs):
    if action in ['post_add', 'post_remove', 'post_clear']:
        clear_user_menu_cache(instance.id)

# Signal handler for permission changes on User model
@receiver(post_save, sender=User)
def handle_permission_change(sender, instance, **kwargs):
    # Call cache invalidation if user permissions changed
    clear_user_menu_cache(instance.id)

@receiver(post_save, sender=Menu)
def handle_menu_update(sender, instance, **kwargs):
    # Clear the menu cache for all users when a menu is updated
    if not instance.pk:  # If instance.pk is None, it means the menu is being created
        return
    clear_all_user_menus_cache()