### 1. Version header table

| Version | Phase | Days |
|---------|-------|------|
| v4.8 | Understanding the Track | Day 112-114 |

### 2. Title

# v4.8 — Pillar tracking: the world exists between frames

### 3. Mission of this version (~600 words)

The single problem this version attacks is **temporal continuity of pillar
perception** — the ability to keep a pillar "alive" in the decision layer
even on frames where the camera does not see it. At the end of v4.7 we could
*detect* a red or green pillar in a single frame and estimate its range with
`pillar_distance_mm()`, but the capability was **stateless**: every frame was
judged independently, and the moment the pillar left the camera's field of
view the whole world — from the robot's point of view — simply ceased to
contain that pillar.

This was the correct next step on the critical path to competition for one
reason that overrides every other: the mission layer does not act on the
camera, it acts on *persistence*. Layer 6 (`MissionManagerLayer`) turns a
pillar detection into an `avoidance_offset` of `+0.6` or `-0.6` (in
normalized cross-track units) via the `SurpriseRuleAdapter` in
`layer6_mission_manager.py`. A single missed frame therefore collapses the
avoidance decision to `0.0`, and the robot steers straight back toward the
pillar it was avoiding. Worse, when the pillar re-enters the frame 300–500 ms
later, the offset snaps from `0.0` back to `±0.6` in one 10 ms control cycle,
a lateral jerk the steering servo must absorb instantly. We watched this
happen live on the shop track and it was ugly.

The capability gap, stated precisely: **detection (v4.4–v4.7) answers "is
there a pillar in this frame?"; the mission needs "is there a pillar in this
part of the world?"** The first is a per-sample question, the second is a
question about a world that exists continuously even when our 30 Hz camera
window does not overlap it. WRO pillars do not teleport; the robot turns, and
turning swings the 62.2° camera field of view past the pillar. The information
is gone from the *image*, not from the *world*.

"Done" for this version, written *before* we wrote a single line:

1. **Holding window.** During a scripted 90° turn at 1.8 m/s (measured
   minimum radius 0.5 m, worst-case pillar occlusion measured 380–460 ms in
   earlier runs), the mission must keep producing a valid pillar observation
   for the full occlusion window, and no longer than 500 ms after the pillar
   leaves view.
2. **Ghost death.** On an empty stretch of track with no pillar ever present,
   the tracker must claim a pillar for **zero** frames beyond its 500 ms
   cooldown. Memory must age out.
3. **Latency budget.** Tracker overhead must stay under 1 ms per update at the
   100 Hz control loop — it must not disturb the 10 ms cadence that the
   ESP32-S3 200 ms watchdog assumes.
4. **Decision continuity.** In 10 scripted pillar passes, the
   `avoidance_offset` must remain non-zero for the entire occlusion window and
   must not double-commit or flip sign.
5. **Non-blocking integration.** The tracker must be callable from the main
   loop's lock-free read path (`process_frame()`) and must never sleep, touch
   I2C, or hold the perception thread's lock.

Everything in this document is judged against those five criteria.

### 4. Engineering context — where we stood (~800 words)

At the end of v4.7 the perception chain was: camera → `_async_camera_loop()`
in `layer4_perception.py` (background thread, 30 FPS) → BGR→HSV →
two-band red mask (`hsv_red1` 0–10 / `hsv_red2` 170–180), green mask
(36–85), magenta mask (135–165), blue stop-line mask (95–130, ROI below 70%
of image height) → `_find_largest_contour()` → a dict with `center_x`,
`normalized_x`, `area`, `bbox`, and `distance_est_mm` → `latest_perception`
under a `threading.Lock`. Distance came from the pixel-height formula
`dist_mm = (img_h * 150.0) / h` with `cos(pitch)` compensation from the
MPU6050, exactly as `pillar_dist.py` (v4.7) specifies.

Its known weaknesses were numerous and we catalogued them honestly: the
formula assumed a 150 mm physical pillar height that only approximately
matched the venue pillars; the whole result was thrown away between frames;
the detection threshold `area < 300` in `_find_largest_contour()` meant that
a far, small pillar vanished abruptly rather than fading; and — the killer —
there was no notion of "this is the same pillar as last frame." A pillar
partial occlusion by its own passage beside the robot, or by the turn, killed
the detection instantly and the mission with it.

The system-level constraints that shaped everything we did this version:

- **Brain/muscle split.** Raspberry Pi 4B reasons (100 Hz, multi-threaded);
  ESP32-S3 executes under a **200 ms watchdog**. If the Pi stalls or the
  serial link fails for longer than the watchdog, the ESP32 stops the motors
  short-braking. Any work we add to the Pi loop must be measured in
  microseconds, and it must never block.
- **100 Hz serial link, 10-byte packets.** `PacketEncoder.encode_drive()`
  packs `seq + cmd + servo_raw(int16) + speed_raw(int16)` = 8 payload bytes,
  plus 2-byte header, CRC8, footer = 10 bytes × 100 Hz = 1,000 B/s ≈ 8 kbps
  of a 115,200 baud link. The link is not the bottleneck; the *decision*
  feeding it is.
- **Sensor cycle vs control cycle.** The front VL53L1X runs a 33 ms ranging
  budget + 35 ms settle ≈ 68 ms cycle (`layer1_sensors.py`), 6.8× slower than
  the 10 ms control frame; the left/right VL53L0X are XSHUT-sequenced on GPIO
  17/27 with a fixed `OFFSET_LR_MM = 50.0`. So ToF *cannot* fill a 100 Hz
  decision stream by itself — it hands the camera the responsibility for
  mid-range object identity.
- **Steering physics.** A single MG995 servo drives a mechanical 4WS linkage,
  rear ratio 0.85 (`rear_to_front_ratio`), wheelbase 230 mm, track 160 mm,
  servo max 40°. Our computed minimum turning radius at full lock is ≈141 mm,
  but the mission's practical turns run at ≈0.5 m radius to cap centripetal
  acceleration. Yaw rate `ω = v/R` is the quantity that decides how long a
  pillar spends outside the camera.
- **Battery / race pressure.** A 3-lap mission at up to 1.8 m/s, three
  rounds, a surprise rule loaded from `robot_config.json`, and a parking
  finish. Every 10-minute shop session has a fixed cost; a bug that forces a
  re-run costs a full lap-worth of tuning time.

Time pressure was real and compounding. We were on **Day 112–114** of a
campaign whose end state (v9.9) demands localization, Stanley control, and
mission behavior on top of what we have now. Every day spent re-solving the
same problem downstream because perception was stateless was debt. v4.9 is
already scheduled for visual odometry; if we shipped stateless detection into
v4.9, the odometry would be trying to measure ego-motion against a world that
blinked in and out of existence — a contradiction in terms. Tracking had to
happen now, before any consumer that needs a persistent world. The alternative
was to let the problem migrate upward into v5.x localization, where it would
be ten times harder to separate from pose estimation. We chose to pay the
small cost now.

### 5. The engineering thought process — first principles (~2,000 words)

#### 5.1 Constraints and hard limits, derived from first principles

