# CLAUDE.md — Project Context & Working Notes

## Project Overview

**Palo Alto GitOps Firewall Rule Automation & Azure VM Provisioning**
A self-service portal for infrastructure automation using GitOps principles. Users submit requests via a web UI, changes are committed to Git, and CI/CD pipelines validate and deploy to Palo Alto firewalls or Azure cloud.

**Status:** Demo / PoC Phase
**Branch:** `claude/fix-netbox-vms-display-PE8Om`

---

## Repository Structure

```
palo_alto_gitops_firewall_rule_automation/
├── .github/workflows/
│   ├── firewall-rule-automation.yml    # Firewall CI/CD (9-stage pipeline)
│   ├── azure-vm-automation.yml         # Azure VM Terraform CI/CD
│   └── pr-validation.yml               # PR validation checks
├── firewall-rules/                     # Firewall rule definitions (JSON per rule)
├── schemas/
│   └── firewall-rule-schema.json       # JSON Schema for rule validation
├── scripts/
│   ├── deploy_rule.py                  # PAN-OS XML API deployment (replaces Ansible)
│   ├── validate_schema.py
│   ├── validate_security.py
│   ├── validate_network.py
│   ├── dry_run.py
│   ├── generate_report.py
│   └── verify_deployment.py
├── self-service-portal/
│   ├── app.py                          # Flask app (monolithic, 1400+ lines)
│   ├── awx_client.py                   # AWX REST API client (NEW)
│   ├── demo_simulator.py               # Demo mode deployment simulator (NEW)
│   ├── apps.json                       # Deployable apps config (NEW)
│   ├── env.example                     # Copy to .env to configure locally
│   ├── service_catalog/
│   │   ├── service_catalog_palo_alto_firewall.json
│   │   ├── azure_vm.json
│   │   └── vlan_provisioning.json
│   └── templates/
│       ├── base.html                   # Base template with shared CSS/nav (NEW)
│       ├── index.html                  # Dashboard - extends base.html
│       ├── service_catalog.html        # Service catalog - extends base.html
│       ├── firewall_rule_form.html     # Firewall form - extends base.html
│       ├── azure_vm_form.html          # Azure VM form - extends base.html
│       ├── request_details.html        # Request details - extends base.html
│       ├── request_form.html           # Generic form - extends base.html
│       ├── new_request.html            # VLAN request - extends base.html
│       ├── error.html                  # Error page - extends base.html
│       └── deploy/
│           └── deploy.html             # Deploy application form (NEW)
├── terraform/
│   └── azure-vm/
│       ├── main.tf                     # VMs, VNet, Subnet, NSG resources
│       ├── variables.tf
│       ├── outputs.tf
│       └── providers.tf
├── tests/
│   ├── test_schema_validation.py
│   ├── test_security_validation.py     # Metadata tests are advisory (warnings only)
│   └── test_network_validation.py
├── docs/
│   ├── platform-engineering-review.md # PE team review document
│   └── awx_job_templates.md           # AWX Tower configuration guide (NEW)
├── ansible/                            # Legacy - kept for reference, NOT used in CI/CD
├── playbooks/                          # AWX deployment playbooks (NEW)
│   ├── deploy_vm.yml                   # VM deployment (systemd service)
│   ├── deploy_ocp.yml                  # OpenShift deployment (Route + Service)
│   ├── deploy_aks.yml                  # AKS deployment (Helm-based)
│   └── templates/
│       └── systemd_service.j2          # systemd unit file template
├── helm/
│   └── app-chart/                      # Generic Flask app Helm chart (NEW)
│       ├── Chart.yaml
│       ├── values.yaml
│       └── templates/
│           ├── deployment.yaml
│           ├── service.yaml
│           └── ingress.yaml
├── requirements.txt
└── pytest.ini
```

---

## Services & Integrations

### Self-Service Portal (Flask)
- **Run:** `cd self-service-portal && python app.py`
- **Config:** Copy `env.example` to `.env` and set values
- **Key env vars:**
  ```
  NETBOX_URL=http://<netbox-host>:8000
  NETBOX_TOKEN=<netbox-api-token>
  GIT_USER_NAME=Self-Service Portal
  GIT_USER_EMAIL=portal@example.com
  ```
- Portal fetches VMs, devices, IPs, and subnets from **NetBox** for source/destination dropdowns
- On form submission, commits JSON rule files to Git and pushes to trigger CI/CD

