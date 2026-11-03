"""Monta e salva a página do resumo pós-partida."""

from __future__ import annotations

import html
import itertools
import json
import math
import re
import threading
import time
import unicodedata
import webbrowser
from datetime import datetime
from pathlib import Path

from brain import ask_post_match_review
from coach_engine import RICH_GOLD_THRESHOLD

# A partir deste ponto, o resumo avisa que o coach pegou a partida em andamento.
LATE_START_SECONDS = 60

MONTHS = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)
MODES = {
    "CLASSIC": "Clássico",
    "ARAM": "ARAM",
    "PRACTICETOOL": "Modo de Prática",
    "CHERRY": "Arena",
    "URF": "URF",
}
RESULTS = {"vitoria": ("Vitória", "win"), "derrota": ("Derrota", "loss")}
DRAGONS = {
    "Fire": "Infernal",
    "Water": "do Oceano",
    "Earth": "da Montanha",
    "Air": "das Nuvens",
    "Hextech": "Hextec",
    "Chemtech": "Quimtec",
    "Elder": "Ancião",
}
TIP_EVENTS = {
    "low_health": "vida baixa",
    "death": "morte",
    "respawn": "renascimento",
    "rich": "ouro acumulado",
    "level_up": "subida de nível",
    "kill": "abate",
    "cs_burst": "farm",
}
EVENT_CLASSES = {
    "abate": "kill",
    "assistencia": "assist",
    "morte": "death",
    "item": "item",
    "nivel": "level",
    "objetivo": "objective",
}
CS_COLOR = "#67e0f2"
GOLD_COLOR = "#f2b84b"

