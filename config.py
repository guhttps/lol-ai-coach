"""Configuração simples e personalização da jogadora."""

import json
import os
import sys
from copy import deepcopy
from pathlib import Path

APP_VERSION = "3.2.0"

APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent

DEFAULT_PROFILE = {
    "nome": "Minha jogadora",
    "lane": "",
    "campeoes_favoritos": [],
    "nivel_experiencia": "iniciante",
    "objetivo": "melhorar sem deixar o jogo estressante",
    "tom_preferido": "carinhoso e engraçado",
}


def _coerce_bool(value, default=True):
    if value is None:
        return default
    return str(value).strip().lower() not in {"0", "false", "no", "off", ""}


def get_runtime_settings():
    try:
        check_interval = float(os.getenv("CHECK_INTERVAL_SECONDS", "3.0"))
    except ValueError:
        check_interval = 3.0

    try:
        max_history = int(os.getenv("MAX_HISTORY_MESSAGES", "12"))
    except ValueError:
        max_history = 12

    key = os.getenv("PUSH_TO_TALK_KEY", "space").strip() or "space"
    personality = os.getenv("COACH_PERSONALITY", "1").strip() or "1"
    overlay_enabled = _coerce_bool(os.getenv("COACH_OVERLAY"), True)

    return {
        "push_to_talk_key": key,
        "check_interval_seconds": max(check_interval, 0.5),
        "max_history_messages": max(max_history, 1),
        "default_personality": personality,
        "overlay_enabled": overlay_enabled,
    }


def load_profile(path=None):
    path = APP_DIR / "player_profile.json" if path is None else path
    if not os.path.exists(path):
        return deepcopy(DEFAULT_PROFILE)
    try:
        with open(path, encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            return deepcopy(DEFAULT_PROFILE)
        profile = deepcopy(DEFAULT_PROFILE)
        profile.update(data)
        return profile
    except (OSError, json.JSONDecodeError):
        return deepcopy(DEFAULT_PROFILE)