### NetBox Integration
- Fetches both **Devices** (physical) and **Virtual Machines** from NetBox API
- Used to populate source/destination dropdowns in the firewall form
- Scripts: `sync_azure_to_netbox.py`, `sync_paloalto_to_netbox.py`

### Palo Alto Firewall Deployment
- **Script:** `scripts/deploy_rule.py`
- Uses **PAN-OS XML API** directly (NOT Ansible — Ansible was removed due to dependency issues)
- Supports `--dry-run` mode
- Required secrets: `PA_FIREWALL_IP`, `PA_USERNAME`, `PA_PASSWORD`, `PA_API_KEY`

### Azure VM Provisioning (Terraform)
- **Templates:** `terraform/azure-vm/`
- Resources deployed: Resource Group, VNet, Subnet, NSG, Public IPs, NICs, Linux/Windows VMs
- Authentication via Service Principal env vars: `ARM_CLIENT_ID`, `ARM_CLIENT_SECRET`, `ARM_TENANT_ID`, `ARM_SUBSCRIPTION_ID`
- **Azure Tenant:** `75d69b80-844c-4077-b28a-cf2b59cc5187`
- **Azure Subscription:** `8527d19f-1ff6-461c-a89e-da961a355bed`
- State is **local** (demo) — migrate to Azure Storage before production

### AWX Integration
- **Module:** `self-service-portal/awx_client.py`
- CD-only: image is pre-built in registry; AWX receives `image_tag` as extra_var and deploys only
- **Functions:**
  - `trigger_job(template_name, extra_vars)` — Resolves template name → id, POSTs to `/launch/`, returns `job_id` string; raises `ValueError` if not found, `RuntimeError` if launch fails
  - `get_job_status(job_id)` — Returns `{"status": "pending|waiting|running|successful|failed|canceled", "finished": bool, "elapsed": float}`
  - `stream_job_log(job_id)` — Generator; polls stdout with byte-range offsets (`Range: bytes=<offset>-`), yields log lines then final `{"status": "done"|"failed", "url": "..."}` dict; **never raises** — catches all exceptions, yields error as log line, then yields failed status
- **Configuration (env vars via python-dotenv):**
  ```
  AWX_HOST=https://awx.internal.example.com
  AWX_TOKEN=<token>
  AWX_VERIFY_SSL=true
  ```
- Uses `requests.Session()` at module level with `Authorization: Token <AWX_TOKEN>` header
- 10 second request timeout, byte-range polling every 2 seconds
- URL detection: scans logs for `DEPLOYED_URL: <url>` pattern
- Logging: DEBUG for all API calls, INFO for job launch success, ERROR for failures
- CLI: `python awx_client.py test|templates|trigger|status|logs`

### Deploy Application Routes
- **Routes in `app.py`:**
  - `GET /deploy` — Render deploy form (`templates/deploy/deploy.html`)
  - `POST /deploy` — Trigger AWX job, returns `{ "job_id": <id> }`
  - `GET /deploy/status/<job_id>` — SSE stream of job logs
- **POST /deploy payload:**
  ```json
  {
    "app_name": "my-app",
    "version": "v1.0.3-abc123",
    "target": "vm | openshift | aks",
    "vm_host": "webserver01.example.com",
    "namespace": "default"
  }
  ```
- **Validation:**
  - `app_name`, `version`, `target` are required
  - `target` must be one of: `vm`, `openshift`, `aks`
  - `vm_host` required when `target == "vm"`
  - `namespace` optional (default: `"default"`) for openshift/aks
- **AWX Job Templates:**
  - `vm` → `Deploy-App-VM` with `{ app_name, version, vm_host }`
  - `openshift` → `Deploy-App-OCP` with `{ app_name, image_tag, namespace, image_registry }`
  - `aks` → `Deploy-App-AKS` with `{ app_name, image_tag, namespace, image_registry, aks_cluster, aks_rg }`
- **Error responses:**
  - 400 — Missing/invalid field
  - 404 — AWX template not found (`ValueError`)
  - 502 — AWX job launch failed (`RuntimeError`)
- **In-memory storage:** `deploy_jobs[job_id]` stores `{ app_name, version, target, status, url, started_at }`
- **Environment variables:**
  ```
  IMAGE_REGISTRY=ghcr.io/your-org
  AKS_CLUSTER_NAME=your-aks-cluster-name
  AKS_RESOURCE_GROUP=your-aks-resource-group
  ```
- **SSE headers:** `Content-Type: text/event-stream`, `Cache-Control: no-cache`, `X-Accel-Buffering: no`

