import unittest
from unittest.mock import Mock, patch

import requests

import brain
import item_data


class GroqIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.working_model = patch.object(brain, "_working_model", None)
        self.working_model.start()
        self.addCleanup(self.working_model.stop)

    def _ask(self):
        with patch.dict("os.environ", {"GROQ_API_KEY": "test-key"}):
            return brain.ask_coach("oi", None, [])

    @staticmethod
    def _response(status_code, body=None):
        response = Mock()
        response.status_code = status_code
        response.ok = 200 <= status_code < 300
        response.json.return_value = body or {
            "choices": [{"message": {"content": "Dica útil."}}]
        }
        if not response.ok:
            response.raise_for_status.side_effect = requests.HTTPError()
        return response

    def test_unavailable_model_falls_through_to_next_candidate(self):
        brain._working_model = brain.CANDIDATE_MODELS[0]
        with patch(
            "brain._call_groq",
            side_effect=[
                self._response(404),
                self._response(200),
            ],
        ) as call:
            self.assertEqual(self._ask(), "Dica útil.")

        self.assertEqual(call.call_count, 2)
        self.assertEqual(call.call_args_list[1].args[0], brain.CANDIDATE_MODELS[1])

    def test_rate_limit_is_reported_without_fallback(self):
        with patch("brain._call_groq", return_value=self._response(429)) as call:
            with self.assertRaisesRegex(RuntimeError, "limite da API"):
                self._ask()

        call.assert_called_once()

    def test_invalid_api_key_is_reported_without_exposing_it(self):
        with patch("brain._call_groq", return_value=self._response(401)):
            with self.assertRaisesRegex(RuntimeError, "GROQ_API_KEY"):
                self._ask()

    def test_connection_failure_has_actionable_message(self):
        with patch("brain._call_groq", side_effect=requests.ConnectionError):
            with self.assertRaisesRegex(RuntimeError, "Verifique a internet"):
                self._ask()

    def test_malformed_success_response_is_reported(self):
        response = self._response(200, {"unexpected": []})

        with patch("brain._call_groq", return_value=response):
            with self.assertRaisesRegex(RuntimeError, "formato inesperado"):
                self._ask()


class ItemDataTests(unittest.TestCase):
    def setUp(self):
        self.finished_ids = patch.object(item_data, "_finished_item_ids", None)
        self.finished_ids.start()
        self.addCleanup(self.finished_ids.stop)
        self.last_attempt = patch.object(item_data, "_last_load_attempt", 0.0)
        self.last_attempt.start()
        self.addCleanup(self.last_attempt.stop)

    @staticmethod
    def _response(body):
        response = Mock()
        response.json.return_value = body
        return response

    def test_catalog_is_cached_and_identifies_finished_items(self):
        versions = self._response(["15.1.1"])
        catalog = self._response({
            "data": {
                "3001": {"gold": {"purchasable": True, "total": 1100}, "tags": []},
                "1001": {"gold": {"purchasable": True, "total": 300}, "tags": []},
                "2001": {
                    "gold": {"purchasable": True, "total": 1500},
                    "tags": [],
                    "into": ["3001"],
                },
            }
        })

        with patch("item_data.requests.get", side_effect=[versions, catalog]) as get:
            self.assertTrue(item_data.is_finished_item("3001"))
            self.assertFalse(item_data.is_finished_item(1001))
            self.assertIsNone(item_data.is_finished_item("invalid"))
            self.assertEqual(get.call_count, 2)

    def test_failed_fetch_is_retried_after_throttle_interval(self):
        failure_time = 100.0
        versions = self._response(["15.1.1"])
        catalog = self._response({
            "data": {
                "3001": {"gold": {"purchasable": True, "total": 1100}, "tags": []}
            }
        })

        with patch("item_data.time.monotonic", return_value=failure_time):
            with patch("item_data.requests.get", side_effect=requests.Timeout):
                with self.assertLogs("item_data", level="WARNING"):
                    self.assertIsNone(item_data.is_finished_item(3001))

        with patch(
            "item_data.time.monotonic",
            return_value=failure_time + item_data._RETRY_INTERVAL_SECONDS,
        ):
            with patch("item_data.requests.get", side_effect=[versions, catalog]) as get:
                self.assertTrue(item_data.is_finished_item(3001))

        self.assertEqual(get.call_count, 2)

    def test_failed_fetch_is_not_repeated_before_retry_interval(self):
        with patch("item_data.time.monotonic", return_value=100.0):
            with patch("item_data.requests.get", side_effect=requests.Timeout) as get:
                with self.assertLogs("item_data", level="WARNING"):
                    self.assertIsNone(item_data.is_finished_item(3001))
                self.assertIsNone(item_data.is_finished_item(3001))

        get.assert_called_once()


if __name__ == "__main__":
    unittest.main()