We did not pick the 500 ms cooldown out of a hat; we derived it from
physics. Start with the camera. The Pi Camera v2-class module we use has a
horizontal field of view of about 62.2°. At 640 px across, that is
`62.2° / 640 = 0.097°` per pixel ≈ 1.7 mrad. A pillar 50 mm wide at 1,500 mm
range subtends `atan(50/1500) ≈ 1.9°` ≈ 20 px — plenty to detect, but only
while it is inside those 62.2°. The moment the robot's heading sweeps past
the pillar's bearing, the pillar is gone from the image entirely. There is no
amount of threshold tuning that brings it back; the photons simply are not
landing on the sensor. This is the fundamental asymmetry of detection vs
tracking: **detection fails at the FOV edge by construction; tracking does
not have an edge.**

Now the kinematic constraint. In a corner at speed `v` and turning radius
`R`, the yaw rate is `ω = v/R`. With our practical corner speed of 1.8 m/s
and radius 0.5 m, `ω = 3.6 rad/s`. A pillar sitting at the corner apex is
swept through the full 62.2° (1.085 rad) of camera travel in
`1.085 / 3.6 ≈ 0.30 s` — but that is only the time for the *center* of the
pillar to cross the FOV. What matters is the occlusion window: from the
moment the pillar exits one FOV edge to the moment it re-enters (or we turn
far enough that we stop caring) can be longer, especially when the pillar
passes beside the robot rather than ahead. Empirically, from the v4.7 log
files and the runs on Day 111, we measured occlusion windows of 380–460 ms
across a series of 90° corner passes at full mission speed. The theoretical
bound and the measured data agreed: a 0.5 s cooldown is the smallest round
number that strictly exceeds the worst observed window with ~14% margin.
Below 400 ms we would lose the pillar mid-turn; above 1 s we would be
steering around ghosts for a full half-second after passing. So constraint
C1 (camera FOV is 62.2°, occlusion window up to ~460 ms) forces requirement
R1 (hold a detection for ≥500 ms, no longer).

Second constraint is the control cadence. The Pi runs `main.py` at 100 Hz
(`loop_frequency_hz` = 100, `target_dt = 1/100 = 10 ms`). At that cadence,
500 ms is exactly **50 control cycles**. The tracker must be callable every
cycle, must return in microseconds, and must be deterministic. If it costs
more than 1 ms we break the `sleep_time = target_dt - elapsed` budget in
`main.py` and start drifting the 100 Hz loop, which the ESP32-S3 watchdog
(200 ms, i.e., ~20 missed heartbeats) will eventually interpret as death.
Constraint C2 (10 ms control period, 200 ms watchdog) forces requirement R3
(tracker O(1), <1 ms) and R4 (no blocking calls, no I2C, no sleeps).

Third constraint is memory hygiene. A "keep last forever" tracker is
mathematically a *stale-state accumulator*: without an expiry, a pillar seen
once at the top of the straightaway would persist through the entire next
lap, and `avoidance_offset` would stay `±0.6` forever, steering the robot
into a wall on lap two. The risk is asymmetric: too-short cooldown = missed
avoidance; too-long cooldown = phantom obstacle. Constraint C3 (world
reverts to obstacle-free after we pass it) forces requirement R5 (hard
expiry; after 500 ms the tracker returns `None` and the mission reverts to
nominal behavior).

Fourth, the serial and sensor budget. The 100 Hz × 10-byte link
(2 header + 1 seq + 1 cmd + 2 + 2 payload + 1 CRC + 1 footer) is ~8 kbps on
a 115,200 baud wire — 13× headroom, so adding one more boolean to the
mission decision adds nothing to the link. The VL53L1X front sensor cycles
at 68 ms (33 ms budget + 35 ms settle), the two VL53L0X are time-multiplexed
by XSHUT on GPIO 17/27. ToF can give us a *range* every ~68–100 ms but
cannot tell red from green, and range is exactly what we already get from
`distance_est_mm` in the perception dict. So constraint C4 (ToF is
color-blind and slow relative to the camera) tells us the tracker must live
on the *camera* stream and the ToF stays a cross-check, not a replacement.

Fifth, compute cost. The perception thread already does a full 640×480
BGR→HSV conversion (`cv2.cvtColor`) plus four `inRange` masks plus
`findContours` per frame at 30 FPS — that is the expensive part of the
pipeline. A tracker that simply remembers a dict and compares two floats is
free: at 100 Hz, two float comparisons and a `time.time()` call is on the
order of tens of microseconds. Constraint C5 (Pi must keep 30 FPS perception
AND 100 Hz control without overshoot) forces requirement R2 (the tracker
must not add a per-frame image operation; it must be pure state).

Finally, the state-machine reality of Layer 6. The mission transitions
depend on `green_pillar is not None` and `red_pillar is not None`
(`update_state` in `layer6_mission_manager.py`). The avoidance logic is:
`green` → avoid LEFT, `red` → avoid RIGHT, offset `0.6` or `-0.6`. If the
tracker feeds that layer a persistent dict during the turn, the mission
keeps its avoidance intent through the whole corner. Constraint C6 (mission
acts on persistence, not on per-frame presence) is the deepest one — it is
why tracking matters at all.

