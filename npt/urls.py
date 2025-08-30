"""
URL configuration for npt project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.auth import views as auth_views
from debug_toolbar.toolbar import debug_toolbar_urls
from core.views import permission_denied_view, page_not_found_view, server_error_view

handler403 = permission_denied_view
handler404 = page_not_found_view
handler500 = server_error_view

urlpatterns = [
    path('login/', auth_views.LoginView.as_view(template_name='admin/login.html', extra_context={'title': 'Log in'}), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path("change-password/", auth_views.PasswordChangeView.as_view(template_name='core/change_password.html', extra_context={'title': 'Change password'}), name='change_password'),
    path("change-password/done/", auth_views.PasswordChangeDoneView.as_view(template_name="core/password_change_done.html", extra_context={"title": "Password Changed"}), name="password_change_done"),
    path('admin/', admin.site.urls),
    path('core/', include('core.urls')),
    path('lib/', include('library.urls')),
    path('', include('frontend.urls')),
    path('summernote/', include('django_summernote.urls')),
    path("django_plotly_dash/", include("django_plotly_dash.urls")),
] + debug_toolbar_urls()

if settings.DEBUG:
     urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

if settings.DEBUG:
     urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