CSS = """
:root{--bg:#0b0d13;--card:#15171e;--card-2:#1c1f28;--line:#2a2e3b;--text:#f1f3f8;--soft:#b9c0d2;--muted:#8a91a3;
--violet:#a996ff;--teal:#67e0f2;--green:#5ad08a;--amber:#f2b84b;--red:#f07178}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;color:var(--text);background:radial-gradient(900px 480px at 0% -8%,rgba(124,92,255,.2),transparent 60%),
radial-gradient(700px 420px at 100% 0%,rgba(34,211,238,.08),transparent 60%),var(--bg);background-repeat:no-repeat;
font:16px/1.55 "Segoe UI Variable Text","Segoe UI",system-ui,-apple-system,"Helvetica Neue",Arial,sans-serif}
p{margin:0}
.page{max-width:1040px;margin:0 auto;padding:44px 24px 56px}
.eyebrow{font-size:13px;font-weight:600;letter-spacing:.16em;text-transform:uppercase;color:var(--teal)}
h1{margin:6px 0 14px;font-size:48px;line-height:1.05;font-weight:700;letter-spacing:-.015em}
h2{margin:0 0 14px;font-size:17px;font-weight:600}
h3{margin:0 0 10px;font-size:14px;font-weight:600;letter-spacing:.02em}
.pills{display:flex;flex-wrap:wrap;gap:8px}
.pill{display:inline-block;padding:4px 12px;border:1px solid;border-radius:999px;font-size:14px;font-weight:600}
.pill.win{color:var(--green);background:rgba(90,208,138,.12);border-color:rgba(90,208,138,.35)}
.pill.loss{color:var(--red);background:rgba(240,113,120,.12);border-color:rgba(240,113,120,.35)}
.pill.unknown{color:var(--soft);background:rgba(255,255,255,.05);border-color:var(--line)}
.pill.partial{color:var(--amber);background:rgba(242,184,75,.12);border-color:rgba(242,184,75,.35)}
.meta{margin-top:12px;color:var(--soft)}
.note{margin-top:8px;color:var(--muted);font-size:14px}
.stats{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-top:28px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 16px}
.stat .label{color:var(--muted);font-size:13px}
.stat .value{margin-top:2px;font-size:26px;font-weight:700;font-variant-numeric:tabular-nums;white-space:nowrap}
.stat .sub{margin-top:2px;color:var(--soft);font-size:13px}
.card{margin-top:16px;background:var(--card);border:1px solid var(--line);border-radius:16px;padding:20px 22px}
.chips{display:flex;flex-wrap:wrap;gap:8px;margin:0;padding:0;list-style:none}
.chip{padding:6px 12px;border:1px solid rgba(169,150,255,.3);border-radius:999px;background:rgba(169,150,255,.1);
color:#ddd6ff;font-size:14px}
.columns{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:20px}
.analysis ul{display:grid;gap:10px;margin:0;padding:0;list-style:none}
.analysis li{position:relative;padding-left:22px;color:var(--soft)}
.analysis li::before{content:"";position:absolute;left:2px;top:.55em;width:9px;height:9px;border-radius:50%}
.analysis .good h3{color:var(--green)}
.analysis .good li::before{background:var(--green)}
.analysis .train h3{color:var(--amber)}
.analysis .train li::before{background:var(--amber)}
.charts{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:16px;margin-top:16px}
.charts .card{margin-top:0}
.chart{display:block;width:100%;height:auto}
.chart text{fill:var(--muted);font-size:11px;font-family:inherit}
.chart .grid{stroke:var(--line);stroke-width:1}
.chart .death{stroke:var(--red);stroke-width:1.2;stroke-dasharray:3 4;opacity:.75}
.chart .limit{stroke:var(--amber);stroke-width:1;stroke-dasharray:6 5;opacity:.6}
.chart-foot{display:flex;flex-wrap:wrap;gap:6px 16px;margin-top:8px;color:var(--muted);font-size:13px}
.swatch{display:inline-block;width:14px;margin-right:6px;border-top:2px dashed var(--red);vertical-align:middle}
.timeline{position:relative;margin:0;padding:0;list-style:none}
.timeline::before{content:"";position:absolute;left:75px;top:6px;bottom:6px;width:2px;background:var(--line)}
.timeline li{position:relative;display:grid;grid-template-columns:56px 16px 1fr;gap:12px;align-items:start;padding:6px 0}
.timeline time{padding-top:1px;color:var(--muted);font-size:14px;font-variant-numeric:tabular-nums;text-align:right}
.dot{width:12px;height:12px;margin:5px 0 0 2px;border-radius:50%;background:var(--muted);box-shadow:0 0 0 3px var(--card)}
.kill .dot{background:var(--green)}
.assist .dot{background:var(--teal)}
.death .dot{background:var(--red)}
.death p{color:#ffc2c6}
.item .dot{background:var(--violet)}
.level .dot{background:var(--soft)}
.objective .dot{border-radius:3px}
.objective.ally .dot{background:var(--green)}
.objective.enemy .dot{background:var(--red)}
.tip .dot{border:2px solid var(--violet);background:var(--card-2)}
.end .dot{background:var(--text)}
.bubble{padding:10px 14px;border:1px solid var(--line);border-radius:12px;background:var(--card-2)}
.bubble .caption{color:var(--violet);font-size:12px;font-weight:600;letter-spacing:.04em;text-transform:uppercase}
.bubble .question{margin-top:4px;color:var(--soft);font-style:italic}
.bubble p+p{margin-top:4px}
footer{margin-top:28px;color:var(--muted);font-size:13px}
@media (max-width:560px){.page{padding:28px 16px 40px}h1{font-size:36px}.card{padding:16px}
.timeline::before{left:61px}.timeline li{grid-template-columns:44px 14px 1fr;gap:10px}}
"""


def _e(value) -> str:
    return html.escape(str(value), quote=True)


def _number(value, decimals: int = 0) -> str:
    """Número no formato brasileiro: 1.800 e 7,5."""
    text = f"{value:,.{decimals}f}"
    return text.replace(",", " ").replace(".", ",").replace(" ", ".")


def _clock(seconds) -> str:
    minutes, secs = divmod(max(0, round(seconds or 0)), 60)
    return f"{minutes:02d}:{secs:02d}"


def _duration(seconds) -> str:
    minutes, secs = divmod(max(0, round(seconds or 0)), 60)
    if minutes and secs:
        return f"{minutes} min {secs} s"
    if minutes:
        return f"{minutes} min"
    return f"{secs} s"


def _date(moment: datetime) -> str:
    month = MONTHS[moment.month - 1]
    return f"{moment.day} de {month} de {moment.year}, {moment:%H:%M}"


def _objective_label(event: dict) -> str:
    objective = event.get("objetivo")
    side = event.get("lado")
    if objective == "torre":
        return {"aliado": "Torre inimiga destruída", "inimigo": "Torre perdida"}.get(side, "Torre destruída")
    if objective == "inibidor":
        return {"aliado": "Inibidor inimigo destruído", "inimigo": "Inibidor perdido"}.get(side, "Inibidor destruído")
    if objective == "dragao":
        dragon = event.get("dragao")
        name = f"Dragão {DRAGONS.get(dragon, dragon)}" if dragon else "Dragão"
    elif objective == "arauto":
        name = "Arauto do Vale"
    elif objective == "barao":
        name = "Barão Na'Shor"
    else:
        name = "Objetivo"
    suffix = {"aliado": " para o seu time", "inimigo": " para o time inimigo"}.get(side, "")
    return name + suffix


