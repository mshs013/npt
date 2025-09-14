# core/context_processors.py

from django.conf import settings
from core.utils.utils import get_active_company

def adminlte_settings(request):
    """
    Add the AdminLTE settings from settings.py to the context.
    """
    return {
        "ADMINLTE_SETTINGS": settings.ADMINLTE_SETTINGS
    }


def active_company(request):
    return {"active_company": get_active_company(request)}