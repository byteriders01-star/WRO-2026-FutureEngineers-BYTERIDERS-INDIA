import asyncio
import logging
from dataclasses import dataclass
from typing import Awaitable, Callable

logger = logging.getLogger("scheduler")


@dataclass
class TaskSpec:
    name: str
    coro_func: Callable[[], Awaitable[None]]
    rate_hz: float
    priority: int = 0
    deadline_slack_pct: float = 20.0


@dataclass
class TaskStats:
    name: str
    iterations: int = 0
    total_runtime_s: float = 0.0
    max_runtime_s: float = 0.0
    last_runtime_s: float = 0.0
    deadline_misses: int = 0


class MultiRateScheduler:
    def __init__(self) -> None:
        self._tasks: list[TaskSpec] = []
        self._stats: dict[str, TaskStats] = {}
        self._running = False

    def add_task(self, spec: TaskSpec) -> None:
        if spec.rate_hz <= 0:
            raise ValueError("Task rate must be greater than zero.")

        self._tasks.append(spec)
        self._stats[spec.name] = TaskStats(name=spec.name)

    async def run(self) -> None:
        self._running = True
        loop = asyncio.get_running_loop()

        tasks = sorted(
            self._tasks,
            key=lambda task: task.priority,
            reverse=True,
        )

        runners = [
            asyncio.create_task(self._run_task(task, loop))
            for task in tasks
        ]

        await asyncio.gather(*runners)

    async def stop(self) -> None:
        self._running = False

    async def _run_task(
        self,
        spec: TaskSpec,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        period = 1.0 / spec.rate_hz
        next_time = loop.time()
        deadline = period * (1.0 - spec.deadline_slack_pct / 100.0)

        stats = self._stats[spec.name]

        while self._running:
            start = loop.time()

            try:
                await spec.coro_func()
            except Exception:
                logger.exception("Task %s raised an exception", spec.name)

            runtime = loop.time() - start

            stats.iterations += 1
            stats.total_runtime_s += runtime
            stats.last_runtime_s = runtime
            stats.max_runtime_s = max(stats.max_runtime_s, runtime)

            if runtime > deadline:
                stats.deadline_misses += 1
                logger.warning(
                    "Task %s missed deadline %.2f ms > %.2f ms",
                    spec.name,
                    runtime * 1000,
                    deadline * 1000,
                )

            next_time += period
            sleep_time = next_time - loop.time()

            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

    def get_stats(self) -> dict[str, TaskStats]:
        return dict(self._stats)

    def print_summary(self) -> None:
        for stats in self._stats.values():
            avg_runtime = (
                stats.total_runtime_s / stats.iterations
                if stats.iterations
                else 0.0
            )

            logger.info(
                "%s: %d iterations, avg %.2f ms, max %.2f ms, missed %d",
                stats.name,
                stats.iterations,
                avg_runtime * 1000,
                stats.max_runtime_s * 1000,
                stats.deadline_misses,
            )