def event_label(event: dict) -> str:
    """Texto curto de um evento da linha do tempo."""
    kind = event.get("tipo")
    if kind == "abate":
        return f"Abate em {event['vitima']}" if event.get("vitima") else "Abate"
    if kind == "assistencia":
        return "Assistência"
    if kind == "morte":
        return f"Morte para {event['por']}" if event.get("por") else "Morte"
    if kind == "item":
        return f"Item finalizado: {event.get('item')}"
    if kind == "nivel":
        return f"Nível {event.get('nivel')}"
    if kind == "objetivo":
        return _objective_label(event)
    return str(kind)


def tip_label(event_kind: str | None) -> str:
    if not event_kind:
        return ""
    if event_kind.startswith("item:"):
        return "item novo de um inimigo"
    if event_kind.startswith("event:"):
        return "objetivo"
    return TIP_EVENTS.get(event_kind, event_kind)


def review_payload(match: dict) -> dict:
    """Resumo compacto da partida para a análise final da IA."""
    numbers = dict(match.get("numeros") or {})
    numbers["observacao"] = (
        f"ouro_parado_seg = segundos com {RICH_GOLD_THRESHOLD}+ de ouro sem gastar; "
        "participacao = fração dos abates do time em que houve abate ou assistência"
    )
    payload = {
        "campeao": match.get("campeao"),
        "modo": MODES.get(match.get("modo"), match.get("modo")),
        "resultado": RESULTS.get(match.get("resultado"), ("desconhecido", ""))[0].lower(),
        "duracao": _clock(match.get("fim_seg")),
        "numeros": numbers,
        "linha_do_tempo": [f"{_clock(event['t'])} {event_label(event)}" for event in match.get("eventos", [])],
    }
    if (match.get("inicio_seg") or 0) > LATE_START_SECONDS:
        payload["acompanhada_a_partir_de"] = _clock(match["inicio_seg"])
    return payload


def _render_header(match: dict) -> str:
    started = datetime.fromisoformat(match["inicio"])
    result_label, result_class = RESULTS.get(match.get("resultado"), ("Resultado não informado", "unknown"))
    pills = f'<span class="pill {result_class}">{result_label}</span>'
    if match.get("parcial"):
        pills += '<span class="pill partial">Parcial</span>'
    meta = [_date(started), f"{_clock(match.get('fim_seg'))} de jogo"]
    mode = MODES.get(match.get("modo"), match.get("modo"))
    if mode:
        meta.append(mode)
    if match.get("personalidade"):
        meta.append(f"Coach {match['personalidade']}")
    notes = ""
    if (match.get("inicio_seg") or 0) > LATE_START_SECONDS:
        start = _clock(match["inicio_seg"])
        notes += (
            f'<p class="note">O coach acompanhou a partida a partir de {start}. Os números finais valem para a '
            "partida toda; a linha do tempo e os gráficos começam nesse ponto.</p>"
        )
    if match.get("parcial"):
        notes += '<p class="note">O coach foi fechado antes do fim da partida.</p>'
    meta_text = " · ".join(_e(part) for part in meta)
    champion = _e(match.get("campeao") or "Partida")
    return (
        '<header class="hero"><p class="eyebrow">Resumo da partida</p>'
        f'<h1>{champion}</h1><div class="pills">{pills}</div><p class="meta">{meta_text}</p>{notes}</header>'
    )


