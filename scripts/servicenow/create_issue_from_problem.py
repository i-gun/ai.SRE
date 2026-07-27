#!/usr/bin/env python3
"""
ServiceNow Problem Task (PTASK) creation from a Problem record.

Creates a Problem Task linked to a given PRB number, which corresponds to the
native 'Create Issue' button on the ServiceNow Problem form.  Records are
created in /api/now/table/problem_task (PTASK prefix).

For the full INC→PRB→Jira flow, Jira issue creation is handled separately by
the @Jira agent using the jira-create-issue-from-servicenow-handoff prompt.
"""

import sys
import argparse
import json
import re

from common import bootstrap

bootstrap(override_env=True)

from servicenow_client import ServiceNowClient


PROBLEM_NUMBER_PATTERN = re.compile(r"^PRB\d{7}$", re.IGNORECASE)
JIRA_PROJECT_PATTERN = re.compile(r"^[A-Z][A-Z0-9]+$")


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Inspect a ServiceNow problem and optionally create a linked PTASK.",
    )
    parser.add_argument("--problem-number", required=True, help="Problem number, for example PRB0040185.")
    parser.add_argument("--jira-project", help="Optional Jira project key for cross-system traceability.")
    parser.add_argument(
        "--execute",
        action="store_true",
        help="Create the Problem Task. Without this flag, the script only inspects the Problem.",
    )
    args = parser.parse_args(argv)

    if not PROBLEM_NUMBER_PATTERN.fullmatch(args.problem_number.strip()):
        parser.error("--problem-number must match PRB followed by 7 digits.")
    if args.jira_project and not JIRA_PROJECT_PATTERN.fullmatch(args.jira_project.strip()):
        parser.error("--jira-project must be an uppercase Jira project key.")
    return args


def main(argv=None):
    args = parse_args(argv)
    # Initialize client from .env
    try:
        client = ServiceNowClient.from_env()
        print("[OK] ServiceNow Client initialized successfully")
    except Exception as e:
        print(f"[FAILED] Failed to initialize ServiceNow client: {str(e)}")
        sys.exit(1)

    problem_number = args.problem_number.strip().upper()
    jira_project = args.jira_project.strip() if args.jira_project else None
    print(f"[CONFIG] Read-only mode: {'no' if args.execute else 'yes'}")
    print(f"[CONFIG] Problem Number: {problem_number}")
    print(f"[CONFIG] Jira Project: {jira_project or '(none)'}")

    # Step 1: Retrieve problem
    print("\n" + "=" * 80)
    print(f"STEP 1: Retrieving Problem {problem_number}")
    print("=" * 80)
    try:
        problem = client._find_problem(problem_number=problem_number, sys_id=None)
        print(f"[SUCCESS] Problem Found: {problem.get('number')}")
        print(f"  Short Description: {problem.get('short_description', '[Not Set]')}")
        print(f"  Description: {problem.get('description', '[Not Set]')}")
        print(f"  Category: {problem.get('category', '[Not Set]')}")
        print(f"  Subcategory: {problem.get('subcategory', '[Not Set]')}")
        print(f"  Configuration Item: {problem.get('cmdb_ci', '[Not Set]')}")
        print(f"  sys_id: {problem.get('sys_id')}")
    except Exception as e:
        print(f"[FAILED] Error retrieving problem: {str(e)}")
        sys.exit(1)

    if not args.execute:
        print("\n[SAFE MODE] No Problem Task was created. Re-run with --execute to create a PTASK.\n")
        return 0

    # Step 2: Create Problem Task from Problem
    print("\n" + "=" * 80)
    print(f"STEP 2: Creating Problem Task (PTASK) from {problem_number}")
    print("=" * 80)
    try:
        result = client.create_issue_from_problem(
            problem_number=problem_number,
            jira_project=jira_project,
        )

        if result.get("problem_task"):
            ptask = result["problem_task"]
            ptask_number = ptask.get("number")
            ptask_sys_id = ptask.get("sys_id")
            print(f"\n[SUCCESS] Problem Task Created Successfully")
            print(f"  PTASK Number: {ptask_number}")
            print(f"  PTASK sys_id: {ptask_sys_id}")
            print(f"  Problem Task Type: {ptask.get('problem_task_type', '[Not Set]')}")
            print(f"  Short Description: {ptask.get('short_description')}")
            print(f"  Jira Project (u_jira_project): {ptask.get('u_jira_project', '[Not Set]')}")
        else:
            print(f"[FAILED] Failed to create problem task")
            print(f"  Response: {json.dumps(result, indent=2)}")
            sys.exit(1)
    except Exception as e:
        print(f"[FAILED] Error creating problem task: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\n" + "=" * 80)
    print("OPERATION REPORT")
    print("=" * 80)
    print(f"  Problem   : {problem_number} ({problem.get('sys_id')})")
    print(f"  PTASK     : {ptask_number} ({ptask_sys_id})")
    print(f"  Linkage   : {problem_number} -> {ptask_number} (problem field)")
    print(f"  Jira Note : Jira issue creation is a separate step via @Jira agent")
    print("=" * 80)
    return 0


if __name__ == "__main__":
    sys.exit(main())

