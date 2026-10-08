"""Leitura e normalização da Live Client Data API do League of Legends."""

from __future__ import annotations

import logging

import requests
import urllib3

from item_data import is_finished_item

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logger = logging.getLogger(__name__)
LIVE_CLIENT_URL = "https://127.0.0.1:2999/liveclientdata/allgamedata"
_last_api_issue = None

IGNORED_WORDS = [
    "ward", "sentinel", "totem", "lente", "potion", "poção", "poca",
    "elixir", "biscuit", "biscoito", "alteration", "alteração", "trinket",
    "control ward", "poro",
]

STARTING_COMPONENTS = [
    "doran", "health potion", "refillable", "amplifying tome", "ruby crystal",
    "long sword", "cloth armor", "null-magic mantle", "dagger", "boots",
    "faerie charm", "rejuvenation bead", "tear of the goddess",
]


def _name(player: dict) -> str | None:
    return player.get("riotIdGameName") or player.get("summonerName")


def eh_item_relevante(item: dict) -> bool:
    nome = item.get("displayName", "").lower()
    if not nome or item.get("consumable", False):
        return False

    # fonte principal: ID do item (funciona em qualquer idioma do cliente)
    finalizado = is_finished_item(item.get("itemID"))
    if finalizado is not None:
        return finalizado

    # reserva: sem internet pro Data Dragon, cai pro nome (só confiável
    # se o cliente do LoL estiver em inglês)
    if any(word in nome for word in IGNORED_WORDS):
        return False
    if any(component in nome for component in STARTING_COMPONENTS):
        return False
    return True


def get_game_data() -> dict | None:
    global _last_api_issue
    try:
        response = requests.get(LIVE_CLIENT_URL, verify=False, timeout=2)
        response.raise_for_status()
        data = response.json()
    except (requests.ConnectionError, requests.Timeout):
        if _last_api_issue != "unavailable":
            logger.info("Live Client API indisponível; aguardando conexão com a partida.")
            _last_api_issue = "unavailable"
        return None
    except requests.HTTPError as exc:
        issue = f"http:{exc.response.status_code if exc.response is not None else 'unknown'}"
        if _last_api_issue != issue:
            logger.warning("A Live Client API respondeu com erro HTTP (%s).", issue.partition(":")[2])
            _last_api_issue = issue
        return None
    except requests.exceptions.JSONDecodeError:
        if _last_api_issue != "invalid_json":
            logger.warning("A Live Client API retornou uma resposta JSON inválida.")
            _last_api_issue = "invalid_json"
        return None
    except requests.RequestException as exc:
        issue = type(exc).__name__
        if _last_api_issue != issue:
            logger.warning("Falha ao consultar a Live Client API (%s).", issue)
            _last_api_issue = issue
        return None
    if _last_api_issue is not None:
        logger.info("Conexão com a Live Client API restabelecida.")
        _last_api_issue = None
    return data


def _player_entry(player: dict) -> dict:
    scores = player.get("scores", {}) or {}
    stats = player.get("championStats", {}) or {}
    items = [
        item.get("displayName")
        for item in player.get("items", []) or []
        if item.get("displayName") and eh_item_relevante(item)
    ]
    return {
        "nome": _name(player),
        "campeao": player.get("championName"),
        "time": player.get("team"),
        "nivel": player.get("level", 0),
        "kda": f"{scores.get('kills', 0)}/{scores.get('deaths', 0)}/{scores.get('assists', 0)}",
        "kills": scores.get("kills", 0),
        "deaths": scores.get("deaths", 0),
        "assists": scores.get("assists", 0),
        "cs": scores.get("creepScore", 0),
        "morto_agora": bool(player.get("isDead", False)),
        "itens": items,
        "vida": round(stats.get("currentHealth", 0)),
        "vida_maxima": round(stats.get("maxHealth", 0)),
    }


def summarize_game_data(data: dict | None) -> dict | None:
    if not data:
        return None

    all_players = data.get("allPlayers", []) or []
    active_player = data.get("activePlayer") or {}
    game_data = data.get("gameData") or {}
    events = (data.get("events") or {}).get("Events", []) or []

    active_name = _name(active_player)
    me_raw = next((p for p in all_players if _name(p) == active_name), None)

    me = _player_entry(me_raw) if me_raw else None
    # During loading/reconnect, do not mistake the first listed player for
    # the local player when the active player has not been identified yet.
    if me is not None:
        me["gold_atual"] = round(float(active_player.get("currentGold", 0) or 0))
    my_team = me.get("time") if me else None

    game_time = float(game_data.get("gameTime", 0) or 0)
    summary = {
        "tempo_de_jogo_seg": round(game_time),
        "tempo_de_jogo_min": round(game_time / 60, 1),
        "fase": _game_phase(game_time),
        "eu": me,
        "aliados": [],
        "inimigos": [],
        "eventos_recentes": [],
        "mapa": game_data.get("mapName"),
        "modo": game_data.get("gameMode"),
    }

    for player in all_players:
        entry = _player_entry(player)
        if me and entry["nome"] == me["nome"]:
            continue
        if my_team:
            if entry["time"] == my_team:
                summary["aliados"].append(entry)
            else:
                summary["inimigos"].append(entry)

    # Preserva os últimos eventos com os campos úteis para heurísticas.
    for event in events[-12:]:
        clean = {
            "id": event.get("EventID"),
            "tipo": event.get("EventName"),
            "timestamp": event.get("EventTime"),
            "assassino": event.get("KillerName"),
            "vitima": event.get("VictimName"),
            "torre": event.get("TurretKilled"),
            "dragao": event.get("DragonType"),
            "time": event.get("Team"),
        }
        summary["eventos_recentes"].append({k: v for k, v in clean.items() if v is not None})

    return summary


def _game_phase(seconds: float) -> str:
    if seconds < 5 * 60:
        return "early"
    if seconds < 14 * 60:
        return "lane"
    if seconds < 25 * 60:
        return "mid"
    return "late"