### Demo Mode
When `DEMO_MODE=true` in `.env`, the deployment portal simulates realistic deployments without calling AWX, GitHub, or any external systems.

**Configuration:**
```
DEMO_MODE=true
AWX_BASE_URL=http://172.20.47.61:30080
APP_PROXY_TARGET=http://127.0.0.1:5001
```

**Behavior:**
- `POST /deploy` generates a fake job_id (5-digit random number) and returns simulated AWX job info
- `GET /deploy/status/<job_id>` streams simulated Ansible log output from `demo_simulator.py`
- `GET /deploy/awx-status/<job_id>` returns simulated job status progression (pending → waiting → running → successful)
- All three targets (VM, OpenShift, AKS) have unique, authentic-looking log sequences
- Final `DEPLOYED_URL` is generated based on target type
- AKS deployments include ArgoCD sync simulation with `ARGOCD_URL` output
- For AKS + `DEMO_MODE=true`, POST `/deploy` also triggers background kubectl commands (`get pods`, `apply`, `get applications`) without blocking the API response
- AKS log stream now uses kubectl + ArgoCD sync style output instead of AWX/Ansible task format
- No "DEMO" or "SIMULATION" labels appear anywhere — output looks completely real

**Realistic Timing (~3 minutes per deployment):**
- VM deployments: ~170-200 seconds total
- OpenShift deployments: ~175-210 seconds total
- AKS deployments: ~60-90 seconds total
- All sleep values use `random.uniform()` for natural variation

**AWX Job Panel:**
The deploy UI shows an AWX Job Details panel with:
- Job ID and template name
- Launched by user and timestamp
- AWX console link → opens fake AWX job output page (`/awx/jobs/<job_id>/output`)
- ArgoCD console link (AKS deployments only)
- Status badge with progression: PENDING (0-5s) → WAITING (5-10s) → RUNNING (10s+) → DONE/FAILED

