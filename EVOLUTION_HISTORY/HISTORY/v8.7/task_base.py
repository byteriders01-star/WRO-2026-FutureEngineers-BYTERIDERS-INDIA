import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class TaskContext:
    iteration: int = 0
    timestamp: float = 0.0
    dt_s: float = 0.0


class RobotTask(ABC):
    def __init__(self, name: str) -> None:
        self.name = name
        self._ctx = TaskContext()

    @abstractmethod
    async def execute(self, ctx: TaskContext) -> None:
        """Execute one iteration of the task."""
        ...

    async def run(self) -> None:
        loop = asyncio.get_running_loop()

        start_time = loop.time()

        self._ctx.iteration += 1
        await self.execute(self._ctx)

        end_time = loop.time()

        self._ctx.dt_s = end_time - start_time
        self._ctx.timestamp = end_time


class SensorTask(RobotTask):
    def __init__(self) -> None:
        super().__init__("sensors")
        self.accelerations: list[float] = []
        self.gyro: list[float] = []

    async def execute(self, ctx: TaskContext) -> None:
        # Read IMU, encoders, etc.
        pass


class PerceptionTask(RobotTask):
    def __init__(self) -> None:
        super().__init__("perception")
        self.detected_pillars: list[dict[str, float]] = []

    async def execute(self, ctx: TaskContext) -> None:
        # Run vision pipeline.
        pass


class ControlTask(RobotTask):
    def __init__(self) -> None:
        super().__init__("control")
        self.steering_cmd: dict[str, float] = {}

    async def execute(self, ctx: TaskContext) -> None:
        # Compute steering and speed commands.
        pass


class LoggingTask(RobotTask):
    def __init__(self) -> None:
        super().__init__("logging")
        self.buffer: list[str] = []

    async def execute(self, ctx: TaskContext) -> None:
        # Store telemetry.
        pass