#!/usr/bin/env python3
"""
Pytest configuration and fixtures.
"""

import json
import pytest
from pathlib import Path


# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
SCHEMA_FILE = PROJECT_ROOT / "schemas" / "firewall-rule-schema.json"
RULES_DIR = PROJECT_ROOT / "firewall-rules"


@pytest.fixture(scope="session")
def project_root():
    """Return project root path."""
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def schema_file():
    """Return schema file path."""
    return SCHEMA_FILE


@pytest.fixture(scope="session")
def rules_dir():
    """Return rules directory path."""
    return RULES_DIR


@pytest.fixture(scope="session")
def schema():
    """Load and return the JSON schema."""
    with open(SCHEMA_FILE, 'r') as f:
        return json.load(f)


@pytest.fixture(scope="session")
def all_rules():
    """Load all rule files."""
    rules = []
    rule_files = list(RULES_DIR.glob("*.json"))
    for rule_file in sorted(rule_files):
        with open(rule_file, 'r') as f:
            rule = json.load(f)
            rule['_file'] = rule_file.name
            rules.append(rule)
    return rules


@pytest.fixture
def sample_allow_rule():
    """Return a sample allow rule for testing."""
    return {
        "rule_name": "Test-Allow-Rule",
        "description": "Test allow rule",
        "source_zone": ["trust"],
        "destination_zone": ["untrust"],
        "source_address": ["192.168.1.0/24"],
        "destination_address": ["10.0.0.1"],
        "application": ["web-browsing"],
        "service": ["tcp-80"],
        "action": "allow",
        "log_at_session_start": True,
        "log_at_session_end": True,
        "tag": ["test"],
        "metadata": {
            "ticket_id": "TEST-001",
            "requested_by": "Test User",
            "environment": "development"
        }
    }


@pytest.fixture
def sample_deny_rule():
    """Return a sample deny rule for testing."""
    return {
        "rule_name": "Test-Deny-Rule",
        "description": "Test deny rule",
        "source_zone": ["untrust"],
        "destination_zone": ["trust"],
        "source_address": ["any"],
        "destination_address": ["192.168.1.0/24"],
        "application": ["any"],
        "service": ["any"],
        "action": "deny",
        "log_at_session_start": True,
        "log_at_session_end": True,
        "tag": ["test"],
        "metadata": {
            "ticket_id": "TEST-002",
            "requested_by": "Test User",
            "environment": "development"
        }
    }
