#!/usr/bin/env python3
"""
Firewall Rule Security Policy Validator
Validates firewall rules against organizational security policies.
"""

import json
import sys
import re
from pathlib import Path
from typing import List, Dict, Any


# Define paths
SCRIPT_DIR = Path(__file__).parent.absolute()
PROJECT_ROOT = SCRIPT_DIR.parent
RULES_DIR = PROJECT_ROOT / "firewall-rules"


# Security policy configuration
SECURITY_POLICIES = {
    # Prohibited source addresses
    "prohibited_sources": [
        "0.0.0.0/0",  # No allow-all from anywhere
    ],

    # Prohibited destination addresses (for allow rules)
    "prohibited_destinations_allow": [
        # Generally should not allow traffic to these
    ],

    # High-risk ports that require explicit approval
    "high_risk_ports": [
        "tcp-22",    # SSH
        "tcp-23",    # Telnet
        "tcp-3389",  # RDP
        "tcp-1433",  # MSSQL
        "tcp-3306",  # MySQL
        "tcp-5432",  # PostgreSQL
        "tcp-27017", # MongoDB
    ],

    # Zones that should not be directly accessible from untrust
    "protected_zones": [
        "trust",
        "internal",
        "database",
        "management",
    ],

    # Applications that should be blocked or require approval
    "restricted_applications": [
        "unknown-tcp",
        "unknown-udp",
        "bittorrent",
        "tor",
    ],

    # Required tags for production rules
    "required_tags_production": [],

    # Maximum number of addresses per rule
    "max_addresses_per_rule": 50,

    # Rules must have logging enabled
    "require_logging": True,

    # Rules must have description
    "require_description": True,

    # Rules must have metadata ticket_id
    "require_ticket_id": True,
}


class SecurityPolicyValidator:
    """Validates firewall rules against security policies."""

    def __init__(self, policies: Dict[str, Any] = None):
        self.policies = policies or SECURITY_POLICIES
        self.warnings = []
        self.errors = []

    def reset(self):
        """Reset validation state."""
        self.warnings = []
        self.errors = []

    def add_error(self, rule_name: str, message: str):
        """Add an error."""
        self.errors.append({"rule": rule_name, "message": message, "severity": "ERROR"})

    def add_warning(self, rule_name: str, message: str):
        """Add a warning."""
        self.warnings.append({"rule": rule_name, "message": message, "severity": "WARNING"})

    def validate_rule(self, rule: Dict[str, Any]) -> bool:
        """Validate a single firewall rule."""
        rule_name = rule.get("rule_name", "Unknown")
        action = rule.get("action", "").lower()

        # Check for 'any' in source/destination
        self._check_any_usage(rule, rule_name, action)

        # Check source addresses
        self._check_source_addresses(rule, rule_name, action)

        # Check high-risk ports
        self._check_high_risk_ports(rule, rule_name, action)

        # Check zone policies
        self._check_zone_policies(rule, rule_name, action)

        # Check restricted applications
        self._check_restricted_applications(rule, rule_name, action)

        # Check logging configuration
        self._check_logging(rule, rule_name)

        # Check description
        self._check_description(rule, rule_name)

        # Check metadata
        self._check_metadata(rule, rule_name)

        # Check address count limits
        self._check_address_limits(rule, rule_name)

        return len(self.errors) == 0

    def _check_any_usage(self, rule: Dict, rule_name: str, action: str):
        """Check for usage of 'any' which could be overly permissive."""
        source_addresses = rule.get("source_address", [])
        dest_addresses = rule.get("destination_address", [])
        applications = rule.get("application", [])
        services = rule.get("service", [])

        if action == "allow":
            if "any" in source_addresses and "any" in dest_addresses:
                self.add_error(rule_name, "Allow rule with 'any' source AND 'any' destination is prohibited")
            elif "any" in source_addresses:
                self.add_warning(rule_name, "Allow rule with 'any' source - ensure this is intentional")
            elif "any" in dest_addresses:
                self.add_warning(rule_name, "Allow rule with 'any' destination - ensure this is intentional")

            if "any" in applications and "any" in services:
                self.add_warning(rule_name, "Allow rule permits any application and any service")

    def _check_source_addresses(self, rule: Dict, rule_name: str, action: str):
        """Check source addresses against prohibited list."""
        source_addresses = rule.get("source_address", [])

        for addr in source_addresses:
            if addr in self.policies.get("prohibited_sources", []):
                if action == "allow":
                    self.add_error(rule_name, f"Prohibited source address: {addr}")

    def _check_high_risk_ports(self, rule: Dict, rule_name: str, action: str):
        """Check for high-risk ports."""
        services = rule.get("service", [])

        if action == "allow":
            for service in services:
                if service.lower() in [p.lower() for p in self.policies.get("high_risk_ports", [])]:
                    self.add_warning(rule_name,
                        f"High-risk port detected: {service} - ensure proper approval obtained")

    def _check_zone_policies(self, rule: Dict, rule_name: str, action: str):
        """Check zone-based security policies."""
        source_zones = rule.get("source_zone", [])
        dest_zones = rule.get("destination_zone", [])
        protected = self.policies.get("protected_zones", [])

        if action == "allow":
            # Check if allowing from untrust to protected zones
            if "untrust" in source_zones or "external" in source_zones:
                for zone in dest_zones:
                    if zone.lower() in [z.lower() for z in protected]:
                        self.add_warning(rule_name,
                            f"Rule allows traffic from untrust to protected zone '{zone}'")

    def _check_restricted_applications(self, rule: Dict, rule_name: str, action: str):
        """Check for restricted applications."""
        applications = rule.get("application", [])

        if action == "allow":
            for app in applications:
                if app.lower() in [a.lower() for a in self.policies.get("restricted_applications", [])]:
                    self.add_error(rule_name, f"Restricted application detected: {app}")

    def _check_logging(self, rule: Dict, rule_name: str):
        """Check logging configuration."""
        if self.policies.get("require_logging", False):
            log_start = rule.get("log_at_session_start", False)
            log_end = rule.get("log_at_session_end", False)

            if not (log_start or log_end):
                self.add_warning(rule_name, "Logging is not enabled for this rule")

    def _check_description(self, rule: Dict, rule_name: str):
        """Check that rule has a description."""
        if self.policies.get("require_description", False):
            description = rule.get("description", "")
            if not description or len(description.strip()) < 10:
                self.add_warning(rule_name, "Rule should have a meaningful description (min 10 characters)")

    def _check_metadata(self, rule: Dict, rule_name: str):
        """Check metadata requirements."""
        metadata = rule.get("metadata", {})

        if self.policies.get("require_ticket_id", False):
            if not metadata.get("ticket_id"):
                self.add_warning(rule_name, "Rule should have a ticket_id in metadata for audit purposes")

    def _check_address_limits(self, rule: Dict, rule_name: str):
        """Check address count limits."""
        max_addresses = self.policies.get("max_addresses_per_rule", 50)

        source_count = len(rule.get("source_address", []))
        dest_count = len(rule.get("destination_address", []))

        if source_count > max_addresses:
            self.add_warning(rule_name,
                f"Rule has {source_count} source addresses (max recommended: {max_addresses})")

        if dest_count > max_addresses:
            self.add_warning(rule_name,
                f"Rule has {dest_count} destination addresses (max recommended: {max_addresses})")


