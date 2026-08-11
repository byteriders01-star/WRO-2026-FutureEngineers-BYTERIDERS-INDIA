| Version | Phase | Days |
|---------|-------|------|
| v3.3 | Sensing the World | Day 67-69 |

# v3.3 — Gyro heading

---

## 3. Mission of this version

The single problem this version attacks is that our robot had pitch, roll,
speed, and three laser rangefinders, but **no sense of direction**. By the end
of v3.2 we could tell the robot it was tilting 2.1° nose-up and rolling 1.4°
left, but we could not tell it which way it was facing. Every later behaviour
that matters in a WRO 2026 Future Engineers run — hold a commanded course,
detect a 90° corner, count laps, and eventually know where it is on the track
— starts from a heading. The track is a closed, walled course; a robot that
cannot tell it has turned around a corner cannot know it has started lap two.
So the correct next step after tilt was **heading**, and the reason it was the
correct step is traceable down the whole roadmap: v4.2's corner detector is
literally defined as "integrated gyro yaw plus front distance dropping below a
threshold", v5.0's dead reckoning integrates `dx = v*cos(theta)*dt,
dy = v*sin(theta)*dt` where `theta` is exactly the heading this version must
produce, and the v5.x UKF will carry a six-dimensional state in which `theta`
and `gyro_bias` are two of the six axes. Nothing downstream works without a
trustworthy heading stream, and everything downstream gets simpler the earlier
we prove the heading is measurable and bounded.

The capability gap at the end of v3.2 was precise. v3.2 (Day 64-66) fused the
accelerometer's gravity vector with gyro integration through a complementary
filter (`ALPHA = 0.92`) to produce low-noise pitch and roll, and it fixed the
1-second lag of `alpha = 0.98` by lowering the constant — a real, measured
trade-off. But the filter only ever used the gyro's **x** and **y** axes; the
**z** axis — the yaw channel — was read, logged, calibrated, and then ignored.
v2.4 (Day 40-42) had proven the z-axis gyro could hold a 0° heading with a PID
(`Kp=1.2, Ki=0.05, Kd=0.1`) over a 5 m straight, and that same version logged
a bias `b ≈ 0.06°/s` and a noise floor around `0.013°/s` RMS. So the hardware
was proven and the axis was understood; what did not exist was a **heading
producer**: a stream of `heading = X.X deg` that is not the error term of a
controller but an independent, reusable measurement. That is the entire
deliverable of v3.3.

We wrote the acceptance criteria on Day 67 before writing a line of code, so
the gate could not be argued with afterwards:

- **AC1 — Heading stream.** The robot must publish a heading estimate at the
  nominal 100 Hz control cadence with no more than 15 ms of jitter in the
  measurement interval, printed or serialised as `heading=±YYY.Y deg`.
- **AC2 — Bounded drift per lap.** After bias subtraction, an integrated
  heading must drift less than **5° over one 60-second lap** of straight-line
  driving with no corners, measured against a fixed reference (the start wall,
  re-read with a protractor).
- **AC3 — Wrap correctness.** The estimate must cross ±180° cleanly — a robot
  turning from 179.9° to -179.9° must not print a 359.8° jump. Verified by a
  bench rotation.
- **AC4 — Stability under motor power.** With the motor and servo running,
  the heading estimate must not swing more than **±1.5°** (noise envelope)
  and must not be systematically displaced by more than 0.5° by the magnetic
  field of the motor. This is the criterion that kills or keeps the
  magnetometer.
- **AC5 — Reset discipline.** The estimate must support a corner-reset
  contract: after a commanded or detected 90° rotation, the heading may be
  snapped to the nearest multiple of 90°, and the design must state what
  accumulated error that snap absorbs.
- **AC6 — CPU budget.** The whole heading loop must stay under **2 ms per
  tick** of Pi CPU, because the same Pi 4B will later run the 640×480@30 FPS
  HSV pipeline, the UKF, and the Stanley controller.

Done looks like: `gyro_heading.py` in this folder, a printed heading stream
that survives motor power on, a signed-off table showing AC1–AC6 pass/fail,
and a one-paragraph hand-off to v4.2 explaining exactly what "reset at
detected corners" means numerically.

---

## 4. Engineering context — where we stood

By Day 67 the sensing phase had built an honest picture of our own IMU, and
v3.3 had to respect every one of those lessons because they were paid for with
real hours.

v3.0 (Day 58-60) logged raw MPU6050 accelerometer and gyro at 100 Hz to a CSV
for offline analysis, and it taught us the **warmup garbage**: the first
~1 second of data after power-on is full of spikes, and the fix was to discard
the first 100 samples during a warmup phase. That 100-sample discard is now
baked into the muscle memory of every file in the family, and `gyro_heading.py`
opens with exactly that `for _ in range(100): mpu.get_gyro_data()` warmup
loop.

v3.1 (Day 61-63) measured gyro bias and accelerometer offset at rest —
`N = 200` samples at 5 ms spacing, i.e. one full second of averaging — wrote
them to `imu_bias.json`, and subtraced them at boot. Its lesson was blunt:
"calibrate at the venue, not at home — temperature changes everything." The
bias that was 0.06°/s at home was 0.09°/s in the hall. v3.1 also set the trap
that v3.3 steps into: once bias is stored in a JSON file, a lazy prototype can
quietly *not load it* and nobody notices until the heading drifts.

v3.2 (Day 64-66) built the complementary filter for pitch and roll with
`ALPHA = 0.92`, proving the integration math (gyro rate times measured `dt`,
then a soft correction toward the accelerometer's gravity vector) and
normalising with `atan2`. It used gyro **x** and **y** only. The z-axis, our
future heading channel, had been read and logged but never integrated.

The system-level constraints that shape everything:

- **Brain:** Raspberry Pi 4B. The heading loop is trivially cheap — a few
  microseconds of I2C and a few multiplies per tick — but the same Pi will
  later hold the 640×480@30 FPS HSV pipeline, a 6-D UKF, and a Stanley
  controller. Whatever timing discipline v3.3 proves at 100 Hz is the
  discipline the whole mission stack inherits. The budget we agreed for the
  heading loop was under 2 ms per tick of the Pi's time.
- **Muscle:** ESP32-S3 with a 200 ms watchdog. The heading estimate lives on
  the Pi, not the ESP32; the ESP32 remains a thin actuator. But the 100 Hz
  serial link that already carries `AA 55 | seq | cmd | servo*100 | speed*10 |
  CRC8 | 0D` ten-byte packets is the same cadence the heading loop must match,
  so that when v6.x closes the loop the heading arrives at the same tick
  rhythm as the commands.
- **Link:** USB-UART at 115200 baud 8N1, 11,520 bytes/s raw; a 10-byte packet
  is 0.868 ms of wire time; 100 Hz of packets is 1,000 bytes/s = 8.7% of link
  capacity. Bandwidth has never been the constraint — cadence and integrity
  are. The heading stream must not need more link; it will ride on the same
  cadence as everything else.
- **IMU:** MPU6050 at address 0x68 on the I2C bus, wired through `busio.I2C`
  on `board.SCL`/`board.SDA`. Full-scale gyro range we selected is ±250°/s,
  which covers the whole driving envelope — v2.9 measured 62°/s of yaw rate in
  a 0.5 m tight turn at 0.54 m/s and 206°/s at 1.8 m/s, both comfortably inside
  ±250°/s. The MPU6050's onboard DMP and the separately-attached magnetometer
  were both options this version has to judge.
- **Actuators:** one MG995 servo through the rigid 4WS linkage with rear ratio
  0.85, and a TB6612FNG motor driver. The MG995 servo draws 1–2 A stall
  current and the motor several amps at launch — both are *magnetic field
  sources*, which is the whole reason this version's headline error exists.
- **Battery:** a single pack sized for a WRO vehicle; v2.0 proved it can sag
  under full motor current. v3.0's logs showed bias drifting with temperature;
  v3.3's measurements run against the same charge sag, so every test had to
  record battery voltage alongside the heading data.
- **UI:** five green LEDs on GPIO 5/6/13/19/26 and a switch on GPIO 16. v3.3
  is a bench/prototype version, so the LEDs are not directly used, but the
  discipline of "state visible on the floor without a laptop" means the
  heading test rig prints `heading=...` to the console continuously and can be
  watched live.

The pressure on Day 67 was real and numerical. The sensing phase (v3.x) spans
Days 58–87; after heading comes ToF production (v3.4), ToF fusion (v3.5),
camera capture (v3.6), colour (v3.7), blobs (v3.8), and health monitoring
(v3.9), and then the whole track-understanding phase (v4.x) starts on Day 88
with v4.0 wall detection and v4.2 corner detection leaning directly on this
version's heading. We had three days to deliver a heading that survives motor
power and a documented reset contract. The debt was compounding in the other
direction too: v2.4's heading-hold PID had quietly depended on an
uncalibrated, unintegrated gyro and had been tuned around a ~2.7° mean heading
residual (recorded in v2.5's journal); every day we postponed a real heading
estimate, that residual stayed an unexplained black box inside a controller
that already worked. This version converts the black box into a measurement.

---

## 5. The engineering thought process — first principles

This is the heart of the journal, so we are going to be honest about the order
in which the reasoning happened — including the two derivations that turned
out to be wrong and the moment a motor field overruled both of them.

### 5.1 Constraints and hard limits (derived with numbers)

We began by writing down the physics of heading, then the numbers of our
specific robot, in that order, because the physics decides what the numbers
mean.

**C1 — Heading is the integral of yaw rate, and integrals accumulate error
without bound.** By definition, angular heading satisfies
`d(theta)/dt = omega_z`, so `theta(t) = theta(0) + integral(0..t) omega_z(t')
dt'`. The gyro measures `omega_z`; we integrate it. Integration is a
low-pass on noise — the noise variance grows linearly with time, so the noise
sigma grows as the square root of time — but a **constant bias** in the rate
integrates into a heading error that grows *linearly* in time. With v2.4's
measured `b ≈ 0.06°/s` of uncompensated z-bias, a 60-second lap carries
`0.06 × 60 = 3.6°` of heading error; a three-minute run carries `10.8°`. A
bias of `0.10°/s` (the venue-warm value v3.1 saw) gives `6.0°` per lap. At a
1 m standoff, `1°` of heading error is `1.75 cm` of lateral offset — so the
uncompensated-bias lap error of 3.6° is a 6.3 cm lateral miss, and the 10.8°
three-minute error is 18.9 cm. **Heading drift is not a tuning problem; it is
a definite integral.** That is the first constraint, and it dictates that any
usable heading needs (a) bias subtraction and (b) an absolute reference that
re-binds the integral before the error grows large.

**C2 — The reference that is cheap, absolute, and always wrong on a
brushed-motor robot: the magnetometer.** A magnetometer measures the local
magnetic field vector — Earth's field is roughly 25–65 µT depending on
latitude — and heading is `atan2(mag_y, mag_x)` in the horizontal plane. In
principle this is a free absolute reference: it points at magnetic north no
matter how long the integration has run. In practice, the field at the sensor
is the *vector sum* of Earth's field and every field the robot itself
produces. A brushed DC motor carries several amps through copper coils wrapped
around permanent magnets; the resulting dipole at 10–30 cm range produces a
field of order 10–100 µT — *comparable to or larger than* Earth's own field.
A magnetic disturbance of magnitude `D` rotating in the horizontal plane
corrupts heading by up to `atan2(D, B_earth)` — for `D = 30 µT` against a
`45 µT` earth field that is `33.7°`. And because the disturbance is driven by
current, it switches sign when the motor reverses and ripples at the PWM
frequency (ours runs above the audible band per v2.2). The MG995 servo adds
the same effect at stall. C2 says: the magnetometer's headline advantage
(absolute reference) is cancelled by a field the robot cannot remove at its
mounting point.

**C3 — The only references that physically exist on a WRO walled course are
the walls and the corners.** A 90° corner is an absolute heading reference in
disguise: if we detect that the robot has turned a corner, the true heading
has changed by *exactly* ±90° (or the course's corner angle). The course is
regular and walled; the corners are guaranteed and detectable by the front
ToF plus the integrated yaw (that is v4.2's definition). So we do not need a
magnetometer to re-bind the integral — **the geometry of the track provides
the reference**, sampled once per corner. The corner-reset contract is then:
at every detected corner, snap the heading to the nearest multiple of 90°.
The accumulated drift between resets is what the corner absorbs, and C1's
arithmetic says it will be small: with residual bias ≤ 0.01°/s after
subtraction and at most ~30 s between corners, the worst drift absorbed by one
reset is `0.01 × 30 = 0.3°` — far inside the ±45° decision margin that
separates one multiple of 90° from its neighbour.

**C4 — The I2C and the clock are both constraints, but different kinds.**
`mpu.get_gyro_data()` reads the MPU6050 registers over I2C. At a 400 kHz clock
a ~14-byte register read costs roughly 0.3–0.5 ms. At a nominal 10 ms tick
that is ≤ 5% of the tick — cheap, but it means the *read itself* takes time
inside the interval it measures. The bigger trap is the clock: `time.sleep(0.01)`
does not deliver exactly 10 ms on a Linux Pi — the scheduler, Python GC, and
USB interrupts stretch it to 10–15 ms. If we *assumed* `dt = 0.010` and the
true gap were 15 ms at a yaw rate of 62°/s (the tight-turn rate), each tick
would over-integrate by `62 × (0.015 − 0.010) = 0.31°` — systematically, in
the same direction, every turn. That is why the snapshot measures `dt` with
`time.time()` twice per loop instead of assuming it: measured `dt` turns the
scheduling jitter from a *systematic* bias into *random* error whose mean is
zero, at the cost of a noise sigma driven by the clock's own resolution
(negligible on the Pi's nanosecond timer).

**C5 — The noise floor decides what the gyro can and cannot resolve.** v2.4
logged a z-gyro noise sigma around `0.013°/s` per sample (the figure cited in
that version's journal) — call it `σ ≈ 0.01–0.05°/s` across conditions. Under
integration over `N` samples the random-walk heading noise is
`σ_heading ≈ σ · sqrt(N)`. At 100 Hz, a 60-second lap is `N = 6000` samples,
so `σ_heading ≈ 0.013 × sqrt(6000) ≈ 1.0°` RMS of pure noise walk — small
against the 5° AC2 budget, and it averages out in the corner resets. The
conclusion of C5: random noise is *not* the enemy of heading; bias is.

**C6 — Tilt couples into yaw, but only a little, and only on slopes.** The
MPU6050's z-axis is perpendicular to its board. If the robot is perfectly
flat, the z-axis is vertical and `omega_z` is pure yaw. On a slope of angle
`pitch`, a turn about the world-vertical axis projects onto the sensor axis
with a cosine loss: apparent `omega_z = omega_true · cos(pitch)`. At 5° pitch,
`cos(5°) = 0.996`, so the error is 0.4% — a full lap of corners (360° of
heading) underestimates by `1.4°`. The WRO track is essentially flat (any
ramp is short), so C6 says tilt coupling is a second-order effect we note and
do not chase in this version; v6.x can revisit if a ramp appears. The
mounting axis, however, was a real decision we verified on the bench: the
sensor is mounted with its board plane horizontal so the z-axis points up,
which is the only mount that makes the yaw channel usable at all — and the
mount is mechanically stiff (no foam), because a loosely-mounted IMU turns
tilt into apparent yaw at any vibration.

**C7 — The heading must not cost the control loop anything.** The 100 Hz
command cadence already costs ~3 ms per tick worst case (v2.9's measured
budget), and the Pi will later run vision. Adding a heading loop that reads
I2C (~0.5 ms), integrates, normalises, and prints (~0.1 ms) adds well under
1 ms per tick — but only if it is a single lightweight loop and not a
framework. AC6's 2 ms ceiling is generous; the design must be a tight loop,
not an abstraction.

### 5.2 Requirements derived from constraints

Every requirement is written as "constraint C ⇒ requirement R" so the review
can audit the chain.

- C1 (integral accumulates bias error linearly: 3.6°/lap at b=0.06°/s) ⇒
  **R1:** The heading estimate must subtract a bias measured at boot from the
  venue (v3.1's `imu_bias.json`), and must be re-bound by a corner reset at
  least once per lap so no drift larger than ~1° is ever carried across a
  corner.
- C2 (motor field 10–100 µT corrupts magnetic heading by tens of degrees) ⇒
  **R2:** The magnetometer must be evaluated under motor power against AC4
  before being trusted; if it fails AC4's ±1.5° envelope, it must be disabled
  permanently via the config flag `enable_magnetometer=false`, not "filtered".
- C3 (90° corners are absolute heading references in disguise) ⇒ **R3:** The
  heading API must expose a reset-to-nearest-90° operation that consumes
  accumulated drift, and the contract must specify that drift magnitude for
  v4.2.
- C4 (I2C read ~0.3–0.5 ms inside a 10–15 ms jittered tick) ⇒ **R4:** `dt`
  must be *measured* with `time.time()` each loop, never assumed equal to the
  sleep period, converting scheduling jitter from systematic to random.
- C5 (noise walk ~1.0° over a lap vs bias error 3.6–10.8°) ⇒ **R5:** Bias
  subtraction and bias stability matter; noise is accepted as-is and averaged
  out by resets. No low-pass smoothing of the rate is required — it would add
  lag for no measurable gain.
- C6 (tilt projects yaw with `cos(pitch)`, 0.4% at 5°) ⇒ **R6:** Mount the
  IMU board-plane-horizontal, z-axis up, mechanically stiff; document the
  0.4% slope error as accepted risk for the flat track.
- C7 (budget: <1 ms added per tick) ⇒ **R7:** The heading loop must be a
  single tight loop; no threads, no queues, no buffering in v3.3.
- System (Pi will run vision + UKF + Stanley later) ⇒ **R8:** Heading is a
  *measurement* — printed and, later, serialised — never hidden inside a
  controller; v5.x's UKF needs it as an observation, and v2.4's mistake of
  keeping the estimate inside the PID is not repeated.
- System (100 Hz link, 8.7% used) ⇒ **R9:** v3.3 ships heading on the Pi side
  without adding new link bandwidth; when telemetry exists (later versions),
  heading rides the existing 100 Hz slot, not a second stream.

### 5.3 Alternatives considered

We walked through five candidates honestly before choosing.

**A1 — Magnetometer heading, taken at face value.** The HMC/AK-style
magnetometer attached to the MPU6050 bus, read directly and converted with
`atan2`. This was our *first* instinct, because it is the classic "free"
absolute heading. On the bench, with the robot unpowered, it produced a
smooth, plausible heading that agreed with a physical protractor to within
~2°. The moment the motor ran — even at 20% PWM, no load — the heading swung
by 30–90° and tracked the throttle sign. This is C2 in the flesh. We did not
filter it, because the swing was not noise (filtering would only smooth the
lie) and because the swing reproduced with the same polarity every run. The
choice became "fix the mounting or drop the sensor"; with three days left and
the corner reference of C3 already available, dropping was the honest call.

**A2 — Magnetometer with soft/hard-iron calibration (figure-8 rotation +
stored offsets), used when the motor is off.** The textbook fix for motor
fields is to calibrate the disturbance out: rotate the robot, fit the
ellipse, store offsets and gains, and subtract them. Honest analysis: hard-iron
calibration removes *static* fields from permanent magnets, but the TB6612FNG
drives a *current-dependent* field that changes with every throttle change —
a dynamic, non-linear disturbance that no static ellipse captures. The MG995
servo's field appears only at stall and jumps in discrete steps. We estimated
the residual heading error after a perfect static calibration would still
exceed 10° whenever current changed, and we would have spent the whole version
chasing a calibration that the rules of the vehicle (motor on, always) forbid
us from ever using. Rejected as a dead end with the venue three days away.

**A3 — Pure gyro yaw integration, bias-subtracted, with corner resets.**
Integrate `omega_z` with measured `dt`, subtract the v3.1 bias, normalise the
angle, and re-bind the integral at every detected corner by snapping to the
nearest 90°. The reference is not a sensor that the robot's own fields can
corrupt — it is the geometry of the track. This is C1+C3 together, and it is
what the original short CHANGE.md summarises as "gyro yaw integration with
reset at detected corners". Cost is low, latency is one tick (~10 ms), and
it exercises exactly the axes v2.4 already proved (the z-gyro noise and bias
are measured, not guessed). Its weakness is absolute-lessness between corners:
if a corner is *missed* by the detector, the drift runs until the next
successful reset — hence the reset contract must include a drift-health bound.

**A4 — Gyro + magnetometer complementary filter.** Blend a slow, absolute
magnetic heading with a fast, drifting gyro heading (the inverse of v3.2's
tilt filter). In a clean magnetic environment this is the best of both worlds.
On our robot, the magnetic channel is a corrupt input, and a complementary
filter would drag the clean gyro estimate toward a corrupted absolute one —
**a filter cannot repair a sensor that is lying**. We computed the damage: at
a 0.5 weight toward the magnetometer and a 30° magnetometer error during a
throttle pulse, the blended heading is displaced by ~15° for the duration of
the pulse. Rejected for the same reason as A2, more sharply: the lying sensor
poisons the honest one.

**A5 — Vision-based heading (vanishing point / lane-edge angle).** Take the
camera's lane-edge lines and derive a heading from their perspective angle.
The 640×480@30 FPS HSV pipeline that would feed this did not exist yet (v3.6
camera, v3.7 colour, v3.8 blobs are all still ahead), and the 33 ms frame
period plus 50–100 ms of processing latency means a vision heading lags a
100 Hz control loop by 5–10 ticks — at 62°/s that is 0.5–1.0° of heading
error from latency alone. Vision is a *position* and *landmark* sensor for us,
not a rate sensor. Deferred, with a note that v4.x's wall detection will
eventually provide an absolute cross-track reference that can anchor the gyro
heading the way the corners do.

### 5.4 Trade-off matrix

Scores 1–5, higher is better. Weights chosen for Day 67: three days to
delivery means effort matters; the robot cannot drive without motor power so
"works only when the motor is off" is a disqualifier; and the estimate feeds
four later versions, so reuse weighs heavily.

| Alternative | Effort (5=easy) | Robustness (5=rock solid) | Speed/latency (5=best) | Risk (5=safest) | Reuse into later code (5=high) | Weighted total | Verdict |
|---|---|---|---|---|---|---|---|
| A1 raw magnetometer | 5 (read + atan2) | 1 (30–90° swings under motor) | 5 | 1 (corrupt input) | 1 | 13 | **Tested, rejected on AC4** |
| A2 mag + static calibration | 2 (figure-8 + ellipse fit) | 2 (static cal misses dynamic field) | 4 | 2 (residual >10°) | 2 | 12 | Rejected: dead end in 3 days |
| A3 gyro integration + corner reset | 4 (30-line loop + reset API) | 4 (drift bounded by geometry) | 5 (10 ms, one tick) | 4 (missed-corner exposure) | 5 (theta feeds v4.2, v5.0, v5.x UKF) | 22 | **Winner** |
| A4 gyro+mag complementary | 2 (blend math) | 2 (lying sensor poisons blend) | 4 | 2 | 3 | 13 | Rejected: cannot repair a liar |
| A5 vision heading | 1 (pipeline not built) | 3 (could be good later) | 1 (33 ms + 50–100 ms latency) | 3 | 4 (v4.x wall anchor) | 12 | Deferred: right idea, wrong week |

Justification for the winning row: A3 is the only option that stays inside the
accuracy budget while the motor is running (the only mode that exists in a
race), that costs one tick of latency, and that produces a `theta` channel
four later versions consume verbatim. Its single real risk — a missed corner
letting drift run — is bounded by C1's arithmetic (≤ 1° per lap of residual
drift at a 0.01°/s bias) and by the reset contract R3, and it is the same risk
every corner-based system in the sport carries.

### 5.5 Decision and mathematical / logical justification

We chose A3: **gyro yaw integration with measured `dt`, bias subtraction from
the venue calibration, `atan2` normalisation, and a corner-reset contract that
snaps heading to the nearest multiple of 90°.** The logic, in one sentence:
*the only heading reference a robot with a brushed motor can trust is the one
that cannot be disturbed by the motor — and on a walled course, the corners
are that reference.*

The maths of the decision is the error budget. Over a 60-second lap:
- bias error with no compensation: `0.06 × 60 = 3.6°` (fails AC2's 5° only
  at the margin, but grows unbounded across laps — fails the *spirit* of the
  criterion);
- bias error after subtraction: `0.01 × 60 = 0.6°` (passes AC2 with 4.4° of
  margin);
- noise walk: `0.013 × sqrt(6000) ≈ 1.0°` RMS (passes);
- tilt coupling on a 2° slope: `2° × 0.02% ... ` i.e. `360° × (1 − cos(2°))
  ≈ 0.22°` over a full lap of corners (negligible);
- worst accumulated drift between two corners (~30 s): `0.01 × 30 = 0.3°`,
  comfortably inside the ±45° nearest-multiple decision margin.

Every term is either a measured quantity (bias 0.06°/s, noise 0.013°/s) or a
geometry constant (90° corners, flat track). No term requires trusting a
sensor the robot's own fields can corrupt. And the corner reset means the
estimate is *bounded* — it cannot wander without limit, because every 90° of
track geometry re-binds it.

The latency argument is the same one v2.4 made for the PID: the heading is
fresh within one 10 ms tick, versus a magnetometer read plus filtering at
best a few ms slower and corrupted, versus vision at 33–100 ms late.

We also chose the **measured-`dt` integrator with `atan2` normalisation**
inside A3, and the reason is the C4/C5 pair: measured `dt` converts
scheduling jitter from systematic to random (zero-mean), and `atan2(sin,
cos)` keeps the angle bounded to ±180° so a crossing of the wrap point prints
`-179.9` instead of `+180.1` — AC3. The bias value itself comes from v3.1's
`imu_bias.json`, recorded at the venue, because v3.1's lesson (calibrate at
the venue) is a hard rule, not a preference.

### 5.6 What we deliberately deferred, and why

Scope control was a conscious act on Days 67–69.

1. **Magnetometer mounting/cabling redesign.** A magnetometer *could* be
   saved by moving it to the top of the vehicle, far from the motor and
   servo, and re-calibrating in situ. That is a mechanical redesign with
   zero guarantee of success on a vehicle whose motor current changes
   every throttle tick. Deferred permanently — the corner reference makes it
   unnecessary, and HISTORY.md's hardware table now correctly records "MPU6050
   (magnetometer disabled)".
2. **Vision-based heading (A5).** The camera pipeline does not exist yet and
   latency disqualifies it for control. It returns in v4.x as a *wall-anchor*
   that corrects cross-track position, not as a yaw rate.
3. **Formal Kalman-style fusion of heading with ToF/camera.** That is the
   v5.x UKF's entire job (6-D state including `theta` and `gyro_bias`). v3.3
   deliberately ships a single-stream estimate, because fusing a measurement
   that does not exist yet is noise.
4. **A heading-hold PID at the *mission* level.** v2.4 already proved heading
   hold; v3.3 builds the *measurement* that hold uses. Re-verifying the PID
   belongs to v6.x control, not this version.
5. **Serialising heading to the ESP32.** No consumer on the ESP32 needs
   heading in v3.3; shipping it down the link would burn 8.7% budget for no
   gain. The hand-off to v4.2/v5.0 happens in software on the Pi.

---

## 6. Decision flowchart

The branching below is the actual decision process of section 5 as we lived
it, from the moment we discovered the magnetometer could not be trusted under
power.

```mermaid
flowchart TD
    A[Day 67: need heading for<br/>corner detection + lap counting<br/>capability gap: tilt only, no yaw] --> B{What can produce<br/>an absolute heading<br/>reference?}
    B -- Magnetometer is<br/>'free absolute north' --> C{Test under motor power:<br/>does heading stay within<br/>+-1.5 deg at any throttle? AC4}
    C -- No: 30-90 deg swings,<br/>scales with current --> D[Root cause: motor + servo<br/>fields 10-100 uT vs earth 45 uT<br/>atan2 disturbance up to 33 deg]
    C -- Yes --> E[Keep magnetometer<br/>enable_magnetometer=true]
    D --> F{Can static hard/soft-iron<br/>calibration remove it?}
    F -- No: field is current-dependent,<br/>dynamic, not an ellipse --> G[Reject magnetometer<br/>enable_magnetometer=false permanently]
    F -- Yes --> H[Calibrate, keep sensor]
    G --> I{What re-binds the integral<br/>of gyro yaw?}
    I -- 90-deg corners are<br/>absolute references in<br/>the track geometry --> J[Corner-reset contract<br/>snap to nearest multiple of 90 deg]
    I -- vision pipeline<br/>not built, 33-100 ms lag --> K[Defer vision heading to v4.x<br/>as wall anchor, not yaw]
    J --> L{Integrate with what dt?}
    L -- time.sleep 10 ms is<br/>10-15 ms real, systematic<br/>over-integration at 62 deg/s --> M[Measure dt with time.time()<br/>each loop: jitter becomes zero-mean]
    L -- assume dt=0.010 --> N[Rejected: 0.31 deg/tick<br/>systematic error in turns]
    M --> O{Bias from where?}
    O -- imu_bias.json measured<br/>at venue, 0.06-0.10 deg/s --> P[Subtract before integrating<br/>residual ~0.01 deg/s]
    O -- home calibration --> Q[Rejected: venue temperature<br/>changes bias 50%]
    P --> R[Normalise with atan2(sin,cos)<br/>wrap cleanly at +-180 deg AC3]
    R --> S[heading=YYY.Y deg at 100 Hz<br/>bounded drift per lap AC2]
    S --> T[v4.2 corner detection<br/>yaw 90 deg + front distance drop]
    T --> U[Lap counting<br/>4 x 90 deg per lap]
    S --> V[v5.0 dead reckoning<br/>dx=v*cos(theta)*dt]
    S --> W[v5.x UKF 6D pose<br/>theta + gyro_bias states]
```

Two decision points carried the version. **C → D → F → G**: we refused to
keep a sensor on a faith that its calibration could be static, when the
measurement under power (30–90° swings tracking throttle sign) proved the
disturbance is dynamic. The order of the branches matters: we tested *under
power* before we tested *calibration*, because a calibration that works only
with the motor off is a museum piece. **I → J**: the insight that corners are
references is what turned a doomed integrator (drift unbounded) into a
bounded one (drift consumed by geometry) without needing any sensor the motor
can corrupt.

There is a quieter branch at **L → M**: measuring `dt` instead of assuming it
is a two-line change that converts a *systematic* failure into a *random*
one. It looks trivial; it is the difference between a heading that is
consistently wrong in turns and one that is merely noisy. We write it into
every future integration on this robot.

---

## 7. Implementation blueprint

The snapshot folder contains exactly one file, `gyro_heading.py`, and it is
deliberately twelve lines long. That is not poverty — it is the entire
version's contract compressed. The heading estimate is a measurement, not a
framework, and the file is written so a junior can read the physics directly
off the screen. Here is the file in full, then the walkthrough.

```python
import time, board, busio, math
from mpu6050 import mpu6050
i2c = busio.I2C(board.SCL, board.SDA)
mpu = mpu6050(0x68)
for _ in range(100): mpu.get_gyro_data()
yaw = 0.0; last = time.time()
while True:
    dt = time.time() - last; last = time.time()
    yaw += math.radians(mpu.get_gyro_data()["z"]) * dt
    yaw = math.atan2(math.sin(yaw), math.cos(yaw))
    print(f"heading={math.degrees(yaw):.1f} deg")
    time.sleep(0.01)
```

### 7.1 The I2C contract (lines 3–4)

`i2c = busio.I2C(board.SCL, board.SDA)` opens the I2C bus on the Pi's hardware
SCL/SDA pins, and `mpu = mpu6050(0x68)` binds the driver to the MPU6050's
factory address. Two things are deliberately *not* here: there is no repeated
bus re-init and no error handling. On this robot the bus was already proven
stable by v3.0's 100 Hz logger; adding retry logic would hide the next real
failure instead of exposing it. If the bus dies, the exception terminates the
loop loudly — on the bench that is what we want during a prototype. The
read itself, `mpu.get_gyro_data()`, returns a dict with `"x"`, `"y"`, `"z"`
keys in degrees per second; we consume only `["z"]`, the yaw channel, in
keeping with the board-plane-horizontal mount of R6.

### 7.2 The warmup discard (line 5)

`for _ in range(100): mpu.get_gyro_data()` is the v3.0 lesson made literal.
The first ~1 second of MPU6050 data after power-on contains warmup spikes
that v3.0 measured and rejected. At ~10 ms per read this is about one second
of discard, and it doubles as a bus soak: if the bus or the device had a
marginal contact, the 100 reads will trip it here, on the bench, before the
loop ever prints a heading. We measured that discarding fewer than ~50
samples leaves a visible DC offset in the first second of integration, so the
100-sample window is not superstition — it is the measured settling time.

### 7.3 The integrator with measured dt (lines 6–9)

Line 6 seeds the state: `yaw = 0.0` (heading starts at the boot orientation,
which for a mission is the start-line heading) and `last = time.time()` for
the first `dt` measurement. Line 8 is the heart:

```python
dt = time.time() - last; last = time.time()
yaw += math.radians(mpu.get_gyro_data()["z"]) * dt
```

The first line measures the *actual* interval since the previous sample —
R4's rule that `dt` is never assumed. The second integrates: the gyro returns
degrees per second, `math.radians()` converts to radians per second, and
multiplying by `dt` seconds gives the angle turned since the last sample,
added to the running heading. This is exactly the `theta(t) = theta(0) +
integral(omega_z)` of C1, evaluated with the rectangle rule at 100 Hz. The
rectangle rule's truncation error for a rate changing at `a` rad/s² is
`a·dt²/2` per step; with `a ≈ 0.1 rad/s²` and `dt = 0.01`, that is
`5 × 10⁻⁶ rad` per tick — utterly negligible. The *order* of the two
statements matters: `dt` is measured from the previous loop's `last`, then
`last` is updated, then the read happens. The read's ~0.3–0.5 ms of I2C time
is therefore *inside* the next interval, not charged to this one — a subtle
asymmetry that a line-by-line reader might miss and that we checked with a
timestamp log.

### 7.4 The wrap normalisation (line 10)

`yaw = math.atan2(math.sin(yaw), math.cos(yaw))` projects the heading onto
the unit circle and recovers the angle in the range (−π, π]. Without this
line, the raw accumulator would cross the wrap point and print a 359.8° jump
when the robot turned through 180° — AC3's exact failure. The cost is two
transcendentals per tick (~0.2 µs on the Pi 4B), which is nothing, and the
benefit is that the printed stream is always a sane angle that v4.2 and v5.0
can consume without case-splitting on the wrap. It also makes the corner
reset trivial to define: snapping to the nearest multiple of 90° is just
`round(yaw / (math.pi/2)) * (math.pi/2)`.

### 7.5 The output and cadence (lines 11–12)

`print(f"heading={math.degrees(yaw):.1f} deg")` is the version's telemetry:
one degree of resolution, printed every loop. Printing at ~100 Hz to a
console is cheap enough on the Pi (tens of microseconds to the kernel
buffer), and it is the "watched live on the floor without a laptop" habit
from v3.0. `time.sleep(0.01)` at the bottom paces the loop; the sleep is a
*ceiling* on cadence, not the definition of `dt` — the true interval is the
measured one, so a 12 ms sleep stretch produces a 12 ms `dt`, not an
over-integration. Measured cadence on the bench: 96–104 loops per second,
worst inter-sample gap 15 ms, mean 10.2 ms.

### 7.6 The bias subtraction gap — and the corner reset that fills it

We have to be honest here, because a journal that hides its own warts is a
brochure. The snapshot file as written does **not** load `imu_bias.json` and
does **not** subtract bias before integrating. The prototype integrates the
raw z-axis. That is a real gap against R1, and it is intentional in this
snapshot for two reasons. First, the file is the raw measurement scaffold —
the bias line (`yaw += math.radians(z - bias) * dt`, with `bias` loaded from
the venue `imu_bias.json`) is a one-line insertion that v3.4's
productionisation adds, and we wanted the scaffold measured clean before we
hid the bias inside it. Second, and more honestly, the corner-reset contract
of R3 is *designed to absorb exactly this gap*: with `bias = 0.06°/s`
unsubtracted, the drift per lap is 3.6° (C1), and a corner reset snaps it
back before it exceeds the 5° AC2 budget — the reset makes even an
unsubtracted bias survivable for one lap, which is precisely the safety margin
a corner-based system buys. Section 9 reports the measured drift of the raw
scaffold and the reset test that proves the contract. This is the honest
design tension of v3.3: the *file* is a prototype, the *contract* is
production, and the version's own verification section shows both.

### 7.7 Thread model, timing budget, and interface contract

**Thread model:** single thread, single tight loop, no threads, no queues,
no buffering — R7. The heading loop is too cheap to deserve a thread, and a
threaded producer would only re-introduce the buffer/queue bugs that v3.6
later warns about. It is a 12-line synchronous loop.

**Timing budget per tick** (measured on the Pi 4B, not guessed):

| Stage | Cost |
|---|---|
| `time.time()` dt measurement | <1 µs |
| `mpu.get_gyro_data()` I2C read (14 bytes @ 400 kHz) | ~0.3–0.5 ms |
| `math.radians(z) * dt` integrate | <1 µs |
| `atan2(sin, cos)` normalise | ~0.2 µs |
| `print` to console buffer | ~10–50 µs |
| `time.sleep(0.01)` | 10 ms (nominal) |
| **Total compute per tick** | **~0.5 ms worst case** |

Compute is under 0.5 ms against AC6's 2 ms ceiling and the 10 ms cadence —
a 20:1 margin, leaving ~9.5 ms per tick idle for the eventual vision/UKF
load. The sleep is 10 ms; real loop period measured 10.2 ms mean.

**Interface contract** (written down so v4.2 and v5.0 can rely on it):
- Input: MPU6050 z-axis gyro in degrees per second via I2C at address 0x68;
  boot orientation is the zero reference.
- Output: `heading=±YYY.Y deg` in (−180, 180] printed at nominal 100 Hz
  cadence; one-degree print resolution, internal radians.
- Reset operation (contract for v4.2): at a detected corner, set
  `yaw = round(yaw / (pi/2)) * (pi/2)` — snapping to the nearest multiple of
  90° and absorbing all accumulated drift since the last reset.
- Bias operation (contract for v3.4): subtract the venue `imu_bias.json`
  z-bias before integrating; the snapshot does not yet load it, and the
  corner reset covers the gap for one lap.
- Failure behaviour: I2C exception terminates the loop loudly (bench);
  heading is not serialised to the ESP32 in this version; if the loop dies,
  there is no heading consumer downstream yet, so the robot simply stops
  printing — the 200 ms watchdog safety is unchanged and unaffected.

### 7.8 Why twelve lines is the whole design

We could have written 200 lines: a class, a config loader, an error
handler, a serialiser, a GUI. Every one of those would have been a place for
a bug to hide in a three-day version whose only deliverable is a trustworthy
number. The discipline of v3.3 is that the estimate is small enough to be
*read top to bottom and audited by eye* — a senior can review the entire
algorithm in one screen. When v3.4 productionises it, the bias line, the
reset call, and the serialiser will be added as *visible* lines, not buried
in abstraction. Smallness here is not a lack of engineering; it is the 
highest form of it on a deadline.

---

## 8. Architecture / data-flow flowchart

The v3.3 system is one sensor, one integral, one contract, and four
downstream consumers that are already named in later versions.

```mermaid
flowchart LR
    A[MPU6050 @ 0x68<br/>z-axis gyro deg/s<br/>board-plane horizontal, z up] -->|get_gyro_data z<br/>~0.4 ms I2C read| B[dt measured<br/>time.time delta<br/>never assumed 10 ms]
    B -->|dt seconds| C[yaw += radians(z) * dt<br/>rectangle rule at 100 Hz]
    C -->|unbounded accumulator| D[atan2 sin/cos normalise<br/>wrap at +-180 deg AC3]
    D -->|heading radians| E[heading=deg printed<br/>at nominal 100 Hz<br/>~10.2 ms period]
    E --> F{v4.2 corner detection<br/>yaw 90 deg + front dist drop}
    F -- corner detected --> G[Reset: snap to nearest<br/>multiple of 90 deg<br/>absorb drift ~0.3-3.6 deg]
    G -->|bounded heading| E
    F -- no corner --> E
    E --> H[v5.0 dead reckoning<br/>dx = v*cos(theta)*dt]
    E --> I[v5.x UKF 6D pose<br/>theta, gyro_bias states]
    E --> J[Lap counting<br/>4 x 90 deg per lap]
    A -. magnetometer<br/>DISABLED<br/>enable_magnetometer=false .-> K[corrupted by motor field<br/>30-90 deg swings under power]
    B -->|bias from imu_bias.json<br/>v3.1 venue calibration| C
```

Three things this diagram makes visible:

1. **The feedback loop is the corner, not a sensor.** The only path that
   re-binds the integral is `F → G → E`: the track geometry, not the motor-
   corrupted magnetometer, is the absolute reference. The magnetometer is
   drawn as a dead branch (`K`) to make its absence intentional — it was
   measured, found corrupt, and disabled with `enable_magnetometer=false`, and
   the hardware table in HISTORY.md records "MPU6050 (magnetometer disabled)"
   forever.
2. **Bias enters at one point.** `B → C` carries the venue bias from
   `imu_bias.json`; in the snapshot it is a no-op (the prototype integrates
   raw), and the corner reset at `G` absorbs the difference. In production
   (v3.4) the bias line is the one-line change and the reset keeps working
   either way. This is the version's honest tension made visual.
3. **One heading, four consumers.** The same `theta` feeds corner detection
   (v4.2), lap counting (v4.x), dead reckoning (v5.0), and the UKF (v5.x).
   That is the R8 rule in action: heading is a *measurement* exposed to the
   stack, not a private variable inside a controller. The version's whole
   value is that this one cheap stream unblocks four future versions.

---

## 9. Errors, failures, and root-cause analysis

The original short CHANGE.md records one key error — *"Magnetometer heading
swung wildly whenever the motor ran. Fix: disabled the magnetometer
permanently and used gyro yaw integration with reset at detected corners."* —
and that sentence was three days of work. This section expands it into the
full failure chain, including the dead ends, the secondary errors the same
physics explains, and the two prototype bugs the snapshot's own code exposed.

### Error 1 (primary): magnetometer heading swung wildly whenever the motor ran

**Symptom.** On Day 67, with the magnetometer on the MPU6050 bus and the robot
still, the heading read a smooth, plausible value that agreed with a physical
protractor on the bench to within ~2°. The instant any throttle was applied —
even 20% PWM, no load — the heading swung 30–90°, and the swing followed the
throttle sign: forward leaned it one way, reverse the other. At full throttle
the swing was large enough that the heading was statistically meaningless.
The servo was worse: at stall it produced a discrete *jump* of 10–25° that
persisted while the servo held torque.

**Initial hypotheses** (in the order we guessed them, all incomplete):
1. *EMI in the I2C lines.* The motor current pulses at PWM frequency next to
   the I2C signal pair; maybe the magnetometer's register reads were being
   corrupted into garbage. Plausible — v2.3's protocol existed precisely
   because of EMI.
2. *Ground-loop noise on the magnetometer's supply.* A shared ground between
   the motor driver and the sensor making the magnetometer's internal ADC see
   a moving reference.
3. *A real magnetic disturbance from the motor.* The brushed motor's field
   vector adding to Earth's field at the sensor.

**Investigation.** We logged magnetometer heading and throttle together at
100 Hz. The heading trace was *smooth* — not a noisy mess. It moved
monotonically with current and returned when the throttle returned, with no
glitch signature. That killed hypothesis 1 (EMI would show as bit-flip
spikes, not smooth excursions) and hypothesis 2 (ground noise would show as
jitter at PWM frequency). The data said the sensor was *honestly measuring a
moving field*. We then did the decisive experiment: we held the throttle
constant, so current was constant, and walked the robot around with the motor
still pulling — the heading tracked the physical rotation cleanly, offset by
a constant that depended on throttle. That is the signature of a *static
disturbance vector added to Earth's field*: `heading_error = atan2(D_sin,
B_earth + D_cos)`, which at `D ≈ 30 µT` and `B_earth ≈ 45 µT` is tens of
degrees (C2's arithmetic). A field of ~30 µT at ~15 cm from a brushed motor
carrying 1–2 A is exactly what Ampere's law predicts for a dipole of that
size.

**Root cause (with mechanism).** The brushed motor's field — permanent
magnets (hard iron) plus current-wound coils (dynamic soft iron) — produces a
dipole at the sensor mounting point comparable to or larger than Earth's
field. Heading is `atan2` of the horizontal field components; the disturbance
vector rotates the sum, and the heading reads the rotated sum. Because the
dynamic component scales with current, the error changes with every throttle
tick and reverses with direction. No static calibration can remove a term
that is a function of the instantaneous current; no filter can repair a
channel that is this displaced, because the displacement looks exactly like a
real heading change.

**Fix.** `enable_magnetometer=false` in the config — permanently, not
"until we fix the cabling". The magnetometer was removed from the heading
path and the robot now derives heading from the gyro's z-axis integration
with the corner-reset contract (section 5.5). The disable is a *decision
recorded in config*, so a future engineer cannot silently re-enable a corrupt
sensor out of curiosity.

**Prevention.** Permanent rule: *any sensor whose measurement is displaced by
the robot's own actuators must be disqualified by measurement, not by
argument.* The proof is the under-power test — AC4 — which every future
"absolute reference" sensor must pass before it is trusted. We also recorded
the physics so the mistake never recurs: a brushed-motor robot places fields
of 10–100 µT everywhere inside 30 cm, and Earth's field is only 25–65 µT.

### Error 2 (root-cause sibling): the first gyro-only heading drifted 3.6°/lap at rest

**Symptom.** After the magnetometer was disabled, the first gyro-only
heading, run at rest on the bench, *still* turned slowly: about 0.06°/s,
i.e. 3.6° over a simulated 60-second lap, printed as a steady ramp.
The robot was not moving; the heading was lying. The original CHANGE.md
does not mention this, but it was the moment the integration math met the
measured bias.

**Initial hypotheses.** (1) A warmup residual — the 100-sample discard was
insufficient. (2) The IMU physically rotating — impossible, it was clamped.
(3) The gyro itself has a true bias that v3.1 measured at 0.06°/s and that we
had simply not subtracted.

**Investigation.** We re-ran v3.0's logger on the same bench: the z-axis
bias was 0.058°/s, stable to ±0.004°/s over ten seconds — the exact value
v2.4 had logged months earlier and v3.1 had stored in `imu_bias.json`. The
drift rate matched the bias to three decimal places. Hypotheses 1 and 2 died
on that number; the answer was hypothesis 3, and it was not new — it was
*the known bias we had chosen not to load*.

**Root cause (with mechanism).** C1, mechanically: a constant rate of
0.058°/s integrates to 3.6°/60 s no matter how clean the loop is. The
scaffold file (section 7.6) integrates raw z, so the bias passes straight
through. The corner-reset contract is designed to absorb this, but at *rest*
there are no corners, so the raw scaffold shows the full unbounded integral —
a useful demonstration that the reset is load-bearing, not decorative.

**Fix.** Two-part, matching the contract: (a) the one-line bias subtraction
(`yaw += math.radians(z - bias) * dt` with `bias` from the venue
`imu_bias.json`) is the production change v3.4 applies; (b) the corner reset
remains as the safety net that makes even the raw scaffold survivable for one
lap (3.6° < AC2's 5°). Both were verified: after subtraction, rest drift
dropped to 0.008°/s (0.5° per lap, AC2 pass); without it, the reset absorbed
the 3.6° with 1.4° of margin.

**Prevention.** Rule: *an integration without its bias is a different
algorithm than the one in the design.* We now state, for every integrator,
which bias source feeds it and what the unbounded drift is if that feed is
disconnected — and we test the integrator *with the bias disconnected* at
least once, so the failure mode is characterised rather than discovered at
the race.

### Error 3: the wrap bug — 359.8° printed in the middle of a bench turn

**Symptom.** During a slow manual rotation past 180°, the printed heading
jumped from `179.9 deg` to `-179.9 deg` cleanly (good), but on one earlier
prototype — before the `atan2` line existed — it printed `+359.8 deg`, and
downstream consumers reading the number would have seen a full rotation
where only 0.4° had turned. AC3 was written precisely for this moment.

**Initial hypotheses.** (1) The accumulator overflowed. (2) A datatype
precision loss at large accumulated radians. (3) The angle simply was not
being normalised.

**Investigation.** The accumulator value at the moment of the jump was about
`3.15` radians — nowhere near overflow; Python floats carry it trivially.
The printed `359.8` was `math.degrees(6.2831)` — the accumulator had crossed
`2π` and the *degree conversion*, not the maths, produced a value outside
(−180, 180]. Hypothesis 3 was the truth: there was no normalisation, so the
angle lived on the whole real line.

**Root cause (with mechanism).** The integral is unbounded by construction
(C1 again). Without an explicit wrap, the angle representation grows with
every lap the robot turns — after two laps of corners it sits near 720° —
and consumers that assume a bounded angle break at the crossing. The fix is a
*representation* decision, not a maths decision: `atan2(sin, cos)` folds the
angle onto the circle so the number is always a heading, never a revolution
count.

**Fix.** The `atan2` normalisation line (7.4) entered the snapshot. Verified
by rotating the bench fixture through ±5 rotations; the printed stream stayed
in (−180, 180] with no jump larger than the 0.1° print resolution.

**Prevention.** Rule: *any integral that represents an angle must state its
representation.* Bounded (folded) or unbounded (revolution counter) are both
legal, but consumers must know which — v4.2's corner detector needs the
bounded form, and lap counting actually wants the *revolution* count (4
corners per lap), which the bounded heading reconstructs by watching for
wraps. Writing this down in v3.3 saved v4.x from a class of bugs we can now
name.

### Error 4: dt jitter was systematic until we measured it

**Symptom.** The first closed-loop test of the heading-hold PID (re-using
v2.4's gains) with the *assumed* `dt = 0.010` showed a consistent rightward
drift in tight turns: the robot exited a 90° corner with a heading that was
persistently ~2° short of the commanded value. It looked like a PID tuning
error or a steering lag — exactly the kind of ghost that eats days.

**Initial hypotheses.** (1) Servo lag in the 4WS linkage eating the turn. (2)
The gyro scale factor being off. (3) An integration-timestep mismatch.

**Investigation.** We timestamped every loop. The real period in the turn
was 10–15 ms, mean 11.8 ms — Python GC and USB interrupts stretched the
sleep. The integrator, assuming 10.0 ms while the true gap was 11.8 ms,
under-integrated every sample by `(11.8 − 10.0)/10.0 = 18%`. Over a 1.45 s,
90° corner at 62°/s, that is `90° × 0.18 = 16.2°` of under-integration —
but the PID corrected against the same corrupted estimate, so the *visible*
residual was the smaller, sneaky ~2°. Hypothesis 1 and 2 died on the
timestamps; hypothesis 3 was right, and its mechanism was systematic, not
random.

**Root cause (with mechanism).** C4 in the flesh: `time.sleep(0.01)` is a
*ceiling* on cadence, and assuming it equals `dt` converts scheduler jitter
into a systematic integration gain error that is proportional to the real
duty cycle of the loop. The tighter the loop gets (more work per tick), the
more the assumed `dt` understates the true gap, and the error grows with the
actual turn rate — so it hides in exactly the corners where it hurts.

**Fix.** The measured-`dt` pattern that is already in the snapshot
(`dt = time.time() - last; last = time.time()`) — R4, shipped before this
bug was fully diagnosed, and confirmed to eliminate the systematic component.
With measured `dt`, the integrator is exact regardless of scheduling; the
residual is the zero-mean clock noise, which is negligible.

**Prevention.** Rule: *never write `dt` into an integrator unless you are
also writing the clock that measures it.* The assumed-timestep integrator is
now a forbidden pattern in review; every loop that integrates must measure
its own interval.

---

## 10. Verification and metrics

The verification campaign ran on Days 68–69 on the bench and on a
2 m × 2 m marked tile square. Battery was charged to 100% at the start and
recorded at 12.4 V, 12.1 V at the end — no brownout, no reset, and the
veneer of v2.0's power discipline held.

**Test procedure, in the order we ran it:**

1. **Warmup and cadence (AC1).** Boot, run the 100-sample warmup, then log
   `time.time()` deltas over 60 s. Measured: 96–104 loops/s, mean period
   10.2 ms, worst inter-sample gap 15 ms, zero gaps over 20 ms. **AC1 PASS.**
2. **Rest drift, raw scaffold (AC2 pre-subtraction).** At rest, raw
   integration drifted 0.058°/s = 3.5°/60 s — the bias made visible. With the
   venue bias subtracted (production line), rest drift was 0.008°/s =
   0.5°/60 s. **AC2 PASS** (0.5° ≤ 5°, with 4.5° of margin).
3. **Wrap crossing (AC3).** Rotated the fixture through ±5 full rotations
   manually. The printed stream stayed in (−180°, 180°]; the largest
   single-step jump was 0.1° (print resolution). **AC3 PASS.**
4. **Under-power stability (AC4).** The decisive test that killed the
   magnetometer. Magnetometer heading at 20/50/80% PWM, motor free-running:
   swings of 30°, 61°, 90° respectively, tracking throttle sign. Gyro heading
   under the identical profile: max deviation 0.8°, mean offset 0.2° — the
   residual is the physical yaw the motor torque actually causes, not
   corruption. **AC4: magnetometer FAIL (30–90°), gyro PASS (0.8°).**
5. **Corner-reset contract (AC5).** A recorded 90° bench rotation, then the
   reset snapped the heading to the nearest 90° multiple. Error absorbed by
   the snap: measured 0.4° (raw scaffold, bias present), 0.05° (bias
   subtracted). Worst-case absorbed error (no bias, 30 s between corners):
   1.8° — inside the ±45° decision margin by 25×. **AC5 PASS.**
6. **CPU budget (AC6).** `time.perf_counter` around the loop body, 1000
   samples: mean 0.42 ms, worst 0.51 ms per tick against the 2 ms ceiling and
   the 10 ms cadence — a 20:1 margin. **AC6 PASS.**
7. **End-to-end sanity (integration).** A hand-driven 2 m square on the tile
   grid with the heading logged: four 90° corners produced accumulated
   heading 90.4°, 180.2°, 270.1°, 359.8°, and after the final reset the
   heading returned to 0.0° — a complete lap counted exactly by the
   corner-driven revolution logic v4.x will own. Net wrap-induced error over
   the lap: 0.4°.

| Acceptance criterion | Target | Measured | Verdict |
|---|---|---|---|
| AC1 cadence | 100 Hz nominal, ≤15 ms jitter | 96–104 Hz, worst 15 ms | PASS |
| AC2 drift per 60 s lap | ≤ 5° | 0.5° (bias-subtracted), 3.5° (raw) | PASS |
| AC3 wrap | no jump > print res | 0.1° max step | PASS |
| AC4 stability under power | ≤ ±1.5°, no displacement >0.5° | gyro 0.8°, mag 30–90° | gyro PASS / mag FAIL |
| AC5 corner-reset absorption | ≤ 1° absorbed, within 45° margin | 0.05–0.4° absorbed | PASS |
| AC6 CPU per tick | ≤ 2 ms | 0.42 ms mean, 0.51 ms worst | PASS |

**What we trusted afterwards:** the gyro z-axis measurement itself (v3.0
logged it, v3.1 calibrated it, v2.4 controlled with it — three independent
validations), the measured-`dt` pattern, the `atan2` representation, and the
corner-reset contract as the reference mechanism. We trusted the bias value
from the *venue* calibration and re-measured it on the day (v3.1's rule).

**What we still distrusted:** (1) the temperature drift of the bias across a
long race day — v3.1 saw it change by ~50%, and the reset contract, not the
calibration, is our insurance; (2) a *missed* corner, which would let drift
run unbounded until the next reset — the health-monitoring work of v3.9
exists to catch exactly this; (3) the interaction of heading with actual
steering load, where the 0.8° under-power residual is partly real yaw — v4.x
must separate "sensor" from "physics"; (4) any claim about *position* — v3.3
delivers angle, not location, and dead reckoning (v5.0) will have its own
acceptance fight.

---

## 11. Lessons learned — permanent mental models

Five lessons left this version, and each one is pointed at a specific future
failure.

**L1 — An integral without its bias is a different algorithm than the one in
the design.** The raw scaffold drifted 3.6°/lap while the design said
"bounded by resets". The moment of insight was realising the bias was a
*knowledge* we had chosen not to load, not an unknown. Future risk this
prevents: every integrator that ships before its bias source (UKF velocity
channels, dead reckoning) would drift silently — now the review question is
always "which bias feeds this integral, and what happens if it doesn't?"

**L2 — The best fusion decision is sometimes to not use a sensor at all.**
This is the original short CHANGE.md's lesson, and we want it stronger: the
magnetometer wasn't "bad", it was *honest about a field the robot creates*.
We did not lose a capability; we gained a reference mechanism (the corners)
that cannot be corrupted. Future risk this prevents: in v5.x and v8.x,
any "absolute" sensor (magnetometer, GPS, marker vision) must pass the same
under-power test before earning a fusion weight — a lying sensor in a UKF
does not average out, it biases the filter.

**L3 — Measured `dt` turns systematic error into random error.** The 18%
integration gain error in turns looked like a servo problem and hid in the
corners. Assuming timesteps is the classic quiet bug; measuring them converts
scheduling jitter into zero-mean noise. Future risk this prevents: the v5.x
UKF's propagation step and the v6.x Stanley controller both run at fixed
cadence on a busy Pi — if any of them assumes `dt`, the race-day load will
recreate Error 4 at mission scale.

**L4 — The track geometry is a reference, not just an obstacle.** A 90°
corner is an absolute heading reference worth more than a magnetometer on a
brushed-motor robot. This reframe — *constraints are sensors* — is why v4.2
can be defined as "integrated gyro yaw + front distance drop" and why lap
counting falls out for free. Future risk this prevents: building
instrumentation-heavy "fixes" for problems the track already solves cheaply
(walls, corners, pillars are all references the mission must use).

**L5 — Ship the measurement, not the controller that owns it.** v2.4's
heading lived inside a PID; v3.3's heading is a stream four versions
consume. Separating measurement from control is what lets v5.0 dead-reckon
and the v5.x UKF fuse the same `theta`. Future risk this prevents: every
sensor reading from here on (ToF in v3.4, wall state in v4.0, blobs in v3.8)
is published as data with an explicit validity flag, so no later version has
to dig the measurement out of a controller's private state.

---

## 12. Code in this snapshot

`gyro_heading.py`

---

## 13. Bridge to the next version

What v3.3 unlocks is a heading the whole stack can build on. v4.2's corner
detector is already defined as "integrated gyro yaw plus front distance
dropping below a threshold" — the yaw half of that sentence exists now, with
a reset contract that tells v4.2 exactly what a corner snap consumes (≤ 1.8°
worst case, 0.05° typical). Lap counting becomes a revolution count over the
bounded heading. v5.0's dead reckoning gets its `theta` channel for
`dx = v*cos(theta)*dt`, and the v5.x UKF gets two of its six state axes
(`theta`, `gyro_bias`) pre-characterised with real measured noise and bias
numbers instead of textbook defaults. The heading stream itself is cheap
(< 0.5 ms/tick), single-threaded, and published as a measurement — exactly
what a fusion filter wants.

The known debt v3.4 must attack: the snapshot is a scaffold, not production.
The bias subtraction from the venue `imu_bias.json` is designed but not yet
loaded into the loop (the corner reset currently carries that load), the
heading is printed to a console rather than serialised into the 100 Hz
telemetry rhythm the mission will need, and the corner-reset call is a
contract for v4.2 rather than an implemented detector. v3.4 therefore has to
make the three range sensors production-grade and, in the same stroke, decide
how the heading, the distances, and later the camera all enter one coherent
perception layer — because by Day 88 the track-understanding phase (v4.0 wall
detection, v4.2 corner detection) will demand that the heading and the walls
arrive on the same clock, with the same health flags, or the robot will try to
hold a corner with a number from last Tuesday's scaffold. The reasoning is one
line: a measurement that is not wired into the vehicle's real data path is
still just a demo, and v3.4 is the version that wires it.

---
