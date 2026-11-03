import unittest
from datetime import datetime

from match_recorder import MIN_TRACKED_SECONDS, MatchRecorder


def reading(seconds, *, kills=0, deaths=0, assists=0, cs=0, gold=500, level=1, items=(), events=(),
            ally_kills=0, vision=0):
    return {
        "tempo_de_jogo_seg": seconds,
        "mapa": "Map11",
        "modo": "CLASSIC",
        "eu": {
            "nome": "Eu", "campeao": "Ahri", "time": "ORDER", "nivel": level, "kills": kills, "deaths": deaths,
            "assists": assists, "cs": cs, "gold_atual": gold, "itens": list(items), "visao": vision,
            "morto_agora": False,
        },
        "aliados": [{"nome": "Aliado", "campeao": "Lux", "time": "ORDER", "kills": ally_kills}],
        "inimigos": [{"nome": "Rival", "campeao": "Zed", "time": "CHAOS", "kills": 0}],
        "eventos_recentes": list(events),
    }


def new_recorder(first_reading):
    recorder = MatchRecorder(clock=lambda: datetime(2026, 11, 3, 21, 40))
    recorder.start(first_reading, "Analítico / Tryhard")
    recorder.update(first_reading)
    return recorder


class MatchRecorderTests(unittest.TestCase):
    def test_short_tracking_is_discarded(self):
        recorder = new_recorder(reading(0))
        recorder.update(reading(MIN_TRACKED_SECONDS - 3))

        self.assertIsNone(recorder.finish())
        self.assertFalse(recorder.active)

    def test_finish_without_match_returns_none(self):
        recorder = MatchRecorder()
        recorder.record_tip(100, "Dica fora de partida")
        self.assertIsNone(recorder.finish())

    def test_kills_and_deaths_use_event_details_when_names_match(self):
        recorder = new_recorder(reading(0))
        recorder.update(reading(200, kills=1, events=[
            {"id": 1, "tipo": "ChampionKill", "timestamp": 198.4, "assassino": "Eu", "vitima": "Rival"},
        ]))
        recorder.update(reading(300, kills=1, deaths=1, events=[
            {"id": 2, "tipo": "ChampionKill", "timestamp": 297.0, "assassino": "Rival", "vitima": "Eu"},
        ]))
        recorder.update(reading(303, kills=1, deaths=1, assists=1))
        recorder.update(reading(400, kills=1, deaths=2, assists=1, events=[
            {"id": 3, "tipo": "ChampionKill", "timestamp": 399.0, "assassino": "Turret_T2_L_03_A", "vitima": "Eu"},
        ]))
        recorder.update(reading(500, kills=1, deaths=3, assists=1))

        match = recorder.finish()

        self.assertEqual(match["eventos"], [
            {"t": 198, "tipo": "abate", "vitima": "Zed"},
            {"t": 297, "tipo": "morte", "por": "Zed"},
            {"t": 303, "tipo": "assistencia"},
            {"t": 399, "tipo": "morte", "por": "uma torre"},
            {"t": 500, "tipo": "morte"},
        ])

    def test_objectives_are_recorded_once_with_the_team_that_took_them(self):
        objectives = [
            {"id": 10, "tipo": "DragonKill", "timestamp": 400, "assassino": "Aliado", "dragao": "Fire"},
            {"id": 11, "tipo": "TurretKilled", "timestamp": 450, "assassino": "Rival", "torre": "Turret_T1_L_03_A"},
            {"id": 12, "tipo": "InhibKilled", "timestamp": 500, "assassino": "Aliado", "inibidor": "Barracks_T2_R1"},
            {"id": 13, "tipo": "BaronKill", "timestamp": 550, "assassino": "Rival"},
            {"id": 14, "tipo": "HeraldKill", "timestamp": 560, "assassino": "Minion_T100L"},
        ]
        recorder = new_recorder(reading(0))
        recorder.update(reading(570, events=objectives))
        recorder.update(reading(573, events=objectives))

        match = recorder.finish()

        self.assertEqual(match["eventos"], [
            {"t": 400, "tipo": "objetivo", "objetivo": "dragao", "lado": "aliado", "dragao": "Fire"},
            {"t": 450, "tipo": "objetivo", "objetivo": "torre", "lado": "inimigo"},
            {"t": 500, "tipo": "objetivo", "objetivo": "inibidor", "lado": "aliado"},
            {"t": 550, "tipo": "objetivo", "objetivo": "barao", "lado": "inimigo"},
            {"t": 560, "tipo": "objetivo", "objetivo": "arauto"},
        ])

    def test_events_before_tracking_started_are_ignored(self):
        old_dragon = {"id": 1, "tipo": "DragonKill", "timestamp": 300, "assassino": "Aliado", "dragao": "Water"}
        recorder = new_recorder(reading(600, events=[old_dragon]))
        recorder.update(reading(900, events=[old_dragon]))

        self.assertEqual(recorder.finish()["eventos"], [])

    def test_items_and_level_milestones(self):
        recorder = new_recorder(reading(0, level=5))
        recorder.update(reading(300, level=6, items=["Companheiro de Luden"]))
        recorder.update(reading(600, level=11, items=["Companheiro de Luden", "Sapatos do Feiticeiro"]))

        self.assertEqual(recorder.finish()["eventos"], [
            {"t": 300, "tipo": "item", "item": "Companheiro de Luden"},
            {"t": 300, "tipo": "nivel", "nivel": 6},
            {"t": 600, "tipo": "item", "item": "Sapatos do Feiticeiro"},
            {"t": 600, "tipo": "nivel", "nivel": 11},
        ])

    def test_numbers_summarize_the_whole_match(self):
        recorder = new_recorder(reading(0))
        for seconds in range(3, 901, 3):
            recorder.update(reading(seconds, cs=seconds // 6))
        recorder.update(reading(903, kills=4, deaths=2, assists=6, cs=150, level=13, ally_kills=10, vision=17,
                                items=["Companheiro de Luden"]))

        numbers = recorder.finish()["numeros"]

        self.assertEqual(numbers["kda"], 5.0)
        self.assertEqual(numbers["abates_do_time"], 14)
        self.assertEqual(numbers["participacao"], 0.71)
        self.assertEqual(numbers["cs_por_min"], 10.0)
        self.assertEqual(numbers["cs_aos_10"], 100)
        self.assertEqual(numbers["nivel"], 13)
        self.assertEqual(numbers["visao"], 17)
        self.assertEqual(numbers["itens"], ["Companheiro de Luden"])

    def test_idle_gold_counts_time_above_threshold_but_not_reconnection_gaps(self):
        recorder = new_recorder(reading(0, gold=2000))
        recorder.update(reading(3, gold=2000))
        recorder.update(reading(6, gold=500))
        recorder.update(reading(9, gold=2500))
        recorder.update(reading(90, gold=2500))
        recorder.update(reading(93, gold=2500))
        recorder.update(reading(300, gold=500))

        self.assertEqual(recorder.finish()["numeros"]["ouro_parado_seg"], 9)

    def test_game_end_event_sets_the_result(self):
        recorder = new_recorder(reading(0))
        recorder.update(reading(1500, events=[{"id": 99, "tipo": "GameEnd", "timestamp": 1500, "resultado": "Win"}]))

        self.assertEqual(recorder.finish()["resultado"], "vitoria")

    def test_tips_keep_game_time_question_and_event_kind(self):
        recorder = new_recorder(reading(0))
        recorder.update(reading(500))
        recorder.record_tip(450, "Recua e espera o jungle.", event_kind="death")
        recorder.record_tip(None, "Vale, mas empurra a wave antes.", question="vale ir no dragão?")

        self.assertEqual(recorder.finish()["falas"], [
            {"t": 450, "texto": "Recua e espera o jungle.", "evento": "death"},
            {"t": 500, "texto": "Vale, mas empurra a wave antes.", "pergunta": "vale ir no dragão?"},
        ])

    def test_partial_flag_metadata_and_final_sample(self):
        recorder = new_recorder(reading(0))
        for seconds in range(3, 302, 3):
            recorder.update(reading(seconds))
        recorder.update(reading(301))

        match = recorder.finish(partial=True)

        self.assertTrue(match["parcial"])
        self.assertEqual(match["campeao"], "Ahri")
        self.assertEqual(match["personalidade"], "Analítico / Tryhard")
        self.assertEqual(match["inicio"], "2026-11-03T21:40:00")
        # A última leitura entra nas amostras mesmo fora do intervalo de 15 s.
        self.assertEqual(match["amostras"][-1]["t"], 301)
        self.assertLessEqual(len(match["amostras"]), 22)
        self.assertFalse(recorder.active)


if __name__ == "__main__":
    unittest.main()
