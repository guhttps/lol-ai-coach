"""Motor local do coach: detecta situações objetivas antes de chamar a IA."""

from __future__ import annotations

import time
from dataclasses import dataclass


@dataclass
class Trigger:
    kind: str
    priority: int
    prompt: str
    cooldown: float = 45.0


class ConnectionGracePeriod:
    """Evita encerrar a sessão por uma falha breve na API local."""

    def __init__(self, grace_seconds: float = 12.0):
        self.grace_seconds = grace_seconds
        self.unavailable_since = None

    def update(self, available: bool, now: float | None = None) -> bool:
        now = time.monotonic() if now is None else now
        if available:
            self.unavailable_since = None
            return False
        if self.unavailable_since is None:
            self.unavailable_since = now
        return now - self.unavailable_since >= self.grace_seconds


# Intervalo mínimo entre duas falas automáticas, mesmo de tipos diferentes.
# Sem isso, vários tipos de evento (level_up, respawn, item:X de cada
# inimigo...) podem disparar em sequência rápida e soar repetitivo, mesmo
# cada um sendo "novo" do ponto de vista do próprio tipo.
GLOBAL_COOLDOWN_SECONDS = 35.0

# Eventos com prioridade >= a este valor ignoram o cooldown global (ex:
# morte é informação de segurança, não deve esperar fila).
CRITICAL_PRIORITY = 95


class GameAnalyzer:
    def __init__(self):
        self.previous = None
        self.last_fired: dict[str, float] = {}
        self.pending_triggers: dict[str, Trigger] = {}
        self.seen_items: dict[str, set[str]] = {}
        self.last_event_ids: set[str] = set()
        self.game_token = None
        self.last_any_trigger = 0.0

    def reset(self):
        self.previous = None
        self.last_fired.clear()
        self.pending_triggers.clear()
        self.seen_items.clear()
        self.last_event_ids.clear()
        self.game_token = None
        self.last_any_trigger = 0.0

    def analyze(self, current: dict) -> list[Trigger]:
        if not current or not current.get("eu"):
            return []
        now = time.time()
        me = current["eu"]
        prev = self.previous

        # Primeira leitura só cria baseline. Não fala imediatamente.
        if prev is None:
            self._remember(current)
            self._remember_items(current)
            return []

        def add(kind, priority, prompt, cooldown=45):
            self.pending_triggers[kind] = Trigger(kind, priority, prompt, cooldown)

        hp = (me.get("vida_maxima") or 0)
        hp_pct = (me.get("vida", 0) / hp) if hp else 1
        if hp_pct <= 0.25 and not me.get("morto_agora"):
            add("low_health", 90, "A jogadora está com menos de 25% da vida. Diga de forma curta se é hora de recuar/basear e por quê.", 90)

        if me.get("morto_agora") and not prev.get("eu", {}).get("morto_agora"):
            add("death", 100, "A jogadora acabou de morrer. Dê uma única lição objetiva sobre a provável decisão a revisar usando apenas os dados disponíveis.", 20)

        if not me.get("morto_agora") and prev.get("eu", {}).get("morto_agora"):
            add("respawn", 55, "A jogadora voltou à vida. Diga qual deve ser a prioridade imediata com base no estado atual.", 35)

        gold = me.get("gold_atual", 0) or 0
        if gold >= 1800 and gold > (prev.get("eu", {}).get("gold_atual", 0) or 0) + 500:
            add("rich", 65, "A jogadora acumulou bastante ouro. Oriente se vale a pena resetar e comprar, sem inventar itens específicos.", 120)

        if me.get("nivel", 0) > prev.get("eu", {}).get("nivel", 0):
            add("level_up", 75, "A jogadora acabou de subir de nível. Diga para aproveitar o novo power spike de forma prática.", 30)

        prev_kills = prev.get("eu", {}).get("kills", 0)
        if me.get("kills", 0) > prev_kills:
            add("kill", 80, "A jogadora conseguiu uma eliminação. Oriente a conversão dessa vantagem em objetivo, wave, visão ou reset, conforme os dados.", 35)

        prev_cs = prev.get("eu", {}).get("cs", 0) or 0
        cs = me.get("cs", 0) or 0
        minute = current.get("tempo_de_jogo_min", 0) or 0
        if minute >= 5 and cs - prev_cs >= 8:
            add("cs_burst", 45, "A jogadora ganhou bastante CS desde a última leitura. Reforce como transformar essa renda em vantagem.", 120)

        # Novos itens dos inimigos.
        for enemy in current.get("inimigos", []):
            name = enemy.get("nome") or enemy.get("campeao")
            items = set(enemy.get("itens", []))
            old = self.seen_items.get(name, items)
            new_items = items - old
            if new_items:
                item_list = ", ".join(sorted(new_items))
                add(
                    f"item:{name}", 70,
                    f"O inimigo {enemy.get('campeao')} acabou de aparecer com estes itens novos: {item_list}. Explique a mudança de ameaça e a adaptação mais importante.",
                    90,
                )
            self.seen_items[name] = items

        # Eventos importantes novos.
        for event in current.get("eventos_recentes", []):
            event_id = str(event.get("id") or f"{event.get('tipo')}:{event.get('timestamp')}")
            if event_id in self.last_event_ids:
                continue
            self.last_event_ids.add(event_id)
            tipo = event.get("tipo", "")
            if tipo in {"DragonKill", "BaronKill", "HeraldKill", "TurretKilled", "InhibKilled"}:
                add(
                    f"event:{event_id}", 85,
                    f"Aconteceu o evento {tipo}. Use o estado atual para orientar a próxima prioridade da jogadora.",
                    30,
                )

        self._remember(current)

        # Não deixe uma dica de vida baixa/renascimento ser falada depois que
        # a situação que a motivou já mudou.
        if hp_pct > 0.25 or me.get("morto_agora"):
            self.pending_triggers.pop("low_health", None)
        if me.get("morto_agora"):
            self.pending_triggers.pop("respawn", None)

        # Mantenha os gatilhos não selecionados enquanto o cooldown global
        # bloqueia a fala; eventos de um único ciclo não devem ser perdidos.
        candidates = sorted(
            self.pending_triggers.values(),
            key=lambda trigger: trigger.priority,
            reverse=True,
        )
        for trigger in candidates:
            last_fired = self.last_fired.get(trigger.kind)
            if last_fired is not None and now - last_fired < trigger.cooldown:
                continue
            if (
                trigger.priority < CRITICAL_PRIORITY
                and now - self.last_any_trigger < GLOBAL_COOLDOWN_SECONDS
            ):
                continue

            self.pending_triggers.pop(trigger.kind, None)
            self.last_fired[trigger.kind] = now
            self.last_any_trigger = now
            return [trigger]

        return []

    def _remember(self, current):
        # Cópia rasa suficiente para os campos usados nas comparações.
        import copy
        self.previous = copy.deepcopy(current)

    def _remember_items(self, current):
        for enemy in current.get("inimigos", []):
            name = enemy.get("nome") or enemy.get("campeao")
            self.seen_items[name] = set(enemy.get("itens", []))
