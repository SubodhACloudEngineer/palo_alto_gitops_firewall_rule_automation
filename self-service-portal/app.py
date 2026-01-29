#!/usr/bin/env python3
from flask import Flask, render_template, request, jsonify, redirect, url_for
import subprocess
import json
import threading
from datetime import datetime
import os
import glob

app = Flask(__name__)

# Configuration
SERVICE_CATALOG_PATH = "/home/subodhkashyap/self-service-portal/service_catalog"
NETBOX_SYNC_SCRIPT = "/home/subodhkashyap/containerlab-labs/sync_to_netbox_simple.py"
NETBOX_URL = "http://localhost:8000"

# In-memory storage for demo
service_requests = []
request_counter = 1000

def load_service_catalog():
    """Load all service templates from catalog"""
    services = []
    catalog_files = glob.glob(f"{SERVICE_CATALOG_PATH}/*.json")
    
    for file_path in catalog_files:
        try:
            with open(file_path, 'r') as f:
                service = json.load(f)
                services.append(service)
        except Exception as e:
            print(f"Error loading {file_path}: {e}")
    
    return services

@app.route('/')
def index():
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
    
    return render_template('request_form.html', service=service)

@app.route('/submit_request/<service_id>', methods=['POST'])
def submit_request(service_id):
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
    
    # Create service request
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

def execute_provisioning(service_request):
    """Execute Ansible playbook for the service"""
    try:
        playbook_path = service_request.get('playbook')
        
        if not playbook_path or not os.path.exists(playbook_path):
            service_request['logs'].append({
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'message': f'❌ Playbook not found: {playbook_path}'
            })
            service_request['status'] = 'Failed'
            return
        
        service_request['status'] = 'Running Automation'
        service_request['logs'].append({
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'message': f'Starting {service_request["type"]} automation...'
        })
        
        # Create temporary extra vars file
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
            
            service_request['logs'].append({
                'timestamp': datetime.now().strftime('%H:%M:%S'),
                'message': f"Executing automation playbook..."
            })
            
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
            
            # Execute Ansible
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
                    'message': f'✅ {service_request["type"]} completed successfully'
                })
                service_request['status'] = 'Completed'
            else:
                service_request['logs'].append({
                    'timestamp': datetime.now().strftime('%H:%M:%S'),
                    'message': f'❌ Automation failed. Check output below.'
                })
                service_request['status'] = 'Failed'
        finally:
            if os.path.exists(extra_vars_file):
                os.unlink(extra_vars_file)
            
    except subprocess.TimeoutExpired:
        service_request['logs'].append({
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'message': '⚠️  Execution took longer than expected'
        })
        service_request['status'] = 'Timeout'
    except Exception as e:
        service_request['logs'].append({
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'message': f'❌ Error: {str(e)}'
        })
        service_request['status'] = 'Failed'

@app.route('/request_details/<request_id>')
def request_details(request_id):
    req = next((r for r in service_requests if r['id'] == request_id), None)
    if not req:
        return "Request not found", 404
    return render_template('request_details.html', request=req, netbox_url=NETBOX_URL)

@app.route('/api/request_status/<request_id>')
def api_request_status(request_id):
    req = next((r for r in service_requests if r['id'] == request_id), None)
    if not req:
        return jsonify({'error': 'Request not found'}), 404
    return jsonify(req)

if __name__ == '__main__':
    print("\n" + "="*60)
    print("NTT DATA - Self-Service Infrastructure Portal")
    print("="*60)
    
    # Load and display available services
    services = load_service_catalog()
    print(f"\n📋 Available Services: {len(services)}")
    for service in services:
        print(f"   • {service['icon']} {service['service_name']} ({service['category']})")
    
    print(f"\n🚀 Starting server at http://localhost:5000")
    print(f"📊 Netbox CMDB available at {NETBOX_URL}")
    print(f"\n{'='*60}\n")
    app.run(host='0.0.0.0', port=5000, debug=True, use_reloader=False)
