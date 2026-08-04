v8.7 — Multi-Rate Task Scheduler
What Changed

As the robot software grew, different subsystems required different update rates. Sensor acquisition and motor control need to execute at high frequency, while perception and logging naturally run much slower.

To support this, I implemented a cooperative multi-rate scheduler in scheduler.py using Python's asyncio. Each task is assigned its own execution rate, and the scheduler runs every task independently using absolute-time scheduling to maintain consistent timing.

The configured update rates are:

Module	Update Rate
Sensors	100 Hz
Motor Control	100 Hz
Perception	50 Hz
Logging	1 Hz

Each task executes asynchronously without blocking the execution of the others.

The Problem

The first implementation used a simple relative delay after every task execution.

period = 1.0 / rate

while True:
    await task.run()
    await asyncio.sleep(period)

Although this appeared correct, every iteration included the task execution time in addition to the sleep period.

Task Runtime
+
Sleep Period
=
Actual Cycle Time

The result was small timing errors every cycle. While each error was only a fraction of a millisecond, they accumulated continuously during long runs.

Over several minutes the sensor and control tasks slowly drifted away from their intended execution rates, reducing timing consistency throughout the system.

Investigation

Timing measurements showed that the scheduler itself introduced cumulative drift because every delay was measured relative to the completion of the previous iteration rather than an absolute clock.

The scheduler remained stable for short runs but gradually lost synchronization during extended operation.

The Fix

I replaced the relative-delay scheduler with absolute-time scheduling.

Each task keeps track of the exact time when the next execution should begin.

period = 1.0 / rate
next_time = loop.time()

while True:
    await task.run()

    next_time += period
    delay = next_time - loop.time()

    if delay > 0:
        await asyncio.sleep(delay)

Since every iteration is scheduled against the event loop clock rather than the previous execution, small timing errors no longer accumulate.

If a task occasionally takes longer than expected, only that execution is delayed. Future executions continue following the correct schedule instead of drifting indefinitely.

Deadline Monitoring

Each task also monitors its execution time.

If a task exceeds its configured deadline, the scheduler records a deadline miss and logs a warning.

if runtime > deadline:
    stats.deadline_misses += 1

Runtime statistics collected for every task include:

Total iterations
Average execution time
Maximum execution time
Last execution time
Number of deadline misses

These statistics help identify overloaded tasks during testing.

Alternatives Considered
Alternative 1 – Relative Delay

Simple to implement but accumulates timing drift over long runs.

Alternative 2 – Thread-Based Scheduling

Provides independent execution but introduces synchronization overhead and Python GIL limitations.

Alternative 3 – Fixed Hardware Timers

Provides very accurate timing but greatly increases implementation complexity for this project.

Alternative 4 – Absolute-Time Async Scheduler (Chosen)

Uses cooperative multitasking with independent update rates while preventing cumulative timing drift and keeping the implementation lightweight.

Testing

The scheduler was tested with multiple asynchronous tasks running simultaneously.

Metric	Result
Sensor Task	100 Hz
Control Task	100 Hz
Perception Task	50 Hz
Logging Task	1 Hz
Timing Drift	Negligible
Deadline Monitoring	Working
Runtime Statistics	Recorded

The scheduler maintained stable execution rates throughout extended runs without cumulative drift.

Stats
Lines of code: 147 (scheduler.py)
Scheduler type: Cooperative asyncio scheduler
Scheduling method: Absolute-time scheduling
Sensor rate: 100 Hz
Control rate: 100 Hz
Perception rate: 50 Hz
Logging rate: 1 Hz
Deadline monitoring: Supported
Runtime statistics: Supported
Lessons Learned

Using relative delays in periodic tasks causes small timing errors to accumulate over time. Scheduling tasks against an absolute clock eliminates this drift while keeping execution rates stable. A lightweight cooperative scheduler is sufficient for the robot's software architecture and provides predictable timing without the complexity of multithreading.