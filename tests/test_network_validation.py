#!/usr/bin/env python3
"""
Unit tests for network validation functionality.
"""

import json
import pytest
from pathlib import Path
import ipaddress

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
RULES_DIR = PROJECT_ROOT / "firewall-rules"


class TestIPAddressValidation:
    """Test IP address validation."""

    def test_valid_ipv4_address(self):
        """Test valid IPv4 address."""
        valid_ips = ["192.168.1.1", "10.0.0.1", "172.16.0.1", "8.8.8.8"]
        for ip in valid_ips:
            assert ipaddress.ip_address(ip), f"{ip} should be valid"

    def test_valid_ipv4_network(self):
        """Test valid IPv4 network."""
        valid_networks = ["192.168.1.0/24", "10.0.0.0/8", "172.16.0.0/12"]
        for network in valid_networks:
            assert ipaddress.ip_network(network, strict=False), f"{network} should be valid"

    def test_invalid_ip_raises_error(self):
        """Test that invalid IP raises error."""
        invalid_ips = ["256.1.1.1", "192.168.1", "not_an_ip"]
        for ip in invalid_ips:
            with pytest.raises(ValueError):
                ipaddress.ip_address(ip)

    def test_private_ip_detection(self):
        """Test private IP detection."""
        private_ips = ["192.168.1.1", "10.0.0.1", "172.16.0.1"]
        public_ips = ["8.8.8.8", "1.1.1.1"]

        for ip in private_ips:
            assert ipaddress.ip_address(ip).is_private, f"{ip} should be private"

        for ip in public_ips:
            assert not ipaddress.ip_address(ip).is_private, f"{ip} should be public"


class TestRuleNetworkValidation:
    """Test network validation on actual rule files."""

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

    def test_all_source_addresses_valid(self):
        """Test that all source addresses are valid."""
        rules = self.get_all_rules()

        for rule in rules:
            for addr in rule.get("source_address", []):
                if addr.lower() in ['any', 'none']:
                    continue

                # Check if it's a valid IP or network
                try:
                    # Try as IP address first
                    ipaddress.ip_address(addr)
                except ValueError:
                    try:
                        # Try as network
                        ipaddress.ip_network(addr, strict=False)
                    except ValueError:
                        # Might be an address object name, which is valid
                        if not addr[0].isalpha():
                            pytest.fail(f"Invalid source address in {rule['_file']}: {addr}")

    def test_all_destination_addresses_valid(self):
        """Test that all destination addresses are valid."""
        rules = self.get_all_rules()

        for rule in rules:
            for addr in rule.get("destination_address", []):
                if addr.lower() in ['any', 'none']:
                    continue

                try:
                    ipaddress.ip_address(addr)
                except ValueError:
                    try:
                        ipaddress.ip_network(addr, strict=False)
                    except ValueError:
                        if not addr[0].isalpha():
                            pytest.fail(f"Invalid destination address in {rule['_file']}: {addr}")

    def test_no_overly_permissive_rules(self):
        """Test that there are no overly permissive allow rules."""
        rules = self.get_all_rules()

        for rule in rules:
            if rule.get("action") == "allow":
                source = rule.get("source_address", [])
                dest = rule.get("destination_address", [])

                # Check for any-to-any
                if "any" in source and "any" in dest:
                    pytest.fail(f"Overly permissive rule in {rule['_file']}: any-to-any allow")

                # Check for 0.0.0.0/0 source to any destination
                if "0.0.0.0/0" in source and "any" in dest:
                    pytest.fail(f"Overly permissive rule in {rule['_file']}: 0.0.0.0/0 to any")

    def test_service_port_ranges_valid(self):
        """Test that service port ranges are valid."""
        rules = self.get_all_rules()

        for rule in rules:
            for service in rule.get("service", []):
                # Parse port from service like "tcp-80" or "udp-53"
                if service.lower() in ['any', 'application-default']:
                    continue

                parts = service.split('-')
                if len(parts) >= 2 and parts[0].lower() in ['tcp', 'udp', 'sctp']:
                    try:
                        port = int(parts[1])
                        assert 1 <= port <= 65535, f"Invalid port in {rule['_file']}: {service}"
                    except ValueError:
                        pass  # Might be a named service


class TestZoneValidation:
    """Test zone validation."""

    KNOWN_ZONES = ['trust', 'untrust', 'dmz', 'internal', 'external',
                   'management', 'database', 'web', 'app', 'any']

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

    def test_source_zones_are_strings(self):
        """Test that source zones are strings."""
        rules = self.get_all_rules()

        for rule in rules:
            for zone in rule.get("source_zone", []):
                assert isinstance(zone, str), f"Zone should be string in {rule['_file']}"

    def test_destination_zones_are_strings(self):
        """Test that destination zones are strings."""
        rules = self.get_all_rules()

        for rule in rules:
            for zone in rule.get("destination_zone", []):
                assert isinstance(zone, str), f"Zone should be string in {rule['_file']}"
