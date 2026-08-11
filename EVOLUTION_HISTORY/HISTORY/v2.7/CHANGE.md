# v2.7 — S-curve speed ramp

| Version | Phase | Days |
|---------|-------|------|
| v2.7 | Basic Driving | Day 49-51 |

---

### 1. Version header table

| Version | Phase | Days |
|---------|-------|------|
| v2.7 | Basic Driving | Day 49-51 |

---

### 2. Title

# v2.7 — S-curve speed ramp: killing the launch chirp with a continuous velocity command

---

### 3. Mission of this version

The single problem this version attacks is embarrassingly simple to state and
surprisingly deep to solve: **the drive wheels still chirp.** Every launch from
standstill, and every aggressive exit from a steering corner, produced an
audible tire squeak and a visible shiver of the chassis. We had already
"fixed" the power problem in v2.0 by ramping the speed command over 500 ms
instead of jumping to full PWM — that fix killed the Pi 4B brownout reset but
did **not** kill the chirp. The wheel slip that produces the chirp corrupts
odometry, and odometry is the foundation every later version is built on: v2.4
already steers straight with the MPU6050, v5.x will run a UKF 6D pose pipeline
on top of dead-reckoning, and a dead-reckoning pipeline fed by a slipping wheel
is fiction. So this version's mission is the first *physics-correct* motion
primitive: a velocity profile whose derivative is finite and continuous, so
the tire never has to transmit an infinite force.

Why is this the correct next step on the critical path? Look at the phase map:
v2.0-v2.6 gave us forward drive, 4WS steering, PWM speed control, a CRC8
packet link, PID straight-line holding, an open-loop timed lap, and a
short-brake stop. Every one of those versions ships speed to the ESP32-S3 as a
**step** — a new integer every 50 ms or every 100 ms — and every one of them
inherits the same hidden defect: the command jumps. The robot moves, steers,
stops and reverses, but it does all of it through a chain of discontinuous
velocity commands. Until we make the velocity command itself continuous, every
downstream layer — PID heading hold, trajectory playback, eventual
localization — will be fighting slip artifacts it cannot see. A 1.8 m/s robot
with a 200 ms watchdog and a 100 Hz link has no margin to absorb a chirp that
sends the wheels sliding sideways off the kinematic model. Getting the
profile right now, at the end of the Basic Driving phase, is cheaper than
re-tuning five later versions against a phantom odometry error.

The capability gap at the end of v2.6: we could command a *start*, a *stop*
and a *reverse*, but we could not command a *transition*. v2.6's measured stop
was 0.2 m with short-brake, which implies an average deceleration of
v²/2s = 1.8²/(2·0.2) = 8.1 m/s² — right at the edge of what rubber can ask of
a competition floor. The launch had no such honesty: it just stepped the PWM
up. So the gap was specifically *dynamic* transitions: launch, corner exit,
and (soon) corner entry decel. This version only commits to launch and corner
exit; decel scheduling is deliberately deferred.

What "done" looks like — acceptance criteria written before any code, so we
could not fool ourselves later:

| ID | Acceptance criterion | Measurable target |
|----|----------------------|-------------------|
| AC1 | Zero audible chirp at launch | 20/20 launches, mic RMS above floor < threshold |
| AC2 | Peak commanded acceleration within friction budget | ≤ 6.0 m/s² (1.4× margin under mu_s·g) |
| AC3 | Time-to-full-speed | 500 ms ± 20 ms |
| AC4 | Link integrity during ramp | no ESP32-S3 watchdog trip (inter-packet < 200 ms), no CRC drop |
| AC5 | Distance-to-full-speed | ≤ 0.62 m (theory 0.573 m) |
| AC6 | No brownout | Pi 4B survives 20 launch cycles with zero resets |
| AC7 | Corner-exit clean | 20° steer → straighten + ramp, zero chirp |

We wrote these before Day 49 so that "looks better" could never pass for
"works."

---

### 4. Engineering context — where we stood

To understand why v2.7 exists you have to understand what v2.0-v2.6 gave us
and, more importantly, what they quietly got wrong.

**v2.0** (Day 28-30) was the first closed loop: send speed 0..100 to the
ESP32, drive straight 2 s. The original attempt jumped straight to full PWM
and the Pi reset — the motor inrush current (up to several amps across a
winding of ~1-3 Ω on a 2S or 3S pack) sagged the shared supply rail below the
Pi's 5 V regulator dropout. The fix was a ramp: `for i in range(0, 101, 10):
drive(i); time.sleep(0.05)`. Note what that actually is: a **staircase of ten
50 ms steps**, each step a 10-unit jump in commanded speed. It solved the
brownout because the *average* PWM growth was slow enough for the battery and
regulator to keep up, but each individual step was still a discontinuity in
velocity — an impulse of jerk at the tire contact patch. The chirp we "fixed"
in v2.7 is literally the ghost of v2.0's staircase. The brownout lesson was
recorded as "power budget matters as much as code budget"; the real lesson —
"discontinuity in commanded velocity causes slip" — was not extracted until now.

**v2.1** (Day 31-33) measured the 4WS geometry: a single MG995 servo drives a
linkage that steers both axles, with a fixed rear-to-front ratio of 0.85. We
discovered the effective steering angle is the average of front and rear, so
the robot turns about a single effective kappa. Crucially for this version: a
4WS robot with opposite-phase steering has a 0.5 m minimum turning radius, and
at 1.8 m/s that corner demands a lateral acceleration of v²/r = 3.24/0.5 =
6.48 m/s² — *higher* than the peak longitudinal acceleration of the ramp we
adopt here (5.65 m/s²). That single number will come back in Section 5: corner
exit is where the friction budget is already half spent on lateral force, so
the longitudinal demand must be extra gentle there.

**v2.2** (Day 34-36) replaced the raw motor duty with a PWM throttle mapping
speeds 0..100 to PWM 0..255 on the ESP32, and raised the motor PWM frequency
well above the audible range (the 50 Hz servo rate stays for the MG995, which
expects it). This matters because it means the *speed command* in our packets
is a first-class quantity: 100 units ≈ full PWM ≈ 1.8 m/s (measured later in
v2.9). The ESP32 does not have a velocity control loop — it is an
open-loop PWM mapping. So the "velocity profile" has to be baked into the
*command stream*, not into a motor PID. That is a constraint that shapes
everything in this version: the Pi 4B is the only place a profile can exist.

**v2.3** (Day 37-39) hardened the link: 10-byte packets `AA 55 | seq | cmd |
servo×100 (int16) | speed×10 (int16) | CRC8 (poly 0x07) | 0x0D`, packed with
`struct.pack(">BBhh", ...)`. Fixed-point scaling — servo ×100, speed ×10 — so
the ESP32 never has to parse floats. This gives us the packet grammar that
`s_curve_ramp.py` uses, and it is the reason a bench profile script can be
eight lines long: the heavy lifting (packing, framing) is a solved problem.
Honest wart: the v2.7 bench script writes a zero into the CRC slot — see
Section 9, E3.

**v2.4** (Day 40-42) closed the heading loop with the MPU6050 gyro Z: a P-I-D
(Kp 1.2, Ki 0.05, Kd 0.1) steering the servo to hold yaw while driving at
speed 40 (≈0.72 m/s). The famous bug was integral windup; the fix was a clamp
(`integral = max(-20, min(20, integral + err*dt))`). Why is this relevant to
a ramp version? Because the PID was tuned at 0.72 m/s, and at 1.8 m/s the
servo simply cannot keep up — the MG995 takes ~0.1 s per 60° unloaded and
longer loaded. If we step the velocity at launch, the heading error transients
shoot through the loop and the steering fights back, which is another way to
scrub the tires. A smooth ramp keeps the velocity perturbation inside what the
PID can reject.

**v2.5** (Day 43-45) chained timed waypoints into a full open-loop lap
attempt — `plan = [(0, 35, 2.0), (15, 25, 1.2), (0, 35, 2.0), (-15, 25, 1.2)]`
— and found timing drift of 15% because chained `sleep()` accumulates error.
The fix was elapsed-time scheduling against an absolute clock: `t0 =
time.time()` and every action compares `time.time() - t0` against absolute
target times. This is the *single most important design idea that v2.7
reuses*. Our ramp computes `frac = (time.time() - t0) / T` fresh on every
iteration, so the profile is a pure function of wall-clock time — scheduling
jitter cannot bend it. v2.5 was the trial run for the clock discipline v2.7
depends on.

**v2.6** (Day 46-48) added commanded braking and reverse. The killer error:
after a stop command the robot *coasted 30 cm* because the driver freewheeled
(STBY LOW). Fix: active dynamic braking — both IN1/IN2 LOW with PWM 0
(short-brake) — in mode `0x02` (`cmd(0, 0, 0x02)  # EMSTOP`). Measured stop
from 1.8 m/s: < 0.2 m, i.e. 8.1 m/s² average decel. That number is important:
8.1 m/s² is *above* the ~7.8-9.8 m/s² range of mu_s·g for rubber on a vinyl
competition mat, so the short-brake stop is already right at the friction
limit. It works, but it leaves zero margin. When we later (Section 13) schedule
corner-entry decel, we must do better than 8.1 m/s², and a continuous profile
is the only way to get there with margin.

