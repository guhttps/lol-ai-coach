import unittest
from unittest.mock import patch

from coach_engine import ConnectionGracePeriod, GameAnalyzer


def game_state(*, kills=0, level=1, health=100, dead=False, events=None):
    return {
        "eu": {
            "vida": health,
            "vida_maxima": 100,
            "morto_agora": dead,
            "gold_atual": 500,
            "nivel": level,
            "kills": kills,
            "cs": 20,
        },
        "inimigos": [],
        "eventos_recentes": events or [],
        "tempo_de_jogo_min": 5,
    }


class GameAnalyzerTests(unittest.TestCase):
    def test_first_snapshot_only_establishes_baseline(self):
        analyzer = GameAnalyzer()

        with patch("coach_engine.time.time", return_value=100):
            self.assertEqual(analyzer.analyze(game_state()), [])

    def test_unselected_trigger_is_not_lost_when_higher_priority_fires(self):
        analyzer = GameAnalyzer()
        baseline = game_state()
        update = game_state(kills=1, level=2)

        with patch("coach_engine.time.time", return_value=100):
            analyzer.analyze(baseline)
        with patch("coach_engine.time.time", return_value=101):
            triggers = analyzer.analyze(update)

        self.assertEqual(triggers[0].kind, "kill")
        with patch("coach_engine.time.time", return_value=137):
            triggers = analyzer.analyze(update)

        self.assertEqual([trigger.kind for trigger in triggers], ["level_up"])

    def test_objective_trigger_waits_for_global_cooldown(self):
        analyzer = GameAnalyzer()
        objective = {"id": 42, "tipo": "DragonKill"}

        with patch("coach_engine.time.time", return_value=100):
            analyzer.analyze(game_state(health=20))
        with patch("coach_engine.time.time", return_value=101):
            triggers = analyzer.analyze(game_state(health=20, events=[objective]))

        self.assertEqual(triggers[0].kind, "low_health")
        with patch("coach_engine.time.time", return_value=137):
            triggers = analyzer.analyze(game_state(health=20, events=[objective]))

        self.assertEqual([trigger.kind for trigger in triggers], ["event:42"])

    def test_stale_low_health_trigger_is_discarded(self):
        analyzer = GameAnalyzer()

        with patch("coach_engine.time.time", return_value=100):
            analyzer.analyze(game_state())
        with patch("coach_engine.time.time", return_value=101):
            analyzer.analyze(game_state(kills=1))
        with patch("coach_engine.time.time", return_value=102):
            triggers = analyzer.analyze(game_state(health=20, kills=1))
        self.assertEqual(triggers, [])
        with patch("coach_engine.time.time", return_value=103):
            triggers = analyzer.analyze(game_state(health=80, kills=1))

        self.assertNotIn("low_health", [trigger.kind for trigger in triggers])


class ConnectionGracePeriodTests(unittest.TestCase):
    def test_short_disconnect_does_not_expire_and_recovery_resets_timer(self):
        grace_period = ConnectionGracePeriod(grace_seconds=12)

        self.assertFalse(grace_period.update(False, now=100))
        self.assertFalse(grace_period.update(False, now=111))
        self.assertFalse(grace_period.update(True, now=112))
        self.assertFalse(grace_period.update(False, now=120))

    def test_disconnect_expires_after_grace_period(self):
        grace_period = ConnectionGracePeriod(grace_seconds=12)

        self.assertFalse(grace_period.update(False, now=100))
        self.assertFalse(grace_period.update(False, now=111.9))
        self.assertTrue(grace_period.update(False, now=112))


if __name__ == "__main__":
    unittest.main()
