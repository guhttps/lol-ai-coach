import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import mock_open, patch

from config import APP_DIR, DEFAULT_PROFILE, get_runtime_settings, load_profile


class ProfileTests(unittest.TestCase):
    def test_default_profile_path_is_relative_to_application(self):
        with patch("config.os.path.exists", return_value=True):
            with patch("builtins.open", mock_open(read_data='{"nome": "Jogadora"}')) as opened:
                self.assertEqual(load_profile()["nome"], "Jogadora")
        opened.assert_called_once_with(APP_DIR / "player_profile.json", "r", encoding="utf-8")

    def test_invalid_profile_formats_fall_back_to_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            for content in ("{", "null", "[]", '"text"'):
                path.write_text(content, encoding="utf-8")
                self.assertEqual(load_profile(path), DEFAULT_PROFILE)

    def test_default_lists_are_independent_between_loads(self):
        with patch("config.os.path.exists", return_value=False):
            first = load_profile()
            first["campeoes_favoritos"].append("Ahri")
            self.assertEqual(load_profile()["campeoes_favoritos"], [])

    def test_partial_profile_preserves_unspecified_defaults(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "profile.json"
            path.write_text(json.dumps({"nome": "Jogadora"}), encoding="utf-8")
            profile = load_profile(path)
        self.assertEqual(profile["nome"], "Jogadora")
        self.assertEqual(profile["objetivo"], DEFAULT_PROFILE["objetivo"])


class RuntimeSettingsTests(unittest.TestCase):
    def test_defaults_are_applied_when_env_is_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            settings = get_runtime_settings()

        self.assertEqual(settings["push_to_talk_key"], "space")
        self.assertEqual(settings["check_interval_seconds"], 3.0)
        self.assertEqual(settings["max_history_messages"], 12)
        self.assertEqual(settings["default_personality"], "1")
        self.assertTrue(settings["overlay_enabled"])

    def test_env_values_override_defaults(self):
        env = {
            "PUSH_TO_TALK_KEY": "x",
            "CHECK_INTERVAL_SECONDS": "5.5",
            "MAX_HISTORY_MESSAGES": "20",
            "COACH_PERSONALITY": "2",
            "COACH_OVERLAY": "false",
        }

        with patch.dict(os.environ, env, clear=True):
            settings = get_runtime_settings()

        self.assertEqual(settings["push_to_talk_key"], "x")
        self.assertEqual(settings["check_interval_seconds"], 5.5)
        self.assertEqual(settings["max_history_messages"], 20)
        self.assertEqual(settings["default_personality"], "2")
        self.assertFalse(settings["overlay_enabled"])


if __name__ == "__main__":
    unittest.main()
