# Seema - AI Law Firm Compliance System

## Local Setup & Running

### Prerequisites
- Python 3.8+ installed
- pip (Python package manager)

### Step 1: Install Dependencies

```bash
cd c:\Users\Faizan\Desktop\Seema
pip install -r requirements.txt
```

### Step 2: Run the Server Locally

```bash
python app/demo-server.py
```

The server will start on **http://localhost:3000**

Open your browser and navigate to: `http://localhost:3000`

### Step 3: Verify it's Running
You should see the Seema Compliance interface load.

---

## Database
- SQLite database: `data/demo-workflows.db`
- Automatically created if not exists

---

## Deployment to Hostinger KVM4

### Prerequisites
- SSH access to Hostinger
- Your domain name (DNS configured)

### Step-by-Step Deployment Guide

See `HOSTINGER_DEPLOYMENT.md` for detailed instructions.
