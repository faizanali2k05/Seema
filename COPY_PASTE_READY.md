# 🚀 Copy-Paste Deployment Commands - Ready to Use!

**Your VPS IP:** `69.62.110.2`  
**Domain:** `seemaai.co.uk`  
**Status:** ✅ Ready to Deploy!

---

## ⚡ Step-by-Step Commands (Copy & Paste)

### STEP 1: SSH into Your VPS

```bash
ssh root@69.62.110.2
```

When prompted, enter your root password (from Hostinger email).

---

### STEP 2: Update & Install (Copy entire block, paste it)

```bash
apt update && apt upgrade -y && apt install -y python3 python3-pip python3-venv git nginx supervisor curl certbot python3-certbot-nginx
```

---

### STEP 3: Create App User

```bash
useradd -m -s /bin/bash seema
usermod -aG sudo seema
su - seema
```

---

### STEP 4: Create App Directory

```bash
mkdir -p /home/seema/seema-app
cd /home/seema/seema-app
```

---

### STEP 5: Get Your Files to VPS

**Choose ONE method below:**

#### **Option A: GitHub + Git (RECOMMENDED ✅)**

Much easier! No password issues. See **DEPLOYMENT_VIA_GITHUB.md** for full guide.

Quick version:
```bash
# On VPS as seema user
cd /home/seema
git clone https://github.com/YOUR_USERNAME/seema-app.git seema-app
cd seema-app
```

#### **Option B: SCP Upload**

Exit VPS first (Ctrl+D or type `exit`)

Then in **Windows PowerShell**, run these:

```powershell
cd c:\Users\Faizan\Desktop\Seema

scp -r app seema@69.62.110.2:/home/seema/seema-app/
scp -r data seema@69.62.110.2:/home/seema/seema-app/
scp requirements.txt seema@69.62.110.2:/home/seema/seema-app/
scp wsgi.py seema@69.62.110.2:/home/seema/seema-app/
```

When prompted, use your root/seema password (set with `passwd seema` first).

---

### STEP 6: Setup Python Environment (SSH back as seema)

```bash
ssh seema@69.62.110.2
cd /home/seema/seema-app
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn
```

---

### STEP 7: Test Gunicorn (Should see startup message)

```bash
gunicorn -w 4 -b 127.0.0.1:8000 wsgi:application
```

Press `Ctrl+C` when you see it's running. ✅

---

### STEP 8: Configure Nginx (as root)

SSH as root and run:

```bash
sudo nano /etc/nginx/sites-available/seemaai.co.uk
```

Paste this entire block:

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

Save: `Ctrl+X` → `Y` → `Enter`

Then run:

```bash
sudo ln -s /etc/nginx/sites-available/seemaai.co.uk /etc/nginx/sites-enabled/
sudo rm /etc/nginx/sites-enabled/default
sudo nginx -t
sudo systemctl restart nginx
```

---

### STEP 9: Configure Supervisor (as root)

```bash
sudo nano /etc/supervisor/conf.d/seema.conf
```

Paste this entire block:

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

Save: `Ctrl+X` → `Y` → `Enter`

Then run:

```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl status
```

You should see: `seema RUNNING pid ####` ✅

---

### STEP 10: Install SSL Certificate

```bash
sudo certbot --nginx -d seemaai.co.uk -d www.seemaai.co.uk
```

Follow prompts:
- Email: (your email)
- Terms: `Y`
- Share: `N`

---

### STEP 11: Verify It Works!

**In your browser, visit:**

```
https://seemaai.co.uk
```

You should see your Seema app! 🎉

---

## 🔍 Quick Status Check Commands

If something doesn't work, check with these:

```bash
# Is app running?
sudo supervisorctl status seema

# View recent errors
tail -f /var/log/seema.log

# Is web server running?
sudo systemctl status nginx

# Can you reach the app?
curl http://127.0.0.1:8000

# Does domain resolve?
nslookup seemaai.co.uk
```

---

## 📋 DNS Setup (Do This Before Deployment if not done)

1. **Hostinger Dashboard** → **Domains** → **seemaai.co.uk**
2. Click **Manage DNS**
3. Find **A Records** section
4. Create/Update records:
   - **Host:** `@` → **Value:** `69.62.110.2`
   - **Host:** `www` → **Value:** `69.62.110.2`
5. **Save** and wait 5-30 minutes

Test DNS:
```bash
nslookup seemaai.co.uk
# Should return: 69.62.110.2
```

---

## 🚨 Troubleshooting Quick Fixes

**502 Bad Gateway?**
```bash
sudo supervisorctl restart seema
sudo systemctl restart nginx
```

**Can't SSH?**
```bash
# Check connection
ping 69.62.110.2

# Verify SSH is working
ssh -v root@69.62.110.2
```

**Domain not working?**
```bash
# Check DNS
nslookup seemaai.co.uk
# Should show 69.62.110.2

# If not, wait 30 minutes
```

**App keeps crashing?**
```bash
tail -f /var/log/seema.log
# Look for error messages
```

---

## 💾 Commands to Save for Later

```bash
# SSH in
ssh root@69.62.110.2

# Restart app
sudo supervisorctl restart seema

# View logs
tail -f /var/log/seema.log

# Restart web server
sudo systemctl restart nginx

# Check status
sudo supervisorctl status seema

# Update system
sudo apt update && sudo apt upgrade -y

# Reboot VPS
sudo reboot
```

---

## ✅ Final Checklist

- [ ] Domain DNS points to 69.62.110.2
- [ ] Can SSH: `ssh root@69.62.110.2`
- [ ] Files uploaded successfully
- [ ] Gunicorn runs locally
- [ ] Nginx configured
- [ ] Supervisor running
- [ ] SSL installed
- [ ] Browser loads: `https://seemaai.co.uk` ✅

**All done? You're live!** 🚀

---

## 📱 Your VPS Details (Save These)

```
VPS IP:       69.62.110.2
VPS Type:     KVM4 (Ubuntu)
Domain:       seemaai.co.uk
App Port:     8000 (internal)
Web Ports:    80 (HTTP), 443 (HTTPS)
Database:     /home/seema/seema-app/data/demo-workflows.db
App User:     seema
Logs:         /var/log/seema.log
```

---

**Ready to deploy? Start at STEP 1 and copy-paste each command! 🎉**
