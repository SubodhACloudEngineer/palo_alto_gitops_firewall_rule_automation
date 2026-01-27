# Palo Alto GitOps Demo - Complete Setup Checklist

## ✅ Pre-Demo Checklist

Use this checklist to ensure everything is ready for your demo.

---

### Phase 1: Azure Infrastructure ✅ (DONE)

- [x] Resource Group created: `rg-panorama-gitops-poc`
- [x] VNet created: `fwVNET (172.19.0.0/16)`
- [x] Palo Alto firewall deployed: `fw1toyota123`
- [x] VM1 deployed: `user01workstation (172.19.1.5)`
- [x] VM2 deployed: `web01application (172.19.2.5)`
- [x] Route table created: `blocktraffic`
- [x] Bastion hosts configured
- [x] Network Security Groups configured

**Status:** ✅ COMPLETE

---

### Phase 2: Firewall Configuration 🔧 (TO DO)

Follow: `01-firewall-configuration-guide.md`

#### 2.1 Network Interfaces

- [ ] Login to firewall: `https://[firewall-public-ip]`
- [ ] Configure ethernet1/1 (Trust)
  - [ ] IP: 172.19.1.4/24
  - [ ] Zone: trust
  - [ ] Virtual Router: default
- [ ] Configure ethernet1/2 (DMZ)
  - [ ] IP: 172.19.2.4/24
  - [ ] Zone: dmz
  - [ ] Virtual Router: default
- [ ] Verify interfaces are UP
  - [ ] `show interface ethernet1/1`
  - [ ] `show interface ethernet1/2`

#### 2.2 Security Zones

- [ ] Create "trust" zone
  - [ ] Assign ethernet1/1
- [ ] Create "dmz" zone
  - [ ] Assign ethernet1/2
- [ ] Verify zones: `show zone all`

#### 2.3 Virtual Router

- [ ] Add static routes
  - [ ] 172.19.1.0/24 → ethernet1/1
  - [ ] 172.19.2.0/24 → ethernet1/2
- [ ] Verify routes: `show routing route`

#### 2.4 Address Objects

- [ ] Create vm1-client (172.19.1.5/32)
- [ ] Create vm2-webserver (172.19.2.5/32)
- [ ] Create public-subnet (172.19.1.0/24)
- [ ] Create private-subnet (172.19.2.0/24)

#### 2.5 Initial Security Policy

- [ ] Create "Deny-All-Initial" rule
  - [ ] Source Zone: trust
  - [ ] Destination Zone: dmz
  - [ ] Action: deny
  - [ ] Log at Session End: yes
- [ ] Commit configuration

#### 2.6 API Access

- [ ] Generate API key
- [ ] Save API key for later use
- [ ] Test API access:
  ```bash
  curl -k -u "admin:password" \
    "https://[firewall-ip]/api/?type=op&cmd=<show><s><info></info></s></show>"
  ```

#### 2.7 Verification

- [ ] VM1 can ping firewall: `ping 172.19.1.4`
- [ ] VM2 can ping firewall: `ping 172.19.2.4`
- [ ] VM1 CANNOT reach VM2: `curl http://172.19.2.5` (should timeout)
- [ ] Firewall logs show deny traffic from VM1 to VM2

**Estimated Time:** 2-3 hours  
**Status:** ⏳ PENDING

---

### Phase 3: GitLab Repository Setup 📦 (TO DO)

#### 3.1 Create Repository

- [ ] Create GitLab repository: `palo-alto-gitops-demo`
- [ ] Clone repository locally
- [ ] Copy all files from this package

#### 3.2 Repository Structure

Upload these files:
- [ ] `.gitlab-ci.yml` (CI/CD pipeline)
- [ ] `ansible.cfg` (Ansible configuration)
- [ ] `README.md` (Documentation)
- [ ] `inventory/firewall.yml` (Inventory)
- [ ] `firewall-rules/allow_vm1_to_vm2.json` (Rule definition)
- [ ] `playbooks/deploy_firewall_rule.yml` (Playbook)
- [ ] `docs/01-firewall-configuration-guide.md`
- [ ] `docs/02-demo-execution-guide.md`
- [ ] `vm1-scripts/setup_vm1.sh`
- [ ] `vm1-scripts/monitor_vm2_access.sh`

