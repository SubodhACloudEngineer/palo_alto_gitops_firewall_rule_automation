#!/usr/bin/env python3
"""
AWX REST API Client for Self-Service Portal

CD-only: the container image is pre-built in the registry.
AWX receives the image tag as an extra_var and handles deployment only.
"""

import os
import re
import time
import logging
import requests
from urllib3.exceptions import InsecureRequestWarning
from dotenv import load_dotenv

# Suppress SSL warnings when AWX_VERIFY_SSL=false
requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

# Load .env file
load_dotenv(os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env'))

# Logging
logger = logging.getLogger(__name__)

# Configuration
AWX_HOST = os.environ.get('AWX_HOST', 'https://awx.internal.example.com').rstrip('/')
AWX_TOKEN = os.environ.get('AWX_TOKEN', '')
AWX_VERIFY_SSL = os.environ.get('AWX_VERIFY_SSL', 'true').lower() in ('true', '1', 'yes')

# Module-level session
_session = requests.Session()
_session.headers.update({
    'Authorization': f'Token {AWX_TOKEN}',
    'Content-Type': 'application/json',
    'Accept': 'application/json',
})
_session.verify = AWX_VERIFY_SSL

TIMEOUT = 10


def trigger_job(template_name: str, extra_vars: dict) -> str:
    """
    Launch an AWX job template by name.

    Steps:
      1. GET /api/v2/job_templates/?name=<template_name>
         → parse results[0].id to get the template id
         → raise ValueError with clear message if not found
      2. POST /api/v2/job_templates/<id>/launch/
         body: { "extra_vars": extra_vars }
         → parse response for job id
         → raise RuntimeError if launch fails (non-2xx)

    Returns: job_id as string
    """
    # Step 1: Look up template by name
    search_url = f'{AWX_HOST}/api/v2/job_templates/?name={requests.utils.quote(template_name)}'
    logger.debug(f'GET {search_url}')
    resp = _session.get(search_url, timeout=TIMEOUT)

    if resp.status_code != 200:
        logger.error(f'Template lookup failed: HTTP {resp.status_code}')
        raise RuntimeError(f'Template lookup failed: HTTP {resp.status_code}')

    results = resp.json().get('results', [])
    if not results:
        logger.error(f'Job template not found: {template_name}')
        raise ValueError(f"Job template '{template_name}' not found in AWX")

    template_id = results[0]['id']

    # Step 2: Launch the job
    launch_url = f'{AWX_HOST}/api/v2/job_templates/{template_id}/launch/'
    logger.debug(f'POST {launch_url}')
    resp = _session.post(launch_url, json={'extra_vars': extra_vars}, timeout=TIMEOUT)

    if resp.status_code not in (200, 201):
        logger.error(f'Job launch failed: HTTP {resp.status_code} - {resp.text}')
        raise RuntimeError(f'Job launch failed: HTTP {resp.status_code}')

    job_id = str(resp.json()['id'])
    logger.info(f'Job launched: template="{template_name}" job_id={job_id}')
    return job_id


def get_job_status(job_id: str) -> dict:
    """
    GET /api/v2/jobs/<job_id>/

    Returns dict:
      {
        "status":   "pending|waiting|running|successful|failed|canceled",
        "finished": bool,
        "elapsed":  float
      }
    """
    url = f'{AWX_HOST}/api/v2/jobs/{job_id}/'
    logger.debug(f'GET {url}')
    resp = _session.get(url, timeout=TIMEOUT)

    if resp.status_code != 200:
        raise RuntimeError(f'get_job_status failed: HTTP {resp.status_code}')

    data = resp.json()
    return {
        'status': data.get('status', 'unknown'),
        'finished': data.get('finished') is not None,
        'elapsed': float(data.get('elapsed', 0.0)),
    }


def stream_job_log(job_id: str):
    """
    Generator function. Streams AWX job stdout incrementally.

    Method:
      - Poll GET /api/v2/jobs/<job_id>/stdout/?format=txt every 2 seconds
      - Track a byte offset (start at 0)
      - Each poll: send Range header → bytes=<offset>-
      - Parse response: extract new content, update offset
      - Split new content into lines, yield each non-empty line as string

    Termination:
      - After each poll, call get_job_status(job_id)
      - When status is "successful" or "failed" or "canceled":
          - Do one final stdout poll to capture remaining lines
          - Scan all yielded lines for a line containing "DEPLOYED_URL:"
            extract the URL after the colon, strip whitespace
          - Yield a final dict:
              { "status": "done", "url": "<extracted_url>" }   if successful
              { "status": "failed", "url": "" }                if failed/canceled
          - Then return (stop generator)

    Error handling:
      - If any request throws an exception, yield the error message as a
        log line string, then yield { "status": "failed", "url": "" }
      - Never raise — always yield and return cleanly
    """
    stdout_url = f'{AWX_HOST}/api/v2/jobs/{job_id}/stdout/?format=txt'
    byte_offset = 0
    all_lines = []

    try:
        while True:
            # Poll stdout with Range header
            try:
                logger.debug(f'GET {stdout_url} (Range: bytes={byte_offset}-)')
                resp = _session.get(
                    stdout_url,
                    headers={'Range': f'bytes={byte_offset}-'},
                    timeout=TIMEOUT
                )

                if resp.status_code in (200, 206):
                    chunk = resp.text
                    if chunk:
                        byte_offset += len(chunk.encode('utf-8'))
                        for line in chunk.splitlines():
                            if line:
                                all_lines.append(line)
                                yield line

            except Exception as e:
                logger.error(f'Error fetching stdout: {e}')
                yield f'[ERROR] Failed to fetch logs: {e}'
                yield {'status': 'failed', 'url': ''}
                return

            # Check job status
            try:
                status = get_job_status(job_id)
            except Exception as e:
                logger.error(f'Error checking job status: {e}')
                yield f'[ERROR] Failed to check job status: {e}'
                yield {'status': 'failed', 'url': ''}
                return

            # Check if job finished
            if status['status'] in ('successful', 'failed', 'canceled'):
                # Final stdout poll
                try:
                    logger.debug(f'GET {stdout_url} (final poll, Range: bytes={byte_offset}-)')
                    resp = _session.get(
                        stdout_url,
                        headers={'Range': f'bytes={byte_offset}-'},
                        timeout=TIMEOUT
                    )
                    if resp.status_code in (200, 206) and resp.text:
                        for line in resp.text.splitlines():
                            if line:
                                all_lines.append(line)
                                yield line
                except Exception as e:
                    logger.error(f'Error in final stdout poll: {e}')

                # Extract DEPLOYED_URL from all lines
                deployed_url = ''
                for line in all_lines:
                    if 'DEPLOYED_URL:' in line:
                        match = re.search(r'DEPLOYED_URL:\s*(\S+)', line)
                        if match:
                            deployed_url = match.group(1).strip()
                            logger.info(f'Extracted deployed URL: {deployed_url}')
                            break

                # Yield final status
                if status['status'] == 'successful':
                    yield {'status': 'done', 'url': deployed_url}
                else:
                    yield {'status': 'failed', 'url': ''}
                return

            time.sleep(2)

    except Exception as e:
        logger.error(f'Unexpected error in stream_job_log: {e}')
        yield f'[ERROR] Unexpected error: {e}'
        yield {'status': 'failed', 'url': ''}
        return


if __name__ == '__main__':
    import sys
    import json

    logging.basicConfig(
        level=logging.DEBUG,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    print('AWX Client')
    print('=' * 40)
    print(f'Host:       {AWX_HOST}')
    print(f'Token set:  {"yes" if AWX_TOKEN else "NO — set AWX_TOKEN"}')
    print(f'Verify SSL: {AWX_VERIFY_SSL}')
    print()

    cmd = sys.argv[1] if len(sys.argv) > 1 else 'help'

    if cmd == 'test':
        url = f'{AWX_HOST}/api/v2/ping/'
        resp = _session.get(url, timeout=TIMEOUT)
        print('OK' if resp.status_code == 200 else f'FAILED: HTTP {resp.status_code}')

    elif cmd == 'templates':
        url = f'{AWX_HOST}/api/v2/job_templates/'
        resp = _session.get(url, timeout=TIMEOUT)
        for t in resp.json().get('results', []):
            print(f'  [{t["id"]}] {t["name"]}')

    elif cmd == 'trigger' and len(sys.argv) > 2:
        job_id = trigger_job(sys.argv[2], {})
        print(f'Job ID: {job_id}')

    elif cmd == 'status' and len(sys.argv) > 2:
        s = get_job_status(sys.argv[2])
        print(json.dumps(s, indent=2))

    elif cmd == 'logs' and len(sys.argv) > 2:
        for item in stream_job_log(sys.argv[2]):
            if isinstance(item, dict):
                print('---')
                print(json.dumps(item, indent=2))
            else:
                print(item)

    else:
        print('Usage:')
        print('  python awx_client.py test')
        print('  python awx_client.py templates')
        print('  python awx_client.py trigger <template-name>')
        print('  python awx_client.py status <job-id>')
        print('  python awx_client.py logs <job-id>')
