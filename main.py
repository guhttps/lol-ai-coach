"""LoL AI Coach v3.1 — voz, análise proativa, memória de sessão e overlay."""

from __future__ import annotations

import logging
import os
import sys
import time

import keyboard
from dotenv import load_dotenv

from brain import PERSONALIDADES
from coach_engine import ConnectionGracePeriod, GameAnalyzer
from coach_worker import CoachJob, CoachWorker
from config import load_profile
from live_client import get_game_data, summarize_game_data
from overlay import CoachOverlay
from voice import Voice, listen_and_transcribe

load_dotenv()

PUSH_TO_TALK_KEY = "space"
CHECK_INTERVAL_SECONDS = 3.0
MAX_HISTORY_MESSAGES = 12


def escolher_personalidade():
    print("\n=== Personalidade do Coach ===")
    for key, info in PERSONALIDADES.items():
        print(f"{key} - {info['nome']}")
    opcao = input("Escolha [1]: ").strip() or "1"
    return opcao if opcao in PERSONALIDADES else "1"


def _session_token(summary):
    if not summary or not summary.get("eu"):
        return None
    return f"{summary.get('mapa')}:{summary['eu'].get('nome')}:{summary['eu'].get('campeao')}"


def main():
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    print("=== LoL AI Coach v3.1 ===")
    personality_id = escolher_personalidade()
    profile = load_profile()
    overlay = CoachOverlay(enabled=os.getenv("COACH_OVERLAY", "true").lower() not in {"0", "false", "no"})
    voice = Voice()
    analyzer = GameAnalyzer()
    coach_worker = CoachWorker()
    connection_grace = ConnectionGracePeriod()
    history = []
    last_check = 0.0
    last_game_token = None
    last_in_game = False

    print(f"🎙️ Segure [{PUSH_TO_TALK_KEY.upper()}] para falar.")
    print("🧠 O coach agora analisa situações automaticamente e evita falar sem motivo.")
    print("🪟 O overlay pode ser fechado sem encerrar o coach.\n")

    while True:
        try:
            now = time.time()

            result = coach_worker.poll(history, personality_id, profile)
            if result:
                job = result.job
                if result.error:
                    if job.kind == "chat":
                        print(f"⚠️ IA: {result.error}")
                    else:
                        print(f"⚠️ IA automática: {result.error}")
                else:
                    reply = result.reply or ""
                    if job.kind == "chat":
                        history.extend([
                            {"role": "user", "content": job.user_text},
                            {"role": "assistant", "content": reply},
                        ])
                    else:
                        history.extend([
                            {"role": "user", "content": f"[evento automático: {job.event_kind}]"},
                            {"role": "assistant", "content": reply},
                        ])
                    history[:] = history[-MAX_HISTORY_MESSAGES:]
                    if reply:
                        overlay.show_tip(reply)
                        voice.speak(reply, priority=job.priority)

            if keyboard.is_pressed(PUSH_TO_TALK_KEY):
                text = listen_and_transcribe(PUSH_TO_TALK_KEY)
                if text:
                    print(f"👤 Ela: {text}")
                    summary = summarize_game_data(get_game_data())
                    coach_worker.submit(CoachJob(
                        kind="chat",
                        user_text=text,
                        game_summary=summary,
                        priority=True,
                    ))
                time.sleep(0.4)

            if now - last_check >= CHECK_INTERVAL_SECONDS:
                last_check = now
                raw = get_game_data()
                summary = summarize_game_data(raw)

                if not summary:
                    if last_in_game:
                        if connection_grace.update(False):
                            print("🏁 Partida encerrada ou cliente indisponível.")
                            last_in_game = False
                            last_game_token = None
                            analyzer.reset()
                            coach_worker.reset()
                            overlay.set_status("○ Fora da partida")
                        else:
                            overlay.set_status("● Conexão interrompida · reconectando")
                    else:
                        connection_grace.update(False)
                        overlay.set_status("○ Fora da partida")
                elif not summary.get("eu"):
                    connection_grace.update(True)
                    # A Live Client API can briefly return gameData/events without
                    # a resolved active player (especially while loading/reconnecting).
                    # Do not let the overlay/coach crash during that window.
                    last_in_game = True
                    overlay.set_status("● Partida detectada · aguardando jogador")
                    time.sleep(0.05)
                    continue
                else:
                    connection_grace.update(True)
                    token = _session_token(summary)
                    if token != last_game_token:
                        analyzer.reset()
                        coach_worker.reset()
                        history.clear()
                        last_game_token = token
                        print(f"🎮 Partida detectada: {summary['eu']['campeao']}")
                    last_in_game = True
                    overlay.set_status(f"● {summary['eu']['campeao']} · {summary['tempo_de_jogo_min']:.1f} min")
                    trigger = analyzer.analyze(summary)
                    if trigger:
                        event = trigger[0]
                        print(f"💡 {event.kind}")
                        coach_worker.submit(CoachJob(
                            kind="automatic",
                            user_text="",
                            game_summary=summary,
                            trigger=event.prompt,
                            event_kind=event.kind,
                            priority=event.priority >= 90,
                        ))

            time.sleep(0.05)
        except KeyboardInterrupt:
            print("\nEncerrando o LoL AI Coach. Boa partida!")
            coach_worker.shutdown()
            sys.exit(0)


if __name__ == "__main__":
    main()
