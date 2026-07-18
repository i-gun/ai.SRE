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

from common import bootstrap

bootstrap()

from servicenow_client import ServiceNowClient
import json


def main():
    # Initialize client from .env
    try:
        client = ServiceNowClient.from_env()
        print("[OK] ServiceNow Client initialized successfully")
    except Exception as e:
        print(f"[FAILED] Failed to initialize ServiceNow client: {str(e)}")
        sys.exit(1)

    # --- Configure target problem number here ---
    PROBLEM_NUMBER = "PRB0040185"
    # Optional: set to Jira project key for cross-system traceability
    JIRA_PROJECT: str | None = None

    # Step 1: Retrieve problem
    print("\n" + "=" * 80)
    print(f"STEP 1: Retrieving Problem {PROBLEM_NUMBER}")
    print("=" * 80)
    try:
        problem = client._find_problem(problem_number=PROBLEM_NUMBER, sys_id=None)
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

    # Step 2: Create Problem Task from Problem
    print("\n" + "=" * 80)
    print(f"STEP 2: Creating Problem Task (PTASK) from {PROBLEM_NUMBER}")
    print("=" * 80)
    try:
        result = client.create_issue_from_problem(
            problem_number=PROBLEM_NUMBER,
            jira_project=JIRA_PROJECT,
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
    print(f"  Problem   : {PROBLEM_NUMBER} ({problem.get('sys_id')})")
    print(f"  PTASK     : {ptask_number} ({ptask_sys_id})")
    print(f"  Linkage   : {PROBLEM_NUMBER} -> {ptask_number} (problem field)")
    print(f"  Jira Note : Jira issue creation is a separate step via @Jira agent")
    print("=" * 80)


if __name__ == "__main__":
    main()