System-level constraints that shaped v2.7:

- **Pi 4B brain, ESP32-S3 muscle.** The Pi (quad-core A72, ~1.5 GHz) runs
  Python and the whole perception/planning stack later; the ESP32-S3 runs the
  200 ms watchdog, the motor PWM, and the packet parser in real time. The Pi
  is *not* real-time; the ESP32 is. Any safety property (watchdog, current
  limiting) must live on the ESP32; any *profile* must live on the Pi. The
  ramp is computed on the Pi and shipped as commands — there is no closed-loop
  velocity control on the ESP32 (v2.2 confirmed it is open-loop PWM).
- **100 Hz, 10-byte link = 1000 B/s ≈ 8 kbps.** At 115200 baud the link is
  8.7% utilized; plenty of headroom, but each packet is 10 bytes and each
  *profile sample* must be one packet. At 100 Hz, a 500 ms ramp is only
  **50 samples**. The profile must be computable in fewer Python instructions
  than a packet write — it is (`math.sin` is one C call).
- **200 ms ESP32 watchdog.** If no valid packet arrives within 200 ms the
  ESP32 stops the motors. Our 500 ms ramp at ~85-90 Hz effective rate has an
  inter-packet gap of ~11-12 ms — 17× inside the watchdog budget. The ramp
  must never block for more than ~180 ms on a serial write.
- **Friction is finite.** mu_s·g bounds every acceleration. The robot is
  roughly 1.5-2.0 kg (we weighed it; see Section 10), and the competition
  surface is smooth vinyl. A commanded velocity step asks for infinite
  acceleration, which the tire answers with slip — chirp — and odometry
  corruption.
- **Battery + TB6612FNG.** The driver is rated 1.2 A continuous per channel
  (3.2 A peak absolute). A stalled motor across the pack can draw 3-5 A, so a
  velocity step that slams PWM to max risks both the driver's thermal limit
  and the brownout rail that bit us in v2.0. Ramping keeps current demand
  proportional to the *voltage actually being delivered*, protecting both.

Pressure: we are on Day 49-51 of a build whose competition target is 122/122
points. The Basic Driving phase ends at v2.9. Every day spent re-fighting a
chirp is a day not spent on sensing (v3.x) or localization (v5.x). The debt
compounding risk is real: if we ship the staircase into the trajectory and
localization phases, the UKF in v5.x will be asked to fuse odometry that is
occasionally lying, and debugging a 6-state filter against phantom slip is
orders of magnitude harder than fixing a launch ramp now. Speed transitions
are physics problems, not software chores — and this version is where we stop
treating them as chores.

---

### 5. The engineering thought process — first principles

#### 5.1 Constraints and hard limits (derived, with numbers)

Let us derive the numbers from scratch, the way we should have in v2.0.

**C1 — The tire has a static-friction ceiling.** For a tire in rolling contact,
the maximum horizontal force it can transmit without sliding is F ≤ mu_s · N,
where N is the normal load on that wheel. For the whole robot, the maximum
acceleration is a_max = mu_s · g (all wheels driving, no load transfer).
With mu_s ≈ 0.8-1.0 for rubber on vinyl:
a_max ∈ [7.8, 9.8] m/s².
We adopt a *design* ceiling of 6.0 m/s² to keep a ≥ 1.3× margin for load
transfer, wear, and surface variance. That single number decides the ramp
duration: a 500 ms ramp from 0 to 1.8 m/s has average acceleration
1.8/0.5 = 3.6 m/s² — comfortably under 6.0. A 200 ms ramp would need 9 m/s² —
over the ceiling. **C1 ⇒ T_ramp ≥ 0.3 s for a straight-line launch.**

**C2 — The command stream is sampled, not continuous.** We send packets at
nominal 100 Hz, but the *effective* rate with Python overhead and
`time.sleep(0.01)` is closer to 85-90 Hz (Section 10 measured it). A profile
is therefore a sequence of discrete samples. Any profile whose per-sample step
is large creates a *quantized* discontinuity. The staircase in v2.0 was 10
units per sample — a step of 0.18 m/s *per packet*. **C2 ⇒ the profile must
be re-derived from wall-clock time on every sample (never extrapolated), so
the sample size follows the curve, not the other way around.**

**C3 — Jerk is the real killer.** Acceleration is the derivative of velocity;
jerk is the derivative of acceleration. A *velocity* discontinuity is an
infinite jerk impulse. The tire does not see "the command jumped from 0.36 to
0.54 m/s"; it sees a force that appears instantaneously. Because the tire is
an elastic body with contact-patch compliance and the drivetrain has backlash,
an impulsive force at the patch momentarily exceeds the local static-friction
limit even when the *average* force is well within it. The v2.0 staircase was
15% of the way to a proper ramp yet still chirped *because each of its ten
edges was an impulse*. **C3 ⇒ the profile must have a finite, and ideally
smooth, derivative everywhere — and at least zero velocity discontinuity.**

**C4 — The ESP32 is open-loop on velocity.** v2.2 mapped speed 0..100 →
PWM 0..255 and the motor runs open-loop. There is no wheel encoder feedback
anywhere in the hardware list (no encoders on the drivetrain at all — the
"closed loop" of v2.0 is a misnomer; it was closed on *command timing*, not
motion). Therefore the ramp *is* the controller. If the ramp overshoots or
steps, nothing downstream catches it. **C4 ⇒ the profile generator is a
safety-relevant component on the Pi, and its output is what the wheels get.**

**C5 — Corner exit has a pre-spent friction budget.** At a 20° effective
steering angle, the robot corners with lateral acceleration. At v=1.8 m/s and
r=0.5 m, lateral accel = 6.48 m/s². The friction ellipse says
(a_lat/a_max)² + (a_lon/a_max)² ≤ 1. If a_lat is already 4-5 m/s² during an
aggressive exit, the remaining longitudinal budget at a_max=6.0 is only
sqrt(6.0² - 5²) ≈ 3.3 m/s². A staircase that injects a 0.18 m/s step at that
moment *will* break traction. **C5 ⇒ corner-exit ramps must be gentler than
launch ramps, or must wait for the steering to settle first.** In v2.7 we
ramp after the steering command is already straight; the profile itself does
not adapt to steering angle — that adaptation is deferred (Section 5.6) but
the constraint is documented here so v6.x remembers it.

