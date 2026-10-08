"""STT e TTS, com fila para a voz não travar o monitoramento da partida."""

from __future__ import annotations

import asyncio
import io
import os
import wave
import queue
import re
import threading
import tempfile
import requests
import time

import edge_tts
import keyboard
import numpy as np
import sounddevice as sd
import speech_recognition as sr
from playsound3 import playsound

SAMPLE_RATE = 16000
SAMPLE_WIDTH = 2
PRIMARY_VOICE = "pt-BR-ThalitaNeural"
FALLBACK_VOICE = "pt-BR-FranciscaNeural"
VOICE_RATE = "-8%"

DICIONARIO_LOL = {
    r"\bgamba\b": "gank", r"\bgangue\b": "gank", r"\bganca\b": "gank",
    r"\bgancar\b": "gankar", r"\bguarda\b": "ward", r"\buard\b": "ward",
    r"\bfama\b": "farm", r"\bfarma\b": "farmar", r"\bveia\b": "wave",
    r"\bueive\b": "wave", r"\befe 15\b": "ff15", r"\befe ef\b": "ff",
    r"\bulta\b": "ultar", r"\bflashar\b": "flashear", r"\bflecha\b": "flash",
    r"\bdreque\b": "drake", r"\bbaro\b": "barão", r"\bse s\b": "cs", r"\bca es\b": "cs",
}


def corrigir_termos_lol(texto):
    texto = (texto or "").lower()
    for pattern, replacement in DICIONARIO_LOL.items():
        texto = re.sub(pattern, replacement, texto, flags=re.IGNORECASE)
    return texto


def _record_while_held(key):
    frames = []
    def callback(indata, frame_count, time_info, status):
        frames.append(indata.copy())
    print("🎙️ Ouvindo... solte a tecla quando terminar.")
    with sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype="int16", callback=callback):
        while keyboard.is_pressed(key):
            time.sleep(0.01)
    return np.concatenate(frames, axis=0).tobytes() if frames else None


def _wav_bytes(raw_audio):
    buffer = io.BytesIO()
    with wave.open(buffer, "wb") as wav:
        wav.setnchannels(1)
        wav.setsampwidth(SAMPLE_WIDTH)
        wav.setframerate(SAMPLE_RATE)
        wav.writeframes(raw_audio)
    return buffer.getvalue()


def _transcribe_groq(raw_audio):
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        return None
    try:
        response = requests.post(
            "https://api.groq.com/openai/v1/audio/transcriptions",
            headers={"Authorization": f"Bearer {api_key}"},
            files={"file": ("voice.wav", _wav_bytes(raw_audio), "audio/wav")},
            data={
                "model": "whisper-large-v3-turbo",
                "language": "pt",
                "response_format": "json",
                "temperature": "0",
                "prompt": "League of Legends em português do Brasil. Termos: gank, farm, wave, ward, flash, ult, drake, barão, CS, lane, jungle, mid, top, bot, suporte.",
            },
            timeout=12,
        )
        if response.ok:
            text = response.json().get("text", "").strip()
            return corrigir_termos_lol(text) if text else None
    except requests.RequestException:
        pass
    return None


def listen_and_transcribe(push_to_talk_key):
    raw_audio = _record_while_held(push_to_talk_key)
    if not raw_audio:
        return None

    # Whisper do Groq é a primeira opção; Google fica como fallback.
    text = _transcribe_groq(raw_audio)
    if text:
        return text

    recognizer = sr.Recognizer()
    recognizer.dynamic_energy_threshold = True
    try:
        text = recognizer.recognize_google(sr.AudioData(raw_audio, SAMPLE_RATE, SAMPLE_WIDTH), language="pt-BR")
        return corrigir_termos_lol(text)
    except (sr.UnknownValueError, sr.RequestError):
        return None


def limpar_texto_para_voz(text):
    text = re.sub(r"[:;=]-?[)D(|pP]", "", text or "")
    text = re.sub(r"[\U00010000-\U0010ffff]", "", text)
    text = re.sub(r"[\u2600-\u27bf]", "", text)
    text = re.sub(r"[*#`_]", "", text)
    return re.sub(r"\s+", " ", text).strip()


class Voice:
    def __init__(self):
        self._queue = queue.Queue(maxsize=3)
        self._worker = threading.Thread(target=self._run, daemon=True)
        self._worker.start()

    def speak(self, text, priority=False):
        text = limpar_texto_para_voz(text)
        if not text:
            return
        if priority:
            while not self._queue.empty():
                try: self._queue.get_nowait()
                except queue.Empty:
                    break
                else:
                    self._queue.task_done()
        try:
            self._queue.put_nowait(text)
        except queue.Full:
            pass

    def _run(self):
        while True:
            text = self._queue.get()
            print(f"🗣️ Coach: {text}")
            try:
                asyncio.run(self._speak(text))
            except Exception as exc:
                print(f"⚠️ Erro no TTS: {exc}")
            finally:
                self._queue.task_done()

    async def _speak(self, text):
        descriptor, path = tempfile.mkstemp(prefix="lol_coach_", suffix=".mp3")
        os.close(descriptor)
        for voice in (PRIMARY_VOICE, FALLBACK_VOICE):
            try:
                await edge_tts.Communicate(text, voice, rate=VOICE_RATE).save(path)
                playsound(path)
                break
            except Exception as exc:
                print(f"⚠️ Falha com {voice}: {exc}")
            finally:
                try:
                    if os.path.exists(path): os.remove(path)
                except OSError:
                    pass
