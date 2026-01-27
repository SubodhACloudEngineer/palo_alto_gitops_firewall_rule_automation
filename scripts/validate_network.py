#!/usr/bin/env python3
"""
Network Configuration Validator
Validates IP addresses, networks, and network-related configurations in firewall rules.
"""

import json
import sys
import re
from pathlib import Path
from typing import List, Dict, Any, Tuple
import ipaddress


# Define paths
SCRIPT_DIR = Path(__file__).parent.absolute()
PROJECT_ROOT = SCRIPT_DIR.parent
RULES_DIR = PROJECT_ROOT / "firewall-rules"


# Network validation configuration
NETWORK_CONFIG = {
    # Reserved/special addresses to warn about
    "warn_addresses": [
        "0.0.0.0/0",
        "255.255.255.255",
        "::/0",
    ],

    # Private address ranges (RFC 1918)
    "private_ranges": [
        "10.0.0.0/8",
        "172.16.0.0/12",
        "192.168.0.0/16",
    ],

    # Known internal network ranges for this organization
    "internal_networks": [
        "172.19.0.0/16",  # Internal VNet
        "10.0.0.0/8",     # Corporate network
        "192.168.0.0/16", # Lab network
    ],

    # Valid zone names
    "valid_zones": [
        "trust",
        "untrust",
        "dmz",
        "internal",
        "external",
        "management",
        "database",
        "web",
        "app",
    ],

    # Address object patterns (not IP addresses)
    "address_object_pattern": r"^[a-zA-Z][a-zA-Z0-9_-]*$",
}


class NetworkValidator:
    """Validates network configurations in firewall rules."""

    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or NETWORK_CONFIG
        self.errors = []
        self.warnings = []
        self.info = []

    def reset(self):
        """Reset validation state."""
        self.errors = []
        self.warnings = []
        self.info = []

    def add_error(self, message: str):
        """Add an error."""
        self.errors.append(message)

    def add_warning(self, message: str):
        """Add a warning."""
        self.warnings.append(message)

    def add_info(self, message: str):
        """Add an info message."""
        self.info.append(message)

    def is_valid_ip_or_network(self, address: str) -> Tuple[bool, str]:
        """Check if address is a valid IP or network."""
        # Check for special keywords
        if address.lower() in ['any', 'none']:
            return True, "keyword"

        # Check if it's an address object (not an IP)
        if re.match(self.config.get("address_object_pattern", r"^[a-zA-Z]"), address):
            if not any(c in address for c in ['.', ':', '/']):
                return True, "address_object"

        try:
            # Try to parse as IP address
            ipaddress.ip_address(address)
            return True, "ip_address"
        except ValueError:
            pass

        try:
            # Try to parse as IP network
            ipaddress.ip_network(address, strict=False)
            return True, "ip_network"
        except ValueError:
            pass

        return False, "invalid"

    def is_private_address(self, address: str) -> bool:
        """Check if address is in private range."""
        try:
            ip = ipaddress.ip_address(address.split('/')[0])
            return ip.is_private
        except ValueError:
            try:
                net = ipaddress.ip_network(address, strict=False)
                return net.is_private
            except ValueError:
                return False

    def validate_addresses(self, addresses: List[str], address_type: str) -> bool:
        """Validate a list of addresses."""
        valid = True

        for addr in addresses:
            is_valid, addr_type = self.is_valid_ip_or_network(addr)

            if not is_valid:
                self.add_error(f"Invalid {address_type} address: {addr}")
                valid = False
                continue

            if addr_type == "address_object":
                self.add_info(f"{address_type} uses address object: {addr}")

            # Check for warning addresses
            if addr in self.config.get("warn_addresses", []):
                self.add_warning(f"{address_type} contains special address: {addr}")

            # Validate network size for CIDR
            if addr_type == "ip_network" and '/' in addr:
                try:
                    net = ipaddress.ip_network(addr, strict=False)
                    if net.prefixlen < 16:
                        self.add_warning(
                            f"{address_type} has large network ({net.num_addresses} addresses): {addr}")
                except ValueError:
                    pass

        return valid

    def validate_zones(self, zones: List[str], zone_type: str) -> bool:
        """Validate zone names."""
        valid = True
        valid_zones = [z.lower() for z in self.config.get("valid_zones", [])]

        for zone in zones:
            if zone.lower() not in valid_zones and zone.lower() != "any":
                self.add_warning(f"Unknown {zone_type} zone: {zone}")

        return valid

    def validate_services(self, services: List[str]) -> bool:
        """Validate service specifications."""
        valid = True
        service_pattern = r"^(tcp|udp|sctp)-\d+(-\d+)?$|^application-default$|^any$|^[a-zA-Z][a-zA-Z0-9_-]*$"

        for service in services:
            if not re.match(service_pattern, service, re.IGNORECASE):
                self.add_warning(f"Unusual service format: {service}")

            # Check for well-known port ranges
            port_match = re.match(r"^(tcp|udp|sctp)-(\d+)(?:-(\d+))?$", service, re.IGNORECASE)
            if port_match:
                port_start = int(port_match.group(2))
                port_end = int(port_match.group(3)) if port_match.group(3) else port_start

                if port_start > 65535 or port_end > 65535:
                    self.add_error(f"Invalid port number in service: {service}")
                    valid = False

                if port_end < port_start:
                    self.add_error(f"Invalid port range in service: {service}")
                    valid = False

        return valid

    def validate_rule(self, rule: Dict[str, Any]) -> bool:
        """Validate network configuration for a single rule."""
        rule_name = rule.get("rule_name", "Unknown")
        valid = True

        # Validate source addresses
        source_addresses = rule.get("source_address", [])
        if not self.validate_addresses(source_addresses, "source"):
            valid = False

        # Validate destination addresses
        dest_addresses = rule.get("destination_address", [])
        if not self.validate_addresses(dest_addresses, "destination"):
            valid = False

        # Validate zones
        source_zones = rule.get("source_zone", [])
        self.validate_zones(source_zones, "source")

        dest_zones = rule.get("destination_zone", [])
        self.validate_zones(dest_zones, "destination")

        # Validate services
        services = rule.get("service", [])
        if services:
            self.validate_services(services)

        return valid


