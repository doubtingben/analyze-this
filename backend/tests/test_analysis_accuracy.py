"""
Test harness for validating analysis accuracy on known test cases.

This module tests that the AI analysis correctly extracts information
from various types of content (screenshots, images, text, URLs).

To add a new test case:
1. Add the test file to backend/tests/fixtures/screenshots/ (or appropriate subdir)
2. Add a new test case dict to TEST_CASES with expected values
3. Run: python -m pytest backend/tests/test_analysis_accuracy.py -v
"""

import unittest
import os
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Optional
from dataclasses import dataclass

# Add backend directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from analysis import analyze_content, get_image_data_url

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@dataclass
class ExpectedEvent:
    """Expected event details for validation."""
    title: Optional[str] = None
    date: Optional[str] = None  # e.g., "2025-01-29" or "January 29"
    start_time: Optional[str] = None  # e.g., "19:00" or "7:00 PM"
    end_time: Optional[str] = None
    location: Optional[str] = None
    price: Optional[str] = None


@dataclass
class TestCase:
    """A test case for analysis validation."""
    name: str
    file_path: str  # Relative to fixtures dir
    item_type: str  # screenshot, image, web_url, text
    expected_action: Optional[str]  # add_event, follow_up, save_image, None
    expected_event: Optional[ExpectedEvent] = None
    expected_tags: Optional[list[str]] = None
    overview_contains: Optional[list[str]] = None  # Strings that should appear in overview


# Define test cases
TEST_CASES = [
    TestCase(
        name="eventbrite_dinner_event",
        file_path="screenshots/eventbrite_flor_fina_dinner.png",
        item_type="screenshot",
        expected_action="add_event",
        expected_event=ExpectedEvent(
            title="Friends of Flor Fina Dinner",
            date="January 29",  # or "Jan 29" - we'll check for partial match
            start_time="7",  # Will match "7:00 PM", "7 pm", "19:00", etc.
            end_time="9",
            location="Tampa",  # Partial match for "Hotel Haya, Tampa, FL"
            price="100",
        ),
        overview_contains=["dinner", "Flor Fina"],
        expected_tags=None,  # Don't require specific tags
    ),
]


