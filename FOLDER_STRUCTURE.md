# 📂 Project Structure & Files Overview

**Your Complete Seema Deployment Package**

---

## 📦 Current Local Folder Structure

```
c:\Users\Faizan\Desktop\Seema\
│
├── 📁 app/
│   ├── demo-server.py              ← Main Python application
│   ├── knowledge-engine.py         ← Logic engine
│   ├── seema-demo.html             ← Web interface
│   └── __pycache__/                ← Python cache (ignore)
│
├── 📁 data/
│   └── evidence/                   ← Data folder (databases go here)
│
├── 📁 .venv/                       ← Your local Python environment (don't upload)
│
├── 📄 wsgi.py                      ← ✅ NEW! Gunicorn entry point
├── 📄 requirements.txt             ← ✅ UPDATED! Has Gunicorn now
├── 📄 README.md                    ← Local setup instructions
│
└── 📚 DEPLOYMENT DOCUMENTATION
    ├── INDEX.md                    ← 📍 START HERE - File guide
    ├── DEPLOYMENT_SUMMARY.md       ← Overview of entire process
    ├── VPS_QUICK_START.md          ← 🚀 FAST deployment (20 min)
    ├── HOSTINGER_DEPLOYMENT.md     ← Detailed step-by-step
    ├── DNS_SETUP.md                ← Domain configuration
    ├── VPS_BASICS.md               ← VPS commands & concepts
    ├── DEPLOYMENT_FLOWCHART.md     ← Visual flowchart & troubleshooting
    ├── FOLDER_STRUCTURE.md         ← This file
    └── HOSTINGER_DEPLOYMENT.md     ← Legacy/backup copy
```

---

## 📋 What Gets Uploaded to VPS

```
What You UPLOAD:
├── app/
│   ├── demo-server.py
│   ├── knowledge-engine.py
│   ├── seema-demo.html
│   └── __pycache__/ (optional, recreated)
├── data/
│   └── (empty OK - database created on VPS)
├── wsgi.py
├── requirements.txt
└── seema-demo.html (optional copy)

What You DON'T upload:
├── .venv/                          (VPS will create own)
├── __pycache__/                    (auto-generated)
├── *.md documentation files        (optional - for reference only)
└── This local folder structure
```

---

## 🖥️ VPS Folder Structure (After Deployment)

```
/home/seema/seema-app/
│
├── 📁 app/
│   ├── demo-server.py
│   ├── knowledge-engine.py
│   ├── seema-demo.html
│   └── __pycache__/
│
├── 📁 data/
│   ├── demo-workflows.db           ← SQLite database (created automatically)
│   ├── evidence/
│   └── (other data files)
│
├── 📁 venv/                        ← Python virtual environment (created on VPS)
│   ├── bin/
│   │   ├── python3
│   │   ├── pip3
│   │   └── gunicorn
│   └── lib/
│       └── python3.x/site-packages/
│           └── (all packages from requirements.txt)
│
├── 📄 wsgi.py                      ← Gunicorn entry point
├── 📄 requirements.txt             ← Python dependencies
└── 📄 seema-demo.html             ← Frontend (optional)
```

---

## 📄 New Files Created for Deployment

### **wsgi.py** (Application Entry Point)

```
Purpose: Gunicorn's connection point to your app
Location: /home/seema/seema-app/wsgi.py (on VPS)
Created: ✅ Included in package
Used By: Gunicorn when starting the app
Command: gunicorn wsgi:application
```

**What it does:**
- Wraps your demo-server.py
- Provides WSGI interface for Gunicorn
- Sets environment variables (DATA_DIR)
- Handles requests and errors

---

### **requirements.txt** (Updated)

```
Before:
  reportlab==4.0.7

After:
  reportlab==4.0.7
  gunicorn==20.1.0
  requests==2.28.0
```

**Changed:** Added Gunicorn and requests library

---

## 🔧 Configuration Files (Created on VPS)

### **/etc/nginx/sites-available/seemaai.co.uk**

