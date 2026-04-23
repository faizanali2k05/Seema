# VPS Basics - Everything You Need to Know

## 🖥️ What is a VPS?

A **Virtual Private Server (VPS)** is a rented computer on the internet:

```
Your Home Computer (Local)     →    Hostinger VPS (Cloud)
├─ Local files                     ├─ Your app runs 24/7
├─ Local applications              ├─ Always connected to internet
└─ Only on when you use it         └─ Your "server" on the cloud
```

**Key differences from local:**
- VPS runs even when your computer is off
- VPS accessible from anywhere via domain
- VPS files can be edited remotely via SSH
- VPS handles user traffic 24/7/365

---

## 🔐 SSH - Your Remote Connection

**SSH = Secure Shell** = Remote terminal access

```
Windows Computer              VPS Server
    (You)                      (Hostinger)
       |
       |--- SSH (port 22) ---|
       |
    (encrypted connection)
```

### Connect to VPS:

```bash
ssh username@vps_ip_address
# Password prompt appears
# Type password (letters don't show while typing - normal!)
# Enter
```

Example:
```bash
ssh root@69.62.110.2
# Password: ••••••••••• (enter your password)
```

---

## 📁 VPS File Structure

```
/
├── home/
│   └── seema/                    ← Your app user's home
│       └── seema-app/           ← Your application folder
│           ├── app/             ← Python files
│           ├── data/            ← Database & files
│           ├── venv/            ← Python virtual environment
│           ├── wsgi.py          ← Entry point for Gunicorn
│           └── requirements.txt
├── etc/
│   ├── nginx/                    ← Web server config
│   └── supervisor/               ← Process manager config
└── var/
    ├── log/
    │   ├── seema.log            ← Your app logs
    │   └── nginx/               ← Web server logs
    └── www/
        └── html/                ← Public files (static)
```

### Important paths:

```bash
# Your app
/home/seema/seema-app

# Application logs
/var/log/seema.log

# Nginx config
/etc/nginx/sites-available/seemaai.co.uk

# Supervisor config
/etc/supervisor/conf.d/seema.conf
```

---

## 📚 Essential VPS Commands

### System Information

```bash
# Current user
whoami

# Current directory
pwd

# List files
ls -la

# Disk space
df -h

# Memory usage
free -h

# System uptime
uptime
```

### Navigation

```bash
# Go to folder
cd /home/seema/seema-app

# Go to home folder
cd ~

# Go back
cd ..

# Go to specific path
cd /var/log
```

### File Editing

```bash
# Edit file (nano editor)
nano /path/to/file

# Exit nano: Ctrl+X, Y, Enter
# Or just Ctrl+C if you don't want to save

# View file contents
cat /path/to/file

# View last lines of file (logs)
tail -f /var/log/seema.log  # Ctrl+C to stop
```

### Application Management

```bash
# Check if app is running
sudo supervisorctl status

# Restart app
sudo supervisorctl restart seema

# Stop app
sudo supervisorctl stop seema

# Start app
sudo supervisorctl start seema

# View logs in real-time
tail -f /var/log/seema.log
```

### Server Management

```bash
# Restart Nginx
sudo systemctl restart nginx

# Check Nginx status
sudo systemctl status nginx

# Reboot VPS
sudo reboot

# Check SSL certificate
sudo certbot certificates

# Renew SSL certificate
sudo certbot renew
```

### Package Management

```bash
# Update package list
sudo apt update

# Upgrade all packages
sudo apt upgrade -y

# Install package
sudo apt install package_name

# Remove package
sudo apt remove package_name
```

---

## 🔍 Common Tasks

### Upload Files to VPS

From your Windows PowerShell:

```powershell
# Upload single file
scp c:\path\to\file.txt seema@69.62.110.2:/home/seema/seema-app/

# Upload entire folder
scp -r c:\path\to\folder seema@69.62.110.2:/home/seema/seema-app/

# Download from VPS
scp seema@69.62.110.2:/home/seema/seema-app/data/file.db c:\Desktop\
```

### Check Application Status

```bash
# Is it running?
sudo supervisorctl status seema

# See recent errors
tail -f /var/log/seema.log

# Check if port 8000 is listening
sudo netstat -tlnp | grep 8000
```

### Restart Application

```bash
# Method 1: Supervisor
sudo supervisorctl restart seema

# Method 2: Manual restart
sudo supervisorctl stop seema
sleep 2
sudo supervisorctl start seema

# Check status
sudo supervisorctl status seema
```

