#!/usr/bin/env python3
"""
Demo Simulator for Deployment Portal

Simulates realistic AWX + Ansible deployment log streams without
calling any external systems. Used when DEMO_MODE=true.
"""

import time
import random
from datetime import datetime, timezone


def simulate_deployment(app_id: str, version: str, target: str,
                        vm_host: str = "", namespace: str = ""):
    """
    Simulates a realistic AWX + Ansible deployment log stream.
    Yields strings (log lines) and a final dict exactly like
    awx_client.stream_job_log() does.

    Timing is realistic with appropriate pauses for each operation type.
    Total simulation times: VM ~90-120s, OpenShift ~100-130s, AKS ~110-140s
    """
    if target == 'vm':
        yield from _simulate_vm_deployment(app_id, version, vm_host)
    elif target == 'openshift':
        yield from _simulate_openshift_deployment(app_id, version, namespace)
    elif target == 'aks':
        yield from _simulate_aks_deployment(app_id, version, namespace)
    else:
        yield f"ERROR: Unknown target '{target}'"
        yield {'status': 'failed', 'url': ''}


def simulate_awx_job(app_id: str, target: str) -> dict:
    """
    Returns a realistic AWX job object.
    Called at POST /deploy time (before SSE stream starts).
    """
    target_to_template = {
        "vm":         {"id": 12, "name": "Deploy-App-VM"},
        "openshift":  {"id": 13, "name": "Deploy-App-OCP"},
        "aks":        {"id": 14, "name": "Deploy-App-AKS"},
    }
    template = target_to_template.get(target, {"id": 12, "name": "Deploy-App-VM"})
    job_id = str(random.randint(10000, 99999))

    return {
        "job_id":           job_id,
        "job_template_id":  template["id"],
        "job_template_name": template["name"],
        "status":           "pending",
        "created":          datetime.now(timezone.utc).isoformat(),
        "launched_by":      "nttdata-portal",
        "extra_vars": {
            "app_name":  app_id,
            "target":    target
        },
        "awx_url": f"https://awx.internal.nttdata.com/#/jobs/playbook/{job_id}/output"
    }


def get_simulated_job_status(elapsed_seconds: float, target: str) -> str:
    """
    Returns realistic AWX job status based on how long ago the job started.
    pending   →  0 to 5 seconds
    waiting   →  5 to 10 seconds
    running   →  10 seconds onwards
    successful → returned via final SSE event (not from this function)
    """
    if elapsed_seconds < 5:
        return "pending"
    elif elapsed_seconds < 10:
        return "waiting"
    else:
        return "running"


def generate_job_id() -> str:
    """Generate a realistic-looking job ID"""
    return str(random.randint(10000, 99999))


def _pause_line():
    """Standard pause between regular log lines"""
    time.sleep(random.uniform(0.6, 1.0))


def _pause_empty():
    """Pause between tasks (empty lines)"""
    time.sleep(0.3)


