#!/usr/bin/env python3
"""
Firewall Rule Schema Validator
Validates firewall rule JSON files against the defined JSON schema.

Usage:
    python validate_schema.py                    # Validate all non-template rules
    python validate_schema.py file1.json file2.json  # Validate specific files
    python validate_schema.py --all              # Validate all files including templates
"""

import json
import sys
import os
import argparse
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

# Files to exclude from validation (templates, examples, etc.)
EXCLUDED_FILES = {
    'template.json',
    'example.json',
    'sample.json',
    '.template.json',
}

# Patterns to exclude (files containing these strings)
EXCLUDED_PATTERNS = [
    'template',
    'example',
    'sample',
    '.bak',
    '.backup',
]


def should_exclude_file(filename):
    """Check if a file should be excluded from validation."""
    lower_name = filename.lower()

    # Check exact matches
    if lower_name in EXCLUDED_FILES:
        return True

    # Check patterns
    for pattern in EXCLUDED_PATTERNS:
        if pattern in lower_name:
            return True

    return False


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


def validate_rules(specific_files=None, include_all=False):
    """
    Validate firewall rules.

    Args:
        specific_files: List of specific files to validate (if None, validates all)
        include_all: If True, includes template files in validation
    """
    print("=" * 60)
    print("FIREWALL RULE SCHEMA VALIDATION")
    print("=" * 60)
    print()

    # Load schema
    print(f"Loading schema from: {SCHEMA_FILE}")
    schema = load_schema()
    print("Schema loaded successfully")
    print()

    # Determine which files to validate
    if specific_files:
        # Validate specific files passed as arguments
        rule_files = []
        for file_path in specific_files:
            path = Path(file_path)
            if not path.is_absolute():
                # Try relative to project root first
                full_path = PROJECT_ROOT / path
                if not full_path.exists():
                    # Try relative to rules directory
                    full_path = RULES_DIR / path.name
                path = full_path

            if path.exists() and path.suffix in ['.json', '.yaml', '.yml']:
                rule_files.append(path)
            else:
                print(f"WARNING: File not found or invalid: {file_path}")
        print(f"Validating {len(rule_files)} specified file(s)")
    else:
        # Find all rule files
        rule_files = list(RULES_DIR.glob("*.json")) + list(RULES_DIR.glob("*.yaml"))

        # Filter out excluded files unless --all is specified
        if not include_all:
            original_count = len(rule_files)
            rule_files = [f for f in rule_files if not should_exclude_file(f.name)]
            excluded_count = original_count - len(rule_files)
            if excluded_count > 0:
                print(f"Excluding {excluded_count} template/example file(s)")
        print(f"Found {len(rule_files)} rule file(s) to validate")

    if not rule_files:
        print("WARNING: No firewall rule files found to validate")
        return True

    print("-" * 60)

    all_errors = []
    validated_count = 0
    failed_count = 0
    skipped_count = 0

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
    parser = argparse.ArgumentParser(
        description='Validate firewall rule JSON files against schema',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s                           Validate all rules (excluding templates)
  %(prog)s rule1.json rule2.json     Validate specific files only
  %(prog)s --all                     Validate all files including templates
  %(prog)s --changed                 Validate only changed files (from git)
        '''
    )
    parser.add_argument(
        'files',
        nargs='*',
        help='Specific rule files to validate'
    )
    parser.add_argument(
        '--all',
        action='store_true',
        help='Include template and example files in validation'
    )
    parser.add_argument(
        '--changed',
        action='store_true',
        help='Only validate files changed in the current git commit/PR'
    )

    args = parser.parse_args()

    try:
        specific_files = args.files if args.files else None

        # If --changed flag, get changed files from git
        if args.changed and not specific_files:
            import subprocess
            try:
                # Try to get changed files from git
                result = subprocess.run(
                    ['git', 'diff', '--name-only', 'HEAD~1', '--', 'firewall-rules/*.json'],
                    capture_output=True,
                    text=True,
                    cwd=PROJECT_ROOT
                )
                if result.returncode == 0 and result.stdout.strip():
                    specific_files = result.stdout.strip().split('\n')
                    print(f"Found {len(specific_files)} changed file(s) from git")
            except Exception as e:
                print(f"WARNING: Could not get changed files from git: {e}")

        success = validate_rules(specific_files=specific_files, include_all=args.all)
        sys.exit(0 if success else 1)
    except Exception as e:
        print(f"FATAL ERROR: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
