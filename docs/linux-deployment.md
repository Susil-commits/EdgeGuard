# EdgeGuard — Linux (Oracle VM / RHEL / Oracle Linux 9) Deployment Guide

## Overview
This guide covers deploying the EdgeGuard **agent** onto an Oracle Linux 9 or RHEL 9 target VM so that it reports real system metrics to your EdgeGuard API running on Windows.

---

## Prerequisites on the Linux VM

SSH into your Oracle Linux VM and run these commands as `root` or a `sudo` user:

```bash
# 1. Install Python 3.11+ (already present on OL9)
python3 --version    # Expect: Python 3.11.x or 3.12.x

# 2. Install pip and venv
sudo dnf install -y python3-pip python3-virtualenv

# 3. Install psutil system dependency (needed for disk / CPU / memory metrics)
sudo dnf install -y python3-devel gcc
```

---

## Step 1: Copy the Agent to the Linux VM

From your **Windows machine** (PowerShell), run:

```powershell
scp -r "c:\Users\nayak\OneDrive\Desktop\Edge\edgeguard\agent" user@<VM_IP>:~/edgeguard-agent/
scp "c:\Users\nayak\OneDrive\Desktop\Edge\edgeguard\requirements.txt" user@<VM_IP>:~/edgeguard-agent/
```

> Replace `user` with your Linux username and `<VM_IP>` with your Oracle Cloud VM public IP.

---

## Step 2: Register the Node via the API

From your **Windows machine**, register the Oracle VM as a node in EdgeGuard:

```powershell
$response = Invoke-RestMethod -Method POST -Uri "http://localhost:8000/v1/nodes/register" `
  -ContentType "application/json" `
  -Body '{"hostname": "oracle-vm-01", "site": "Oracle-Cloud-OCI", "environment": "staging", "os": "Oracle Linux 9.2"}'

$response  # Shows the assigned node_id UUID
```

Copy the `id` field from the response — you need it for the agent config.

---

## Step 3: Get a JWT Token for the Agent

```powershell
# First create an operator user (only needed once)
Invoke-RestMethod -Method POST -Uri "http://localhost:8000/v1/auth/register" `
  -ContentType "application/json" `
  -Body '{"username": "agent-oracle-01", "password": "agent-secret", "role": "operator"}'

# Then get a token
$token_resp = Invoke-RestMethod -Method POST -Uri "http://localhost:8000/v1/auth/token" `
  -ContentType "application/x-www-form-urlencoded" `
  -Body "username=agent-oracle-01&password=agent-secret"

$token_resp.access_token  # Copy this token
```

---

## Step 4: Configure the Agent on the Linux VM

SSH into the VM and create the agent environment file:

```bash
ssh user@<VM_IP>
cd ~/edgeguard-agent

# Create a virtual environment and install dependencies
python3 -m venv .venv
source .venv/bin/activate
pip install psutil httpx requests

# Create the agent config file
cat > agent.env << 'EOF'
EDGEGUARD_API_URL=http://<YOUR_WINDOWS_IP>:8000
NODE_ID=<paste-the-node-id-uuid-from-step-2>
AGENT_TOKEN=<paste-the-jwt-token-from-step-3>
MONITORED_SERVICES=sshd,chronyd,NetworkManager
COLLECT_INTERVAL_S=30
SPOOL_PATH=/var/lib/edgeguard/spool.db
EOF

# Make spool directory
sudo mkdir -p /var/lib/edgeguard
sudo chown $USER /var/lib/edgeguard
```

> Replace `<YOUR_WINDOWS_IP>` with your Windows machine local IP (run `ipconfig` on Windows to find it, look for "IPv4 Address" under your network adapter).

---

## Step 5: Run the Agent

```bash
# Test run (you will see metric POST logs)
cd ~/edgeguard-agent
source .venv/bin/activate
source agent.env
export EDGEGUARD_API_URL NODE_ID AGENT_TOKEN MONITORED_SERVICES COLLECT_INTERVAL_S SPOOL_PATH
python3 -m agent
```

You should see output like:
```
INFO  [collector] cpu=23.4% mem=41.2% disk=38.1% services={'sshd': 1.0}
INFO  [sender] Sent 4 metrics. HTTP 201.
```

---

## Step 6: Install as a systemd Service (Permanent Background Process)

```bash
# Create a systemd service file
sudo tee /etc/systemd/system/edgeguard-agent.service << 'EOF'
[Unit]
Description=EdgeGuard Monitoring Agent
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=edgeguard
WorkingDirectory=/opt/edgeguard-agent
EnvironmentFile=/etc/edgeguard/agent.env
ExecStart=/opt/edgeguard-agent/.venv/bin/python3 -m agent
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal
SyslogIdentifier=edgeguard-agent

[Install]
WantedBy=multi-user.target
EOF

# Create a dedicated system user (security best practice)
sudo useradd --system --no-create-home --shell /sbin/nologin edgeguard

# Copy agent to /opt
sudo cp -r ~/edgeguard-agent /opt/edgeguard-agent
sudo chown -R edgeguard:edgeguard /opt/edgeguard-agent

# Copy env file to /etc/edgeguard
sudo mkdir -p /etc/edgeguard
sudo cp ~/edgeguard-agent/agent.env /etc/edgeguard/agent.env
sudo chmod 600 /etc/edgeguard/agent.env  # Only root can read the token

# Enable and start
sudo systemctl daemon-reload
sudo systemctl enable edgeguard-agent
sudo systemctl start edgeguard-agent

# Verify
sudo systemctl status edgeguard-agent
sudo journalctl -u edgeguard-agent -f  # Follow live logs
```

---

## Step 7: Verify in the Dashboard

1. Open **[http://localhost:3000/](http://localhost:3000/)** in your browser.
2. Click the **Fleet View** tab.
3. Within 30 seconds, you should see `oracle-vm-01` with status **online** and a live **Last Heartbeat** timestamp.

---

## Troubleshooting

| Problem | Solution |
|---|---|
| **Agent can't reach API** | Run `curl http://<YOUR_WINDOWS_IP>:8000/health` from the VM. If it fails, check Windows Firewall — add inbound rule for port 8000. |
| **401 Unauthorized from API** | Token may have expired (default: 60 min). Re-run Step 3 to get a fresh token. |
| **Service not detected** | Check `MONITORED_SERVICES` matches exact systemd unit names: `systemctl list-units --type=service --state=active` |
| **Spool growing but not draining** | Normal during network outage. When connectivity resumes, agent auto-replays queued events. |
