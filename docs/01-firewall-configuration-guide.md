# Palo Alto Firewall Configuration Guide
# Network Automation Demo - GitOps with Panorama

## Your Network Information

**Resource Group:** rg-panorama-gitops-poc  
**Location:** East US  

**Network Topology:**
```
Management Subnet: 172.19.0.0/24
  - Firewall eth0: 172.19.0.4

Public Subnet (Trust): 172.19.1.0/24
  - VM1 (user01workstation): 172.19.1.5
  - Firewall eth1: 172.19.1.4

Private Subnet (DMZ): 172.19.2.0/24
  - VM2 (web01application): 172.19.2.5
  - Firewall eth2: 172.19.2.4
```

**Firewall:** fw1toyota123  
**Management Interface:** https://[FIREWALL-PUBLIC-IP]

---

## Phase 1: Initial Firewall Configuration

### Step 1: Login to Firewall

1. Access firewall web UI: `https://[FIREWALL-PUBLIC-IP]`
2. Login with credentials you set during deployment
3. Accept any certificate warnings

### Step 2: Configure Network Interfaces

#### Option A: Using Web UI

Navigate to **Network → Interfaces**

**Configure ethernet1/1 (Public/Trust Interface):**
```
Interface: ethernet1/1
Interface Type: Layer3
Config tab:
  - Virtual Router: default
  - Security Zone: trust
IPv4 tab:
  - Type: Static
  - IP Address: 172.19.1.4/24
Advanced → Other Info:
  - Management Profile: (create if needed: allow ping, SSH)
```

**Configure ethernet1/2 (Private/DMZ Interface):**
```
Interface: ethernet1/2
Interface Type: Layer3
Config tab:
  - Virtual Router: default
  - Security Zone: dmz
IPv4 tab:
  - Type: Static
  - IP Address: 172.19.2.4/24
```

#### Option B: Using CLI

```xml
# SSH to firewall management IP
ssh admin@[FIREWALL-MGMT-PUBLIC-IP]

# Enter configuration mode
configure

# Configure ethernet1/1 (Trust)
set network interface ethernet ethernet1/1 layer3 ip 172.19.1.4/24
set network interface ethernet ethernet1/1 layer3 interface-management-profile allow-ping

# Configure ethernet1/2 (DMZ)
set network interface ethernet ethernet1/2 layer3 ip 172.19.2.4/24
set network interface ethernet ethernet1/2 layer3 interface-management-profile allow-ping

# Assign to virtual router
set network virtual-router default interface [ ethernet1/1 ethernet1/2 ]

# Commit
commit
```

### Step 3: Configure Security Zones

Navigate to **Network → Zones**

**Create Trust Zone:**
```
Name: trust
Type: Layer3
Interfaces: ethernet1/1
```

**Create DMZ Zone:**
```
Name: dmz
Type: Layer3
Interfaces: ethernet1/2
```

**CLI Commands:**
```xml
set zone trust network layer3 [ ethernet1/1 ]
set zone dmz network layer3 [ ethernet1/2 ]
commit
```

### Step 4: Configure Virtual Router

Navigate to **Network → Virtual Routers → default**

**Static Routes:**

**Route 1: To Public Subnet**
```
Name: to-public-subnet
Destination: 172.19.1.0/24
Interface: ethernet1/1
Next Hop: None (directly connected)
Metric: 10
```

**Route 2: To Private Subnet**
```
Name: to-private-subnet
Destination: 172.19.2.0/24
Interface: ethernet1/2
Next Hop: None (directly connected)
Metric: 10
```

**CLI Commands:**
```xml
set network virtual-router default routing-table ip static-route to-public-subnet destination 172.19.1.0/24 interface ethernet1/1
set network virtual-router default routing-table ip static-route to-private-subnet destination 172.19.2.0/24 interface ethernet1/2
commit
```

### Step 5: Create Address Objects

Navigate to **Objects → Addresses**

**VM1 (Client):**
```
Name: vm1-client
Type: IP Netmask
IP/Netmask: 172.19.1.5/32
Description: user01workstation - Ubuntu client
```

**VM2 (Web Server):**
```
Name: vm2-webserver
Type: IP Netmask
IP/Netmask: 172.19.2.5/32
Description: web01application - Nginx server
```