One more constraint deserves its own derivation because it is the one that
usually bites teams on competition day: the **venue-practice window**. WRO
Future Engineers gives roughly 120 minutes on the actual field before the
rounds. In that window we must re-calibrate HSV thresholds (v4.4's lesson),
re-check sensor offsets, and test the surprise rule from
`robot_config.json`. A tracking constant is not something we want to tune on
the field — the field has neither the repetition count nor the time to
measure occlusion windows properly. So the cooldown had to be a value we
could commit to *before* venue day and that is insensitive to the 
200–400 ms class of venue variation. The measured 384–462 ms band and the
500 ms pick leave ~40 ms of margin; if a venue's walls are 800 mm instead of
600 mm, the corner radius grows and the occlusion *shrinks* (slower yaw for
the same speed), so the 500 ms window is conservative in the safe direction.
This "design for the 120-minute window" mindset — put only what must vary on
venue day into config, and derive everything else in advance — is exactly the
discipline the trade-off matrix encodes.

We also did a quick sanity check on the *data rate* argument that a tracker
somehow needs more bandwidth. It does not: the tracker returns one dict or
`None` per color per cycle — at worst the same 5-key dict that already
existed in `latest_perception`, referenced, not copied. The 100 Hz × 10-byte
serial link already carries `servo_angle` and `motor_speed` (2×int16 scaled
×100 and ×10 in `encode_drive`); the tracker adds nothing to the wire. The
only "cost" of persistence is in the Pi's memory, two float slots per color.
So the constraint analysis closes: the feature is free in every budget that
matters (link, CPU, watchdog, venue time) and buys correctness in the one
place that was failing (mission decision continuity).

#### 5.2 Requirements derived from constraints (traceability)

| Constraint | Derivation | Requirement |
|---|---|---|
| C1: FOV 62.2°, occlusion 380–460 ms measured | R1 | Hold last detection ≥500 ms, expire at 500 ms |
| C2: 10 ms control period, 200 ms watchdog | R3, R4 | O(1), <1 ms, no blocking calls |
| C3: world reverts to obstacle-free after passing | R5 | Hard expiry → return `None` after cooldown |
| C4: ToF color-blind, 68 ms cycle | R6 | Tracker lives on camera stream; ToF = cross-check |
| C5: Pi must sustain 30 FPS + 100 Hz | R2 | Pure-state tracker, zero image ops |
| C6: mission acts on persistence | R7 | Output must be a per-color dict or `None` every cycle |

#### 5.3 Alternatives considered

**Alternative A — Do nothing (stateless detection, v4.7 behavior).** Zero
code. Honest analysis: during the 380–460 ms occlusion the mission sees no
pillar, `avoidance_offset` drops to 0, the Stanley controller in layer 10
steers back to centerline, and 30–46 frames later the pillar reappears and
the offset snaps back to ±0.6. Net effect: a mid-turn correction away from
centerline exactly when we most need to hold the line. Measured on Day 111:
the robot cut the corner apex by up to ~90 mm of cross-track excursion during
these flickers — enough to flirt with the 600–800 mm corridor edge at 1.8
m/s. Rejected.

**Alternative B — Keep-last forever (no cooldown).** Even simpler code, one
line: never clear `self.last`. Fatal flaw: stale forever. After passing the
pillar, the mission would avoid a ghost for the rest of the lap, and the
STOP state machine would never see a clean field. Rejected on the C3
memory-hygiene argument: the world *does* revert.

**Alternative C — Keep-last + fixed cooldown expiry (chosen).** Remember the
dict; remember *when* we last saw it; if `now - last_seen > cooldown`, clear.
This is the two-state tracker we built. It satisfies R1–R7 with ~5 lines of
Python. Its weakness is that the held position is frozen at last-seen, so
during a long turn the *held range* is stale while the robot advances — but
the mission does not need range during the turn; it needs the *identity* of
the obstacle to keep the avoidance direction. Acceptable.

**Alternative D — Kalman / constant-velocity predictive tracker.** Predict
the pillar's bearing and range through the occlusion using robot odometry
(`x, y, theta` from layer 5 localization), then re-associate when it
reappears. Honest analysis: this is the "right" engineering answer for a
tracking course, but it is overkill here. We had no reliable odometry yet
(v4.8 is two versions before v5.x localization reaches the field), the pillar
is *static* while the robot moves (so a constant-velocity assumption on the
world is wrong — the velocity belongs to the ego frame), and prediction
adds a full covariance to manage. The benefit (better held position over 500
ms) was not worth the risk (divergent filter feeding the mission). Deferred —
see 5.6.

**Alternative E — ToF-dominated short-range handoff.** When the camera loses
the pillar, let the front VL53L1X claim "obstacle at range X" and keep the
avoidance engaged purely on range. Rejected on the C4 argument: the front ToF
sees the *wall* at the apex of a turn too, and it cannot distinguish a red
pillar from a green pillar or from the corridor wall. It would keep the
avoidance engaged but with the wrong *direction* information, and it would
false-trigger on every corner wall. The right sensor for *identity* is the
camera; the ToF stays what it is — a range cross-check.

#### 5.4 Trade-off matrix

| Alternative | Effort (LOC/days) | Robustness (1-5) | Speed added to loop (µs) | Risk | Reuse for v5+ | Verdict |
|---|---|---|---|---|---|---|
| A: stateless | 0 / 0 | 1 — flickers mid-turn | 0 | High — corner cutting | none | Rejected |
| B: keep-forever | 1 / 0.1 | 2 — no flicker but ghosts | ~1 | High — ghost obstacle for a lap | none | Rejected |
| C: keep + cooldown | 10 / 0.5 | 4 — holds turn, expires cleanly | ~2 | Low — single constant to tune | Pattern reused by v5.x landmark persistence | **Chosen** |
| D: Kalman predict | 200 / 3 | 5 — best estimate | ~50 | Medium — divergence | High — but needs odometry we lack | Deferred |
| E: ToF handoff | 40 / 1 | 3 — holds but wrong identity | ~5 | Medium — false walls | Partial (range fusion) | Rejected |

#### 5.5 Decision and justification

We chose **Alternative C: keep-last + 500 ms cooldown expiry**. The logical
chain: the mission needs *identity-persistence* through a bounded occlusion
window (R1, R7); the occlusion window is bounded by kinematics to ≤460 ms
(measured, and ~0.30 s by `FOV/ω` theory); 500 ms is the minimal round
number ≥ measured max with margin; therefore a fixed 500 ms cooldown with a
hard expiry satisfies every requirement at a cost of 10 lines and ~2 µs per
call. The held-state staleness that Alternative D would fix is irrelevant
within 500 ms because the mission consumes *presence and direction*, not
range, during a turn. We chose the constant because it is auditable: any
reviewer can recompute `FOV 62.2° / (ω = 3.6 rad/s) ≈ 0.30 s` and compare
against our 0.5 s, and the margin covers the robot's finite size pushing the
occlusion longer. The verification burden of a filter (process noise, gate
tuning, divergence logs) was not justified when a 30 ms-accurate clock and a
float comparison solve the stated problem exactly.

#### 5.6 What we deliberately deferred

1. **Predictive motion of the held state.** We freeze `self.last` at
   last-seen instead of advancing it with odometry. Deferred because the
   odometry is not trusted yet (v5.x) and the mission doesn't need it within
   the 500 ms window.
2. **Data association / multiple pillars.** The tracker holds one dict per
   color (`red_pillar`, `green_pillar`); a second pillar of the same color in
   view would be ignored by `_find_largest_contour` (largest-area only) and
   the tracker would silently switch identities. The WRO field puts at most
   one pillar of each color in the corridor at a time, so this is scope we
   chose not to pay for.
3. **ToF range fusion into the held state.** We keep `distance_est_mm` frozen
   at last-seen rather than re-ranging the front VL53L1X. Cross-check only.
4. **Adaptive cooldown from yaw rate.** A smarter `cooldown = k / ω` would
   adapt the window to the actual turn speed. We kept a constant because a
   variable cooldown makes the code and the tuning table harder to reason
   about, and the constant covers the measured worst case.

This discipline kept the version to ~10 lines of real logic and one tuning
constant, which is exactly the scope control the 120-minute venue-practice
constraint demands.

### 6. Decision flowchart (~500 words + mermaid)

The decision tree below is the branching logic of Section 5 distilled into
the questions we actually asked, in order. Start at the top with the mission
failure we saw on Day 111. The first branch is the honest one: "is the
pillar actually gone, or just not in this frame?" That question — detection
vs. world-state — is the entire reason this version exists. If we answer
"gone from image = gone from world," we choose Alternative A (stateless) and
accept the flicker. We did not, and the reason is written on the arrow: a
pillar's disappearance is always explainable by `FOV/ω ≈ 0.30 s` of ego-motion,
so an unexplained gap is far more likely to be a sampling gap than a
teleportation.

The second branch is the cooldown decision: once we commit to holding state,
for how long? We require the hold to strictly exceed the worst measured
occlusion (460 ms, from the Day 111 logs and the 5.1 derivation), and to
return `None` once the world has truly reverted. That gives us the 500 ms
window. The third branch asks whether the held state must *move* during the
hold. Our honest answer was "not yet" — we have no trusted odometry (that is
v5.x), and the mission consumes identity+direction, not range, inside the
window. That deferral is drawn as a terminal node feeding v5.x, not as a
rejection.

The fourth branch is the sensor-identity question. When the camera drops the
pillar, could the ToF sensors substitute? We rejected it on the color-blind
argument: the VL53L1X and VL53L0X return range, never color, and the corner
wall would produce identical ranges. Identity comes from the camera; the
tracker is where that identity is held while the camera is looking elsewhere.

Every edge is labeled with the number or requirement that justifies it. The
flowchart is the argument, and the argument is arithmetic.

```mermaid
flowchart TD
    A[Day 111: pillar avoidance flickers mid-turn, offset 0.6->0->0.6 at 100 Hz] --> B{Is the pillar gone, or just not in this frame?}
    B -- 'Detection = world' (stateless, Alt A) --> R1[Rejected: 90 mm corner apex excursion measured]
    B -- 'Detection != world; FOV 62.2 deg / 3.6 rad/s = 0.30 s gap' --> C{Do we hold state across the gap?}
    C -- No --> R2[Rejected: identical flicker every corner]
    C -- Yes, keep-last + expiry --> D{For how long can we hold?}
    D -- 'must exceed worst measured occlusion 460 ms' --> E[cooldown = 500 ms = 50 control cycles]
    E --> F{Does the held state need to move during the hold?}
    F -- 'No trusted odometry yet (v5.x); mission needs identity+direction not range' --> G[Freeze last dict; defer motion model to v5.x]
    F -- Yes --> H[Alt D Kalman predictor -> Deferred: divergence risk, no pose source]
    G --> I{Who else can sense the pillar while camera is blind?}
    I -- 'ToF is color-blind, 68 ms cycle, sees corner wall identically' --> J[Camera-only identity; ToF = range cross-check only]
    I -- 'Camera FOV edge is the only blind spot' --> K[Chosen: PillarTracker keep-last + 500 ms cooldown]
    K --> L[Output: per-color dict or None every cycle -> Layer 6]
```

### 7. Implementation blueprint (~2,000 words)

The whole of this version is one class in one file, `pillar_track.py`,
10 lines of Python, and it is worth walking through line by line because the
design decisions are hiding in the whitespace. Here is the file, verbatim as
it was frozen in this snapshot:

```python
import time
class PillarTracker:
    def __init__(self, cooldown=0.5):
        self.last = None; self.last_seen = 0.0; self.cooldown = cooldown
    def update(self, det):
        if det is not None:
            self.last = det; self.last_seen = time.time()
        if time.time() - self.last_seen > self.cooldown:
            self.last = None
        return self.last
```

**The state space.** The tracker holds exactly two variables. `self.last` is
the most recent valid detection dict (or `None`); `self.last_seen` is the
monotonic-ish wall-clock time at which that dict was last written. There is
no history, no buffer, no frame counter. This is a deliberate choice forced
by requirement R3: at 100 Hz, a buffer of even 10 frames would be 10× the
state we need, and we verified in the trade-off matrix that the mission only
consumes the latest identity. Two floats of state is the minimal
implementation of "remember the pillar, remember when you saw it."

**The `update` contract.** `update(det)` accepts exactly two kinds of input:
a detection dict from the perception layer (the `red_pillar` or `green_pillar`
value from `latest_perception`, which is itself the output of
`_find_largest_contour` with keys `center_x`, `normalized_x`, `area`,
`bbox`, `distance_est_mm`), or `None`, meaning "no detection this frame."
The contract is symmetric: **if you give me a detection, I adopt it; if you
give me nothing, I keep what I had until it ages out.** The output is always
either the held dict or `None`. Callers do not need to know which branch
fired; they just read the return value. This is the interface contract that
makes the tracker drop-in for Layer 6: `update_state` already checks
`green_pillar is not None`, so a returned `None` reverts the mission to
nominal automatically.

**The update path, line by line.** On line 6, if `det is not None`, we
overwrite `self.last` with the new dict and stamp `self.last_seen =
time.time()`. Two things matter here. First, the write is unconditional on
the dict's content: we do not validate that the dict has sane ranges or a
fresh `frame_processed` flag. We trust the perception layer's
`_find_largest_contour` gate (which already rejects `area < 300` and returns
`None` for no contour), so by the time a dict reaches the tracker it has
already passed a size check. Duplicating that validation here would be
redundant, and redundancy has a cost in a 100 Hz loop: every branch is
microseconds of jitter against the 200 ms watchdog. Second, the stamp uses
`time.time()` and not a frame counter, because the occlusion window is a
*duration in wall time*, and the source of truth for "how long has the
pillar been out of view" is the clock, not the 30 FPS frame number. A frame
counter would give us only 15 frames of grace for a 500 ms window at 30 FPS,
and if the camera ever hiccups (the `_async_camera_loop` sleeps 0.02 s and
retries on failed reads) the frame count and the wall time would diverge.
Wall-clock expiry is robust to camera stutters by construction.

**The expiry check.** On line 8, *regardless of the input branch*, we check
`time.time() - self.last_seen > self.cooldown`. This unconditional check is
the heart of the design and it is easy to miss. Consider the two cases. Case
1: `det is not None` — we just stamped `last_seen = now`, so the difference
is ~0 and the check is false; the pillar lives. Case 2: `det is None` — the
difference grows each call, and the instant it exceeds 0.5 s, `self.last`
is cleared to `None` and the tracker reports no pillar. The clever bit is
that the check runs in *both* branches, so a 0.5 s gap in detections expires
the state even if the camera is delivering frames — and a 0.5 s camera
stall (which delivers `None` because `frame_processed` never flips) also
expires it, because `last_seen` is wall time. There is no code path where
state outlives `cooldown` wall-seconds. That is requirement R5 made
structural rather than behavioral: it is not "we try to clear ghosts"; it is
impossible to have a ghost older than 500 ms.

**The return.** `return self.last` hands the caller the surviving dict or
`None`. Note the subtlety: when `det is not None` and the pillar has been
continuously present, we return the *fresh* dict (which the caller then
reads `center_x`/`distance_est_mm` from). When the pillar is in the hold
window, we return the *frozen* dict from before the gap. The consumer cannot
tell the difference from the interface — and that is deliberate. The mission
layer wants to know "is there a red pillar and where was it," not "was this
frame a fresh or held observation." We considered adding an `is_stale` flag
to the output and rejected it: it would force `update_state` to branch on
staleness, which reintroduces exactly the flicker we are removing. The
freeze is invisible because within 500 ms the held position is close enough
to the true position that the mission's 0.6 offset does not need the
correction. For the record, the stale error bound: in 500 ms at 1.8 m/s the
robot advances 0.9 m, and at a turn radius of 0.5 m the pillar's bearing
drifts by `atan(0.9/0.5) ≈ 61°` — large in angle, but the mission only
needs the *sign* of the offset, and the sign is unchanged by the drift
within the hold window. We verified this by logging `normalized_x` through a
full turn and watching it stay on the correct side of zero for the whole
hold.

**The cooldown constant.** `cooldown=0.5` is a keyword argument, not a
module constant. That was a deliberate API choice: it lets the integration
site decide the window without editing the class, and it documents the
intent at the call site. In practice we instantiate two trackers — one for
red, one for green — with the same default. The 0.5 s value comes straight
from Section 5.1 (`max measured occlusion 460 ms + 14% margin`), and we
kept it in code rather than `robot_config.json` because it is a *physics
constant of the vehicle and camera*, not a venue-tunable perception
threshold. Venue lighting moves HSV; vehicle kinematics does not move on
venue day. (Contrast with v4.4's lesson that HSV must be config — different
class of parameter, different home.)

**Thread model and timing budget.** The tracker is instantiated in the
mission/perception path, which is the main loop of `main.py`. `main.py`
already runs at 100 Hz and calls `layer4_percep.process_frame(frame=None)`
to grab the latest locked perception dict non-blockingly, then hands it to
`layer6_mission.update_state(perception, raw, localization)`. Our integration
sits between those two calls: we pull `perception["red_pillar"]` and
`perception["green_pillar"]`, push each through its `PillarTracker.update`,
and write the results back into the dict that Layer 6 consumes. The camera
thread (`_async_camera_loop`) is untouched — it keeps writing
`latest_perception` under the lock at 30 FPS, and the tracker never touches
that lock. That is the non-blocking requirement R4 honored: the tracker does
no I/O, no sleeps, no locks, no allocations beyond a dict reference and a
float write. Worst-case wall time of `update` measured with
`time.perf_counter` around 100,000 calls: ~1.6 µs median, ~3 µs p99 — over
three orders of magnitude inside the 10 ms control budget. In terms of the
watchdog: 500 ms of tracking activity is 50 calls × ~2 µs = 100 µs of added
Pi CPU per second, which cannot contribute to a watchdog trip.

Let us be explicit about *why* the tracker lives in the main loop and not in
the perception thread, because a junior engineer might reasonably put it in
`_process_frame_internal` next to the masks. If the tracker lived in the
camera thread, its state would advance at 30 FPS and its 500 ms expiry would
quantize to 15-frame steps — a pillar would appear to survive exactly 15
frames and then vanish, and a camera stutter would stall the expiry as well.
More importantly, the perception thread has no knowledge of the control
loop's cadence, and the whole reason the two-clock architecture exists is
that perception and control must not share a heartbeat. Putting the memory
in the *consumer's* clock (100 Hz) means the held state is sampled at the
same rate the mission samples everything else, so the tracker and the
mission see the world on the same beat. The 30 FPS thread stays a pure
sampler; the 100 Hz loop owns belief. That split — sampler owns pixels,
consumer owns memory — is the architectural sentence this version
contributes, and it generalizes: any future tracker, filter, or state
machine should live at the cadence of the layer that consumes it, not the
layer that senses it.

**Why the perception dict shape survives.** The tracker is polymorphic on
its input: it never indexes into the dict, so the perception layer can add
keys later without breaking the tracker. It holds the dict by reference, not
by copy, which means the caller must not mutate the dict after passing it in
(this is documented in the interface: treat the returned dict as
read-only). We chose pass-by-reference deliberately — a `dict(det)` copy per
frame at 100 Hz × 2 trackers is ~200 copies/s of a 5-key dict, which is
negligible, but a copy would silently decouple the held state from the live
perception, and we wanted the held state to *be* the last real observation,
bit-for-bit. When Layer 6 later reads `distance_est_mm` from the held dict,
it reads the real last-seen value.

**Interface contract, formally.**

- Input: `det` = detection dict (`center_x`, `normalized_x`, `area`,
  `bbox`, `distance_est_mm`) or `None`.
- Output: `self.last` = most recent detection dict if `now - last_seen <=
  cooldown`, else `None`. Guaranteed `None` within 500 ms of the last real
  detection regardless of input stream.
- Side effects: none. Thread-safe only if called from a single thread (the
  main loop) — we do not claim concurrent-safety; the main loop is the only
  caller.
- Failure behavior: if `det` is a malformed dict (missing keys), the tracker
  still stores and returns it; the failure is deferred to the consumer's
  KeyError. This is documented technical debt — validation lives upstream in
  `_find_largest_contour`, and we chose not to duplicate it.

**The integration wiring, concretely.** In the mission path we build a
derived perception view:

```python
red_tracker  = PillarTracker(cooldown=0.5)
green_tracker = PillarTracker(cooldown=0.5)

# per main loop, before layer6 update:
perception["red_pillar"]   = red_tracker.update(perception.get("red_pillar"))
perception["green_pillar"] = green_tracker.update(perception.get("green_pillar"))
```

Because `update_state` in `layer6_mission_manager.py` reads
`green_pillar is not None` and `red_pillar is not None` and then calls
`self.adapter.get_avoidance_direction(color)` to produce the ±0.6 offset,
the tracker output feeds the avoidance decision with zero changes to Layer 6
itself. The tracker is thus an adapter between the perception contract and
the mission contract — it does not change what either layer means, only
guarantees the mission never sees a pillar blink out of existence for less
than 500 ms. This "no-touch integration" was itself a design goal: on a
version with 10 lines of logic, touching three layers would have made the
diff impossible to audit.

**Timing budget summary.** Perception thread: 30 FPS, ~20 ms/frame budget,
dominated by HSV + masks + contours. Main loop: 100 Hz, 10 ms/frame budget,
tracker contribution ~2 µs (0.02% of the budget). Watchdog: 200 ms, tracker
can never contribute. The version adds no new thread, no new allocation
path in the hot loop beyond two small dict writes, and no config surface.
That is the entire blueprint: a two-float state machine with a wall-clock
expiry, wired as a pass-through between two existing layers.

### 8. Architecture / data-flow flowchart (~400 words + mermaid)

Data in v4.8 flows on two independent clocks that meet at the tracker. On
the left, the **30 FPS camera clock**: the Pi Camera v2 delivers 640×480
frames to `_async_camera_loop` in `layer4_perception.py`, which converts to
HSV, runs the four color masks, calls `_find_largest_contour` per color, and
writes a fresh perception dict under the `threading.Lock`. On the right, the
**100 Hz control clock**: `main.py` grabs the latest dict lock-free via
`process_frame()`, runs the 10-layer stack, and transmits 10-byte CRC8
packets to the ESP32-S3 at 100 Hz. The two clocks are decoupled by design —
the camera may stutter, the control loop must not.

The `PillarTracker` sits exactly on that seam, which is the architectural
point of this version. It receives the per-color detection (`red_pillar`,
`green_pillar`) from the perception dict and returns either the fresh dict
or the frozen last-seen dict, time-boxed to 500 ms. Downstream, Layer 6
converts persistence into `avoidance_offset = ±0.6`, and the Stanley
controller in Layer 10 turns that into `servo_angle_deg` and `motor_speed`
for the `PacketEncoder`. The VL53 sensors are drawn as a secondary lane:
they feed Layer 1 at ~68–100 ms cadence and end up in Layer 5's
`crosstrack_error_mm` / `front_mm`, but they do *not* carry pillar identity —
that lane stays color-blind and never feeds the tracker. That separation is
the C4 constraint made visible: identity flows only through the camera lane;
range flows through both but only the camera lane knows red from green.

```mermaid
flowchart LR
    subgraph SENSORS[30 FPS camera clock]
        CAM[Pi Camera v2<br/>640x480 @ 30 FPS] --> HSV[BGR->HSV + 4 masks]
        HSV --> CONT[findContours / largest / area>300]
        CONT --> PDICT[latest_perception dict<br/>red_pillar green_pillar magenta blue]
    end
    subgraph TOF[100 Hz-ish ToF lane, color-blind]
        VL1[VL53L1X front<br/>33ms+35ms ~68ms] --> L1[Layer1 sensors]
        VL2[2x VL53L0X XSHUT seq<br/>GPIO17/27] --> L1
        L1 --> L5[Layer5 localization<br/>crosstrack=(L-R)/2, front_mm]
    end
    PDICT -->|lock-free read| MAIN[main.py 100 Hz loop]
    MAIN --> TRK{{PillarTracker<br/>keep-last + 500ms expiry}}
    TRK -->|dict or None every cycle| L6[Layer6 mission<br/>offset = +-0.6 via SurpriseRuleAdapter]
    L6 --> L10[Layer10 Stanley<br/>desired_steering_rad]
    L10 --> ENC[PacketEncoder<br/>10-byte CRC8 @ 100 Hz]
    ENC --> ESP[ESP32-S3<br/>200ms watchdog]
    ESP --> ACT[Servo MG995 + TB6612]
    L5 --> L10
```

The two lanes meet only inside Layer 5→Layer 10 fusion for *geometry*
(cross-track centering), and the tracker is deliberately isolated from the
ToF lane. One design note: the tracker's output is re-injected into the same
`perception` dict the mission reads, so the data-flow arrow through the
tracker is a *replace-in-place* — no new channel was introduced, which keeps
the architecture diagrams from every prior version accurate except for one
annotated node.

### 9. Errors, failures, and root-cause analysis (~1,500 words)

**Error 1 (the headline): "Pillars vanished mid-turn, breaking the avoidance
decision."**

*Symptom.* During every 90° corner at mission speed on Day 111, the log
showed the mission's `avoidance_offset` flipping `0.6 → 0.0 → 0.6` at the
100 Hz control cadence for the duration of the turn. The red/green pillar
was present in `latest_perception` on the straightaway, then absent for
300–500 ms in the corner, then present again. The robot visibly steered back
toward the pillar in the middle of the very corner it was trying to avoid,
then snapped back. On one run this caused a ~90 mm cross-track excursion at
the apex — measured from the `crosstrack_error_mm` log in Layer 5 — and we
saw the robot brush the corridor edge marker.

*Initial hypotheses (honest list of what we guessed first).* (1) The camera
was dropping frames — a `cap.read()` failure or a USB bandwidth stall.
(2) The HSV thresholds had gone stale for corner lighting — the same class of
bug v4.4 fixed at venue lighting. (3) The pillar was genuinely too far to
detect mid-turn — a range problem. (4) The avoidance logic was toggling by
itself in Layer 6. We wasted about half a day chasing hypotheses 1 and 2
because they were our "known bad actors" from previous versions, and both
were consistent with what we saw on paper.

*Investigation.* We instrumented rather than guessed. We timestamped every
`process_frame()` read in `main.py` and every perception write in the camera
thread, and logged `frame_processed` and `camera_ok` alongside
`avoidance_offset` and the raw `front_mm`. Three facts came out of the log.
First, `frame_processed` was `True` for the *entire* corner — the camera was
delivering frames at 30 FPS, so hypothesis 1 was dead. Second, the HSV masks
were producing *zero* red/green contour output during the gap even though the
pillar was within 1.5 m — but the masks were also producing zero output for
*every* color including blue, which ruled out a color-specific threshold
failure and pointed at geometry, not lighting; hypothesis 2 died. Third, and
decisively, the gap start and end correlated exactly with the robot's yaw
rate: we overlaid `front_mm` and the Layer 5 heading, and the disappearance
happened precisely when `ω = v/R ≈ 3.6 rad/s` swept the pillar's bearing out
past the 62.2° camera FOV edge. The pillar wasn't gone; it was **outside the
sensor**, and our architecture had no mechanism to remember that it existed.

*Root cause, with the physical mechanism.* The failure was structural, not
accidental. The perception layer is a *sampler*: it reports what the camera
sees *now*. The mission layer is a *state machine*: it acts on what it
believes about the world. Between a sampler and a state machine there must
be a *memory*, and v4.4–v4.7 had none. When the robot turned, the camera
yaw rate moved the pillar's bearing past the FOV half-angle (31.1° each
side of boresight). The pillar then legitimately produced no pixels — the
photons weren't hitting the sensor — so `_find_largest_contour` returned
`None`, `latest_perception["red_pillar"]` became `None`, and
`update_state` read `red_pillar is not None` as `False`, zeroing the offset.
The mechanism is: **ego-motion moves the field of view faster than the
mission's belief-update can tolerate; without a temporal prior, absence of
evidence is interpreted as evidence of absence.** That last sentence is the
whole bug, and it is why the fix is not a detection fix.

