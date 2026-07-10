import json
from pathlib import Path


def load_test_cases():
    cases_file = Path(__file__).parent / "test_cases.json"
    with open(cases_file, encoding="utf-8") as f:
        return json.load(f)


def pytest_generate_tests(metafunc):
    if "test_case" in metafunc.fixturenames:
        cases = load_test_cases()
        metafunc.parametrize("test_case", cases, ids=[c["id"] for c in cases])
