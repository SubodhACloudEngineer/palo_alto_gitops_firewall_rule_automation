#!/usr/bin/env python3
"""
Self-Service Infrastructure Portal with NetBox Integration
Palo Alto Firewall Rule Provisioning via GitOps
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for
import subprocess
import json
import threading
from datetime import datetime
import os
import glob
import requests
from urllib3.exceptions import InsecureRequestWarning

# Disable SSL warnings
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

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

# NetBox Configuration
# Priority: Environment variable > .env file > None
NETBOX_URL = os.environ.get("NETBOX_URL", "http://localhost:8000")
NETBOX_TOKEN = os.environ.get("NETBOX_TOKEN")

# Git configuration for firewall rules
GIT_REPO_PATH = BASE_DIR
GIT_USER_NAME = os.environ.get("GIT_USER_NAME", "Self-Service Portal")
GIT_USER_EMAIL = os.environ.get("GIT_USER_EMAIL", "portal@example.com")

# In-memory storage for requests
service_requests = []
request_counter = 1000


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
            response = requests.get(url, headers=self.headers, params=params, verify=False, timeout=10)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 403:
                self.last_error = "Authentication failed. Check your NETBOX_TOKEN in .env file."
            elif e.response.status_code == 404:
                self.last_error = f"NetBox endpoint not found: {endpoint}"
            else:
                self.last_error = f"HTTP {e.response.status_code}: {str(e)}"
            print(f"NetBox API error: {self.last_error}")
            return {'results': [], 'count': 0, 'error': self.last_error}
        except requests.exceptions.ConnectionError:
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

def handle_firewall_rule_request(service, requester, form_data):
    """Handle firewall rule submission with Git integration"""
    global request_counter

    # Extract source and destination based on type
    source_type = form_data.get('source_type', 'vm')
    dest_type = form_data.get('destination_type', 'vm')

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

    # Check for duplicate rule
    is_duplicate, existing_rule = netbox.check_duplicate_rule(source_address, dest_address)

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
        "target_firewall": details.get('target_firewall', ''),
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


@app.route('/api/netbox/check-duplicate')
def api_netbox_check_duplicate():
    """Check if a rule already exists"""
    source_ip = request.args.get('source_ip')
    dest_ip = request.args.get('dest_ip')

    if not source_ip or not dest_ip:
        return jsonify({'duplicate': False})

    is_duplicate, existing_rule = netbox.check_duplicate_rule(source_ip, dest_ip)

    return jsonify({
        'duplicate': is_duplicate,
        'existing_rule': existing_rule
    })


@app.route('/api/request_status/<request_id>')
def api_request_status(request_id):
    """Get request status as JSON (for AJAX polling)"""
    req = next((r for r in service_requests if r['id'] == request_id), None)
    if not req:
        return jsonify({'error': 'Request not found'}), 404
    return jsonify(req)


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