#### 3.3 GitLab CI/CD Variables

Navigate to: **Settings → CI/CD → Variables**

Add these **MASKED** variables:

- [ ] `PA_FIREWALL_IP` = [firewall-public-ip]
- [ ] `PA_USERNAME` = admin
- [ ] `PA_PASSWORD` = [firewall-password]
- [ ] `VM1_PUBLIC_IP` = [vm1-public-ip]
- [ ] `VM2_PUBLIC_IP` = [vm2-public-ip]

**Important:** Check "Mask variable" for all passwords!

#### 3.4 Test Pipeline

- [ ] Commit and push to GitLab
- [ ] Verify pipeline runs
- [ ] Check for any errors
- [ ] Fix any issues

**Estimated Time:** 1 hour  
**Status:** ⏳ PENDING

---

### Phase 4: VM1 Setup 💻 (TO DO)

#### 4.1 Upload Scripts

- [ ] SSH to VM1: `ssh azureuser@[VM1-PUBLIC-IP]`
- [ ] Upload setup script:
  ```bash
  # Option 1: SCP
  scp vm1-scripts/setup_vm1.sh azureuser@[VM1-PUBLIC-IP]:~/
  
  # Option 2: Curl from GitLab
  curl -o setup_vm1.sh [GitLab-raw-url]
  ```

#### 4.2 Run Setup

- [ ] Make executable: `chmod +x setup_vm1.sh`
- [ ] Run setup: `./setup_vm1.sh`
- [ ] Verify tools installed (curl, netcat, etc.)
- [ ] Verify scripts created in `~/palo-demo/`

#### 4.3 Test Monitoring Script

- [ ] Run: `cd ~/palo-demo`
- [ ] Start: `./monitor_vm2_access.sh`
- [ ] Verify shows: ❌ BLOCKED messages
- [ ] Stop: Ctrl+C
- [ ] Keep terminal open for demo

#### 4.4 Quick Connectivity Test

- [ ] Run: `./quick_test.sh`
- [ ] Verify:
  - [ ] Can ping firewall (172.19.1.4) ✅
  - [ ] CANNOT reach VM2 (172.19.2.5) ❌
  - [ ] This is expected!

**Estimated Time:** 30 minutes  
**Status:** ⏳ PENDING

---

### Phase 5: Final Pre-Demo Checks ✅ (Day of Demo)

#### 5.1 Azure Resources (10 min before)

- [ ] All VMs are running
- [ ] Firewall is accessible
- [ ] Bastion is working (if needed)
- [ ] No Azure maintenance windows scheduled

#### 5.2 Firewall Status (5 min before)

- [ ] Login to firewall web UI
- [ ] Verify interfaces are UP
- [ ] Check "Deny-All-Initial" rule exists
- [ ] Open traffic logs panel
- [ ] Leave browser tab open

#### 5.3 VM1 Terminal (5 min before)

- [ ] SSH to VM1
- [ ] Navigate to `~/palo-demo/`
- [ ] Start monitoring: `./monitor_vm2_access.sh`
- [ ] Verify: Shows ❌ BLOCKED messages
- [ ] Keep this running and visible

#### 5.4 GitLab (5 min before)

- [ ] Login to GitLab
- [ ] Open repository
- [ ] Verify main branch is clean
- [ ] Prepare to create merge request
- [ ] Test merge request creation (optional)

#### 5.5 Screen Sharing Setup (5 min before)

Arrange windows for optimal viewing:

**Layout:**
```
┌─────────────────────┬─────────────────────┐
│                     │                     │
│   Browser           │   Terminal          │
│   (GitLab)          │   (VM1 Monitoring)  │
│                     │                     │
├─────────────────────┼─────────────────────┤
│                     │                     │
│   Browser           │   Slides            │
│   (Firewall UI)     │   (Backup)          │
│                     │                     │
└─────────────────────┴─────────────────────┘
```

