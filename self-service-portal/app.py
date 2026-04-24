#!/usr/bin/env python3
"""
Self-Service Infrastructure Portal with NetBox Integration
Palo Alto Firewall Rule Provisioning via GitOps
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for, Response, stream_with_context
import subprocess
import json
import threading
import random
import time
import math
from datetime import datetime
import os
import glob
import requests as req_lib
from urllib3.exceptions import InsecureRequestWarning

# AWX client for job template automation
import awx_client
import demo_simulator

# Disable SSL warnings
req_lib.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

app = Flask(__name__)

# ============================================
# CONFIGURATION
# ============================================

# Load .env file if it exists
def load_env_file():
    """Load environment variables from .env file"""
    env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    # Only set if not already in environment
                    if key.strip() not in os.environ:
                        os.environ[key.strip()] = value.strip().strip('"').strip("'")

load_env_file()

# Base paths - relative to the project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTAL_DIR = os.path.dirname(os.path.abspath(__file__))
SERVICE_CATALOG_PATH = os.path.join(PORTAL_DIR, "service_catalog")
FIREWALL_RULES_PATH = os.path.join(BASE_DIR, "firewall-rules")
PLAYBOOKS_PATH = os.path.join(BASE_DIR, "playbooks")
TERRAFORM_TEMPLATES_PATH = os.path.join(BASE_DIR, "terraform", "azure-vm")
TERRAFORM_DEPLOYMENTS_PATH = os.path.join(BASE_DIR, "terraform-deployments")

# NetBox Configuration
# Priority: Environment variable > .env file > None
NETBOX_URL = os.environ.get("NETBOX_URL", "http://localhost:8000")
NETBOX_TOKEN = os.environ.get("NETBOX_TOKEN")

# Git configuration for firewall rules
GIT_REPO_PATH = BASE_DIR
GIT_USER_NAME = os.environ.get("GIT_USER_NAME", "Self-Service Portal")
GIT_USER_EMAIL = os.environ.get("GIT_USER_EMAIL", "portal@example.com")

# Demo mode - simulates deployments without calling external systems
DEMO_MODE = os.environ.get("DEMO_MODE", "false").lower() == "true"

# AWX base URL for job links
AWX_BASE_URL = os.environ.get("AWX_BASE_URL", "http://172.20.47.61:30080")

# App proxy target for demo app
APP_PROXY_TARGET = os.environ.get("APP_PROXY_TARGET", "http://127.0.0.1:5001")

# In-memory storage for requests
service_requests = []
request_counter = 1000

# In-memory storage for deploy jobs
deploy_jobs = {}


def _build_vm_monitoring_links(app_id):
    """Build InfluxDB and Grafana URLs for VM monitoring."""
    influx_base_url = os.environ.get("INFLUX_BASE_URL", "http://localhost:8086").rstrip('/')
    influx_org_id = os.environ.get("INFLUX_ORG_ID", "17953261761d6a38")
    influx_bucket = os.environ.get("INFLUX_BUCKET", "vm_resource_metrics")

    grafana_base_url = os.environ.get("GRAFANA_BASE_URL", "http://localhost:3000").rstrip('/')
    grafana_dashboard_uid = os.environ.get("GRAFANA_VM_DASHBOARD_UID", "").strip()

    if grafana_dashboard_uid:
        grafana_url = f"{grafana_base_url}/d/{grafana_dashboard_uid}?var-app_id={app_id}"
    else:
        grafana_url = f"{grafana_base_url}/dashboards"

    return {
        "influxdb_url": f"{influx_base_url}/orgs/{influx_org_id}",
        "grafana_url": grafana_url,
        "influx_bucket": influx_bucket,
        "influx_org_id": influx_org_id
    }


def _stream_vm_metrics_to_influx(app_id, vm_host, influx_bucket, influx_org_id):
    """
    Stream synthetic VM KPIs to InfluxDB for demo graphs.
    Best-effort only: errors are logged and ignored.
    """
    influx_base_url = os.environ.get("INFLUX_BASE_URL", "http://localhost:8086").rstrip('/')
    influx_token = os.environ.get("INFLUX_TOKEN", "").strip()
    write_url = f"{influx_base_url}/api/v2/write?org={influx_org_id}&bucket={influx_bucket}&precision=s"

    headers = {"Content-Type": "text/plain; charset=utf-8"}
    if influx_token:
        headers["Authorization"] = f"Token {influx_token}"

    for step in range(45):  # ~90 seconds at 2s intervals
        phase = (step / 45.0) * (2 * math.pi)
        cpu = max(1.0, min(95.0, 42 + 25 * math.sin(phase) + random.uniform(-6, 6)))
        memory = max(5.0, min(98.0, 55 + 18 * math.sin(phase * 0.7 + 1.2) + random.uniform(-4, 4)))
        disk_iops = max(20.0, 160 + 70 * math.sin(phase * 1.4 + 0.5) + random.uniform(-20, 20))
        net_kbps = max(50.0, 350 + 180 * math.sin(phase * 1.8 + 0.8) + random.uniform(-45, 45))

        payload = (
            f"vm_resource,app_id={app_id},vm_host={vm_host} "
            f"cpu={cpu:.2f},memory={memory:.2f},disk_iops={disk_iops:.2f},net_kbps={net_kbps:.2f}"
        )

        try:
            req_lib.post(write_url, headers=headers, data=payload, timeout=3)
        except Exception as e:
            app.logger.warning(f"Failed to push VM metrics to InfluxDB: {e}")

        time.sleep(2)


# ============================================
# NETBOX API CLIENT
# ============================================

class NetBoxClient:
    """Client for interacting with NetBox API"""

    def __init__(self, url, token):
        self.url = url.rstrip('/')
        self.token = token
        self.configured = bool(token)
        self.last_error = None
        self.headers = {
            'Authorization': f'Token {token}' if token else '',
            'Accept': 'application/json',
            'Content-Type': 'application/json'
        }

    def get(self, endpoint, params=None):
        """Make GET request to NetBox"""
        self.last_error = None

        if not self.configured:
            self.last_error = "NetBox token not configured. Please set NETBOX_TOKEN in .env file."
            print(f"NetBox API error: {self.last_error}")
            return {'results': [], 'count': 0, 'error': self.last_error}

        url = f"{self.url}{endpoint}"
        try:
            response = req_lib.get(url, headers=self.headers, params=params, verify=False, timeout=10)
            response.raise_for_status()
            return response.json()
        except req_lib.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                self.last_error = "Authentication failed. Check your NETBOX_TOKEN in .env file."
            elif e.response.status_code == 404:
                self.last_error = f"NetBox endpoint not found: {endpoint}"
            else:
                self.last_error = f"HTTP {e.response.status_code}: {str(e)}"
            print(f"NetBox API error: {self.last_error}")
            return {'results': [], 'count': 0, 'error': self.last_error}
        except req_lib.exceptions.ConnectionError:
            self.last_error = f"Cannot connect to NetBox at {self.url}. Is NetBox running?"
            print(f"NetBox API error: {self.last_error}")
            return {'results': [], 'count': 0, 'error': self.last_error}
        except Exception as e:
            self.last_error = str(e)
            print(f"NetBox API error: {self.last_error}")
            return {'results': [], 'count': 0, 'error': self.last_error}

    def get_devices(self, site=None, role=None, exclude_role=None):
        """Get devices from NetBox"""
        params = {}
        if site:
            params['site'] = site
        if role:
            params['role'] = role
        if exclude_role:
            params['role__n'] = exclude_role

        data = self.get('/api/dcim/devices/', params)
        return data.get('results', [])

    def get_firewalls(self):
        """Get firewall devices from NetBox"""
        params = {'role': 'firewall'}
        data = self.get('/api/dcim/devices/', params)
        return data.get('results', [])

    def get_virtual_machines(self, site=None, status='active'):
        """Get virtual machines from NetBox"""
        params = {'status': status}
        if site:
            params['site'] = site

        data = self.get('/api/virtualization/virtual-machines/', params)
        return data.get('results', [])

    def get_ip_addresses(self, status='active'):
        """Get IP addresses from NetBox"""
        params = {'status': status}
        data = self.get('/api/ipam/ip-addresses/', params)
        return data.get('results', [])

    def get_prefixes(self, site=None):
        """Get prefixes (subnets) from NetBox"""
        params = {}
        if site:
            params['site'] = site

        data = self.get('/api/ipam/prefixes/', params)
        return data.get('results', [])

    def get_firewall_rules(self, firewall_name='fw1toyota123'):
        """Get existing firewall rules from NetBox"""
        devices = self.get_devices()
        firewall = next((d for d in devices if d['name'] == firewall_name), None)

        if not firewall:
            return []

        config_context = firewall.get('config_context', {})
        rules = config_context.get('firewall_rules', [])

        return rules

    def check_duplicate_rule(self, source_ip, dest_ip, firewall_name='fw1toyota123'):
        """Check if a rule already exists for this source/dest pair"""
        rules = self.get_firewall_rules(firewall_name)

        for rule in rules:
            if source_ip in rule.get('source', []) and dest_ip in rule.get('destination', []):
                return True, rule

        return False, None


# Initialize NetBox client
netbox = NetBoxClient(NETBOX_URL, NETBOX_TOKEN)


# ============================================
# SERVICE CATALOG FUNCTIONS
# ============================================

def load_service_catalog():
    """Load all service templates from catalog"""
    services = []
    catalog_files = glob.glob(os.path.join(SERVICE_CATALOG_PATH, "*.json"))

    for file_path in catalog_files:
        try:
            with open(file_path, 'r') as f:
                service = json.load(f)
                services.append(service)
        except Exception as e:
            print(f"Error loading {file_path}: {e}")

    return services


# ============================================
# FLASK ROUTES - PAGES
# ============================================

@app.route('/')
def index():
    """Dashboard - list all service requests"""
    return render_template('index.html', requests=service_requests, netbox_url=NETBOX_URL)


@app.route('/new_request')
def new_request():
    """Show service catalog"""
    services = load_service_catalog()
    return render_template('service_catalog.html', services=services)


@app.route('/request_form/<service_id>')
def request_form(service_id):
    """Show request form for specific service"""
    services = load_service_catalog()
    service = next((s for s in services if s['service_id'] == service_id), None)

    if not service:
        return "Service not found", 404

    # For firewall rules, use specialized template with NetBox integration
    if service_id == 'palo_alto_firewall_rule':
        return render_template('firewall_rule_form.html', service=service, netbox_url=NETBOX_URL)

    # For Azure VM, use specialized template
    if service_id == 'azure_vm':
        return render_template('azure_vm_form.html', service=service)

    return render_template('request_form.html', service=service)


@app.route('/request_details/<request_id>')
def request_details(request_id):
    """View request details and status"""
    req = next((r for r in service_requests if r['id'] == request_id), None)
    if not req:
        return "Request not found", 404
    return render_template('request_details.html', request=req, netbox_url=NETBOX_URL)


# ============================================
# FLASK ROUTES - FORM SUBMISSION
# ============================================

@app.route('/submit_request/<service_id>', methods=['POST'])
def submit_request(service_id):
    """Handle service request submission"""
    global request_counter

    # Load service definition
    services = load_service_catalog()
    service = next((s for s in services if s['service_id'] == service_id), None)

    if not service:
        return "Service not found", 404

    # Get requester
    requester = request.form.get('requester', 'Unknown')

    # Collect form data dynamically based on service fields
    form_data = {}
    for field in service['fields']:
        field_name = field['name']

        if field['type'] == 'checkbox':
            form_data[field_name] = request.form.getlist(field_name)
        else:
            form_data[field_name] = request.form.get(field_name)

    # For firewall rules, also collect additional fields
    if service_id == 'palo_alto_firewall_rule':
        additional_fields = [
            'target_firewall',
            'source_vm_manual', 'source_ip_manual', 'source_subnet_manual',
            'destination_vm_manual', 'destination_ip_manual', 'destination_subnet_manual'
        ]
        for field_name in additional_fields:
            form_data[field_name] = request.form.get(field_name, '')

    # Special handling for firewall rules
    if service_id == 'palo_alto_firewall_rule':
        return handle_firewall_rule_request(service, requester, form_data)

    # Special handling for Azure VM
    if service_id == 'azure_vm':
        return handle_azure_vm_request(service, requester, form_data)

    # Standard handling for other services
    request_counter += 1
    service_request = {
        'id': f'SR-{request_counter}',
        'type': service['service_name'],
        'service_id': service_id,
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'status': 'Pending',
        'requester': requester,
        'details': form_data,
        'playbook': service.get('playbook'),
        'logs': []
    }

    service_requests.insert(0, service_request)

    # Execute provisioning in background
    thread = threading.Thread(target=execute_provisioning, args=(service_request,))
    thread.daemon = True
    thread.start()

    return redirect(url_for('index'))


# ============================================
# FIREWALL RULE HANDLING
# ============================================

def is_any_address(value):
    """Check if an address represents 'any' (0.0.0.0/0, any, etc.)"""
    if not value:
        return False
    normalized = value.lower().strip()
    return normalized in ('any', '0.0.0.0/0', '0.0.0.0', '::/0', '::')


def handle_firewall_rule_request(service, requester, form_data):
    """Handle firewall rule submission with Git integration"""
    global request_counter

    # Extract source and destination based on type
    source_type = form_data.get('source_type', 'vm')
    dest_type = form_data.get('destination_type', 'vm')
    action = form_data.get('action', 'allow')

    # Helper to get value from dropdown or manual entry
    def get_field_value(field_name, field_type):
        dropdown_value = form_data.get(field_name, '')
        # Check if manual entry was selected
        if dropdown_value == '__manual__':
            manual_value = form_data.get(f'{field_name}_manual', '').strip()
            return manual_value
        return dropdown_value

    if source_type == 'vm':
        source_address = get_field_value('source_vm', 'vm').split('/')[0]  # Remove /32
    elif source_type == 'ip':
        source_address = get_field_value('source_ip', 'ip').split('/')[0]
    else:
        source_address = get_field_value('source_subnet', 'subnet')

    if dest_type == 'vm':
        dest_address = get_field_value('destination_vm', 'vm').split('/')[0]
    elif dest_type == 'ip':
        dest_address = get_field_value('destination_ip', 'ip').split('/')[0]
    else:
        dest_address = get_field_value('destination_subnet', 'subnet')

    # SECURITY CHECK: Block "Allow Any to Any" rules
    if action == 'allow' and is_any_address(source_address) and is_any_address(dest_address):
        return render_template('error.html',
                             error_title='Security Policy Violation',
                             error_message='Implicit Allow All is a cybersecurity RISK! Creating a rule that allows traffic from ANY source to ANY destination is extremely dangerous and violates security best practices.',
                             back_url='/new_request'), 400

    # Check for duplicate rule in firewall-rules directory
    is_duplicate_file, existing_file_rule = check_existing_rules(source_address, dest_address)
    if is_duplicate_file:
        return render_template('error.html',
                             error_title='Duplicate Rule Detected',
                             error_message=f"A rule with the same source and destination already exists: {existing_file_rule.get('rule_name', 'Unknown')}",
                             back_url='/new_request'), 400

    # Check for duplicate rule in NetBox
    is_duplicate, existing_rule = netbox.check_duplicate_rule(source_address, dest_address)
    if is_duplicate:
        return render_template('error.html',
                             error_title='Duplicate Rule Detected',
                             error_message=f"A rule with the same source and destination already exists in NetBox.",
                             back_url='/new_request'), 400

    # Create service request
    request_counter += 1
    service_request = {
        'id': f'SR-{request_counter}',
        'type': service['service_name'],
        'service_id': 'palo_alto_firewall_rule',
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'status': 'Pending',
        'requester': requester,
        'details': form_data,
        'source_address': source_address,
        'destination_address': dest_address,
        'duplicate_warning': is_duplicate,
        'existing_rule': existing_rule if is_duplicate else None,
        'playbook': os.path.join(PLAYBOOKS_PATH, 'deploy_firewall_rule.yml'),
        'git_enabled': service.get('git_enabled', False),
        'logs': []
    }

    service_requests.insert(0, service_request)

    # Execute with Git integration
    thread = threading.Thread(target=execute_firewall_rule_provisioning, args=(service_request,))
    thread.daemon = True
    thread.start()

    return redirect(url_for('index'))


def execute_firewall_rule_provisioning(service_request):
    """Execute firewall rule provisioning with Git integration"""
    try:
        # Step 1: Create firewall rule JSON
        service_request['status'] = 'Generating Rule'
        service_request['logs'].append({
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'message': 'Generating firewall rule JSON...'
        })

        rule_json = create_firewall_rule_json(service_request)
        rule_filename = f"{service_request['details']['rule_name']}.json"
        rule_filepath = os.path.join(FIREWALL_RULES_PATH, rule_filename)

        # Ensure firewall-rules directory exists
        os.makedirs(FIREWALL_RULES_PATH, exist_ok=True)

        # Write rule JSON
        with open(rule_filepath, 'w') as f:
            json.dump(rule_json, f, indent=2)

        service_request['logs'].append({
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'message': f'Rule definition created: {rule_filename}'
        })

        # Step 2: Git operations (if enabled)
        git_success = False
        if service_request.get('git_enabled'):
            service_request['status'] = 'Committing to Git'
            service_request['logs'].append({
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'message': 'Adding rule to Git repository...'
            })

            git_success = commit_rule_to_git(service_request, rule_filepath, rule_filename)

            if git_success:
                service_request['logs'].append({
                    'timestamp': datetime.now().strftime('%H:%M:%S'),
                    'message': 'Rule committed to Git successfully'
                })
                service_request['logs'].append({
                    'timestamp': datetime.now().strftime('%H:%M:%S'),
                    'message': 'CI/CD pipeline will deploy the rule automatically'
                })
                service_request['status'] = 'Completed - Pending CI/CD'
            else:
                service_request['logs'].append({
                    'timestamp': datetime.now().strftime('%H:%M:%S'),
                    'message': 'Git commit failed, falling back to direct deployment'
                })

        # Step 3: Direct Ansible deployment (if Git disabled or failed)
        if not service_request.get('git_enabled') or not git_success:
            service_request['status'] = 'Deploying to Firewall'
            execute_ansible_deployment(service_request, rule_filepath)

    except Exception as e:
        service_request['logs'].append({
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'message': f'Error: {str(e)}'
        })
        service_request['status'] = 'Failed'


def create_firewall_rule_json(service_request):
    """Create firewall rule JSON from form data"""
    details = service_request['details']

    # Get service list
    services = details.get('service', [])
    if not isinstance(services, list):
        services = [services]

    rule_json = {
        "rule_name": details['rule_name'],
        "description": details.get('description', ''),
        "source_zone": [details['source_zone']],
        "destination_zone": [details['destination_zone']],
        "source_address": [service_request['source_address']],
        "destination_address": [service_request['destination_address']],
        "application": services,
        "service": ["application-default"],
        "action": details['action'],
        "log_at_session_start": True,
        "log_at_session_end": True,
        "position": "top",
        "tag": ["gitops-managed", "self-service"],
        "metadata": {
            "created_by": service_request['requester'],
            "created_via": "Self-Service Portal",
            "timestamp": service_request['timestamp'],
            "request_id": service_request['id'],
            "target_firewall": details.get('target_firewall', ''),
            "business_justification": details.get('description', '')
        }
    }

    return rule_json


def commit_rule_to_git(service_request, rule_filepath, rule_filename):
    """Commit firewall rule to Git repository with new branch"""
    try:
        request_id = service_request['id']
        rule_name = service_request['details']['rule_name']

        # Branch name based on SR number
        branch_name = f"firewall-rule/{request_id}"

        # Re-load .env file to get latest credentials
        load_env_file()

        # Get Git credentials
        git_username = os.environ.get('GIT_USERNAME', '')
        git_token = os.environ.get('GIT_TOKEN', '')

        service_request['logs'].append({
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'message': f'Git credentials configured: {"Yes" if git_username and git_token else "No"}'
        })

        # Configure Git
        subprocess.run(['git', 'config', 'user.name', GIT_USER_NAME],
                      cwd=GIT_REPO_PATH, check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', GIT_USER_EMAIL],
                      cwd=GIT_REPO_PATH, check=True, capture_output=True)

        # Get current remote URL
        remote_result = subprocess.run(
            ['git', 'remote', 'get-url', 'origin'],
            cwd=GIT_REPO_PATH, capture_output=True, text=True
        )
        original_remote_url = remote_result.stdout.strip()
        url_changed = False

        # Fetch latest from origin (with credentials if available)
        if git_username and git_token:
            # Build authenticated URL
            if 'github.com' in original_remote_url:
                if original_remote_url.startswith('https://'):
                    auth_url = original_remote_url.replace(
                        'https://github.com',
                        f'https://{git_username}:{git_token}@github.com'
                    )
                elif original_remote_url.startswith('git@'):
                    # Convert SSH to HTTPS with auth
                    repo_path = original_remote_url.replace('git@github.com:', '').replace('.git', '')
                    auth_url = f'https://{git_username}:{git_token}@github.com/{repo_path}.git'
                else:
                    auth_url = original_remote_url

                # Temporarily set remote URL with auth
                subprocess.run(['git', 'remote', 'set-url', 'origin', auth_url],
                              cwd=GIT_REPO_PATH, capture_output=True)
                url_changed = True

        # Fetch from origin
        fetch_result = subprocess.run(['git', 'fetch', 'origin'],
                      cwd=GIT_REPO_PATH, capture_output=True, text=True)

        # Create and checkout new branch from main/master
        base_branch = 'main'
        check_main = subprocess.run(
            ['git', 'rev-parse', '--verify', 'origin/main'],
            cwd=GIT_REPO_PATH, capture_output=True
        )
        if check_main.returncode != 0:
            base_branch = 'master'

        # Create new branch
        subprocess.run(['git', 'checkout', '-b', branch_name, f'origin/{base_branch}'],
                      cwd=GIT_REPO_PATH, check=True, capture_output=True)

        service_request['logs'].append({
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'message': f'Created branch: {branch_name}'
        })

        # Git add
        subprocess.run(['git', 'add', rule_filepath],
                      cwd=GIT_REPO_PATH, check=True, capture_output=True)

        # Git commit with SR number
        commit_message = f"[{request_id}] Add firewall rule: {rule_name}\n\n" \
                        f"Request ID: {request_id}\n" \
                        f"Requester: {service_request['requester']}\n" \
                        f"Target Firewall: {service_request['details'].get('target_firewall', 'N/A')}\n" \
                        f"Action: {service_request['details']['action']}\n" \
                        f"Source: {service_request['source_address']}\n" \
                        f"Destination: {service_request['destination_address']}"

        subprocess.run(['git', 'commit', '-m', commit_message],
                      cwd=GIT_REPO_PATH, check=True, capture_output=True)

        service_request['logs'].append({
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'message': f'Committed rule with message: [{request_id}] Add firewall rule: {rule_name}'
        })

        # Git push
        service_request['logs'].append({
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'message': f'Pushing to remote branch: {branch_name}'
        })

        push_result = subprocess.run(
            ['git', 'push', '-u', 'origin', branch_name],
            cwd=GIT_REPO_PATH, capture_output=True, text=True
        )

        # Restore original remote URL if we changed it
        if url_changed:
            subprocess.run(['git', 'remote', 'set-url', 'origin', original_remote_url],
                          cwd=GIT_REPO_PATH, capture_output=True)

        if push_result.returncode == 0:
            service_request['git_commit'] = True
            service_request['git_branch'] = branch_name
            service_request['git_output'] = push_result.stdout
            service_request['logs'].append({
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'message': f'Successfully pushed to branch: {branch_name}'
            })
            return True
        else:
            service_request['git_error'] = push_result.stderr
            service_request['logs'].append({
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'message': f'Push failed: {push_result.stderr}'
            })
            return False

    except subprocess.CalledProcessError as e:
        service_request['git_error'] = str(e)
        service_request['logs'].append({
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'message': f'Git error: {str(e)}'
        })
        # Restore original remote URL on error
        try:
            if 'url_changed' in locals() and url_changed:
                subprocess.run(['git', 'remote', 'set-url', 'origin', original_remote_url],
                              cwd=GIT_REPO_PATH, capture_output=True)
        except:
            pass
        return False
    except Exception as e:
        service_request['git_error'] = str(e)
        service_request['logs'].append({
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'message': f'Unexpected error: {str(e)}'
        })
        # Restore original remote URL on error
        try:
            if 'url_changed' in locals() and url_changed:
                subprocess.run(['git', 'remote', 'set-url', 'origin', original_remote_url],
                              cwd=GIT_REPO_PATH, capture_output=True)
        except:
            pass
        return False


def execute_ansible_deployment(service_request, rule_filepath):
    """Execute Ansible playbook for direct deployment"""
    try:
        playbook_path = service_request.get('playbook')

        if not playbook_path or not os.path.exists(playbook_path):
            service_request['logs'].append({
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'message': f'Playbook not found: {playbook_path}'
            })
            service_request['status'] = 'Failed'
            return

        service_request['logs'].append({
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'message': 'Executing Ansible playbook...'
        })

        # Run Ansible
        ansible_cmd = [
            'ansible-playbook',
            playbook_path,
            '-e', f'rule_file={rule_filepath}',
            '-v'
        ]

        result = subprocess.run(
            ansible_cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=os.path.dirname(playbook_path)
        )

        service_request['ansible_output'] = result.stdout
        service_request['ansible_errors'] = result.stderr

        if result.returncode == 0:
            service_request['logs'].append({
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'message': 'Firewall rule deployed successfully'
            })
            service_request['status'] = 'Completed'
        else:
            service_request['logs'].append({
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'message': 'Ansible deployment failed'
            })
            service_request['status'] = 'Failed'

    except subprocess.TimeoutExpired:
        service_request['logs'].append({
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'message': 'Ansible execution timed out'
        })
        service_request['status'] = 'Timeout'
    except Exception as e:
        service_request['logs'].append({
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'message': f'Error: {str(e)}'
        })
        service_request['status'] = 'Failed'


# ============================================
# AZURE VM HANDLING
# ============================================

def handle_azure_vm_request(service, requester, form_data):
    """Handle Azure VM submission with Terraform and Git integration"""
    global request_counter

    # Create service request
    request_counter += 1
    deployment_name = form_data.get('deployment_name', f'deployment-{request_counter}')

    service_request = {
        'id': f'SR-{request_counter}',
        'type': service['service_name'],
        'service_id': 'azure_vm',
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'status': 'Pending',
        'requester': requester,
        'details': form_data,
        'deployment_name': deployment_name,
        'terraform_enabled': service.get('terraform_enabled', True),
        'git_enabled': service.get('git_enabled', True),
        'logs': []
    }

    service_requests.insert(0, service_request)

    # Execute Terraform deployment in background
    thread = threading.Thread(target=execute_azure_vm_provisioning, args=(service_request,))
    thread.daemon = True
    thread.start()

    return redirect(url_for('index'))


def execute_azure_vm_provisioning(service_request):
    """Execute Azure VM provisioning with Terraform and Git integration"""
    try:
        deployment_name = service_request['deployment_name']
        details = service_request['details']

        # Step 1: Create Terraform deployment directory
        service_request['status'] = 'Generating Terraform'
        service_request['logs'].append({
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'message': 'Creating Terraform deployment configuration...'
        })

        deployment_dir = os.path.join(TERRAFORM_DEPLOYMENTS_PATH, deployment_name)
        os.makedirs(deployment_dir, exist_ok=True)

        # Step 2: Copy Terraform templates
        import shutil
        for tf_file in ['providers.tf', 'variables.tf', 'main.tf', 'outputs.tf']:
            src_file = os.path.join(TERRAFORM_TEMPLATES_PATH, tf_file)
            if os.path.exists(src_file):
                shutil.copy(src_file, deployment_dir)

        service_request['logs'].append({
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'message': f'Created deployment directory: {deployment_name}'
        })

        # Step 3: Generate terraform.tfvars
        tfvars_content = generate_terraform_tfvars(service_request)
        tfvars_path = os.path.join(deployment_dir, 'terraform.tfvars')

        with open(tfvars_path, 'w') as f:
            f.write(tfvars_content)

        service_request['logs'].append({
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'message': 'Generated terraform.tfvars configuration'
        })

        # Step 4: Git operations (if enabled)
        git_success = False
        if service_request.get('git_enabled'):
            service_request['status'] = 'Committing to Git'
            service_request['logs'].append({
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'message': 'Adding Terraform configuration to Git repository...'
            })

            git_success = commit_terraform_to_git(service_request, deployment_dir, deployment_name)

            if git_success:
                service_request['logs'].append({
                    'timestamp': datetime.now().strftime('%H:%M:%S'),
                    'message': 'Terraform configuration committed to Git successfully'
                })
                service_request['logs'].append({
                    'timestamp': datetime.now().strftime('%H:%M:%S'),
                    'message': 'CI/CD pipeline will run terraform apply automatically'
                })
                service_request['status'] = 'Completed - Pending CI/CD'
            else:
                service_request['logs'].append({
                    'timestamp': datetime.now().strftime('%H:%M:%S'),
                    'message': 'Git commit failed'
                })
                service_request['status'] = 'Failed - Git Error'
        else:
            service_request['status'] = 'Completed - Manual Deployment Required'
            service_request['logs'].append({
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'message': f'Terraform configuration ready at: {deployment_dir}'
            })
            service_request['logs'].append({
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'message': 'Run "terraform init && terraform apply" to deploy'
            })

    except Exception as e:
        service_request['logs'].append({
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'message': f'Error: {str(e)}'
        })
        service_request['status'] = 'Failed'


def generate_terraform_tfvars(service_request):
    """Generate terraform.tfvars content from form data"""
    details = service_request['details']

    # Parse NSG rules
    nsg_rules = details.get('nsg_rules', [])
    if not isinstance(nsg_rules, list):
        nsg_rules = [nsg_rules] if nsg_rules else []

    tfvars = f'''# Terraform Variables for {service_request['deployment_name']}
# Generated by Self-Service Portal
# Request ID: {service_request['id']}
# Requester: {service_request['requester']}
# Timestamp: {service_request['timestamp']}

# Deployment Settings
deployment_name     = "{details.get('deployment_name', service_request['deployment_name'])}"
resource_group_name = "{details.get('resource_group', 'rg-' + service_request['deployment_name'])}"
location            = "{details.get('location', 'eastus')}"
environment         = "{details.get('environment', 'dev')}"

# VM Settings
vm_count        = {details.get('vm_count', '1')}
vm_name_prefix  = "{details.get('vm_name_prefix', 'vm')}"
vm_size         = "{details.get('vm_size', 'Standard_B2s')}"
os_type         = "{details.get('os_type', 'ubuntu_22_04')}"
admin_username  = "{details.get('admin_username', 'azureadmin')}"

# Network Settings
vnet_address_space    = "{details.get('vnet_address_space', '10.0.0.0/16')}"
subnet_address_prefix = "{details.get('subnet_address_prefix', '10.0.1.0/24')}"
create_public_ip      = true

# NSG Rules
nsg_rules = {json.dumps(nsg_rules)}

# Custom Ports
custom_ports = "{details.get('custom_ports', '')}"

# Metadata
request_id  = "{service_request['id']}"
requester   = "{service_request['requester']}"
description = "{details.get('description', '').replace('"', '\\"')}"

# Tags
tags = {{
  "Environment" = "{details.get('environment', 'dev')}"
  "Project"     = "{details.get('deployment_name', 'azure-vm')}"
  "ManagedBy"   = "Terraform"
  "RequestId"   = "{service_request['id']}"
  "Requester"   = "{service_request['requester']}"
}}
'''
    return tfvars


def commit_terraform_to_git(service_request, deployment_dir, deployment_name):
    """Commit Terraform deployment to Git repository"""
    try:
        request_id = service_request['id']

        # Branch name based on SR number
        branch_name = f"azure-vm/{request_id}"

        # Re-load .env file to get latest credentials
        load_env_file()

        # Get Git credentials
        git_username = os.environ.get('GIT_USERNAME', '')
        git_token = os.environ.get('GIT_TOKEN', '')

        # Configure Git
        subprocess.run(['git', 'config', 'user.name', GIT_USER_NAME],
                      cwd=GIT_REPO_PATH, check=True, capture_output=True)
        subprocess.run(['git', 'config', 'user.email', GIT_USER_EMAIL],
                      cwd=GIT_REPO_PATH, check=True, capture_output=True)

        # Get current remote URL
        remote_result = subprocess.run(
            ['git', 'remote', 'get-url', 'origin'],
            cwd=GIT_REPO_PATH, capture_output=True, text=True
        )
        original_remote_url = remote_result.stdout.strip()
        url_changed = False

        # Build authenticated URL if credentials available
        if git_username and git_token and 'github.com' in original_remote_url:
            if original_remote_url.startswith('https://'):
                auth_url = original_remote_url.replace(
                    'https://github.com',
                    f'https://{git_username}:{git_token}@github.com'
                )
            elif original_remote_url.startswith('git@'):
                repo_path = original_remote_url.replace('git@github.com:', '').replace('.git', '')
                auth_url = f'https://{git_username}:{git_token}@github.com/{repo_path}.git'
            else:
                auth_url = original_remote_url

            subprocess.run(['git', 'remote', 'set-url', 'origin', auth_url],
                          cwd=GIT_REPO_PATH, capture_output=True)
            url_changed = True

        # Fetch from origin
        subprocess.run(['git', 'fetch', 'origin'], cwd=GIT_REPO_PATH, capture_output=True)

        # Create new branch from main/master
        base_branch = 'main'
        check_main = subprocess.run(
            ['git', 'rev-parse', '--verify', 'origin/main'],
            cwd=GIT_REPO_PATH, capture_output=True
        )
        if check_main.returncode != 0:
            base_branch = 'master'

        subprocess.run(['git', 'checkout', '-b', branch_name, f'origin/{base_branch}'],
                      cwd=GIT_REPO_PATH, check=True, capture_output=True)

        service_request['logs'].append({
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'message': f'Created branch: {branch_name}'
        })

        # Git add the deployment directory
        subprocess.run(['git', 'add', deployment_dir],
                      cwd=GIT_REPO_PATH, check=True, capture_output=True)

        # Git commit
        commit_message = f"[{request_id}] Add Azure VM deployment: {deployment_name}\n\n" \
                        f"Request ID: {request_id}\n" \
                        f"Requester: {service_request['requester']}\n" \
                        f"Resource Group: {service_request['details'].get('resource_group', 'N/A')}\n" \
                        f"VM Count: {service_request['details'].get('vm_count', '1')}\n" \
                        f"VM Size: {service_request['details'].get('vm_size', 'N/A')}\n" \
                        f"OS: {service_request['details'].get('os_type', 'N/A')}"

        subprocess.run(['git', 'commit', '-m', commit_message],
                      cwd=GIT_REPO_PATH, check=True, capture_output=True)

        service_request['logs'].append({
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'message': f'Committed with message: [{request_id}] Add Azure VM deployment'
        })

        # Git push
        push_result = subprocess.run(
            ['git', 'push', '-u', 'origin', branch_name],
            cwd=GIT_REPO_PATH, capture_output=True, text=True
        )

        # Restore original remote URL
        if url_changed:
            subprocess.run(['git', 'remote', 'set-url', 'origin', original_remote_url],
                          cwd=GIT_REPO_PATH, capture_output=True)

        if push_result.returncode == 0:
            service_request['git_commit'] = True
            service_request['git_branch'] = branch_name
            service_request['logs'].append({
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'message': f'Successfully pushed to branch: {branch_name}'
            })
            return True
        else:
            service_request['git_error'] = push_result.stderr
            service_request['logs'].append({
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'message': f'Push failed: {push_result.stderr}'
            })
            return False

    except subprocess.CalledProcessError as e:
        service_request['git_error'] = str(e)
        service_request['logs'].append({
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'message': f'Git error: {str(e)}'
        })
        return False
    except Exception as e:
        service_request['git_error'] = str(e)
        service_request['logs'].append({
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'message': f'Unexpected error: {str(e)}'
        })
        return False


def execute_provisioning(service_request):
    """Standard provisioning for non-firewall services"""
    try:
        playbook_path = service_request.get('playbook')

        if not playbook_path or not os.path.exists(playbook_path):
            service_request['logs'].append({
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'message': f'Playbook not found: {playbook_path}'
            })
            service_request['status'] = 'Failed'
            return

        service_request['status'] = 'Running'
        service_request['logs'].append({
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'message': f'Starting {service_request["type"]} automation...'
        })

        # Create extra vars
        import tempfile
        extra_vars = dict(service_request['details'])
        extra_vars['requester'] = service_request['requester']

        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump(extra_vars, f)
            extra_vars_file = f.name

        try:
            ansible_cmd = [
                'ansible-playbook',
                playbook_path,
                '-e', f'@{extra_vars_file}',
                '-v'
            ]

            # Build summary message
            summary_parts = []
            for key, value in service_request['details'].items():
                if isinstance(value, list):
                    summary_parts.append(f"{key}: {', '.join(value)}")
                else:
                    summary_parts.append(f"{key}: {value}")

            service_request['logs'].append({
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'message': f"Configuration: {' | '.join(summary_parts[:3])}"
            })

            result = subprocess.run(
                ansible_cmd,
                capture_output=True,
                text=True,
                timeout=60,
                cwd=os.path.dirname(playbook_path)
            )

            service_request['ansible_output'] = result.stdout
            service_request['ansible_errors'] = result.stderr

            if result.returncode == 0:
                service_request['logs'].append({
                    'timestamp': datetime.now().strftime('%H:%M:%S'),
                    'message': f'{service_request["type"]} completed successfully'
                })
                service_request['status'] = 'Completed'
            else:
                service_request['logs'].append({
                    'timestamp': datetime.now().strftime('%H:%M:%S'),
                    'message': 'Automation failed'
                })
                service_request['status'] = 'Failed'
        finally:
            if os.path.exists(extra_vars_file):
                os.unlink(extra_vars_file)

    except subprocess.TimeoutExpired:
        service_request['logs'].append({
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'message': 'Execution timed out'
        })
        service_request['status'] = 'Timeout'
    except Exception as e:
        service_request['logs'].append({
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'message': f'Error: {str(e)}'
        })
        service_request['status'] = 'Failed'


# ============================================
# API ENDPOINTS FOR NETBOX DATA
# ============================================

@app.route('/api/netbox/firewalls')
def api_netbox_firewalls():
    """Get firewall devices from NetBox for dropdown"""
    firewalls = netbox.get_firewalls()

    # Check for errors
    if netbox.last_error:
        return jsonify({'error': netbox.last_error, 'options': []})

    options = []
    for fw in firewalls:
        name = fw.get('name', '')
        primary_ip = fw.get('primary_ip4')
        if primary_ip:
            ip_address = primary_ip['address'].split('/')[0]  # Remove CIDR
            options.append({
                'value': name,
                'label': f"{name} ({ip_address})",
                'ip_address': ip_address
            })
        else:
            options.append({
                'value': name,
                'label': name,
                'ip_address': None
            })

    return jsonify({'options': options})


@app.route('/api/netbox/devices')
def api_netbox_devices():
    """Get devices and virtual machines from NetBox for dropdown (excluding firewalls)"""
    site = request.args.get('site')
    role = request.args.get('role')

    # Fetch devices (excluding firewalls) and virtual machines
    devices = netbox.get_devices(site=site, role=role, exclude_role='firewall')
    virtual_machines = netbox.get_virtual_machines(site=site)

    # Check for errors
    if netbox.last_error:
        return jsonify({'error': netbox.last_error, 'options': []})

    # Format for dropdown - combining devices and VMs
    options = []
    seen_names = set()

    # Roles to exclude (network infrastructure, not endpoints)
    excluded_roles = {'firewall', 'switch', 'router'}

    # Process devices
    for device in devices:
        name = device.get('name', '')
        if name in seen_names:
            continue

        # Skip devices with infrastructure roles
        device_role = device.get('role', {})
        if device_role:
            role_slug = device_role.get('slug', '').lower() if isinstance(device_role, dict) else ''
            if role_slug in excluded_roles:
                continue

        seen_names.add(name)

        primary_ip = device.get('primary_ip4')
        if primary_ip:
            ip_address = primary_ip['address']
            options.append({
                'value': ip_address,
                'label': f"{name} ({ip_address})",
                'device_name': name,
                'ip_address': ip_address,
                'type': 'device'
            })
        else:
            # Include devices without IP - user can still select by name
            options.append({
                'value': name,
                'label': f"{name} (No IP assigned)",
                'device_name': name,
                'ip_address': None,
                'type': 'device'
            })

    # Process virtual machines
    for vm in virtual_machines:
        name = vm.get('name', '')
        if name in seen_names:
            continue
        seen_names.add(name)

        primary_ip = vm.get('primary_ip4')
        if primary_ip:
            ip_address = primary_ip['address']
            options.append({
                'value': ip_address,
                'label': f"{name} ({ip_address})",
                'device_name': name,
                'ip_address': ip_address,
                'type': 'vm'
            })
        else:
            # Include VMs without IP
            options.append({
                'value': name,
                'label': f"{name} (No IP assigned)",
                'device_name': name,
                'ip_address': None,
                'type': 'vm'
            })

    # Sort by label for easier selection
    options.sort(key=lambda x: x['label'].lower())

    return jsonify({'options': options})


@app.route('/api/netbox/ip-addresses')
def api_netbox_ip_addresses():
    """Get IP addresses from NetBox for dropdown"""
    ips = netbox.get_ip_addresses()

    # Check for errors
    if netbox.last_error:
        return jsonify({'error': netbox.last_error, 'options': []})

    options = []
    for ip in ips:
        description = ip.get('description', '')
        options.append({
            'value': ip['address'],
            'label': f"{ip['address']}" + (f" - {description}" if description else "")
        })

    return jsonify({'options': options})


@app.route('/api/netbox/prefixes')
def api_netbox_prefixes():
    """Get prefixes (subnets) from NetBox for dropdown"""
    prefixes = netbox.get_prefixes()

    # Check for errors
    if netbox.last_error:
        return jsonify({'error': netbox.last_error, 'options': []})

    options = []
    for prefix in prefixes:
        description = prefix.get('description', '')
        options.append({
            'value': prefix['prefix'],
            'label': f"{prefix['prefix']}" + (f" - {description}" if description else "")
        })

    return jsonify({'options': options})


@app.route('/api/netbox/existing-rules')
def api_netbox_existing_rules():
    """Get existing firewall rules from NetBox"""
    rules = netbox.get_firewall_rules()
    return jsonify(rules)


def check_existing_rules(source_address, dest_address):
    """Check if a rule with the same source/destination already exists in firewall-rules directory"""
    if not os.path.exists(FIREWALL_RULES_PATH):
        return False, None

    # Normalize addresses (remove CIDR notation for comparison)
    source_normalized = source_address.split('/')[0].lower().strip()
    dest_normalized = dest_address.split('/')[0].lower().strip()

    rule_files = glob.glob(os.path.join(FIREWALL_RULES_PATH, '*.json'))

    for rule_file in rule_files:
        try:
            with open(rule_file, 'r') as f:
                rule = json.load(f)

            # Get source and destination from the rule
            rule_sources = rule.get('source_address', [])
            rule_dests = rule.get('destination_address', [])

            # Normalize rule addresses
            for src in rule_sources:
                src_normalized = src.split('/')[0].lower().strip()
                for dst in rule_dests:
                    dst_normalized = dst.split('/')[0].lower().strip()

                    # Check if source and destination match
                    if src_normalized == source_normalized and dst_normalized == dest_normalized:
                        return True, {
                            'rule_name': rule.get('rule_name'),
                            'file': os.path.basename(rule_file),
                            'source': rule_sources,
                            'destination': rule_dests,
                            'action': rule.get('action')
                        }
        except (json.JSONDecodeError, IOError):
            continue

    return False, None


@app.route('/api/netbox/check-duplicate')
def api_netbox_check_duplicate():
    """Check if a rule already exists in firewall-rules directory or NetBox"""
    source_ip = request.args.get('source_ip', '').strip()
    dest_ip = request.args.get('dest_ip', '').strip()

    if not source_ip or not dest_ip:
        return jsonify({'duplicate': False})

    # First check firewall-rules directory
    is_duplicate, existing_rule = check_existing_rules(source_ip, dest_ip)

    if is_duplicate:
        return jsonify({
            'duplicate': True,
            'existing_rule': existing_rule,
            'source': 'firewall-rules'
        })

    # Then check NetBox
    is_duplicate, existing_rule = netbox.check_duplicate_rule(source_ip, dest_ip)

    return jsonify({
        'duplicate': is_duplicate,
        'existing_rule': existing_rule,
        'source': 'netbox' if is_duplicate else None
    })


@app.route('/api/request_status/<request_id>')
def api_request_status(request_id):
    """Get request status as JSON (for AJAX polling)"""
    req = next((r for r in service_requests if r['id'] == request_id), None)
    if not req:
        return jsonify({'error': 'Request not found'}), 404
    return jsonify(req)


# ============================================
# DEPLOY APPLICATION ROUTES
# ============================================

def load_apps_config():
    """Load apps configuration from apps.json"""
    apps_file = os.path.join(PORTAL_DIR, 'apps.json')
    try:
        with open(apps_file, 'r') as f:
            data = json.load(f)
            return data.get('apps', [])
    except Exception as e:
        print(f'Error loading apps.json: {e}')
        return []


def find_app_by_id(app_id):
    """Find an app by its id in apps.json"""
    apps = load_apps_config()
    for app in apps:
        if app.get('id') == app_id:
            return app
    return None


@app.route('/deploy')
def deploy_form():
    """Render the deploy application form"""
    apps = load_apps_config()
    return render_template('deploy/deploy.html', title="Deploy Application", apps=apps)


@app.route('/deploy/app-info/<app_id>')
def deploy_app_info(app_id):
    """Fetch app info and latest GitHub release tag"""
    app = find_app_by_id(app_id)
    if not app:
        return jsonify({'error': 'App not found'}), 404

    # Fetch latest tag from GitHub
    tag_result = awx_client.get_latest_github_tag(
        app.get('repo_owner', ''),
        app.get('repo_name', '')
    )

    return jsonify({
        'id': app.get('id', ''),
        'display_name': app.get('display_name', ''),
        'description': app.get('description', ''),
        'repo_url': app.get('repo_url', ''),
        'image_registry': app.get('image_registry', ''),
        'default_namespace': app.get('default_namespace', ''),
        'latest_tag': tag_result.get('tag', ''),
        'published_at': tag_result.get('published_at', ''),
        'tag_found': tag_result.get('found', False)
    })


@app.route('/deploy', methods=['POST'])
def deploy_app():
    """Trigger AWX job to deploy application"""
    data = request.get_json()

    if not data:
        return jsonify({'error': 'Request body must be JSON'}), 400

    # Validate required fields
    app_id = data.get('app_id', '').strip() if data.get('app_id') else ''
    version = data.get('version', '').strip() if data.get('version') else ''
    target = data.get('target', '').strip() if data.get('target') else ''

    if not app_id:
        return jsonify({'error': 'app_id is required'}), 400

    if not version:
        return jsonify({'error': 'version is required'}), 400

    if target not in ('vm', 'openshift', 'aks'):
        return jsonify({'error': 'target must be one of: "vm", "openshift", "aks"'}), 400

    # Look up app from apps.json (source of truth)
    app = find_app_by_id(app_id)
    if not app:
        return jsonify({'error': 'Unknown app'}), 400

    app_name = app.get('id', '')
    repo_url = app.get('repo_url', '')
    image_registry = app.get('image_registry', '')

    # Initialize target-specific fields
    vm_host = ''
    namespace = 'default'

    # Target-specific validation and extra_vars
    if target == 'vm':
        vm_host = data.get('vm_host', '').strip() if data.get('vm_host') else ''
        if not vm_host:
            return jsonify({'error': 'vm_host is required when target is "vm"'}), 400
        extra_vars = {
            'app_name': app_name,
            'version': version,
            'vm_host': vm_host,
            'repo_url': repo_url
        }
        template_name = 'Deploy-App-VM'

    elif target == 'openshift':
        namespace = data.get('namespace', 'default').strip() if data.get('namespace') else 'default'
        extra_vars = {
            'app_name': app_name,
            'image_tag': version,
            'namespace': namespace,
            'image_registry': image_registry
        }
        template_name = 'Deploy-App-OCP'

    elif target == 'aks':
        namespace = data.get('namespace', 'default').strip() if data.get('namespace') else 'default'
        extra_vars = {
            'app_name': app_name,
            'image_tag': version,
            'namespace': namespace,
            'image_registry': image_registry,
            'aks_cluster': os.getenv('AKS_CLUSTER_NAME', ''),
            'aks_rg': os.getenv('AKS_RESOURCE_GROUP', '')
        }
        template_name = 'Deploy-App-AKS'

    # Trigger AWX job or simulate in demo mode
    if DEMO_MODE:
        awx_job = demo_simulator.simulate_awx_job(app_id, target, AWX_BASE_URL)
        job_id = awx_job['job_id']
    else:
        try:
            job_id = awx_client.trigger_job(template_name, extra_vars)
            awx_job = None
        except ValueError as e:
            return jsonify({'error': str(e)}), 404
        except RuntimeError as e:
            return jsonify({'error': str(e)}), 502

    # Store job metadata
    vm_monitoring = _build_vm_monitoring_links(app_id) if target == 'vm' else {}
    deploy_jobs[job_id] = {
        'app_id': app_id,
        'app_name': app_name,
        'version': version,
        'target': target,
        'vm_host': vm_host,
        'namespace': namespace,
        'status': 'running',
        'url': None,
        'started_at': datetime.utcnow().isoformat(),
        'awx_job': awx_job,
        'influxdb_url': vm_monitoring.get('influxdb_url'),
        'grafana_url': vm_monitoring.get('grafana_url')
    }

    if target == 'aks' and DEMO_MODE:
        import subprocess
        import threading

        def run_kubectl_commands():
            commands = [
                ["kubectl", "get", "pods", "-n", "argocd"],
                ["kubectl", "apply", "-f", "argocd-app.yaml"],
                ["kubectl", "get", "applications", "-n", "argocd"],
            ]
            for cmd in commands:
                try:
                    subprocess.Popen(
                        cmd,
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL
                    )
                except Exception as e:
                    app.logger.warning(f"kubectl command failed: {e}")

        # Run in background thread so it doesn't block the response
        threading.Thread(target=run_kubectl_commands, daemon=True).start()

    # Store ArgoCD info for AKS deployments
    if target == 'aks':
        deploy_jobs[job_id]['argocd_url'] = f"https://localhost:8080/applications/{app_id}"

    # Return response with AWX job info if in demo mode
    response = {'job_id': job_id}
    if DEMO_MODE and awx_job:
        response['awx_job_id'] = awx_job['job_id']
        response['awx_template_name'] = awx_job['job_template_name']
        response['awx_launched_by'] = awx_job['launched_by']
        response['awx_started_at'] = awx_job['created']
        response['awx_url'] = awx_job['awx_url']
        response['argocd_url'] = awx_job.get('argocd_url')
        response['uses_argocd'] = awx_job.get('uses_argocd', False)
    else:
        response['argocd_url'] = f"https://localhost:8080/applications/{app_id}" if target == 'aks' else None
        response['uses_argocd'] = target == 'aks'

    if target == 'vm':
        response['influxdb_url'] = vm_monitoring.get('influxdb_url')
        response['grafana_url'] = vm_monitoring.get('grafana_url')

    return jsonify(response)


@app.route('/deploy/status/<job_id>')
def deploy_status(job_id):
    """Stream job logs via Server-Sent Events"""
    def generate():
        # Check if job exists
        if job_id not in deploy_jobs:
            yield f"data: {json.dumps({'error': 'Job not found'})}\n\n"
            return

        job = deploy_jobs[job_id]

        # Choose log source based on mode
        if DEMO_MODE:
            log_stream = demo_simulator.simulate_deployment(
                app_id=job.get('app_id', ''),
                version=job.get('version', ''),
                target=job.get('target', ''),
                vm_host=job.get('vm_host', ''),
                namespace=job.get('namespace', '')
            )
        else:
            log_stream = awx_client.stream_job_log(job_id)

        # Stream logs
        for item in log_stream:
            if isinstance(item, dict):
                # Final status dict - update job record
                deploy_jobs[job_id]['status'] = item.get('status', 'unknown')
                deploy_jobs[job_id]['url'] = item.get('url')
                if item.get('argocd_url'):
                    deploy_jobs[job_id]['argocd_url'] = item.get('argocd_url')
                if job.get('target') == 'vm':
                    item['influxdb_url'] = job.get('influxdb_url')
                    item['grafana_url'] = job.get('grafana_url')
                yield f"data: {json.dumps(item)}\n\n"
                return
            else:
                # Log line
                yield f"data: {item}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype='text/event-stream',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no'
        }
    )


@app.route('/deploy/awx-status/<job_id>')
def deploy_awx_status(job_id):
    """Return current AWX job status (for polling)"""
    if job_id not in deploy_jobs:
        return jsonify({'error': 'Job not found'}), 404

    job = deploy_jobs[job_id]
    started_at_str = job.get('started_at', '')

    # Calculate elapsed time
    try:
        started_at = datetime.fromisoformat(started_at_str.replace('Z', '+00:00'))
        elapsed = (datetime.utcnow() - started_at.replace(tzinfo=None)).total_seconds()
    except Exception:
        elapsed = 0

    # Get status based on elapsed time in demo mode
    if DEMO_MODE:
        status = demo_simulator.get_simulated_job_status(elapsed, job.get('target', ''))
    else:
        status = job.get('status', 'unknown')

    return jsonify({
        'job_id': job_id,
        'status': status,
        'elapsed': elapsed
    })


@app.route('/awx/jobs/<job_id>/output')
def awx_job_output(job_id):
    """Render fake AWX job output page"""
    if job_id not in deploy_jobs:
        return "Job not found", 404

    job = deploy_jobs[job_id]
    awx_job = job.get('awx_job', {})

    return render_template('awx_job_output.html',
        job_id=job_id,
        app_name=job.get('app_name', ''),
        version=job.get('version', ''),
        target=job.get('target', ''),
        template_name=awx_job.get('job_template_name', f"Deploy-App-{job.get('target', 'VM').upper()}"),
        launched_by='nttdata-portal',
        started_at=job.get('started_at', ''),
        status=job.get('status', 'running')
    )


# ============================================
# APP PROXY (Reverse Proxy for Demo App)
# ============================================

def _proxy(subpath=""):
    """Proxy requests to the demo app running on APP_PROXY_TARGET"""
    target_url = f"{APP_PROXY_TARGET}/{subpath}"

    # Forward query string
    if request.query_string:
        target_url += "?" + request.query_string.decode()

    # Forward the request to the target app
    resp = req_lib.request(
        method=request.method,
        url=target_url,
        headers={
            key: val for key, val in request.headers
            if key.lower() not in
            ("host", "content-length", "transfer-encoding")
        },
        data=request.get_data(),
        cookies=request.cookies,
        allow_redirects=False,
        timeout=10
    )

    # Rewrite any absolute URLs in HTML responses
    # so internal links stay on the portal domain
    content_type = resp.headers.get("Content-Type", "")
    content = resp.content
    if "text/html" in content_type:
        content = content.replace(
            b"http://127.0.0.1:5001",
            b""
        ).replace(
            b"http://localhost:5001",
            b""
        )

    # Strip hop-by-hop headers
    excluded = {
        "content-encoding", "content-length",
        "transfer-encoding", "connection"
    }
    headers = {
        k: v for k, v in resp.headers.items()
        if k.lower() not in excluded
    }

    return Response(
        content,
        status=resp.status_code,
        headers=headers,
        content_type=content_type
    )


@app.route("/app-proxy/", defaults={"subpath": ""})
@app.route("/app-proxy/<path:subpath>", methods=["GET", "POST", "PUT", "DELETE"])
def app_proxy(subpath):
    """Reverse proxy to demo app"""
    return _proxy(subpath)


# ============================================
# MAIN
# ============================================

if __name__ == '__main__':
    print("\n" + "="*60)
    print("Self-Service Infrastructure Portal")
    print("Palo Alto Firewall Rule Automation with NetBox Integration")
    print("="*60)

    # Print configuration
    print(f"\nConfiguration:")
    print(f"  Base Directory: {BASE_DIR}")
    print(f"  Service Catalog: {SERVICE_CATALOG_PATH}")
    print(f"  Firewall Rules: {FIREWALL_RULES_PATH}")
    print(f"  NetBox URL: {NETBOX_URL}")

    # Load and display available services
    services = load_service_catalog()
    print(f"\nAvailable Services: {len(services)}")
    for service in services:
        netbox_badge = " [NetBox]" if service.get('netbox_integration') else ""
        git_badge = " [GitOps]" if service.get('git_enabled') else ""
        print(f"  - {service['icon']} {service['service_name']}{netbox_badge}{git_badge}")

    print(f"\nStarting server at http://localhost:5000")
    print(f"{'='*60}\n")

    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
