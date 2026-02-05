#!/usr/bin/env python3
"""
Unit tests for security policy validation.
"""

import json
import pytest
import warnings
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
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


class TestSecurityPolicies:
    """Test security policy compliance."""

    def get_all_rules(self):
        """Load all rule files excluding templates."""
        rules = []
        rule_files = get_rule_files()
        for rule_file in rule_files:
            with open(rule_file, 'r') as f:
                rule = json.load(f)
                rule['_file'] = rule_file.name
                rules.append(rule)
        return rules

    def test_all_rules_have_description(self):
        """Test that all rules have a description."""
        rules = self.get_all_rules()

        for rule in rules:
            description = rule.get("description", "")
            assert len(description) > 0, f"Rule {rule['_file']} should have a description"

    def test_allow_rules_have_logging(self):
        """Test that allow rules have logging enabled."""
        rules = self.get_all_rules()

        for rule in rules:
            if rule.get("action") == "allow":
                log_start = rule.get("log_at_session_start", False)
                log_end = rule.get("log_at_session_end", True)

                # At least one logging option should be enabled
                assert log_start or log_end, \
                    f"Rule {rule['_file']} should have logging enabled"

    def test_deny_rules_configured_correctly(self):
        """Test that deny rules are configured correctly."""
        rules = self.get_all_rules()

        for rule in rules:
            if rule.get("action") in ["deny", "drop"]:
                # Deny rules should have logging enabled
                log_end = rule.get("log_at_session_end", True)
                assert log_end, f"Deny rule {rule['_file']} should log denied traffic"

    def test_no_restricted_applications_allowed(self):
        """Test that restricted applications are not allowed."""
        restricted_apps = ["bittorrent", "tor", "unknown-tcp", "unknown-udp"]
        rules = self.get_all_rules()

        for rule in rules:
            if rule.get("action") == "allow":
                apps = [a.lower() for a in rule.get("application", [])]
                for restricted in restricted_apps:
                    assert restricted not in apps, \
                        f"Rule {rule['_file']} allows restricted application: {restricted}"

    def test_rules_have_tags(self):
        """Test that rules have tags for organization."""
        rules = self.get_all_rules()

        for rule in rules:
            tags = rule.get("tag", [])
            assert len(tags) > 0, f"Rule {rule['_file']} should have at least one tag"

    def test_rules_have_gitops_tag(self):
        """Test that all rules have gitops-managed tag."""
        rules = self.get_all_rules()

        for rule in rules:
            tags = [t.lower() for t in rule.get("tag", [])]
            # Check for any gitops-related tag
            gitops_tags = ["gitops-managed", "gitops-demo", "auto-deployed", "gitops"]
            has_gitops_tag = any(tag in tags for tag in gitops_tags)
            assert has_gitops_tag, \
                f"Rule {rule['_file']} should have a gitops-related tag"


class TestMetadataCompliance:
    """Test metadata compliance for audit purposes.

    Note: These tests are advisory (warnings) not mandatory (failures).
    Missing metadata fields will generate warnings but won't block deployment.
    """

    def get_all_rules(self):
        """Load all rule files excluding templates."""
        rules = []
        rule_files = get_rule_files()
        for rule_file in rule_files:
            with open(rule_file, 'r') as f:
                rule = json.load(f)
                rule['_file'] = rule_file.name
                rules.append(rule)
        return rules

    def test_rules_have_metadata(self):
        """Test that rules have metadata section (advisory)."""
        rules = self.get_all_rules()
        missing_metadata = []

        for rule in rules:
            if "metadata" not in rule:
                missing_metadata.append(rule['_file'])

        if missing_metadata:
            warnings.warn(f"Rules missing metadata section: {', '.join(missing_metadata)}")

    def test_metadata_has_ticket_id(self):
        """Test that metadata includes ticket ID for audit trail (advisory)."""
        rules = self.get_all_rules()
        missing_ticket_id = []

        for rule in rules:
            metadata = rule.get("metadata", {})
            ticket_id = metadata.get("ticket_id", "")
            if not ticket_id:
                missing_ticket_id.append(rule['_file'])

        if missing_ticket_id:
            warnings.warn(f"Rules missing ticket_id in metadata: {', '.join(missing_ticket_id)}")

    def test_metadata_has_requested_by(self):
        """Test that metadata includes who requested the rule (advisory)."""
        rules = self.get_all_rules()
        missing_requested_by = []

        for rule in rules:
            metadata = rule.get("metadata", {})
            requested_by = metadata.get("requested_by", "")
            if not requested_by:
                missing_requested_by.append(rule['_file'])

        if missing_requested_by:
            warnings.warn(f"Rules missing requested_by in metadata: {', '.join(missing_requested_by)}")

    def test_metadata_has_environment(self):
        """Test that metadata includes target environment (advisory)."""
        rules = self.get_all_rules()
        missing_environment = []

        for rule in rules:
            metadata = rule.get("metadata", {})
            environment = metadata.get("environment", "")
            if not environment:
                missing_environment.append(rule['_file'])

        if missing_environment:
            warnings.warn(f"Rules missing environment in metadata: {', '.join(missing_environment)}")

    def test_valid_environment_values(self):
        """Test that environment values are valid (advisory)."""
        valid_environments = ["production", "staging", "development", "all"]
        rules = self.get_all_rules()
        invalid_environments = []

        for rule in rules:
            metadata = rule.get("metadata", {})
            environment = metadata.get("environment", "").lower()
            if environment and environment not in valid_environments:
                invalid_environments.append(f"{rule['_file']}: {environment}")

        if invalid_environments:
            warnings.warn(f"Rules with invalid environment values: {', '.join(invalid_environments)}")


class TestRuleNaming:
    """Test rule naming conventions."""

    def get_all_rules(self):
        """Load all rule files excluding templates."""
        rules = []
        rule_files = get_rule_files()
        for rule_file in rule_files:
            with open(rule_file, 'r') as f:
                rule = json.load(f)
                rule['_file'] = rule_file.name
                rules.append(rule)
        return rules

    def test_rule_names_not_empty(self):
        """Test that rule names are not empty."""
        rules = self.get_all_rules()

        for rule in rules:
            rule_name = rule.get("rule_name", "")
            assert len(rule_name) > 0, f"Rule in {rule['_file']} has empty name"

    def test_rule_names_no_spaces(self):
        """Test that rule names don't contain spaces."""
        rules = self.get_all_rules()

        for rule in rules:
            rule_name = rule.get("rule_name", "")
            assert " " not in rule_name, \
                f"Rule name in {rule['_file']} contains spaces: {rule_name}"

    def test_rule_names_start_with_letter(self):
        """Test that rule names start with a letter."""
        rules = self.get_all_rules()

        for rule in rules:
            rule_name = rule.get("rule_name", "")
            if rule_name:
                assert rule_name[0].isalpha(), \
                    f"Rule name in {rule['_file']} should start with a letter: {rule_name}"

    def test_rule_names_max_length(self):
        """Test that rule names don't exceed maximum length."""
        max_length = 63  # PAN-OS limit
        rules = self.get_all_rules()

        for rule in rules:
            rule_name = rule.get("rule_name", "")
            assert len(rule_name) <= max_length, \
                f"Rule name in {rule['_file']} exceeds {max_length} characters: {rule_name}"