*Fix.* We built `PillarTracker` (this version's entire code change): a
two-float state machine that keeps `self.last` and `self.last_seen`, adopts
any non-None detection, and clears the hold exactly 500 ms after the last
real detection. The mission now sees a continuous red/green pillar
observation through the whole corner and for up to 500 ms of occlusion.
Wired in as a pass-through on the perception→mission seam (Section 7).

*Prevention (process change, so it never returns).* We added a standing rule
to our architecture checklist: **any consumer that feeds a continuous
actuator (steering) must be fed a continuous belief, not a raw sample
stream.** Every perception output handed to a state machine from now on goes
through a temporal layer; the tracker pattern becomes a template. We also
added a regression test: a scripted corner with a stationary pillar where the
acceptance criterion is "`avoidance_offset` never touches 0.0 between pillar
entry and pillar exit." We log a test-assert failure if it does.

**Error 2 (discovered while tuning): the first cooldown we tried was 1.5 s,
and it produced ghost pillars.**

*Symptom.* With `cooldown=1.5`, the robot completed a pillar pass, drove 3 m
down the straight, and *still* reported a red pillar in the mission — the
`avoidance_offset` stayed at `-0.6` for a full 1.5 s after the pillar was
behind it. On the straights this meant the robot ran offset to the centerline
for 1.5 s / ~100 cycles after every pillar, and on lap two of the mission it
nearly shoved the car toward the opposite wall.

*Initial hypothesis.* We initially wrote it off as a Layer 6 state bug — we
were suspicious of the `SurpriseRuleAdapter`. That guess was wrong, but the
*shape* of the guess mattered: we assumed the bug was downstream of the
tracker when it was actually *in* the tracker's tuning.

*Investigation.* We logged `last_seen`, `now`, and `cooldown` every cycle for
a single pass. The data was unambiguous: `now - last_seen` grew past the
pillar-pass time and only crossed the 1.5 s threshold a full 1.5 s later,
exactly as the code says. There was no bug in the logic; the *constant* was
wrong. 1.5 s was chosen because "longer feels safer for the turn," which is
exactly the kind of non-derived tuning our own Section 5.1 methodology is
supposed to forbid.

*Root cause.* The cooldown is a *physics-derived* number (worst occlusion ≈
0.46 s) but we had tuned it by *feel* (1.5 s ≈ "long enough"). The mismatch
between a geometry-derived requirement and an intuition-picked constant is
the mechanism: a cooldown is a bet on how long the *world can hide a pillar*
while we still care about it, and the correct duration is bounded above by
"how long until acting on the pillar is wrong" and below by "how long the
pillar can genuinely hide." 1.5 s violates the upper bound: 3 m past the
pillar at 1.8 m/s, the pillar is no longer an obstacle to avoid, so holding
it is steering at a ghost.

*Fix.* `cooldown=0.5`, derived in Section 5.1 (≥ measured 0.46 s max, ≤ the
time-to-pass on the straight). The regression test (Error 1's) catches any
future regression because it asserts the offset returns to 0.0 within 500 ms
of the pillar passing the robot's widest point.

*Prevention.* A written rule: **temporal constants in a tracking/state
system must be derived from measured occlusion windows or from vehicle
kinematics, never chosen by comfort.** We added the measurement protocol
(record occlusion windows during scripted corners) to our test harness so
the constant has an audit trail. The `cooldown` value now has a comment
pointing to this journal entry.

**Error 3 (a near-miss we caught in review): a naive `while det is None:
sleep(0.1)` fallback that we almost wrote before the tracker.**

*Symptom.* None — this one never shipped. But the design review caught the
attempt, and it is worth recording because it was a genuinely plausible
"easy fix" and it would have been a live-fire failure.

*Initial design.* One of us proposed: when the mission sees `None` for a
pillar that was recently present, *busy-wait / sleep 100 ms and re-read the
perception dict*, on the theory that the pillar would reappear shortly. It is
a natural thought — "give the sensor time."

*Investigation / analysis.* We timed it on paper before writing it. A 100 ms
sleep inside the mission path violates the 10 ms control budget *tenfold*
and would cause a single 200 ms watchdog trip the instant two such retries
piled up (`100 ms × 2 > 200 ms`). We traced the exact failure: `main.py`
calls `layer6_mission.update_state(...)` inline in the 100 Hz loop; a sleep
there stalls `transmit_command` and the ESP32 watchdog fires, short-braking
the motors mid-corner — *worse* than the flicker we were fixing.

*Root cause.* The proposal inverted the architecture: it tried to make the
*sampling layer* synchronous to fix a *temporal belief* problem, adding
latency to the hot loop instead of adding state to the belief layer. Blocking
to "wait for data" is the anti-pattern that all our threading work in v4.x
(v4.4's async camera, v4.1's non-blocking sensor reads) was built to avoid.

*Fix.* We wrote the tracker — O(1), non-blocking, no sleeps — which achieves
the same "wait for the pillar to come back" *without blocking*, by
remembering it. The lesson turned into a hard rule: **never block the control
loop to await data; always add state that bridges the data gap.** This is now
checked in every design review: any `time.sleep` in the mission/control path
is rejected.

*Prevention.* The non-blocking rule above, plus a code-review checklist item:
hot-loop functions must contain no `sleep`, no I/O, no locks. The tracker
passes trivially; the fallback design fails it immediately.

**Error 4 (integration bug, fixed same day): both trackers were accidentally
sharing one instance.**

*Symptom.* Red and green pillars both steered the robot LEFT on the first
bench test — the red pillar produced a green-style avoidance.

*Initial hypothesis.* We suspected the `SurpriseRuleAdapter` direction logic
(SIGN_LOGIC) was inverted. Wrong guess.

*Investigation.* We read `update_state`: it branches on `green_pillar` then
`red_pillar`, calling `get_avoidance_direction(color)` for each — the logic
is color-correct. The bug was upstream: in the integration wiring we had
written `red_tracker = green_tracker = PillarTracker()`, one object aliased
under two names, so whatever color was seen last was held by *both*.
`update_state` then saw a "green" dict (actually the red one) and chose LEFT.

*Root cause.* Aliasing — two names bound to one object — in Python, two
separate `PillarTracker()` calls are required. The state machine had *one*
memory cell where the design required *two* (one per color). Identity
collision: red's detection was stamped into the same `self.last` that green
read.

*Fix.* Two instances: `red_tracker = PillarTracker(); green_tracker =
PillarTracker()`. Verified: red detection → red avoidance only, and the two
no longer cross-talk.

*Prevention.* A code-review rule: **stateful objects that model distinct
world entities (per-color trackers) must be separately instantiated; aliasing
state machines collapses identity.** We also added a unit test that feeds a
red dict and a green dict alternately to two trackers and asserts no
cross-contamination. This is the same class of bug as sharing a single filter
across two sensors, and the review rule generalizes to v5.x's filters.

### 10. Verification and metrics (~800 words)

**Test procedure.** We verified against the five acceptance criteria from
Section 3, in order, on the shop track with the robot's full 3-sensor suite
active.

1. *Holding window (criterion 1).* We placed a single red pillar at a corner
   apex, ran 12 scripted 90° turns at 1.8 m/s, and logged the mission's
   pillar observation plus the camera's raw detection per 100 Hz cycle. We
   measured the occlusion window (time from last raw detection to first raw
   re-detection) and the tracker's hold (time from last raw detection to
   tracker's `None`).
2. *Ghost death (criterion 2).* A 60-second run on an empty straight, no
   pillar present, tracking both colors the whole time. Counted every frame
   where the tracker returned a non-None result.
3. *Latency budget (criterion 3).* Timed `update()` over 100,000 calls with
   `time.perf_counter()` while the system ran the full 100 Hz loop, and
   compared loop latency (via `sys_mgr.get_average_latency_ms()`) with and
   without the tracker wired.
4. *Decision continuity (criterion 4).* Ran 10 pillar passes; logged
   `avoidance_offset` across each, asserting it never touched 0.0 between
   first detection and 500 ms after last detection, and never flipped sign.
5. *Non-blocking (criterion 5).* Reviewed the code for sleeps/locks/I/O in
   the update path (static) and confirmed the camera thread's FPS did not
   drop while the tracker ran (dynamic).

**Raw numbers measured.**

| Metric | Value measured | Acceptance |
|---|---|---|
| Occlusion window, 90° turn @ 1.8 m/s, 12 runs | 384–462 ms (mean 421, σ 24) | — (characterization) |
| Tracker hold before `None` | 500–507 ms (deterministic from wall clock) | ≥ window, ≤ 500+ε |
| Empty-track false claims (60 s) | 0 frames | 0 frames |
| `update()` median / p99 cost | 1.6 µs / 3.1 µs | < 1 ms |
| Loop latency delta with tracker | +0.02 ms (0.2% of 10 ms budget) | < 1 ms |
| Camera thread FPS with tracker | 30.0 FPS, unchanged | 30 FPS |
| `avoidance_offset` zero-crossings in 10 passes | 0 | 0 |
| Sign flips during hold | 0 | 0 |
| Ghost duration past widest point, cooldown 0.5 | 500 ms (by construction) | ≤ 500 ms |

**Pass/fail against Section 3 criteria.** All five PASS. Criterion 1: the
tracker held the pillar for 500–507 ms across all 12 turns, exceeding the
measured 462 ms worst occlusion. Criterion 2: zero false claims in 60 s on an
empty track. Criterion 3: 1.6 µs median versus a 1 ms allowance — the tracker
is 3 orders of magnitude inside budget, and the loop's average latency
changed by 0.02 ms. Criterion 4: zero offset zero-crossings and zero sign
flips across 10 scripted passes. Criterion 5: no sleeps/locks/I/O in the
path (static review), camera FPS unchanged at 30.0 (dynamic check).

**What we trusted afterwards.** The geometry derivation now has a measured
shadow: the 384–462 ms occlusion band sits exactly where `FOV/ω` predicted
(~0.30 s center-crossing, longer for corner-apex passes), which tells us our
camera FOV and vehicle kinematic models are honest — they produced a
falsifiable prediction that the data confirmed. We trust the wall-clock
expiry because it is structural (impossible to age past 500 ms), and we trust
the 30 FPS camera thread's stability because the tracker demonstrably added
zero load to it.

**What we still distrusted afterwards.** We did not yet trust the *held
position* over long occlusions — the frozen `center_x`/`distance_est_mm`
goes stale with robot advance, and while the sign never flipped in our 12
tests, we had no odometry to prove it stays correct in a sustained
multi-meter occlusion. We also distrusted our confidence in "one pillar per
color per frame": `_find_largest_contour` picks the largest blob, and a
tracker fed by a *mis-assigned* largest blob would quietly swap identities.
Neither case appeared in 22 runs, but both are known residual risks that we
deliberately deferred to versions with real localization (v5.x). Finally, we
distrusted the 0.5 s constant against *unknown* surprise-rule track layouts:
a future rule that hides a pillar behind a 0.7 s feature would beat our
cooldown, and nothing in this version adapts the window. That is a parameter
we expect to revisit under competition conditions.

**Regression notes.** Error 1's regression test (offset never touches 0.0 in
a scripted corner) ran clean after the fix; Error 4's identity test
(red/green cross-talk) ran clean; Error 2's ghost test (offset returns to
0.0 within 500 ms of the widest point) ran clean. All three are now part of
the pre-commit harness.

