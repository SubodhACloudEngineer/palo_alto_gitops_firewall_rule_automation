# Palo Alto GitOps Demo - Complete Execution Guide

## Demo Overview

**Duration:** 10-12 minutes  
**Goal:** Demonstrate automated firewall rule deployment via GitOps  
**Wow Factor:** Live transition from BLOCKED → SUCCESS in terminal  

**The Story:**
- VM1 (user workstation) needs access to VM2 (web application)
- Security policy currently blocks this access
- Developer commits firewall rule to GitLab
- CI/CD pipeline automatically deploys rule to Palo Alto firewall
- Access is granted - visible in real-time on terminal

---

## Pre-Demo Setup Checklist

### 1 Day Before Demo

- [ ] Complete firewall configuration (see 01-firewall-configuration-guide.md)
- [ ] Verify VM1 cannot access VM2 (currently blocked)
- [ ] Test GitLab pipeline in development branch
- [ ] Prepare presentation slides
- [ ] Record backup video (in case of technical issues)

### 2 Hours Before Demo

- [ ] Verify all VMs are running
- [ ] Test SSH access to VM1
- [ ] Verify firewall is accessible (https://[firewall-ip])
- [ ] Check GitLab repository is accessible
- [ ] Prepare all browser tabs

### 30 Minutes Before Demo

- [ ] Open Terminal 1: SSH to VM1, ready to run monitor script
- [ ] Open Terminal 2: Ready for firewall CLI commands
- [ ] Open Browser Tab 1: GitLab repository
- [ ] Open Browser Tab 2: Firewall web UI (logged in)
- [ ] Open Browser Tab 3: Azure portal (resource group view)
- [ ] Test all URLs are accessible

### 5 Minutes Before Demo

- [ ] Start VM1 monitoring script (shows BLOCKED messages)
- [ ] Position all windows for screen sharing
- [ ] Mute non-essential notifications
- [ ] Have backup slides ready

---

## Demo Script - Minute by Minute

### **Minute 0-1: Introduction & Problem Statement**

**Script:**
> "Today I'm going to show you how we automate firewall rule deployment using GitOps principles with Palo Alto Networks firewall in Azure."
>
> "The traditional approach requires manual firewall changes, which are slow, error-prone, and lack version control. We're changing that."

**Show:**
- Azure architecture diagram (VM1, Firewall, VM2)
- Current state: Access blocked

**Demo Action:**
1. Show Terminal with VM1 monitoring script running
   ```
   [2025-01-26 14:00:01] Attempt #1: ❌ BLOCKED - Connection refused
   [2025-01-26 14:00:06] Attempt #2: ❌ BLOCKED - Connection refused
   ```

2. Explain: "VM1 cannot access the web application on VM2. The firewall is blocking this traffic."

---

### **Minute 1-3: Show Current Configuration**

**Script:**
> "Let me show you the current firewall configuration and logs to prove traffic is being blocked at the firewall layer."

**Demo Action:**

1. **Switch to Firewall UI** (Browser Tab 2)
   - Navigate to: `Policies → Security`
   - Show: "Deny-All-Initial" rule
   - Point out: trust → dmz, action = deny

2. **Show Firewall Logs**
   - Navigate to: `Monitor → Logs → Traffic`
   - Filter: `source = 172.19.1.5 AND destination = 172.19.2.5`
   - Show: Deny logs appearing
   - Explain: "Every 5 seconds, VM1 tries to connect, and firewall denies it"

3. **SSH to VM1 (optional live test)**
   ```bash
   curl http://172.19.2.5
   # Shows: curl: (28) Connection timed out
   ```

---

### **Minute 3-5: Show the Solution (GitLab Repository)**

**Script:**
> "Instead of manually configuring the firewall, we use Infrastructure as Code. The firewall rule is defined in JSON format and stored in GitLab."

**Demo Action:**

1. **Switch to GitLab** (Browser Tab 1)
   - Navigate to repository: `palo-alto-gitops-demo`
   - Show directory structure:
     ```
     firewall-rules/
       allow_vm1_to_vm2.json
     playbooks/
       deploy_firewall_rule.yml
     .gitlab-ci.yml
     ```

2. **Open firewall rule file** (`firewall-rules/allow_vm1_to_vm2.json`)
   - Highlight key fields:
     - `rule_name`: "Allow-VM1-to-VM2-Web"
     - `source_address`: ["172.19.1.5"] ← VM1
     - `destination_address`: ["172.19.2.5"] ← VM2
     - `action`: "allow"

3. **Show Ansible playbook** (briefly)
   - `playbooks/deploy_firewall_rule.yml`
   - Explain: "Ansible will deploy this rule to the firewall"

4. **Show CI/CD Pipeline** (`.gitlab-ci.yml`)
   - Highlight stages:
     - Validate
     - Test  
     - Deploy
     - Verify
   - Explain: "Fully automated deployment pipeline"

---

### **Minute 5-6: Create Merge Request**

**Script:**
> "Now I'll create a merge request to deploy this rule. This triggers our automated pipeline."

**Demo Action:**

1. **Create new branch** (if not already done)
   - Branch name: `feature/allow-vm1-web-access`
   - Or work from existing branch

2. **Create Merge Request**
   - Title: "Allow VM1 access to VM2 web application"
   - Description:
     ```
     ## Change Summary
     Deploy firewall rule to allow user01workstation access to web01application
     
     ## Details
     - Source: 172.19.1.5 (VM1)
     - Destination: 172.19.2.5 (VM2)
     - Service: HTTP/HTTPS
     - Action: Allow
     ```

3. **Submit MR**
   - Pipeline starts automatically
   - Show: "Pipeline Running" badge

---

### **Minute 6-9: Watch Pipeline Execute (THE MAGIC)**

**Script:**
> "The pipeline is now running. Watch as it validates, tests, and deploys our firewall rule completely automatically."

**Demo Action:**

1. **Click on Pipeline**
   - Show all stages

2. **Watch stages complete** (explain each):
   
   **✅ Stage 1: Validate** (~30 seconds)
   - validate-json-schema
   - validate-rule-content
   - Explain: "Ensures rule syntax is correct"

   **✅ Stage 2: Test** (~30 seconds)
   - ansible-syntax-check
   - ansible-lint
   - dry-run-deployment
   - Explain: "Validates Ansible playbook"

   **✅ Stage 3: Deploy** (~60 seconds)
   - deploy-to-development (if using dev environment)
   - OR deploy-to-production
   - Explain: "Ansible connects to firewall via API"
   - Show logs in real-time:
     ```
     TASK [Create security rule on Palo Alto firewall]
     changed: [localhost]
     
     TASK [Commit configuration to firewall]
     changed: [localhost]
     ```

   **⏸️ Stage 4: Manual Approval** (if configured)
   - Show approval gate
   - Click "Play" button
   - Explain: "Production deployments require approval"

   **✅ Stage 5: Verify** (~30 seconds)
   - verify-firewall-rule
   - verify-connectivity

3. **During pipeline execution:**
   - Keep Terminal 1 (VM1 monitor) visible in corner
   - Point out: "Still showing BLOCKED messages"

---

### **Minute 9-10: THE MAGIC MOMENT 🎉**

**Script:**
> "The pipeline has completed. The rule is now deployed. Watch what happens..."

**Demo Action:**

1. **Switch focus to Terminal 1** (VM1 monitoring script)
   
2. **Watch for the transition:**
   ```
   [2025-01-26 14:09:45] Attempt #115: ❌ BLOCKED - Connection refused
   [2025-01-26 14:09:50] Attempt #116: ❌ BLOCKED - Connection refused
   [2025-01-26 14:09:55] Attempt #117: ✅ SUCCESS - HTTP 200 OK
                           🎉 FIREWALL RULE IS ACTIVE!
   
   ╔═══════════════════════════════════════════════════════════╗
   ║                                                           ║
   ║     🎊 BREAKTHROUGH! Firewall Rule Deployed! 🎊          ║
   ║                                                           ║
   ║  GitOps pipeline has successfully deployed the rule      ║
   ║  Traffic from VM1 to VM2 is now permitted                ║
   ║                                                           ║
   ╚═══════════════════════════════════════════════════════════╝
   ```

3. **Celebrate the transition!**
   - Point out: "From BLOCKED to SUCCESS - completely automated!"
   - Let it run for a few more iterations showing SUCCESS

4. **Optional: Show in browser**
   - Open new terminal: `curl http://172.19.2.5`
   - Or open browser: `http://172.19.2.5` (if accessible)
   - Show nginx success page with fancy styling

---

### **Minute 10-11: Show Verification**

**Script:**
> "Let me prove this worked by showing you the firewall configuration and logs."

**Demo Action:**

1. **Switch to Firewall UI**
   
   **Show New Rule:**
   - Navigate to: `Policies → Security`
   - Show: "Allow-VM1-to-VM2-Web" rule (at top)
   - Highlight:
     - Source: 172.19.1.5
     - Destination: 172.19.2.5
     - Action: allow
     - Tags: "gitops-demo", "auto-deployed"

2. **Show Allow Logs:**
   - Navigate to: `Monitor → Logs → Traffic`
   - Filter: `source = 172.19.1.5 AND destination = 172.19.2.5`
   - Show: **Allow** logs now appearing
   - Point out:
     - Action changed from "deny" to "allow"
     - Timestamp matches deployment time
     - Bytes transferred (traffic is flowing)

3. **Show GitLab Pipeline Success**
   - Back to GitLab
   - Show: All stages green ✅
   - Show: Deployment artifacts/reports

---

### **Minute 11-12: Wrap Up & Benefits**

**Script:**
> "So what did we just accomplish?"

**Explain Benefits:**

📊 **Speed:**
- Traditional: 30-60 minutes (manual firewall changes)
- GitOps: 2-3 minutes (fully automated)

🔒 **Security:**
- Every change is peer-reviewed (MR process)
- Complete audit trail in Git
- Automated validation prevents errors

📝 **Compliance:**
- Who, what, when, why - all documented
- Easy rollback (git revert)
- Version controlled configurations

🔄 **Repeatability:**
- Same process for dev, staging, production
- No manual steps = no human error
- Scalable to hundreds of rules

**Show Architecture Diagram:**
- Developer → GitLab → CI/CD → Ansible → Palo Alto API → Firewall
- Emphasize: "Zero manual firewall configuration"

**Future Enhancements:**
- Panorama for multi-firewall management
- ServiceNow integration for approvals
- Automated testing in dev environment
- Self-service portal for developers

---

## Post-Demo Q&A Preparation

### Expected Questions:

**Q: What if the pipeline fails?**
A: The firewall remains in its current state (safe). GitLab shows exactly which stage failed. We can fix and redeploy. No manual rollback needed - just git revert.

**Q: How do you handle emergency changes?**
A: We have a "break glass" procedure with manual approval gate that can be fast-tracked. The change still goes through Git for audit purposes, but approval is expedited.

**Q: Can you rollback a change?**
A: Yes, two ways:
1. Git revert → triggers pipeline → removes rule
2. Manual in firewall (emergency only)

**Q: What about Panorama?**
A: This demo uses direct firewall API for simplicity. With Panorama, same process works - just point Ansible to Panorama instead. Benefit: manage multiple firewalls centrally.

**Q: How long did this take to build?**
A: Initial setup: 1-2 days. Now that it's built, deploying new rules takes 3 minutes. ROI is huge for environments with frequent changes.

**Q: What about approval workflows?**
A: Built into GitLab - you saw the manual approval gate. Can integrate with ServiceNow for formal change management.

**Q: Does this work with other vendors?**
A: Yes! Same GitOps principles apply. Ansible has modules for Cisco, Fortinet, Check Point, etc. The process is vendor-agnostic.

---

## Troubleshooting During Demo

### Issue: Pipeline fails at deploy stage

**Cause:** Firewall API credentials incorrect

**Fix:**
1. Check GitLab CI/CD variables
2. Verify firewall is accessible
3. Re-run pipeline job

### Issue: VM1 monitoring script shows errors

**Cause:** Network issue or VM offline

**Quick Fix:**
1. Have backup video ready
2. Show firewall logs instead
3. Explain: "In production, we'd see SUCCESS here"

### Issue: Firewall UI is slow

**Cause:** Azure resource constraints

**Workaround:**
1. Use CLI commands instead
2. Show pre-captured screenshots
3. Focus on GitLab pipeline

### Issue: Screen sharing lag

**Backup Plan:**
1. Use pre-recorded video segments
2. Have screenshots ready
3. Narrate from slides if needed

---

## Demo Environment Reset

To reset demo for next presentation:

```bash
# 1. SSH to firewall
ssh admin@[firewall-ip]

# 2. Delete the rule
configure
delete rulebase security rules Allow-VM1-to-VM2-Web
commit

# 3. Verify VM1 is blocked again
# SSH to VM1
curl http://172.19.2.5
# Should timeout

# 4. Close GitLab MR (or revert)
# Ready for next demo!
```

---

## Materials Checklist

- [ ] This demo guide (printed/on tablet)
- [ ] Architecture diagram (slide)
- [ ] Backup video recording
- [ ] Screenshots of each step
- [ ] GitLab credentials ready
- [ ] Firewall credentials ready
- [ ] VM SSH keys ready
- [ ] Backup slides (technical issues)

---

## Demo Success Metrics

After demo, you should be able to show:

✅ Live transition from BLOCKED to SUCCESS  
✅ Firewall rule created automatically  
✅ Complete audit trail in GitLab  
✅ Traffic logs in firewall showing allowed traffic  
✅ End-to-end automation (no manual steps)  
✅ Time saved: ~90% compared to manual process  

---

## Additional Tips

🎯 **Audience Engagement:**
- Pause after each major step
- Ask: "Can everyone see the terminal?"
- Explain what's happening in real-time
- Use the word "automatically" frequently

📱 **Backup Plans:**
- Have video recording ready
- Take screenshots of each step beforehand
- Practice demo 3-5 times
- Have co-presenter who can help with technical issues

🎬 **Recording:**
- Record successful run beforehand
- Use as backup or for async viewing
- Share with stakeholders who couldn't attend

---

**Good luck with your demo! 🚀**

This is a very impressive demonstration of modern network automation and will definitely wow your audience!
