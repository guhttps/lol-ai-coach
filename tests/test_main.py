import unittest
from contextlib import ExitStack
from unittest.mock import Mock, patch

import main


class SessionTests(unittest.TestCase):
    def test_consecutive_matches_with_same_champion_reset_context(self):
        summaries = [
            {"mapa": "Map", "eu": {"nome": "Player", "campeao": "Ahri"},
             "tempo_de_jogo_seg": seconds, "tempo_de_jogo_min": seconds / 60}
            for seconds in (1200, 15)
        ]
        worker = Mock()
        worker.poll.return_value = None
        analyzer = Mock()
        analyzer.analyze.return_value = []
        with ExitStack() as stack:
            for target, kwargs in (
                ("escolher_personalidade", {"return_value": "1"}),
                ("load_profile", {"return_value": {}}),
                ("CoachOverlay", {}), ("Voice", {}),
                ("ConnectionGracePeriod", {}),
                ("CoachWorker", {"return_value": worker}),
                ("GameAnalyzer", {"return_value": analyzer}),
                ("get_game_data", {"return_value": {}}),
                ("summarize_game_data", {"side_effect": summaries}),
                ("keyboard.is_pressed", {"return_value": False}),
                ("time.sleep", {}),
                ("time.monotonic", {"side_effect": [3, 6, KeyboardInterrupt]}),
            ):
                stack.enter_context(patch("main." + target, **kwargs))
            stack.enter_context(patch("builtins.print"))
            with self.assertRaises(SystemExit) as exit_result:
                main.main()
        self.assertEqual(exit_result.exception.code, 0)
        self.assertEqual(worker.reset.call_count, 2)
        self.assertEqual(analyzer.reset.call_count, 2)
        worker.shutdown.assert_called_once()
