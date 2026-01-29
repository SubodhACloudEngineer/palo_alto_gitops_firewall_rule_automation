# Azure to NetBox Sync - Setup Guide

## 🎯 What This Script Does

Syncs your entire Azure resource group `rg-panorama-gitops-poc` to NetBox:

### ✅ Resources Synced:
- **Virtual Machines** (user01workstation, web01application)
- **Virtual Networks** (fwVNET, vnet-eastus, vnet-eastus-1)
- **Subnets** with IP ranges
- **Network Interfaces** (NICs)
- **Public IP addresses**
- **Private IP addresses**
- **VM metadata** (size, OS, location)

### 📊 Result in NetBox:
```
Site: Azure-EastUS
├── Devices
│   ├── user01workstation (Server)
│   │   └── NIC with 172.19.1.5
│   ├── web01application (Server)
│   │   └── NIC with 172.19.2.5
│   └── fw1toyota123 (Firewall) ← From Palo Alto sync
│
└── IPAM
    ├── VNets
    │   ├── fwVNET (172.19.0.0/16)
    │   ├── vnet-eastus
    │   └── vnet-eastus-1
    └── IP Addresses
        ├── All private IPs
        └── All public IPs
```

---

## 🚀 Quick Start (10 Minutes)

### **Step 1: Login to Azure CLI (2 min)**

```bash
# Login to Azure
az login

# Verify you're in the right subscription
az account show

# Should show:
# "id": "8527d19f-1ff6-461c-a89e-da961a355bed"
# "name": "Your Subscription Name"

# If not, set the correct subscription:
az account set --subscription "8527d19f-1ff6-461c-a89e-da961a355bed"
```

### **Step 2: Install Azure SDK (3 min)**

```bash
pip install -r requirements_azure_sync.txt
```

This installs:
- `azure-identity` - Authentication
- `azure-mgmt-compute` - VM management
- `azure-mgmt-network` - Network management
- `azure-mgmt-resource` - Resource management

### **Step 3: Update Script Config (2 min)**

Edit `sync_azure_to_netbox.py`:

```python
# Line 37-41: Azure Configuration
AZURE_CONFIG = {
    'subscription_id': '8527d19f-1ff6-461c-a89e-da961a355bed',  # Already correct!
    'resource_group': 'rg-panorama-gitops-poc',  # Already correct!
    'location': 'eastus'  # Already correct!
}

# Line 44-48: NetBox Configuration
NETBOX_CONFIG = {
    'url': 'http://localhost:8000',
    'token': 'YOUR_NETBOX_TOKEN',  # Same token as Palo Alto sync
    'verify_ssl': False
}
```

**That's it!** Only need to update the NetBox token (same as before).

### **Step 4: Run the Sync (30 seconds!)**

```bash
python3 sync_azure_to_netbox.py
```

**Expected output:**
```
============================================================
  Azure → NetBox Sync
============================================================

🔌 Connecting to Azure...
   Using Azure CLI credentials
   ✅ Found resource group: rg-panorama-gitops-poc (eastus)

🔌 Connecting to NetBox...

📦 Setting up NetBox objects...
  ✅ Site: Azure-EastUS
  ✅ Manufacturer: Microsoft
  ✅ Role: Server

🌐 Syncing Virtual Networks...
  Found 3 VNets

  • VNet: fwVNET
    Address Space: 172.19.0.0/16
    Subnets: 4
      - Mgmt: 172.19.0.0/24
      - AzureBastionSubnet: 172.19.0.0/26
      - Public: 172.19.1.0/24
      - Private: 172.19.2.0/24

  • VNet: vnet-eastus
    Address Space: 10.x.x.x/16
    Subnets: 2

  • VNet: vnet-eastus-1
    Address Space: 10.x.x.x/16
    Subnets: 1

💻 Syncing Virtual Machines...
  Found 2 VMs

  • VM: user01workstation
    Size: Standard_B2s
    OS: Canonical Ubuntu2204
    ✅ Device created/updated in NetBox
    NICs: 1
      - NIC: user01workstation128_z1
        Private IP: 172.19.1.5/24
        Public IP: x.x.x.x

  • VM: web01application
    Size: Standard_B2s
    OS: Canonical Ubuntu2204
    ✅ Device created/updated in NetBox
    NICs: 1
      - NIC: web01application384_z1
        Private IP: 172.19.2.5/24
        Public IP: x.x.x.x

🌍 Syncing Public IP Addresses...
  Found 5 Public IPs
  • user01workstation-ip: x.x.x.x
  • web01application-ip: x.x.x.x
  • fw1toyota123: x.x.x.x
  • vnet-eastus-IPv4: x.x.x.x
  • fwVNET-IPv4: x.x.x.x

============================================================
  ✅ Azure Sync Complete!
============================================================

📊 Summary:
  • Virtual Networks: 3
  • Virtual Machines: 2
  • Public IPs: 5

🌐 View in NetBox: http://localhost:8000/dcim/sites/1/
```

### **Step 5: Verify in NetBox (3 min)**

1. **Open NetBox**: http://localhost:8000

