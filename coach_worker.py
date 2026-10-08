"""Executa chamadas ao coach sem bloquear o monitoramento da partida."""

from __future__ import annotations

from collections import deque
from concurrent.futures import CancelledError, Future, ThreadPoolExecutor
from dataclasses import dataclass

from brain import ask_coach


@dataclass(frozen=True)
class CoachJob:
    kind: str
    user_text: str
    game_summary: dict | None
    trigger: str | None = None
    event_kind: str | None = None
    priority: bool = False


@dataclass(frozen=True)
class CoachResult:
    job: CoachJob
    reply: str | None = None
    error: Exception | None = None


class CoachWorker:
    def __init__(self):
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="coach-ai")
        self._pending: deque[CoachJob] = deque()
        self._current_job: CoachJob | None = None
        self._future: Future[str] | None = None
        self._generation = 0
        self._current_generation = 0

    def submit(self, job: CoachJob) -> None:
        self._pending.append(job)
        self._pending = deque(
            sorted(self._pending, key=lambda queued_job: queued_job.kind != "chat")
        )

    def reset(self) -> None:
        self._generation += 1
        self._pending.clear()
        if self._future is not None and self._future.cancel():
            self._future = None
            self._current_job = None

    def poll(
        self,
        conversation_history: list[dict],
        personality_id: str,
        profile: dict,
    ) -> CoachResult | None:
        if self._future is not None:
            if not self._future.done():
                return None

            job = self._current_job
            future = self._future
            generation = self._current_generation
            self._future = None
            self._current_job = None
            if job is None:
                raise RuntimeError("CoachWorker concluiu uma chamada sem solicitação ativa.")
            if generation != self._generation:
                return None
            try:
                return CoachResult(job=job, reply=future.result())
            except CancelledError:
                return None
            except Exception as exc:
                return CoachResult(job=job, error=exc)

        if self._pending:
            job = self._pending.popleft()
            history_snapshot = [message.copy() for message in conversation_history]
            self._current_job = job
            self._current_generation = self._generation
            self._future = self._executor.submit(
                ask_coach,
                job.user_text,
                job.game_summary,
                history_snapshot,
                personality_id,
                trigger=job.trigger,
                profile=profile,
            )
        return None

    def shutdown(self) -> None:
        self._executor.shutdown(wait=False, cancel_futures=True)
