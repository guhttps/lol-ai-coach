"""Configuração simples e personalização da jogadora."""

import json
import os

DEFAULT_PROFILE = {
    "nome": "Minha jogadora",
    "lane": "",
    "campeoes_favoritos": [],
    "nivel_experiencia": "iniciante",
    "objetivo": "melhorar sem deixar o jogo estressante",
    "tom_preferido": "carinhoso e engraçado",
}


def load_profile(path="player_profile.json"):
    if not os.path.exists(path):
        return DEFAULT_PROFILE.copy()
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
        profile = DEFAULT_PROFILE.copy()
        profile.update(data)
        return profile
    except (OSError, json.JSONDecodeError):
        return DEFAULT_PROFILE.copy()