### Increase Gunicorn Workers (if needed for high traffic)

Edit supervisor config:
```bash
sudo nano /etc/supervisor/conf.d/seema.conf
```

Change this line:
```
command=/home/seema/seema-app/venv/bin/gunicorn -w 4 -b 127.0.0.1:8000 wsgi:application
```

To (increase `-w 4` to higher number):
```
command=/home/seema/seema-app/venv/bin/gunicorn -w 8 -b 127.0.0.1:8000 wsgi:application
```

Save and reload:
```bash
sudo supervisorctl reread
sudo supervisorctl update
sudo supervisorctl restart seema
```

---

## ⚠️ Common Problems & Solutions

### Problem: "Permission denied"

**Cause:** You don't have permission to edit file

**Solution:**
```bash
# Add sudo before command
sudo nano /etc/nginx/sites-available/seemaai.co.uk

# Or change file ownership
sudo chown seema:seema /home/seema/seema-app/file.txt
```

### Problem: "502 Bad Gateway"

**Cause:** Gunicorn not running or Nginx can't connect to it

**Check:**
```bash
sudo supervisorctl status seema          # Should show RUNNING
sudo netstat -tlnp | grep 8000           # Should show Gunicorn listening
sudo nginx -t                             # Should show OK
```

**Fix:**
```bash
sudo supervisorctl restart seema
sudo systemctl restart nginx
```

### Problem: "Connection refused"

**Cause:** Can't SSH into VPS or service not running

**Check:**
```bash
# From your computer - test connection
ping 69.62.110.2

# Check if SSH is working
ssh -v root@69.62.110.2
```

### Problem: "Disk full"

**Check usage:**
```bash
df -h

# Find large files/folders
du -sh /home/seema/seema-app/*
du -sh /var/log/*
```

**Clean up:**
```bash
# Clear old logs
sudo journalctl --vacuum=10d

# Remove old package cache
sudo apt clean && sudo apt autoclean
```

---

## 🔒 Security Best Practices

```bash
# 1. Change root password regularly
# Do this in Hostinger control panel

# 2. Keep system updated
sudo apt update && sudo apt upgrade -y

# 3. Check open ports
sudo netstat -tlnp

# 4. Check running processes
ps aux

# 5. Review logs for suspicious activity
tail -f /var/log/auth.log

# 6. Set up firewall (ufw)
sudo apt install ufw
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw allow 22/tcp      # SSH
sudo ufw allow 80/tcp      # HTTP
sudo ufw allow 443/tcp     # HTTPS
sudo ufw enable
```

---

## 📊 Monitoring & Logs

### System Logs

```bash
# All system messages
tail -f /var/log/syslog

# Authentication logs
tail -f /var/log/auth.log

# Kernel messages
dmesg | tail -20
```

### Application Logs

```bash
# Your app
tail -f /var/log/seema.log

# Nginx access
tail -f /var/log/nginx/access.log

# Nginx errors
tail -f /var/log/nginx/error.log
```

### Supervisor Logs

```bash
# Supervisor main log
sudo tail -f /var/log/supervisor/supervisord.log

# Individual program log
sudo tail -f /var/log/seema.log
```

---

## 🚀 Quick Reference Card

```bash
# Most used commands:
ssh seema@YOUR_VPS_IP              # Connect
cd /home/seema/seema-app           # Go to app
tail -f /var/log/seema.log         # View logs
sudo supervisorctl status          # Check app status
sudo supervisorctl restart seema   # Restart app
sudo systemctl restart nginx       # Restart web server
sudo apt update && apt upgrade -y  # Update system
nano filename.txt                  # Edit file
scp file seema@IP:/path/           # Upload file
```

---

## 📞 Need Help?

**Issue:** VPS not responding
**Solution:** Check Hostinger dashboard → VPS → Power status

**Issue:** Can't SSH in
**Solution:** Reset password in Hostinger dashboard

**Issue:** Domain not working
**Solution:** Check DNS is pointing to correct IP (use `nslookup seemaai.co.uk`)

**Issue:** App keeps crashing
**Solution:** Check logs: `tail -f /var/log/seema.log`

---

## 🎓 Further Learning

- **Nginx docs:** nginx.org/en/docs
- **Supervisor docs:** supervisord.org
- **Linux commands:** man.linuxmint.com
- **Python Gunicorn:** gunicorn.org

Good luck with your VPS deployment! 🚀