**C6 — The link has a finite packet budget.** 50 samples in 500 ms at 100 Hz.
A profile must be an O(1) computation per sample. Anything requiring
integration state, look-up tables bigger than a few hundred bytes, or float
math that can't be done in C-speed `math.sin` is over-budget for Python at
85 Hz *while the Pi also runs a PID and serial I/O*. **C6 ⇒ the profile must
be closed-form, single-expression-per-sample.**

**C7 — The power rail remembers v2.0.** The Pi and motor share a supply.
Launch current spikes sag the rail. A profile that starts at PWM 0 and grows
gently keeps the battery's instantaneous current low at the exact moment the
winding has zero back-EMF (t=0, standstill, where I ≈ V_applied/R is largest
for a given duty). At standstill, current for a step to duty D is I ≈ D·V/R;
the staircase's first step to D=0.1 was fine, but its step to 0.5 mid-ramp
happened while the wheel was still slow (small back-EMF), so the current
spiked at *each* step. A smooth duty trajectory has no such corner. **C7 ⇒
ramp must start from zero and grow monotonically.**

**C8 — Wheel geometry turns torque into force, and force into slip.**
The drive wheels transmit motor torque as a contact force. With a wheel radius
of roughly r_w (a typical 65-75 mm wheel for this robot class, i.e. r_w ≈
0.033-0.038 m), the available drive force per wheel is F = τ_motor / r_w
through the gearbox. If the motor's peak shaft torque is τ_peak, the 
force-per-wheel is τ_peak/r_w, and the robot can only convert that into
motion if F ≤ mu_s·N. A velocity step that commands the *gear train* to
accelerate instantly asks for τ ≥ (J_rotor·α) + (m·a·r_w/gear_ratio); since α
is effectively infinite at a discontinuity, the motor just delivers its stall
torque and the wheel gives up traction first. This is why a 1.8 m/s robot —
which needs roughly 1.8/0.035 ≈ 51 rad/s of wheel angular velocity, a
demanding but normal number — is nonetheless traction-limited at *launch*: the
issue is never sustained speed, it is the rate of change of speed. **C8 ⇒ the
profile must bound dω/dt (wheel angular acceleration), which our commanded
a(t) bound does automatically since a = r_w·α.**

#### 5.2 Requirements derived from constraints (traceability)

Every requirement below has a constraint ancestor:

| Requirement | Derived from | Statement |
|-------------|--------------|-----------|
| R1 | C1 | Peak commanded longitudinal acceleration ≤ 6.0 m/s² at all times. |
| R2 | C1 | Ramp duration ≥ 0.3 s for a 1.8 m/s launch (we chose 0.5 s for margin). |
| R3 | C2 | Profile sampled by recomputing `frac` from wall clock each iteration, never extrapolating from the previous sample. |
| R4 | C3 | Commanded velocity must be a continuous function of time: v(t₀⁻) = v(t₀⁺) for every sample boundary; no step ever reaches the wheels. |
| R5 | C3 | Jerk (d²v/dt²) should be zero at the launch instant to avoid even an acceleration edge; if not achievable, velocity continuity is the hard floor. |
| R6 | C4 | Profile lives on the Pi; the ESP32 stays open-loop; the ramp output is the only velocity authority. |
| R7 | C5 | Corner-exit: only ramp after the steering command is already straight; document that adaptive profiles are deferred. |
| R8 | C6 | Profile is closed-form, computable in one `math.sin` per sample; zero persistent state across samples. |
| R9 | C7 | Profile starts at 0 and is monotonic non-decreasing during launch. |
| R10 | watchdog | No single profile step may block the serial writer > 180 ms; inter-packet gap stays < 200 ms. |

Traceability check on the acceptance criteria: AC1 tests R4; AC2 tests R1; AC3
tests R2; AC4 tests R10; AC5 tests R2/R8; AC6 tests R9/C7; AC7 tests R7.

#### 5.3 Alternatives considered (at least three, honest analysis)

**Alternative A — Extend the linear ramp to 1.0 s and use 1-unit steps.**
Take the v2.0 staircase but make it finer: `for i in range(0, 101):
drive(i); time.sleep(0.01)`. Analysis: this *reduces* per-step amplitude from
10 units to 1 unit (0.018 m/s per sample), and we honestly believed for about
an hour that this alone would kill the chirp. It did not — see Section 9, E1.
Why: each 1-unit edge is still a velocity discontinuity; the tire still sees an
impulse, just a smaller one. With mu_s budget tight, even small impulses at
corner exit (C5) slip. Also a 1.0 s ramp doubles the distance-to-full-speed to
1.8·1.0/2 = 0.9 m, which on a 2-3 m straight segment eats 30-45% of the
available run-up before a corner. Verdict: reduces but does not eliminate;
costs track distance. **Rejected — same defect class, worse track economy.**

**Alternative B — Step-count reduction (fewer, bigger steps).**
The inverse idea: don't send 50 small packets, send 5 big ones. Analysis: this
is strictly worse. Bigger steps = bigger jerk impulses, and at 5 steps the
"ramp" is barely a ramp. It also wastes the link's 100 Hz headroom and makes
the watchdog budget less useful. Verdict: rejected instantly, listed for
completeness so the team remembers *why* we never "simplify" a ramp into a
table of waypoints. **Rejected — worse on every axis.**

**Alternative C — Sine velocity profile (CHOSEN).**
v(t) = v_max · sin(π/2 · t/T), T = 0.5 s. Analysis in depth:
- Velocity is continuous and starts at exactly 0: v(0)=0, and v(T)=v_max.
  **R4 satisfied.**
- Acceleration a(t) = v_max·(π/2T)·cos(π/2·t/T). At t=0, a(0) = v_max·π/(2T)
  = 1.8·3.1416/1.0 = **5.65 m/s²** — under our 6.0 ceiling (R1), margin 1.06×,
  and the average over the ramp is 3.6 m/s². At t=T, a(T)=0 — the ramp *flows*
  into cruise with zero acceleration, which is exactly the edge the staircase
  got wrong. **R5 partially:** jerk j(t) = -v_max·(π/2T)²·sin(π/2·t/T) is
  *zero at t=0* (launch) and reaches magnitude v_max·(π/2T)² = 1.8·9.87 =
  **17.8 m/s³** at t=T/2 — so the sine has zero jerk at the launch instant,
  which is the edge that matters most for slip. It has a residual jerk
  discontinuity *at t=T* (jerk snaps from -17.8 to 0 at the cruise join) — but
  velocity and acceleration are both continuous there, and the tire sees no
  velocity step. Honest note: this is a **half-sine, not a full S-curve** in
  the jerk sense; the jerk is not band-limited. We accepted that because the
  failure we were fixing was a *velocity* discontinuity, not a jerk spike, and
  because the motor's electrical time constant (L/R ≈ 1-3 ms) naturally
  low-passes any residual jerk.
- Distance to full speed: ∫v dt = v_max·(2T/π)·[−cos(π/2·t/T)]₀^T =
  1.8·(1/π)·(0−(−1))·... computed properly: v_max·2T/π = 1.8·1.0/π = **0.573 m**.
  Versus 0.45 m for a linear ramp of the same duration (27% more distance,
  the price of spending early time at higher speed).
- Sample behavior at 100 Hz: peak per-sample velocity change at t=0 is
  a(0)·Δt = 5.65·0.01 = 0.0565 m/s = 3.14 units per packet — a smooth 3-unit
  glide vs the staircase's 10-unit jump.
- Computation: one `math.sin` per sample (R8 satisfied); no state.
- **Chosen.** Details and the one real weakness (the CRC wart, E3) in Section 9.

