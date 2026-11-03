import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

import post_match_report
from post_match_report import (
    ReportWriter,
    _duration,
    _number,
    _slug,
    render_html,
    report_basename,
    review_payload,
    save_report,
)

FIXTURE = Path(__file__).parent / "fixtures" / "sample_match.json"


def sample_match(**overrides):
    match = {
        "versao_app": "3.3.0",
        "inicio": "2026-11-03T21:40:00",
        "fim": "2026-11-03T22:09:00",
        "campeao": "Ahri",
        "modo": "CLASSIC",
        "mapa": "Map11",
        "personalidade": "Analítico / Tryhard",
        "resultado": "vitoria",
        "parcial": False,
        "inicio_seg": 0,
        "fim_seg": 1694,
        "amostras": [
            {"t": 0, "nivel": 1, "kills": 0, "deaths": 0, "assists": 0, "cs": 0, "ouro": 500, "morto": False},
            {"t": 900, "nivel": 11, "kills": 3, "deaths": 1, "assists": 4, "cs": 110, "ouro": 2100, "morto": False},
            {"t": 1694, "nivel": 16, "kills": 7, "deaths": 3, "assists": 9, "cs": 212, "ouro": 800, "morto": False},
        ],
        "eventos": [
            {"t": 312, "tipo": "abate", "vitima": "Zed"},
            {"t": 640, "tipo": "morte", "por": "Zed"},
            {"t": 700, "tipo": "objetivo", "objetivo": "dragao", "lado": "aliado", "dragao": "Fire"},
            {"t": 820, "tipo": "objetivo", "objetivo": "torre", "lado": "inimigo"},
            {"t": 905, "tipo": "item", "item": "Companheiro de Luden"},
        ],
        "falas": [
            {"t": 645, "texto": "Revise a posição antes de avançar sem visão.", "evento": "death"},
            {"t": 1000, "texto": "Vale, com o jungle por perto.", "pergunta": "vale ir no barão?"},
        ],
        "numeros": {
            "kills": 7, "deaths": 3, "assists": 9, "kda": 5.33, "abates_do_time": 25, "participacao": 0.64,
            "cs": 212, "cs_por_min": 7.5, "cs_aos_10": 68, "nivel": 16, "visao": 21,
            "itens": ["Companheiro de Luden", "Sapatos do Feiticeiro"], "ouro_parado_seg": 200,
        },
        "analise": {"fortes": ["Bom farm."], "treinar": ["Menos mortes sem visão."]},
    }
    match.update(overrides)
    return match


class RenderTests(unittest.TestCase):
    def test_page_shows_numbers_analysis_and_timeline(self):
        page = render_html(sample_match())

        for expected in (
            "<h1>Ahri</h1>", "Vitória", "7 / 3 / 9", "KDA 5,33", "64%", "de 25 abates do time",
            "7,5 por minuto · 68 aos 10 min", "3 min 20 s", "Pontos fortes", "Menos mortes sem visão.",
            "Abate em Zed", "Morte para Zed", "Dragão Infernal para o seu time", "Torre perdida",
            "Item finalizado: Companheiro de Luden", "Dica automática · morte", "“vale ir no barão?”",
            "3 de novembro de 2026, 21:40", "28:14 de jogo", "Coach Analítico / Tryhard",
            "Fim da partida: vitória",
        ):
            self.assertIn(expected, page)

    def test_dynamic_text_is_escaped_and_page_is_self_contained(self):
        match = sample_match(campeao="<b>Ahri</b>")
        match["falas"][0]["texto"] = "<script>alert(1)</script>"
        match["numeros"]["itens"] = ['<img src=x onerror="alert(1)">']

        page = render_html(match)

        self.assertNotIn("<script", page)
        self.assertNotIn("<img", page)
        self.assertNotIn("<b>Ahri", page)
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", page)
        self.assertNotIn("http://", page)
        self.assertNotIn("https://", page)

    def test_optional_sections_and_notes(self):
        page = render_html(sample_match(
            resultado=None, parcial=True, inicio_seg=312, analise=None, amostras=[], eventos=[], falas=[],
        ))

        self.assertIn("Resultado não informado", page)
        self.assertIn("Parcial", page)
        self.assertIn("a partir de 05:12", page)
        self.assertIn("fechado antes do fim", page)
        self.assertNotIn("Análise do coach", page)
        self.assertNotIn("<svg", page)
        self.assertNotIn("Linha do tempo", page)

    def test_perfect_kda(self):
        match = sample_match()
        match["numeros"].update(deaths=0, kda=16.0)
        self.assertIn("KDA perfeito", render_html(match))

    def test_brazilian_number_formats(self):
        self.assertEqual(_number(1800), "1.800")
        self.assertEqual(_number(7.5, 1), "7,5")
        self.assertEqual(_number(12345.678, 2), "12.345,68")
        self.assertEqual(_duration(200), "3 min 20 s")
        self.assertEqual(_duration(120), "2 min")
        self.assertEqual(_duration(0), "0 s")

    def test_sample_fixture_renders(self):
        match = json.loads(FIXTURE.read_text(encoding="utf-8"))
        page = render_html(match)
        self.assertIn("Análise do coach", page)
        self.assertEqual(page.count("<svg"), 2)


