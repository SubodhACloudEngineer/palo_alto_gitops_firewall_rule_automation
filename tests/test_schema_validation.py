#!/usr/bin/env python3
"""
Unit tests for firewall rule schema validation.
"""

import json
import pytest
from pathlib import Path
from jsonschema import validate, ValidationError

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
SCHEMA_FILE = PROJECT_ROOT / "schemas" / "firewall-rule-schema.json"
RULES_DIR = PROJECT_ROOT / "firewall-rules"

# Files to exclude from validation (templates, examples, etc.)
EXCLUDED_PATTERNS = ['template', 'example', 'sample', '.bak', '.backup']


def get_rule_files():
    """Get all rule files excluding templates and examples."""
    rule_files = []
    for rule_file in RULES_DIR.glob("*.json"):
        filename_lower = rule_file.name.lower()
        if not any(pattern in filename_lower for pattern in EXCLUDED_PATTERNS):
            rule_files.append(rule_file)
    return rule_files


@pytest.fixture
def schema():
    """Load the JSON schema."""
    with open(SCHEMA_FILE, 'r') as f:
        return json.load(f)


@pytest.fixture
def sample_valid_rule():
    """Return a valid sample rule."""
    return {
        "rule_name": "Test-Rule-001",
        "description": "Test rule for unit testing",
        "source_zone": ["trust"],
        "destination_zone": ["untrust"],
        "source_address": ["192.168.1.0/24"],
        "destination_address": ["10.0.0.1"],
        "application": ["web-browsing"],
        "service": ["tcp-80"],
        "action": "allow",
        "log_at_session_start": True,
        "log_at_session_end": True
    }


class TestSchemaValidation:
    """Test schema validation functionality."""

    def test_schema_file_exists(self):
        """Test that schema file exists."""
        assert SCHEMA_FILE.exists(), "Schema file should exist"

    def test_schema_is_valid_json(self, schema):
        """Test that schema is valid JSON."""
        assert isinstance(schema, dict), "Schema should be a dictionary"
        assert "$schema" in schema, "Schema should have $schema property"

    def test_valid_rule_passes(self, schema, sample_valid_rule):
        """Test that a valid rule passes validation."""
        validate(instance=sample_valid_rule, schema=schema)

    def test_missing_rule_name_fails(self, schema, sample_valid_rule):
        """Test that missing rule_name fails validation."""
        del sample_valid_rule["rule_name"]
        with pytest.raises(ValidationError):
            validate(instance=sample_valid_rule, schema=schema)

    def test_missing_source_zone_fails(self, schema, sample_valid_rule):
        """Test that missing source_zone fails validation."""
        del sample_valid_rule["source_zone"]
        with pytest.raises(ValidationError):
            validate(instance=sample_valid_rule, schema=schema)

    def test_missing_destination_zone_fails(self, schema, sample_valid_rule):
        """Test that missing destination_zone fails validation."""
        del sample_valid_rule["destination_zone"]
        with pytest.raises(ValidationError):
            validate(instance=sample_valid_rule, schema=schema)

    def test_missing_action_fails(self, schema, sample_valid_rule):
        """Test that missing action fails validation."""
        del sample_valid_rule["action"]
        with pytest.raises(ValidationError):
            validate(instance=sample_valid_rule, schema=schema)

    def test_invalid_action_fails(self, schema, sample_valid_rule):
        """Test that invalid action fails validation."""
        sample_valid_rule["action"] = "invalid_action"
        with pytest.raises(ValidationError):
            validate(instance=sample_valid_rule, schema=schema)

    def test_valid_actions(self, schema, sample_valid_rule):
        """Test all valid action values."""
        valid_actions = ["allow", "deny", "drop", "reset-client", "reset-server", "reset-both"]
        for action in valid_actions:
            sample_valid_rule["action"] = action
            validate(instance=sample_valid_rule, schema=schema)

    def test_empty_source_zone_fails(self, schema, sample_valid_rule):
        """Test that empty source_zone array fails validation."""
        sample_valid_rule["source_zone"] = []
        with pytest.raises(ValidationError):
            validate(instance=sample_valid_rule, schema=schema)

    def test_empty_destination_address_fails(self, schema, sample_valid_rule):
        """Test that empty destination_address array fails validation."""
        sample_valid_rule["destination_address"] = []
        with pytest.raises(ValidationError):
            validate(instance=sample_valid_rule, schema=schema)


class TestRuleFiles:
    """Test existing rule files in the repository."""

    def test_rules_directory_exists(self):
        """Test that rules directory exists."""
        assert RULES_DIR.exists(), "Rules directory should exist"

    def test_all_rule_files_valid_json(self):
        """Test that all rule files are valid JSON."""
        rule_files = get_rule_files()
        assert len(rule_files) > 0, "Should have at least one rule file"

        for rule_file in rule_files:
            with open(rule_file, 'r') as f:
                try:
                    json.load(f)
                except json.JSONDecodeError as e:
                    pytest.fail(f"Invalid JSON in {rule_file.name}: {e}")

    def test_all_rule_files_pass_schema(self, schema):
        """Test that all rule files pass schema validation."""
        rule_files = get_rule_files()

        for rule_file in rule_files:
            with open(rule_file, 'r') as f:
                rule_data = json.load(f)

            try:
                validate(instance=rule_data, schema=schema)
            except ValidationError as e:
                pytest.fail(f"Schema validation failed for {rule_file.name}: {e.message}")

    def test_all_rules_have_required_fields(self):
        """Test that all rules have the minimum required fields."""
        required_fields = ["rule_name", "source_zone", "destination_zone",
                          "source_address", "destination_address", "action"]

        rule_files = get_rule_files()

        for rule_file in rule_files:
            with open(rule_file, 'r') as f:
                rule_data = json.load(f)

            for field in required_fields:
                assert field in rule_data, f"Rule {rule_file.name} missing required field: {field}"

    def test_all_rules_have_unique_names(self):
        """Test that all rule names are unique."""
        rule_files = get_rule_files()
        rule_names = []

        for rule_file in rule_files:
            with open(rule_file, 'r') as f:
                rule_data = json.load(f)
            rule_names.append(rule_data.get("rule_name"))

        assert len(rule_names) == len(set(rule_names)), "All rule names should be unique"
