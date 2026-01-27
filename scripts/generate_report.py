#!/usr/bin/env python3
"""
Deployment Report Generator
Generates markdown reports for firewall rule deployments.
"""

import json
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List


# Define paths
SCRIPT_DIR = Path(__file__).parent.absolute()
PROJECT_ROOT = SCRIPT_DIR.parent
RULES_DIR = PROJECT_ROOT / "firewall-rules"


def load_rules() -> List[Dict[str, Any]]:
    """Load all firewall rules."""
    rules = []
    rule_files = list(RULES_DIR.glob("*.json"))

    for rule_file in sorted(rule_files):
        try:
            with open(rule_file, 'r') as f:
                rule = json.load(f)
                rule["_file"] = rule_file.name
                rules.append(rule)
        except Exception as e:
            rules.append({
                "_file": rule_file.name,
                "_error": str(e)
            })

    return rules


def generate_markdown_report(environment: str) -> str:
    """Generate a markdown deployment report."""
    rules = load_rules()
    timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

    report = []

    # Header
    report.append(f"# Firewall Rule Deployment Report")
    report.append("")
    report.append(f"**Environment:** {environment.upper()}")
    report.append(f"**Deployment Time:** {timestamp}")
    report.append(f"**Deployed By:** GitHub Actions (GitOps)")
    report.append(f"**Total Rules:** {len(rules)}")
    report.append("")

    # Summary table
    report.append("## Deployment Summary")
    report.append("")
    report.append("| Rule Name | Action | Source | Destination | Status |")
    report.append("|-----------|--------|--------|-------------|--------|")

    for rule in rules:
        if "_error" in rule:
            report.append(f"| {rule['_file']} | - | - | - | ERROR |")
        else:
            rule_name = rule.get("rule_name", "Unknown")
            action = rule.get("action", "unknown").upper()
            source = ", ".join(rule.get("source_address", [])[:2])
            if len(rule.get("source_address", [])) > 2:
                source += "..."
            dest = ", ".join(rule.get("destination_address", [])[:2])
            if len(rule.get("destination_address", [])) > 2:
                dest += "..."
            report.append(f"| {rule_name} | {action} | {source} | {dest} | DEPLOYED |")

    report.append("")

    # Detailed rules section
    report.append("## Rule Details")
    report.append("")

    for rule in rules:
        if "_error" in rule:
            report.append(f"### {rule['_file']}")
            report.append(f"**Error:** {rule['_error']}")
            report.append("")
            continue

        rule_name = rule.get("rule_name", "Unknown")
        report.append(f"### {rule_name}")
        report.append("")
        report.append(f"**File:** `{rule['_file']}`")
        report.append("")

        if rule.get("description"):
            report.append(f"**Description:** {rule['description']}")
            report.append("")

        report.append("| Property | Value |")
        report.append("|----------|-------|")
        report.append(f"| **Action** | {rule.get('action', 'N/A').upper()} |")
        report.append(f"| **Source Zone** | {', '.join(rule.get('source_zone', []))} |")
        report.append(f"| **Destination Zone** | {', '.join(rule.get('destination_zone', []))} |")
        report.append(f"| **Source Address** | {', '.join(rule.get('source_address', []))} |")
        report.append(f"| **Destination Address** | {', '.join(rule.get('destination_address', []))} |")
        report.append(f"| **Application** | {', '.join(rule.get('application', ['any']))} |")
        report.append(f"| **Service** | {', '.join(rule.get('service', ['application-default']))} |")
        report.append(f"| **Log Start** | {rule.get('log_at_session_start', False)} |")
        report.append(f"| **Log End** | {rule.get('log_at_session_end', True)} |")

        if rule.get("tag"):
            report.append(f"| **Tags** | {', '.join(rule.get('tag', []))} |")

        report.append("")

        # Metadata if present
        metadata = rule.get("metadata", {})
        if metadata:
            report.append("**Metadata:**")
            report.append("")
            for key, value in metadata.items():
                report.append(f"- **{key.replace('_', ' ').title()}:** {value}")
            report.append("")

    # Traffic flow section
    report.append("## Traffic Flow Summary")
    report.append("")
    report.append("```")

    for rule in rules:
        if "_error" not in rule:
            rule_name = rule.get("rule_name", "Unknown")
            action = rule.get("action", "?").upper()
            src = rule.get("source_address", ["?"])[0]
            dst = rule.get("destination_address", ["?"])[0]
            src_zone = rule.get("source_zone", ["?"])[0]
            dst_zone = rule.get("destination_zone", ["?"])[0]

            report.append(f"[{rule_name}]")
            report.append(f"  {src} ({src_zone}) --> [{action}] --> {dst} ({dst_zone})")
            report.append("")

    report.append("```")
    report.append("")

    # Verification section
    report.append("## Verification Steps")
    report.append("")
    report.append("1. Log into the Palo Alto firewall web interface")
    report.append("2. Navigate to **Policies** > **Security**")
    report.append("3. Verify the following rules are present:")
    report.append("")

    for rule in rules:
        if "_error" not in rule:
            report.append(f"   - [ ] `{rule.get('rule_name', 'Unknown')}`")

    report.append("")
    report.append("4. Check the traffic logs at **Monitor** > **Logs** > **Traffic**")
    report.append("5. Test connectivity from source to destination hosts")
    report.append("")

    # Footer
    report.append("---")
    report.append("")
    report.append(f"*Generated by GitOps Firewall Automation Pipeline*")
    report.append(f"*Timestamp: {timestamp}*")

    return "\n".join(report)


def main():
    """Main entry point."""
    environment = sys.argv[1] if len(sys.argv) > 1 else "staging"

    report = generate_markdown_report(environment)
    print(report)


if __name__ == "__main__":
    main()
