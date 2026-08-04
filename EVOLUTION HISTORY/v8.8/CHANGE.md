v8.8 — Health Monitor and Heartbeat Watchdog
What Changed

As the robot software grew to include multiple asynchronous tasks running at different update rates, I needed a reliable way to detect when a task stopped running or became unresponsive. I implemented health_monitor.py, which monitors heartbeat signals from each task and reports when a task has not updated within its expected time window.

Each scheduled task periodically sends a heartbeat after completing an iteration. The health monitor runs independently at a lower update rate and compares the current time against the most recent heartbeat from every registered task. If a heartbeat becomes stale, the monitor can trigger an appropriate safety response.

The Problem

The first version of the watchdog used heartbeat timeouts that were too strict. During periods of heavier processor load, some tasks occasionally completed later than expected even though they were still running correctly.

This caused the monitor to report false task failures.

Example log:

[HEALTH] Warning: Sensor task heartbeat delayed
[HEALTH] Warning: Perception task heartbeat delayed
[HEALTH] Warning: Task recovered

The issue was not that the tasks had crashed. They were simply completing slightly later because different subsystems naturally require different execution times.

The Fix

Instead of treating every delayed heartbeat as a failure, the monitor now allows a configurable number of missed heartbeat intervals before declaring a task unhealthy.

The timeout is calculated from each task's expected update period, making the watchdog flexible for tasks running at different frequencies.

timeout = allowed_missed_heartbeats * task_period

This approach provides tolerance for normal scheduling jitter while still detecting tasks that genuinely stop updating.

Design

The heartbeat system follows a simple workflow:

Task Executes
      │
Send Heartbeat
      │
Update Timestamp
      │
────────────────────────
Health Monitor
Check Heartbeat Age
      │
Heartbeat Valid?
      │
 ┌────┴────┐
 │         │
Yes       No
 │         │
Continue  Trigger Safety Action

Each task is monitored independently, allowing failures to be identified without affecting the heartbeat tracking of other modules.

Alternatives Considered
Alternative 1 — Immediate Timeout

Declare a task failed after the first missed heartbeat.

Simple to implement, but normal scheduling delays may produce false alarms.

Alternative 2 — Hardware Watchdog

Use the Raspberry Pi hardware watchdog to reset the entire system if software stops responding.

Provides strong protection against complete system failures but restarts the robot, making it unsuitable as the primary recovery mechanism during a run.

Alternative 3 — Supervisor Process

Run a separate monitoring process that watches the main application.

Improves fault detection but increases software complexity and communication overhead.

Alternative 4 — Configurable Heartbeat Watchdog (Chosen)

Monitor heartbeat timestamps for every task and allow a configurable timeout based on each task's expected update rate. This approach integrates naturally with the existing scheduler while remaining simple and lightweight.

Testing

The heartbeat monitor was tested under normal scheduler operation and during simulated delayed task execution.

The monitor correctly distinguished between temporary scheduling delays and prolonged heartbeat loss. Normal task execution continued without unnecessary safety triggers, while stale heartbeat conditions were detected as expected.

Stats
Lines of code: ~120 (health_monitor.py)
Monitoring Method: Per-task heartbeat timestamps
Scheduler Integration: Multi-rate task scheduler
Timeout: Configurable per task
Safety Response: Triggered when heartbeat timeout is exceeded
Lessons Learned

A heartbeat watchdog should tolerate small variations in task timing while still detecting genuine failures. Making the timeout configurable for each task improves robustness across subsystems running at different update rates. Integrating the watchdog with the scheduler provides an additional layer of safety without adding significant overhead.