**Public Subnet:**
```
Name: public-subnet
Type: IP Netmask
IP/Netmask: 172.19.1.0/24
Description: Public/Trust subnet
```

**Private Subnet:**
```
Name: private-subnet
Type: IP Netmask
IP/Netmask: 172.19.2.0/24
Description: Private/DMZ subnet
```

**CLI Commands:**
```xml
set address vm1-client ip-netmask 172.19.1.5/32 description "user01workstation"
set address vm2-webserver ip-netmask 172.19.2.5/32 description "web01application"
set address public-subnet ip-netmask 172.19.1.0/24
set address private-subnet ip-netmask 172.19.2.0/24
commit
```

### Step 6: Create Service Objects (Optional)

Navigate to **Objects → Services**

```
Name: tcp-80
Protocol: TCP
Destination Port: 80

Name: tcp-443
Protocol: TCP
Destination Port: 443
```

**CLI Commands:**
```xml
set service tcp-80 protocol tcp port 80
set service tcp-443 protocol tcp port 443
commit
```

### Step 7: Create Initial Security Policy (Deny All)

Navigate to **Policies → Security**

**Rule: Deny-All-Initial**
```
Name: Deny-All-Initial
Source Zone: trust
Destination Zone: dmz
Source Address: any
Destination Address: any
Application: any
Service: application-default
Action: deny
Log at Session End: yes
Position: bottom
```

**CLI Commands:**
```xml
set rulebase security rules Deny-All-Initial from trust
set rulebase security rules Deny-All-Initial to dmz
set rulebase security rules Deny-All-Initial source any
set rulebase security rules Deny-All-Initial destination any
set rulebase security rules Deny-All-Initial application any
set rulebase security rules Deny-All-Initial service application-default
set rulebase security rules Deny-All-Initial action deny
set rulebase security rules Deny-All-Initial log-end yes
commit
```

### Step 8: Verify Configuration

**Check Interfaces:**
```
show interface all
show interface ethernet1/1
show interface ethernet1/2
```

**Check Zones:**
```
show zone all
```

**Check Routes:**
```
show routing route
```

**Test Connectivity:**
```
ping source 172.19.1.4 host 172.19.1.5
ping source 172.19.2.4 host 172.19.2.5
```

---

## Phase 2: Enable API Access

For GitOps automation, enable API access on the firewall.

### Method 1: Web UI

Navigate to **Device → Setup → Management**

```
Administrators tab:
  - Username: admin (or create new API user)
  - Authentication Profile: None (use local auth)

Management Interface Settings:
  - HTTPS: Enable
  - HTTP Server Profile: (create if needed)
  - API key: Generate
```

### Method 2: Generate API Key via CLI

```bash
# From your workstation
curl -k -X POST 'https://[FIREWALL-PUBLIC-IP]/api/?type=keygen&user=admin&password=YOUR_PASSWORD'

# Response will contain:
# <response status="success"><result><key>LUFRPT14MW5xOEo1R09...</key></result></response>

# Save this API key for Ansible/GitLab
```

**Store API Key:**
```bash
export PALO_ALTO_API_KEY="LUFRPT14MW5xOEo1R09..."
```

---

## Phase 3: Verification Tests

### Test 1: Firewall Interfaces are UP

```bash
# SSH to firewall
ssh admin@[FIREWALL-PUBLIC-IP]

# Check interface status
show interface all

# Expected output:
# ethernet1/1: up
# ethernet1/2: up
```

### Test 2: VM1 to Firewall Connectivity

```bash
# SSH to VM1
ssh azureuser@[VM1-PUBLIC-IP]

# Ping firewall trust interface
ping 172.19.1.4

# Should succeed ✅
```

### Test 3: VM2 to Firewall Connectivity

```bash
# SSH to VM2 (via Bastion or public IP if accessible)
ssh azureuser@[VM2-PUBLIC-IP]

# Ping firewall DMZ interface
ping 172.19.2.4

# Should succeed ✅
```

### Test 4: VM1 to VM2 Blocked

```bash
# SSH to VM1
ssh azureuser@[VM1-PUBLIC-IP]

# Try to reach VM2
curl http://172.19.2.5

# Should be BLOCKED/TIMEOUT ❌
# This is expected - no allow rule exists
```

### Test 5: Check Firewall Traffic Logs

