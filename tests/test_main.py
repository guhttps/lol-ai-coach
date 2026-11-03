import io
import sys
import unittest
from contextlib import ExitStack
from unittest.mock import Mock, call, patch

import main
from coach_worker import CoachJob, CoachResult


def in_game(seconds, champion="Ahri"):
    return {"mapa": "Map", "eu": {"nome": "Player", "campeao": champion},
            "tempo_de_jogo_seg": seconds, "tempo_de_jogo_min": seconds / 60}


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
                ("MatchRecorder", {}), ("ReportWriter", {}),
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


class PostMatchReportTests(unittest.TestCase):
    PROFILE = {"nome": "Teste"}

    def run_main(self, summaries, ticks, *, finished, poll=()):
        recorder = Mock()
        recorder.finish.side_effect = list(finished)
        reports = Mock()
        writer_class = Mock(return_value=reports)
        worker = Mock()
        worker.poll.side_effect = list(poll) + [None] * 10
        analyzer = Mock()
        analyzer.analyze.return_value = []
        grace = Mock()
        # A API sumir encerra a partida na hora; o prazo de reconexão tem testes próprios.
        grace.update.side_effect = lambda available, now=None: not available
        with ExitStack() as stack:
            for target, kwargs in (
                ("escolher_personalidade", {"return_value": "2"}),
                ("load_profile", {"return_value": self.PROFILE}),
                ("CoachOverlay", {}), ("Voice", {}),
                ("ConnectionGracePeriod", {"return_value": grace}),
                ("CoachWorker", {"return_value": worker}),
                ("GameAnalyzer", {"return_value": analyzer}),
                ("MatchRecorder", {"return_value": recorder}),
                ("ReportWriter", {"new": writer_class}),
                ("get_game_data", {"return_value": {}}),
                ("summarize_game_data", {"side_effect": summaries}),
                ("keyboard.is_pressed", {"return_value": False}),
                ("time.sleep", {}),
                ("time.monotonic", {"side_effect": ticks}),
            ):
                stack.enter_context(patch("main." + target, **kwargs))
            stack.enter_context(patch("builtins.print"))
            with self.assertRaises(SystemExit):
                main.main()
        return recorder, reports, writer_class

    def test_match_end_submits_the_report(self):
        match = in_game(1200)
        recorder, reports, _ = self.run_main(
            [match, None], [3, 6, KeyboardInterrupt], finished=[None, {"partida": 1}, None],
        )

        recorder.start.assert_called_once_with(match, "Analítico / Tryhard")
        recorder.update.assert_called_once_with(match)
        self.assertEqual(reports.submit.call_args_list, [
            call(None, "2", self.PROFILE),
            call({"partida": 1}, "2", self.PROFILE),
        ])
        self.assertEqual(recorder.finish.call_args_list, [call(), call(), call(partial=True)])
        reports.write_partial.assert_called_once_with(None)
        reports.wait.assert_called_once_with(timeout=5)

    def test_new_match_without_an_end_closes_the_previous_report(self):
        recorder, reports, _ = self.run_main(
            [in_game(1200), in_game(15)], [3, 6, KeyboardInterrupt],
            finished=[None, {"partida": 1}, {"partida": 2, "parcial": True}],
        )

        self.assertEqual(recorder.start.call_count, 2)
        self.assertEqual(reports.submit.call_args_list[1], call({"partida": 1}, "2", self.PROFILE))
        reports.write_partial.assert_called_once_with({"partida": 2, "parcial": True})

    def test_coach_replies_are_recorded_in_the_match(self):
        question = CoachJob(kind="chat", user_text="vale o barão?", game_summary={"tempo_de_jogo_seg": 610})
        tip = CoachJob(kind="automatic", user_text="", game_summary={"tempo_de_jogo_seg": 640}, event_kind="death")
        silence = CoachJob(kind="automatic", user_text="", game_summary={"tempo_de_jogo_seg": 700}, event_kind="rich")
        recorder, _, _ = self.run_main(
            [None, None, None], [3, 6, 9, KeyboardInterrupt], finished=[None],
            poll=[
                CoachResult(job=question, reply="Vale, com o jungle por perto."),
                CoachResult(job=tip, reply="Revise a posição."),
                CoachResult(job=silence, reply=""),
            ],
        )

        self.assertEqual(recorder.record_tip.call_args_list, [
            call(610, "Vale, com o jungle por perto.", question="vale o barão?", event_kind=None),
            call(640, "Revise a posição.", question=None, event_kind="death"),
        ])

    def test_report_settings_come_from_the_env(self):
        with patch.dict(main.RUNTIME_SETTINGS, {"post_match_report": False, "post_match_open": False}):
            _, _, writer_class = self.run_main([None], [3, KeyboardInterrupt], finished=[None])

        writer_class.assert_called_once_with(main.APP_DIR / "partidas", enabled=False, open_browser=False)


class ConsoleTests(unittest.TestCase):
    def test_redirected_cp1252_output_accepts_emoji_logs(self):
        buffer = io.BytesIO()
        stream = io.TextIOWrapper(buffer, encoding="cp1252")
        with patch.object(sys, "stdout", stream), patch.object(sys, "stderr", stream):
            main._configure_console()
            print("🎙️ Segure [SPACE] para falar.", file=stream)
        stream.flush()
        self.assertIn("🎙️".encode(), buffer.getvalue())