2. **Check Devices**:
   - Organization → Devices
   - Should see:
     - user01workstation ✅
     - web01application ✅
     - fw1toyota123 ✅

3. **Check IPAM**:
   - IPAM → Prefixes
   - Should see all VNets and subnets ✅
   
   - IPAM → IP Addresses
   - Should see all private and public IPs ✅

4. **Check Device Details**:
   - Click on `user01workstation`
   - Interfaces tab: Should show NIC with IP
   - Config Context tab: Should show Azure metadata

---

## 🔄 Scheduling Automatic Sync

### **Option 1: Simple Cron Job**

```bash
# Edit crontab
crontab -e

# Add this line (runs every 15 minutes)
*/15 * * * * cd /path/to/scripts && python3 sync_azure_to_netbox.py >> azure_sync.log 2>&1
```

### **Option 2: Combined Sync Script**

Create `sync_all_to_netbox.sh`:

```bash
#!/bin/bash

echo "Starting full sync to NetBox..."
echo "================================"

# Sync Palo Alto
echo "1. Syncing Palo Alto NGFW..."
python3 sync_paloalto_to_netbox.py
PA_EXIT=$?

# Sync Azure
echo ""
echo "2. Syncing Azure resources..."
python3 sync_azure_to_netbox.py
AZURE_EXIT=$?

echo ""
echo "================================"
if [ $PA_EXIT -eq 0 ] && [ $AZURE_EXIT -eq 0 ]; then
    echo "✅ Full sync complete!"
    exit 0
else
    echo "❌ Sync had errors"
    exit 1
fi
```

**Run it:**
```bash
chmod +x sync_all_to_netbox.sh
./sync_all_to_netbox.sh
```

**Schedule it:**
```bash
# Every 15 minutes
*/15 * * * * /path/to/sync_all_to_netbox.sh >> full_sync.log 2>&1
```

---

## 🔐 Authentication Methods

### **Method 1: Azure CLI (Current - Easiest)**

✅ **What you're using now**
- Run `az login` once
- Script uses your credentials
- Best for: Development, testing, personal use

**Pros:**
- ✅ No configuration needed
- ✅ Uses your existing Azure access
- ✅ Works immediately

**Cons:**
- ❌ Requires interactive login
- ❌ Token expires after some time

### **Method 2: Service Principal (Production)**

✅ **Recommended for production/automation**

**Create service principal:**
```bash
# Create with Reader role on resource group
az ad sp create-for-rbac \
  --name "netbox-sync-sp" \
  --role "Reader" \
  --scopes /subscriptions/8527d19f-1ff6-461c-a89e-da961a355bed/resourceGroups/rg-panorama-gitops-poc

# Output:
{
  "appId": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx",
  "displayName": "netbox-sync-sp",
  "password": "your-secret-password",
  "tenant": "xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx"
}
```

**Set environment variables:**
```bash
# Add to ~/.bashrc or script
export AZURE_CLIENT_ID="<appId>"
export AZURE_CLIENT_SECRET="<password>"
export AZURE_TENANT_ID="<tenant>"
export AZURE_SUBSCRIPTION_ID="8527d19f-1ff6-461c-a89e-da961a355bed"
```

**Update script:**
```python
# Script will automatically use environment variables
# No code changes needed!
```

**Pros:**
- ✅ Non-interactive (perfect for cron)
- ✅ Doesn't expire
- ✅ Can restrict permissions

### **Method 3: Managed Identity (If running on Azure VM)**

If you run this script on an Azure VM:

1. **Enable System Managed Identity** on the VM
2. **Grant permissions** to the identity
3. **No configuration needed** - script auto-detects

**Pros:**
- ✅ No credentials to manage
- ✅ Most secure
- ✅ Zero configuration

---

## 📊 What Gets Stored in NetBox

### **Devices:**
```json
{
  "name": "user01workstation",
  "device_type": "Azure-Standard_B2s",
  "role": "Server",
  "site": "Azure-EastUS",
  "status": "active",
  "config_context": {
    "azure": {
      "resource_id": "/subscriptions/.../user01workstation",
      "vm_size": "Standard_B2s",
      "os_type": "Canonical Ubuntu2204",
      "location": "eastus",
      "provisioning_state": "Succeeded",
      "last_synced": "2025-01-29T12:00:00"
    }
  }
}
```

### **Interfaces:**
```json
{
  "device": "user01workstation",
  "name": "user01workstation128_z1",
  "type": "virtual",
  "enabled": true
}
```

### **IP Addresses:**
```json
{
  "address": "172.19.1.5/24",
  "status": "active",
  "assigned_object": "user01workstation128_z1",
  "description": "Azure VM: user01workstation"
}
```

### **Prefixes (VNets/Subnets):**
```json
{
  "prefix": "172.19.1.0/24",
  "site": "Azure-EastUS",
  "status": "active",
  "description": "Azure Subnet: Public (VNet: fwVNET)"
}
```

---

## 🎯 Portal Integration Example

Now that NetBox has all Azure resources, your portal can:

