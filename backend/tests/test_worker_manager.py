import unittest
import asyncio
import sys
import os
from unittest.mock import AsyncMock, MagicMock, patch

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import worker_manager


class TestWorkerManager(unittest.TestCase):
    @patch("worker_manager.send_irccat_message", new_callable=AsyncMock)
    def test_run_manager_cycle_sends_summary_when_rules_act(self, mock_irccat):
        db = MagicMock()

        async def rule_one(_db, _logger):
            return 2

        async def rule_two(_db, _logger):
            return 0

        async def rule_three(_db, _logger):
            return 1

        with patch.object(
            worker_manager,
            "MANAGER_RULES",
            [("retry_jobs", rule_one), ("noop", rule_two), ("launch_jobs", rule_three)],
        ):
            asyncio.run(worker_manager.run_manager_cycle(db))

        mock_irccat.assert_awaited_once()
        message = mock_irccat.await_args.args[0]
        self.assertIn("retry_jobs=2", message)
        self.assertIn("launch_jobs=1", message)
        self.assertNotIn("noop=0", message)

    @patch("worker_manager.send_irccat_message", new_callable=AsyncMock)
    def test_run_manager_cycle_skips_summary_when_no_rules_act(self, mock_irccat):
        db = MagicMock()

        async def rule_one(_db, _logger):
            return 0

        async def rule_two(_db, _logger):
            return 0

        with patch.object(
            worker_manager,
            "MANAGER_RULES",
            [("noop_one", rule_one), ("noop_two", rule_two)],
        ):
            asyncio.run(worker_manager.run_manager_cycle(db))

        mock_irccat.assert_not_awaited()


if __name__ == "__main__":
    unittest.main()
