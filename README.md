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
CREATE USER db_user WITH PASSWORD 'your_db_pass';
ALTER ROLE db_user SET client_encoding TO 'utf8';
ALTER ROLE db_user SET default_transaction_isolation TO 'read committed';
ALTER ROLE db_user SET timezone TO 'Asia/Dhaka';
GRANT ALL PRIVILEGES ON DATABASE npt TO db_user;
ALTER DATABASE npt OWNER TO db_user;
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
DEBUG=True
DB_ENGINE=django.db.backends.postgresql
DB_NAME=npt
DB_USER=your-db-user
DB_PASS=your-db-pass
DB_HOST=localhost
DB_PORT=5432
```

---

## 5. 📁 Database & Static Files

```bash
python manage.py makemigrations
python manage.py migrate
python manage.py createsuperuser
python manage.py collectstatic
```

---

## 6. 🔥 Gunicorn Setup

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

## 7. 🌐 Nginx Setup

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

## 8. 🔐 Firewall Setup

```bash
sudo ufw delete allow 8000
sudo ufw allow 'Nginx Full'
```

---

## 9. ✅ Access Application

- App: `http://your_server_ip/`
- Admin: `http://your_server_ip/admin/`

---

## 10. 🧪 Useful Debug Commands

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