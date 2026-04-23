# Seema Deployment Flowchart

## Complete Deployment Flow

```
START
  ↓
[Gather Info]
  ├─ VPS IP from Hostinger
  ├─ Root password
  └─ Domain: seemaai.co.uk
  ↓
[Setup DNS] (Do this FIRST - 5-30 min to propagate)
  ├─ Hostinger Dashboard → Domains
  ├─ seemaai.co.uk → A Record → YOUR_VPS_IP
  └─ Wait 5-30 minutes ⏳
  ↓
[SSH into VPS] ← ssh root@YOUR_VPS_IP
  ↓
[1. Update System] ← apt update && apt upgrade -y
  ↓
[2. Install Packages] ← apt install python3 python3-pip... nginx supervisor
  ↓
[3. Create App User] ← useradd -m -s /bin/bash seema
  ↓
[4. Switch to seema] ← su - seema
  ↓
[5. Upload App Files] ← scp from your Windows machine
  ↓
[6. Setup Virtual Environment] ← python3 -m venv venv
  ↓
[7. Install Dependencies] ← pip install -r requirements.txt
  ↓
[8. Test Gunicorn] ← gunicorn wsgi:application
  ├─ Should start successfully
  └─ Ctrl+C to stop
  ↓
[9. Configure Nginx] ← nano /etc/nginx/sites-available/seemaai.co.uk
  ├─ Paste nginx config
  ├─ Enable site
  └─ sudo systemctl restart nginx
  ↓
[10. Configure Supervisor] ← nano /etc/supervisor/conf.d/seema.conf
  ├─ Paste supervisor config
  └─ sudo supervisorctl update
  ↓
[11. Install SSL] ← sudo certbot --nginx -d seemaai.co.uk
  ├─ Follow prompts
  └─ Auto-renewal configured
  ↓
[12. Test in Browser] ← https://seemaai.co.uk
  ├─ Do you see your app? 
  ├─ YES → ✅ DEPLOYMENT SUCCESSFUL!
  └─ NO → Check logs & troubleshoot
  ↓
[Verify] 
  ├─ App running: sudo supervisorctl status seema
  ├─ Nginx active: sudo systemctl status nginx
  ├─ SSL valid: Visit in browser (green lock)
  └─ Logs clean: tail -f /var/log/seema.log
  ↓
[🎉 LIVE!]
```

---

## Decision Tree: Troubleshooting

```
PROBLEM?
  ↓
├─ "502 Bad Gateway"
│  └─→ Check if app running
│     sudo supervisorctl status seema
│     If NOT running: sudo supervisorctl restart seema
│
├─ "Can't connect to VPS"
│  └─→ Check firewall / port 22 open
│     Try: ssh -v root@YOUR_VPS_IP
│
├─ "Domain not working"
│  └─→ Check DNS propagation
│     nslookup seemaai.co.uk
│     Should return YOUR_VPS_IP
│     If not: wait 30 minutes
│
├─ "SSL certificate failed"
│  └─→ Need working DNS first
│     Retry after DNS resolves
│     sudo certbot --nginx -d seemaai.co.uk
│
└─ "App crashes after restart"
   └─→ Check logs for errors
      tail -f /var/log/seema.log
      Fix error and restart
```

---

## File Upload Strategy

```
Your Computer                  VPS Server
(Windows)                      (Ubuntu)

c:\Users\Faizan\
Desktop\Seema\
├── app/               scp -r app/* seema@IP:/home/seema/seema-app/
├── data/              scp -r data seema@IP:/home/seema/seema-app/
├── requirements.txt   scp requirements.txt seema@IP:/home/seema/seema-app/
├── wsgi.py            scp wsgi.py seema@IP:/home/seema/seema-app/
└── *.md files         (optional, for reference)

                       ↓↓↓ After upload ↓↓↓

                       /home/seema/seema-app/
                       ├── app/
                       ├── data/
                       ├── venv/             (created)
                       ├── requirements.txt
                       ├── wsgi.py
                       └── logs/             (created)
```

---

## Service Dependencies

```
Your Application Depends On:
    ↓
    ├─ Python 3 (runtime)
    ├─ Gunicorn (WSGI server)
    │  └─ Calls wsgi.py
    │     └─ Calls demo-server.py
    ├─ Nginx (reverse proxy)
    │  └─ Forwards traffic to Gunicorn
    ├─ Supervisor (keeps it running)
    │  └─ Restarts Gunicorn if crash
    └─ SSL/TLS (HTTPS security)
       └─ Let's Encrypt certificate
```

---

## Environment Variables

```
On VPS, these are set:

DATA_DIR=/home/seema/seema-app/data
  └─ Your SQLite database location

PATH includes:
  └─ /home/seema/seema-app/venv/bin
  └─ Python packages in virtual environment

Gunicorn uses:
  ├─ -w 4 (4 worker processes)
  ├─ -b 127.0.0.1:8000 (bind to localhost:8000)
  └─ wsgi:application (import wsgi.py's application)
```

