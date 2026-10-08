import unittest
from unittest.mock import Mock

from overlay import CoachOverlay


class OverlayTests(unittest.TestCase):
    def test_closed_overlay_does_not_accumulate_events(self):
        overlay = CoachOverlay(enabled=False)
        overlay.enabled = True
        overlay.root = Mock()
        root = overlay.root
        overlay.set_status("Partida")
        overlay.show_tip("Dica")
        overlay._close()
        for _ in range(100):
            overlay.set_status("Fora da partida")
            overlay.show_tip("Nova dica")
        self.assertTrue(overlay.events.empty())
        self.assertIsNone(overlay.root)
        root.destroy.assert_called_once()
