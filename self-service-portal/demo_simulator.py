#!/usr/bin/env python3
"""
Demo Simulator for Deployment Portal

Simulates realistic AWX + Ansible deployment log streams without
calling any external systems. Used when DEMO_MODE=true.
"""

import time
import random


def simulate_deployment(app_id: str, version: str, target: str,
                        vm_host: str = "", namespace: str = ""):
    """
    Simulates a realistic AWX + Ansible deployment log stream.
    Yields strings (log lines) and a final dict exactly like
    awx_client.stream_job_log() does.

    Timing feels real with short pauses between lines and longer
    pauses at key steps to simulate actual work happening.
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


def _pause(min_seconds=0.3, max_seconds=1.2):
    """Random pause between log lines"""
    time.sleep(random.uniform(min_seconds, max_seconds))


def _long_pause(min_seconds=2.0, max_seconds=4.0):
    """Longer pause for key steps"""
    time.sleep(random.uniform(min_seconds, max_seconds))


def _simulate_vm_deployment(app_id: str, version: str, vm_host: str):
    """Simulate VM deployment via SSH + git clone + systemd"""
    deployed_url = f"http://{vm_host}:5000"

    lines = [
        f"PLAY [Deploy {app_id} to {vm_host}] ****************************",
        "",
        "TASK [Gathering Facts] *****************************************",
    ]
    for line in lines:
        yield line
        _pause()

    yield f"ok: [{vm_host}]"
    _pause()
    yield ""
    _pause()

    yield "TASK [Ensure git and python3-pip are installed] ****************"
    _pause()
    yield f"ok: [{vm_host}] => (item=git)"
    _pause()
    yield f"ok: [{vm_host}] => (item=python3-pip)"
    _pause()
    yield ""
    _pause()

    yield "TASK [Clone / update application repository] *******************"
    _pause()
    yield f"  Cloning into '/opt/apps/{app_id}'..."
    _long_pause()
    yield f"changed: [{vm_host}]"
    _pause()
    yield ""
    _pause()

    yield "TASK [Install Python dependencies into virtualenv] **************"
    _pause()
    yield "  Collecting flask>=2.0"
    _pause(0.5, 1.0)
    yield "  Collecting requests"
    _pause()
    yield "  Collecting python-dotenv"
    _pause()
    yield "  Successfully installed all packages"
    _pause()
    yield f"changed: [{vm_host}]"
    _pause()
    yield ""
    _pause()

    yield "TASK [Render systemd service unit] ******************************"
    _pause()
    yield f"changed: [{vm_host}]"
    _pause()
    yield ""
    _pause()

    yield "TASK [Enable and restart systemd service] ***********************"
    _pause()
    yield f"changed: [{vm_host}]"
    _long_pause()
    yield ""
    _pause()

    yield "TASK [Wait for application health check] ************************"
    _pause()
    yield "  Waiting for port 5000..."
    _pause(1.0, 1.5)
    yield "  Attempt 1/10 — GET http://localhost:5000/health"
    _pause()
    yield "  HTTP 200 OK"
    _pause()
    yield f"ok: [{vm_host}]"
    _pause()
    yield ""
    _pause()

    yield "TASK [Report deployed URL] **************************************"
    _pause()
    yield f"ok: [{vm_host}] => " + "{"
    _pause()
    yield f'  "msg": "DEPLOYED_URL: {deployed_url}"'
    _pause()
    yield "}"
    _pause()
    yield ""
    _pause()

    yield "PLAY RECAP *****************************************************"
    _pause()
    yield f"{vm_host}   : ok=8  changed=4  unreachable=0  failed=0"
    _pause()
    yield ""
    _pause()
    yield f"DEPLOYED_URL: {deployed_url}"
    _pause()

    yield {'status': 'done', 'url': deployed_url}


def _simulate_openshift_deployment(app_id: str, version: str, namespace: str):
    """Simulate OpenShift deployment via oc + Route"""
    deployed_url = f"https://{app_id}.apps.ocp.azure.example.com"

    yield f"PLAY [Deploy {app_id} to OpenShift namespace {namespace}] ******"
    _pause()
    yield ""
    _pause()

    yield "TASK [Authenticate to OpenShift cluster] ***********************"
    _pause()
    yield "  Connecting to OCP API server..."
    _pause(1.0, 1.5)
    yield "ok: [localhost]"
    _pause()
    yield ""
    _pause()

    yield "TASK [Ensure namespace exists] *********************************"
    _pause()
    yield f"ok: [localhost] => namespace '{namespace}' already exists"
    _pause()
    yield ""
    _pause()

    yield "TASK [Fetch secret from Azure Key Vault] ***********************"
    _pause()
    yield f"  Reading secret '{app_id}-secret' from Key Vault..."
    _pause(0.8, 1.2)
    yield "ok: [localhost]"
    _pause()
    yield ""
    _pause()

    yield "TASK [Apply Kubernetes Secret] *********************************"
    _pause()
    yield "changed: [localhost]"
    _pause()
    yield ""
    _pause()

    yield "TASK [Apply Deployment manifest] *******************************"
    _pause()
    yield f"  Image: ghcr.io/your-org/{app_id}:{version}"
    _pause()
    yield "changed: [localhost]"
    _long_pause()
    yield ""
    _pause()

    yield "TASK [Apply Service manifest] **********************************"
    _pause()
    yield "changed: [localhost]"
    _pause()
    yield ""
    _pause()

    yield "TASK [Apply OpenShift Route] ***********************************"
    _pause()
    yield f"  Route host: {app_id}.apps.ocp.azure.example.com"
    _pause()
    yield "changed: [localhost]"
    _pause()
    yield ""
    _pause()

    yield "TASK [Wait for deployment rollout] *****************************"
    _pause()
    yield "  Waiting for pods to become ready..."
    _long_pause(2.5, 3.5)
    pod_suffix = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=5))
    yield f"  Pod {app_id}-7d9f8b-{pod_suffix} → Running"
    _pause()
    yield "  readyReplicas: 1"
    _pause()
    yield "ok: [localhost]"
    _pause()
    yield ""
    _pause()

    yield "TASK [Smoke test — GET /health] ********************************"
    _pause()
    yield f"  GET https://{app_id}.apps.ocp.azure.example.com/health"
    _pause()
    yield "  HTTP 200 OK"
    _pause()
    yield "ok: [localhost]"
    _pause()
    yield ""
    _pause()

    yield "TASK [Report deployed URL] *************************************"
    _pause()
    yield "ok: [localhost] => {"
    _pause()
    yield f'  "msg": "DEPLOYED_URL: {deployed_url}"'
    _pause()
    yield "}"
    _pause()
    yield ""
    _pause()

    yield "PLAY RECAP *****************************************************"
    _pause()
    yield "localhost   : ok=10  changed=5  unreachable=0  failed=0"
    _pause()
    yield ""
    _pause()
    yield f"DEPLOYED_URL: {deployed_url}"
    _pause()

    yield {'status': 'done', 'url': deployed_url}


def _simulate_aks_deployment(app_id: str, version: str, namespace: str):
    """Simulate AKS deployment via az CLI + Helm"""
    deployed_url = f"https://{app_id}.aks.azure.example.com"

    yield f"PLAY [Deploy {app_id} to AKS namespace {namespace}] ************"
    _pause()
    yield ""
    _pause()

    yield "TASK [Azure CLI login — service principal] *********************"
    _pause()
    yield "  Authenticating with Azure..."
    _pause(1.0, 1.5)
    yield "  [WARNING]: Do not store credentials in source control"
    _pause()
    yield "ok: [localhost]"
    _pause()
    yield ""
    _pause()

    yield "TASK [Fetch AKS credentials] ***********************************"
    _pause()
    yield "  az aks get-credentials --name nttdata-aks-poc ..."
    _pause()
    yield "  Merged cluster config into ~/.kube/config"
    _pause()
    yield "ok: [localhost]"
    _pause()
    yield ""
    _pause()

    yield "TASK [Ensure namespace exists] *********************************"
    _pause()
    yield f"changed: [localhost] => namespace '{namespace}' created"
    _pause()
    yield ""
    _pause()

    yield "TASK [Fetch secret from Azure Key Vault] ***********************"
    _pause()
    yield f"  Reading secret '{app_id}-secret' from Key Vault..."
    _pause(0.8, 1.2)
    yield "ok: [localhost]"
    _pause()
    yield ""
    _pause()

    yield "TASK [Create Kubernetes Secret] ********************************"
    _pause()
    yield "changed: [localhost]"
    _pause()
    yield ""
    _pause()

    yield "TASK [Helm upgrade --install] **********************************"
    _pause()
    yield f"  Release name:  {app_id}"
    _pause()
    yield "  Chart:         helm/app-chart"
    _pause()
    yield f"  Namespace:     {namespace}"
    _pause()
    yield f"  Image:         ghcr.io/your-org/{app_id}:{version}"
    _pause()
    yield "  "
    _long_pause(2.5, 3.5)
    yield f"  Release '{app_id}' has been upgraded. Happy Helming!"
    _pause()
    yield "changed: [localhost]"
    _pause()
    yield ""
    _pause()

    yield "TASK [Wait for deployment rollout] *****************************"
    _pause()
    yield "  Waiting for pods to become ready..."
    _long_pause(2.5, 3.5)
    pod_suffix = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=5))
    yield f"  Pod {app_id}-6cf9d-{pod_suffix} → Running"
    _pause()
    yield "  readyReplicas: 1"
    _pause()
    yield "ok: [localhost]"
    _pause()
    yield ""
    _pause()

    yield "TASK [Smoke test — GET /health] ********************************"
    _pause()
    yield f"  GET https://{app_id}.aks.azure.example.com/health"
    _pause()
    yield "  HTTP 200 OK"
    _pause()
    yield "ok: [localhost]"
    _pause()
    yield ""
    _pause()

    yield "TASK [Report deployed URL] *************************************"
    _pause()
    yield "ok: [localhost] => {"
    _pause()
    yield f'  "msg": "DEPLOYED_URL: {deployed_url}"'
    _pause()
    yield "}"
    _pause()
    yield ""
    _pause()

    yield "PLAY RECAP *****************************************************"
    _pause()
    yield "localhost   : ok=10  changed=5  unreachable=0  failed=0"
    _pause()
    yield ""
    _pause()
    yield f"DEPLOYED_URL: {deployed_url}"
    _pause()

    yield {'status': 'done', 'url': deployed_url}


def generate_job_id() -> str:
    """Generate a realistic-looking job ID"""
    return str(random.randint(10000, 99999))
