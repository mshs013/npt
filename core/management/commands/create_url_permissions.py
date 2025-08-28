# core/management/commands/create_url_permissions.py
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.urls import get_resolver
import sys

class Command(BaseCommand):
    help = "Create permissions for project URLs dynamically"

    def handle(self, *args, **kwargs):
        ct, _ = ContentType.objects.get_or_create(app_label='core', model='custompermission')
        existing_perms = set(Permission.objects.values_list('codename', flat=True))
        url_patterns = get_resolver().url_patterns
        created_count = 0
        url_names_set = set()  # Collect all valid URL names

        def is_third_party(callback):
            if not callback:
                return True
            module_name = getattr(callback, '__module__', '')
            if not module_name:
                return True
            if module_name.startswith('django.') or module_name.startswith('rest_framework.'):
                return True
            module = sys.modules.get(module_name)
            if module:
                file_path = getattr(module, '__file__', '')
                if file_path and 'site-packages' in file_path:
                    return True
            if 'admin' in module_name.lower():
                return True
            return False

        def create_perm(url_name, callback):
            nonlocal created_count
            if not url_name:
                return
            # Skip model-based view permissions
            if url_name.startswith(('trashed_', 'restore_')):
                return
            if is_third_party(callback):
                return
            # Skip if the view function has @skip_permission
            if getattr(callback, "_skip_permission", False):
                return
    
            url_names_set.add(url_name)
            if url_name not in existing_perms:
                Permission.objects.create(
                    codename=url_name,
                    name=f"Can access {url_name}",
                    content_type=ct
                )
                created_count += 1
                print(f"Created permission: {url_name}")

        def traverse(patterns):
            for p in patterns:
                if hasattr(p, 'url_patterns'):
                    traverse(p.url_patterns)
                else:
                    create_perm(getattr(p, 'name', None), getattr(p, 'callback', None))

        traverse(url_patterns)

        # Remove permissions that no longer exist in URL patterns
        removed_count = 0
        for codename in existing_perms:
            if codename not in url_names_set:
                perm = Permission.objects.filter(codename=codename, content_type=ct)
                if perm.exists():
                    perm.delete()
                    removed_count += 1
                    print(f"Removed old permission: {codename}")

        print(f"Total custom permissions created: {created_count}")
        print(f"Total old permissions removed: {removed_count}")
