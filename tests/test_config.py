import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import mock_open, patch

from config import APP_DIR, DEFAULT_PROFILE, load_profile


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
