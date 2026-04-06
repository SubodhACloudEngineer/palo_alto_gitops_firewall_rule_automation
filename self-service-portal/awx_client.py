#!/usr/bin/env python3
"""
AWX REST API Client for Self-Service Portal
Provides functions to trigger job templates, check job status, and stream logs.
"""

import os
import re
import time
import logging
import requests
from typing import Generator, Optional
from urllib3.exceptions import InsecureRequestWarning

# Suppress SSL warnings when AWX_VERIFY_SSL is False
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# ============================================
# LOGGING CONFIGURATION
# ============================================

# Configure logging to match app.py style
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('awx_client')


# ============================================
# CONFIGURATION
# ============================================

def load_env_file():
    """Load environment variables from .env file"""
    env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    if key.strip() not in os.environ:
                        os.environ[key.strip()] = value.strip().strip('"').strip("'")


# Load .env on module import
load_env_file()


def get_config():
    """Get AWX configuration from environment variables"""
    return {
        'host': os.environ.get('AWX_HOST', 'https://awx.example.com').rstrip('/'),
        'token': os.environ.get('AWX_TOKEN', ''),
        'verify_ssl': os.environ.get('AWX_VERIFY_SSL', 'true').lower() in ('true', '1', 'yes'),
    }


# ============================================
# AWX API CLIENT CLASS
# ============================================

class AWXClient:
    """Client for interacting with AWX REST API"""

    def __init__(self):
        config = get_config()
        self.host = config['host']
        self.token = config['token']
        self.verify_ssl = config['verify_ssl']
        self.timeout = 10
        self.headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
        }

    def _request(self, method: str, endpoint: str, **kwargs) -> requests.Response:
        """Make HTTP request to AWX API"""
        url = f"{self.host}{endpoint}"
        kwargs.setdefault('timeout', self.timeout)
        kwargs.setdefault('verify', self.verify_ssl)
        kwargs.setdefault('headers', self.headers)

        logger.debug(f"AWX API {method} {url}")

        try:
            response = requests.request(method, url, **kwargs)
            return response
        except requests.exceptions.Timeout:
            logger.error(f"AWX API request timeout: {method} {url}")
            raise AWXError(f"Request to AWX timed out after {self.timeout} seconds")
        except requests.exceptions.ConnectionError as e:
            logger.error(f"AWX API connection error: {e}")
            raise AWXError(f"Failed to connect to AWX at {self.host}: {e}")
        except requests.exceptions.RequestException as e:
            logger.error(f"AWX API request error: {e}")
            raise AWXError(f"AWX API request failed: {e}")

    def get(self, endpoint: str, **kwargs) -> requests.Response:
        """Make GET request"""
        return self._request('GET', endpoint, **kwargs)

    def post(self, endpoint: str, **kwargs) -> requests.Response:
        """Make POST request"""
        return self._request('POST', endpoint, **kwargs)


# ============================================
# EXCEPTIONS
# ============================================

class AWXError(Exception):
    """Base exception for AWX client errors"""
    pass


class AWXTemplateNotFoundError(AWXError):
    """Raised when job template is not found"""
    pass


class AWXJobLaunchError(AWXError):
    """Raised when job launch fails"""
    pass


class AWXAuthenticationError(AWXError):
    """Raised when authentication fails"""
    pass


# ============================================
# MODULE-LEVEL FUNCTIONS
# ============================================