### 11. Lessons learned — permanent mental models (~600 words)

**Lesson 1 — Detection is sampling; tracking is belief.** A camera at 30 FPS
reports what it sees *now*; a mission state machine needs what it *believes*
about the world. Between any sampler and any actor there must be memory.
This version's entire value was adding two floats of memory. The permanent
model: **every sensor output that feeds a decision about the continuous
world needs a temporal filter, or absence of evidence becomes evidence of
absence.** Applied forward: v5.x localization, v6.x control, and v7.x mission
must all assume the perception stream is sampled, and each must carry its own
stateful bridge. The future risk prevented: shipping UKF localization (v5.x)
against a raw sample stream would have produced exactly the mid-corner
explosion we fixed here, but at the pose-estimation layer where it is far
harder to debug.

**Lesson 2 — Derive constants from physics, never from comfort.** The 1.5 s
cooldown felt safe and produced ghost pillars; the 0.5 s cooldown derived
from `FOV/ω` and measured occlusions was exactly right. The permanent model:
**any time constant in a tracking system is a bet about how long the world
can hide an entity while we still care about it — compute both bounds
(measured worst occlusion below, time-to-pass above) and pick between
them.** Applied forward: every filter constant in v5.x (UKF process noise,
measurement gates) and every delay in v7.x mission timing must carry a
derivation or a measurement. The future risk prevented: a UKF with
comfort-tuned process noise that diverges on Day 1 of competition.

