# 🚀 Deployment Guide for NPT (Django)

This guide walks you through deploying the **NPT** Django application using PostgreSQL, Gunicorn, Nginx, and systemd on Ubuntu (22.04 or later).

---

## 1. 🧰 Server Preparation

### Install Required Packages

```bash
sudo apt update
sudo apt install python3-venv python3-dev libpq-dev postgresql postgresql-contrib nginx curl
```

---

## 2. 🐘 PostgreSQL Setup

### Create Database and User

```bash
sudo -u postgres psql
```

Inside the shell:

```sql
CREATE DATABASE npt;
CREATE USER ocms WITH PASSWORD 'Ocmsbd.com2016';
ALTER ROLE ocms SET client_encoding TO 'utf8';
ALTER ROLE ocms SET default_transaction_isolation TO 'read committed';
ALTER ROLE ocms SET timezone TO 'Asia/Dhaka';
GRANT ALL PRIVILEGES ON DATABASE npt TO ocms;
ALTER DATABASE npt OWNER TO ocms;
\q
```

---

## 3. 📦 Clone and Setup Project

```bash
mkdir ~/npt
cd ~/npt
git clone https://github.com/mshs013/npt .
```

### Create Virtual Environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

---

## 4. 🔐 Setup Environment Variables

Create a `.env` file in the project root:

```ini
SECRET_KEY=your-django-secret-key
DEBUG=False
DB_ENGINE=django.db.backends.postgresql
DB_NAME=npt
DB_USER=ocms
DB_PASS=Ocmsbd.com2016
DB_HOST=localhost
DB_PORT=5432
```

---

## 5. ⚙️ Django Configuration

In npt/settings.py, add:

