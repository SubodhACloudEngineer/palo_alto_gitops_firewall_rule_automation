# Platform Engineering Review Document
## Palo Alto GitOps Firewall Rule Automation & Azure VM Provisioning

**Date:** February 2026
**Prepared For:** Platform Engineering Team Review
**Project Status:** Demo/PoC Phase

---

## 1. Executive Summary

This project implements a **Self-Service Portal** for infrastructure automation using GitOps principles:
- **Firewall Rule Management**: Users submit requests via web form → JSON committed to Git → CI/CD validates and deploys to Palo Alto firewall
- **Azure VM Provisioning**: Users request VMs via web form → Terraform configs generated → CI/CD provisions infrastructure

---

## 2. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           SELF-SERVICE PORTAL                                │
│                         (Flask Application)                                  │
├─────────────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │  Firewall    │  │  Azure VM    │  │   NetBox     │  │   Service    │    │
│  │  Rule Form   │  │  Request     │  │ Integration  │  │   Catalog    │    │
│  └──────┬───────┘  └──────┬───────┘  └──────────────┘  └──────────────┘    │
└─────────┼─────────────────┼─────────────────────────────────────────────────┘
          │                 │
          ▼                 ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                              GIT REPOSITORY                                  │
│  ┌──────────────────┐         ┌──────────────────────────────────────────┐ │
│  │  firewall-rules/ │         │  terraform/azure-vm/deployments/         │ │
│  │  ├── rule1.json  │         │  ├── deployment-001/terraform.tfvars     │ │
│  │  ├── rule2.json  │         │  └── deployment-002/terraform.tfvars     │ │
│  └──────────────────┘         └──────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────────────┘
          │                                    │
          ▼                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                          GITHUB ACTIONS CI/CD                                │
│  ┌────────────────────────────┐    ┌────────────────────────────────────┐  │
│  │  firewall-rule-automation  │    │  azure-vm-automation               │  │
│  │  • JSON Schema Validation  │    │  • Terraform Format Check          │  │
│  │  • Security Checks         │    │  • Terraform Validate              │  │
│  │  • Duplicate Detection     │    │  • Terraform Plan                  │  │
│  │  • Deploy via PAN-OS API   │    │  • Terraform Apply                 │  │
│  └────────────────────────────┘    └────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────────────────────────┘
          │                                    │
          ▼                                    ▼
