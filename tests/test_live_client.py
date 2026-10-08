import unittest
from unittest.mock import patch

import requests

from live_client import summarize_game_data
import live_client


def player(name, champion, team):
    return {
        "riotIdGameName": name,
        "summonerName": name,
        "championName": champion,
        "team": team,
        "level": 1,
        "scores": {"kills": 0, "deaths": 0, "assists": 0, "creepScore": 0},
        "championStats": {"currentHealth": 500, "maxHealth": 500},
        "items": [],
    }


class SummarizeGameDataTests(unittest.TestCase):
    def test_matches_active_player_and_splits_teams(self):
        local_player = player("MinhaConta", "Ahri", "ORDER")
        ally = player("Aliado", "Lux", "ORDER")
        enemy = player("Oponente", "Zed", "CHAOS")
        data = {
            "allPlayers": [ally, enemy, local_player],
            "activePlayer": {
                "riotIdGameName": "MinhaConta",
                "currentGold": 1250.4,
            },
            "gameData": {"gameTime": 600, "mapName": "Map", "gameMode": "CLASSIC"},
            "events": {
                "Events": [
                    {"EventID": index, "EventName": "DragonKill", "EventTime": index}
                    for index in range(15)
                ]
            },
        }

        with patch("live_client.is_finished_item", return_value=None):
            summary = summarize_game_data(data)

        self.assertEqual(summary["eu"]["nome"], "MinhaConta")
        self.assertEqual(summary["eu"]["campeao"], "Ahri")
        self.assertEqual(summary["eu"]["gold_atual"], 1250)
        self.assertEqual([entry["campeao"] for entry in summary["aliados"]], ["Lux"])
        self.assertEqual([entry["campeao"] for entry in summary["inimigos"]], ["Zed"])
        self.assertEqual(len(summary["eventos_recentes"]), 12)
        self.assertEqual(summary["eventos_recentes"][0]["id"], 3)
        self.assertEqual(summary["fase"], "lane")

    def test_missing_active_player_does_not_guess_first_player(self):
        data = {
            "allPlayers": [player("OutraConta", "Lux", "ORDER")],
            "activePlayer": {},
            "gameData": {"gameTime": 60},
            "events": {"Events": []},
        }

        with patch("live_client.is_finished_item", return_value=None):
            summary = summarize_game_data(data)

        self.assertIsNone(summary["eu"])
        self.assertEqual(summary["aliados"], [])
        self.assertEqual(summary["inimigos"], [])

    def test_empty_payload_returns_none(self):
        self.assertIsNone(summarize_game_data(None))

    def test_null_sections_are_treated_as_loading_data(self):
        summary = summarize_game_data({
            "allPlayers": None,
            "activePlayer": None,
            "gameData": None,
            "events": None,
        })

        self.assertIsNone(summary["eu"])
        self.assertEqual(summary["tempo_de_jogo_seg"], 0)
        self.assertEqual(summary["eventos_recentes"], [])


class LiveClientDiagnosticsTests(unittest.TestCase):
    def tearDown(self):
        live_client._last_api_issue = None

    def test_unavailable_connection_is_logged_once_until_recovery(self):
        with patch("live_client.requests.get", side_effect=requests.ConnectionError):
            with self.assertLogs("live_client", level="INFO") as logs:
                self.assertIsNone(live_client.get_game_data())
                self.assertIsNone(live_client.get_game_data())

        self.assertEqual(len(logs.output), 1)
        self.assertIn("indisponível", logs.output[0])

        response = unittest.mock.Mock()
        response.json.return_value = {"gameData": {}}
        with patch("live_client.requests.get", return_value=response):
            with self.assertLogs("live_client", level="INFO") as recovery_logs:
                self.assertEqual(live_client.get_game_data(), {"gameData": {}})

        self.assertIn("restabelecida", recovery_logs.output[0])

    def test_http_failure_is_reported_and_not_repeated(self):
        response = unittest.mock.Mock()
        response.status_code = 503
        response.raise_for_status.side_effect = requests.HTTPError(response=response)

        with patch("live_client.requests.get", return_value=response):
            with self.assertLogs("live_client", level="WARNING") as logs:
                self.assertIsNone(live_client.get_game_data())
                self.assertIsNone(live_client.get_game_data())

        self.assertEqual(len(logs.output), 1)
        self.assertIn("503", logs.output[0])


if __name__ == "__main__":
    unittest.main()
