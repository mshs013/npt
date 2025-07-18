# core/context_processors.py

from django.conf import settings

def adminlte_settings(request):
    """
    Add the AdminLTE settings from settings.py to the context.
    """
    return {
        "ADMINLTE_SETTINGS": settings.ADMINLTE_SETTINGS
    }
