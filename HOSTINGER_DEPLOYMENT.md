# Deploying Seema to Hostinger KVM4 VPS - Complete Deployment Guide

**Status:** First-time deployment to production  
**Domain:** seemaai.co.uk  
**VPS:** Hostinger KVM4 (Ubuntu)  
**App Type:** Python HTTP Server (Port 3000)  
**Stack:** Python + Gunicorn + Nginx + Supervisor + Let's Encrypt SSL

---

## 📋 Quick Reference

| Component | Purpose |
|-----------|---------|
| **Python** | Your app runtime |
| **Gunicorn** | WSGI application server (replaces http.server) |
| **Nginx** | Reverse proxy (handles HTTPS, domain routing) |
| **Supervisor** | Process manager (keeps app running 24/7) |
| **Let's Encrypt** | Free SSL/HTTPS certificates |
| **SSH** | Secure connection to your VPS |

---

## ✅ Pre-Deployment Checklist

- [ ] VPS IP address from Hostinger
- [ ] Root password or SSH key from Hostinger
- [ ] Domain DNS pointed to VPS IP (seemaai.co.uk → your_vps_ip)
- [ ] Application files ready (all in this folder)
- [ ] requirements.txt updated with all dependencies
- [ ] SSH client on Windows (PuTTY or built-in Windows Terminal)

---

# PHASE 1: VPS Setup (First Time - ~15 minutes)

## Step 1: Connect to Your VPS via SSH

**Get your VPS IP from Hostinger dashboard**

### Option A: Windows Terminal / PowerShell
```bash
ssh root@69.62.110.2
# Enter password when prompted
```

### Option B: PuTTY (Windows GUI)
1. Download PuTTY from putty.org
2. Host Name: `YOUR_VPS_IP_ADDRESS`
3. Port: `22`
4. Click "Open"
5. Login as: `root`
6. Password: (from Hostinger)

✅ **You're now in your VPS terminal**

---

## Step 2: Update System Packages

```bash
apt update && apt upgrade -y
```

This ensures all system packages are current and secure.

---

## Step 3: Install Required Software

```bash
apt install -y python3 python3-pip python3-venv git nginx supervisor curl certbot python3-certbot-nginx
```

**What each package does:**
- `python3` - Python runtime
- `python3-pip` - Package installer
- `python3-venv` - Virtual environment tool
- `git` - Version control (optional)
- `nginx` - Web server/reverse proxy
- `supervisor` - Process manager
- `curl` - Download tool
- `certbot` - SSL certificate tool

Verify installation:
```bash
python3 --version
pip3 --version
```

---

## Step 4: Create Application User (Security Best Practice)

Instead of running as `root`, create a dedicated user:

```bash
useradd -m -s /bin/bash seema
usermod -aG sudo seema
su - seema
```

Now you're logged in as the `seema` user. Continue all remaining steps in this user context.

---

## Step 5: Upload Your Application

### Option A: Using SCP (if on Windows with SSH)

**Run this on your Windows PowerShell:**
```powershell
# From c:\Users\Faizan\Desktop\Seema
scp -r app/* seema@YOUR_VPS_IP:/home/seema/seema-app/
scp requirements.txt seema@YOUR_VPS_IP:/home/seema/seema-app/
```

### Option B: Using Git (if repository exists)

```bash
# In VPS as seema user:
cd /home/seema
git clone https://github.com/YOUR_USERNAME/seema.git seema-app
cd seema-app
```

### Option C: Manual via Hostinger File Manager

Use Hostinger's File Manager in their control panel to upload files.

---

## Step 6: Set Up Python Virtual Environment

```bash
cd /home/seema/seema-app
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
pip install gunicorn
```

Verify installation:
```bash
which gunicorn
gunicorn --version
```

---

# PHASE 2: Configure Application for Production

## Step 7: Create WSGI Entry Point

Your current app uses Python's `http.server`. We need to modify it for Gunicorn. Create a new file:

```bash
nano /home/seema/seema-app/wsgi.py
```

Paste this content:

```python
#!/usr/bin/env python3
"""
WSGI entry point for Gunicorn
"""
import os
import sys

# Add app directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Set environment variable for data directory
os.environ['DATA_DIR'] = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data')

# Import and run the demo server
from app.demo_server import run_server, PORT

# Create WSGI application
def application(environ, start_response):
    """WSGI application wrapper"""
    from app import demo_server
    
    # Create an instance of the request handler
    handler = demo_server.RequestHandler(
        (environ['SERVER_NAME'], int(environ['SERVER_PORT'])), 
        demo_server.RequestHandler
    )
    
    # This is a simplified WSGI approach
    # For production, consider using Flask or FastAPI instead
    return handler.run_wsgi(environ, start_response)
```