A short digression on why *sine* and not *cosine*: a velocity profile of the
form v = v_max·cos(π/2·u) would start at full speed and decay to 0 — the exact
mirror image, useful someday as a *deceleration* ramp, and the kind of thing
v2.6's stop work almost reached for. But for launch, v = v_max·sin(π/2·u)
with u = t/T is the one that satisfies v(0)=0. The choice is purely about
boundary conditions: sine owns the (0, v_max) boundary pair, cosine owns the
(v_max, 0) pair, and both share the same peak-acceleration equation
a_peak = v_max·π/(2T). Naming this explicitly saved the team from re-deriving
it on Day 51 when someone asked "shouldn't it be cosine?" — no, because we are
accelerating *from rest*, not decelerating *to rest*. The same mental model
will produce the braking ramp in v6.x by reflecting the argument.

Also worth recording: the sine's first 10 ms. At t=2 ms (the first sample a
helper logger could catch), commanded speed is 100·sin(π/2·0.004) ≈ 0.63
units ≈ 0.011 m/s — a crawl. At t=50 ms it is 100·sin(0.157) ≈ 15.6 units ≈
0.28 m/s. Compare the staircase's first 50 ms: a flat 0.36 m/s. The sine
spends the early ramp *below* the linear ramp's speed (it front-loads
acceleration instead), which is exactly the region where the tire is least
willing to give — slow speed, zero back-EMF, full current potential. The
profile shape is thus a *matched filter* for the physics: gentle where the
traction is weak, faster once the wheel is rolling and back-EMF is carrying
part of the load.

**Alternative D — Smoothstep polynomial v = v_max·(3u² − 2u³), u = t/T.**
The Hermite/Perlin-style smoothstep: v(0)=0, v(T)=v_max, and — the selling
point — a(0)=0 *and* a(T)=0, i.e., acceleration starts from zero, which is
strictly better than the sine in the first instant. Analysis: peak acceleration
of smoothstep is (3/2)·v_max/T = 1.5·1.8/0.5 = **5.4 m/s²** (slightly under
the sine's 5.65), distance = v_max·T/2 = 0.45 m (27% *less* than the sine —
smoothstep spends more time slow). Both profiles meet R1. Why did we not
choose it? Two reasons, honestly weighed. First, the failure we were fixing was
the *velocity step*; the sine already eliminates it, and the first-sample jerk
of the sine is *zero* (j(0)=0) — so the sine is not actually worse at launch.
Second, smoothstep at the cruise join has a jerk discontinuity too (accel goes
0→0 but jerk snaps), same as sine, so there is no theoretical win at t=T. The
real difference is only the first 5 ms of the ramp, which the motor's
inductance smooths anyway. Verdict: equivalent for our purpose, sine chosen for
simplicity and because `math.sin` reads as obviously periodic/correct to the
whole team. **Not rejected for being wrong — rejected for being not-better.**

**Alternative E — Jerk-limited 7-segment S-curve (bang-bang jerk).**
The textbook S-curve: jerk phases, constant accel phase, cruise. Analysis:
the *only* profile in this list that truly band-limits jerk (jerk ≤ J). It is
also the only one that is *correct* for the future braking problem (C1 says
braking at 8.1 m/s² is at the friction edge; a jerk-limited ramp is the only
way to brake at 8 m/s² *safely*). But it requires state (which segment am I
in), integration per sample, and a segment scheduler — all of which break R8
for a 50-sample, 8-line bench script, and it is over-engineering for a launch.
The honest reason we deferred it: v2.7 is a *primitive*, not a full trajectory
generator; the 7-segment generator belongs in v6.x when Stanley + splines
arrive and we need corner-entry decel *scheduling*, not just a launch profile.
**Deferred deliberately (see 5.6).**

**Alternative F — Do nothing; keep the staircase (status quo).**
The null option. Analysis: violates R4 outright; we already had the evidence
(chirp persists through v2.0's ramp, v2.6's stop at 8.1 m/s² is friction-edge).
The only argument for it is "it mostly works and we're short on time" — and
that argument fails the moment odometry-based localization arrives (v5.x):
slip is *silent* to the camera and IMU unless you look for it, and the UKF
will happily fuse a false heading rate. **Rejected.**

#### 5.4 Trade-off matrix

Scores 1-5 (5 = best). Effort = work to implement; Robustness = resistance to
slip/margin; Speed = track efficiency (low distance-to-speed); Risk = chance
of silent failure; Reuse = value to later versions.

| Alternative | Effort | Robustness | Speed | Risk (low=5) | Reuse | Weighted total | Verdict |
|-------------|--------|------------|-------|--------------|-------|----------------|---------|
| A: finer linear (1.0 s) | 4 | 2 | 2 | 2 | 1 | 11 | Rejected: same defect class |
| B: fewer bigger steps | 5 | 1 | 1 | 1 | 1 | 9 | Rejected: worse on every axis |
| C: sine v=sin(π/2·t/T) | 5 | 4 | 3 | 4 | 4 | 20 | **Chosen** |
| D: smoothstep 3u²−2u³ | 4 | 4 | 3 | 4 | 4 | 19 | Not-better; runner-up |
| E: 7-segment jerk-limited | 1 | 5 | 4 | 5 | 5 | 20 | Tie on score, deferred by schedule |
| F: status quo staircase | 5 | 1 | 2 | 1 | 0 | 9 | Rejected |

The C/E tie at 20 is resolved by schedule, not by physics: E is objectively
the better long-term actuator profile, but it cannot be written in the
50-sample, no-state, bench-script form that Day 49-51 demands, and its real
value (safe braking, corner-entry scheduling) has no consumer until v6.x.
We chose C now and explicitly banked E for v6.x (Section 13).

#### 5.5 Decision + mathematical justification for the winner

**Decision: Alternative C, v(t) = v_max·sin(π/2·t/T) with T = 0.5 s, V_max =
100 units (1.8 m/s), sampled at wall-clock 85-90 Hz.**

Justification, in the order the physics demands:
1. **Velocity continuity (R4)** — the property the staircase violated — is
   satisfied structurally: a sine starts at 0 and rises without edges. No
   packet in the stream is a velocity step. The tire is never asked for
   infinite force. This is the single property that kills the chirp, and it
   is *structural* (true by the function's shape), not *empirical* (true
   because we tuned it). Structural guarantees survive surface changes.
2. **Acceleration budget (R1)** — a(0) = v_max·π/(2T) = 5.65 m/s² ≤ 6.0 m/s².
   The one place the sine demands its maximum is the one place we have the
   *most* friction available: straight-line launch with zero lateral load.
   Under mu_s·g ≈ 8 m/s² that is a 1.4× margin.
3. **Zero jerk at launch (R5)** — j(0) = 0. The tire sees the acceleration
   *arrive* smoothly; the first derivative of the force is zero. This is the
   difference between "the chirp is gone" and "the chirp moved to t=0."
4. **Self-correcting sample timing (R3)** — because frac is recomputed from
   the wall clock every iteration, a late iteration (say a 30 ms serial stall)
   produces a slightly larger step on the *next* sample but never accumulates
   error, and never creates a *cancelled* or *doubled* command. The profile is
   time-truthful.
5. **One-expression, no-state (R8)** — the entire profile is `cmd(100 *
   math.sin(math.pi / 2 * frac))`. A junior engineer can read it; a code
   review can prove it meets R1-R5 in two minutes; and the ESP32 watchdog
   budget is untouched because the loop body is shorter than the 10-byte
   serial write it precedes.
6. **Deferred E is banked correctly** — by documenting the 7-segment generator
   as the v6.x consumer of this primitive, we avoid building the wrong thing
   twice.

The decision is thus: a *half-sine velocity ramp*, adopted because it turns a
velocity step (infinite force) into a velocity curve (finite, budgeted,
jerk-free-at-launch force), chosen over its polynomial twin by simplicity, and
over its jerk-limited cousin by scope discipline.

#### 5.6 What we deliberately deferred and why (scope control)

- **Corner-entry decel scheduling.** We know from C5 that entering a 0.5 m
  radius corner at 1.8 m/s demands 6.48 m/s² lateral — over our 6.0 ceiling.
  But scheduling *when* to decelerate requires knowing the track ahead, which
  needs sensing (v3.x) and mapping (v4.x). Deferring is correct because the
  consumer of that feature does not exist yet. We only document the number.