```python
import os
from dotenv import load_dotenv
load_dotenv()

SECRET_KEY = os.getenv('SECRET_KEY')
DEBUG = os.getenv('DEBUG')
ALLOWED_HOSTS = ['127.0.0.1', 'localhost']

INSTALLED_APPS = [
    'jazzmin',
    'django_filters',
    'crispy_forms',
    'crispy_bootstrap4',
    'import_export',
    'django_summernote',
    'django_extensions',
    'debug_toolbar',
    'core',
]

MIDDLEWARE = [
    ...,
    'debug_toolbar.middleware.DebugToolbarMiddleware',
    'core.middleware.CurrentUserAndIdleTimeoutMiddleware',
]

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                ...,
                'core.context_processors.adminlte_settings',
            ],
        },
    },
]

DATABASES = {
    'default': {
        'ENGINE': os.getenv('DB_ENGINE'),
        'NAME': os.getenv('DB_NAME'),
        'USER': os.getenv('DB_USER'),
        'PASSWORD': os.getenv('DB_PASS'),
        'HOST': os.getenv('DB_HOST'),
        'PORT': os.getenv('DB_PORT'),
    }
}

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

AUTH_USER_MODEL = "core.User"

SESSION_IDLE_TIMEOUT = 600
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

PUBLIC_PATHS = ['/login/', '/static/', '/media/']

# Auth User Model
AUTH_USER_MODEL = "core.User"

# Set idle session timeout (in seconds)
SESSION_IDLE_TIMEOUT = 600  # 10 minutes

LOGIN_URL = '/login/'  # This should match your login URL pattern
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/'

ADMINLTE_SETTINGS = {
    # title of the window (Will default to site_title if absent or None)
    "site_title": "NPT",
    # Dark Mode
    "dark_mode": False,

    # Header Options
    "header_fixed": False,
    "dropdown_legacy_offset": False,
    "no_border": False,

    # Sidebar Options
    "sidebar_collapsed": False,
    "sidebar_fixed": True,
    "sidebar_mini": True,
    "sidebar_mini_md": False,
    "sidebar_mini_xs": False,
    "nav_flat_style": False,
    "nav_legacy_style": False,
    "nav_compact": False,
    "nav_child_indent": False,
    "nav_child_hide_on_collapse": False,
    "disable_hover_expand": False,

    # Footer Options
    "footer_fixed": True,

    # Small Text Options
    "small_text_body": False,
    "small_text_navbar": False,
    "small_text_brand": False,
    "small_text_sidebar": False,
    "small_text_footer": False,

    # Navbar Variants (Light/Dark)
    "navbar_variant": "bg-lightblue",  # Options like navbar-dark, navbar-primary, etc.

    # Accent Color Variants
    "accent_color": "",  # Options like accent-danger, accent-warning, etc.

    # Sidebar Variants
    "sidebar_dark_variant": "sidebar-dark-primary",  # Options like sidebar-dark-danger, sidebar-dark-warning
    "sidebar_light_variant": "",  # Options like sidebar-light-warning, sidebar-light-danger

    # Brand Logo Variants
    "brand_logo_variant": "",  # Options like navbar-dark, navbar-light
}

JAZZMIN_SETTINGS = {
    # title of the window (Will default to current_admin_site.site_title if absent or None)
    "site_title": "NPT",

    # Title on the login screen (19 chars max) (defaults to current_admin_site.site_header if absent or None)
    "site_header": "NPT",

    # Title on the brand (19 chars max) (defaults to current_admin_site.site_header if absent or None)
    "site_brand": "NPT",

    # Logo to use for your site, must be present in static files, used for brand on top left
    "site_logo": "logo/logo.png",

    # Logo to use for your site, must be present in static files, used for login form logo (defaults to site_logo)
    "login_logo": None,

    # Logo to use for login form in dark themes (defaults to login_logo)
    "login_logo_dark": None,

    # CSS classes that are applied to the logo above
    "site_logo_classes": "img-circle",

    # Relative path to a favicon for your site, will default to site_logo if absent (ideally 32x32 px)
    "site_icon": True,

    # Welcome text on the login screen
    "welcome_sign": "Welcome to the NPT",

    # Copyright on the footer
    "copyright": "OCMS",

    # Field name on user model that contains avatar ImageField/URLField/Charfield or a callable that receives the user
    "user_avatar": False,
    
    #############
    # Side Menu #
    #############

    # Whether to display the side menu
    "show_sidebar": True,

    # Whether to aut expand the menu
    "navigation_expanded": False,

    # Hide these apps when generating side menu e.g (auth)
    "hide_apps": [],

    # Hide these models when generating side menu (e.g auth.user)
    "hide_models": [],

    # List of apps (and/or models) to base side menu ordering off of (does not need to contain all apps/models)
    "order_with_respect_to": [],
    
    # Custom icons for side menu apps/models See https://fontawesome.com/icons?d=gallery&m=free&v=5.0.0,5.0.1,5.0.10,5.0.11,5.0.12,5.0.13,5.0.2,5.0.3,5.0.4,5.0.5,5.0.6,5.0.7,5.0.8,5.0.9,5.1.0,5.1.1,5.2.0,5.3.0,5.3.1,5.4.0,5.4.1,5.4.2,5.13.0,5.12.0,5.11.2,5.11.1,5.10.0,5.9.0,5.8.2,5.8.1,5.7.2,5.7.1,5.7.0,5.6.3,5.5.0,5.4.2
    # for the full list of 5.13.0 free icon classes
    "icons": {
        "auth": "fas fa-users-cog",
        "auth.user": "fas fa-user",
        "auth.Group": "fas fa-users",
        "auth.permission": "fas fa-key",
        "ocmscore": "fas fa-cogs",
    },
    # Icons that are used when one is not manually specified
    "default_icon_parents": "fas fa-chevron-circle-right",
    "default_icon_children": "fas fa-circle",

    #################
    # Related Modal #
    #################
    # Use modals instead of popups
    "related_modal_active": False,

    #############
    # UI Tweaks #
    #############
    # Relative paths to custom CSS/JS scripts (must be present in static files)
    "custom_css": 'assets/css/admin-theme.css',
    "custom_js": None,
    # Whether to link font from fonts.googleapis.com (use custom_css to supply font otherwise)
    "use_google_fonts_cdn": False,
    # Whether to show the UI customizer on the sidebar
    "show_ui_builder": False,

    ###############
    # Change view #
    ###############
    # Render out the change view as a single form, or in tabs, current options are
    # - single
    # - horizontal_tabs (default)
    # - vertical_tabs
    # - collapsible
    # - carousel
    "changeform_format": "single",
    # override change forms on a per modeladmin basis
    "changeform_format_overrides": {"auth.user": "collapsible", "auth.group": "vertical_tabs"},
    # Add a language dropdown into the admin
    #"language_chooser": True,
}

SUMMERNOTE_THEME = 'bs4'  # Show summernote with Bootstrap4

SUMMERNOTE_CONFIG = {
    'iframe': True,
    'height': 400,
    'width': '100%',
    'toolbar': [
        ['style', ['style']],
        ['font', ['bold', 'underline', 'clear']],
        ['color', ['color']],
        ['para', ['ul', 'ol', 'paragraph']],
        ['table', ['table']],
        ['insert', ['link', 'picture', 'video']],
        ['view', ['fullscreen', 'codeview', 'help']],
    ],
}
```