def _simulate_vm_deployment(app_id: str, version: str, vm_host: str):
    """Simulate VM deployment via SSH + git clone + systemd"""
    deployed_url = f"http://{vm_host}:5000"

    # PLAY header
    yield f"PLAY [Deploy {app_id} to {vm_host}] ****************************"
    _pause_empty()
    yield ""
    _pause_empty()

    # Gathering Facts (always slow)
    yield "TASK [Gathering Facts] *****************************************"
    time.sleep(random.uniform(3.5, 4.5))
    yield f"ok: [{vm_host}]"
    _pause_empty()
    yield ""
    _pause_empty()

    # Package install
    yield "TASK [Ensure git and python3-pip are installed] ****************"
    _pause_line()
    yield f"ok: [{vm_host}] => (item=git)"
    _pause_line()
    yield f"ok: [{vm_host}] => (item=python3-pip)"
    _pause_line()
    yield f"ok: [{vm_host}] => (item=python3-venv)"
    _pause_empty()
    yield ""
    _pause_empty()

    # Git clone (slow operation)
    yield "TASK [Clone / update application repository] *******************"
    _pause_line()
    yield f"  Cloning into '/opt/apps/{app_id}'..."
    time.sleep(random.uniform(5.5, 6.5))
    yield f"  remote: Enumerating objects: 847, done."
    time.sleep(0.5)
    yield f"  remote: Counting objects: 100% (847/847), done."
    time.sleep(0.5)
    yield f"  remote: Compressing objects: 100% (412/412), done."
    time.sleep(0.5)
    yield f"  Receiving objects: 100% (847/847), 2.14 MiB | 8.42 MiB/s, done."
    time.sleep(0.5)
    yield f"  Resolving deltas: 100% (389/389), done."
    time.sleep(0.5)
    yield f"changed: [{vm_host}]"
    _pause_empty()
    yield ""
    _pause_empty()

    # Pip install (slow operation)
    yield "TASK [Install Python dependencies into virtualenv] **************"
    _pause_line()
    yield "  Creating virtual environment..."
    time.sleep(random.uniform(2.0, 3.0))
    yield "  Collecting flask>=2.0"
    time.sleep(random.uniform(0.7, 0.9))
    yield "    Downloading Flask-3.0.0-py3-none-any.whl (99 kB)"
    time.sleep(random.uniform(0.7, 0.9))
    yield "  Collecting requests>=2.28"
    time.sleep(random.uniform(0.7, 0.9))
    yield "    Downloading requests-2.31.0-py3-none-any.whl (62 kB)"
    time.sleep(random.uniform(0.7, 0.9))
    yield "  Collecting python-dotenv"
    time.sleep(random.uniform(0.7, 0.9))
    yield "  Collecting gunicorn>=21.0"
    time.sleep(random.uniform(0.7, 0.9))
    yield "  Installing collected packages: MarkupSafe, Jinja2, itsdangerous, click, blinker, Werkzeug, flask, urllib3, charset-normalizer, certifi, idna, requests, python-dotenv, gunicorn"
    time.sleep(random.uniform(2.0, 3.0))
    yield "  Successfully installed all packages"
    _pause_line()
    yield f"changed: [{vm_host}]"
    _pause_empty()
    yield ""
    _pause_empty()

    # Systemd service
    yield "TASK [Render systemd service unit] ******************************"
    _pause_line()
    yield f"changed: [{vm_host}]"
    _pause_empty()
    yield ""
    _pause_empty()

    # Systemd restart (moderate wait)
    yield "TASK [Enable and restart systemd service] ***********************"
    _pause_line()
    yield f"  Reloading systemd daemon..."
    time.sleep(random.uniform(1.0, 1.5))
    yield f"  Enabling {app_id}.service..."
    time.sleep(random.uniform(0.5, 0.8))
    yield f"  Restarting {app_id}.service..."
    time.sleep(random.uniform(2.5, 3.5))
    yield f"changed: [{vm_host}]"
    _pause_empty()
    yield ""
    _pause_empty()

    # Health check (wait for app to start)
    yield "TASK [Wait for application health check] ************************"
    _pause_line()
    yield "  Waiting for port 5000..."
    time.sleep(random.uniform(2.5, 3.5))
    yield "  Attempt 1/10 — GET http://localhost:5000/health"
    time.sleep(random.uniform(0.4, 0.6))
    yield "  HTTP 200 OK"
    _pause_line()
    yield f"ok: [{vm_host}]"
    _pause_empty()
    yield ""
    _pause_empty()

    # Report URL
    yield "TASK [Report deployed URL] **************************************"
    _pause_line()
    yield f"ok: [{vm_host}] => " + "{"
    _pause_line()
    yield f'  "msg": "DEPLOYED_URL: {deployed_url}"'
    _pause_line()
    yield "}"
    _pause_empty()
    yield ""
    _pause_empty()

    # Play recap
    yield "PLAY RECAP *****************************************************"
    _pause_line()
    yield f"{vm_host}   : ok=8  changed=4  unreachable=0  failed=0"
    _pause_empty()
    yield ""
    _pause_empty()
    yield f"DEPLOYED_URL: {deployed_url}"
    _pause_line()

    yield {'status': 'done', 'url': deployed_url}


