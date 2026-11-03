"""Coleta os dados da partida atual para o resumo pós-partida."""

from __future__ import annotations

from collections import Counter
from datetime import datetime

from coach_engine import RICH_GOLD_THRESHOLD
from config import APP_VERSION

# Trechos acompanhados mais curtos que isso (remake, coach aberto no fim) não geram resumo.
MIN_TRACKED_SECONDS = 180
SAMPLE_INTERVAL_SECONDS = 15
LEVEL_MILESTONES = (6, 11, 16)
CS_BENCHMARK_SECONDS = 600
# Intervalos maiores que isso entre leituras (reconexão) não contam como ouro parado.
MAX_READING_GAP_SECONDS = 30

OBJECTIVES = {
    "DragonKill": "dragao",
    "HeraldKill": "arauto",
    "BaronKill": "barao",
    "TurretKilled": "torre",
    "InhibKilled": "inibidor",
}
# Torres e inibidores trazem no nome o time dono: Turret_T2_L_03_A, Barracks_T1_C1.
STRUCTURE_OWNERS = {"_T1_": "ORDER", "_T2_": "CHAOS"}
GAME_RESULTS = {"Win": "vitoria", "Lose": "derrota"}


def _event_id(event: dict) -> str:
    event_id = event.get("id")
    return str(event_id) if event_id is not None else f"{event.get('tipo')}:{event.get('timestamp')}"


def _event_time(event: dict, fallback: int) -> int:
    try:
        return round(float(event.get("timestamp")))
    except (TypeError, ValueError):
        return fallback


def _snapshot(me: dict) -> dict:
    return {
        "nivel": me.get("nivel", 0) or 0,
        "kills": me.get("kills", 0) or 0,
        "deaths": me.get("deaths", 0) or 0,
        "assists": me.get("assists", 0) or 0,
        "cs": me.get("cs", 0) or 0,
        "gold_atual": me.get("gold_atual", 0) or 0,
        "morto_agora": bool(me.get("morto_agora")),
        "visao": me.get("visao", 0) or 0,
        "itens": list(me.get("itens", []) or []),
    }


def _players(summary: dict) -> dict[str, dict]:
    players = {}
    for entry in [summary.get("eu") or {}, *summary.get("aliados", []), *summary.get("inimigos", [])]:
        if entry.get("nome"):
            players[entry["nome"]] = {"campeao": entry.get("campeao"), "time": entry.get("time")}
    return players


def _killer(name: str | None, players: dict[str, dict]) -> str | None:
    """Campeão (ou estrutura/tropas) que aparece como autor de um abate."""
    if not name:
        return None
    if name in players:
        return players[name]["campeao"]
    if "Turret" in name:
        return "uma torre"
    if "Minion" in name:
        return "as tropas"
    if name.startswith("SRU_"):
        return "um monstro"
    return None


def _objective_side(event: dict, objective: str, players: dict[str, dict], my_team: str | None) -> str | None:
    """'aliado' quando o seu time conquistou o objetivo e 'inimigo' no caso contrário."""
    if not my_team:
        return None
    if objective in {"torre", "inibidor"}:
        structure = event.get(objective) or ""
        owner = next((team for code, team in STRUCTURE_OWNERS.items() if code in structure), None)
        if owner:
            return "inimigo" if owner == my_team else "aliado"
    killer = players.get(event.get("assassino") or "")
    if killer and killer.get("time"):
        return "aliado" if killer["time"] == my_team else "inimigo"
    return None


