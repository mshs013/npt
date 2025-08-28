# core/backends.py
from django.contrib.auth.backends import ModelBackend
from core.models import UserMachinePermission, UserBlockPermission, Machine, Block

class MachineBlockPermissionBackend(ModelBackend):
    """Custom backend for object-level Machine/Block permissions."""

    def has_perm(self, user_obj, perm, obj=None):
        # Default permission check
        if super().has_perm(user_obj, perm, obj):
            return True

        if not user_obj.is_authenticated:
            return False

        # Object-level permissions
        if isinstance(obj, Machine):
            if UserMachinePermission.objects.filter(user=user_obj, machine=obj).exists():
                return True
            if UserBlockPermission.objects.filter(user=user_obj, block=obj.block).exists():
                return True
            # Group permissions
            if obj.block.machines.filter(block__group_permissions__group__in=user_obj.groups.all()).exists():
                return True
            if UserMachinePermission.objects.filter(user=user_obj, machine=obj).exists():
                return True

        if isinstance(obj, Block):
            if UserBlockPermission.objects.filter(user=user_obj, block=obj).exists():
                return True
            if obj.group_permissions.filter(group__in=user_obj.groups.all()).exists():
                return True

        return False