def _render_stats(numbers: dict) -> str:
    kills, deaths, assists = numbers.get("kills", 0), numbers.get("deaths", 0), numbers.get("assists", 0)
    kda = "KDA perfeito" if deaths == 0 else f"KDA {_number(numbers.get('kda', 0), 2)}"
    participation = numbers.get("participacao")
    team_kills = numbers.get("abates_do_time", 0)
    cs_details = []
    if numbers.get("cs_por_min") is not None:
        cs_details.append(f"{_number(numbers['cs_por_min'], 1)} por minuto")
    if numbers.get("cs_aos_10") is not None:
        cs_details.append(f"{numbers['cs_aos_10']} aos 10 min")
    cards = [
        ("K / D / A", f"{kills} / {deaths} / {assists}", kda),
        (
            "Participação",
            f"{round(participation * 100)}%" if participation is not None else "—",
            f"de {team_kills} abates do time" if team_kills else "o time não teve abates",
        ),
        ("CS", str(numbers.get("cs", 0)), " · ".join(cs_details)),
        ("Ouro parado", _duration(numbers.get("ouro_parado_seg")), f"com {_number(RICH_GOLD_THRESHOLD)}+ sem gastar"),
        ("Nível", str(numbers.get("nivel", 0)), ""),
        ("Placar de visão", str(numbers.get("visao", 0)), ""),
    ]
    rendered = ""
    for label, value, detail in cards:
        sub = f'<p class="sub">{_e(detail)}</p>' if detail else ""
        rendered += f'<div class="stat"><p class="label">{_e(label)}</p><p class="value">{_e(value)}</p>{sub}</div>'
    return f'<section class="stats" aria-label="Números da partida">{rendered}</section>'


def _render_items(items: list[str]) -> str:
    if not items:
        return ""
    chips = "".join(f'<li class="chip">{_e(item)}</li>' for item in items)
    return f'<section class="card"><h2>Itens finais</h2><ul class="chips">{chips}</ul></section>'


def _render_analysis(analysis: dict | None) -> str:
    if not analysis or not (analysis.get("fortes") or analysis.get("treinar")):
        return ""
    columns = ""
    for title, points, css_class in (
        ("Pontos fortes", analysis.get("fortes"), "good"),
        ("Pontos a treinar", analysis.get("treinar"), "train"),
    ):
        if points:
            items = "".join(f"<li>{_e(point)}</li>" for point in points)
            columns += f'<div class="{css_class}"><h3>{title}</h3><ul>{items}</ul></div>'
    return f'<section class="card analysis"><h2>Análise do coach</h2><div class="columns">{columns}</div></section>'


def _nice_step(peak: float) -> float:
    raw = peak / 4
    magnitude = 10 ** math.floor(math.log10(raw)) if raw > 0 else 1
    for factor in (1, 2, 2.5, 5, 10):
        if factor * magnitude >= raw:
            return max(1, factor * magnitude)
    return max(1, 10 * magnitude)


def _line_chart(chart_id: str, label: str, points: list[tuple[int, int]], deaths: list[int],
                color: str, threshold: int | None = None) -> str:
    width, height = 560, 230
    left, right, top, bottom = 48, 16, 16, 30
    start = points[0][0]
    end = max(points[-1][0], start + 60)
    peak = max([value for _, value in points] + [threshold or 0, 4])
    step = _nice_step(peak)
    ceiling = step * math.ceil(peak / step)

    def x(seconds):
        return left + (seconds - start) / (end - start) * (width - left - right)

    def y(value):
        return height - bottom - value / ceiling * (height - top - bottom)

    parts = [
        f'<svg class="chart" viewBox="0 0 {width} {height}" role="img" aria-label="{_e(label)}">',
        f"<title>{_e(label)}</title>",
        f'<defs><linearGradient id="fill-{chart_id}" x1="0" y1="0" x2="0" y2="1">'
        f'<stop offset="0" stop-color="{color}" stop-opacity="0.28"/>'
        f'<stop offset="1" stop-color="{color}" stop-opacity="0"/></linearGradient></defs>',
    ]
    value = 0
    while value <= ceiling:
        parts.append(f'<line class="grid" x1="{left}" x2="{width - right}" y1="{y(value):.1f}" y2="{y(value):.1f}"/>')
        parts.append(f'<text x="{left - 8}" y="{y(value) + 4:.1f}" text-anchor="end">{_number(value)}</text>')
        value += step
    tick = 300 if end - start <= 2400 else 600
    for seconds in range(math.ceil(start / tick) * tick, int(end) + 1, tick):
        parts.append(f'<text x="{x(seconds):.1f}" y="{height - 8}" text-anchor="middle">{seconds // 60} min</text>')
    if threshold:
        parts.append(
            f'<line class="limit" x1="{left}" x2="{width - right}" y1="{y(threshold):.1f}" y2="{y(threshold):.1f}"/>'
        )
        # O rótulo fica à esquerda: no começo da partida o ouro ainda é baixo e não cobre o texto.
        parts.append(
            f'<text x="{left + 6}" y="{y(threshold) - 6:.1f}" text-anchor="start">{_number(threshold)}</text>'
        )
    for seconds in deaths:
        if start <= seconds <= end:
            parts.append(
                f'<line class="death" x1="{x(seconds):.1f}" x2="{x(seconds):.1f}" y1="{top}" y2="{height - bottom}"/>'
            )
    coordinates = [f"{x(seconds):.1f},{y(value):.1f}" for seconds, value in points]
    area = f"M{x(points[0][0]):.1f},{y(0):.1f} L" + " L".join(coordinates) + f" L{x(points[-1][0]):.1f},{y(0):.1f} Z"
    parts.append(f'<path d="{area}" fill="url(#fill-{chart_id})"/>')
    parts.append(
        f'<polyline points="{" ".join(coordinates)}" fill="none" stroke="{color}" stroke-width="2.2" '
        'stroke-linejoin="round" stroke-linecap="round"/>'
    )
    parts.append("</svg>")
    return "".join(parts)