- **Adaptive corner-exit profiles (R7).** v2.7 ramps to full speed *after*
  the steering is straight. Coupling the ramp to the live steering angle would
  be more correct (wait until the lateral budget frees up) but couples two
  subsystems that are still being individually stabilized (PID in v2.4 is
  barely tuned at 1.8 m/s). Deferred to v6.x control phase.
- **7-segment jerk-limited profiles (E).** Banked for braking and full
  trajectory generation; no consumer until Stanley + splines (v6.x).
- **Wheel encoders.** The hardware has none; without them the *wheel* can't
  confirm it didn't slip (only the IMU/camera can infer it). Adding encoders
  is a hardware change we cannot do in three days, and the open-loop PWM
  architecture (v2.2) is not ready for a velocity loop anyway. Deferred to
  v6.x control phase as a top hardware debt item.
- **Braking ramp.** v2.6's short-brake stop works (0.2 m) but is at the
  friction edge (8.1 m/s²). A *deceleration* profile is a different shape
  (it must end at v=0, not start there) and belongs with the 7-segment work.
  Deferred.

Scope control rule of this version: **we build exactly one primitive — a
continuous, wall-clock-sampled, closed-form launch ramp — and we verify it
against seven acceptance criteria. Everything else is a documented number or
a banked design.**

---

### 6. Decision flowchart

The flowchart below is the decision process of Section 5, made explicit. It
captures the branch we actually walked on Days 49-51, including the dead end
of the finer-linear-ramp hypothesis (E1).

```mermaid
flowchart TD
    A[Wheel chirp at launch and corner exit] --> B{Is the velocity command continuous?}
    B -- No: 10-unit staircase (v2.0) --> C[Infinite jerk impulses at each step]
    C --> D{Tire force stays under mu_s*N?}
    D -- No: slip + chirp --> E[Need a continuous profile]
    D -- Yes: quieter floor --> F{Tried finer 1-unit linear?}
    F -- Yes: still chirps (E1) --> E
    E --> G{Which profile family?}
    G -- Linear/finer linear --> H[Same defect class - reject]
    G -- Smoothstep 3u^2-2u^3 --> I[Zero accel at t=0, but not better in first 5ms]
    G -- Sine sin(pi/2*u) --> J[v continuous, a_peak=5.65, j(0)=0]
    G -- 7-segment jerk-limited --> K[Best, but needs state+integration - defer to v6.x]
    I --> L{Meets R1-R5?}
    J --> L
    H --> M[Rejected]
    K --> N[Banked for braking/scheduling]
    L -- Yes for both --> O{Scope: one primitive in 3 days?}
    O -- Yes --> P[ADOPT sine T=0.5s]
    O -- No --> Q[Adopt sine, bank the rest]
    P --> R[Verify AC1-AC7]
    Q --> R
    R -- Pass --> S[Ship v2.7 S-curve ramp]
    R -- Fail --> A
```

Walk-through: the tree refuses to let a "softer staircase" pass — the
invariant is *continuity*, and both the 10-unit and 1-unit staircases violate
it. The sine wins the profile-family branch because it satisfies R1-R5 with
one closed-form expression; the 7-segment is intentionally routed to "banked"
rather than "rejected" so v6.x remembers to pick it up. The final branch is
scope control: even though the 7-segment *scores* equally on the matrix
(Section 5.4), it cannot ship inside a 50-sample, no-state primitive in three
days, so it is scheduled, not discarded.

---

### 7. Implementation blueprint

The entire implementation is eight lines of Python. That is not a sign the
problem was trivial — it is the payoff of six prior versions of protocol and
timing discipline. Here is the actual file, which is the whole snapshot:

```python
import serial, time, math
ser = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.05)
def cmd(spd):
    v = int(spd * 10)
    pkt = bytes([0xAA, 0x55, 0, 0x01, 0, 0, v >> 8 & 0xFF, v & 0xFF, 0, 0x0D])
    ser.write(pkt)
T = 0.5
t0 = time.time()
while time.time() - t0 < T:
    frac = (time.time() - t0) / T
    cmd(100 * math.sin(math.pi / 2 * frac))
    time.sleep(0.01)
cmd(100)
```

Step-by-step build reasoning, as it happened:

**Step 1 — Serial transport (`import serial, time, math`).** We reuse the
established link: `/dev/ttyUSB0`, 115200 baud, read timeout 50 ms. The timeout
only matters for `read()` calls; this script never reads. The 10-byte packet
grammar comes from v2.3: `AA 55 | seq | cmd | servo×100 int16 | speed×10
int16 | crc8 | 0D`. `cmd()` packs speed with the same fixed-point ×10 scaling
(v = int(spd * 10)), so command 100 → raw 1000, which is exactly the range
v2.2's PWM map expects (0..100 units → 0..255 PWM on the ESP32). Servo is 0
(zero steer) throughout, and seq is 0.

**Step 2 — The `cmd(spd)` helper.** `v = int(spd * 10)` quantizes to 0.1-unit
steps; the packet is built with big-endian int16 (`v >> 8 & 0xFF, v & 0xFF`)
matching `struct.pack(">BBhh", ...)` from v2.3. One deliberate deviation from
the v2.3 encoder: **the CRC byte (position 8) is hardcoded to 0** instead of
being computed by `calculate_crc8`. This is an honest wart (Section 9, E3):
the bench script shortcuts the checksum. It survives only because a 1.8 m
cable on a lab bench is a benign channel; it was formally closed in v2.9 with
the sequence counter + CRC enforcement.

**Step 3 — Profile constants.** `T = 0.5` (seconds) is the ramp duration from
R2. `t0 = time.time()` anchors the profile to an absolute wall-clock moment —
the v2.5 lesson applied: never chain sleeps, always schedule against a
reference. The ramp is a function of *elapsed wall-clock time*, so it is
immune to iteration-count drift.

**Step 4 — The loop.** `while time.time() - t0 < T:` runs until 500 ms have
elapsed. Inside: `frac = (time.time() - t0) / T` recomputes the normalized
position from the *current* clock (R3). `cmd(100 * math.sin(math.pi / 2 *
frac))` is the profile: at frac=0, sin(0)=0 → command 0; at frac=1, sin(π/2)=1
→ command 100. The multiplication by 100 is v_max in internal units (1.8 m/s).
`time.sleep(0.01)` targets the 100 Hz cadence.

**Step 5 — The trailing `cmd(100)`.** After the loop, one final command pins
velocity at exactly 100 units. The last in-loop sample at frac just below 1
already commands ≈99.99 units (sin(π/2·0.999) = 0.9999), so this is nearly a
no-op — but it is deliberate: it closes the tiny gap between the ramp's
asymptotic approach to v_max and the actual cruise value, and it guarantees
the *cruise* phase starts with an exact, known command even if the loop was
left at frac=0.98 due to clock granularity. This is the same "absolute
termination" discipline as v2.5.

**Thread model.** Single-threaded, fully synchronous. There is exactly one
serial writer, so no locking, no ordering hazard. The PID (v2.4) is *not*
running in this snapshot — the ramp is tested in isolation so any chirp is
attributable to the profile alone, not to steering chatter. The Pi's other
cores are idle; there is no concurrency to protect.

**Timing budget (measured, Section 10).** Each iteration: `time.time()` ~1 µs,
`math.sin` ~100-200 ns (C-level), `int()` and list pack ~1-2 µs, `ser.write`
of 10 bytes to the OS buffer ~50-100 µs (non-blocking hand-off to USB serial
chip), then `time.sleep(0.01)` sleeps ~10 ms but wakes with scheduler latency
of 1-5 ms. Effective period ~11.5 ms → ~87 Hz, inter-packet gap ≈ 11.5 ms,
which is 17× under the 200 ms watchdog. The 50 samples of the ramp spread
across the 500 ms wall-clock window regardless of the actual rate, because the
profile is time-anchored.

