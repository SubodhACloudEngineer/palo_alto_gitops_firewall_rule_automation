# NetBox Integration Setup Guide

## Prerequisites

You already have:
- ✅ NetBox running on Docker (localhost:8000)
- ✅ Palo Alto NGFW (40.76.129.220)
- ✅ Palo Alto API key

---

## Step 1: Get NetBox API Token (5 minutes)

1. **Login to NetBox**
   ```
   URL: http://localhost:8000
   Default: admin / admin (or your credentials)
   ```

2. **Create API Token**
   - Click your username (top right)
   - Click "API Tokens"
   - Click "Add a token"
   - Give it a name: "Palo Alto Sync"
   - Check "Write enabled" ✅
   - Click "Create"
   - **COPY THE TOKEN** (you won't see it again!)

3. **Save the token**
   ```bash
   echo "YOUR_TOKEN_HERE" > .netbox_token
   ```

---

## Step 2: Update Sync Script (2 minutes)

Edit `sync_paloalto_to_netbox.py`:

```python
# Line 28-31: Palo Alto Configuration
PA_CONFIG = {
    'host': '40.76.129.220',
    'api_key': 'YOUR_PALO_ALTO_API_KEY',  # From earlier
    'verify_ssl': False
}

# Line 34-38: NetBox Configuration
NETBOX_CONFIG = {
    'url': 'http://localhost:8000',
    'token': 'YOUR_NETBOX_TOKEN',  # From Step 1
    'verify_ssl': False
}
```

---

## Step 3: Install Dependencies (1 minute)

```bash
pip install -r requirements_netbox_sync.txt
```

---

## Step 4: Run the Sync (30 seconds!)

```bash
python3 sync_paloalto_to_netbox.py
```

**Expected output:**
```
============================================================
  Palo Alto → NetBox Sync
============================================================

🔌 Connecting to Palo Alto NGFW...
🔌 Connecting to NetBox...

📦 Setting up NetBox objects...
  ✅ Site: Azure-EastUS
  ✅ Manufacturer: Palo Alto Networks
  ✅ Device Type: PA-VM-Series
  ✅ Role: Firewall
  ✅ Device: fw1toyota123

🔌 Syncing interfaces...
  Found 2 interfaces
  • ethernet1/1: 172.19.1.4/24 (zone: trust)
  • ethernet1/2: 172.19.2.4/24 (zone: dmz)

📍 Syncing address objects...
  Found 4 address objects
  • vm1-client: 172.19.1.5/32
  • vm2-webserver: 172.19.2.5/32
  • public-subnet: 172.19.1.0/24
  • private-subnet: 172.19.2.0/24

🔐 Syncing security rules...
  Found 2 security rules
  • Deny-All-Initial: ['trust'] → ['dmz'] (deny)
  • Allow-VM1-to-VM2-Web: ['trust'] → ['dmz'] (allow)

🏷️  Syncing zones...
  Found 2 zones
  • trust: ethernet1/1
  • dmz: ethernet1/2

============================================================
  ✅ Sync Complete!
============================================================

📊 Summary:
  • Interfaces: 2
  • Address Objects: 4
  • Security Rules: 2
  • Zones: 2

🌐 View in NetBox: http://localhost:8000/dcim/devices/1/
```

---

## Step 5: Verify in NetBox (2 minutes)

1. **Open NetBox**: http://localhost:8000

2. **Navigate to Device**
   - Organization → Devices
   - Click "fw1toyota123"

3. **Check Interfaces Tab**
   - Should see: ethernet1/1, ethernet1/2
   - With IP addresses: 172.19.1.4/24, 172.19.2.4/24

4. **Check IPAM → IP Addresses**
   - Should see all IPs:
     - 172.19.1.4/24 (firewall)
     - 172.19.2.4/24 (firewall)
     - 172.19.1.5/32 (vm1-client)
     - 172.19.2.5/32 (vm2-webserver)

5. **Check Config Context**
   - Device page → Config Context tab
   - Should see firewall rules stored as JSON

---

## Step 6: Schedule Automatic Sync (Optional)

### Option A: Cron Job (Linux/Mac)

```bash
# Run sync every 15 minutes
crontab -e

# Add this line:
*/15 * * * * cd /path/to/script && python3 sync_paloalto_to_netbox.py >> sync.log 2>&1
```

### Option B: Windows Task Scheduler

```powershell
# Create scheduled task
$action = New-ScheduledTaskAction -Execute "python" -Argument "C:\path\to\sync_paloalto_to_netbox.py"
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) -RepetitionInterval (New-TimeSpan -Minutes 15)
Register-ScheduledTask -Action $action -Trigger $trigger -TaskName "NetBox-Sync" -Description "Sync Palo Alto to NetBox"
```

### Option C: Docker Container (Best)

```bash
# Create Dockerfile
cat > Dockerfile << 'EOF'
FROM python:3.11-slim
WORKDIR /app
COPY requirements_netbox_sync.txt .
RUN pip install -r requirements_netbox_sync.txt
COPY sync_paloalto_to_netbox.py .
CMD while true; do python sync_paloalto_to_netbox.py; sleep 900; done
EOF

# Build and run
docker build -t netbox-sync .
docker run -d --name netbox-sync --network netbox-docker_default netbox-sync
```

---

## Troubleshooting

### Issue: "Invalid API Key"

**Solution:**
```bash
# Regenerate Palo Alto API key
curl -k -X POST 'https://40.76.129.220/api/?type=keygen&user=azureuser&password=Welcome@ntt!0725'

# Copy the key and update script
```

### Issue: "NetBox connection refused"

**Check Docker:**
```bash
docker ps | grep netbox
docker logs netbox-1

# If not running:
cd /path/to/netbox-docker
docker-compose up -d
```

### Issue: "Permission denied" in NetBox

**Solution:**
- Make sure API token has "Write enabled" checked
- Recreate token with write permissions

### Issue: Script hangs

**Solution:**
```bash
# Check network connectivity
ping 40.76.129.220
curl -k https://40.76.129.220

# Check NetBox
curl http://localhost:8000/api/
```

---

## What Gets Synced

### ✅ Synced to NetBox:
- Network interfaces (ethernet1/1, ethernet1/2)
- IP addresses (with assignments)
- Address objects (as IP addresses with descriptions)
- Security rules (stored in device config context)
- Zones (stored in interface descriptions)

### ❌ Not Synced (by design):
- Firewall logs (too much data)
- Real-time sessions (changes too fast)
- VPN configurations (complex structure)
- NAT rules (can be added if needed)

---

## Portal Integration

Once NetBox is populated, your portal can query it:

```python
# In your portal backend
import requests

NETBOX_URL = "http://localhost:8000"
NETBOX_TOKEN = "your-token"

headers = {
    'Authorization': f'Token {NETBOX_TOKEN}',
    'Accept': 'application/json'
}

# Get all IPs
response = requests.get(f"{NETBOX_URL}/api/ipam/ip-addresses/", headers=headers)
ip_addresses = response.json()['results']

# Get firewall rules
response = requests.get(f"{NETBOX_URL}/api/dcim/devices/?name=fw1toyota123", headers=headers)
device = response.json()['results'][0]
firewall_rules = device['config_context']['firewall_rules']

# Display in portal form
for ip in ip_addresses:
    print(f"Available IP: {ip['address']} - {ip['description']}")

for rule in firewall_rules:
    print(f"Existing rule: {rule['name']} ({rule['action']})")
```

---

## Next Steps

1. ✅ Run sync script once manually
2. ✅ Verify data in NetBox
3. ✅ Setup automatic sync (cron/docker)
4. ✅ Integrate with your portal
5. ✅ Show NetBox data in portal form

---

## Quick Reference

**Sync Command:**
```bash
python3 sync_paloalto_to_netbox.py
```

**Check NetBox:**
```bash
curl -H "Authorization: Token YOUR_TOKEN" http://localhost:8000/api/dcim/devices/
```

**Check Palo Alto:**
```bash
curl -k "https://40.76.129.220/api/?type=op&cmd=<show><interface>all</interface></show>&key=YOUR_KEY"
```

**Docker Logs:**
```bash
docker logs netbox-1
docker logs netbox-sync  # if using sync container
```

---

## Support

If you encounter issues:
1. Check script output for error messages
2. Verify API tokens are valid
3. Check network connectivity
4. Review NetBox/Palo Alto logs

**Common fixes:**
- Regenerate API keys
- Restart NetBox Docker containers
- Check firewall connectivity
- Verify NetBox token permissions

---

**Estimated total setup time: 10-15 minutes** ⚡

**Sync frequency: Every 15 minutes (configurable)** 🔄

**Data freshness: Always current** ✅