def _simulate_openshift_deployment(app_id: str, version: str, namespace: str):
    """Simulate OpenShift deployment via oc + Route"""
    deployed_url = f"https://{app_id}.apps.ocp.azure.example.com"

    # PLAY header
    yield f"PLAY [Deploy {app_id} to OpenShift namespace {namespace}] ******"
    _pause_empty()
    yield ""
    _pause_empty()

    # Gathering Facts
    yield "TASK [Gathering Facts] *****************************************"
    time.sleep(random.uniform(3.5, 4.5))
    yield "ok: [localhost]"
    _pause_empty()
    yield ""
    _pause_empty()

    # OCP Authentication (slow)
    yield "TASK [Authenticate to OpenShift cluster] ***********************"
    _pause_line()
    yield "  Connecting to OCP API server..."
    time.sleep(random.uniform(3.5, 4.5))
    yield "  Validating cluster certificate..."
    time.sleep(random.uniform(0.5, 0.8))
    yield "ok: [localhost]"
    _pause_empty()
    yield ""
    _pause_empty()

    # Namespace check
    yield "TASK [Ensure namespace exists] *********************************"
    _pause_line()
    yield f"ok: [localhost] => namespace '{namespace}' already exists"
    _pause_empty()
    yield ""
    _pause_empty()

    # Key Vault fetch (slow)
    yield "TASK [Fetch secret from Azure Key Vault] ***********************"
    _pause_line()
    yield f"  Reading secret '{app_id}-secret' from Key Vault..."
    time.sleep(random.uniform(2.5, 3.5))
    yield "  Secret retrieved successfully"
    _pause_line()
    yield "ok: [localhost]"
    _pause_empty()
    yield ""
    _pause_empty()

    # Apply Secret
    yield "TASK [Apply Kubernetes Secret] *********************************"
    _pause_line()
    yield f"  secret/{app_id}-secret configured"
    _pause_line()
    yield "changed: [localhost]"
    _pause_empty()
    yield ""
    _pause_empty()

    # Apply Deployment (slow)
    yield "TASK [Apply Deployment manifest] *******************************"
    _pause_line()
    yield f"  Image: ghcr.io/your-org/{app_id}:{version}"
    time.sleep(random.uniform(3.5, 4.5))
    yield f"  deployment.apps/{app_id} configured"
    _pause_line()
    yield "changed: [localhost]"
    _pause_empty()
    yield ""
    _pause_empty()

    # Apply Service
    yield "TASK [Apply Service manifest] **********************************"
    _pause_line()
    yield f"  service/{app_id} configured"
    _pause_line()
    yield "changed: [localhost]"
    _pause_empty()
    yield ""
    _pause_empty()

    # Apply Route
    yield "TASK [Apply OpenShift Route] ***********************************"
    _pause_line()
    yield f"  Route host: {app_id}.apps.ocp.azure.example.com"
    _pause_line()
    yield f"  route.route.openshift.io/{app_id} configured"
    _pause_line()
    yield "changed: [localhost]"
    _pause_empty()
    yield ""
    _pause_empty()

    # Wait for rollout (slow)
    yield "TASK [Wait for deployment rollout] *****************************"
    _pause_line()
    yield "  Waiting for pods to become ready..."
    time.sleep(random.uniform(4.0, 5.0))
    yield "  Pod status: ContainerCreating"
    time.sleep(random.uniform(3.0, 4.0))
    pod_suffix = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=5))
    yield f"  Pod {app_id}-7d9f8b-{pod_suffix} → Running"
    time.sleep(random.uniform(0.8, 1.2))
    yield "  readyReplicas: 1"
    time.sleep(random.uniform(0.4, 0.6))
    yield "ok: [localhost]"
    _pause_empty()
    yield ""
    _pause_empty()

    # Smoke test
    yield "TASK [Smoke test — GET /health] ********************************"
    _pause_line()
    yield f"  GET https://{app_id}.apps.ocp.azure.example.com/health"
    time.sleep(random.uniform(1.5, 2.5))
    yield "  HTTP 200 OK"
    _pause_line()
    yield "ok: [localhost]"
    _pause_empty()
    yield ""
    _pause_empty()

    # Report URL
    yield "TASK [Report deployed URL] *************************************"
    _pause_line()
    yield "ok: [localhost] => {"
    _pause_line()
    yield f'  "msg": "DEPLOYED_URL: {deployed_url}"'
    _pause_line()
    yield "}"
    _pause_empty()
    yield ""
    _pause_empty()

    # Play recap
    yield "PLAY RECAP *****************************************************"
    _pause_line()
    yield "localhost   : ok=10  changed=5  unreachable=0  failed=0"
    _pause_empty()
    yield ""
    _pause_empty()
    yield f"DEPLOYED_URL: {deployed_url}"
    _pause_line()

    yield {'status': 'done', 'url': deployed_url}