def _render_charts(match: dict) -> str:
    samples = match.get("amostras") or []
    if len(samples) < 2:
        return ""
    deaths = [event["t"] for event in match.get("eventos", []) if event.get("tipo") == "morte"]
    legend = '<span><span class="swatch"></span>Mortes</span>' if deaths else ""
    cs_chart = _line_chart(
        "cs", "CS ao longo da partida", [(sample["t"], sample["cs"]) for sample in samples], deaths, CS_COLOR,
    )
    gold_chart = _line_chart(
        "ouro", "Ouro disponível ao longo da partida", [(sample["t"], sample["ouro"]) for sample in samples],
        deaths, GOLD_COLOR, threshold=RICH_GOLD_THRESHOLD,
    )
    gold_note = f"<span>Linha tracejada: {_number(RICH_GOLD_THRESHOLD)} de ouro. A API do jogo só mostra o ouro ainda não gasto.</span>"
    return (
        '<section class="charts">'
        f'<div class="card"><h2>CS</h2>{cs_chart}<p class="chart-foot">{legend}</p></div>'
        f'<div class="card"><h2>Ouro disponível</h2>{gold_chart}<p class="chart-foot">{legend}{gold_note}</p></div>'
        "</section>"
    )


def _timeline_event(event: dict) -> str:
    css_class = EVENT_CLASSES.get(event.get("tipo"), "other")
    if event.get("tipo") == "objetivo":
        css_class += {"aliado": " ally", "inimigo": " enemy"}.get(event.get("lado"), "")
    when = _clock(event["t"])
    return (
        f'<li class="{css_class}"><time>{when}</time><span class="dot" aria-hidden="true"></span>'
        f"<p>{_e(event_label(event))}</p></li>"
    )


def _timeline_tip(tip: dict) -> str:
    when = _clock(tip["t"])
    if tip.get("pergunta"):
        caption = "Pergunta por voz"
        question = f'<p class="question">“{_e(tip["pergunta"])}”</p>'
    else:
        label = tip_label(tip.get("evento"))
        caption = f"Dica automática · {label}" if label else "Dica automática"
        question = ""
    return (
        f'<li class="tip"><time>{when}</time><span class="dot" aria-hidden="true"></span>'
        f'<div class="bubble"><p class="caption">{_e(caption)}</p>{question}<p>{_e(tip["texto"])}</p></div></li>'
    )


def _render_timeline(match: dict) -> str:
    entries = [(event["t"], 0, _timeline_event(event)) for event in match.get("eventos", [])]
    entries += [(tip["t"], 1, _timeline_tip(tip)) for tip in match.get("falas", [])]
    if not entries:
        return ""
    if not match.get("parcial"):
        result = RESULTS.get(match.get("resultado"), ("", ""))[0]
        label = f"Fim da partida: {result.lower()}" if result else "Fim da partida"
        when = _clock(match.get("fim_seg"))
        entries.append((
            match.get("fim_seg") or 0, 2,
            f'<li class="end"><time>{when}</time><span class="dot" aria-hidden="true"></span>'
            f"<p><strong>{_e(label)}</strong></p></li>",
        ))
    entries.sort(key=lambda entry: (entry[0], entry[1]))
    items = "".join(entry[2] for entry in entries)
    return f'<section class="card"><h2>Linha do tempo</h2><ol class="timeline">{items}</ol></section>'