def validate_all_rules():
    """Validate all firewall rules against security policies."""
    print("=" * 60)
    print("FIREWALL RULE SECURITY POLICY VALIDATION")
    print("=" * 60)
    print()

    # Find all rule files
    rule_files = list(RULES_DIR.glob("*.json"))

    if not rule_files:
        print("WARNING: No firewall rule files found")
        return True

    print(f"Found {len(rule_files)} rule file(s) to validate")
    print("-" * 60)

    validator = SecurityPolicyValidator()
    total_errors = []
    total_warnings = []

    for rule_file in sorted(rule_files):
        print(f"\nValidating: {rule_file.name}")
        validator.reset()

        try:
            with open(rule_file, 'r') as f:
                rule_data = json.load(f)

            validator.validate_rule(rule_data)

            # Report results for this rule
            if validator.errors:
                print(f"  ERRORS: {len(validator.errors)}")
                for error in validator.errors:
                    print(f"    - {error['message']}")
                total_errors.extend(validator.errors)

            if validator.warnings:
                print(f"  WARNINGS: {len(validator.warnings)}")
                for warning in validator.warnings:
                    print(f"    - {warning['message']}")
                total_warnings.extend(validator.warnings)

            if not validator.errors and not validator.warnings:
                print(f"  PASSED - No security issues found")

        except json.JSONDecodeError as e:
            print(f"  ERROR - Invalid JSON: {e}")
            total_errors.append({"rule": rule_file.name, "message": f"Invalid JSON: {e}"})

        except Exception as e:
            print(f"  ERROR - {e}")
            total_errors.append({"rule": rule_file.name, "message": str(e)})

    # Print summary
    print()
    print("=" * 60)
    print("SECURITY VALIDATION SUMMARY")
    print("=" * 60)
    print(f"Total rules:    {len(rule_files)}")
    print(f"Total errors:   {len(total_errors)}")
    print(f"Total warnings: {len(total_warnings)}")
    print()

    if total_errors:
        print("ERRORS (must be fixed):")
        for error in total_errors:
            print(f"  - [{error['rule']}] {error['message']}")
        print()
        print("RESULT: SECURITY VALIDATION FAILED")
        return False

    if total_warnings:
        print("WARNINGS (review recommended):")
        for warning in total_warnings:
            print(f"  - [{warning['rule']}] {warning['message']}")
        print()

    print("RESULT: SECURITY VALIDATION PASSED")
    return True


def main():
    """Main entry point."""
    try:
        success = validate_all_rules()
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
