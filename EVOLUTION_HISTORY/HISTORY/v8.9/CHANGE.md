v8.9 — Rate-Limited Error Logger
What Changed

The previous logging system generated thousands of repetitive error messages, making it difficult to identify important failures during runtime.

For example, a single sensor communication failure could generate hundreds of identical messages every second:

[WARN] sensor_left: read timeout
[WARN] sensor_left: read timeout
[WARN] sensor_left: read timeout
...

This made debugging difficult and could hide important system information.

To solve this problem, I implemented error_logger.py, which introduces controlled logging and fault management.

Key Features Added
Rate limiting: Limits repeated messages from the same source.
WARNING and INFO messages: maximum 1 message every 2 seconds per source.
ERROR messages: maximum 1 message every 5 seconds per source.
Severity levels:
DEBUG
INFO
WARNING
ERROR
CRITICAL
Critical message bypass:
CRITICAL messages are always displayed immediately and are never suppressed.
Automatic source disabling:
A faulty source generating 50 consecutive failures is temporarily disabled to prevent continuous log flooding.
The source automatically becomes active again after a successful recovery.
Problem Encountered

While implementing the rate limiter, a new issue was discovered during competition simulation.

A health monitoring failure produced an emergency stop message:

[HEALTH_MONITOR] CRITICAL: Task 'control' heartbeat overdue

However, because the original design treated all messages equally, repeated emergency messages were also rate-limited.

Only the first message was displayed, while following messages were suppressed:

[ERROR_LOGGER] INFO: Suppressed 47 messages from 'health_monitor' in last 2.0s

This created a risk because the operator could miss the seriousness of the situation.

Solution Implemented

The logger was redesigned with severity-based filtering.

Critical failures now bypass all rate limiting:

def log(self, source, message, severity=Severity.ERROR):
    if severity == Severity.CRITICAL:
        self._write(source, message, severity)
        return

    # Apply rate limiting for lower severity messages

This ensures that emergency conditions such as:

Emergency stop activation
Motor failure
Complete sensor failure
Safety system faults

are always visible to the operator.

The auto-disable mechanism was also improved to support recovery. A disabled source is automatically re-enabled when it successfully returns valid data.

Alternatives Considered
1. Circular Buffer

A ring buffer could store recent messages and remove duplicates automatically.

Advantages:

Simple duplicate management.
Maintains recent history.

Disadvantages:

Requires continuous memory allocation.
Unnecessary memory usage for long competition runs.
2. Exponential Backoff

Increase the suppression interval for repeated failures:

2s → 4s → 8s → 16s

Advantages:

Handles temporary and persistent failures naturally.

Disadvantages:

Difficult to guarantee operator awareness of ongoing failures.
3. Message Deduplication Hash

Store hashes of recent messages and ignore duplicates.

Advantages:

Simple implementation.

Disadvantages:

Does not handle intermittent failures effectively.
Similar messages with changing parameters may bypass detection.
4. External Logging Service

Send logs to a remote monitoring system.

Advantages:

Advanced analytics and storage.

Disadvantages:

Requires network connectivity.
Not reliable for competition environments where the robot operates offline.
Testing

The logger was tested under different failure scenarios:

Test	Result
CRITICAL messages	Always displayed, no suppression
WARNING messages	Limited to 1 message per 2 seconds per source
ERROR messages	Limited to 1 message per 5 seconds per source
Auto-disable	Source disabled after 50 consecutive failures
Recovery	Source automatically re-enabled after successful response
Memory usage	~1KB per source (10 sources ≈ 10KB total)
Performance overhead	<0.01ms per log call
Lessons Learned

Rate limiting is useful for reducing log noise, but incorrect implementation can hide important system failures.

The main lesson was that not all errors have equal importance. Safety-critical events such as emergency stops or motor failures must always reach the operator immediately.

Another important improvement was adding recovery handling. A disabled component should not remain silent forever — the system must detect when it starts working again.

For v9.0, the plan is to implement a burst mode, where the logger temporarily increases output frequency when multiple independent systems fail simultaneously. This will help identify large-scale issues such as power failures, communication problems, or controller faults.