```
Location: /etc/nginx/sites-available/seemaai.co.uk
Purpose: Nginx configuration
Listening: Port 80 (HTTP) and 443 (HTTPS)
Forwards to: http://127.0.0.1:8000 (Gunicorn)
```

### **/etc/supervisor/conf.d/seema.conf**

```
Location: /etc/supervisor/conf.d/seema.conf
Purpose: App process management
Monitors: /home/seema/seema-app/venv/bin/gunicorn
Restarts: If app crashes
Logs to: /var/log/seema.log
```

---

## 📍 Important VPS Paths

| Path | Purpose | Notes |
|------|---------|-------|
| `/home/seema/seema-app` | Your app folder | Main directory |
| `/home/seema/seema-app/data` | Database location | SQLite files here |
| `/home/seema/seema-app/venv` | Python environment | Python 3 + packages |
| `/etc/nginx/sites-available` | Nginx config | Website setup |
| `/etc/supervisor/conf.d` | Supervisor config | Auto-restart setup |
| `/var/log/seema.log` | App logs | View with: tail -f |
| `/var/log/nginx` | Web server logs | Nginx activity |

---

## 🗂️ Documentation File Purpose

| File | Purpose | Length | Read When |
|------|---------|--------|-----------|
| **INDEX.md** | File guide & index | 5 min | First, to understand structure |
| **DEPLOYMENT_SUMMARY.md** | Overview & timeline | 10 min | Planning deployment |
| **VPS_QUICK_START.md** | Fast deployment guide | 20 min | Ready to deploy now |
| **HOSTINGER_DEPLOYMENT.md** | Detailed walkthrough | 30 min | Want full explanations |
| **DNS_SETUP.md** | Domain configuration | 10 min | Setting up seemaai.co.uk |
| **VPS_BASICS.md** | VPS commands & concepts | 20 min | Learning VPS |
| **DEPLOYMENT_FLOWCHART.md** | Flowchart & troubleshooting | 15 min | Troubleshooting issues |
| **FOLDER_STRUCTURE.md** | This file | 10 min | Understanding file layout |

---

## 🔄 File Dependencies

```
Deployment depends on:
├── wsgi.py (entry point)
│   └─ imports demo-server.py
├── requirements.txt (packages)
│   └─ Gunicorn installs
├── app/demo-server.py (app logic)
│   └─ imports knowledge-engine.py
└── Nginx config (web routing)
    └─ forwards to Gunicorn on port 8000

Database:
└── data/demo-workflows.db (created on first run)
```

---

## ✅ Pre-Deployment File Checklist

Before uploading to VPS, verify:

```
☐ wsgi.py exists in root folder
☐ requirements.txt has gunicorn==20.1.0
☐ app/ folder has all Python files
☐ data/ folder exists (can be empty)
☐ .venv/ folder NOT going to VPS
☐ All *.py files are valid Python
☐ requirements.txt has valid package names
```

---

## 📤 Upload Instructions

**From your Windows PowerShell:**

```powershell
cd c:\Users\Faizan\Desktop\Seema

# Upload application folder
scp -r app seema@120.240.150.100:/home/seema/seema-app/

# Upload data folder
scp -r data seema@120.240.150.100:/home/seema/seema-app/

# Upload configuration files
scp requirements.txt seema@120.240.150.100:/home/seema/seema-app/
scp wsgi.py seema@120.240.150.100:/home/seema/seema-app/

# Optional: HTML interface
scp app/seema-demo.html seema@120.240.150.100:/home/seema/seema-app/
```

---

## 🔍 Verify Files After Upload

**On VPS:**

```bash
# Check files uploaded
ls -la /home/seema/seema-app/

# Should show:
# drwxr-xr-x app
# drwxr-xr-x data
# -rw-r--r-- requirements.txt
# -rw-r--r-- wsgi.py

# Check app folder
ls -la /home/seema/seema-app/app/

# Should show:
# -rw-r--r-- demo-server.py
# -rw-r--r-- knowledge-engine.py
# -rw-r--r-- seema-demo.html
```

