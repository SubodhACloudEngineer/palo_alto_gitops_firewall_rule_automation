#!/usr/bin/env python3
"""
Palo Alto Firewall Rule Deployment via REST API
Deploys firewall rules directly using the PAN-OS XML API without requiring Ansible.
"""

import json
import os
import sys
import time
import ssl
import urllib.request
import urllib.parse
import xml.etree.ElementTree as ET
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional, List, Tuple


class PaloAltoAPI:
    """Palo Alto Networks Firewall REST API Client."""

    def __init__(self, host: str, username: str = None, password: str = None, api_key: str = None, verify_ssl: bool = False):
        self.host = host
        self.base_url = f"https://{host}/api/"
        self.api_key = api_key
        self.username = username
        self.password = password
        self.verify_ssl = verify_ssl

        # Create SSL context
        if not verify_ssl:
            self.ssl_context = ssl.create_default_context()
            self.ssl_context.check_hostname = False
            self.ssl_context.verify_mode = ssl.CERT_NONE
        else:
            self.ssl_context = None

        # Get API key if not provided
        if not self.api_key and username and password:
            self.api_key = self._get_api_key()

    def _get_api_key(self) -> str:
        """Generate API key from username/password."""
        params = {
            'type': 'keygen',
            'user': self.username,
            'password': self.password
        }
        response = self._make_request(params, use_key=False)
        root = ET.fromstring(response)
        key_elem = root.find('.//key')
        if key_elem is not None:
            return key_elem.text
        raise Exception("Failed to generate API key")

    def _make_request(self, params: Dict[str, str], use_key: bool = True) -> str:
        """Make API request to firewall."""
        if use_key and self.api_key:
            params['key'] = self.api_key

        url = self.base_url + '?' + urllib.parse.urlencode(params)

        request = urllib.request.Request(url)
        request.add_header('Content-Type', 'application/x-www-form-urlencoded')

        try:
            if self.ssl_context:
                response = urllib.request.urlopen(request, context=self.ssl_context, timeout=60)
            else:
                response = urllib.request.urlopen(request, timeout=60)
            return response.read().decode('utf-8')
        except urllib.error.HTTPError as e:
            error_body = e.read().decode('utf-8') if e.fp else str(e)
            raise Exception(f"HTTP Error {e.code}: {error_body}")
        except urllib.error.URLError as e:
            raise Exception(f"URL Error: {e.reason}")

    def get_system_info(self) -> Dict[str, Any]:
        """Get firewall system information."""
        params = {
            'type': 'op',
            'cmd': '<show><system><info></info></system></show>'
        }
        response = self._make_request(params)
        return self._parse_response(response)

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """Parse XML response into dictionary."""
        root = ET.fromstring(response)
        status = root.get('status', 'error')

        result = {
            'status': status,
            'code': root.get('code', ''),
            'message': ''
        }

        msg_elem = root.find('.//msg')
        if msg_elem is not None:
            if msg_elem.text:
                result['message'] = msg_elem.text
            else:
                # Try to get nested message
                line_elem = msg_elem.find('.//line')
                if line_elem is not None:
                    result['message'] = line_elem.text or ''

        return result

    def check_rule_exists(self, rule_name: str, vsys: str = 'vsys1') -> bool:
        """Check if a security rule already exists."""
        xpath = f"/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='{vsys}']/rulebase/security/rules/entry[@name='{rule_name}']"
        params = {
            'type': 'config',
            'action': 'get',
            'xpath': xpath
        }
        try:
            response = self._make_request(params)
            root = ET.fromstring(response)
            entry = root.find('.//entry')
            return entry is not None
        except:
            return False

    def create_security_rule(self, rule: Dict[str, Any], vsys: str = 'vsys1', position: str = 'bottom') -> Dict[str, Any]:
        """Create or update a security rule."""
        rule_name = rule['rule_name']

        # Build the rule XML element
        element = self._build_rule_element(rule)

        # XPath for the rule
        if position == 'top':
            xpath = f"/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='{vsys}']/rulebase/security/rules/entry[@name='{rule_name}']"
        else:
            xpath = f"/config/devices/entry[@name='localhost.localdomain']/vsys/entry[@name='{vsys}']/rulebase/security/rules/entry[@name='{rule_name}']"

        params = {
            'type': 'config',
            'action': 'set',
            'xpath': xpath,
            'element': element
        }

        response = self._make_request(params)
        return self._parse_response(response)

    def _build_rule_element(self, rule: Dict[str, Any]) -> str:
        """Build XML element string for a security rule."""
        elements = []

        # Description
        if rule.get('description'):
            elements.append(f"<description>{self._escape_xml(rule['description'])}</description>")

        # Source zone
        elements.append(self._build_member_element('from', rule.get('source_zone', ['any'])))

        # Destination zone
        elements.append(self._build_member_element('to', rule.get('destination_zone', ['any'])))

        # Source address
        elements.append(self._build_member_element('source', rule.get('source_address', ['any'])))

        # Destination address
        elements.append(self._build_member_element('destination', rule.get('destination_address', ['any'])))

        # Source user
        elements.append(self._build_member_element('source-user', rule.get('source_user', ['any'])))

        # Category
        elements.append(self._build_member_element('category', rule.get('category', ['any'])))

        # Application
        elements.append(self._build_member_element('application', rule.get('application', ['any'])))

        # Service
        elements.append(self._build_member_element('service', rule.get('service', ['application-default'])))

        # Action
        elements.append(f"<action>{rule.get('action', 'deny')}</action>")

        # Logging
        if rule.get('log_at_session_start', True):
            elements.append("<log-start>yes</log-start>")
        else:
            elements.append("<log-start>no</log-start>")

        if rule.get('log_at_session_end', True):
            elements.append("<log-end>yes</log-end>")
        else:
            elements.append("<log-end>no</log-end>")

        # Log forwarding profile
        if rule.get('log_forwarding'):
            elements.append(f"<log-setting>{self._escape_xml(rule['log_forwarding'])}</log-setting>")

        # Security profiles
        if rule.get('group_profile'):
            elements.append(f"<profile-setting><group><member>{self._escape_xml(rule['group_profile'])}</member></group></profile-setting>")

        # Tags
        if rule.get('tag'):
            elements.append(self._build_member_element('tag', rule['tag']))

        # Disabled
        if rule.get('disabled', False):
            elements.append("<disabled>yes</disabled>")

        # Negate source/destination
        if rule.get('negate_source', False):
            elements.append("<negate-source>yes</negate-source>")
        if rule.get('negate_destination', False):
            elements.append("<negate-destination>yes</negate-destination>")

        return ''.join(elements)

    def _build_member_element(self, name: str, values: List[str]) -> str:
        """Build a member element with multiple values."""
        if not values:
            values = ['any']
        members = ''.join([f"<member>{self._escape_xml(v)}</member>" for v in values])
        return f"<{name}>{members}</{name}>"

    def _escape_xml(self, text: str) -> str:
        """Escape special XML characters."""
        if not text:
            return ''
        return (text
                .replace('&', '&amp;')
                .replace('<', '&lt;')
                .replace('>', '&gt;')
                .replace('"', '&quot;')
                .replace("'", '&apos;'))

    def commit(self, description: str = None) -> Dict[str, Any]:
        """Commit configuration changes."""
        if description:
            cmd = f'<commit><description>{self._escape_xml(description)}</description></commit>'
        else:
            cmd = '<commit></commit>'

        params = {
            'type': 'commit',
            'cmd': cmd
        }

        response = self._make_request(params)
        result = self._parse_response(response)

        # Extract job ID
        root = ET.fromstring(response)
        job_elem = root.find('.//job')
        if job_elem is not None:
            result['job_id'] = job_elem.text

        return result

    def get_commit_status(self, job_id: str) -> Dict[str, Any]:
        """Get the status of a commit job."""
        params = {
            'type': 'op',
            'cmd': f'<show><jobs><id>{job_id}</id></jobs></show>'
        }

        response = self._make_request(params)
        root = ET.fromstring(response)

        result = {
            'status': 'unknown',
            'progress': 0,
            'details': ''
        }

        job = root.find('.//job')
        if job is not None:
            status_elem = job.find('status')
            if status_elem is not None:
                result['status'] = status_elem.text

            progress_elem = job.find('progress')
            if progress_elem is not None:
                try:
                    result['progress'] = int(progress_elem.text)
                except:
                    pass

            result_elem = job.find('result')
            if result_elem is not None:
                result['result'] = result_elem.text

            details_elem = job.find('details')
            if details_elem is not None:
                result['details'] = ET.tostring(details_elem, encoding='unicode')

        return result

    def wait_for_commit(self, job_id: str, timeout: int = 300, poll_interval: int = 5) -> Tuple[bool, str]:
        """Wait for a commit job to complete."""
        start_time = time.time()

        while time.time() - start_time < timeout:
            status = self.get_commit_status(job_id)

            if status.get('status') == 'FIN':
                if status.get('result') == 'OK':
                    return True, "Commit successful"
                else:
                    return False, f"Commit failed: {status.get('details', 'Unknown error')}"

            print(f"  Commit progress: {status.get('progress', 0)}%")
            time.sleep(poll_interval)

        return False, "Commit timed out"