def validate_all_rules():
    """Validate all firewall rules for network configuration."""
    print("=" * 60)
    print("NETWORK CONFIGURATION VALIDATION")
    print("=" * 60)
    print()

    # Find all rule files
    rule_files = list(RULES_DIR.glob("*.json"))

    if not rule_files:
        print("WARNING: No firewall rule files found")
        return True

    print(f"Found {len(rule_files)} rule file(s) to validate")
    print("-" * 60)

    validator = NetworkValidator()
    all_valid = True
    total_errors = []
    total_warnings = []

    for rule_file in sorted(rule_files):
        print(f"\nValidating: {rule_file.name}")
        validator.reset()

        try:
            with open(rule_file, 'r') as f:
                rule_data = json.load(f)

            rule_name = rule_data.get("rule_name", "Unknown")
            valid = validator.validate_rule(rule_data)

            if not valid:
                all_valid = False

            # Report results
            if validator.errors:
                print(f"  ERRORS:")
                for error in validator.errors:
                    print(f"    - {error}")
                    total_errors.append(f"[{rule_name}] {error}")

            if validator.warnings:
                print(f"  WARNINGS:")
                for warning in validator.warnings:
                    print(f"    - {warning}")
                    total_warnings.append(f"[{rule_name}] {warning}")

            if validator.info:
                print(f"  INFO:")
                for info in validator.info:
                    print(f"    - {info}")

            if not validator.errors and not validator.warnings:
                # Print address summary
                src = rule_data.get("source_address", [])
                dst = rule_data.get("destination_address", [])
                print(f"  PASSED")
                print(f"    Source: {', '.join(src[:3])}{'...' if len(src) > 3 else ''}")
                print(f"    Destination: {', '.join(dst[:3])}{'...' if len(dst) > 3 else ''}")

        except json.JSONDecodeError as e:
            print(f"  ERROR - Invalid JSON: {e}")
            total_errors.append(f"[{rule_file.name}] Invalid JSON: {e}")
            all_valid = False

        except Exception as e:
            print(f"  ERROR - {e}")
            total_errors.append(f"[{rule_file.name}] {e}")
            all_valid = False

    # Print summary
    print()
    print("=" * 60)
    print("NETWORK VALIDATION SUMMARY")
    print("=" * 60)
    print(f"Total rules:    {len(rule_files)}")
    print(f"Total errors:   {len(total_errors)}")
    print(f"Total warnings: {len(total_warnings)}")
    print()

    if total_errors:
        print("ERRORS (must be fixed):")
        for error in total_errors:
            print(f"  - {error}")
        print()

    if total_warnings:
        print("WARNINGS (review recommended):")
        for warning in total_warnings:
            print(f"  - {warning}")
        print()

    if all_valid:
        print("RESULT: NETWORK VALIDATION PASSED")
    else:
        print("RESULT: NETWORK VALIDATION FAILED")

    return all_valid


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