---

## 📊 File Sizes (Approximate)

| File/Folder | Size | Notes |
|------------|------|-------|
| app/ | 50-100 KB | Python source code |
| data/ | 10 KB | Empty initially |
| wsgi.py | 2 KB | Entry point |
| requirements.txt | 1 KB | Package list |
| .venv/ (local) | 50-100 MB | **Don't upload!** |

**Total to upload:** ~60-100 KB  
**Total on VPS after venv:** ~50-100 MB (venv created on VPS)

---

## 🔐 File Permissions (VPS)

After deployment, files should have:

```bash
# Python files
-rw-r--r-- (readable by all, writable by owner)

# Folders
drwxr-xr-x (accessible by all, writable by owner)

# If need to fix:
chmod 644 /home/seema/seema-app/*.py
chmod 755 /home/seema/seema-app/
chmod 755 /home/seema/seema-app/data/
```

---

## 🔄 After Deployment - File Locations

**For Updates/Maintenance:**

```bash
# SSH into VPS
ssh seema@120.240.150.100

# Go to app folder
cd /home/seema/seema-app

# Edit files
nano app/demo-server.py              # Edit app code
nano wsgi.py                         # Edit entry point
nano requirements.txt                # Update dependencies

# After changes
pip install -r requirements.txt      # If new packages
sudo supervisorctl restart seema    # Restart app

# Check logs
tail -f /var/log/seema.log
```

---

## 📝 Version Control (Optional)

If you want to use Git:

```bash
# On VPS
cd /home/seema/seema-app

# Initialize git (if not already)
git init
git config user.email "you@example.com"
git config user.name "Your Name"

# Stage changes
git add .
git commit -m "Initial deployment"

# Push to repo (if have GitHub)
git push origin main

# Or track locally
git log --oneline
```

---

## 🔗 Related Files Reference

```
LOCAL (Windows):
  c:\Users\Faizan\Desktop\Seema\*

VPS:
  /home/seema/seema-app/*

Nginx Config:
  /etc/nginx/sites-available/seemaai.co.uk

Supervisor Config:
  /etc/supervisor/conf.d/seema.conf

Logs:
  /var/log/seema.log

Database:
  /home/seema/seema-app/data/demo-workflows.db

SSL Certificate:
  /etc/letsencrypt/live/seemaai.co.uk/
```

---

## ✨ Special Files

**wsgi.py** (New)
- Created for this deployment
- Makes app compatible with Gunicorn
- Copy to VPS during deployment

**requirements.txt** (Updated)
- Added gunicorn==20.1.0
- Added requests==2.28.0
- Ensures all packages installed on VPS

---

## 📦 Package Structure

```
Your Package:
├── Source Code (75%)
│   ├── Python files
│   ├── HTML interface
│   └── Database schema
│
├── Documentation (20%)
│   ├── Deployment guides
│   ├── VPS basics
│   └── Troubleshooting
│
└── Configuration (5%)
    ├── wsgi.py entry point
    └── requirements.txt packages
```

---

## 🎯 Quick Reference

**LOCAL FOLDER (Windows):**
```
c:\Users\Faizan\Desktop\Seema\
```

**VPS FOLDER (Production):**
```
/home/seema/seema-app/
```

**UPLOAD COMMAND:**
```
scp -r * seema@69.62.110.2:/home/seema/seema-app/
```

**VERIFY UPLOAD:**
```
ssh seema@69.62.110.2
ls -la /home/seema/seema-app/
```

---

## 🚀 Ready to Deploy?

Your file structure is ready!

1. ✅ wsgi.py created
2. ✅ requirements.txt updated
3. ✅ All files organized
4. ✅ Documentation complete

**Next Step:** Follow VPS_QUICK_START.md to deploy

---

**Last Updated:** April 23, 2026  
**Status:** ✅ Ready for Deployment