**Fake AWX Job Output Page:**
`GET /awx/jobs/<job_id>/output` renders a standalone page (`templates/awx_job_output.html`) that mimics the real AWX Tower job output interface:
- Dark navy theme matching AWX Tower (#1b1b21 background)
- Top navbar with "Ansible AWX" logo and version
- Status bar showing job status, elapsed timer, template, launched by
- Two-column layout: terminal output (70%) + details sidebar (30%)
- Terminal streams logs via SSE from `/deploy/status/<job_id>` (same endpoint as portal)
- ANSI colour simulation for Ansible output (green for ok, amber for changed, blue for TASK, etc.)
- Details sidebar shows job metadata and extra variables as JSON
- "Back to Portal" button links to `/deploy`

**ArgoCD Integration (AKS only):**
- AKS deployments simulate ArgoCD application sync after Helm upgrade
- `simulate_awx_job()` returns `uses_argocd: true` and `argocd_url` for AKS
- UI shows ArgoCD Console link in AWX Job Details panel
- Result banner includes both application URL and ArgoCD sync link

**Simulator Functions (`demo_simulator.py`):**
- `simulate_deployment(app_id, version, target, vm_host, namespace)` — Generator yielding log lines with realistic timing
- `simulate_awx_job(app_id, target, awx_base_url)` — Returns fake AWX job object with job_id, template name, AWX URL (`/awx/jobs/<job_id>/output`), and ArgoCD info for AKS
- `get_simulated_job_status(elapsed_seconds, target)` — Returns status based on elapsed time

**Use cases:**
- Demos to stakeholders without AWX infrastructure
- Development and testing of the portal UI
- Training new team members on the deployment workflow

**App Proxy (Reverse Proxy for Demo App):**
The portal includes a reverse proxy route (`/app-proxy/`) that proxies requests to the demo app running on `APP_PROXY_TARGET` (default: `http://127.0.0.1:5001`):
- `GET/POST /app-proxy/` and `/app-proxy/<path>` — Proxies all requests to the target app
- Rewrites absolute URLs in HTML responses to keep links on the portal domain
- VM deployments use `/app-proxy/` as the `DEPLOYED_URL` so "Open Application" stays on the portal
- Portal runs on port 5000, demo app runs on port 5001
- Browser URL shows `http://<portal-ip>:5000/app-proxy/` while content comes from localhost:5001

### AWX Deployment Playbooks
Three Ansible playbooks in `playbooks/` are executed by AWX job templates:

| Playbook | AWX Template | Target | Description |
|----------|--------------|--------|-------------|
| `deploy_vm.yml` | `Deploy-App-VM` | Traditional VMs | Git clone, pip venv, systemd service |
| `deploy_ocp.yml` | `Deploy-App-OCP` | OpenShift | k8s_auth, Deployment, Service, Route |
| `deploy_aks.yml` | `Deploy-App-AKS` | Azure AKS | az login, helm upgrade --install |

**Common extra_vars:**
- `app_name` — Application name (used for service name, paths, labels)
- `version` / `image_tag` — Image tag to deploy

**VM-specific vars:**
- `vm_host` — Target VM hostname (Ansible inventory host)
- `app_port` — Application port (default: 5000)
- `app_user` — Linux user to run service (default: appuser)

**OpenShift-specific vars:**
- `namespace` — OpenShift project/namespace
- `image_registry` — Container registry URL
- `ocp_api_url` — OpenShift API endpoint
- `key_vault_name` — Azure Key Vault for secrets

**AKS-specific vars:**
- `namespace` — Kubernetes namespace
- `image_registry` — Container registry URL
- `aks_cluster` — AKS cluster name
- `aks_rg` — AKS resource group

**DEPLOYED_URL output:** All playbooks emit `debug: msg: "DEPLOYED_URL: {{ url }}"` which `awx_client.py` parses to extract the deployed application URL.

**Required Ansible Collections:**
- `kubernetes.core` (OpenShift, AKS)
- `redhat.openshift` (OpenShift Routes)
- `azure.azcollection` (AKS authentication)

### Helm Chart (AKS Deployments)
`helm/app-chart/` is a generic Flask application chart used by `deploy_aks.yml`:

```yaml
# values.yaml defaults
image:
  repository: ghcr.io/your-org/app
  tag: latest
  pullPolicy: Always
service:
  port: 5000
ingress:
  enabled: true
  host: app.example.com
replicaCount: 1
existingSecret: ""  # Reference pre-created K8s secret for env vars
```

**Templates:**
- `deployment.yaml` — Deployment with health probes, optional secretRef
- `service.yaml` — ClusterIP service (port 80 → container port)
- `ingress.yaml` — Ingress with TLS (conditional on `.Values.ingress.enabled`)

**Usage:**
```bash
helm upgrade --install my-app ./helm/app-chart \
  --set image.repository=ghcr.io/org/app \
  --set image.tag=v1.0.0 \
  --set ingress.host=my-app.example.com \
  --set existingSecret=my-app-secrets \
  -n default
```

---

## CI/CD Pipelines

### Firewall Rule Automation (`.github/workflows/firewall-rule-automation.yml`)
Triggers on: push/PR to `main` affecting `firewall-rules/**`

| Stage | Job | Notes |
|-------|-----|-------|
| 1 | Detect Changed Rules | Only validates files changed in the PR/commit — NOT all rules |
| 2 | Validate JSON Schema | Against `schemas/firewall-rule-schema.json` |
| 3 | Security Policy Check | Custom security rules (e.g. no `any` to `any`) |
| 4 | Network Config Check | IP address/network validation |
| 5 | Dry Run Deployment | Calls `deploy_rule.py --dry-run` |
| 6 | Integration Tests | `pytest tests/` |
| 7 | Deploy to Staging | Requires `STAGING_FIREWALL_IP` secret |
| 8 | Deploy to Production | Only on `main` branch push |
| 9 | Notifications | Creates GitHub issue on failure |

**Important:** Template files are excluded from validation using `grep -v -i template | grep -v -i example | grep -v -i sample`

### Azure VM Automation (`.github/workflows/azure-vm-automation.yml`)
Triggers on: push/PR to `main` affecting `terraform/**`

Stages: Detect Changes → Terraform Format → Validate → Plan → Apply → (optional) Destroy

---

## Key Design Decisions

### Why Ansible was Replaced
Ansible was removed from CI/CD because of unreliable collection installs (`paloaltonetworks.panos`) in GitHub Actions. Replaced with `scripts/deploy_rule.py` which uses the PAN-OS XML API directly via `requests`.

### Metadata Tests are Advisory
`tests/test_security_validation.py` — the `TestMetadataCompliance` class uses `warnings.warn()` instead of `assert`. Tests pass even if `ticket_id`, `requested_by`, or `environment` are missing. This was changed because new rules submitted through the portal don't always include full metadata.

### Template Exclusion
`firewall-rules/template.json` exists as a reference. All CI/CD stages and test helpers explicitly exclude files matching `template`, `example`, or `sample` patterns.

### Firewall Rule Uniqueness
Rules must have unique `rule_name` values. The portal checks for duplicates before committing. A duplicate file (`allow_vm1_to_vm2.json`) was deleted to fix earlier test failures.

### Template Architecture
All HTML templates now extend `templates/base.html` using Jinja2 template inheritance:
- **`base.html`** — Contains all shared CSS, sidebar navigation, and defines blocks (`{% block title %}`, `{% block content %}`, `{% block extra_css %}`, `{% block extra_js %}`)
- **Sidebar navigation** — Links to Dashboard, Service Catalog, Firewall Rules, Azure VMs, Deploy App (placeholder), and external NetBox CMDB
- **Child templates** — Use `{% extends "base.html" %}` and override only the blocks they need
- **Page-specific CSS/JS** — Placed in `{% block extra_css %}` and `{% block extra_js %}` blocks

---

## GitHub Secrets Required

| Secret | Used By | Purpose |
|--------|---------|---------|
| `PA_API_KEY` | Firewall CI/CD | PAN-OS API authentication |
| `PA_USERNAME` | Firewall CI/CD | Firewall username |
| `PA_PASSWORD` | Firewall CI/CD | Firewall password |
| `STAGING_FIREWALL_IP` | Firewall CI/CD | Staging firewall hostname/IP |
| `PROD_FIREWALL_IP` | Firewall CI/CD | Production firewall hostname/IP |
| `ARM_CLIENT_ID` | Azure VM CI/CD | Azure Service Principal ID |
| `ARM_CLIENT_SECRET` | Azure VM CI/CD | Azure Service Principal Secret |
| `ARM_TENANT_ID` | Azure VM CI/CD | Azure Tenant ID |
| `ARM_SUBSCRIPTION_ID` | Azure VM CI/CD | Azure Subscription ID |

---

## Known Issues & Limitations

1. **No authentication** on the portal — open access (demo only)
2. **Local Terraform state** — risk of conflicts; must migrate to remote backend for production
3. **Monolithic `app.py`** — all routes, business logic, and integrations in one 1400+ line file
4. **No job queue** — Git/deployment operations are synchronous
5. **Azure Service Principal** — user cannot create SP due to insufficient Azure AD privileges; workaround: ask Azure admin or use existing SP credentials
6. **Ansible files kept** — `ansible/` directory is legacy/unused; kept for reference but not invoked anywhere in active CI/CD

---

## Running Locally

### Portal
```bash
cd self-service-portal
cp env.example .env
# Edit .env with your NetBox URL and token
pip install flask requests
python app.py
# Visit http://localhost:5001
```

### Tests
```bash
pip install -r requirements.txt
pytest tests/ -v
```

### Terraform (manual)
```bash
cd terraform/azure-vm
export ARM_CLIENT_ID="..."
export ARM_CLIENT_SECRET="..."
export ARM_TENANT_ID="75d69b80-844c-4077-b28a-cf2b59cc5187"
export ARM_SUBSCRIPTION_ID="8527d19f-1ff6-461c-a89e-da961a355bed"
terraform init
terraform plan -var-file="terraform.tfvars"
terraform apply -var-file="terraform.tfvars"
```

---

## Firewall Rule JSON Format

Rules live in `firewall-rules/*.json`. Required fields per `schemas/firewall-rule-schema.json`:

```json
{
  "rule_name": "Allow-Web-Access",
  "source_zone": ["trust"],
  "destination_zone": ["untrust"],
  "source_address": ["10.0.1.10/32"],
  "destination_address": ["any"],
  "application": ["web-browsing"],
  "service": ["application-default"],
  "action": "allow",
  "metadata": {
    "ticket_id": "SR-1001",
    "requested_by": "user@company.com",
    "environment": "production"
  }
}
```

---

## Pending / Future Work

- [ ] Migrate Terraform state to Azure Storage Account (remote backend)
- [ ] Add SSO/SAML authentication to portal
- [x] Refactor templates to use `base.html` (completed)
- [ ] Refactor `app.py` into Flask Blueprints (modular)
- [ ] Add job queue (Celery + Redis) for async deployments
- [ ] Integrate with ServiceNow or Jira for approval workflows
- [ ] Add drift detection for firewall and Azure resources
- [ ] Add centralised logging and monitoring (Azure Monitor / Datadog)
- [ ] Azure Service Principal — resolve insufficient privileges issue with Azure Admin

---

## Change Log (Session History)

| Change | Description |
|--------|-------------|
| NetBox VM display fix | Portal now fetches both Devices and Virtual Machines from NetBox |
| Replaced Ansible with API | `scripts/deploy_rule.py` uses PAN-OS XML API instead of Ansible |
| CI/CD scoped validation | Changed pipelines to validate only changed files, not all rules |
| Template exclusion | Added pattern exclusion for `template`, `example`, `sample` files |
| Metadata tests advisory | Changed `TestMetadataCompliance` assertions to `warnings.warn()` |
| Duplicate rule fix | Deleted duplicate `allow_vm1_to_vm2.json` (same `rule_name` as another file) |
| Azure VM feature | Added Terraform-based GitOps workflow for Azure VM provisioning |
| Terraform format fix | Fixed `terraform fmt` compliance issues in `main.tf` and `outputs.tf` |
| PE Review document | Created `docs/platform-engineering-review.md` for team meeting |
| Template refactoring | Created `base.html` with shared CSS/nav; all templates now extend it with Jinja2 blocks |
| AWX client module | Added `awx_client.py` with `trigger_job`, `get_job_status`, `stream_job_log` functions for AWX REST API |
| Deploy application routes | Added `/deploy`, `/deploy` (POST), `/deploy/status/<job_id>` routes for app deployment via AWX |
| Deploy template | Created `templates/deploy/deploy.html` with VM/OpenShift target cards, SSE log streaming, and portal-matching styles |
| AWX client rewrite | Fixed auth header (`Token` not `Bearer`), added `elapsed` to `get_job_status`, byte-range polling in `stream_job_log`, CD-only design |
| AWX client v2 | Refactored to use `requests.Session()`, `python-dotenv`, DEBUG logging for API calls, `stream_job_log` never raises (yields errors as log lines) |
| Deploy routes v2 | Added AKS target support, proper error handling (404/502), `started_at` timestamp, IMAGE_REGISTRY/AKS_CLUSTER_NAME/AKS_RESOURCE_GROUP env vars |
| Deploy template v2 | Rewrote `deploy.html` with 3 target cards (VM/OpenShift/AKS), conditional fields, SSE log streaming, status badges, result banners, reset functionality |
| AWX playbooks | Created `playbooks/deploy_vm.yml`, `deploy_ocp.yml`, `deploy_aks.yml` for VM, OpenShift, and AKS deployments with DEPLOYED_URL output |
| Helm chart | Created `helm/app-chart/` with Deployment, Service, Ingress templates for AKS deployments |
| AWX job templates doc | Created `docs/awx_job_templates.md` — handoff guide for AWX Tower configuration with custom credential types |
| Deploy template JS fix | Fixed non-responsive target cards: changed `{% block scripts %}` to `{% block extra_js %}` to match base.html; added `.service-card.selected` CSS |
| App selector & GitHub tags | Added `apps.json` config, app dropdown selector, auto-fetch latest GitHub release tag, `get_latest_github_tag()` in awx_client.py, `/deploy/app-info/<app_id>` route |
| Demo mode | Added `DEMO_MODE` flag and `demo_simulator.py` — simulates realistic AWX deployments without external calls for demos/testing |
| Demo mode v2 | Slower realistic timing (VM ~90-120s, OpenShift ~100-130s, AKS ~110-140s); AWX Job Details panel with status progression (pending→waiting→running→done); new `simulate_awx_job()`, `get_simulated_job_status()` functions; new `/deploy/awx-status/<job_id>` endpoint |
| Demo mode v3 | (1) AWX URL configurable via `AWX_BASE_URL` env var (default: `http://172.20.47.61:30080`); (2) Extended timing to ~3 minutes (VM ~170-200s, OpenShift ~175-210s, AKS ~180-220s) with `random.uniform()` for all sleeps; (3) AKS deployments now simulate ArgoCD sync with ArgoCD Console link in AWX panel and result banner |
| Demo mode v4 (AKS) | AKS-only demo flow now runs background kubectl commands at deploy trigger, streams kubectl/ArgoCD-style sync logs (60-90s), hides AWX Console row for AKS in deploy panel, and prioritizes ArgoCD deployment metadata/linking in the UI |
| Fake AWX page | Added `GET /awx/jobs/<job_id>/output` route and `templates/awx_job_output.html` — standalone page mimicking AWX Tower job output interface with dark theme, terminal output via SSE, ANSI colour simulation, elapsed timer, and job details sidebar |
| App proxy | Added `/app-proxy/` reverse proxy route to proxy requests to demo app on `APP_PROXY_TARGET` (default `http://127.0.0.1:5001`); VM deployments now use `/app-proxy/` as DEPLOYED_URL so "Open Application" stays on portal domain |
