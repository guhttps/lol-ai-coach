"""
Sabe quais itens do LoL são "finalizados" (lendários/míticos/botas
completas), usando o Data Dragon público da Riot — indexado pelo ID
numérico do item, que é sempre o mesmo não importa o idioma do cliente
do jogo (diferente do nome, que muda: "Faerie Charm" em inglês é
"Amuleto da Fada" em português, mesmo item, mesmo ID).
"""

import requests

_VERSIONS_URL = "https://ddragon.leagueoflegends.com/api/versions.json"
_ITEMS_URL = "https://ddragon.leagueoflegends.com/cdn/{version}/data/en_US/item.json"

_finished_item_ids = None  # cache em memória: carrega uma vez só por execução

# custo mínimo pra considerar um item "relevante" de citar. Isso cobre
# lendários/míticos (2200-3400g) e botas completas (~1100g), e exclui
# componentes básicos (a maioria custa 250-1100g, mas SEM "into" e mais
# barato que isso).
_GOLD_MINIMO = 1000


def _carregar_itens_finalizados():
    global _finished_item_ids
    if _finished_item_ids is not None:
        return _finished_item_ids

    try:
        versoes = requests.get(_VERSIONS_URL, timeout=5).json()
        versao_atual = versoes[0]
        itens = requests.get(_ITEMS_URL.format(version=versao_atual), timeout=5).json()["data"]

        finalizados = set()
        for item_id, info in itens.items():
            gold = info.get("gold", {}) or {}
            if not gold.get("purchasable", False):
                continue
            if info.get("consumable"):
                continue
            tags = info.get("tags", []) or []
            if "Trinket" in tags:
                continue

            tem_upgrade = bool(info.get("into"))  # ainda constrói em algo maior?
            custo_total = gold.get("total", 0)

            # "finalizado" = não constrói em mais nada E custa o suficiente
            # pra não ser um componente básico
            if not tem_upgrade and custo_total >= _GOLD_MINIMO:
                finalizados.add(int(item_id))

        _finished_item_ids = finalizados
    except Exception:
        # sem internet ou Data Dragon fora do ar: fica com um conjunto vazio.
        # quem chamar is_finished_item deve tratar None como "não sei dizer"
        _finished_item_ids = set()

    return _finished_item_ids


def is_finished_item(item_id):
    """True/False se soubermos, ou None se não foi possível carregar os
    dados do Data Dragon (aí quem chamou decide o que fazer, ex: usar um
    fallback por nome).
    """
    if item_id is None:
        return None
    ids = _carregar_itens_finalizados()
    if not ids:
        return None
    return int(item_id) in ids
