#!/usr/bin/env python3
"""
Unit tests for security policy validation.
"""

import json
import pytest
from pathlib import Path

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
RULES_DIR = PROJECT_ROOT / "firewall-rules"


class TestSecurityPolicies:
    """Test security policy compliance."""

    def get_all_rules(self):
        """Load all rule files."""
        rules = []
        rule_files = list(RULES_DIR.glob("*.json"))
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
    """Test metadata compliance for audit purposes."""

    def get_all_rules(self):
        """Load all rule files."""
        rules = []
        rule_files = list(RULES_DIR.glob("*.json"))
        for rule_file in rule_files:
            with open(rule_file, 'r') as f:
                rule = json.load(f)
                rule['_file'] = rule_file.name
                rules.append(rule)
        return rules

    def test_rules_have_metadata(self):
        """Test that rules have metadata section."""
        rules = self.get_all_rules()

        for rule in rules:
            assert "metadata" in rule, f"Rule {rule['_file']} should have metadata"

    def test_metadata_has_ticket_id(self):
        """Test that metadata includes ticket ID for audit trail."""
        rules = self.get_all_rules()

        for rule in rules:
            metadata = rule.get("metadata", {})
            ticket_id = metadata.get("ticket_id", "")
            assert len(ticket_id) > 0, \
                f"Rule {rule['_file']} should have ticket_id in metadata"

    def test_metadata_has_requested_by(self):
        """Test that metadata includes who requested the rule."""
        rules = self.get_all_rules()

        for rule in rules:
            metadata = rule.get("metadata", {})
            requested_by = metadata.get("requested_by", "")
            assert len(requested_by) > 0, \
                f"Rule {rule['_file']} should have requested_by in metadata"

    def test_metadata_has_environment(self):
        """Test that metadata includes target environment."""
        rules = self.get_all_rules()

        for rule in rules:
            metadata = rule.get("metadata", {})
            environment = metadata.get("environment", "")
            assert len(environment) > 0, \
                f"Rule {rule['_file']} should have environment in metadata"

    def test_valid_environment_values(self):
        """Test that environment values are valid."""
        valid_environments = ["production", "staging", "development", "all"]
        rules = self.get_all_rules()

        for rule in rules:
            metadata = rule.get("metadata", {})
            environment = metadata.get("environment", "").lower()
            if environment:
                assert environment in valid_environments, \
                    f"Invalid environment '{environment}' in {rule['_file']}"


class TestRuleNaming:
    """Test rule naming conventions."""

    def get_all_rules(self):
        """Load all rule files."""
        rules = []
        rule_files = list(RULES_DIR.glob("*.json"))
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
