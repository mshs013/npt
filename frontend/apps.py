from django.apps import AppConfig


class FrontendConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'frontend'

    def ready(self):
        # Import Dash apps so they register
        from frontend.dash_apps import register_dash_apps
        register_dash_apps()
        # Import signals module (or just access signals here)
        import django.db.models.signals
