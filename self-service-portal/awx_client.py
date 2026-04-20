#!/usr/bin/env python3
"""
AWX REST API Client for Self-Service Portal

CD-only: the container image is pre-built in the registry.
AWX receives the image tag as an extra_var and handles deployment only.
"""

import os
import re
import time
import json
import logging
import requests
from urllib3.exceptions import InsecureRequestWarning

requests.packages.urllib3.disable_warnings(category=InsecureRequestWarning)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('awx_client')

TIMEOUT = 10


# ============================================
# CONFIGURATION
# ============================================

def _load_env_file():
    env_file = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
    if os.path.exists(env_file):
        with open(env_file, 'r') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith('#') and '=' in line:
                    key, value = line.split('=', 1)
                    if key.strip() not in os.environ:
                        os.environ[key.strip()] = value.strip().strip('"').strip("'")


_load_env_file()


def _config():
    return {
        'host':       os.environ.get('AWX_HOST', 'https://awx.example.com').rstrip('/'),
        'token':      os.environ.get('AWX_TOKEN', ''),
        'verify_ssl': os.environ.get('AWX_VERIFY_SSL', 'true').lower() in ('true', '1', 'yes'),
    }


def _headers(extra=None):
    cfg = _config()
    h = {
        'Authorization': f'Token {cfg["token"]}',
        'Content-Type':  'application/json',
        'Accept':        'application/json',
    }
    if extra:
        h.update(extra)
    return h


def _get(endpoint, extra_headers=None):
    cfg = _config()
    url = cfg['host'] + endpoint
    return requests.get(
        url,
        headers=_headers(extra_headers),
        verify=cfg['verify_ssl'],
        timeout=TIMEOUT,
    )


def _post(endpoint, payload):
    cfg = _config()
    url = cfg['host'] + endpoint
    return requests.post(
        url,
        headers=_headers(),
        json=payload,
        verify=cfg['verify_ssl'],
        timeout=TIMEOUT,
    )


# ============================================
# PUBLIC FUNCTIONS
# ============================================

def trigger_job(template_name: str, extra_vars: dict) -> str:
    """
    Launch an AWX job template by name.

    Steps:
      1. GET /api/v2/job_templates/?name=<template_name>  → get template id
      2. POST /api/v2/job_templates/<id>/launch/  with body: {"extra_vars": extra_vars}

    Returns job_id as string. Raises ValueError if template not found.
    """
    # Step 1: resolve template name → id
    search = f'/api/v2/job_templates/?name={requests.utils.quote(template_name)}'
    resp = _get(search)

    if resp.status_code == 401:
        raise PermissionError('AWX authentication failed — check AWX_TOKEN')
    if resp.status_code != 200:
        raise RuntimeError(f'Template lookup failed: HTTP {resp.status_code}')

    results = resp.json().get('results', [])
    if not results:
        raise ValueError(f"Job template '{template_name}' not found in AWX")

    template_id = results[0]['id']
    logger.info(f'Launching template "{template_name}" (id={template_id}) extra_vars={extra_vars}')

    # Step 2: launch
    resp = _post(f'/api/v2/job_templates/{template_id}/launch/', {'extra_vars': extra_vars})

    if resp.status_code == 401:
        raise PermissionError('AWX authentication failed during job launch')
    if resp.status_code == 400:
        detail = resp.json().get('detail', resp.text)
        raise RuntimeError(f'Job launch rejected: {detail}')
    if resp.status_code not in (200, 201):
        raise RuntimeError(f'Job launch failed: HTTP {resp.status_code}')

    job_id = str(resp.json()['id'])
    logger.info(f'Job launched: id={job_id}')
    return job_id


def get_job_status(job_id: str) -> dict:
    """
    GET /api/v2/jobs/<job_id>/

    Returns:
        {
            "status":   "pending|waiting|running|successful|failed|canceled",
            "finished": bool,
            "elapsed":  float,
        }
    """
    resp = _get(f'/api/v2/jobs/{job_id}/')

    if resp.status_code == 404:
        raise LookupError(f'Job {job_id} not found')
    if resp.status_code != 200:
        raise RuntimeError(f'get_job_status failed: HTTP {resp.status_code}')

    data = resp.json()
    return {
        'status':   data.get('status', 'unknown'),
        'finished': data.get('finished') is not None,
        'elapsed':  float(data.get('elapsed', 0.0)),
    }


def stream_job_log(job_id: str):
    """
    Generator. Polls GET /api/v2/jobs/<job_id>/stdout/?format=txt using byte-range
    offsets to fetch only new content each poll. Yields log lines as strings every
    2 seconds.

    When the job finishes, scans the final stdout for:
        'deployed_url = <url>'  or  'DEPLOYED_URL: <url>'

    Yields a final dict: { "status": "done"|"failed", "url": "<url>"|"" }
    then stops.
    """
    endpoint = f'/api/v2/jobs/{job_id}/stdout/?format=txt'
    byte_offset = 0
    deployed_url = ''

    _URL_RE = re.compile(
        r'(?:deployed_url\s*=\s*|DEPLOYED_URL:\s*)["\']?(https?://[^\s"\']+)',
        re.IGNORECASE,
    )

    while True:
        # Fetch only new bytes since last poll
        resp = _get(endpoint, extra_headers={'Range': f'bytes={byte_offset}-'})

        if resp.status_code in (200, 206):
            chunk = resp.text
            if chunk:
                byte_offset += len(chunk.encode('utf-8'))
                for line in chunk.splitlines():
                    yield line
                    m = _URL_RE.search(line)
                    if m:
                        deployed_url = m.group(1)
                        logger.info(f'Detected deployed URL: {deployed_url}')

        # Check completion
        try:
            status = get_job_status(job_id)
        except Exception as e:
            logger.warning(f'Status check error (will retry): {e}')
            time.sleep(2)
            continue

        if status['finished']:
            final = 'done' if status['status'] == 'successful' else 'failed'
            logger.info(f'Job {job_id} finished: {final}')
            yield {'status': final, 'url': deployed_url}
            return

        time.sleep(2)


# ============================================
# CLI
# ============================================

if __name__ == '__main__':
    import sys

    cfg = _config()
    print('AWX Client')
    print('=' * 40)
    print(f'Host:       {cfg["host"]}')
    print(f'Token set:  {"yes" if cfg["token"] else "NO — set AWX_TOKEN"}')
    print(f'Verify SSL: {cfg["verify_ssl"]}')
    print()

    cmd = sys.argv[1] if len(sys.argv) > 1 else 'help'

    if cmd == 'test':
        resp = _get('/api/v2/ping/')
        print('OK' if resp.status_code == 200 else f'FAILED: HTTP {resp.status_code}')

    elif cmd == 'templates':
        resp = _get('/api/v2/job_templates/')
        for t in resp.json().get('results', []):
            print(f'  [{t["id"]}] {t["name"]}')

    elif cmd == 'trigger' and len(sys.argv) > 2:
        jid = trigger_job(sys.argv[2], {})
        print(f'Job ID: {jid}')

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
