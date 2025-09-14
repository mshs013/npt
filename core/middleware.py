# core/middleware.py
import threading
from datetime import datetime
from django.conf import settings
from django.contrib.auth import logout
from django.shortcuts import redirect
from django.apps import apps
from django.core.exceptions import PermissionDenied
from django.utils.deprecation import MiddlewareMixin

_thread_locals = threading.local()

def get_current_user():
    """Return the current user stored in thread-local storage."""
    user = getattr(_thread_locals, 'user', None)
    return user if user and user.is_authenticated else None

def get_current_request():
    """Return the current request stored in thread-local storage."""
    return getattr(_thread_locals, 'request', None)

# ---------------------------
# 1️⃣ Current user & idle timeout
# ---------------------------
class CurrentUserAndIdleTimeoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Set current user in thread-local storage
        _thread_locals.user = request.user
        _thread_locals.request = request

        if request.user.is_authenticated:
            timeout = getattr(settings, 'SESSION_IDLE_TIMEOUT', 600)  # 10 min default
            last_activity = request.session.get('last_activity')

            if last_activity:
                elapsed_time = datetime.now() - datetime.fromisoformat(last_activity)
                if elapsed_time.total_seconds() > timeout:
                    logout(request)
                    request.session.flush()
                    return self.get_response(request)

            request.session['last_activity'] = datetime.now().isoformat()

        response = self.get_response(request)

        # Clean up
        if hasattr(_thread_locals, 'user'):
            del _thread_locals.user
        if hasattr(_thread_locals, 'request'):
            del _thread_locals.request

        return response


# ---------------------------
# 2️⃣ Login required
# ---------------------------
class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        public_paths = getattr(settings, 'PUBLIC_PATHS', ['/login/', '/logout/', '/static/', '/media/'])
        if not request.user.is_authenticated and not any(request.path.startswith(path) for path in public_paths):
            next_url = request.path.split("?next=")[0]
            login_url_with_next = f"{settings.LOGIN_URL}?next={next_url}"
            return redirect(login_url_with_next)

        response = self.get_response(request)
        return response


# ---------------------------
# 3️⃣ Dynamic Permission Middleware
# ---------------------------
def skip_permission(view_func):
    """Decorator to skip permission check."""
    setattr(view_func, "_skip_permission", True)
    return view_func

class DynamicPermissionMiddleware(MiddlewareMixin):
    """
    Middleware that dynamically checks permissions based on URL name,
    and skips URLs listed in PUBLIC_PATHS.
    """

    def process_view(self, request, view_func, view_args, view_kwargs):
        url_name = getattr(request.resolver_match, 'url_name', None)
        path = request.path

        public_paths = getattr(settings, 'PUBLIC_PATHS', ['/login/', '/logout/', '/static/', '/media/'])

        # Skip public paths or decorated views
        if not url_name or getattr(view_func, "_skip_permission", False) or any(path.startswith(p) for p in public_paths) or "django_plotly_dash" in path:
            return None

        perm_name = self.get_permission_from_url(url_name)

        if not request.user.is_superuser and not request.user.has_perm(perm_name):
            raise PermissionDenied(f"You do not have permission: {perm_name}")

    @staticmethod
    def get_permission_from_url(url_name: str) -> str:
        """
        Determine permission codename from URL name:
        - If URL name matches a model: <action>_<modelname_lower> -> app_label.<action>_<modelname>
        - Otherwise: return custom permission with 'core' app
        """
        if "_" in url_name:
            action, model_str = url_name.split("_", 1)
            model = DynamicPermissionMiddleware.get_model_by_lower_name(model_str)
            if model:
                app_label = model._meta.app_label
                model_name = model._meta.model_name
                return f"{app_label}.{action}_{model_name}"

        # Custom permission (like 'home', 'report_npt')
        return f"core.{url_name}"

    @staticmethod
    def get_model_by_lower_name(model_str):
        for model in apps.get_models():
            if model.__name__.lower() == model_str.lower():
                return model
        return None


class ActiveCompanyMiddleware(MiddlewareMixin):
    """
    Ensure session['active_company_id'] exists (using default if not)
    and sets request.active_company for easy access in templates/views.
    """
    def process_request(self, request):
        request.active_company = None  # default

        if not request.user.is_authenticated:
            return

        # Lazy import to avoid circular import
        from .models import Company

        session_company_id = request.session.get('active_company_id')

        if session_company_id:
            try:
                request.active_company = Company.objects.get(pk=session_company_id)
                return
            except Company.DoesNotExist:
                request.active_company = None  # fallback to profile

        profile = getattr(request.user, "profile", None)
        if not profile:
            return

        # Use default company
        if profile.default_company:
            request.active_company = profile.default_company
            request.session['active_company_id'] = profile.default_company.id
            request.session.modified = True
            return

        # Use first company assigned
        first_company = profile.company.first()
        if first_company:
            request.active_company = first_company
            request.session['active_company_id'] = first_company.id
            request.session.modified = True