def trigger_job(template_name: str, extra_vars: dict) -> str:
    """
    Calls the AWX REST API to launch a job template by name.

    Args:
        template_name: Name of the job template to launch
        extra_vars: Dictionary of extra variables to pass to the job

    Returns:
        The job_id as a string

    Raises:
        AWXTemplateNotFoundError: If template is not found
        AWXJobLaunchError: If job launch fails
        AWXAuthenticationError: If authentication fails
        AWXError: For other API errors
    """
    client = AWXClient()

    if not client.token:
        logger.error("AWX_TOKEN not configured")
        raise AWXAuthenticationError("AWX_TOKEN environment variable is not set")

    # Step 1: Find the job template by name
    logger.info(f"Looking up job template: {template_name}")
    search_endpoint = f"/api/v2/job_templates/?name={requests.utils.quote(template_name)}"

    response = client.get(search_endpoint)

    if response.status_code == 401:
        logger.error("AWX authentication failed - invalid token")
        raise AWXAuthenticationError("AWX authentication failed. Check your AWX_TOKEN.")

    if response.status_code == 403:
        logger.error("AWX authorization failed - insufficient permissions")
        raise AWXAuthenticationError("AWX authorization failed. Token lacks required permissions.")

    if response.status_code != 200:
        logger.error(f"AWX API error: {response.status_code} - {response.text}")
        raise AWXError(f"Failed to search job templates: HTTP {response.status_code}")

    data = response.json()
    results = data.get('results', [])

    if not results:
        logger.error(f"Job template not found: {template_name}")
        raise AWXTemplateNotFoundError(f"Job template '{template_name}' not found in AWX")

    template = results[0]
    template_id = template['id']
    logger.info(f"Found job template: {template_name} (ID: {template_id})")

    # Step 2: Launch the job template
    launch_endpoint = f"/api/v2/job_templates/{template_id}/launch/"
    payload = {}

    if extra_vars:
        payload['extra_vars'] = extra_vars

    logger.info(f"Launching job template {template_name} with extra_vars: {extra_vars}")
    response = client.post(launch_endpoint, json=payload)

    if response.status_code == 401:
        logger.error("AWX authentication failed during job launch")
        raise AWXAuthenticationError("AWX authentication failed during job launch.")

    if response.status_code == 400:
        error_detail = response.json().get('detail', response.text)
        logger.error(f"AWX job launch failed (bad request): {error_detail}")
        raise AWXJobLaunchError(f"Job launch failed: {error_detail}")

    if response.status_code not in (200, 201):
        logger.error(f"AWX job launch failed: {response.status_code} - {response.text}")
        raise AWXJobLaunchError(f"Failed to launch job: HTTP {response.status_code}")

    job_data = response.json()
    job_id = str(job_data['id'])

    logger.info(f"Job launched successfully: ID {job_id}")
    return job_id


def get_job_status(job_id: str) -> dict:
    """
    Returns job status information.

    Args:
        job_id: The AWX job ID

    Returns:
        Dict with keys:
            - status: "pending" | "running" | "successful" | "failed"
            - finished: bool

    Raises:
        AWXError: If API request fails
    """
    client = AWXClient()

    if not client.token:
        logger.error("AWX_TOKEN not configured")
        raise AWXAuthenticationError("AWX_TOKEN environment variable is not set")

    endpoint = f"/api/v2/jobs/{job_id}/"
    response = client.get(endpoint)

    if response.status_code == 404:
        logger.error(f"Job not found: {job_id}")
        raise AWXError(f"Job {job_id} not found")

    if response.status_code != 200:
        logger.error(f"Failed to get job status: {response.status_code}")
        raise AWXError(f"Failed to get job status: HTTP {response.status_code}")

    data = response.json()

    # AWX status values: pending, waiting, running, successful, failed, error, canceled
    awx_status = data.get('status', 'unknown')
    finished = data.get('finished') is not None

    # Normalize status for our interface
    status_map = {
        'pending': 'pending',
        'waiting': 'pending',
        'running': 'running',
        'successful': 'successful',
        'failed': 'failed',
        'error': 'failed',
        'canceled': 'failed',
    }

    normalized_status = status_map.get(awx_status, 'pending')

    return {
        'status': normalized_status,
        'finished': finished,
    }


def stream_job_log(job_id: str) -> Generator[str | dict, None, None]:
    """
    Generator function that streams job output logs.

    Polls GET /api/v2/jobs/<job_id>/stdout/?format=txt every 2 seconds.
    Tracks character offset to yield only NEW lines each poll.

    Yields:
        str: Log lines as they appear
        dict: Final status dict when job completes:
              { "status": "done"|"failed", "url": "..." }
              (url extracted from "deployed_url = ..." in logs)

    Raises:
        AWXError: If API request fails
    """
    client = AWXClient()

    if not client.token:
        logger.error("AWX_TOKEN not configured")
        raise AWXAuthenticationError("AWX_TOKEN environment variable is not set")

    last_offset = 0
    poll_interval = 2
    deployed_url: Optional[str] = None
    all_output = ""

    logger.info(f"Starting log stream for job {job_id}")

    while True:
        # Get job output
        endpoint = f"/api/v2/jobs/{job_id}/stdout/?format=txt"
        try:
            response = client.get(endpoint)

            if response.status_code != 200:
                logger.warning(f"Failed to get job output: {response.status_code}")
            else:
                content = response.text

                # Yield only new content since last poll
                if len(content) > last_offset:
                    new_content = content[last_offset:]
                    all_output += new_content
                    last_offset = len(content)

                    # Yield each new line
                    for line in new_content.splitlines():
                        yield line

                        # Check for deployed_url pattern in Ansible debug output
                        # Pattern: "deployed_url = https://..." or similar
                        url_match = re.search(r'deployed_url\s*[=:]\s*["\']?(https?://[^\s"\']+)', line)
                        if url_match:
                            deployed_url = url_match.group(1)
                            logger.info(f"Found deployed URL: {deployed_url}")

        except AWXError as e:
            logger.warning(f"Error fetching job output: {e}")

        # Check job status
        try:
            status = get_job_status(job_id)

            if status['finished']:
                final_status = 'done' if status['status'] == 'successful' else 'failed'
                logger.info(f"Job {job_id} finished with status: {final_status}")

                # Yield final status dict
                yield {
                    'status': final_status,
                    'url': deployed_url,
                }
                return

        except AWXError as e:
            logger.warning(f"Error checking job status: {e}")

        # Wait before next poll
        time.sleep(poll_interval)