class MatchRecorder:
    """Guarda amostras, eventos e falas do coach durante uma partida."""

    def __init__(self, clock=datetime.now):
        self._clock = clock
        self._match: dict | None = None
        self._reset_tracking()

    def _reset_tracking(self) -> None:
        self._previous: dict | None = None
        self._last_time: int | None = None
        self._last_sample_time: int | None = None
        self._seen_events: set[str] = set()
        self._gold_idle_seconds = 0.0
        self._cs_at_10: int | None = None
        self._team_kills = 0

    @property
    def active(self) -> bool:
        return self._match is not None

    def start(self, summary: dict, personality: str) -> None:
        """Começa a acompanhar uma partida. Chame update() com a mesma leitura em seguida."""
        me = summary["eu"]
        game_time = summary.get("tempo_de_jogo_seg", 0) or 0
        self._reset_tracking()
        self._match = {
            "versao_app": APP_VERSION,
            "inicio": self._clock().isoformat(timespec="seconds"),
            "fim": None,
            "campeao": me.get("campeao"),
            "modo": summary.get("modo"),
            "mapa": summary.get("mapa"),
            "personalidade": personality,
            "resultado": None,
            "parcial": False,
            "inicio_seg": game_time,
            "fim_seg": game_time,
            "amostras": [],
            "eventos": [],
            "falas": [],
        }
        # Eventos anteriores ao início do acompanhamento não entram na linha do tempo.
        self._seen_events = {_event_id(event) for event in summary.get("eventos_recentes", [])}

    def update(self, summary: dict | None) -> None:
        if self._match is None or not summary or not summary.get("eu"):
            return
        me = summary["eu"]
        game_time = summary.get("tempo_de_jogo_seg", 0) or 0
        current = _snapshot(me)
        players = _players(summary)
        new_events = [event for event in summary.get("eventos_recentes", []) if _event_id(event) not in self._seen_events]
        self._seen_events.update(_event_id(event) for event in new_events)

        if self._previous is not None:
            self._track_gold_and_cs(self._previous, current, game_time)
            self._record_changes(self._previous, current, me.get("nome"), new_events, players, game_time)
        self._record_objectives(new_events, players, me.get("time"), game_time)

        self._team_kills = current["kills"] + sum(ally.get("kills", 0) or 0 for ally in summary.get("aliados", []))
        self._previous = current
        self._last_time = game_time
        self._match["fim_seg"] = game_time
        if self._last_sample_time is None or game_time - self._last_sample_time >= SAMPLE_INTERVAL_SECONDS:
            self._add_sample(game_time)

    def record_tip(self, game_time, text: str, question: str | None = None, event_kind: str | None = None) -> None:
        """Registra uma fala do coach: dica automática (event_kind) ou resposta a uma pergunta."""
        if self._match is None or not text:
            return
        if not isinstance(game_time, (int, float)):
            game_time = self._match["fim_seg"]
        tip = {"t": round(game_time), "texto": text}
        if question:
            tip["pergunta"] = question
        if event_kind:
            tip["evento"] = event_kind
        self._match["falas"].append(tip)

    def finish(self, partial: bool = False) -> dict | None:
        """Encerra a partida atual e devolve os dados do resumo, ou None se não houver o que mostrar."""
        match = self._match
        if match is None:
            return None
        try:
            if match["fim_seg"] - match["inicio_seg"] < MIN_TRACKED_SECONDS:
                return None
            if match["amostras"] and match["amostras"][-1]["t"] != match["fim_seg"]:
                self._add_sample(match["fim_seg"])
            match["fim"] = self._clock().isoformat(timespec="seconds")
            match["parcial"] = partial
            match["eventos"].sort(key=lambda event: event["t"])
            match["numeros"] = self._numbers(match)
            return match
        finally:
            self._match = None
            self._reset_tracking()

    def _track_gold_and_cs(self, previous: dict, current: dict, game_time: int) -> None:
        elapsed = game_time - self._last_time
        if 0 < elapsed <= MAX_READING_GAP_SECONDS and previous["gold_atual"] >= RICH_GOLD_THRESHOLD:
            self._gold_idle_seconds += elapsed
        if self._cs_at_10 is None and self._last_time < CS_BENCHMARK_SECONDS <= game_time:
            self._cs_at_10 = current["cs"] if game_time == CS_BENCHMARK_SECONDS else previous["cs"]

    def _record_changes(self, previous, current, my_name, new_events, players, game_time) -> None:
        new_deaths = max(0, current["deaths"] - previous["deaths"])
        new_kills = max(0, current["kills"] - previous["kills"])
        new_assists = max(0, current["assists"] - previous["assists"])
        # O evento ChampionKill traz o horário exato e o outro campeão, quando o nome bate.
        for event in new_events:
            if event.get("tipo") != "ChampionKill":
                continue
            when = _event_time(event, game_time)
            if new_deaths and event.get("vitima") == my_name:
                self._add_event(when, "morte", por=_killer(event.get("assassino"), players))
                new_deaths -= 1
            elif new_kills and event.get("assassino") == my_name:
                self._add_event(when, "abate", vitima=players.get(event.get("vitima") or "", {}).get("campeao"))
                new_kills -= 1
        for _ in range(new_deaths):
            self._add_event(game_time, "morte")
        for _ in range(new_kills):
            self._add_event(game_time, "abate")
        for _ in range(new_assists):
            self._add_event(game_time, "assistencia")
        for item in (Counter(current["itens"]) - Counter(previous["itens"])).elements():
            self._add_event(game_time, "item", item=item)
        for level in LEVEL_MILESTONES:
            if previous["nivel"] < level <= current["nivel"]:
                self._add_event(game_time, "nivel", nivel=level)

    def _record_objectives(self, new_events, players, my_team, game_time) -> None:
        for event in new_events:
            kind = event.get("tipo")
            if kind == "GameEnd" and event.get("resultado") in GAME_RESULTS:
                self._match["resultado"] = GAME_RESULTS[event["resultado"]]
                continue
            objective = OBJECTIVES.get(kind)
            if not objective:
                continue
            self._add_event(
                _event_time(event, game_time),
                "objetivo",
                objetivo=objective,
                lado=_objective_side(event, objective, players, my_team),
                dragao=event.get("dragao") if objective == "dragao" else None,
            )

    def _add_event(self, game_time: int, kind: str, **details) -> None:
        event = {"t": game_time, "tipo": kind}
        event.update({key: value for key, value in details.items() if value is not None})
        self._match["eventos"].append(event)

    def _add_sample(self, game_time: int) -> None:
        state = self._previous
        self._match["amostras"].append({
            "t": game_time,
            "nivel": state["nivel"],
            "kills": state["kills"],
            "deaths": state["deaths"],
            "assists": state["assists"],
            "cs": state["cs"],
            "ouro": state["gold_atual"],
            "morto": state["morto_agora"],
        })
        self._last_sample_time = game_time

    def _numbers(self, match: dict) -> dict:
        last = self._previous or _snapshot({})
        kills, deaths, assists = last["kills"], last["deaths"], last["assists"]
        minutes = match["fim_seg"] / 60
        return {
            "kills": kills,
            "deaths": deaths,
            "assists": assists,
            "kda": round((kills + assists) / max(deaths, 1), 2),
            "abates_do_time": self._team_kills,
            "participacao": min(1.0, round((kills + assists) / self._team_kills, 2)) if self._team_kills else None,
            "cs": last["cs"],
            "cs_por_min": round(last["cs"] / minutes, 1) if minutes >= 1 else None,
            "cs_aos_10": self._cs_at_10,
            "nivel": last["nivel"],
            "visao": last["visao"],
            "itens": list(last["itens"]),
            "ouro_parado_seg": round(self._gold_idle_seconds),
        }
