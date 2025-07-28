# core/middleware.py
import threading
from datetime import datetime
from django.conf import settings
from django.contrib.auth import logout
from django.shortcuts import redirect

_thread_locals = threading.local()

def get_current_user():
    """Return the current user stored in thread-local storage."""
    user = getattr(_thread_locals, 'user', None)
    return user if user and user.is_authenticated else None

class CurrentUserAndIdleTimeoutMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Set the current user in thread-local storage before processing the request
        _thread_locals.user = request.user

        # Handle idle timeout logic if the user is authenticated
        if request.user.is_authenticated:
            timeout = getattr(settings, 'SESSION_IDLE_TIMEOUT', 600)  # Default to 10 minutes
            last_activity = request.session.get('last_activity')

            if last_activity:
                elapsed_time = datetime.now() - datetime.fromisoformat(last_activity)
                if elapsed_time.total_seconds() > timeout:
                    # Log out user and flush session on timeout
                    logout(request)
                    request.session.flush()
                    return self.get_response(request)

            # Update the last activity time
            request.session['last_activity'] = datetime.now().isoformat()

        # Process the request and generate the response
        response = self.get_response(request)

        # Clean up the user from thread-local storage after the response is processed
        if hasattr(_thread_locals, 'user'):
            del _thread_locals.user

        return response


class LoginRequiredMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # List of paths that are allowed without authentication
        public_paths = getattr(settings, 'PUBLIC_PATHS', ['/login/', '/static/', '/media/'])
        
        # Check if the path is in the list of public paths
        if not request.user.is_authenticated and not any(request.path.startswith(path) for path in public_paths):
            # Build the next URL parameter to redirect back after login
            next_url = request.path.split("?next=")[0]
            login_url_with_next = f"{settings.LOGIN_URL}?next={next_url}"
            return redirect(login_url_with_next)
        
        response = self.get_response(request)
        return response