**Checklist:**
- [ ] Close unnecessary tabs/windows
- [ ] Mute notifications
- [ ] Test screen sharing
- [ ] Adjust font sizes for visibility
- [ ] Test audio/video

#### 5.6 Backup Materials

- [ ] Demo guide printed/accessible
- [ ] Backup video ready
- [ ] Screenshots of each step
- [ ] Architecture diagram slide
- [ ] Contact info for tech support

---

## 🎬 Demo Day Checklist

### 15 Minutes Before

- [ ] Join meeting early
- [ ] Test audio/video
- [ ] Share screen (test)
- [ ] Open all required windows
- [ ] Start VM1 monitoring script
- [ ] Verify GitLab is accessible

### 5 Minutes Before

- [ ] Final connectivity check
- [ ] Verify VM1 shows BLOCKED
- [ ] Check firewall logs updating
- [ ] Breathe and relax! 😊

### During Demo

- [ ] Follow demo-execution-guide.md
- [ ] Speak clearly and slowly
- [ ] Pause for questions
- [ ] Show terminal in real-time
- [ ] Celebrate the BLOCKED → SUCCESS moment! 🎉

### After Demo

- [ ] Q&A session
- [ ] Share recording/slides
- [ ] Collect feedback
- [ ] Reset environment (optional)

---

## 🔄 Post-Demo Reset (Optional)

To reset for another demo:

### Quick Reset (5 minutes)

```bash
# 1. SSH to firewall
ssh admin@[firewall-ip]

# 2. Delete the rule
configure
delete rulebase security rules Allow-VM1-to-VM2-Web
commit
exit

# 3. Verify VM1 blocked again
ssh azureuser@[VM1-PUBLIC-IP]
curl http://172.19.2.5  # Should timeout

# 4. Close GitLab MR or reset branch
# Done! Ready for next demo
```

### Full Reset (if needed)

- [ ] Delete all demo rules from firewall
- [ ] Reset GitLab repository (revert commits)
- [ ] Restart VM1 monitoring script
- [ ] Verify blocked state

---

## 📊 Demo Success Metrics

After demo, you should have shown:

- [x] Live BLOCKED → SUCCESS transition ✅
- [x] Automated firewall rule deployment ✅
- [x] Complete audit trail in GitLab ✅
- [x] Firewall logs verification ✅
- [x] Time saved: 90%+ ✅
- [x] Zero manual steps ✅

---

## ⏱️ Time Estimates

| Phase | Duration | When |
|-------|----------|------|
| Firewall Configuration | 2-3 hours | 1-2 days before |
| GitLab Setup | 1 hour | 1 day before |
| VM1 Setup | 30 minutes | 1 day before |
| Pre-Demo Checks | 30 minutes | Day of demo |
| Demo Execution | 10-12 minutes | Live |

**Total Prep Time:** 4-5 hours  
**Demo Time:** 10-12 minutes

---

## 📞 Emergency Contacts

**Azure Issues:**
- Azure Portal: portal.azure.com
- Azure Support: [ticket-number]

**GitLab Issues:**
- GitLab Status: status.gitlab.com
- GitLab Support: [your-support-channel]

**Palo Alto Issues:**
- TAC Support: [support-number]
- Documentation: docs.paloaltonetworks.com

---

## 🎯 Critical Success Factors

**Must Have:**
1. ✅ Firewall configured and accessible
2. ✅ VM1 monitoring script running and showing BLOCKED
3. ✅ GitLab pipeline working
4. ✅ All credentials available

**Nice to Have:**
- Backup video recording
- Pre-captured screenshots
- Printed demo guide
- Secondary internet connection

**Can Skip (if time constrained):**
- Manual approval gates (for demo)
- Advanced pipeline features
- Notification integrations

---

## 📝 Notes Section

Use this space for your specific notes:

**Firewall Public IP:** _________________________

**VM1 Public IP:** _________________________

**VM2 Public IP:** _________________________

**API Key:** _________________________

**GitLab URL:** _________________________

**Demo Date/Time:** _________________________

**Audience:** _________________________

**Special Requests:** _________________________

---

**Good luck with your demo! 🚀**

Remember: Practice makes perfect. Run through the demo 2-3 times before the live presentation!