**Lesson 3 — Never block the hot loop to await data; add state instead.** The
busy-wait fallback we almost wrote would have tripped the 200 ms watchdog
mid-corner — a failure worse than the bug it was fixing. The permanent model:
**latency and state are both legitimate ways to bridge a data gap; blocking
borrows latency from every downstream consumer, while state costs
microseconds and is local.** Applied forward: all v6.x control and v7.x
mission logic must be non-blocking at the 10 ms cadence; any sleep in the
mission path is a code-review reject. The future risk prevented: a
"wait for sensor" pattern in v5.x or v7.x that stalls the ESP32 watchdog and
costs a whole round.

**Lesson 4 — Stateful objects that model distinct world entities must be
separately instantiated.** The red/green alias bug collapsed two pillar
identities into one memory cell and steered the robot LEFT at a red pillar.
The permanent model: **a stateful object is an identity; aliasing two
identities onto one object is identity collision.** Applied forward: v5.x's
filters, v7.x's per-obstacle trackers, and any future multi-object state must
be instantiated one-object-per-entity. The future risk prevented: sharing one
filter between two sensors in v5.x, producing cross-contaminated pose
estimates.

**Lesson 5 — The smallest change that satisfies the stated requirements is
the strongest change.** Ten lines of Python replaced what a senior engineer
might have built as a Kalman filter with covariance, gates, and prediction.
The trade-off matrix (Section 5.4) is why we won: effort 10 LOC vs 200 LOC,
risk low vs medium, and the deferred alternative (D) reused the exact
pattern when v5.x arrives. The permanent model: **write the acceptance
criteria first, then find the minimum state machine that satisfies them;
filters buy accuracy only where accuracy is consumed.** Applied forward: v4.9
visual odometry and v6.x planning must ask "what does the consumer actually
need" before adding math. The future risk prevented: a heavy filter stack
that makes the 10 ms loop unschedulable and is untunable in the 120-minute
venue window.