---

## 6. 📁 Database & Static Files

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic
```

---

## 7. 🔥 Gunicorn Setup

### Create Gunicorn Socket

```bash
sudo nano /etc/systemd/system/gunicorn.socket
```

Paste:

```ini
[Unit]
Description=gunicorn socket

[Socket]
ListenStream=/run/gunicorn.sock

[Install]
WantedBy=sockets.target
```

---

### Create Gunicorn Service

```bash
sudo nano /etc/systemd/system/gunicorn.service
```

Paste:

```ini
[Unit]
Description=gunicorn daemon
Requires=gunicorn.socket
After=network.target

[Service]
User=sazzad
Group=www-data
WorkingDirectory=/home/sazzad/npt
ExecStart=/home/sazzad/npt/.venv/bin/gunicorn \
          --access-logfile - \
          --workers 3 \
          --bind unix:/run/gunicorn.sock \
          npt.wsgi:application

[Install]
WantedBy=multi-user.target
```

---

### Enable and Start Gunicorn

```bash
sudo systemctl start gunicorn.socket
sudo systemctl enable gunicorn.socket
sudo systemctl daemon-reload
sudo systemctl restart gunicorn
```

---

## 8. 🌐 Nginx Setup

### Create Nginx Config

```bash
sudo nano /etc/nginx/sites-available/npt
```

Paste:

```nginx
server {
    listen 80;
    server_name localhost;

    location = /favicon.ico { access_log off; log_not_found off; }

    location /static/ {
        alias /home/sazzad/npt/staticfiles/;
    }

    location /media/ {
        alias /home/sazzad/npt/media/;
    }

    location / {
        include proxy_params;
        proxy_pass http://unix:/run/gunicorn.sock;
    }
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/npt /etc/nginx/sites-enabled
sudo nginx -t
sudo systemctl restart nginx
```

---

## 9. 🔐 Firewall Setup

```bash
sudo ufw delete allow 8000
sudo ufw allow 'Nginx Full'
```

---

## 10. ✅ Access Application

- App: `http://your_server_ip/`
- Admin: `http://your_server_ip/admin/`

---

## 11. 🧪 Useful Debug Commands

```bash
sudo systemctl status gunicorn
sudo systemctl status nginx
journalctl -u gunicorn
```

---

## 📌 Notes

- Make sure your project paths match your server username and location.
- Store the `.env` file securely and never commit it.
- For production, consider setting up HTTPS with Let’s Encrypt (Certbot).

---

## 👨‍💻 Maintainer

**Sazzad Hossain**  
🔗 [GitHub: mshs013](https://github.com/mshs013)