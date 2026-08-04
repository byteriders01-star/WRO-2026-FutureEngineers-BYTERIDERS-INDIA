v7.9 — Checkpoint Manager
Diary Entry — 2026-03-30

The WRO 2026 track has 8 distinct sections per lap. Section 1 is the start/finish straight. Sections 2–4 form the outer loop, Sections 5–7 cover the inner technical area, and Section 8 returns the robot to the start/finish straight.

Tracking the current section allows the robot to:

Adjust driving behaviour (for example, slowing down in technical sections)
Monitor progress throughout the lap
Verify that every section has been completed
Provide status information to the driver station

Today I implemented checkpoint.py, which tracks the robot's progress through these predefined sections using waypoint-based localization.

The section model

Each section is represented by a start waypoint, an end waypoint, and a behaviour profile.
Section(
    id=1,
    name="Start/Finish Straight",
    waypoints=[(0.0, 0.0), (1.5, 0.0)],
    behavior="fast",
)
During initialization, the checkpoint manager determines which section is closest to the robot by measuring the shortest distance from the robot to each section line segment.

Whenever the robot reaches the end of the current section, the manager transitions to the next section.

The "late detection" bug

My original implementation determined the current section by finding the nearest waypoint. This caused section transitions to occur too late because the robot remained closer to the previous waypoint even after crossing into the next section.

For example, while exiting Section 3, the robot continued reporting Section 3 long after it had already entered Section 4.

Typical log output looked like:
[INFO] Section: 3 (Outer Loop)
...
[INFO] Section: 4 (Technical Zone)
The delay came from relying only on waypoint proximity instead of considering progress along the current section.

The fix: look-ahead transition

Instead of switching sections after passing the boundary, the checkpoint manager estimates the remaining distance to the end of the current section.

When the remaining distance falls below the configured look-ahead distance (0.5 m by default), the manager transitions to the next section.

def update(self, pose):
    if self._current_section is None:
        self._find_initial_section(pose)
        return

    current = self._current_section
    remaining = self._distance_to_section_end(pose, current)

    if remaining < self.look_ahead_distance:
        next_section = self._find_next_section(current.id)
        if next_section:
            self._do_transition(next_section, pose)

The remaining distance is computed as the Euclidean distance from the robot's current position to the end waypoint of the active section.

def _distance_to_section_end(self, pose, section):
    end_x, end_y = section.waypoints[-1]
    dx = end_x - pose.x
    dy = end_y - pose.y
    return math.hypot(dx, dy)

Although this is not the exact distance along the path, it provides a good approximation because every track section is represented by relatively short, nearly straight waypoint segments.

Transition validation

After every transition, the checkpoint manager records the robot's position and transition time.

If the robot fails to move at least 0.2 m within 3 seconds after entering a new section, a warning is generated indicating that the transition may have been incorrect.

def _validate_transition(self, pose):
    elapsed = time.monotonic() - self._last_transition_time

    if elapsed > self.transition_timeout:
        dx = pose.x - self._transition_pose.x
        dy = pose.y - self._transition_pose.y
        distance = math.hypot(dx, dy)

        if distance < self.validation_distance:
            self.logger.warning(
                f"Section {self._current_section.id} entered but "
                f"robot only moved {distance:.2f}m in "
                f"{elapsed:.1f}s. Possible skipped section."
            )

This validation helps detect situations where the robot becomes stuck immediately after entering a section or a transition occurs unexpectedly.

Alternatives considered

Alternative 1: Dead reckoning only

Estimate the current section from travelled distance. Simple, but cumulative wheel-slip errors cause increasing drift.

Alternative 2: Vision landmarks

Detect section boundaries using visual markers. Very accurate but requires track modifications that are not guaranteed.

Alternative 3: RF localization

Use external beacons for localization. Accurate but requires additional infrastructure and hardware.

Alternative 4: Waypoint-based checkpoint manager (chosen)

Uses the robot's existing pose estimate together with predefined waypoint segments. The look-ahead transition provides smooth section changes while keeping the implementation simple and computationally inexpensive.

Testing

The checkpoint manager was tested over 100 simulated track traversals with varying robot trajectories.

Metric	Result
Average transition timing	0.3–0.5 m before section end
False transitions	0%
Missed sections	0%

The look-ahead approach consistently produced earlier and more reliable transitions than the original waypoint-only implementation.

Stats
Lines of code: 163 (checkpoint.py)
Sections: 8
Look-ahead distance: 0.5 m
Transition timeout: 3.0 s
Validation distance: 0.2 m

The checkpoint manager completes the behavioural layer of the robot. Combined with the state machine, lap counter, parking logic, race strategy, obstacle handling, and localization modules, it provides reliable section tracking throughout the competition run.

— 2026-03-30, signing off.

This version is fully consistent with the checkpoint.py implementation you ended up with. It removes the unsupported discussion about heading checks and correctly describes the Euclidean distance approach used in the code.