class TestAnalysisAccuracy(unittest.TestCase):
    """Test that analysis correctly extracts information from known test cases."""

    @classmethod
    def setUpClass(cls):
        """Check if we can run live tests (requires API key)."""
        from analysis import client
        cls.can_run_live = client is not None
        if not cls.can_run_live:
            print("\nWARNING: OpenRouter client not configured. Skipping live analysis tests.")
            print("Set OPENROUTER_API_KEY to run live tests.\n")

    def _check_event_field(self, details: dict, field: str, expected: str, case_name: str):
        """Check if an event field contains the expected value (case-insensitive partial match)."""
        if expected is None:
            return True

        # Look for the field in various possible locations
        actual = None

        # Direct field access
        if field in details:
            actual = str(details[field])

        # Check nested structures
        elif "event" in details and isinstance(details["event"], dict):
            if field in details["event"]:
                actual = str(details["event"][field])

        # Check for date/time in various formats
        if actual is None:
            # Try common field name variations
            variations = {
                "title": ["name", "event_name", "eventName", "summary"],
                "date": ["event_date", "eventDate", "day", "start_date", "startDate"],
                "start_time": ["time", "startTime", "start", "begins"],
                "end_time": ["endTime", "end", "ends"],
                "location": ["venue", "place", "address"],
                "price": ["cost", "ticket_price", "ticketPrice"],
            }
            for variant in variations.get(field, []):
                if variant in details:
                    actual = str(details[variant])
                    break
                elif "event" in details and isinstance(details["event"], dict):
                    if variant in details["event"]:
                        actual = str(details["event"][variant])
                        break

        if actual is None:
            # Check if the expected value appears anywhere in the details JSON
            details_str = json.dumps(details).lower()
            if expected.lower() in details_str:
                return True
            self.fail(f"[{case_name}] Field '{field}' not found in details. Expected to contain: '{expected}'. Details: {details}")

        self.assertIn(
            expected.lower(),
            actual.lower(),
            f"[{case_name}] Field '{field}' = '{actual}' does not contain expected '{expected}'"
        )

    def _run_test_case(self, case: TestCase):
        """Run a single test case."""
        # Build full path to test file
        file_path = FIXTURES_DIR / case.file_path

        if not file_path.exists():
            self.skipTest(f"Test fixture not found: {file_path}")

        # For image/screenshot types, convert to data URL
        if case.item_type in ["screenshot", "image"]:
            # Read file and convert to data URL
            with open(file_path, "rb") as f:
                import base64
                image_bytes = f.read()

            ext = file_path.suffix.lower()
            mime_map = {
                ".png": "image/png",
                ".jpg": "image/jpeg",
                ".jpeg": "image/jpeg",
                ".gif": "image/gif",
                ".webp": "image/webp",
            }
            mime_type = mime_map.get(ext, "image/png")
            content = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode()}"
        else:
            # For text/URL, read content directly
            with open(file_path, "r") as f:
                content = f.read().strip()

        # Run analysis
        result = analyze_content(content, item_type=case.item_type)

        self.assertIsNotNone(result, f"[{case.name}] Analysis returned None")
        self.assertIsInstance(result, dict, f"[{case.name}] Analysis should return dict")

        # Check for errors
        if "error" in result and case.expected_action is not None:
            self.fail(f"[{case.name}] Analysis returned error: {result['error']}")

        # Validate action
        if case.expected_action:
            self.assertEqual(
                result.get("action"),
                case.expected_action,
                f"[{case.name}] Expected action '{case.expected_action}', got '{result.get('action')}'"
            )

        # Validate overview contains expected strings
        if case.overview_contains:
            overview = result.get("overview", "").lower()
            for expected_str in case.overview_contains:
                self.assertIn(
                    expected_str.lower(),
                    overview,
                    f"[{case.name}] Overview should contain '{expected_str}'. Got: '{result.get('overview')}'"
                )

        # Validate event details
        if case.expected_event and case.expected_action == "add_event":
            details = result.get("details", {})
            self.assertIsNotNone(details, f"[{case.name}] Expected event details but got None")

            if case.expected_event.title:
                self._check_event_field(details, "title", case.expected_event.title, case.name)
            if case.expected_event.date:
                self._check_event_field(details, "date", case.expected_event.date, case.name)
            if case.expected_event.start_time:
                self._check_event_field(details, "start_time", case.expected_event.start_time, case.name)
            if case.expected_event.end_time:
                self._check_event_field(details, "end_time", case.expected_event.end_time, case.name)
            if case.expected_event.location:
                self._check_event_field(details, "location", case.expected_event.location, case.name)
            if case.expected_event.price:
                self._check_event_field(details, "price", case.expected_event.price, case.name)

        # Validate tags if specified
        if case.expected_tags:
            actual_tags = [t.lower() for t in result.get("tags", [])]
            for expected_tag in case.expected_tags:
                self.assertIn(
                    expected_tag.lower(),
                    actual_tags,
                    f"[{case.name}] Expected tag '{expected_tag}' not found in {actual_tags}"
                )

        return result


# Dynamically generate test methods for each test case
def _make_test_method(case: TestCase):
    def test_method(self):
        if not self.can_run_live:
            self.skipTest("OpenRouter client not configured")
        self._run_test_case(case)
    test_method.__doc__ = f"Test analysis accuracy for: {case.name}"
    return test_method


for case in TEST_CASES:
    test_name = f"test_{case.name}"
    setattr(TestAnalysisAccuracy, test_name, _make_test_method(case))


class TestAnalysisAccuracyOffline(unittest.TestCase):
    """Offline tests that don't require API calls."""

    def test_fixtures_directory_exists(self):
        """Verify fixtures directory structure exists."""
        self.assertTrue(FIXTURES_DIR.exists(), f"Fixtures directory not found: {FIXTURES_DIR}")
        screenshots_dir = FIXTURES_DIR / "screenshots"
        self.assertTrue(screenshots_dir.exists(), f"Screenshots directory not found: {screenshots_dir}")

    def test_all_test_case_files_exist(self):
        """Verify all test case files are present."""
        missing = []
        for case in TEST_CASES:
            file_path = FIXTURES_DIR / case.file_path
            if not file_path.exists():
                missing.append(case.file_path)

        if missing:
            self.skipTest(f"Missing test fixtures (add them to run tests): {missing}")


if __name__ == "__main__":
    unittest.main()