┌──────────────────────┐            ┌──────────────────────┐
│   PALO ALTO FIREWALL │            │      AZURE CLOUD     │
│   (PAN-OS XML API)   │            │  (VMs, VNet, NSG)    │
└──────────────────────┘            └──────────────────────┘
```

---

## 3. Current State Assessment

### 3.1 Modularity Analysis

| Component | Current State | Assessment |
|-----------|---------------|------------|
| Flask Portal (`app.py`) | 1,400+ lines, single file | ❌ Monolithic |
| Terraform Templates | Separated files (main, variables, outputs) | ✅ Modular |
| CI/CD Workflows | Separate workflow per service | ✅ Modular |
| Firewall Rules | Individual JSON per rule | ✅ Modular |
| Tests | Present but in single files | ⚠️ Partial |
| Service Catalog | JSON-based, extensible | ✅ Modular |

### 3.2 Component Breakdown

#### Self-Service Portal
- **Technology**: Python Flask
- **Authentication**: None (demo mode)
- **Database**: None (stateless, Git-backed)
- **Key Functions**:
  - Service catalog display
  - Form rendering and validation
  - Git operations (commit, push)
  - NetBox integration for source/destination lookup

#### Firewall Rule Deployment
- **Source of Truth**: Git repository (`firewall-rules/*.json`)
- **Validation**: JSON Schema, security checks, duplicate detection
- **Deployment**: PAN-OS XML API via Python script
- **Rollback**: Git revert + redeploy

#### Azure VM Provisioning
- **IaC Tool**: Terraform
- **Authentication**: Service Principal (environment variables)
- **State Storage**: Local (demo) - needs migration to remote
- **Resources**: Resource Group, VNet, Subnet, NSG, VMs

---

## 4. Security Considerations

### 4.1 Current Implementation

| Area | Current State | Risk Level |
|------|---------------|------------|
| Portal Authentication | None | 🔴 High |
| Secrets Management | Environment variables / GitHub Secrets | 🟡 Medium |
| API Credentials | Stored in CI/CD secrets | 🟡 Medium |
| Network Security | NSG rules configurable | 🟢 Low |
| Audit Trail | Git commit history | 🟢 Low |
| Input Validation | JSON Schema + custom checks | 🟢 Low |

### 4.2 Credentials Required

| System | Credential Type | Storage Location |
|--------|-----------------|------------------|
| Palo Alto Firewall | API Key | GitHub Secrets |
| Azure | Service Principal (Client ID, Secret, Tenant, Subscription) | GitHub Secrets |
| NetBox | API Token | Environment Variable |
| Git | PAT or SSH Key | GitHub Secrets |

---

## 5. Known Limitations

### 5.1 Technical Limitations

1. **No Authentication/Authorization**
   - Portal is open access
   - No RBAC or approval workflows

2. **Local Terraform State**
   - Risk of state conflicts with concurrent deployments
   - No state locking mechanism
   - State loss = infrastructure drift

3. **Synchronous Processing**
   - No job queue for long-running deployments
   - User waits for Git operations to complete

4. **Single Point of Failure**
   - Single Flask instance
   - No horizontal scaling capability

5. **Limited Observability**
   - No centralized logging
   - No metrics/monitoring
   - No alerting

### 5.2 Operational Limitations

1. **No Drift Detection**
   - Changes made directly to firewall/Azure not detected

2. **No Emergency Bypass**
   - All changes must go through GitOps flow

3. **Limited Rollback**
   - Manual Git revert required
   - No one-click rollback in UI

---

## 6. Potential Questions & Answers

### Architecture & Scalability

**Q: How does this scale with 100+ concurrent users?**
> A: Currently it doesn't scale horizontally. The Flask app is single-threaded. For production, we'd need: load balancer, multiple instances, job queue (Celery/Redis), and database for request tracking.

**Q: What happens if deployment fails mid-way?**
> A: For firewall rules, PAN-OS commits are atomic. For Terraform, partial state is preserved and can be remediated with `terraform apply`. No automatic retry mechanism exists.

### Security

**Q: How are API credentials protected?**
> A: Stored in GitHub Secrets, injected as environment variables during CI/CD. Not exposed in logs. For production, recommend Azure Key Vault or HashiCorp Vault.

**Q: Is there approval workflow for firewall changes?**
> A: Currently relies on GitHub PR approval. No integration with ServiceNow/Jira. No multi-level approval.

**Q: How do you prevent unauthorized access?**
> A: Currently no authentication. Production would require SSO/SAML integration with corporate IdP.

### State Management

**Q: Why is Terraform state local?**
> A: Demo simplification. Production requires Azure Storage Account or Terraform Cloud with state locking.

**Q: How do you handle state conflicts?**
> A: Currently no mechanism. CI/CD runs sequentially per deployment, but concurrent deployments could conflict.

### Compliance & Audit

**Q: How do you track who made what change?**
> A: Git commit history includes requester name and ticket ID. Full audit trail in GitHub.

**Q: Is this PCI/SOC2 compliant?**
> A: Not currently. Would need: authentication, encryption at rest, access logging, separation of duties.

### Operations

**Q: What's the RTO/RPO?**
> A: Not defined. Git repo is the source of truth, so RPO is last commit. RTO depends on redeployment time.

**Q: How do you handle emergency changes?**
> A: Must go through Git. For true emergencies, direct firewall access with manual Git sync afterward.

---

## 7. Recommended Improvements

### Phase 1: Security Hardening (Immediate)

| Item | Priority | Effort |
|------|----------|--------|
| Add SSO/SAML authentication | 🔴 Critical | Medium |
| Migrate to remote Terraform state | 🔴 Critical | Low |
| Implement state locking | 🔴 Critical | Low |
| Add secrets management (Vault/Key Vault) | 🟡 High | Medium |

### Phase 2: Reliability & Scalability (Short-term)

| Item | Priority | Effort |
|------|----------|--------|
| Add job queue (Celery + Redis) | 🟡 High | Medium |
| Refactor app.py into Flask blueprints | 🟡 High | Medium |
| Add health checks and monitoring | 🟡 High | Low |
| Implement database for request tracking | 🟡 High | Medium |

### Phase 3: Enterprise Features (Medium-term)

| Item | Priority | Effort |
|------|----------|--------|
| ServiceNow/Jira integration | 🟢 Medium | High |
| Multi-level approval workflows | 🟢 Medium | High |
| Drift detection | 🟢 Medium | Medium |
| Cost estimation integration | 🟢 Medium | Medium |
| Rollback UI | 🟢 Medium | Medium |

### Phase 4: Production Readiness (Long-term)

| Item | Priority | Effort |
|------|----------|--------|
| Kubernetes deployment | 🔵 Low | High |
| Multi-region DR | 🔵 Low | High |
| Full observability stack | 🔵 Low | High |
| Compliance certifications | 🔵 Low | High |

---

## 8. Technology Stack Summary

| Layer | Technology | Purpose |
|-------|------------|---------|
| Frontend | HTML/CSS/JavaScript (Jinja2) | User interface |
| Backend | Python Flask | Web application |
| IaC - Firewall | PAN-OS XML API | Firewall configuration |
| IaC - Cloud | Terraform | Azure provisioning |
| CI/CD | GitHub Actions | Automation pipeline |
| Source Control | Git/GitHub | Version control |
| IPAM | NetBox | IP/Device inventory |

---

## 9. Repository Structure

```
palo_alto_gitops_firewall_rule_automation/
├── .github/workflows/          # CI/CD pipelines
│   ├── firewall-rule-automation.yml
│   └── azure-vm-automation.yml
├── firewall-rules/             # Firewall rule definitions (JSON)
├── schemas/                    # JSON validation schemas
├── scripts/                    # Deployment scripts
│   └── deploy_rule.py          # PAN-OS API deployment
├── self-service-portal/        # Flask web application
│   ├── app.py                  # Main application
│   ├── service_catalog/        # Service definitions
│   └── templates/              # HTML templates
├── terraform/
│   └── azure-vm/               # Azure VM Terraform templates
├── tests/                      # Validation tests
└── docs/                       # Documentation
```

---

## 10. Contact & Resources

- **Repository**: [GitHub Link]
- **Documentation**: This document + inline code comments
- **Demo Environment**: [Portal URL if available]

---

*Document Version: 1.0*
*Last Updated: February 2026*
