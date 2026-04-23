# DNS & Domain Setup for seemaai.co.uk on Hostinger

## 🌐 Understanding DNS

DNS (Domain Name System) translates `seemaai.co.uk` → `Your VPS IP Address`

Example:
- When someone visits `https://seemaai.co.uk`
- DNS looks up and finds: `120.240.150.100` (your VPS IP)
- Browser connects to that IP
- Nginx shows your Seema app

---

## ✅ Step 1: Get Your VPS IP Address

1. Log in to **Hostinger Dashboard** (hpanel.hostinger.com)
2. Go to **VPS** section
3. Click on your KVM4 plan
4. Look for **IP Address** - copy it (format: `123.45.67.89`)

**Save this somewhere safe!** 

---

## ✅ Step 2: Point Domain to VPS IP

### If Domain & VPS Both on Hostinger (EASIEST)

1. **Hostinger Dashboard** → **Domains** → `seemaai.co.uk`
2. Click **Manage DNS**
3. Look for **A Records** section
4. Find or create records for:
   - **Host:** `@` (or leave blank) → **IP:** `YOUR_VPS_IP`
   - **Host:** `www` → **IP:** `YOUR_VPS_IP`
5. **Save**
6. **Wait 5-30 minutes** for DNS to propagate

### If Domain Elsewhere (Alternative Registrar)

1. Log into your domain registrar
2. Find **DNS Settings** or **Nameservers**
3. Set nameservers to Hostinger:
   - `ns1.hostinger.com`
   - `ns2.hostinger.com`
   - `ns3.hostinger.com`
   - `ns4.hostinger.com`
4. **Save** and wait 24 hours

Then follow the "If Domain & VPS Both on Hostinger" steps above.

---

## ✅ Step 3: Verify DNS is Working

Run this command on your **Windows PowerShell**:

```powershell
nslookup seemaai.co.uk
```

**Good result:** Shows your VPS IP
```
Server: 8.8.8.8
Address: 8.8.8.8

Name: seemaai.co.uk
Address: 69.62.110.2
```

**Bad result:** Shows different IP or error
```
*** google.dns can't find seemaai.co.uk: Non-existent domain
```

If bad, wait 30 minutes and try again.

---

## 🔗 DNS Propagation Timeline

| Time | Status |
|------|--------|
| 0-5 min | Not yet updated |
| 5-30 min | Partially propagated |
| 30 min - 2 hours | Mostly ready |
| 2-24 hours | Fully propagated worldwide |

**To speed up:** Use Google's DNS while waiting:
```powershell
nslookup seemaai.co.uk 8.8.8.8
```

---

## 📋 DNS Records Explained

```
A Record:
├─ Type: A
├─ Name: @ (or blank)
├─ Value: YOUR_VPS_IP
└─ Purpose: Routes seemaai.co.uk to your VPS

A Record (www):
├─ Type: A
├─ Name: www
├─ Value: YOUR_VPS_IP
└─ Purpose: Routes www.seemaai.co.uk to your VPS

CNAME (optional, for subdomains):
├─ Type: CNAME
├─ Name: api
├─ Value: seemaai.co.uk
└─ Purpose: api.seemaai.co.uk routes to seemaai.co.uk
```

---

## ⚠️ Troubleshooting DNS

### "Domain still shows old site"

**Browser DNS cache issue:**
```powershell
# Clear DNS cache (Windows Admin PowerShell)
ipconfig /flushdns

# Try again
nslookup seemaai.co.uk
```

### "Domain points wrong IP"

1. Check Hostinger DNS settings
2. Verify you updated the **A record** (not CNAME)
3. Wait for propagation
4. Test with: `nslookup seemaai.co.uk 8.8.8.8`

### "SSL certificate fails"

SSL requires domain to resolve correctly first:
```bash
# On VPS - should work
ping seemaai.co.uk

# If fails, DNS not ready yet
# Wait 30 more minutes and try certbot again
sudo certbot --nginx -d seemaai.co.uk
```

---

## 🔐 DNS Security (Optional)

Consider adding these records later:

```
SPF Record (prevent email spoofing):
Type: TXT
Name: @
Value: v=spf1 -all

DMARC Record (email security):
Type: TXT
Name: _dmarc
Value: v=DMARC1; p=none
```

For now, these are optional.

---

## 📞 Quick Help

**Still not working?** Ask:
1. Does `nslookup seemaai.co.uk` show your VPS IP? (Yes = DNS OK)
2. Can you SSH into VPS? (Yes = VPS OK)
3. Is Nginx running? `sudo systemctl status nginx`
4. Check Nginx config: `sudo nginx -t`

---

## ✅ DNS Success Checklist

- [ ] VPS IP copied from Hostinger
- [ ] A record created: `@` → YOUR_VPS_IP
- [ ] A record created: `www` → YOUR_VPS_IP
- [ ] `nslookup seemaai.co.uk` returns YOUR_VPS_IP
- [ ] You can ping the domain: `ping seemaai.co.uk`
- [ ] Domain visited in browser shows your app

**All checked? Your DNS is ready!** 🎉