---

## Monitoring Workflow (After Deployment)

```
Daily:
  ├─ Check if live: https://seemaai.co.uk (works?)
  └─ Check logs: tail -f /var/log/seema.log (errors?)

Weekly:
  ├─ Backup data: cp -r /home/seema/seema-app/data ~/backup/
  └─ Review full logs: sudo journalctl -u seema -n 100

Monthly:
  ├─ Update system: sudo apt update && apt upgrade -y
  └─ Renew SSL: sudo certbot renew (automatic, but can force)

Quarterly:
  ├─ Review security: sudo tail -f /var/log/auth.log
  └─ Check storage: df -h
```

---

## Port Mapping

```
Internet (User's Browser)
    ↓↓↓ Port 443 (HTTPS)
Nginx
    ↓ (Internal, unencrypted)
Port 80 → Port 80 (Nginx listens here)
Port 443 → Port 443 (Nginx listens here - SSL/TLS)
    ↓ (Nginx reverse proxy)
Port 8000 (Gunicorn)
    ↓
Your Python Application (demo-server.py)
    ↓
SQLite Database (/home/seema/seema-app/data/)
```

---

## SSL Certificate Lifecycle

```
Day 1:
  ├─ Run: sudo certbot --nginx -d seemaai.co.uk
  └─ Certificate issued (valid for 90 days)
  ↓
Day 60:
  ├─ Automatic renewal attempt (systemd timer)
  └─ New 90-day certificate issued
  ↓
Day 1 (always before expiration):
  ├─ Manual renewal: sudo certbot renew
  └─ Manual check: sudo certbot certificates
```

---

## Quick Status Check Commands

```bash
# Copy these commands and run on VPS after deployment

# 1. Is application running?
sudo supervisorctl status seema
# Expected: seema RUNNING pid ####

# 2. Is web server running?
sudo systemctl status nginx
# Expected: active (running)

# 3. Can it connect to backend?
curl http://127.0.0.1:8000
# Expected: Response from your app (not error)

# 4. Is domain working?
nslookup seemaai.co.uk
# Expected: Returns YOUR_VPS_IP

# 5. Any recent errors?
tail -20 /var/log/seema.log
# Expected: No error messages

# 6. Disk space?
df -h /home
# Expected: Plenty of free space

# 7. Memory usage?
free -h
# Expected: Most available memory free
```

---

## Restart Hierarchy (if needed)

```
If app crashes:
  ↓
Step 1: Restart just the app
  └─ sudo supervisorctl restart seema (fastest)
  
If app restart fails:
  ↓
Step 2: Restart Nginx + app
  └─ sudo systemctl restart nginx
  └─ sudo supervisorctl restart seema

If still issues:
  ↓
Step 3: Full reboot
  └─ sudo reboot
  └─ Wait 30 seconds for VPS to come back
  └─ SSH back and check status

If still problems:
  ↓
Step 4: Debug
  └─ tail -f /var/log/seema.log (check errors)
  └─ sudo nginx -t (check config)
  └─ Ask Hostinger support
```

---

## Success Indicators ✅

After deployment, you should see:

```
✅ Domain resolves: nslookup seemaai.co.uk → YOUR_VPS_IP
✅ Website loads: https://seemaai.co.uk (green lock in browser)
✅ No 502 errors: Browser doesn't show "Bad Gateway"
✅ App running: sudo supervisorctl status seema → RUNNING
✅ Logs clean: tail -f /var/log/seema.log → no errors
✅ SSL valid: Browser shows green lock, not warning
✅ Performance: Page loads in < 2 seconds
```

If all ✅, your deployment is complete!

---

## Failure Indicators ❌

If you see these, deployment needs fixing:

```
❌ Domain doesn't resolve: nslookup returns error
❌ 502 Bad Gateway error: Gunicorn not running
❌ Connection refused: VPS or port not accessible
❌ SSL warning: Certificate not installed properly
❌ App crashes: Check /var/log/seema.log for errors
❌ Slow load times: Check supervisor/nginx logs
```

---

## Next Steps After Successful Deployment

```
Immediately After:
  ├─ Test all features of your app
  ├─ Verify database is working
  └─ Check email notifications (if any)

Within First Week:
  ├─ Set up automated backups
  ├─ Monitor logs regularly
  └─ Test disaster recovery

Within First Month:
  ├─ Add monitoring alerts
  ├─ Document any customizations
  └─ Plan for scaling if needed

Ongoing:
  ├─ Monthly security updates
  ├─ Regular log reviews
  └─ Annual security audit
```

---

**Use this flowchart as your deployment roadmap!** 🗺️