```python
# Portal backend - Query NetBox

# 1. Get all Azure VMs for dropdown
response = requests.get(
    "http://localhost:8000/api/dcim/devices/",
    headers={'Authorization': f'Token {token}'},
    params={'site': 'azure-eastus', 'role': 'server'}
)

vms = response.json()['results']

# 2. Display in form
for vm in vms:
    # Get VM's primary IP
    if vm['primary_ip4']:
        ip = vm['primary_ip4']['address'].split('/')[0]
        print(f"VM: {vm['name']} ({ip})")

# 3. Check for existing firewall rules
# (From Palo Alto sync)
response = requests.get(
    "http://localhost:8000/api/dcim/devices/",
    params={'name': 'fw1toyota123'}
)

firewall = response.json()['results'][0]
existing_rules = firewall['config_context']['firewall_rules']

# 4. Validate user input
source_ip = "172.19.1.5"
dest_ip = "172.19.2.5"

# Check if rule already exists
for rule in existing_rules:
    if source_ip in rule['source'] and dest_ip in rule['destination']:
        print(f"⚠️  Rule already exists: {rule['name']}")
        break
```

---

## 🔧 Troubleshooting

### **Issue: "Azure authentication failed"**

```bash
# Solution: Login to Azure CLI
az login

# Verify subscription
az account show

# If wrong subscription:
az account set --subscription "8527d19f-1ff6-461c-a89e-da961a355bed"
```

### **Issue: "Resource group not found"**

```bash
# Verify resource group exists
az group show --name rg-panorama-gitops-poc

# List all resource groups
az group list --output table
```

### **Issue: Script hangs or times out**

```bash
# Check Azure connectivity
az vm list --resource-group rg-panorama-gitops-poc

# Check NetBox
curl http://localhost:8000/api/

# Increase timeout in script (line 77)
'timeout': 60  # Increase from 30 to 60
```

### **Issue: "Module not found: azure.identity"**

```bash
# Reinstall Azure SDK
pip install --upgrade -r requirements_azure_sync.txt

# If still fails, install individually:
pip install azure-identity azure-mgmt-compute azure-mgmt-network azure-mgmt-resource
```

### **Issue: Some VMs not appearing**

```bash
# Check VM provisioning state
az vm list --resource-group rg-panorama-gitops-poc --query "[].{Name:name, State:provisioningState}" -o table

# Script only syncs VMs in "Succeeded" state
```

---

## 📈 Performance

**Sync time estimates:**
- 2 VMs: ~30 seconds
- 3 VNets: ~10 seconds
- 5 Public IPs: ~5 seconds
- **Total: ~45 seconds**

**Resource usage:**
- Memory: ~100 MB
- CPU: Minimal
- Network: ~1-2 MB per sync

**API calls:**
- Azure: ~10-20 calls
- NetBox: ~30-50 calls
- Rate limits: No issues with 15-min frequency

---

## 🎨 NetBox UI After Sync

### **Devices View:**
```
Organization → Devices

Name                | Type              | Site         | Status | IP
--------------------|-------------------|--------------|--------|-------------
user01workstation   | Azure-Standard_B2s| Azure-EastUS | Active | 172.19.1.5
web01application    | Azure-Standard_B2s| Azure-EastUS | Active | 172.19.2.5
fw1toyota123        | PA-VM-Series      | Azure-EastUS | Active | 172.19.0.4
```

### **IPAM View:**
```
IPAM → IP Addresses

Address        | Status | Assigned To                     | Description
---------------|--------|--------------------------------|------------------
172.19.0.4/24  | Active | fw1toyota123 (ethernet1/1)    | Firewall Mgmt
172.19.1.4/24  | Active | fw1toyota123 (ethernet1/1)    | Zone: trust
172.19.1.5/24  | Active | user01workstation (NIC)       | Azure VM
172.19.2.4/24  | Active | fw1toyota123 (ethernet1/2)    | Zone: dmz
172.19.2.5/24  | Active | web01application (NIC)        | Azure VM
```

### **Topology View (with plugin):**
```
    [Internet]
        │
    [Bastion]
        │
    ┌───┴────┐
    │fwVNET  │ (172.19.0.0/16)
    └───┬────┘
        │
    ┌───┴────────┬─────────────┬──────────┐
    │            │             │          │
[Firewall]  [VM1 Client]  [VM2 Web]  [Panorama]
172.19.0.4   172.19.1.5    172.19.2.5
```

---

## 🚀 Next Steps

1. ✅ Run Azure sync script
2. ✅ Verify all resources in NetBox
3. ✅ Schedule automatic sync (cron)
4. ✅ Integrate with your portal
5. ✅ Demo the complete solution!

---

## 📝 Summary

**Setup time:** 10 minutes
**Sync time:** 45 seconds
**Frequency:** Every 15 minutes (configurable)
**Maintenance:** Zero (runs automatically)

**What you have now:**
- ✅ Palo Alto firewall in NetBox
- ✅ All Azure VMs in NetBox
- ✅ All networks and IPs in NetBox
- ✅ Complete infrastructure inventory
- ✅ Ready for portal integration

**Your NetBox is now the Single Source of Truth!** 🎯
