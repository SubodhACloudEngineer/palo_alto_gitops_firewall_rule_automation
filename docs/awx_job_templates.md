# AWX Job Templates — Application Deployment Portal

## Overview

This document describes three AWX job templates used by the self-service Flask portal to deploy applications to different infrastructure targets. The portal triggers these templates via the AWX REST API (`/api/v2/job_templates/<id>/launch/`) and streams job logs back to users in real-time.

**Key points:**

- The portal sends all deployment parameters as `extra_vars` at launch time — **do not hardcode** application-specific values in the templates
- All three playbooks live in this Git repository under `playbooks/`
- The portal parses job output looking for `DEPLOYED_URL: <url>` to extract the final application URL
- This is CD-only: container images are pre-built by CI pipelines; AWX only deploys them

---

## Prerequisites

Before creating the job templates, ensure the following are in place:

### AWX/AAP Version
- AWX Tower 21.x or later
- Ansible Automation Platform 2.x (if using Red Hat's commercial offering)

### AWX Project
Add this Git repository as an AWX Project:
1. Navigate to **Resources → Projects → Add**
2. Name: `GitOps Portal Playbooks`
3. Source Control Type: `Git`
4. Source Control URL: `https://github.com/your-org/palo_alto_gitops_firewall_rule_automation.git`
5. Source Control Branch: `main`
6. Update Revision on Launch: ✅ Enabled

### Execution Environment
The AWX execution environment must include these Ansible collections:

| Collection | Used By | Purpose |
|------------|---------|---------|
| `kubernetes.core` | OCP, AKS | K8s resource management |
| `redhat.openshift` | OCP | OpenShift Route and Auth |
| `community.kubernetes` | AKS | Helm deployments |
| `azure.azcollection` | OCP, AKS | Azure Key Vault, AKS auth |

If using a custom EE, add to `requirements.yml`:
```yaml
collections:
  - name: kubernetes.core
  - name: redhat.openshift
  - name: community.kubernetes
  - name: azure.azcollection
```

### Infrastructure Prerequisites

| Target | Requirement |
|--------|-------------|
| AKS | NGINX Ingress Controller installed (`ingress-nginx` namespace) |
| AKS | Azure Key Vault provisioned with secrets named `<app_name>-secret` |
| OCP | OpenShift service account token with namespace admin rights |
| OCP | Azure Key Vault provisioned with secrets named `<app_name>-secret` |
| VM | SSH access from AWX to target VMs |
| VM | Python 3.x and pip installed on target VMs |

---

## Template 1: Deploy-App-VM

Deploys a Flask application to a traditional VM by cloning the source from Git, installing dependencies in a virtualenv, and configuring a systemd service.

### Template Settings

| Setting | Value |
|---------|-------|
| **Name** | `Deploy-App-VM` |
| **Job Type** | Run |
| **Inventory** | See note below |
| **Project** | GitOps Portal Playbooks |
| **Playbook** | `playbooks/deploy_vm.yml` |
| **Credentials** | Machine Credential (SSH private key) |
| **Verbosity** | 1 (Normal) |
| **Extra Variables** | Leave empty — passed by portal at runtime |

**Inventory Note:** You have two options:
1. **Static inventory** — Create an inventory with your VM hostnames/IPs as hosts
2. **Dynamic inventory with limit** — Use a dynamic inventory and the portal's `vm_host` value maps to a host pattern

### Extra Variables Reference

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| `app_name` | string | Yes | Application name (becomes systemd service name) |
| `version` | string | Yes | Git tag or branch to checkout |
| `vm_host` | string | Yes | Target VM hostname or IP (must exist in inventory) |
| `repo_url` | string | No | Git repository URL (defaults to `https://github.com/your-org/<app_name>.git`) |
| `app_port` | integer | No | Application port (default: 5000) |

### Creation Steps

1. Navigate to **Resources → Templates → Add → Job Template**
2. Fill in the settings from the table above
3. Under **Credentials**, click **Select** and choose your SSH machine credential
4. Under **Inventory**, select or create your VM inventory
5. Leave **Extra Variables** empty (portal provides these)
6. Click **Save**

---

## Template 2: Deploy-App-OCP

Deploys a containerized Flask application to OpenShift (ARO) using the Kubernetes and OpenShift Ansible collections. Creates a Deployment, Service, and Route.

### Template Settings

| Setting | Value |
|---------|-------|
| **Name** | `Deploy-App-OCP` |
| **Job Type** | Run |
| **Inventory** | localhost (or any inventory with localhost) |
| **Project** | GitOps Portal Playbooks |
| **Playbook** | `playbooks/deploy_ocp.yml` |
| **Credentials** | OpenShift Credential (custom type — see below) |
| **Verbosity** | 1 (Normal) |
| **Extra Variables** | Leave empty — passed by portal at runtime |

### Environment Variables

Set these as environment variables in the job template:

| Variable | Example | Description |
|----------|---------|-------------|
| `OCP_HOST` | `https://api.aro-cluster.eastus.aroapp.io:6443` | OpenShift API endpoint |
| `OCP_TOKEN` | `sha256~xxxxx` | Service account token |
| `OCP_DOMAIN` | `apps.aro-cluster.eastus.aroapp.io` | Wildcard app domain |
| `AKV_NAME` | `mycompany-keyvault` | Azure Key Vault name for secrets |

### Extra Variables Reference

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| `app_name` | string | Yes | Application name |
| `image_tag` | string | Yes | Container image tag (pre-built by CI) |
| `namespace` | string | Yes | OpenShift project/namespace |
| `image_registry` | string | Yes | Container registry URL (e.g., `ghcr.io/your-org`) |

### Creating the OpenShift Custom Credential Type

Before creating the template, create a custom credential type for OpenShift:

1. Navigate to **Administration → Credential Types → Add**
2. **Name:** `OpenShift API Token`
3. **Input Configuration:**
```yaml
fields:
  - id: ocp_host
    type: string
    label: OpenShift API Host
  - id: ocp_token
    type: string
    label: OpenShift Token
    secret: true
  - id: ocp_domain
    type: string
    label: OpenShift Apps Domain
required:
  - ocp_host
  - ocp_token
  - ocp_domain
```
4. **Injector Configuration:**
```yaml
env:
  OCP_HOST: '{{ ocp_host }}'
  OCP_TOKEN: '{{ ocp_token }}'
  OCP_DOMAIN: '{{ ocp_domain }}'
```
5. Click **Save**

Then create a credential of this type:
1. Navigate to **Resources → Credentials → Add**
2. **Name:** `ARO Production`
3. **Credential Type:** `OpenShift API Token`
4. Fill in the OCP values
5. Click **Save**

### Creation Steps

1. Navigate to **Resources → Templates → Add → Job Template**
2. Fill in the settings from the table above
3. Under **Credentials**, add both:
   - Your OpenShift credential (custom type)
   - Azure credential (for Key Vault access)
4. Under **Variables**, add the `AKV_NAME` environment variable
5. Click **Save**

---

## Template 3: Deploy-App-AKS

Deploys a containerized Flask application to Azure Kubernetes Service (AKS) using Helm. The Helm chart is included in this repository at `helm/app-chart/`.

### Template Settings

| Setting | Value |
|---------|-------|
| **Name** | `Deploy-App-AKS` |
| **Job Type** | Run |
| **Inventory** | localhost |
| **Project** | GitOps Portal Playbooks |
| **Playbook** | `playbooks/deploy_aks.yml` |
| **Credentials** | Azure Service Principal (custom type — see below) |
| **Verbosity** | 1 (Normal) |
| **Extra Variables** | Leave empty — passed by portal at runtime |

### Environment Variables

Set these as environment variables in the job template:

| Variable | Example | Description |
|----------|---------|-------------|
| `AZ_CLIENT_ID` | `xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx` | Azure SP Application ID |
| `AZ_CLIENT_SECRET` | `xxxxx~xxxxx` | Azure SP Secret |
| `AZ_TENANT_ID` | `75d69b80-844c-4077-b28a-cf2b59cc5187` | Azure Tenant ID |
| `AKS_INGRESS_DOMAIN` | `aks.mycompany.com` | Wildcard domain for ingress |
| `AKV_NAME` | `mycompany-keyvault` | Azure Key Vault name |

### Extra Variables Reference

| Variable | Type | Required | Description |
|----------|------|----------|-------------|
| `app_name` | string | Yes | Application name |
| `image_tag` | string | Yes | Container image tag |
| `namespace` | string | Yes | Kubernetes namespace |
| `image_registry` | string | Yes | Container registry URL |
| `aks_cluster` | string | Yes | AKS cluster name |
| `aks_rg` | string | Yes | AKS resource group name |

### Creating the Azure SP Custom Credential Type

1. Navigate to **Administration → Credential Types → Add**
2. **Name:** `Azure Service Principal`
3. **Input Configuration:**
```yaml
fields:
  - id: az_client_id
    type: string
    label: Azure Client ID
  - id: az_client_secret
    type: string
    label: Azure Client Secret
    secret: true
  - id: az_tenant_id
    type: string
    label: Azure Tenant ID
required:
  - az_client_id
  - az_client_secret
  - az_tenant_id
```
4. **Injector Configuration:**
```yaml
env:
  AZ_CLIENT_ID: '{{ az_client_id }}'
  AZ_CLIENT_SECRET: '{{ az_client_secret }}'
  AZ_TENANT_ID: '{{ az_tenant_id }}'
```
5. Click **Save**

Then create a credential of this type with your Azure SP values.

### Creation Steps

1. Navigate to **Resources → Templates → Add → Job Template**
2. Fill in the settings from the table above
3. Under **Credentials**, add your Azure SP credential
4. Under **Variables**, add environment variables for `AKS_INGRESS_DOMAIN` and `AKV_NAME`
5. Click **Save**

---

## Testing the Templates

Before connecting the portal, test each template manually from the AWX UI.

### Test Deploy-App-VM

1. Navigate to **Resources → Templates → Deploy-App-VM**
2. Click the **Launch** button (rocket icon)
3. In the **Extra Variables** prompt, enter:
```json
{
  "app_name": "test-app",
  "version": "main",
  "vm_host": "webserver01.example.com"
}
```
4. Click **Launch**
5. Monitor the job output — look for `DEPLOYED_URL:` in the final tasks

### Test Deploy-App-OCP

1. Navigate to **Resources → Templates → Deploy-App-OCP**
2. Click **Launch**
3. Enter extra variables:
```json
{
  "app_name": "test-app",
  "image_tag": "v1.0.0",
  "namespace": "test-ns",
  "image_registry": "ghcr.io/your-org"
}
```
4. Click **Launch**
5. Verify the Route is created: `oc get route test-app -n test-ns`

### Test Deploy-App-AKS

1. Navigate to **Resources → Templates → Deploy-App-AKS**
2. Click **Launch**
3. Enter extra variables:
```json
{
  "app_name": "test-app",
  "image_tag": "v1.0.0",
  "namespace": "default",
  "image_registry": "ghcr.io/your-org",
  "aks_cluster": "my-aks-cluster",
  "aks_rg": "my-resource-group"
}
```
4. Click **Launch**
5. Verify the deployment: `kubectl get deployment test-app -n default`

---

## Troubleshooting

### Common Issues — All Templates

| Symptom | Cause | Solution |
|---------|-------|----------|
| Job fails immediately with "Template not found" | Portal using wrong template name | Template names must exactly match: `Deploy-App-VM`, `Deploy-App-OCP`, `Deploy-App-AKS` |
| Job hangs at "Pending" | No execution environment available | Check EE health, ensure required collections are installed |
| `DEPLOYED_URL:` not appearing in logs | Playbook failed before final task | Check earlier tasks for errors |

### Deploy-App-VM Issues

| Symptom | Cause | Solution |
|---------|-------|----------|
| "Host not found" error | `vm_host` not in inventory | Add the VM to inventory, or use a dynamic inventory that includes it |
| SSH connection refused | Wrong credentials or firewall | Verify SSH key works manually; check security groups |
| Git clone fails | Bad `repo_url` or credentials | Verify repo URL; add deploy key if repo is private |
| Health check times out | App not starting | SSH to VM, check `journalctl -u <app_name>` for errors |

### Deploy-App-OCP Issues

| Symptom | Cause | Solution |
|---------|-------|----------|
| "Unauthorized" from OpenShift | Token expired or invalid | Generate new SA token: `oc sa get-token <sa-name>` |
| Namespace creation fails | Insufficient permissions | SA needs `namespace-admin` or cluster-admin role |
| Route not accessible | Missing router/ingress | Verify OCP router is running: `oc get pods -n openshift-ingress` |
| Key Vault access denied | Azure credentials wrong | Verify SP has `Key Vault Secrets User` role on the vault |

### Deploy-App-AKS Issues

| Symptom | Cause | Solution |
|---------|-------|----------|
| `az login` fails | Bad SP credentials | Regenerate SP secret in Azure portal |
| `az aks get-credentials` fails | SP lacks AKS access | Assign `Azure Kubernetes Service Cluster User Role` to SP |
| Helm deployment fails | Chart syntax error | Run `helm lint ./helm/app-chart` locally |
| Ingress not working | NGINX controller missing | Install ingress-nginx: `helm install ingress-nginx ingress-nginx/ingress-nginx -n ingress-nginx` |
| Image pull error | Registry auth missing | Create image pull secret, reference in Helm values |

### Checking Job Logs

For any failed job:
1. Navigate to **Views → Jobs**
2. Click the failed job
3. Scroll through output or use **Search** to find error messages
4. Check the **Details** tab for environment and extra_vars used

### Portal Connection Issues

If the portal cannot trigger jobs:
1. Verify AWX host URL in portal's `.env` file
2. Test API connectivity: `curl -H "Authorization: Token <token>" https://awx.example.com/api/v2/ping/`
3. Verify the token has permission to launch job templates
4. Check AWX user has "Execute" permission on all three templates

---

## Portal Integration Reference

The portal (`self-service-portal/awx_client.py`) expects:

1. **Template names** — Must be exactly `Deploy-App-VM`, `Deploy-App-OCP`, `Deploy-App-AKS`
2. **DEPLOYED_URL output** — Playbooks must emit `debug: msg: "DEPLOYED_URL: <url>"` for the portal to capture the final URL
3. **Job status** — Portal polls `/api/v2/jobs/<id>/` and streams `/api/v2/jobs/<id>/stdout/`

Portal environment variables:
```bash
AWX_HOST=https://awx.internal.example.com
AWX_TOKEN=<your-token>
AWX_VERIFY_SSL=true
```

To create an API token for the portal:
1. Navigate to **Users → <your-user> → Tokens → Add**
2. **Scope:** Write
3. Copy the generated token to the portal's `.env` file
