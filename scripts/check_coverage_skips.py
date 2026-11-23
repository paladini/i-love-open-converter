"""Fail CI when an operation's required success witness was skipped."""

from __future__ import annotations

import runpy
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from i_love_open_converter.main import SUPPORTED_OPERATIONS  # noqa: E402


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit("usage: check_coverage_skips.py JUNIT_XML")

    matrix = runpy.run_path(str(ROOT / "tests/test_conversion_coverage.py"))
    operation_cases = matrix["OPERATION_CASES"]

    if set(operation_cases) != SUPPORTED_OPERATIONS:
        raise SystemExit("operation coverage map differs from the application's accepted tools")
    required_names = {test_name for _, test_name in operation_cases.values()}
    root = ET.parse(sys.argv[1]).getroot()
    skipped = []
    platform_only = []
    platform_only_names = set()
    executed = set()
    for case in root.iter("testcase"):
        name = case.get("name", "")
        function_name = name.split("[", maxsplit=1)[0]
        if function_name in required_names:
            executed.add(function_name)
        if function_name in required_names and case.find("skipped") is not None:
            reason = case.find("skipped").get("message", "no skip reason")
            if sys.platform != "linux" and "isolated Linux worker" in reason:
                platform_only.append((name, reason))
                platform_only_names.add(function_name)
            else:
                skipped.append((name, reason))

    missing = required_names - executed
    if missing:
        print(
            "Required operation coverage did not run: " + ", ".join(sorted(missing)),
            file=sys.stderr,
        )
        return 1
    if skipped:
        for name, reason in skipped:
            print(f"Required operation coverage was skipped: {name}: {reason}", file=sys.stderr)
        return 1

    if platform_only:
        for name, reason in platform_only:
            print(f"Platform-only coverage not counted on {sys.platform}: {name}: {reason}")
    completed_count = len(required_names) - len(platform_only_names)
    print(f"{completed_count} required operation success witnesses ran.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
