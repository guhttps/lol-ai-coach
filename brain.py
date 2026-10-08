"""Cérebro do coach e integração com Groq."""

from __future__ import annotations

import json
import os
import requests

GROQ_API_URL = "https://api.groq.com/openai/v1/chat/completions"

REGRAS_GERAIS = (
    "REGRAS OBRIGATÓRIAS:\n"
    "1. Use somente fatos presentes no estado do jogo. Se algo não estiver disponível, não invente.\n"
    "2. Nomes de itens podem vir em inglês. Prefira o nome conhecido em português do Brasil quando souber com segurança; se não souber, mantenha o nome original.\n"
    "3. Não use Markdown, listas, emojis ou títulos.\n"
    "4. Nunca use as palavras 'alerta', 'atenção' ou 'notificação'.\n"
    "5. Fale como uma pessoa de verdade: uma ou duas frases curtas, naturais e fáceis de ouvir durante uma partida.\n"
    "6. Não descreva o JSON nem diga que recebeu dados.\n"
    "7. Seja útil antes de ser engraçado. Nunca humilhe a jogadora.\n"
    "8. Em dicas automáticas, se não houver motivo forte para falar, responda exatamente SILENCIO. Quando a "
    "jogadora falar ou fizer uma pergunta, sempre responda ao que ela pediu; nunca use SILENCIO para encerrar "
    "uma pergunta direta.\n"
    "9. NUNCA repita uma recomendação (itens, build, o que comprar) que você já deu nas últimas mensagens do "
    "histórico. Se a situação não mudou o suficiente para dizer algo novo, responda SILENCIO.\n"
    "10. Nomes de habilidades (Q/W/E/R) são fáceis de confundir entre campeões. Se você não tiver certeza "
    "absoluta do nome exato da habilidade de um campeão, refira-se a ela só pela letra (ex: 'seu Q', 'o W dela'), "
    "nunca invente um nome de habilidade que possa estar errado.\n"
    "11. Só comente itens totalmente finalizados (lendários, míticos, botas completas). NUNCA comente "
    "componentes básicos/intermediários (ex: Amuleto da Fada, Cristal de Rubi, Adaga) como se fossem uma "
    "escolha de build relevante.\n"
    "12. Converse sempre em português brasileiro, como uma companheira de equipe natural. Considere o histórico "
    "para entender perguntas de acompanhamento, responda diretamente ao que foi perguntado e não recomece a "
    "conversa nem repita contexto que a jogadora já conhece. Se faltar informação para responder com segurança, "
    "diga isso brevemente ou faça uma pergunta curta em vez de inventar.\n"
    "13. Em conversa por voz, prefira frases faladas e fluidas, com palavras simples e pausas naturais. Evite "
    "respostas telegráficas, listas e introduções como 'com certeza' ou 'olhando para o estado do jogo'.\n"
)

PERSONALIDADES = {
    "1": {"nome": "Debochado / Zueira", "prompt": "Você é um coach de LoL zoeiro, carinhoso e espirituoso. Use gírias de LoL com moderação e faça piadas leves, mas sempre entregue uma ação prática."},
    "2": {"nome": "Analítico / Tryhard", "prompt": "Você é um coach técnico de alto nível. Priorize wave, recursos, power spikes, visão, objetivos e conversões de vantagem. Seja direto."},
    "3": {"nome": "Hype / Motivacional", "prompt": "Você é um coach empolgado e motivador. Comemore acertos, mantenha a calma nas derrotas e transforme cada situação em uma próxima ação clara."},
}

CANDIDATE_MODELS = [
    "openai/gpt-oss-120b",
    "openai/gpt-oss-20b",
    "qwen/qwen3-32b",
]
_working_model = None


def _call_groq(model, messages, headers):
    payload = {"model": model, "max_tokens": 180, "temperature": 0.45, "messages": messages}
    if model.startswith("openai/gpt-oss"):
        payload["reasoning_effort"] = "low"
    return requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=20)


def ask_coach(user_text, game_summary, conversation_history, personality_id="1", trigger=None, profile=None):
    global _working_model
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY não encontrada no arquivo .env.")

    perfil = PERSONALIDADES.get(str(personality_id), PERSONALIDADES["1"])
    context = json.dumps(game_summary, ensure_ascii=False, separators=(",", ":")) if game_summary else "SEM_PARTIDA"
    trigger_text = trigger or "A jogadora chamou o coach por voz. Responda à pergunta dela."
    profile_text = json.dumps(profile or {}, ensure_ascii=False, separators=(",", ":"))

    conversation_mode = (
        "A jogadora iniciou uma conversa por voz. Responda à fala dela, mesmo que não haja evento importante."
        if not trigger
        else "Dica automática: só fale se o evento justificar uma orientação útil; caso contrário, responda SILENCIO."
    )
    system = (
        f"{perfil['prompt']}\n\n{REGRAS_GERAIS}\n"
        "Perfil da jogadora (preferências, não fatos da partida): " + profile_text + "\n"
        "Modo atual: " + conversation_mode + "\n"
        "Sua missão agora: " + trigger_text
    )
    user_content = f"ESTADO ATUAL:\n{context}\n\nFALA DA JOGADORA:\n{user_text or '(nenhuma)'}"
    messages = [{"role": "system", "content": system}] + conversation_history[-10:] + [{"role": "user", "content": user_content}]
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}

    models = list(dict.fromkeys(([_working_model] if _working_model else []) + CANDIDATE_MODELS))
    for model in models:
        try:
            response = _call_groq(model, messages, headers)
        except requests.RequestException as exc:
            raise RuntimeError("Não foi possível conectar à API da Groq. Verifique a internet e tente novamente.") from exc
        if response.status_code == 429:
            raise RuntimeError("O limite da API do Groq foi atingido. Tente novamente mais tarde.")
        if response.status_code in {401, 403}:
            raise RuntimeError("A Groq recusou a chave de API. Confira GROQ_API_KEY no arquivo .env.")
        if response.ok:
            try:
                text = response.json()["choices"][0]["message"]["content"].strip()
            except (KeyError, IndexError, TypeError, AttributeError, ValueError) as exc:
                raise RuntimeError("A API da Groq retornou uma resposta em formato inesperado.") from exc
            _working_model = model
            if text.upper() == "SILENCIO":
                return ""
            return text
        if response.status_code == 404:
            _working_model = None
            continue
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise RuntimeError(f"A API da Groq retornou erro HTTP {response.status_code}.") from exc
    raise RuntimeError("Nenhum modelo configurado do Groq está disponível.")
