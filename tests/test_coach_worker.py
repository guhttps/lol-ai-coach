import time
import unittest
from threading import Event
from unittest.mock import patch

from coach_worker import CoachJob, CoachWorker


class CoachWorkerTests(unittest.TestCase):
    def setUp(self):
        self.worker = CoachWorker()
        self.addCleanup(self.worker.shutdown)

    def _poll_until_result(self, history):
        deadline = time.monotonic() + 2
        while time.monotonic() < deadline:
            result = self.worker.poll(history, "1", {})
            if result is not None:
                return result
            time.sleep(0.001)
        self.fail("A resposta em segundo plano não terminou dentro do prazo.")

    def test_submit_does_not_wait_for_slow_ai_response(self):
        started = Event()
        release = Event()

        def slow_response(*args, **kwargs):
            started.set()
            release.wait(timeout=1)
            return "Resposta"

        with patch("coach_worker.ask_coach", side_effect=slow_response):
            self.worker.submit(CoachJob("chat", "oi", None))
            self.assertIsNone(self.worker.poll([], "1", {}))
            self.assertTrue(started.wait(timeout=1))
            self.assertIsNone(self.worker.poll([], "1", {}))
            release.set()
            result = self._poll_until_result([])

        self.assertEqual(result.reply, "Resposta")
        self.assertEqual(result.job.user_text, "oi")

    def test_queued_request_receives_history_updated_by_previous_reply(self):
        history = []
        first_finished = Event()

        def respond(user_text, game_summary, conversation_history, *args, **kwargs):
            if user_text == "primeira":
                first_finished.set()
                return "resposta"
            return str(conversation_history)

        with patch("coach_worker.ask_coach", side_effect=respond) as ask:
            self.worker.submit(CoachJob("chat", "primeira", None))
            self.worker.submit(CoachJob("chat", "acompanhamento", None))
            self.worker.poll(history, "1", {})
            self.assertTrue(first_finished.wait(timeout=1))
            first_result = self._poll_until_result(history)
            history.extend([
                {"role": "user", "content": first_result.job.user_text},
                {"role": "assistant", "content": first_result.reply},
            ])

            self.assertIsNone(self.worker.poll(history, "1", {}))
            second_result = self._poll_until_result(history)

        self.assertIn("resposta", second_result.reply)
        self.assertEqual(ask.call_args_list[1].args[2], history)

    def test_chat_request_is_prioritized_over_queued_automatic_tip(self):
        with patch("coach_worker.ask_coach", return_value="Resposta") as ask:
            self.worker.submit(CoachJob("automatic", "", None, trigger="evento"))
            self.worker.submit(CoachJob("chat", "pergunta", None))
            self.worker.poll([], "1", {})
            result = self._poll_until_result([])

        self.assertEqual(result.job.kind, "chat")
        self.assertEqual(ask.call_args.args[0], "pergunta")

    def test_match_reset_discards_stale_response_and_queued_requests(self):
        started = Event()
        release = Event()

        def slow_response(user_text, *args, **kwargs):
            if user_text == "antiga":
                started.set()
                release.wait(timeout=1)
            return user_text

        with patch("coach_worker.ask_coach", side_effect=slow_response):
            self.worker.submit(CoachJob("chat", "antiga", None))
            self.worker.submit(CoachJob("automatic", "", None, trigger="velho evento"))
            self.worker.poll([], "1", {})
            self.assertTrue(started.wait(timeout=1))
            self.worker.reset()
            self.worker.submit(CoachJob("chat", "nova partida", None))
            release.set()

            result = self._poll_until_result([])
            if result.job.user_text == "antiga":
                result = self._poll_until_result([])

        self.assertEqual(result.job.user_text, "nova partida")


if __name__ == "__main__":
    unittest.main()