def render_html(match: dict) -> str:
    started = datetime.fromisoformat(match["inicio"])
    title = f"Resumo · {match.get('campeao') or 'Partida'} · {started:%d/%m/%Y %H:%M}"
    version = _e(match.get("versao_app", ""))
    body = "".join([
        _render_header(match),
        _render_stats(match.get("numeros") or {}),
        _render_analysis(match.get("analise")),
        _render_items((match.get("numeros") or {}).get("itens") or []),
        _render_charts(match),
        _render_timeline(match),
        f"<footer>Gerado pelo LoL AI Coach v{version}. Dados da Live Client Data API do jogo, que não informa "
        "posição no mapa nem visão real. Projeto de fã, sem vínculo com a Riot Games.</footer>",
    ])
    return (
        '<!doctype html>\n<html lang="pt-BR">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        '<meta name="color-scheme" content="dark">\n'
        f"<title>{_e(title)}</title>\n<style>{CSS}</style>\n</head>\n"
        f'<body>\n<main class="page">{body}</main>\n</body>\n</html>\n'
    )


def _slug(text: str | None) -> str:
    plain = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode()
    return re.sub(r"[^A-Za-z0-9]+", "-", plain).strip("-") or "partida"


def report_basename(match: dict) -> str:
    started = datetime.fromisoformat(match["inicio"])
    return f"{started:%Y-%m-%d_%H-%M}_{_slug(match.get('campeao'))}"


def write_report(match: dict, path: Path) -> None:
    """Regrava um resumo existente (por exemplo, depois que a análise da IA chega)."""
    path = Path(path)
    path.write_text(render_html(match), encoding="utf-8")
    path.with_suffix(".json").write_text(json.dumps(match, ensure_ascii=False, indent=2), encoding="utf-8")


def save_report(match: dict, directory: Path) -> Path:
    """Salva o resumo em um arquivo novo, sem sobrescrever partidas anteriores."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    base = report_basename(match)
    content = render_html(match)
    for number in itertools.count(1):
        path = directory / (f"{base}.html" if number == 1 else f"{base}_{number}.html")
        try:
            with open(path, "x", encoding="utf-8") as file:
                file.write(content)
        except FileExistsError:
            continue
        path.with_suffix(".json").write_text(json.dumps(match, ensure_ascii=False, indent=2), encoding="utf-8")
        return path


def _ask_review(match: dict, personality_id: str, profile: dict) -> dict:
    return ask_post_match_review(review_payload(match), personality_id, profile)


class ReportWriter:
    """Gera os resumos fora do loop principal: a análise da IA pode levar alguns segundos."""

    def __init__(self, directory: Path, enabled: bool = True, open_browser: bool = True, review=None):
        self.directory = Path(directory)
        self.enabled = enabled
        self.open_browser = open_browser
        self._review = review or _ask_review
        self._threads: list[threading.Thread] = []

    def submit(self, match: dict | None, personality_id: str, profile: dict) -> None:
        if not self.enabled or not match:
            return
        thread = threading.Thread(
            target=self._generate, args=(match, personality_id, profile), name="post-match-report", daemon=True,
        )
        self._threads = [running for running in self._threads if running.is_alive()] + [thread]
        thread.start()

    def write_partial(self, match: dict | None) -> Path | None:
        """Salva na hora, sem análise da IA nem navegador: usado quando o coach é fechado."""
        if not self.enabled or not match:
            return None
        return self._save(match)

    def wait(self, timeout: float) -> None:
        """Espera os resumos em andamento por no máximo `timeout` segundos no total."""
        running = [thread for thread in self._threads if thread.is_alive()]
        if not running:
            return
        deadline = time.monotonic() + timeout
        for thread in running:
            thread.join(max(0.0, deadline - time.monotonic()))

    def _generate(self, match: dict, personality_id: str, profile: dict) -> None:
        # Salva antes da análise: assim o resumo existe mesmo se a IA demorar ou falhar.
        path = self._save(match)
        if path is None:
            return
        try:
            match["analise"] = self._review(match, personality_id, profile)
        except Exception as exc:  # a análise é opcional; sem ela o resumo fica sem essa seção
            print(f"⚠️ Análise da partida indisponível: {exc}")
        else:
            try:
                write_report(match, path)
            except OSError as exc:
                print(f"⚠️ Não foi possível incluir a análise no resumo: {exc}")
        if self.open_browser:
            try:
                webbrowser.open(path.resolve().as_uri())
            except OSError as exc:
                print(f"⚠️ Não foi possível abrir o resumo no navegador: {exc}")

    def _save(self, match: dict) -> Path | None:
        try:
            path = save_report(match, self.directory)
        except Exception as exc:  # um problema no resumo nunca pode derrubar o coach
            print(f"⚠️ Não foi possível salvar o resumo da partida: {exc}")
            return None
        print(f"📊 Resumo da partida salvo em {path}")
        return path