**Web UI:**
- Navigate to **Monitor → Logs → Traffic**
- Filter: `( addr.src in 172.19.1.5 ) and ( addr.dst in 172.19.2.5 )`

**Expected:**
- You should see **deny** logs when VM1 tries to reach VM2
- This confirms traffic IS going through the firewall ✅

**CLI:**
```bash
show log traffic direction equal both source equal 172.19.1.5 destination equal 172.19.2.5
```

---

## Phase 4: Firewall Configuration Summary

After completing all steps, you should have:

✅ **Interfaces:**
- ethernet1/1 (172.19.1.4/24) - Trust zone
- ethernet1/2 (172.19.2.4/24) - DMZ zone

✅ **Zones:**
- trust (ethernet1/1)
- dmz (ethernet1/2)

✅ **Virtual Router:**
- Default router with static routes to both subnets

✅ **Address Objects:**
- vm1-client (172.19.1.5/32)
- vm2-webserver (172.19.2.5/32)
- public-subnet (172.19.1.0/24)
- private-subnet (172.19.2.0/24)

✅ **Security Policy:**
- Deny-All-Initial rule (trust → dmz, deny, logged)

✅ **API Access:**
- API key generated and saved

✅ **Traffic Flow:**
- VM1 → Firewall eth1 → (blocked by policy) → Firewall eth2 → VM2
- Firewall logs show deny traffic ✅

---

## Phase 5: Ready for GitOps!

Your firewall is now configured and ready for automated rule deployment via GitLab CI/CD!

**Current State:**
- ❌ VM1 **CANNOT** access VM2 (denied by firewall)
- ✅ Firewall **IS** in the traffic path
- ✅ Firewall **LOGS** traffic attempts
- ✅ API **ENABLED** for automation

**Next Steps:**
1. Setup GitLab repository with Ansible playbooks
2. Create firewall rule JSON (allow_vm1_to_vm2.json)
3. Configure GitLab CI/CD pipeline
4. Deploy rule via GitOps → VM1 can access VM2! 🎉

---

## Troubleshooting

### Issue: Cannot ping firewall interfaces

**Check:**
1. Interface management profile allows ping
2. Security zones are configured
3. Interfaces are in "up" state

**Fix:**
```xml
set network interface ethernet ethernet1/1 layer3 interface-management-profile allow-ping
set network profiles interface-management-profile allow-ping ping yes
commit
```

### Issue: No traffic logs appearing

**Check:**
1. Security policy has "log at session end" enabled
2. Log forwarding profile is configured
3. Wait a few minutes for logs to appear

### Issue: VM1 still can reach VM2 after deny rule

**Check:**
1. Route table is applied to correct subnets
2. Firewall interfaces are UP
3. Security policy is committed
4. Check effective routes on VM1's NIC in Azure portal

### Issue: API authentication fails

**Check:**
1. API key is valid (regenerate if needed)
2. Admin account is not locked
3. HTTPS is enabled on management interface

---

## Important Notes

🔒 **Security:**
- This is a DEMO configuration
- In production, use more granular policies
- Enable threat prevention profiles
- Implement URL filtering
- Use dedicated service accounts for API

📊 **Monitoring:**
- Always enable logging on security policies
- Monitor traffic logs during demo
- Set up log forwarding to Azure Monitor (optional)

🚀 **Next Phase:**
- We'll automate rule creation via Ansible
- GitLab CI/CD will deploy rules on git commit
- VM1 monitoring script will show BLOCKED → SUCCESS

---

## Quick Reference

**Firewall Management:**
- Web UI: https://[FIREWALL-PUBLIC-IP]
- SSH: ssh admin@[FIREWALL-PUBLIC-IP]
- API Endpoint: https://[FIREWALL-PUBLIC-IP]/api/

**Important IPs:**
- VM1 Client: 172.19.1.5
- VM2 Web Server: 172.19.2.5
- Firewall Trust: 172.19.1.4
- Firewall DMZ: 172.19.2.4

**Demo Command (from VM1):**
```bash
# This should be BLOCKED initially
curl http://172.19.2.5

# After GitOps deployment, this will succeed
curl http://172.19.2.5
# Output: nginx welcome page HTML
```

---

**Status: ✅ Configuration Complete - Ready for GitOps Demo!**
