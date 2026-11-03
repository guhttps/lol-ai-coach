import unittest
from unittest.mock import Mock

from overlay import STATUS_OFFLINE, STATUS_ONLINE, STATUS_WAITING, CoachOverlay, status_color


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

    def test_status_color_matches_main_loop_states(self):
        self.assertEqual(status_color("● Ahri · 12.3 min"), STATUS_ONLINE)
        self.assertEqual(status_color("● Conexão interrompida · reconectando"), STATUS_WAITING)
        self.assertEqual(status_color("● Partida detectada · aguardando jogador"), STATUS_WAITING)
        self.assertEqual(status_color("○ Fora da partida"), STATUS_OFFLINE)
