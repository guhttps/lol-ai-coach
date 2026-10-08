"""Configuração simples e personalização da jogadora."""

import json
import os
import sys
from copy import deepcopy
from pathlib import Path


APP_DIR = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent

DEFAULT_PROFILE = {
    "nome": "Minha jogadora",
    "lane": "",
    "campeoes_favoritos": [],
    "nivel_experiencia": "iniciante",
    "objetivo": "melhorar sem deixar o jogo estressante",
    "tom_preferido": "carinhoso e engraçado",
}


def load_profile(path=None):
    path = APP_DIR / "player_profile.json" if path is None else path
    if not os.path.exists(path):
        return deepcopy(DEFAULT_PROFILE)
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
        if not isinstance(data, dict):
            return deepcopy(DEFAULT_PROFILE)
        profile = deepcopy(DEFAULT_PROFILE)
        profile.update(data)
        return profile
    except (OSError, json.JSONDecodeError):
        return deepcopy(DEFAULT_PROFILE)