def _simulate_aks_deployment(app_id: str, version: str, namespace: str):
    """Simulate AKS deployment via az CLI + Helm"""
    deployed_url = f"https://{app_id}.aks.azure.example.com"

    # PLAY header
    yield f"PLAY [Deploy {app_id} to AKS namespace {namespace}] ************"
    _pause_empty()
    yield ""
    _pause_empty()

    # Gathering Facts
    yield "TASK [Gathering Facts] *****************************************"
    time.sleep(random.uniform(3.5, 4.5))
    yield "ok: [localhost]"
    _pause_empty()
    yield ""
    _pause_empty()

    # Azure CLI login (slow)
    yield "TASK [Azure CLI login — service principal] *********************"
    _pause_line()
    yield "  Authenticating with Azure..."
    time.sleep(random.uniform(4.5, 5.5))
    yield "  [WARNING]: Do not store credentials in source control"
    _pause_line()
    yield "  Login successful. Tenant: 75d69b80-844c-4077-b28a-cf2b59cc5187"
    _pause_line()
    yield "ok: [localhost]"
    _pause_empty()
    yield ""
    _pause_empty()

    # AKS credentials (slow)
    yield "TASK [Fetch AKS credentials] ***********************************"
    _pause_line()
    yield "  az aks get-credentials --name nttdata-aks-poc --resource-group nttdata-rg"
    time.sleep(random.uniform(3.5, 4.5))
    yield "  Merged \"nttdata-aks-poc\" as current context in ~/.kube/config"
    _pause_line()
    yield "ok: [localhost]"
    _pause_empty()
    yield ""
    _pause_empty()

    # Namespace
    yield "TASK [Ensure namespace exists] *********************************"
    _pause_line()
    yield f"  namespace/{namespace} created"
    _pause_line()
    yield f"changed: [localhost] => namespace '{namespace}' created"
    _pause_empty()
    yield ""
    _pause_empty()

    # Key Vault fetch (slow)
    yield "TASK [Fetch secret from Azure Key Vault] ***********************"
    _pause_line()
    yield f"  Reading secret '{app_id}-secret' from Key Vault..."
    time.sleep(random.uniform(2.5, 3.5))
    yield "  Secret retrieved successfully"
    _pause_line()
    yield "ok: [localhost]"
    _pause_empty()
    yield ""
    _pause_empty()

    # Create Secret
    yield "TASK [Create Kubernetes Secret] ********************************"
    _pause_line()
    yield f"  secret/{app_id}-secret created"
    _pause_line()
    yield "changed: [localhost]"
    _pause_empty()
    yield ""
    _pause_empty()

    # Helm upgrade (slow)
    yield "TASK [Helm upgrade --install] **********************************"
    _pause_line()
    yield f"  Release name:  {app_id}"
    time.sleep(random.uniform(0.8, 1.2))
    yield "  Chart:         helm/app-chart"
    time.sleep(random.uniform(0.8, 1.2))
    yield f"  Namespace:     {namespace}"
    time.sleep(random.uniform(0.8, 1.2))
    yield f"  Image:         ghcr.io/your-org/{app_id}:{version}"
    time.sleep(random.uniform(0.8, 1.2))
    yield "  "
    yield "  Upgrading release..."
    time.sleep(random.uniform(4.0, 5.0))
    yield "  Creating deployment..."
    time.sleep(random.uniform(2.0, 3.0))
    yield f"  Release '{app_id}' has been upgraded. Happy Helming!"
    _pause_line()
    yield "changed: [localhost]"
    _pause_empty()
    yield ""
    _pause_empty()

    # Wait for rollout (slow)
    yield "TASK [Wait for deployment rollout] *****************************"
    _pause_line()
    yield "  Waiting for pods to become ready..."
    time.sleep(random.uniform(4.0, 5.0))
    yield "  Pod status: ContainerCreating"
    time.sleep(random.uniform(3.0, 4.0))
    pod_suffix = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=5))
    yield f"  Pod {app_id}-6cf9d-{pod_suffix} → Running"
    time.sleep(random.uniform(0.8, 1.2))
    yield "  readyReplicas: 1"
    time.sleep(random.uniform(0.4, 0.6))
    yield "ok: [localhost]"
    _pause_empty()
    yield ""
    _pause_empty()

    # Smoke test
    yield "TASK [Smoke test — GET /health] ********************************"
    _pause_line()
    yield f"  GET https://{app_id}.aks.azure.example.com/health"
    time.sleep(random.uniform(1.5, 2.5))
    yield "  HTTP 200 OK"
    _pause_line()
    yield "ok: [localhost]"
    _pause_empty()
    yield ""
    _pause_empty()

    # Report URL
    yield "TASK [Report deployed URL] *************************************"
    _pause_line()
    yield "ok: [localhost] => {"
    _pause_line()
    yield f'  "msg": "DEPLOYED_URL: {deployed_url}"'
    _pause_line()
    yield "}"
    _pause_empty()
    yield ""
    _pause_empty()

    # Play recap
    yield "PLAY RECAP *****************************************************"
    _pause_line()
    yield "localhost   : ok=10  changed=5  unreachable=0  failed=0"
    _pause_empty()
    yield ""
    _pause_empty()
    yield f"DEPLOYED_URL: {deployed_url}"
    _pause_line()

    yield {'status': 'done', 'url': deployed_url}