def load_rule_file(file_path: str) -> Dict[str, Any]:
    """Load a firewall rule from a JSON file."""
    with open(file_path, 'r') as f:
        return json.load(f)


def deploy_rule(rule_file: str, dry_run: bool = False, environment: str = 'staging') -> bool:
    """Deploy a single firewall rule."""
    print()
    print("=" * 70)
    print(f"PALO ALTO FIREWALL RULE DEPLOYMENT")
    print("=" * 70)
    print(f"Rule File:   {rule_file}")
    print(f"Environment: {environment.upper()}")
    print(f"Dry Run:     {dry_run}")
    print(f"Timestamp:   {datetime.utcnow().isoformat()}Z")
    print("=" * 70)

    # Load rule
    try:
        rule = load_rule_file(rule_file)
    except Exception as e:
        print(f"\nERROR: Failed to load rule file: {e}")
        return False

    rule_name = rule.get('rule_name', 'Unknown')
    print(f"\nRule Name: {rule_name}")
    print(f"Action:    {rule.get('action', 'deny').upper()}")
    print(f"Source:    {', '.join(rule.get('source_address', []))} ({', '.join(rule.get('source_zone', []))})")
    print(f"Dest:      {', '.join(rule.get('destination_address', []))} ({', '.join(rule.get('destination_zone', []))})")

    if dry_run:
        print("\n" + "-" * 70)
        print("[DRY RUN] No changes will be made to the firewall")
        print("-" * 70)
        print(f"\nRule '{rule_name}' would be deployed with the following configuration:")
        print(json.dumps(rule, indent=2))
        print("\n[DRY RUN] Deployment simulation completed successfully")
        return True

    # Get firewall credentials from environment
    firewall_ip = os.environ.get('PA_FIREWALL_IP')
    username = os.environ.get('PA_USERNAME')
    password = os.environ.get('PA_PASSWORD')
    api_key = os.environ.get('PA_API_KEY')

    if not firewall_ip:
        print("\nERROR: PA_FIREWALL_IP environment variable not set")
        return False

    if not api_key and not (username and password):
        print("\nERROR: Either PA_API_KEY or PA_USERNAME/PA_PASSWORD must be set")
        return False

    print(f"\nConnecting to firewall: {firewall_ip}")

    try:
        # Initialize API client
        api = PaloAltoAPI(
            host=firewall_ip,
            username=username,
            password=password,
            api_key=api_key,
            verify_ssl=False
        )

        # Test connection
        print("  Testing connection...")
        try:
            info = api.get_system_info()
            print(f"  Connected successfully")
        except Exception as e:
            print(f"  WARNING: Could not get system info: {e}")

        # Check if rule exists
        print(f"\n  Checking for existing rule '{rule_name}'...")
        exists = api.check_rule_exists(rule_name)
        if exists:
            print(f"  Rule exists - will be updated")
        else:
            print(f"  Rule does not exist - will be created")

        # Create/update the rule
        print(f"\n  {'Updating' if exists else 'Creating'} security rule...")
        result = api.create_security_rule(rule, position=rule.get('position', 'bottom'))

        if result['status'] != 'success':
            print(f"  ERROR: Failed to create rule: {result.get('message', 'Unknown error')}")
            return False

        print(f"  Rule {'updated' if exists else 'created'} successfully")

        # Commit changes
        print(f"\n  Committing configuration...")
        commit_desc = f"GitOps deployment - {rule_name} - {datetime.utcnow().isoformat()}"
        commit_result = api.commit(description=commit_desc)

        if commit_result['status'] != 'success':
            print(f"  WARNING: Commit may have failed: {commit_result.get('message', 'Unknown')}")

        job_id = commit_result.get('job_id')
        if job_id:
            print(f"  Commit job ID: {job_id}")
            print("  Waiting for commit to complete...")

            success, message = api.wait_for_commit(job_id)
            if success:
                print(f"  {message}")
            else:
                print(f"  ERROR: {message}")
                return False
        else:
            print("  Commit initiated (no job ID returned)")

        print("\n" + "=" * 70)
        print("DEPLOYMENT SUCCESSFUL")
        print("=" * 70)
        print(f"Rule '{rule_name}' has been deployed to {firewall_ip}")
        print("=" * 70)

        return True

    except Exception as e:
        print(f"\nERROR: Deployment failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Deploy Palo Alto firewall rules via API')
    parser.add_argument('rule_files', nargs='*', help='Rule files to deploy')
    parser.add_argument('--dry-run', action='store_true', help='Simulate deployment without making changes')
    parser.add_argument('--environment', '-e', default='staging', choices=['staging', 'production'],
                        help='Target environment')
    parser.add_argument('--all', action='store_true', help='Deploy all rules in firewall-rules directory')

    args = parser.parse_args()

    # Determine which rule files to process
    rule_files = []

    if args.all:
        rules_dir = Path(__file__).parent.parent / 'firewall-rules'
        rule_files = [str(f) for f in rules_dir.glob('*.json')
                      if 'template' not in f.name.lower()
                      and 'example' not in f.name.lower()
                      and 'sample' not in f.name.lower()]
    elif args.rule_files:
        rule_files = args.rule_files
    else:
        # Default: look for rule files in firewall-rules directory
        rules_dir = Path(__file__).parent.parent / 'firewall-rules'
        rule_files = [str(f) for f in rules_dir.glob('*.json')
                      if 'template' not in f.name.lower()
                      and 'example' not in f.name.lower()
                      and 'sample' not in f.name.lower()]

    if not rule_files:
        print("No rule files found to deploy")
        sys.exit(0)

    print(f"Found {len(rule_files)} rule file(s) to deploy")

    # Deploy each rule
    success_count = 0
    fail_count = 0

    for rule_file in rule_files:
        if not Path(rule_file).exists():
            print(f"WARNING: Rule file not found: {rule_file}")
            fail_count += 1
            continue

        if deploy_rule(rule_file, dry_run=args.dry_run, environment=args.environment):
            success_count += 1
        else:
            fail_count += 1

    # Summary
    print("\n" + "=" * 70)
    print("DEPLOYMENT SUMMARY")
    print("=" * 70)
    print(f"Total:     {len(rule_files)}")
    print(f"Succeeded: {success_count}")
    print(f"Failed:    {fail_count}")
    print("=" * 70)

    sys.exit(0 if fail_count == 0 else 1)


if __name__ == '__main__':
    main()