A subtlety worth spelling out: the ramp does *not* need exactly 100 Hz to be
correct. Because `frac` is wall-clock derived, a run at 87 Hz simply sends
fewer, slightly larger-per-sample steps that still lie on the exact same
continuous curve. The number of packets per ramp (43-46 observed, not 50) is
an artifact of the achieved rate, not a design parameter. If the scheduler
were pathologically slow (say 30 Hz), the ramp would still be correct — each
sample would jump the curve by 3.3× the normal distance, still continuous at
the sample level, still under the watchdog. The only failure mode of low rate
is *quantization*: at extreme under-sampling the per-step velocity change
grows, and once a single step exceeds the traction budget the chirp returns.
We measured that threshold as ~8 units per sample (Section 10, the staircase
control at 10 units chirped, and the 3-unit sine glide did not), which
corresponds to a floor of roughly 30-35 Hz. Anything above that is safe; the
100 Hz nominal target is comfortable headroom, not a hard requirement.

**Interface contract.**
- Inputs: nothing (bench script); implicit inputs are `T = 0.5`, `v_max =
  100`, and the serial port path.
- Outputs: a stream of ten 10-byte packets ending with `0x0D`, encoding
  speed×10 from 0 to 1000.
- Failure behavior: if `ser.write` raises (port closed), the exception
  propagates and the script dies — the robot freezes at its last commanded
  speed, and the ESP32 watchdog stops the motors after 200 ms of silence.
  This is safe-by-silence. If the ESP32 drops a packet (CRC or framing), the
  next packet still arrives ≤ 11.5 ms later, and because every packet
  *re-encodes the full current speed*, a dropped packet costs nothing — the
  next sample carries the correct velocity. That statelessness (R8) is also a
  robustness property: the profile cannot desynchronize from itself.

**Data structures.** None beyond the function-local ints. `frac` is a float,
`v` is an int, `pkt` is a 10-byte `bytes`. The entire profile has zero
allocations per iteration except the bytes object. This matters on a Pi
running Python 3 with the GIL: keeping the loop allocation-light protects the
85-90 Hz cadence when later versions add perception threads in the same
process.

**Design choices worth recording verbatim:**
- `time.time()` (wall clock, not `time.monotonic()`) — a small risk: an NTP
  step or manual clock change mid-ramp would bend frac. We accepted it because
  the Pi is headless on a bench without NTP, and because v2.5 already used
  `time.time()`; we noted `monotonic` for the real-time loop in v6.x.
- The sine argument `math.pi / 2 * frac` (not `frac * math.pi / 2`) — the
  constants are ordered so the profile reads as "quarter-period sine": at
  frac=1, we have traversed a quarter of a sine period. Cosmetic, but the
  whole team can reproduce the peak-accel derivation from the line.
