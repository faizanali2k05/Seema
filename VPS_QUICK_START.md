# Seema VPS Deployment - Quick Start Checklist

## 🎯 Your Deployment Plan Summary

**Project:** Seema (AI Law Firm Compliance System)  
**Domain:** seemaai.co.uk  
**VPS Provider:** Hostinger KVM4 (Ubuntu)  
**Environment:** Production  

---

## 📝 What You Need Before Starting

```
☐ Hostinger Dashboard Access
☐ VPS IP Address (from Hostinger control panel)
☐ Root Password or SSH Key
☐ Domain DNS configured to point to VPS IP
  └─ Use Hostinger's nameservers or:
     A Record: seemaai.co.uk → YOUR_VPS_IP
     A Record: www.seemaai.co.uk → YOUR_VPS_IP
☐ SSH Client (PuTTY or built-in Windows SSH)
☐ All files from this folder ready
```

---

## 🚀 Deployment Timeline

| Phase | Task | Time | Status |
|-------|------|------|--------|
| 1 | SSH into VPS & install packages | 5 min | ⏳ |
| 2 | Upload application files | 3 min | ⏳ |
| 3 | Configure Gunicorn + Nginx | 5 min | ⏳ |
| 4 | Configure Supervisor | 2 min | ⏳ |
| 5 | Install SSL certificate | 3 min | ⏳ |
| 6 | Test and verify | 2 min | ⏳ |
| **Total** | | **~20 min** | |

---

## 📋 Step-by-Step Deployment (Copy-Paste Commands)

### STEP 1: Connect to VPS
```powershell
# Windows PowerShell
ssh root@69.62.110.2
```

### STEP 2: Run These Commands in Order

```bash
# 1. Update system
apt update && apt upgrade -y

# 2. Install packages
apt install -y python3 python3-pip python3-venv git nginx supervisor curl certbot python3-certbot-nginx

# 3. Create app user
useradd -m -s /bin/bash seema
su - seema

# 4. Create app directory
mkdir -p /home/seema/seema-app
cd /home/seema/seema-app

# 5. Upload files (do this from your Windows machine instead)
# Use: scp -r app/* seema@69.62.110.2:/home/seema/seema-app/
```

### STEP 3: Upload Application Files (Windows PowerShell)

Run this FROM your Windows machine (not on VPS):

```powershell
# Change to your Seema folder
cd c:\Users\Faizan\Desktop\Seema

# Upload application files
scp -r app seema@69.62.110.2:/home/seema/seema-app/
scp -r data seema@69.62.110.2:/home/seema/seema-app/
scp requirements.txt seema@69.62.110.2:/home/seema/seema-app/
scp wsgi.py seema@69.62.110.2:/home/seema/seema-app/
scp seema-demo.html seema@69.62.110.2:/home/seema/seema-app/
```

### STEP 4: Set Up Python Environment (back on VPS)

```bash
cd /home/seema/seema-app
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn
```

### STEP 5: Test Gunicorn

```bash
gunicorn -w 4 -b 127.0.0.1:8000 wsgi:application
# Should start successfully - Ctrl+C to stop
```

### STEP 6: Configure Nginx (as root)

```bash
sudo nano /etc/nginx/sites-available/seemaai.co.uk
```

Paste this content:

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
    }
}
```

Then:
```bash
sudo ln -s /etc/nginx/sites-available/seemaai.co.uk /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl restart nginx
```

### STEP 7: Configure Supervisor (as root)

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

Then:
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl status
# Should show: seema RUNNING
```

### STEP 8: Install SSL (HTTPS)

```bash
sudo certbot --nginx -d seemaai.co.uk -d www.seemaai.co.uk
```

Answer the prompts:
- Email: (your email)
- Terms: `y`
- Share: `n`

---

## ✅ Verification

After all steps, test in your browser:

```
https://seemaai.co.uk
```

You should see your Seema application! 🎉

---

## 🔍 If Something Goes Wrong

**App won't start:**
```bash
sudo supervisorctl restart seema
tail -f /var/log/seema.log
```

**502 Bad Gateway:**
```bash
sudo supervisorctl status seema
sudo nginx -t
```

**Domain not working:**
```bash
nslookup seemaai.co.uk  # Should return your VPS IP
```

---

## 📞 Hostinger Support

If you need help with your VPS:
- Hostinger Dashboard: https://hpanel.hostinger.com
- Support: support@hostinger.com
- SSH/Root password reset available in dashboard

---

## 🔄 After Deployment

**Regular maintenance commands:**

```bash
# Restart app
sudo supervisorctl restart seema

# View logs
tail -f /var/log/seema.log

# Update system
sudo apt update && sudo apt upgrade -y

# Check disk usage
df -h

# Reboot if needed
sudo reboot
```

---

**Good luck with your deployment! 🚀**
