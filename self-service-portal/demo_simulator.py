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
    Total simulation times: VM ~170-200s, OpenShift ~175-210s, AKS ~180-220s
    """
    if target == 'vm':
        yield from _simulate_vm_deployment(app_id, version, vm_host)
    elif target == 'openshift':
        yield from _simulate_openshift_deployment(app_id, version, namespace)
    elif target == 'aks':
        yield from _simulate_aks_deployment(app_id, version, namespace)
    else:
        yield f"ERROR: Unknown target '{target}'"
        yield {'status': 'failed', 'url': '', 'uses_argocd': False}


def simulate_awx_job(app_id: str, target: str, awx_base_url: str) -> dict:
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

    result = {
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
        "awx_url": f"/awx/jobs/{job_id}/output"
    }

    if target == "aks":
        result["argocd_url"] = f"https://localhost:8080/applications/{app_id}"
        result["uses_argocd"] = True
    else:
        result["argocd_url"] = None
        result["uses_argocd"] = False

    return result


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


def _simulate_vm_deployment(app_id: str, version: str, vm_host: str):
    """Simulate VM deployment via SSH + git clone + systemd"""
    deployed_url = "/app-proxy/"

    # PLAY header
    yield f"PLAY [Deploy {app_id} to {vm_host}] ****************************"
    time.sleep(random.uniform(0.4, 0.7))
    yield ""
    time.sleep(random.uniform(0.4, 0.7))

    # Gathering Facts (always slow)
    yield "TASK [Gathering Facts] *****************************************"
    time.sleep(random.uniform(6.0, 8.0))
    yield f"ok: [{vm_host}]"
    time.sleep(random.uniform(0.4, 0.7))
    yield ""
    time.sleep(random.uniform(0.4, 0.7))

    # Package install
    yield "TASK [Ensure git and python3-pip are installed] ****************"
    time.sleep(random.uniform(4.0, 6.0))
    yield f"ok: [{vm_host}] => (item=git)"
    time.sleep(random.uniform(1.0, 1.5))
    yield f"ok: [{vm_host}] => (item=python3-pip)"
    time.sleep(random.uniform(1.0, 1.5))
    yield f"ok: [{vm_host}] => (item=python3-venv)"
    time.sleep(random.uniform(0.4, 0.7))
    yield ""
    time.sleep(random.uniform(0.4, 0.7))

    # Git clone (slow operation)
    yield "TASK [Clone / update application repository] *******************"
    time.sleep(random.uniform(1.0, 1.5))
    yield f"  Cloning into '/opt/apps/{app_id}'..."
    time.sleep(random.uniform(10.0, 14.0))
    yield f"  remote: Enumerating objects: 847, done."
    time.sleep(random.uniform(0.8, 1.2))
    yield f"  remote: Counting objects: 100% (847/847), done."
    time.sleep(random.uniform(0.8, 1.2))
    yield f"  remote: Compressing objects: 100% (412/412), done."
    time.sleep(random.uniform(0.8, 1.2))
    yield f"  Receiving objects: 100% (847/847), 2.14 MiB | 8.42 MiB/s, done."
    time.sleep(random.uniform(0.8, 1.2))
    yield f"  Resolving deltas: 100% (389/389), done."
    time.sleep(random.uniform(0.8, 1.2))
    yield f"changed: [{vm_host}]"
    time.sleep(random.uniform(0.4, 0.7))
    yield ""
    time.sleep(random.uniform(0.4, 0.7))

    # Pip install (slow operation)
    yield "TASK [Install Python dependencies into virtualenv] **************"
    time.sleep(random.uniform(1.0, 1.5))
    yield "  Creating virtual environment..."
    time.sleep(random.uniform(2.0, 3.0))
    yield "  Collecting flask>=2.0"
    time.sleep(random.uniform(3.0, 4.0))
    yield "    Downloading Flask-3.0.0-py3-none-any.whl (99 kB)"
    time.sleep(random.uniform(0.8, 1.2))
    yield "  Collecting requests>=2.28"
    time.sleep(random.uniform(2.0, 3.0))
    yield "    Downloading requests-2.31.0-py3-none-any.whl (62 kB)"
    time.sleep(random.uniform(0.8, 1.2))
    yield "  Collecting python-dotenv"
    time.sleep(random.uniform(2.0, 3.0))
    yield "  Collecting gunicorn>=21.0"
    time.sleep(random.uniform(0.8, 1.2))
    yield "  Installing collected packages: MarkupSafe, Jinja2, itsdangerous, click, blinker, Werkzeug, flask, urllib3, charset-normalizer, certifi, idna, requests, python-dotenv, gunicorn"
    time.sleep(random.uniform(5.0, 7.0))
    yield "  Successfully installed all packages"
    time.sleep(random.uniform(0.8, 1.2))
    yield f"changed: [{vm_host}]"
    time.sleep(random.uniform(0.4, 0.7))
    yield ""
    time.sleep(random.uniform(0.4, 0.7))

    # Systemd service
    yield "TASK [Render systemd service unit] ******************************"
    time.sleep(random.uniform(3.0, 4.0))
    yield f"changed: [{vm_host}]"
    time.sleep(random.uniform(0.4, 0.7))
    yield ""
    time.sleep(random.uniform(0.4, 0.7))

    # Systemd restart (moderate wait)
    yield "TASK [Enable and restart systemd service] ***********************"
    time.sleep(random.uniform(5.0, 7.0))
    yield f"  Reloading systemd daemon..."
    time.sleep(random.uniform(2.0, 3.0))
    yield f"  Enabling {app_id}.service..."
    time.sleep(random.uniform(1.0, 2.0))
    yield f"  Restarting {app_id}.service..."
    time.sleep(random.uniform(3.0, 4.0))
    yield f"changed: [{vm_host}]"
    time.sleep(random.uniform(0.4, 0.7))
    yield ""
    time.sleep(random.uniform(0.4, 0.7))

    # Health check (wait for app to start)
    yield "TASK [Wait for application health check] ************************"
    time.sleep(random.uniform(0.8, 1.2))
    yield "  Waiting for port 5000..."
    time.sleep(random.uniform(2.0, 3.0))
    yield "  Attempt 1/10 — GET http://localhost:5000/health"
    time.sleep(random.uniform(5.0, 7.0))
    yield "  HTTP 200 OK"
    time.sleep(random.uniform(1.0, 1.5))
    yield f"ok: [{vm_host}]"
    time.sleep(random.uniform(0.4, 0.7))
    yield ""
    time.sleep(random.uniform(0.4, 0.7))

    # Report URL
    yield "TASK [Report deployed URL] **************************************"
    time.sleep(random.uniform(1.0, 1.5))
    yield f"ok: [{vm_host}] => " + "{"
    time.sleep(random.uniform(0.8, 1.2))
    yield f'  "msg": "DEPLOYED_URL: {deployed_url}"'
    time.sleep(random.uniform(0.8, 1.2))
    yield "}"
    time.sleep(random.uniform(0.4, 0.7))
    yield ""
    time.sleep(random.uniform(0.4, 0.7))

    # Play recap
    yield "PLAY RECAP *****************************************************"
    time.sleep(random.uniform(0.8, 1.2))
    yield f"{vm_host}   : ok=8  changed=4  unreachable=0  failed=0"
    time.sleep(random.uniform(0.4, 0.7))
    yield ""
    time.sleep(random.uniform(0.4, 0.7))
    yield f"DEPLOYED_URL: {deployed_url}"
    time.sleep(random.uniform(0.8, 1.2))

    yield {'status': 'done', 'url': deployed_url, 'uses_argocd': False}


def _simulate_openshift_deployment(app_id: str, version: str, namespace: str):
    """Simulate OpenShift deployment via oc + Route"""
    deployed_url = f"https://{app_id}.apps.ocp.azure.example.com"

    # PLAY header
    yield f"PLAY [Deploy {app_id} to OpenShift namespace {namespace}] ******"
    time.sleep(random.uniform(0.4, 0.7))
    yield ""
    time.sleep(random.uniform(0.4, 0.7))

    # Gathering Facts
    yield "TASK [Gathering Facts] *****************************************"
    time.sleep(random.uniform(6.0, 8.0))
    yield "ok: [localhost]"
    time.sleep(random.uniform(0.4, 0.7))
    yield ""
    time.sleep(random.uniform(0.4, 0.7))

    # OCP Authentication (slow)
    yield "TASK [Authenticate to OpenShift cluster] ***********************"
    time.sleep(random.uniform(8.0, 10.0))
    yield "  Connecting to OCP API server..."
    time.sleep(random.uniform(4.0, 6.0))
    yield "  Validating cluster certificate..."
    time.sleep(random.uniform(0.8, 1.2))
    yield "ok: [localhost]"
    time.sleep(random.uniform(0.4, 0.7))
    yield ""
    time.sleep(random.uniform(0.4, 0.7))

    # Namespace check
    yield "TASK [Ensure namespace exists] *********************************"
    time.sleep(random.uniform(3.0, 4.0))
    yield f"ok: [localhost] => namespace '{namespace}' already exists"
    time.sleep(random.uniform(0.4, 0.7))
    yield ""
    time.sleep(random.uniform(0.4, 0.7))

    # Key Vault fetch (slow)
    yield "TASK [Fetch secret from Azure Key Vault] ***********************"
    time.sleep(random.uniform(6.0, 8.0))
    yield f"  Reading secret '{app_id}-secret' from Key Vault..."
    time.sleep(random.uniform(4.0, 5.0))
    yield "  Secret retrieved successfully"
    time.sleep(random.uniform(0.8, 1.2))
    yield "ok: [localhost]"
    time.sleep(random.uniform(0.4, 0.7))
    yield ""
    time.sleep(random.uniform(0.4, 0.7))

    # Apply Secret
    yield "TASK [Apply Kubernetes Secret] *********************************"
    time.sleep(random.uniform(3.0, 4.0))
    yield f"  secret/{app_id}-secret configured"
    time.sleep(random.uniform(0.8, 1.2))
    yield "changed: [localhost]"
    time.sleep(random.uniform(0.4, 0.7))
    yield ""
    time.sleep(random.uniform(0.4, 0.7))

    # Apply Deployment (slow)
    yield "TASK [Apply Deployment manifest] *******************************"
    time.sleep(random.uniform(6.0, 8.0))
    yield f"  Image: ghcr.io/your-org/{app_id}:{version}"
    time.sleep(random.uniform(2.0, 3.0))
    yield f"  deployment.apps/{app_id} configured"
    time.sleep(random.uniform(3.0, 4.0))
    yield "changed: [localhost]"
    time.sleep(random.uniform(0.4, 0.7))
    yield ""
    time.sleep(random.uniform(0.4, 0.7))

    # Apply Service
    yield "TASK [Apply Service manifest] **********************************"
    time.sleep(random.uniform(3.0, 4.0))
    yield f"  service/{app_id} configured"
    time.sleep(random.uniform(0.8, 1.2))
    yield "changed: [localhost]"
    time.sleep(random.uniform(0.4, 0.7))
    yield ""
    time.sleep(random.uniform(0.4, 0.7))

    # Apply Route
    yield "TASK [Apply OpenShift Route] ***********************************"
    time.sleep(random.uniform(4.0, 5.0))
    yield f"  Route host: {app_id}.apps.ocp.azure.example.com"
    time.sleep(random.uniform(2.0, 3.0))
    yield f"  route.route.openshift.io/{app_id} configured"
    time.sleep(random.uniform(0.8, 1.2))
    yield "changed: [localhost]"
    time.sleep(random.uniform(0.4, 0.7))
    yield ""
    time.sleep(random.uniform(0.4, 0.7))

    # Wait for rollout (slow)
    yield "TASK [Wait for deployment rollout] *****************************"
    time.sleep(random.uniform(3.0, 4.0))
    yield "  Waiting for pods to become ready..."
    time.sleep(random.uniform(15.0, 20.0))
    yield "  Pod status: ContainerCreating"
    time.sleep(random.uniform(2.0, 3.0))
    pod_suffix = ''.join(random.choices('abcdefghijklmnopqrstuvwxyz0123456789', k=5))
    yield f"  Pod {app_id}-7d9f8b-{pod_suffix} → Running"
    time.sleep(random.uniform(2.0, 3.0))
    yield "  readyReplicas: 1"
    time.sleep(random.uniform(1.0, 2.0))
    yield "ok: [localhost]"
    time.sleep(random.uniform(0.4, 0.7))
    yield ""
    time.sleep(random.uniform(0.4, 0.7))

    # Smoke test
    yield "TASK [Smoke test — GET /health] ********************************"
    time.sleep(random.uniform(4.0, 5.0))
    yield f"  GET https://{app_id}.apps.ocp.azure.example.com/health"
    time.sleep(random.uniform(2.0, 3.0))
    yield "  HTTP 200 OK"
    time.sleep(random.uniform(1.0, 1.5))
    yield "ok: [localhost]"
    time.sleep(random.uniform(0.4, 0.7))
    yield ""
    time.sleep(random.uniform(0.4, 0.7))

    # Report URL
    yield "TASK [Report deployed URL] *************************************"
    time.sleep(random.uniform(1.0, 1.5))
    yield "ok: [localhost] => {"
    time.sleep(random.uniform(0.8, 1.2))
    yield f'  "msg": "DEPLOYED_URL: {deployed_url}"'
    time.sleep(random.uniform(0.8, 1.2))
    yield "}"
    time.sleep(random.uniform(0.4, 0.7))
    yield ""
    time.sleep(random.uniform(0.4, 0.7))

    # Play recap
    yield "PLAY RECAP *****************************************************"
    time.sleep(random.uniform(0.8, 1.2))
    yield "localhost   : ok=10  changed=5  unreachable=0  failed=0"
    time.sleep(random.uniform(0.4, 0.7))
    yield ""
    time.sleep(random.uniform(0.4, 0.7))
    yield f"DEPLOYED_URL: {deployed_url}"
    time.sleep(random.uniform(0.8, 1.2))

    yield {'status': 'done', 'url': deployed_url, 'uses_argocd': False}


def _simulate_aks_deployment(app_id: str, version: str, namespace: str):
    """Simulate AKS deployment via kubectl + ArgoCD sync output"""
    deployed_url = f"https://{app_id}.aks.azure.example.com"
    argocd_url = f"https://localhost:8080/applications/{app_id}"
    yield "$ kubectl get pods -n argocd"
    time.sleep(random.uniform(2.0, 3.0))
    yield "NAME                                             READY   STATUS    RESTARTS   AGE"
    yield "argocd-application-controller-0                  1/1     Running   0          2d"
    yield "argocd-applicationset-controller-b8f7c9d-xk2pq   1/1     Running   0          2d"
    yield "argocd-dex-server-6d8f9b7c4-m7rnx                1/1     Running   0          2d"
    yield "argocd-image-updater-7f6d8c9b5-p4qrs             1/1     Running   0          2d"
    yield "argocd-redis-7d9f8b6c5-j3kl2                     1/1     Running   0          2d"
    yield "argocd-repo-server-5c8d7f9b4-n6opq               1/1     Running   0          2d"
    yield "argocd-server-6b9f8c7d5-r8stu                    1/1     Running   0          2d"
    time.sleep(random.uniform(1.0, 1.5))
    yield ""
    yield "$ kubectl apply -f argocd-app.yaml"
    time.sleep(random.uniform(3.0, 4.0))
    yield f"application.argoproj.io/{app_id} configured"
    time.sleep(random.uniform(1.0, 1.5))
    yield ""
    yield "$ kubectl get applications -n argocd"
    time.sleep(random.uniform(2.0, 3.0))
    yield "NAME             SYNC STATUS   HEALTH STATUS   REVISION"
    yield f"{app_id}         OutOfSync     Healthy         main"
    time.sleep(random.uniform(1.0, 1.5))
    yield ""
    yield "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    yield "ArgoCD Sync Started"
    yield "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    time.sleep(random.uniform(2.0, 3.0))
    yield ""
    yield f"Application:     {app_id}"
    yield f"Destination:     aks_one  /  {namespace}"
    yield "Sync Policy:     Automated (image-updater)"
    yield f"Revision:        {version}"
    time.sleep(random.uniform(2.0, 3.0))
    yield ""
    yield "Syncing resources..."
    time.sleep(random.uniform(4.0, 5.0))
    yield f"  · ServiceAccount/{app_id}                    Synced"
    time.sleep(random.uniform(1.0, 1.5))
    yield f"  · ConfigMap/{app_id}-config                  Synced"
    time.sleep(random.uniform(1.0, 1.5))
    yield f"  · Secret/{app_id}-secret                     Synced"
    time.sleep(random.uniform(1.0, 1.5))
    yield f"  · Deployment/apps/{app_id}                   Synced"
    time.sleep(random.uniform(2.0, 3.0))
    yield f"  · Service/{app_id}                           Synced"
    time.sleep(random.uniform(1.0, 1.5))
    yield f"  · Ingress/{app_id}-ingress                   Synced"
    time.sleep(random.uniform(1.5, 2.0))
    yield ""
    yield "Waiting for rollout..."
    time.sleep(random.uniform(8.0, 12.0))
    yield ""
    yield f"  Pod {app_id}-7d9f4b-xk2pq   Pending  →  ContainerCreating"
    time.sleep(random.uniform(4.0, 6.0))
    yield f"  Pod {app_id}-7d9f4b-xk2pq   ContainerCreating  →  Running"
    time.sleep(random.uniform(3.0, 4.0))
    yield "  Readiness probe:  GET /health  →  HTTP 200 OK"
    time.sleep(random.uniform(2.0, 3.0))
    yield ""
    yield "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    yield "Sync Status:     Synced"
    yield "Health Status:   Healthy"
    yield f"Image:           ghcr.io/your-org/{app_id}:{version}"
    yield "Pods Ready:      1/1"
    yield "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    time.sleep(random.uniform(2.0, 3.0))
    yield ""
    yield "$ kubectl get applications -n argocd"
    time.sleep(random.uniform(2.0, 3.0))
    yield "NAME             SYNC STATUS   HEALTH STATUS   REVISION"
    yield f"{app_id}         Synced        Healthy         {version}"
    time.sleep(random.uniform(1.0, 1.5))
    yield ""
    yield f"ARGOCD_URL: {argocd_url}"
    yield f"DEPLOYED_URL: {deployed_url}"

    yield {
        'status': 'done',
        'url': deployed_url,
        'argocd_url': 'https://localhost:8080/applications/firewall-audit',
        'uses_argocd': True
    }
