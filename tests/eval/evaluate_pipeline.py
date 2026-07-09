#!/usr/bin/env python3
"""
Automated evaluation pipeline for the multi-agent onboarding system.

Loads all test cases from test_cases.json, runs each through the deterministic
logic functions (routing decision, age calculation, document validity checks,
PII masking), and produces a JSON quality report.
"""

import json
import time
import sys
from pathlib import Path

# Ensure project root is on sys.path for direct script execution
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.policy_validator import (
    calculate_age,
    check_document_validity,
    get_minimum_age_for_account,
)
from src.pii_guardian import mask_dict
from src.schemas import make_routing_decision

TEST_CASES_FILE = Path(__file__).parent / "test_cases.json"


def evaluate_test_case(case: dict) -> dict:
    """Run a single test case through the deterministic pipeline checks.

    Args:
        case: A test case dict with 'document_data', 'account_type', and 'expected' keys.

    Returns:
        dict: Result containing pass/fail status, individual check results,
              and any error messages.
    """
    doc = case["document_data"]
    account_type = case["account_type"]
    expected = case["expected"]
    result = {"id": case["id"], "passed": True, "checks": {}, "errors": []}

    # Check routing decision
    t0 = time.perf_counter()
    routing = make_routing_decision(doc["confidence"]).value
    result["checks"]["routing_time_ms"] = (time.perf_counter() - t0) * 1000

    if "routing" in expected:
        result["checks"]["routing_match"] = routing == expected["routing"]
        if not result["checks"]["routing_match"]:
            result["passed"] = False
            result["errors"].append(
                f"Expected routing={expected['routing']}, got {routing}"
            )

    if routing in ("REJECTED", "PENDING_REVIEW"):
        result["checks"]["skipped_validation"] = True
        return result

    # Check age calculation
    t0 = time.perf_counter()
    age = calculate_age.func(doc["tanggal_lahir"])
    result["checks"]["age_calc_time_ms"] = (time.perf_counter() - t0) * 1000
    result["checks"]["calculated_age"] = age

    # Check minimum age requirement
    age_req = get_minimum_age_for_account.func(account_type)
    result["checks"]["min_age"] = age_req["minimum_age"]
    if "minimum_age_required" in expected:
        match = age_req["minimum_age"] == expected["minimum_age_required"]
        result["checks"]["min_age_match"] = match
        if not match:
            result["passed"] = False
            result["errors"].append(
                f"Expected min_age={expected['minimum_age_required']}, "
                f"got {age_req['minimum_age']}"
            )

    # Check status outcome
    meets_age = age >= age_req["minimum_age"]
    doc_valid = check_document_validity.func(doc["tanggal_kadaluarsa"])
    inferred_status = "APPROVED" if (meets_age and doc_valid["is_valid"]) else "REJECTED"

    if "status" in expected:
        result["checks"]["status_match"] = inferred_status == expected["status"]
        if not result["checks"]["status_match"]:
            result["passed"] = False
            result["errors"].append(
                f"Expected status={expected['status']}, got {inferred_status}"
            )

    # Check PII masking
    if "pii_masked" in expected:
        masked = mask_dict(doc)
        is_masked = masked.masked_data.get("nik") != doc.get("nik")
        result["checks"]["pii_masked"] = is_masked
        if expected["pii_masked"] and not is_masked:
            result["passed"] = False
            result["errors"].append("Expected NIK to be masked, but it wasn't")
        if "nik_masked_contains" in expected:
            contains = expected["nik_masked_contains"] in str(
                masked.masked_data.get("nik", "")
            )
            result["checks"]["nik_mask_format"] = contains
            if not contains:
                result["passed"] = False
                result["errors"].append(
                    f"Expected NIK mask to contain "
                    f"'{expected['nik_masked_contains']}'"
                )

    return result


def main():
    with open(TEST_CASES_FILE, encoding="utf-8") as f:
        cases = json.load(f)

    results = []
    passed = 0
    failed = 0

    for case in cases:
        r = evaluate_test_case(case)
        results.append(r)
        if r["passed"]:
            passed += 1
        else:
            failed += 1

    total_time = sum(
        r["checks"].get("routing_time_ms", 0)
        + r["checks"].get("age_calc_time_ms", 0)
        for r in results
    )

    report = {
        "summary": {
            "total_cases": len(cases),
            "passed": passed,
            "failed": failed,
            "pass_rate": f"{passed / len(cases) * 100:.1f}%",
            "total_eval_time_ms": round(total_time, 2),
        },
        "results": results,
    }

    print(json.dumps(report, indent=2))

    if failed > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