class ReviewPayloadTests(unittest.TestCase):
    def test_payload_has_numbers_and_readable_timeline(self):
        payload = review_payload(sample_match(inicio_seg=312))

        self.assertEqual(payload["resultado"], "vitória")
        self.assertEqual(payload["duracao"], "28:14")
        self.assertEqual(payload["acompanhada_a_partir_de"], "05:12")
        self.assertEqual(payload["numeros"]["participacao"], 0.64)
        self.assertIn("ouro_parado_seg", payload["numeros"]["observacao"])
        self.assertIn("10:40 Morte para Zed", payload["linha_do_tempo"])
        self.assertNotIn("falas", payload)


class SaveTests(unittest.TestCase):
    def test_file_names_are_safe_for_any_champion(self):
        self.assertEqual(_slug("Kai'Sa"), "Kai-Sa")
        self.assertEqual(_slug("Nunu & Willump"), "Nunu-Willump")
        self.assertEqual(_slug("Dr. Mundo"), "Dr-Mundo")
        self.assertEqual(_slug(None), "partida")
        self.assertEqual(report_basename(sample_match(campeao="Kai'Sa")), "2026-11-03_21-40_Kai-Sa")

    def test_reports_are_never_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            first = save_report(sample_match(), Path(directory) / "partidas")
            second = save_report(sample_match(), Path(directory) / "partidas")

            self.assertEqual(first.name, "2026-11-03_21-40_Ahri.html")
            self.assertEqual(second.name, "2026-11-03_21-40_Ahri_2.html")
            saved = json.loads(first.with_suffix(".json").read_text(encoding="utf-8"))
            self.assertEqual(saved["campeao"], "Ahri")


class ReportWriterTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.directory = Path(temporary.name) / "partidas"
        browser = patch("post_match_report.webbrowser.open")
        self.open_browser = browser.start()
        self.addCleanup(browser.stop)
        quiet = patch("builtins.print")
        self.print = quiet.start()
        self.addCleanup(quiet.stop)

    def _saved_page(self):
        pages = list(self.directory.glob("*.html"))
        self.assertEqual(len(pages), 1)
        return pages[0], pages[0].read_text(encoding="utf-8")

    def test_report_gets_the_analysis_and_opens_in_the_browser(self):
        review = Mock(return_value={"fortes": ["Farm consistente."], "treinar": ["Use mais sentinelas."]})
        writer = ReportWriter(self.directory, review=review)

        writer.submit(sample_match(analise=None), "2", {"nome": "Teste"})
        writer.wait(5)

        path, page = self._saved_page()
        self.assertIn("Use mais sentinelas.", page)
        review.assert_called_once()
        self.assertEqual(review.call_args.args[1:], ("2", {"nome": "Teste"}))
        self.open_browser.assert_called_once_with(path.resolve().as_uri())

    def test_report_is_kept_when_the_analysis_fails(self):
        writer = ReportWriter(self.directory, open_browser=False, review=Mock(side_effect=RuntimeError("sem chave")))

        writer.submit(sample_match(analise=None), "1", {})
        writer.wait(5)

        _, page = self._saved_page()
        self.assertNotIn("Análise do coach", page)
        self.open_browser.assert_not_called()
        self.assertIn("sem chave", " ".join(str(call.args[0]) for call in self.print.call_args_list))

    def test_partial_report_skips_analysis_and_browser(self):
        review = Mock()
        writer = ReportWriter(self.directory, review=review)

        path = writer.write_partial(sample_match(analise=None, parcial=True))

        self.assertTrue(path.exists())
        review.assert_not_called()
        self.open_browser.assert_not_called()

    def test_disabled_writer_does_nothing(self):
        review = Mock()
        writer = ReportWriter(self.directory, enabled=False, review=review)

        writer.submit(sample_match(), "1", {})
        writer.wait(5)

        self.assertIsNone(writer.write_partial(sample_match()))
        self.assertFalse(self.directory.exists())
        review.assert_not_called()

    def test_missing_match_is_ignored(self):
        writer = ReportWriter(self.directory)
        writer.submit(None, "1", {})
        self.assertIsNone(writer.write_partial(None))
        self.assertFalse(self.directory.exists())

    def test_save_errors_never_raise(self):
        with patch.object(post_match_report, "save_report", side_effect=PermissionError("negado")):
            writer = ReportWriter(self.directory)
            self.assertIsNone(writer.write_partial(sample_match()))


if __name__ == "__main__":
    unittest.main()