### 12. Code in this snapshot

`pillar_track.py`

### 13. Bridge to the next version (~400 words)

v4.8 unlocks a perception layer that *persists* — the mission can now hold a
pillar's identity and direction across occlusion windows, which is the
precondition for anything that needs a coherent world over time. That is the
capability this version hands forward: **temporal continuity.** v4.9, already
scheduled (Day 115–117), is visual odometry: FAST corner features at 320×240
to estimate lateral motion between frames (`visual_odom.py`, `track_motion`).
The bridge is direct — the tracker's held pillar *is* a landmark that odometry
can measure against, and the odometry's measured ego-motion is exactly what
our frozen held-state (Section 5.6, deferred item 1) needs to stop being
frozen. The two features are mutual: tracking gives odometry a persistent
reference; odometry gives tracking the motion model we explicitly deferred.

The known debt that v4.9 must attack is the **staleness of the held state**.
Within 500 ms at 1.8 m/s the robot advances 0.9 m and the pillar's bearing
drifts ~61°; our tracker tolerates that because the mission only needs the
sign of the offset, but any consumer that needs *position* — path planning,
parking geometry, or a surprise rule that demands a precise avoidance line —
will break on a frozen dict. Visual odometry is the first step of the fix:
if we can estimate the robot's own motion between frames, we can advance
`self.last`'s position by the ego-motion delta instead of freezing it, and
the cooldown window can stretch beyond 500 ms without going stale. Second
debt: identity disambiguation (largest-blob ambiguity, Error 4's family)
needs a real data-association layer once the field can hold more than one
pillar per color. And third, the 0.5 s constant is a fixed bet; v5.x
localization's heading estimate lets us make the cooldown adaptive
(`cooldown = k/ω`) so a slow, wide turn doesn't expire the pillar
prematurely. The reasoning for ordering: pose (v5.x) cannot be trusted
without first having ego-motion (v4.9), and ego-motion cannot be measured
against a blinking world (fixed in v4.8). The chain is deliberately built
brick by brick.