# ============================================
# UTILITY FUNCTIONS
# ============================================

def test_connection() -> bool:
    """
    Test AWX connection and authentication.

    Returns:
        True if connection is successful, False otherwise
    """
    client = AWXClient()

    if not client.token:
        logger.error("AWX_TOKEN not configured")
        return False

    try:
        response = client.get("/api/v2/ping/")
        if response.status_code == 200:
            logger.info("AWX connection test successful")
            return True
        else:
            logger.error(f"AWX connection test failed: HTTP {response.status_code}")
            return False
    except AWXError as e:
        logger.error(f"AWX connection test failed: {e}")
        return False


def list_job_templates() -> list:
    """
    List all available job templates.

    Returns:
        List of dicts with 'id', 'name', 'description' keys

    Raises:
        AWXError: If API request fails
    """
    client = AWXClient()

    if not client.token:
        raise AWXAuthenticationError("AWX_TOKEN environment variable is not set")

    response = client.get("/api/v2/job_templates/")

    if response.status_code != 200:
        raise AWXError(f"Failed to list job templates: HTTP {response.status_code}")

    data = response.json()
    templates = []

    for template in data.get('results', []):
        templates.append({
            'id': template['id'],
            'name': template['name'],
            'description': template.get('description', ''),
        })

    return templates


# ============================================
# CLI INTERFACE (for testing)
# ============================================

if __name__ == '__main__':
    import sys

    print("AWX Client - Connection Test")
    print("=" * 40)

    config = get_config()
    print(f"AWX Host: {config['host']}")
    print(f"Token configured: {'Yes' if config['token'] else 'No'}")
    print(f"Verify SSL: {config['verify_ssl']}")
    print()

    if len(sys.argv) > 1:
        command = sys.argv[1]

        if command == 'test':
            print("Testing connection...")
            if test_connection():
                print("✓ Connection successful")
            else:
                print("✗ Connection failed")

        elif command == 'templates':
            print("Listing job templates...")
            try:
                templates = list_job_templates()
                for t in templates:
                    print(f"  [{t['id']}] {t['name']}")
            except AWXError as e:
                print(f"Error: {e}")

        elif command == 'trigger' and len(sys.argv) > 2:
            template_name = sys.argv[2]
            print(f"Triggering job template: {template_name}")
            try:
                job_id = trigger_job(template_name, {})
                print(f"✓ Job launched: {job_id}")
            except AWXError as e:
                print(f"✗ Error: {e}")

        elif command == 'status' and len(sys.argv) > 2:
            job_id = sys.argv[2]
            print(f"Getting status for job: {job_id}")
            try:
                status = get_job_status(job_id)
                print(f"  Status: {status['status']}")
                print(f"  Finished: {status['finished']}")
            except AWXError as e:
                print(f"✗ Error: {e}")

        elif command == 'logs' and len(sys.argv) > 2:
            job_id = sys.argv[2]
            print(f"Streaming logs for job: {job_id}")
            print("-" * 40)
            try:
                for item in stream_job_log(job_id):
                    if isinstance(item, dict):
                        print("-" * 40)
                        print(f"Final status: {item['status']}")
                        if item.get('url'):
                            print(f"Deployed URL: {item['url']}")
                    else:
                        print(item)
            except AWXError as e:
                print(f"✗ Error: {e}")

        else:
            print("Usage:")
            print("  python awx_client.py test              # Test connection")
            print("  python awx_client.py templates         # List job templates")
            print("  python awx_client.py trigger <name>    # Trigger a job template")
            print("  python awx_client.py status <job_id>   # Get job status")
            print("  python awx_client.py logs <job_id>     # Stream job logs")
    else:
        print("Run with 'test' argument to test connection:")
        print("  python awx_client.py test")