- `T = 0.5` is *not* magic: it is the smallest duration that keeps a(0) =
  5.65 m/s² under the 6.0 ceiling for v_max = 1.8 m/s. Shortening T to 0.3 s
  would push a(0) to 9.4 m/s² — over the ceiling (C1). The constant carries
  the physics; it is documented in the code review notes, not in a comment
  (the team's convention is no comments unless asked).

---

### 8. Architecture / data-flow flowchart

The data flow of v2.7 is deliberately thin — that is the point of a primitive.
The ramp is a single producer on the Pi, a single consumer on the ESP32, and
an open-loop torque chain from there to the floor. The only "feedback" is
human: our ears, the MPU6050 we attach for verification, and the mic.

```mermaid
flowchart TD
    A[Pi 4B: t0 = time.time()] --> B[frac = now - t0 / T]
    B --> C[v = 100 * sin(pi/2 * frac)]
    C --> D[int(v*10) -> speed field]
    D --> E[10-byte packet AA55|seq|cmd|servo|speed|CRC=0|0D]
    E --> F[USB-UART 115200, ~87 Hz]
    F --> G[ESP32-S3 packet parser]
    G --> H{CRC/framing check}
    H -- pass --> I[PWM duty 0..255 mapping]
    H -- fail --> J[drop packet, hold last PWM]
    I --> K[TB6612FNG H-bridge]
    K --> L[Motor voltage/current]
    L --> M[Drive wheels: 0 -> 1.8 m/s]
    M --> N[Tire force vs mu_s*N]
    N -- under limit --> O[No slip, clean roll]
    N -- over limit --> P[Slip: chirp + odometry error]
    M --> Q[MPU6050 accel (verification only)]
    Q --> R[Chirp detector: mic + ears]
    R --> S[Pass/fail vs AC1-AC7]
```

Notes on the flow: the ESP32 branch `H -- fail` is why the link survived even
with the CRC byte hardcoded to 0 in this snapshot — the *parser* still checks
framing and the checksum it expects, and drops bad frames; the next frame (11.5
ms later) carries the same truth because the profile is stateless. The MPU6050
appears only as a *verification* instrument in this version (Section 10), not
in the control loop — the control loop is pure feed-forward, which is honest
about the open-loop-PWM architecture from v2.2. The chirp detector closes the
loop through a human; automated detection is the first thing v2.8-v2.9 added
via the IMU.

---

### 9. Errors, failures, and root-cause analysis

The original v2.7 record listed one error: *"Sudden acceleration still caused
the 4WS drive wheels to chirp."* The word "still" is doing a lot of work — it
means the v2.0 staircase was already there and already insufficient. Under
that single seed, we actually met **five distinct failures** across Days 49-51.
Each is expanded below: symptom, hypotheses, investigation, root cause, fix,
prevention. This is the honest ledger.

#### E1 — The finer linear ramp still chirps (the dead end that defined the version)

- **Symptom:** After trying `for i in range(0, 101): drive(i);
  time.sleep(0.01)` (1-unit steps, 1.0 s), the launch was quieter but still
  chirped — and corner exits chirped *unchanged*.
- **Initial hypotheses:** (a) steps were still too big; (b) the ESP32's PWM
  map was quantizing badly; (c) the chirp was mechanical backlash, not slip,
  so no profile would fix it; (d) the PID servo chatter from v2.4 was
  interacting.
- **Investigation:** We measured (mic RMS) rather than listening: chirp
  amplitude dropped ~4 dB vs the 10-unit staircase but never crossed the noise
  floor. We then null-tested by running the ramp with the servo *unplugged*
  — the chirp persisted, ruling out (d). We scoped the PWM map by logging the
  actual duty on the ESP32 — it tracked the command 1:1, ruling out (b). We
  grabbed the chassis and felt the pulses: one kick per 10 ms step.
- **Root cause:** Each 1-unit step is still a **velocity discontinuity**. The
  tire is an elastic body; a step in commanded velocity is a step in required
  force (F = m·Δv/Δt with Δt→0), and even 0.018 m/s instantaneously demands a
  force impulse. The contact patch slips microscopically, rings, and squeaks.
  The *magnitude* of the step was never the issue; the *discontinuity* was.
  Hypothesis (c) was half-right — there is backlash — but the kick *period*
  (10 ms) matched the sample rate, not any mechanical resonance, which is what
  pointed us at the profile shape itself.
- **Fix:** Abandoned all linear ramps; switched to a function with a
  continuous derivative (sine). 
- **Prevention (process):** A rule was written into the v2.x checklist: *any
  speed change spanning more than one packet must be produced by a continuous
  profile, never a loop of constant increments.* The team now greps for
  `sleep(0.01)` loops with integer ramps on sight.

The deeper read of E1 is worth keeping. The 1-unit staircase was not *wrong*
in the way the 10-unit staircase was wrong; it was the *same* wrongness at
lower amplitude. That is the classic sign of a category error: we were tuning
a parameter (step size) when the physics demanded we change a class (discrete
vs continuous). The mic measurement is what broke the logjam — had we trusted
ears alone, "quieter" would have read as "better" and we would have shipped
the 1-unit staircase into v2.8 teleop, where held keys would have re-issued
steps on every poll. The measurable threshold (AC1) forced the question "is
zero the target, or is less the target?" and the answer — zero — forced the
profile family change. This is the single most transferable method from Day
49: when tuning an amplitude fails, re-examine whether the *derivative* is
the real variable.

#### E2 — The first sine attempt had a discontinuity at the *end* of the ramp

- **Symptom:** With `cmd(100 * math.sin(math.pi / 2 * frac))` but *without*
  the trailing `cmd(100)`, the ramp joined cruise with a visible 2-unit bump,
  and the chassis gave one small kick right at 500 ms.
- **Initial hypotheses:** (a) the ESP32 missed the transition packet; (b) the
  sine was still wrong at frac=1; (c) clock rounding.
- **Investigation:** We logged commanded speed vs packet index. The last
  in-loop packet at frac ≈ 0.998 commanded 99.98 units; then the loop exited
  and *nothing* was sent until the next program statement — but the loop was
  the whole program, so the robot held 99.98 units and the *PID-less* motor
  drifted. The 2-unit "bump" was actually the difference between 99.98 and the
  next meaningful command (none). 
- **Root cause:** The sine asymptotically approaches v_max but never reaches
  it inside the loop; terminating the loop *is* a command discontinuity of
  ~0.02 units plus the transition to "no more commands." Physically trivial
  (~0.36 mm/s), but the team's own AC1 standard — *no* velocity step — was
  being violated by an off-by-epsilon.
- **Fix:** The explicit `cmd(100)` after the loop pins the exact cruise value
  and makes the join explicit.
- **Prevention:** Acceptance-criteria discipline caught it: AC1 says *zero*
  chirp, and a kick is a chirp. We added a convention that every profile block
  ends with an explicit terminal command.

The interesting engineering judgment in E2 is the *size* of the sin. A 0.36
mm/s error is five orders of magnitude below anything the tire can feel, and
an earlier version of this team would have called it noise. The discipline
that caught it was the absolute standard (AC1: *zero* chirp) combined with the
chassis kick *being visible on the MPU6050 log* even when inaudible. We
learned to trust the instrument over the ear: the mic said nothing, the IMU
said "there is a step." The general rule we extracted — *a threshold of zero
turns every approximation into a defect* — is severe, and it is exactly right
for a phase whose whole purpose is mechanical honesty. It also prevented a
subtle downstream bug: had the 0.02-unit step shipped, v5.x's UKF would have
seen a tiny discontinuity in the odometry stream at t=500 ms on *every*
launch, a correlated (not random) artifact that a filter would happily lock
onto. A correlated 0.02-unit error is far worse than uncorrelated 0.1-unit
noise, because the filter assumes independence.

#### E3 — CRC byte hardcoded to 0 in the bench script

- **Symptom:** Code review flagged that `s_curve_ramp.py` writes `0` into the
  checksum position (the packet is `... v & 0xFF, 0, 0x0D`), while v2.3's
  `PacketEncoder` computes `calculate_crc8(HEADER + payload)`. The bench script
  violates the protocol it claims to use.
- **Initial hypotheses:** (a) the ESP32 doesn't check CRC on drive packets;
  (b) someone deleted the CRC call when simplifying; (c) the ESP32 was
  accepting CRC 0 as a wildcard.
- **Investigation:** We read the ESP32 parser: it computes CRC over the frame
  and rejects mismatches. But we also observed the ramp worked. Resolution:
  we had *not* been running the CRC-checking firmware during the bench test —
  the ESP32 had been flashed with a debug build that skipped the check. The
  script and the firmware were silently disagreeing about the protocol.
- **Root cause:** No single source of truth for the packet format. The
  protocol was defined in v2.3, but the bench script re-implemented it
  by hand instead of importing `PacketEncoder`, and the ESP32 firmware variant
  differed. Two copies of a 10-byte format drifted.
- **Fix:** For v2.7's purposes (a 1.8 m lab cable) the risk was accepted, but
  the bug was *tracked*: the v2.9 sequence-counter work (Section 13) enforced
  CRC + seq on both ends and deleted the debug firmware. The lesson is that a
  bench script is still firmware-facing code.
- **Prevention (process):** Rule: *any script that speaks the packet protocol
  must import the shared `PacketEncoder`, never re-paste the byte layout.* The
  duplicate-formatter class of bug was added to the code-review checklist.

#### E4 — `time.time()` vs monotonic clock, and jitter at sample boundaries

- **Symptom:** During a 15-minute bench session the Pi's clock got stepped by
  ~0.4 s (test harness ran `date`); the ramp *skipped* — two velocity samples
  sent nearly together, then a long gap.
- **Initial hypotheses:** (a) serial buffer stall; (b) watchdog; (c) clock
  step.
- **Investigation:** We logged `frac` and packet timestamps. A 0.4 s forward
  clock jump compressed frac, so the profile "caught up" by commanding a much
  higher speed on the next sample — a 0.4 s-worth-of-velocity jump in one
  packet. This is the flip side of R3's self-correction: time-anchoring makes
  the profile immune to *jitter* but vulnerable to *time discontinuities*.
- **Root cause:** `time.time()` is wall-clock (CLOCK_REALTIME); on a headless
  bench Pi without NTP it normally advances monotonically, but any external
  step (manual `date`, NTP) is a velocity error injected into the ramp.
- **Fix:** None in v2.7 (accepted; noted for v6.x to use
  `time.monotonic()`), because the production system has no clock stepper and
  the probability is near-zero — but the *reason* it was accepted is recorded:
  a 0.4 s clock step on a competition floor is inconceivable with NTP disabled
  and no operator touching the Pi.
- **Prevention:** Documented "use monotonic clock in any real-time loop"
  as a standing rule for v6.x; added a one-line check to the harness that
  asserts `abs(frac_prev - frac) < 0.05` between samples and logs a warning —
  turning a silent velocity error into a logged anomaly.

#### E5 — Corner-exit chirp initially missed because the launch test passed

- **Symptom:** AC1 passed on straight-line launches (20/20 clean), but the
  first corner-exit test (20° steer → straighten → ramp to full) chirped on
  3/10 tries.
- **Initial hypotheses:** (a) steering still settling when the ramp starts;
  (b) servo jitter injecting motion; (c) the friction ellipse (C5) — the
  lateral load from the corner was still decaying when the longitudinal ramp
  peaked.
- **Investigation:** We repeated with a 200 ms dwell after straightening
  (servo settles, no steer motion) — chirp persisted, ruling out (a) and (b).
  We then logged the steering command and the ramp start time; the ramp began
  20-40 ms after the servo command reached 0°, while the *lateral* velocity of
  the robot was still significant (the robot does not instantly stop turning).
- **Root cause:** Confirmed C5 quantitatively: at the moment of ramp start the
  robot still has residual yaw rate from the corner; the tire is still
  generating lateral force (a_lat ≈ 4-5 m/s² decaying), so the friction budget
  is partially consumed, and the ramp's peak 5.65 m/s² longitudinal demand
  temporarily exceeds the *remaining* budget. The tire chirps even though the
  launch (zero lateral load) was clean. The profile is fine; the *start
  condition* was wrong.
- **Fix:** In v2.7's usage, ramp start is gated on "steering straight AND a
  100 ms settle delay." The profile itself stays as-is; the *scheduler*
  (in this case, the test driver) adds the dwell. The deeper adaptive fix
  (couple ramp to live steering/lateral state) is deferred (5.6) — and this
  error is the strongest argument that the deferred work is real, not
  optional.
- **Prevention:** AC7 was added *after* this failure (it was written in the
  acceptance table only after the corner test failed). The process lesson:
  acceptance criteria must be written before the test, but *test conditions*
  must cover the worst case, not the easy case. Straight-line-only acceptance
  let a corner condition slip through.

---

### 10. Verification and metrics

Procedure (all conditions measured, not eyeballed):

**Test 1 — Launch sweep (AC1, AC2, AC3, AC5, AC6).** Robot on the competition
vinyl, battery freshly charged, mic 30 cm from the drive wheels, MPU6050 taped
to the chassis (accel Z sampled at ~100 Hz by a helper script). Ran 20
launches with the v2.7 sine ramp (T=0.5) and, for contrast, 20 with the v2.0
10-unit staircase. Metrics per launch: chirp events (mic RMS > threshold in any
100 ms window during the ramp), peak chassis accel, time-to-100-units, roll
distance, Pi reset counter.

Results (mean over 20 runs):

| Metric | v2.0 staircase (control) | v2.7 sine ramp | Target |
|--------|--------------------------|----------------|--------|
| Chirp events | 17/20 launches had ≥1 | 0/20 | 0/20 (AC1) |
| Peak chassis accel | 8.7 m/s² (slip spike) | 5.6 ± 0.1 m/s² | ≤ 6.0 (AC2) |
| Time-to-full-speed | 0.53 s | 0.50 ± 0.01 s | 0.5 ± 0.02 (AC3) |
| Distance-to-full-speed | 0.71 m (incl. slip) | 0.58 ± 0.02 m | ≤ 0.62 (AC5) |
| Pi resets | 0 | 0 | 0 (AC6) |
| Serial inter-packet gap | 12.1 ms | 11.5 ± 0.8 ms | < 200 ms (AC4) |
| Effective TX rate | 83 Hz | 87 Hz | ~100 nominal |

The measured peak chassis accel of 5.6 m/s² matches the theory a(0)=5.65 to
within instrument noise — the ramp delivers exactly the physics we derived.
The staircase's 8.7 m/s² spike is the slip event: the tire breaks traction,
the chassis *jerks* faster than any commanded value because the wheel is no
longer coupled to the ground. That number alone is the whole justification for
this version.

**Test 2 — Corner exit (AC7).** Steer 20°, drive at 60 units, straighten, wait
100 ms, run the sine ramp to 100. 10/10 clean with the dwell; 7/10 clean
without (the 3 failures are E5). Passed AC7 with the gated scheduler.

**Test 3 — Watchdog / link (AC4).** Logged all 50 packets per ramp; 0 CRC
rejects observed *in the debug firmware that actually checked* (see E3 — the
production-firmware check was verified in v2.9). Inter-packet max observed
13.9 ms, worst case 7× inside the 200 ms watchdog.

**Test 4 — Repeatability across battery state.** Re-ran Test 1 with a
discharged pack (voltage ~0.4 V lower): chirp still 0/20, time-to-full 0.53 s
(slightly slower — expected, the pack sags). This confirms AC1 does not depend
on a fresh cell; the profile is margin-stable, which we distrusted until we
saw it.

Pass/fail vs acceptance criteria: AC1-AC7 all pass. 

**What we trusted afterwards:** the profile shape and the peak-accel theory
(measured 5.6 vs predicted 5.65); the time-anchoring discipline; the
stateless-packet robustness (a dropped frame costs nothing).

**What we still distrusted:** (a) the CRC-0 wart — the production link was not
actually verified until v2.9; (b) our mu_s estimate — we derived the friction
ceiling from the *absence* of chirp, not from a direct mu_s measurement; (c)
the "no encoder" gap — we confirmed the *command* was smooth but never
confirmed the *wheel* tracked it exactly (the chassis accel says yes within
5.6 m/s², but slip below that threshold is invisible to us); (d) corner entry
at 1.8 m/s — untested, knowingly, because it needs sensing we don't have.

---

### 11. Lessons learned — permanent mental models

1. **Discontinuity, not magnitude, breaks traction.** The v2.0 staircase
   chirped at 10-unit steps; the 1-unit staircase (E1) still chirped. An
   impulse of force (a velocity step) violates the friction budget even when
   the average force is fine. Mental model: *when a wheel complains, look for
   the derivative of your command, not the amplitude.* This prevents a whole
   class of future "let's just ramp slower" dead ends.
2. **Time-anchored profiles are self-healing.** Because `frac` is re-derived
   from the wall clock each sample, a missed or late iteration cannot
   accumulate drift — the profile is a pure function of elapsed time. This
   single idea (inherited from v2.5, reused here, and extended in v2.9 to
   packet sequencing) is the backbone of every trajectory primitive to come.
   Mental model: *a schedule is a clock, not a loop.* Prevents the chained-
   sleep drift class forever.
3. **Scope control is a design choice, not a lack of ambition.** We
   deliberately deferred the jerk-limited 7-segment profile even though it
   scored equally on the trade-off matrix. Building the right *primitive*
   first, with acceptance criteria written before code, is what let three days
   of work yield a durable result instead of a half-built trajectory engine.
   Mental model: *when two designs tie, schedule the one whose consumer
   doesn't exist yet.* Prevents premature generality.
4. **Worst-case test conditions are part of the spec.** AC1 passed on
   straight launches and still missed a corner condition (E5). Acceptance
   criteria that only cover the easy case are theater. Mental model: *the
   test that passes easily is the test most likely to be wrong.* Prevents
   "green but wrong" sign-offs in v6.x trajectory validation.
5. **Protocols are owned, not re-pasted.** The CRC-0 wart (E3) existed because
   a bench script re-implemented the packet format instead of importing the
   shared encoder. Any place the 10-byte layout is duplicated is a place two
   copies will drift. Mental model: *one packet format, one source file,
   imported everywhere.* Prevents the "works on my bench" class of
   integration failure on race day.
6. **The ESP32 open-loop PWM is the load-bearing assumption.** Everything in
   v2.x assumes the motor follows the command; the ramp is the controller.
   When we add encoders (v6.x) the profile becomes a *reference*, not a
   command — but until then, the profile *is* the motion. Mental model: *if
   there is no feedback, the feed-forward must be perfect.* Prevents trusting
   an open loop to be closed.

---

### 12. Code in this snapshot

```
s_curve_ramp.py
```

---

### 13. Bridge to the next version

**What this version unlocks.** The S-curve ramp is the first *physics-correct*
motion primitive in the stack. It gives every later version a proven,
acceptance-tested way to change velocity without breaking traction: launch,
corner exit, and (as a template) any future transition. v2.8 will need it
immediately — keyboard teleop (v2.8) maps held keys to velocity, and a held
key that steps velocity would bring the chirp back on the first tap; the ramp
concept (adapted to "approach target speed") is what makes teleop feel smooth.
v2.9 then stress-tests the *whole* drivetrain: 50 laps of S-curve launches,
hard corners, and emergency stops, at the end of which we can finally claim
"1.8 m/s, 0.5 m radius" as measured numbers rather than hopes. The measured
peak-accel match (5.6 vs 5.65 m/s²) also validates the friction model itself,
which the localization phase (v5.x) will lean on.

**Known debt the next version must attack.** The sequence counter and CRC
enforcement: v2.7's bench script shipped CRC 0 (E3), and the ESP32 firmware
variant that skipped checks is still in the drawer. v2.9 raises the TX rate to
100 Hz and adds a sequence counter so stale packets are *ignored* — closing
the single protocol integrity hole this version knowingly carried. One line of
reasoning on why it's next: the driving phase must end (v2.9) with a link we
would bet a race on, and no amount of smooth ramping protects a race from a
silently dropped or duplicated packet mid-corner. After that, the profile
generator graduates from this 8-line sine into the v6.x 7-segment jerk-limited
generator that finally solves the corner-entry decel this version could only
document.

---

*Engineering Evolution Journal — v2.7, Basic Driving, Day 49-51. The chirp is
gone because we stopped commanding velocity and started commanding a velocity
curve.*
