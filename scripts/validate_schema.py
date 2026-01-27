#!/usr/bin/env python3
"""
Firewall Rule Schema Validator
Validates firewall rule JSON files against the defined JSON schema.
"""

import json
import sys
import os
from pathlib import Path

try:
    from jsonschema import validate, ValidationError, Draft7Validator
except ImportError:
    print("ERROR: jsonschema module not installed. Run: pip install jsonschema")
    sys.exit(1)


# Define paths
SCRIPT_DIR = Path(__file__).parent.absolute()
PROJECT_ROOT = SCRIPT_DIR.parent
RULES_DIR = PROJECT_ROOT / "firewall-rules"
SCHEMA_FILE = PROJECT_ROOT / "schemas" / "firewall-rule-schema.json"


def load_schema():
    """Load the JSON schema for firewall rules."""
    if not SCHEMA_FILE.exists():
        print(f"ERROR: Schema file not found: {SCHEMA_FILE}")
        sys.exit(1)

    with open(SCHEMA_FILE, 'r') as f:
        return json.load(f)


def load_rule(rule_path):
    """Load a firewall rule from a JSON file."""
    with open(rule_path, 'r') as f:
        return json.load(f)


def validate_rule(rule_data, schema, rule_file):
    """Validate a single rule against the schema."""
    errors = []
    validator = Draft7Validator(schema)

    for error in validator.iter_errors(rule_data):
        error_path = " -> ".join(str(p) for p in error.absolute_path) if error.absolute_path else "root"
        errors.append({
            "file": str(rule_file),
            "path": error_path,
            "message": error.message,
            "value": error.instance if not isinstance(error.instance, (dict, list)) else "[complex value]"
        })

    return errors


def validate_all_rules():
    """Validate all firewall rules in the rules directory."""
    print("=" * 60)
    print("FIREWALL RULE SCHEMA VALIDATION")
    print("=" * 60)
    print()

    # Load schema
    print(f"Loading schema from: {SCHEMA_FILE}")
    schema = load_schema()
    print("Schema loaded successfully")
    print()

    # Find all rule files
    rule_files = list(RULES_DIR.glob("*.json")) + list(RULES_DIR.glob("*.yaml"))

    if not rule_files:
        print("WARNING: No firewall rule files found in", RULES_DIR)
        return True

    print(f"Found {len(rule_files)} rule file(s) to validate")
    print("-" * 60)

    all_errors = []
    validated_count = 0
    failed_count = 0

    for rule_file in sorted(rule_files):
        print(f"\nValidating: {rule_file.name}")

        try:
            rule_data = load_rule(rule_file)
            errors = validate_rule(rule_data, schema, rule_file.name)

            if errors:
                failed_count += 1
                print(f"  FAILED - {len(errors)} error(s) found")
                for error in errors:
                    print(f"    - [{error['path']}] {error['message']}")
                all_errors.extend(errors)
            else:
                validated_count += 1
                rule_name = rule_data.get('rule_name', 'Unknown')
                print(f"  PASSED - Rule: {rule_name}")

        except json.JSONDecodeError as e:
            failed_count += 1
            print(f"  FAILED - Invalid JSON: {e}")
            all_errors.append({
                "file": str(rule_file.name),
                "path": "root",
                "message": f"Invalid JSON: {e}",
                "value": None
            })

        except Exception as e:
            failed_count += 1
            print(f"  FAILED - Error: {e}")
            all_errors.append({
                "file": str(rule_file.name),
                "path": "root",
                "message": str(e),
                "value": None
            })

    # Print summary
    print()
    print("=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)
    print(f"Total rules:  {len(rule_files)}")
    print(f"Passed:       {validated_count}")
    print(f"Failed:       {failed_count}")
    print()

    if all_errors:
        print("ERRORS FOUND:")
        for error in all_errors:
            print(f"  - {error['file']}: [{error['path']}] {error['message']}")
        print()
        print("RESULT: VALIDATION FAILED")
        return False
    else:
        print("RESULT: ALL VALIDATIONS PASSED")
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