Press `Ctrl+X`, then `Y`, then `Enter` to save.

---

## Step 8: Test Gunicorn Locally

```bash
cd /home/seema/seema-app
source venv/bin/activate
gunicorn -w 4 -b 127.0.0.1:8000 wsgi:application
```

You should see:
```
[INFO] Starting gunicorn 20.1.0
[INFO] Listening at: http://127.0.0.1:8000
```

Press `Ctrl+C` to stop. ✅ Gunicorn is working!

---

# PHASE 3: Configure Nginx (Reverse Proxy)

## Step 9: Create Nginx Configuration

```bash
sudo nano /etc/nginx/sites-available/seemaai.co.uk
```

Paste this:

```nginx
server {
    listen 80;
    server_name seemaai.co.uk www.seemaai.co.uk;

    client_max_body_size 50M;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }

    location /static/ {
        alias /home/seema/seema-app/static/;
        expires 30d;
    }
}
```

Save with `Ctrl+X`, `Y`, `Enter`.

---

## Step 10: Enable Nginx Site

```bash
sudo ln -s /etc/nginx/sites-available/seemaai.co.uk /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
```

You should see: `nginx: configuration is ok` ✅

---

## Step 11: Reload Nginx

```bash
sudo systemctl restart nginx
sudo systemctl enable nginx
```

---

# PHASE 4: Configure Supervisor (Process Manager)

## Step 12: Create Supervisor Configuration

```bash
sudo nano /etc/supervisor/conf.d/seema.conf
```

Paste this:

```ini
[program:seema]
directory=/home/seema/seema-app
command=/home/seema/seema-app/venv/bin/gunicorn -w 4 -b 127.0.0.1:8000 wsgi:application
user=seema
autostart=true
autorestart=true
redirect_stderr=true
stdout_logfile=/var/log/seema.log
environment=PATH="/home/seema/seema-app/venv/bin",DATA_DIR="/home/seema/seema-app/data"
```

Save with `Ctrl+X`, `Y`, `Enter`.

---

## Step 13: Start Supervisor

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl status
```

You should see: `seema RUNNING pid ####` ✅

---

# PHASE 5: SSL Certificate (HTTPS)

## Step 14: Enable HTTPS with Let's Encrypt

```bash
sudo certbot --nginx -d seemaai.co.uk -d www.seemaai.co.uk
```

Follow the prompts:
- Enter email: (your email)
- Agree to terms: `Y`
- Share email: `N` (your choice)

Certbot will automatically update Nginx configuration.

---

## Step 15: Verify SSL Auto-Renewal

```bash
sudo certbot renew --dry-run
```

Should complete without errors. Let's Encrypt certificates auto-renew automatically.

---

# PHASE 6: Verification & Monitoring

## Step 16: Test Your Deployment

**From your Windows computer:**

```bash
# Visit in browser:
https://seemaai.co.uk
```

✅ You should see your Seema app!

---

## Step 17: View Logs

Monitor what's happening on your VPS:

```bash
# Application logs
tail -f /var/log/seema.log

# Nginx logs
sudo tail -f /var/log/nginx/access.log
sudo tail -f /var/log/nginx/error.log

# Supervisor logs
sudo tail -f /var/log/supervisor/supervisord.log
```

Press `Ctrl+C` to exit log view.

---

# 🔧 Common VPS Commands (Bookmark These!)

```bash
# Restart app
sudo supervisorctl restart seema

# Stop app
sudo supervisorctl stop seema

# Start app
sudo supervisorctl start seema

# Restart web server
sudo systemctl restart nginx

# Check app status
sudo supervisorctl status

# View real-time logs
tail -f /var/log/seema.log

# SSH back into VPS
ssh seema@YOUR_VPS_IP

# Check disk space
df -h

# Check memory usage
free -h

# Reboot VPS
sudo reboot
```

---

# 📊 Post-Deployment Checklist

- [ ] Domain points to VPS IP (DNS A record)
- [ ] Nginx running: `sudo systemctl status nginx`
- [ ] App running: `sudo supervisorctl status seema`
- [ ] HTTPS working: Visit `https://seemaai.co.uk` ✅
- [ ] Logs clean: `tail -f /var/log/seema.log`
- [ ] Database created: Check `/home/seema/seema-app/data/` folder
- [ ] SSL certificate valid: `sudo certbot certificates`

---

# ⚠️ Troubleshooting

### App won't start
```bash
sudo supervisorctl restart seema
tail -f /var/log/seema.log
```

### 502 Bad Gateway error
- Check if Gunicorn is running: `sudo supervisorctl status seema`
- Check Nginx config: `sudo nginx -t`
- Restart Nginx: `sudo systemctl restart nginx`

