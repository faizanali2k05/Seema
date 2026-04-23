# 🚀 Deployment via GitHub + Git - Fast & Easy!

**Your VPS IP:** `69.62.110.2`  
**Domain:** `seemaai.co.uk`  
**Method:** GitHub + Git Clone  
**Status:** ✅ Ready to Deploy!

---

## 📋 Prerequisites (5 minutes)

1. **GitHub Account** (free at github.com)
2. **Create a repository** for your Seema app
3. **Push your code** to GitHub
4. **Get repo URL** (use HTTPS, not SSH)

---

## ⚡ Step-by-Step Commands (Copy & Paste)

### STEP 1: SSH into Your VPS

```bash
ssh root@69.62.110.2
```

Enter root password (from Hostinger).

---

### STEP 2: Update & Install

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

### STEP 4: Clone Your GitHub Repository

```bash
cd /home/seema
git clone https://github.com/YOUR_USERNAME/seema-repo.git seema-app
cd seema-app
```

**Replace:**
- `YOUR_USERNAME` = your GitHub username
- `seema-repo` = your repository name

Example:
```bash
git clone https://github.com/faizan/seema-app.git seema-app
cd seema-app
```

---

### STEP 5: Verify Files

```bash
ls -la
```

You should see:
- `app/` folder
- `data/` folder
- `requirements.txt`
- `wsgi.py`

---

### STEP 6: Setup Python Environment

```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
pip install gunicorn
```

---

### STEP 7: Test Gunicorn

```bash
gunicorn -w 4 -b 127.0.0.1:8000 wsgi:application
```

You should see startup messages. Press `Ctrl+C` when ready. ✅

---

### STEP 8: Exit and Configure Nginx (as root)

```bash
exit
exit
```

Now SSH as root again:

```bash
ssh root@69.62.110.2
```

Create Nginx config:

```bash
nano /etc/nginx/sites-available/seemaai.co.uk
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
    }
}
```

Save: `Ctrl+X` → `Y` → `Enter`

Enable it:

```bash
ln -s /etc/nginx/sites-available/seemaai.co.uk /etc/nginx/sites-enabled/
rm /etc/nginx/sites-enabled/default
nginx -t
systemctl restart nginx
```

---

### STEP 9: Configure Supervisor

```bash
nano /etc/supervisor/conf.d/seema.conf
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

Save: `Ctrl+X` → `Y` → `Enter`

Enable it:

```bash
supervisorctl reread
supervisorctl update
supervisorctl status
```

Should show: `seema RUNNING pid ####` ✅

---

### STEP 10: Install SSL

```bash
certbot --nginx -d seemaai.co.uk -d www.seemaai.co.uk
```

Follow prompts:
- Email: (your email)
- Terms: `Y`
- Share: `N`

---

### STEP 11: Verify in Browser

```
https://seemaai.co.uk
```

You should see your Seema app! 🎉

---

## 📱 GitHub Setup (Quick Guide)

### Create Repository on GitHub:

1. Go to https://github.com/new
2. Name: `seema-app` (or anything)
3. Private or Public (your choice)
4. Create repository
5. Click "Code" button
6. Copy HTTPS URL

### Push Your Local Code:

From **Windows PowerShell** in your Seema folder:

```powershell
cd c:\Users\Faizan\Desktop\Seema

# Initialize git (if not already)
git init

# Add files
git add .

# Commit
git commit -m "Initial commit - Seema deployment"

# Add remote (replace with your HTTPS URL)
git remote add origin https://github.com/YOUR_USERNAME/seema-app.git

# Push
git branch -M main
git push -u origin main
```

When prompted for password, use your GitHub **personal access token** (not your password):
1. Go to GitHub Settings → Developer settings → Personal access tokens
2. Generate token with `repo` scope
3. Use token as password

---

## 🔄 Later Updates (How to Update on VPS)

Once deployed, updating is super easy:

```bash
ssh seema@69.62.110.2
cd seema-app

# Pull latest changes
git pull origin main

# Restart app
sudo supervisorctl restart seema
```

---

## 💾 Quick Reference Commands

```bash
# SSH
ssh root@69.62.110.2

# Clone repo
git clone https://github.com/YOUR_USERNAME/seema-app.git seema-app

# Check status
sudo supervisorctl status seema

# View logs
tail -f /var/log/seema.log

# Restart app
sudo supervisorctl restart seema

# Update code
cd /home/seema/seema-app
git pull origin main
sudo supervisorctl restart seema
```

---

## ✅ Final Checklist

- [ ] GitHub repo created with your code
- [ ] DNS points to 69.62.110.2
- [ ] Can SSH: `ssh root@69.62.110.2`
- [ ] `git clone` works
- [ ] Gunicorn runs locally
- [ ] Nginx configured
- [ ] Supervisor running
- [ ] SSL installed
- [ ] Browser loads: `https://seemaai.co.uk` ✅

---

## 🎯 Advantages of Git Method

✅ **No SCP authentication issues**  
✅ **Easy to update code** - just `git pull`  
✅ **Version history** - track all changes  
✅ **Team friendly** - multiple people can work  
✅ **Professional** - standard deployment practice  
✅ **Faster** - no file transfer delays  
✅ **Rollback easy** - revert changes with `git checkout`

---

## 🚀 Ready? 

1. **Push code to GitHub** (use commands above)
2. **Get HTTPS repo URL**
3. **Follow steps above** starting with Step 1
4. **Done in ~15 minutes!**

Questions? Let me know! 🎉