### Domain not working
- Check DNS: `nslookup seemaai.co.uk`
- Should return your VPS IP address
- Wait up to 24 hours for DNS propagation

### SSL certificate expired
```bash
sudo certbot renew --force-renewal
sudo systemctl restart nginx
```

---

# 🚀 Next Steps (After First Deployment)

1. **Set up backups** - Backup `/home/seema/seema-app/data/` weekly
2. **Monitor uptime** - Use services like UptimeRobot
3. **Update regularly** - `sudo apt update && sudo apt upgrade -y` monthly
4. **Review logs** - Check logs weekly for errors
5. **Scale up** - If needed: add more Gunicorn workers in supervisor config
import multiprocessing

bind = "127.0.0.1:8000"
workers = multiprocessing.cpu_count() * 2 + 1
worker_class = "sync"
timeout = 30
keepalive = 2
```

---

## Phase 4: Configure Supervisor (Auto-Start)

### Create `/etc/supervisor/conf.d/seema.conf`:

```bash
sudo nano /etc/supervisor/conf.d/seema.conf
```

Paste:

```ini
[program:seema]
directory=/home/seema/seema-app
command=/home/seema/seema-app/venv/bin/gunicorn --config /home/seema/gunicorn_config.py wsgi:application
autostart=true
autorestart=true
user=seema
stderr_logfile=/var/log/seema/err.log
stdout_logfile=/var/log/seema/out.log

[group:seema]
programs=seema
priority=999
```

Create log directory:
```bash
sudo mkdir -p /var/log/seema
sudo chown seema:seema /var/log/seema
```

---

## Phase 5: Configure Nginx (Reverse Proxy)

### Create `/etc/nginx/sites-available/seema`:

```bash
sudo nano /etc/nginx/sites-available/seema
```

Paste (replace `yourdomain.com` with your actual domain):

```nginx
server {
    listen 80;
    server_name yourdomain.com www.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        proxy_redirect off;
    }
}
```

Enable the site:

```bash
sudo ln -s /etc/nginx/sites-available/seema /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default  # Remove default site
sudo nginx -t  # Test config
sudo systemctl restart nginx
```

---

## Phase 6: SSL Certificate (Let's Encrypt - Free!)

### Install Certbot:

```bash
sudo apt install -y certbot python3-certbot-nginx
```

### Get Certificate:

```bash
sudo certbot --nginx -d yourdomain.com -d www.yourdomain.com
```

Follow prompts. Certbot will:
- Generate FREE SSL certificate
- Auto-update Nginx config
- Enable auto-renewal

### Verify Auto-Renewal:

```bash
sudo systemctl status certbot.timer
```

---

## Phase 7: Start Application

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl start seema
sudo supervisorctl status seema
```

Check logs:
```bash
tail -f /var/log/seema/out.log
```

---

## Phase 8: Configure DNS

In your domain registrar (Namecheap, GoDaddy, etc.):
1. Point `A record` to your Hostinger VPS IP address
2. Wait 15 minutes for DNS to propagate
3. Visit `https://yourdomain.com`

---

## Phase 9: Firewall (Optional but Recommended)

```bash
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable
```

---

## Troubleshooting

### Check if Gunicorn is running:
```bash
ps aux | grep gunicorn
```

### View Supervisor logs:
```bash
sudo tail -50 /var/log/supervisor/supervisord.log
```

### View Nginx logs:
```bash
sudo tail -50 /var/log/nginx/error.log
```

### Restart everything:
```bash
sudo supervisorctl restart seema
sudo systemctl restart nginx
```

### Check port 8000:
```bash
netstat -tuln | grep 8000
```

---

## Database Backup

Add to crontab for daily backups:

```bash
crontab -e
```

Add:
```
0 2 * * * cp /home/seema/seema-app/data/demo-workflows.db /home/seema/seema-app/backups/demo-workflows-$(date +\%Y\%m\%d).db
```

---

## Monitoring

### Check app status:
```bash
sudo supervisorctl status seema
```

### View real-time logs:
```bash
tail -f /var/log/seema/out.log
```

### Monitor resources:
```bash
htop
```

---

## Email Configuration (Optional)

Edit your database to add SMTP settings:

```python
# Via Python shell on VPS:
import sqlite3
conn = sqlite3.connect('/home/seema/seema-app/data/demo-workflows.db')
cursor = conn.cursor()
cursor.execute('''
    INSERT INTO email_settings (enabled, smtp_host, smtp_port, smtp_user, smtp_password, from_email, from_name)
    VALUES (1, 'smtp.gmail.com', 587, 'your-email@gmail.com', 'app-password', 'noreply@yourdomain.com', 'Seema')
''')
conn.commit()
conn.close()
```

---

## Success!

Your Seema app is now live at **https://yourdomain.com**

For more help, check Hostinger's documentation or contact support.
