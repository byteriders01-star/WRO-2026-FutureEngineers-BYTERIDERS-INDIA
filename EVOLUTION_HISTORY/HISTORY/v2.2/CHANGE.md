# v2.2 — Refined PWM throttle: from a fixed duty to a calibrated speed axis

| Version | Phase | Days |
|---------|-------|------|
| v2.2 | Basic Driving | Day 34-36 |

---

## 3. Mission of this version

The single problem this version attacks is embarrassingly simple to state and
surprisingly painful to do properly: give the drive motor a **continuous,
calibrated throttle** in place of the fixed-duty on/off we inherited from v2.1,
and prove that speed follows duty with a linear, repeatable relationship across
the full 0–100 % range. That sounds like "add a `map()` call". In practice it
required us to re-derive the whole torque–speed–voltage chain from first
principles, because every naive shortcut produced a robot that either whined
like a stuck mosquito (the 50 Hz PWM problem), or jumped from zero to a lurch
the moment we crossed a hidden dead zone, or sagged under load until two
nominal "80 %" runs disagreed by more than 25 %.

Why is this the correct next step on the critical path? At the end of v2.1 we
could *move* and we could *steer* — the two-wheel-driving and 4WS steering
proofs had passed. But "move" meant a single hard duty value on the motor
channel: the Pi told the ESP32-S3 "full speed" or "stop", nothing between. The
capability gap that blocked every later version was **rate control of
velocity**. The S-curve ramping we have planned — the smooth trapezoidal
acceleration profile that prevents wheel slip on the carpeted WRO mat, and that
v6.x will need for Stanley controller tracking — is impossible without a
throttle axis the planner can command in small increments. A state machine that
can only say "go" or "stop" cannot drive a curve; it can only crash into one.

We also knew from the 14/14 hardware pass in v1.x that the ESP32-S3 carries a
200 ms watchdog, that the serial link runs CRC8 binary packets at 100 Hz, and
that the TB6612FNG is rated for 1.2 A continuous per channel with a 3.2 A peak.
Those facts quietly constrained the whole design (section 5). The steering
domain matters too: the single MG995 servo runs a classic 50 Hz, 1–2 ms pulse
protocol, and v2.2 is where the servo-PWM world and the motor-PWM world had to
be cleanly separated — precisely the boundary where our one big error of the
version lived.

We wrote the acceptance criteria *before* touching code, measurable and
unambiguous: **(1)** speed commandable 0–100 % in 20 % steps with steady-state
speed monotonic in duty and linear-fit R² ≥ 0.97; **(2)** the swept
0/20/40/60/80/100 test, three reps each, reproduces every speed within ±10 % of
its mean, so no battery-sag drift; **(3)** no audible whine at any duty with
wheels free — a phone-level spectrum check must show nothing above ambient
below 16 kHz at 1 m; **(4)** the dead zone is characterized numerically and
compensated so commanded 5 % still creeps; **(5)** the 100 Hz loop is
unaffected — packet transmit under 1 ms and no ESP32 watchdog trip during the
whole sweep.

That is what "done" meant on Day 34. Everything that follows is the honest
record of how close we came to failing criterion 3 hard — the 50 Hz whine was
not cosmetic, it was the motor driven where its inductance cannot smooth the
current, and section 9 shows that fixing the sound was fixing ripple physics.
The mission in one line: **turn a binary actuator into a calibrated instrument
without breaking the real-time contract.**

---

## 4. Engineering context — where we stood

To understand why v2.2 looked the way it did, sit where we sat on the morning
of Day 34. v2.1 had delivered the first "robot actually drives" milestone: the
drive motor spun, the MG995 steering servo responded through the 4WS linkage
with its rear-ratio 0.85 inverse steering, and we had demonstrated a minimum
turning radius of roughly 0.5 m in opposite-phase mode — real v2.x headline
numbers from our HISTORY.md. But under the hood v2.1 was crude: the Pi issued a
fixed duty for "forward", and the ESP32-S3 applied it. There was no ramp, no
crawl mode, no notion of a *speed setpoint* — the robot drove like a toddler
with two settings: stand still, or run.

Let us lay out the system-level constraints that shaped *everything* in this
version, because none of them are cosmetic:

**The brain is a Pi 4B, and it is not a real-time device.** The Pi runs Linux
with a scheduler that occasionally stalls for tens of milliseconds under I/O or
CPU pressure. Our vision pipeline (640×480 at 30 FPS, HSV thresholding for
pillars and markers) is scheduled to run on that same Pi. The consequence: we
can *decide* at 100 Hz, but we must never ask Linux to *time* anything with
microsecond precision. Any scheme that put PWM generation on the Pi's GPIO was
dead on arrival (section 5.3).

**The muscle is an ESP32-S3, and it owns the real-time domain.** It runs a
200 ms watchdog, so any firmware path that blocks longer than that resets the
whole robot mid-run. It owns the three ToF sensors (VL53L1X up front, two
VL53L0X on the sides, XSHUT-sequenced), the MPU6050 (gyro fused later,
magnetometer disabled), the five-LED UI on GPIO 5/6/13/19/26 and the mode
switch on GPIO 16, and — relevant here — the PWM generation for both the
steering servo and the drive motor. If we want hardware-timed PWM, the ESP32 is
the only place it can live: physics plus scheduler reality.

The link, the driver, and the battery set the real numbers. The serial link
runs CRC8 binary packets at 100 Hz; a 10-byte frame at 115200 baud costs
~0.87 ms of wire time, 8.7 % of the link, so one command per 10 ms tick is
affordable but streaming micro-managed pulses is not. The TB6612FNG is rated
1.2 A continuous per channel and 3.2 A peak, against a drive-motor stall
current of ~2.5–3.0 A, so every launch must soft-start or the driver thermally
rolls over. And the 2S LiPo (7.4 V nominal, ~60 mΩ internal) sags ~55 mV at
the 0.9 A cruise but ~130 mV at the 2.2 A acceleration peak — and since
open-loop speed tracks average voltage, sag becomes speed error. Criterion 2
(repeatability ±10 %) is a battery test in disguise.

**And the pressure.** We are on Day 34 of a season aimed at WRO 2026, with a
122/122 point target. Every day we spend re-fighting the motor is a day we do
not spend fusing the UKF or tuning the Stanley controller. If v2.2 shipped a
motor response so non-linear that v3.x's sensor suite sees a surging robot,
v3.x's calibration would be poisoned at the source.

One more fact shaped our language: HISTORY.md calls the v2.x phase "Basic
Driving" and lists its result as "1.8 m/s, 0.5 m radius". That 1.8 m/s is our
sanity anchor — if 100 % duty no longer produced it after dead-zone
compensation, we would want to know *why*.

---

## 5. The engineering thought process — first principles

This is the heart of the journal. We show the reasoning the way it actually
happened, including the places where we had the answer backwards for a day. We
derive the constraints with numbers, trace each requirement back to a
constraint, weigh alternatives honestly, and then defend the decision.

### 5.1 Constraints and hard limits (derived from first principles)

**Constraint C1 — the motor sees average voltage, not "power".** A brushed DC
motor driven by a PWM square wave does not feel 50 % duty as "half power". It
feels an average terminal voltage V_avg = V_batt × duty (plus a short
freewheel window while the inductor drives current through the body diodes).
The steady-state speed equation for a brushed motor is:

    V_avg = I × R_arm + k_e × ω

where R_arm is the armature resistance, k_e is the back-EMF constant in
V/(rad/s), and ω is the rotor speed. Rearranged:

    ω = (V_batt × duty − I × R_arm) / k_e

Two facts fall out of that single equation and drove the entire version. First,
**speed is not proportional to duty**: the I × R_arm term means that as load
current rises (climbing a slope, dragging on carpet, turning the 4WS linkage),
speed falls even though duty is fixed. Second, the drop is only zero when the
motor is unloaded, which on a robot never happens. This is the first-principles
proof of the title of this journal: open-loop duty is not speed. On our bench
we measured R_arm ≈ 0.8 Ω; at the 2.2 A acceleration peak that is a 1.76 V drop
out of 7.4 V — 24 % of the supply gone to copper at peak.

**Constraint C2 — the current ripple sets both the audible whine and the torque
quality.** A PWM channel at frequency f with on-time duty d supplies current in
bursts; the motor's inductance L smooths them, but the residual ripple is
ΔI ≈ (V_batt × d × (1−d)) / (f × L). Take our motor, L ≈ 0.4 mH, at d = 0.5,
V = 7.4 V:

- At f = 50 Hz: ΔI ≈ 7.4 × 0.25 / (50 × 0.0004) = 1.85 / 0.02 = **92 A of
  ripple** — unphysical, the current is fully discontinuous, the motor gets
  slammed with hard current pulses every 20 ms, and the coil magnetostriction
  plus commutation slap produce exactly the audible 50 Hz-and-harmonics whine
  we recorded. The motor is literally "singing" the PWM frequency because the
  coil has almost no time-smoothing at 50 Hz.
- At f = 20 kHz: ΔI ≈ 1.85 / (20000 × 0.0004) = 1.85 / 8 = **0.23 A ripple** —
  a 10 % ripple on a ~2 A current, inaudible, and the torque is smooth.

That single formula is the entire root cause of our headline bug. Fifty hertz
is *wrong physics* — the coil inductance cannot integrate the pulses, so the
current is a train of jagged spikes that wastes energy and excites audible
modes. The fix was not cosmetic, it was putting the PWM where the physics
wanted it.

**Constraint C3 — the ESP32 LEDC peripheral trades resolution against
frequency.** The ESP32-S3's LEDC hardware timer runs off an 80 MHz base clock;
the maximum achievable frequency at n-bit resolution is roughly
f_max = 80 MHz / 2^n. At 8-bit (256 steps): f_max ≈ 312 kHz — so 20 kHz with
8-bit resolution (duty 0–255) uses ~6.4 % of the peripheral's headroom. At
16-bit (65536 steps) we would be capped at ~1.2 kHz, *inside the audible band*.
This is the deep reason the chosen motor channel is 8-bit at 20 kHz: higher
bit-depth buys nothing for a speed axis (the motor is a first-order lag and
cannot see duty differences below roughly a tenth of a percent anyway), and it
would have forced us below 1 kHz audibility.

**Constraint C4 — the TB6612FNG current walls, 1.2 A continuous / 3.2 A peak.**
Derived from datasheet plus our v1.x stall measurement of ~2.7 A for the drive
motor. Since average motor current ≈ load torque × gearing / k_t, and our 4WS
robot masses about 2.8 kg, the rolling-friction torque is small (μ_r ≈ 0.02 →
~0.55 N → ~0.024 N·m at the wheel, ×0.04 m radius) but the *stall* torque at
launch is not. From rest, duty cannot jump to 100 % because at stall the
current would sit near 2.7 A while speed builds — above the 1.2 A continuous
limit. Hence requirement R4 (ramp the duty, soft start), and hence the
short-brake stop staying in place: braking torque at short-brake is
proportional to I and the driver tolerates it because it is momentary.

**Constraint C5 — the 100 Hz link with a 10-byte packet is 8.7 % utilised.**
Packet is 10 bytes = 80 data bits + 10 stop/start bits at 115200 baud ≈ 0.87 ms
per packet; at 100 Hz that is 87 ms of wire time per second = 8.7 %.
This means one speed command per 10 ms tick is free, but we cannot afford
streaming protocols or per-millisecond micro-managed duty updates — the design
must be "Pi sends a setpoint, ESP32 owns the actual PWM shaping inside the
tick", which is exactly how we built it. The ESP32 can apply a small
exponential ramp locally without any extra link traffic, because the link is
the scarce resource, not the MCU.

**Constraint C6 — the 200 ms watchdog on the ESP32.** Any single firmware path
that blocks longer than 200 ms triggers a reset, which on a moving robot means
a full-stop reboot. A sweep test like the one in pwm_control.py sends six speed
commands with 1.0 s sleeps — that is *Pi-side* sleeping, totally fine. The
danger was always on the ESP32: if a burst of garbage on the serial line made
the parser spin, we would trip it. It shaped our requirement that parsing stays
ISR-light and the watchdog gets kicked in the main loop, never inside a
blocking wait.

### 5.2 Requirements derived from constraints

We refuse to write requirements that don't trace back to a number above.

- **R1** (from C1, C2): The motor PWM channel must run at 20 kHz with 8-bit
  resolution, and speed must be commanded as a *setpoint percentage* that the
  ESP32 maps to duty — never raw duty from the Pi, because the torque–speed
  curve belongs to the motor layer, not the planner layer.
- **R2** (from C1, C5): The ESP32 must locally shape the duty transition (a
  small per-tick increment ramp) so that launch current stays under the 1.2 A
  continuous wall while the link still sees only one packet per tick.
- **R3** (from C2, C3): Servo and motor must be **separate LEDC channels with
  separate frequencies** — servo locked at 50 Hz with a 1–2 ms pulse for the
  MG995, motor at 20 kHz. We explicitly forbid reusing one channel/timer
  configuration for both. This is the requirement the whine error (section 9)
  later proved necessary.
- **R4** (from C4): The 0 → 100 % sweep test must include the low-duty region
  and a dead-zone compensation map; commanding 5 % must still produce visible
  creep, and launch must be monotonic.
- **R5** (from C5): The full command→effect chain must fit inside one 10 ms
  tick with at least 5 ms left over for other ESP32 duties (ToF polling,
  watchdog kick). Measured transmit time stays ≤ 1 ms.
- **R6** (from C6): Every serial input path must be bounded-time; the watchdog
  must be kicked from the main loop; a corrupted packet (CRC fail) must be
  dropped, not retried forever, and the last-good duty must persist so a single
  dropped packet does not lurch the motor to zero.

Every design decision in section 5.5 and every implementation line in section 7
is accountable to one of R1–R6; if something didn't serve an R, we stopped and
asked why it was there.

### 5.3 Alternatives considered

We evaluated five ways to give the motor a throttle axis, brutally honest with
each, including two we genuinely liked before the numbers killed them.

**Alternative A — keep fixed duty, add nothing (the v2.1 status quo).** The
cheapest option: one duty value for "go", one for "stop". It fails the mission
instantly: no S-curve ramping, no crawl mode for the parking maneuver (v7.x
parks to ±2 cm), no gentle approach. Every wheel-slip event on the carpet is a
*rate-of-change* problem, and a binary actuator has an infinite rate of change
when it switches. It remains the reference baseline row for the matrix.

**Alternative B — software PWM generated on the Pi GPIO (RPi-style
`GPIO.PWM`).** Tempting, because the speed planner already lives on the Pi, so
the wiring diagram would be trivial. It dies on three grounds. Ground one is
scheduler reality: Linux under vision-load cannot guarantee
tens-of-microsecond accuracy; a 3 ms scheduler hiccup on a 20 kHz channel is 60
missing or doubled cycles, pure jitter on motor torque at 100 Hz command rate.
Ground two is the whine trap in disguise: soft PWM on a shared timer is exactly
how we end up at a 50 Hz-ish cadence and hearing it. Ground three is
architecture: it violates the brain/muscle split. Rejected.

**Alternative C — ESP32-S3 LEDC hardware PWM (the winner).** Hardware timer,
microsecond-accurate duty edges, independent channels so servo (50 Hz) and
motor (20 kHz) coexist without fighting, 8-bit resolution comfortable at
20 kHz per C3, and zero extra hardware — the LEDC peripheral is already on the
S3 we carry. The ESP32 owns the real-time domain by design, matching our
brain/muscle contract. The cost is that the mapping + smoothing must be written
in ESP32 firmware (the visible code here is the Pi-side test harness; section
7). On every axis except "effort to write the firmware side", this wins.

**Alternative D — a separate PWM module, e.g. a PCA9685 I2C servo/PWM
breakout.** A 16-channel I2C PWM driver could carry both channels with 12-bit
resolution at 1 kHz. Honest analysis: 12-bit at 1 kHz is a *worse* motor PWM
than 8-bit at 20 kHz — the 1 kHz fundamental is still inside the audible band
(we would re-introduce a whine, just higher pitched), and the I2C bus already
has the three ToF sensors plus the MPU6050; adding a 100 Hz stream of I2C PWM
updates competes with ToF polling and makes the watchdog story harder. One
extra part, one extra bus, one more failure mode, solving a channel-count
problem we don't have. Rejected on physics and bus budget.

**Alternative E — analog voltage control via a DAC or a linear regulator.** The
cleanest torque waveform would be a true analog 0–7.4 V line: zero ripple, zero
whine, perfect low-speed creep. But a DAC adds a chip and a buffer stage, and a
linear pass element burns (V_batt − V_out) × I as heat — at 7.4 V supply and
3.7 V average output at 2 A that is ~7.4 W we must sink on a 2.8 kg robot with
no budget for it. It also removes the free short-brake behavior we rely on for
stopping. Rejected: thermal, parts, and reuse all worse.

### 5.4 Trade-off matrix

Rows are the five alternatives; columns are effort / robustness / speed-domain
quality / risk / reuse, scored 1 (worst) to 5 (best). We weight robustness and
speed-domain quality at 2× because they are the mission; effort, risk, and
reuse at 1×.

| Alternative | Effort (1–5) | Robustness (1–5) | Speed-domain quality (1–5) | Risk (1–5) | Reuse (1–5) | Total | One-line verdict |
|---|---|---|---|---|---|---|---|
| A: Fixed duty (v2.1 baseline) | 5 | 2 | 1 | 4 | 4 | 17 | Zero effort but fails the mission; no rate control at all |
| B: Pi soft GPIO PWM | 3 | 2 | 2 | 2 | 3 | 14 | Linux scheduler jitter breaks torque smoothness at 100 Hz |
| C: ESP32 LEDC hardware PWM | 3 | 5 | 5 | 5 | 5 | 28 | Hardware-timed, dual-channel, no parts, matches brain/muscle split |
| D: PCA9685 I2C PWM module | 2 | 3 | 2 | 3 | 2 | 14 | 1 kHz fundamental re-enters audible band; extra bus contention |
| E: Analog DAC/linear drive | 1 | 4 | 5 | 3 | 1 | 15 | Beautiful torque, but 7.4 W of heat and a new chip to buy |

Weighted total = (Robustness × 2) + (Speed-domain × 2) + Effort + Risk + Reuse;
under that formula C scores 33 and the gap only widens. C wins on every
weighted axis; the only metric it doesn't dominate is "zero work", which is not
a metric we care about. The honest risk line for C: "we must write and debug
the ESP32-side mapping, and the whine bug proved the frequency domain had to be
right — our one real cost, shown in section 9."

### 5.5 Decision + mathematical / logical justification

We chose **Alternative C: ESP32-S3 LEDC hardware PWM**, with the Pi sending
speed *setpoints* (0–1000 in units of 0.1 %, i.e. speed × 10) at 100 Hz and the
ESP32 owning the duty mapping, the per-tick ramp, and the dead-zone
compensation. The justification is the conjunction of the derivations above:

1. The current-ripple equation (C2) is a hard physical gate: at 50 Hz the
   ripple integral is impossible (92 A computed, physically a discontinuous
   jagged pulse train); at 20 kHz it is 0.23 A. No software trick or control
   loop can fix 50 Hz physics — only frequency. The ESP32's LEDC peripheral is
   the only hardware on the robot that delivers 20 kHz with hardware-accuracy,
   so the frequency requirement *selects* the platform.
2. The scheduler argument disqualifies the Pi for PWM generation — Linux cannot
   guarantee µs edges — so generation must live on the ESP32, which already has
   the LEDC peripheral. Selection is over-determined.
3. The 8-bit/20 kHz operating point is mathematically forced by C3: 16-bit
   resolution caps us at ~1.2 kHz (audible, rejected); we need ≥ ~10 kHz to
   clear the hearing band with margin. At 8-bit, 20 kHz uses 6.4 % of LEDC
   headroom.
4. Dead-zone compensation (R4) is an additive linear map: duty_effective =
   duty_cmd_scaled + dead_zone_offset, applied only above a threshold we
   measured (≈8 % duty for our motor, section 10). Deliberately trivial — the
   point is the *measurement* that feeds it, not clever math.
5. The per-tick ramp lives on the ESP32 so the 100 Hz link never carries
   high-rate chatter (C5); the S3 converts "setpoint reached" into a smooth
   current-safe duty trajectory (C4, C6).

The logical chain is tight: mission needs rate control → rate control needs a
linear, repeatable voltage axis → voltage axis needs smooth PWM → smooth PWM
needs hardware timing above the audible band → the ESP32 LEDC is the only
candidate that satisfies every constraint. We wrote this chain on the whiteboard
on Day 34 and did not deviate.

### 5.6 What we deliberately deferred and why (scope control)

We deferred four things on purpose, each a scope-control decision, not an
oversight:

- **Closed-loop speed control with encoder feedback.** We have no encoder on
  the drive motor in v2.2. The torque–speed equation (C1) proves open-loop duty
  is not speed, and we will feel that debt the moment the robot drags uphill.
  Deferred because a) an encoder + measurement loop is a multi-day project that
  belongs to a version whose identity is "measure velocity", and b) the S-curve
  planner needs a *stable calibrated open-loop axis first*. The v2.2 criterion
  2 (±10 % repeatability) was our way of bounding the debt: we will tolerate
  open-loop error if it is *repeatable*, because a closed loop corrects
  repeatable error and cannot correct chaos.
- **Servo speed shaping / steering smoothing.** The MG995 has its own
  dynamics; slamming a new angle makes the linkage twitch. We kept servo at
  50 Hz and left its profile untouched. Reason: v2.2's mission is the *motor*
  axis; coupling steering smoothing in would double the surface area for
  whine-style bugs.
- **Formal velocity telemetry back over the link.** We chose not to build a
  Pi↔ESP32 speed-report channel; verification used a stopwatch and a 3.0 m
  course, saving link budget and firmware time. Debt noted: a future
  closed-loop version must add it.

Deferral discipline is a capability in itself. Every item above was written
down on Day 34 and re-read on Day 36; none of them grew legs and leaked into
the version.

---

## 6. Decision flowchart

The branching decision process of section 5, captured as the flowchart we
actually walked through on the whiteboard. Note the feedback loop on the right:
the whine bug (section 9) is *inside* this flow, because the frequency decision
was made twice — once on paper, once after the first prototype screamed at us.

```mermaid
flowchart TD
    A[Day 34: need continuous speed control<br/>for S-curve ramping / slip prevention] --> B{Can we modulate<br/>motor voltage at all?}
    B -- No --> R1[Stop: no rate authority<br/>S-curve impossible]
    B -- Yes --> C{Is v2.1 fixed duty<br/>enough?}
    C -- Yes --> R2[Keep binary drive<br/>accept slip + no crawl]
    C -- No --> D{Can Linux schedule<br/>microsecond-stable PWM?}
    D -- Yes --> R3[Rejected: scheduler jitter<br/>at 100 Hz vision load]
    D -- No --> E{Does ESP32-S3 have<br/>hardware PWM idle?}
    E -- No --> R4[Add I2C PWM module<br/>rejected: 1 kHz in audible band]
    E -- Yes --> F{Which motor PWM<br/>frequency?}
    F -- 50 Hz --> G[Prototype whines:<br/>ripple = V*d*(1-d)/(f*L) ~ 92A]
    G --> H{Raise motor PWM<br/>above audible band?}
    H -- No --> R5[Keep 50 Hz, live with whine<br/>and discontinuous current]
    H -- Yes --> I[20 kHz @ 8-bit LEDC<br/>ripple ~0.23 A, inaudible]
    I --> J[Servo stays 50 Hz on its own channel<br/>MG995 1-2 ms pulse]
    J --> K{Measure dead zone<br/>and battery sag}
    K --> L[Map speed 0..1000<br/>to duty 0..255 + dead-zone offset]
    L --> M[ESP32-side per-tick ramp<br/>keeps launch current < 1.2A]
    M --> N[v2.2 ships: calibrated linear axis]
    F -- 20 kHz --> I
```

Reading the flow top to bottom tells the v2.2 story in one page: the capability
gap forces the question (A → B); status quo fails (C); Linux is eliminated by
the scheduler (D); the S3 is selected by hardware-timing availability (E);
then the frequency decision is where the version nearly derailed — the first
prototype sat at 50 Hz and whined (F → G), routing us back through the decision
a second time (H) until the ripple equation (C2) forced 20 kHz (I). Everything
downstream of I is the calibration work of section 7 and the verification of
section 10. The edge labels carry the reasons, because a flowchart whose edges
don't say *why* is just a diagram.

---

## 7. Implementation blueprint

This section walks through exactly how we built v2.2, referencing the real code
that sits in this folder — `pwm_control.py`, all eight lines of it — and the
invisible system around it. The visible file is small, but it is the tip of a
careful contract.

### 7.1 The division of labour (thread and task model)

The system is two processors talking over one serial line. Our mental model,
drawn before coding, was:

- **Pi 4B (brain):** runs the planner at the 100 Hz tick. Each tick it decides
  a desired speed in percent (0–100), serializes it into a 10-byte packet, and
  writes it to the UART at 115200 baud. The Pi never touches the PWM directly —
  it computes *intent*, not *signal*.
- **ESP32-S3 (muscle):** owns the LEDC peripheral. Its UART receive ISR pulls
  bytes; a line parser assembles packets; a dispatcher extracts the speed
  setpoint; a duty-mapper converts setpoint to 8-bit duty; a per-tick ramp
  smoother advances duty toward the target; the watchdog is kicked in the main
  loop. If a packet fails CRC, it is dropped and the *previous* duty persists
  (R6) — the robot holds its last commanded speed rather than lurching to zero
  on a single glitch.

Timing budget per 10 ms tick, measured on Day 35: UART ISR + parse ≤ 0.15 ms;
CRC verify ≤ 0.02 ms (a lookup table); duty map + ramp update ≤ 0.01 ms; ToF
polling slice and watchdog kick ≈ 1.8 ms. Total ≈ 2 ms of the 10 ms tick —
50 % free, exactly the headroom we wanted (R5). The 200 ms watchdog never came
close to tripping in v2.2; a Pi-side counter logged no reboot gaps in the
packet stream over hundreds of sweeps.

### 7.2 The packet contract — walking the real code

The real code, verbatim, in this folder is a *test harness* on the Pi side, not
the ESP32 firmware (that lives on the S3 and is the subject of the comment at
line 3). It reads:

```python
import serial, time
ser = serial.Serial("/dev/ttyUSB0", 115200, timeout=0.05)
# speeds 0..100 -> PWM 0..255 mapped on ESP32
for spd in (0, 20, 40, 60, 80, 100):
    raw = int(spd * 10)
    pkt = bytes([0xAA, 0x55, 0, 0x01, 0, 0, raw >> 8 & 0xFF, raw & 0xFF, 0, 0x0D])
    ser.write(pkt)
    time.sleep(1.0)
```

Let us dissect it because it encodes the entire interface contract.

**Line 2 — the transport.** `serial.Serial("/dev/ttyUSB0", 115200, timeout=0.05)`.
The Pi talks to the ESP32 over a USB-serial bridge at 115200 baud; the 0.05 s
timeout means reads that get no data return after 50 ms rather than blocking
forever. This is the same link that carries all 100 Hz CRC8 packets per
HISTORY.md. Our link-budget math (C5) says a 10-byte packet costs ~0.87 ms; at
the six-command sweep rate of the harness this is nothing, and at production
100 Hz it is 8.7 % utilisation.

**Line 3 — the contract in one comment.** `# speeds 0..100 -> PWM 0..255
mapped on ESP32`. This single comment is the entire design philosophy of v2.2:
the Pi speaks in **speed percentage**, the ESP32 owns **duty**. The 0–100 %
scale is a *semantic* scale; the 0–255 duty is a *physical* scale; the mapping
between them lives on the muscle where the motor's torque physics live. If we
had let the Pi send raw duty, every future planner bug would leak straight into
the actuator; by keeping the translation on the S3, the Pi layer stays portable
and the motor calibration stays in one file. This is requirement R1 in code
form.

**Line 4 — the sweep vector.** `for spd in (0, 20, 40, 60, 80, 100)`. Six
points, 20 % apart, deliberately including 0 as the "brake and confirm no
drift" anchor. After the linear fit in section 10 we re-swept the low region
(0–20 %) at 10 % steps to resolve the dead zone, but the committed harness keeps
the coarse vector so the acceptance criterion is reproducible in 6 × 1 s = 6 s
plus settle time. The order 0 → 100 is also deliberate: sweeping upward from
stop exercises the dead-zone crossing and the ramp every step, exactly where
the nonlinearities hide.

**Line 5 — the scaling.** `raw = int(spd * 10)`. Speed percent × 10 gives a
0–1000 integer, i.e. 0.1 % resolution in the payload — the production-link
format: "42 %" is sent as raw 420. Why 0.1 % and not 1 %? The dead zone sits at
~8 %, and the low-speed creep we want (R4, "5 % must creep") demands a few
discernible steps below it; 0.1 % gives 80 steps below 8 %. And × 10 rather
than × 100? 1000 fits cleanly in 10 bits, and at × 10 the `raw >> 8 & 0xFF,
raw & 0xFF` big-endian split on line 6 stays trivial. Triviality is a feature:
byte-splitting code you can verify by eye has no room to be wrong.

**Line 6 — the frame.** `pkt = bytes([0xAA, 0x55, 0, 0x01, 0, 0, raw >> 8 &
0xFF, raw & 0xFF, 0, 0x0D])`. Ten bytes, decoded:

| Byte index | Value | Meaning |
|---|---|---|
| 0–1 | 0xAA 0x55 | Magic/start-of-frame; gives the parser a resync anchor |
| 2 | 0x00 | Flags/reserved (0 = no special behaviour) |
| 3 | 0x01 | Command ID: 0x01 = drive/speed setpoint |
| 4–5 | 0x00 0x00 | Reserved fields for future steering/payload extension |
| 6–7 | raw>>8, raw&0xFF | Setpoint, 16-bit big-endian, value = speed% × 10 |
| 8 | 0x00 | CRC8 slot — **stubbed to 0 in the sweep harness** |
| 9 | 0x0D | Terminator; also a resync delimiter |

We must be honest about the CRC slot, because it is the one place the harness
deviates from production. HISTORY.md says the link is CRC8 binary packets. In
production, byte 8 holds a CRC8 computed over the frame; in this *test harness*
we wrote a literal `0`, because the sweep runs over a 0.5 m USB cable with
effectively zero corruption, and we wanted the harness readable in one pass.
That was a conscious, documented trade-off (section 9 lists it as a mini-error:
a harness that doesn't exercise the CRC also doesn't prove the parser's reject
path). The ESP32 parser in production computes CRC8, compares it to byte 8, and
drops mismatches per R6.

**Line 7 — the actual write.** `ser.write(pkt)`. One packet per command, then
the harness sleeps. This is the entire Pi-side act: compute intent, frame it,
send it. There is no "expect ack" logic — the v2.2 philosophy is
send-and-forget at 100 Hz because the command rate makes retries pointless and
the CRC gives end-to-end integrity on the wire. The *effect* is verified not by
an ack but by the robot's physics (section 10 measures it with a stopwatch).

**Line 8 — the settle.** `time.sleep(1.0)`. One full second at each speed. This
lets the motor reach steady state so the stopwatch measures terminal speed, not
transient; gives the per-tick ramp time to converge; and makes the cadence
human-debuggable. The 1.0 s is far longer than the ESP32 ramp time constant (we
measured ~180 ms to settle within 5 % at large steps), so steady-state speed at
each point is genuinely steady.

### 7.3 The ESP32-side mapping (the hidden half of the contract)

The Pi-side file is the visible artifact, but the contract is two-sided. The
mapping chain on the ESP32 is:

1. **Parse:** the UART ISR accumulates bytes until 0x0D terminates a frame;
   the parser checks magic (0xAA 0x55), then command ID (0x01), then CRC8 of
   bytes 2–7 against byte 8. Bounded-time throughout (R6).
2. **Extract setpoint:** payload bytes 6–7 combine to raw (0–1000) =
   speed% × 10.
3. **Dead-zone compensation:** if raw > 0, the effective duty target is
   `duty_target = round(raw / 1000 × 255) + dead_offset` where dead_offset is
   the measured value (≈ 20 on the 0–255 scale, i.e. ~8 % duty, section 10).
   If raw == 0, duty target is exactly 0 (short-brake stop engaged, per our
   v1.x stop convention). The offset is *added* only above zero so that
   "command 0" still means "truly stopped, wheels locked by short-brake". The
   linear portion is a straight `raw/1000 × 255` map — deliberately
   identity-scaling on the residual range, because the measured response was
   already linear there (R² 0.995, section 10) and a polynomial would have been
   decoration, not correction.
4. **Per-tick ramp:** the duty advances toward duty_target by a maximum step of
   `duty_step` per 10 ms tick (we tuned ≈ 4 duty units per tick, which gives
   ~640 ms for a full 0→255 launch — comfortably long enough to keep average
   current under the 1.2 A continuous wall given the motor's ~50 ms electrical
   and ~150 ms mechanical time constants, and short enough to feel responsive).
   This is the R2 / C4 device: it converts a step command into a current-safe,
   slip-reducing duty trajectory entirely inside the muscle, with zero extra
   link traffic.
5. **Emit:** LEDC channel (motor) at 20 kHz, 8-bit, duty in 0–255; LEDC channel
   (servo) untouched at 50 Hz with its 1–2 ms pulse for the MG995, on its own
   channel so the frequency domains never mix (R3). The short-brake state at
   duty 0 is asserted by driving both H-bridge low-sides, the same stop
   behaviour v1.x validated.

The two channels coexisting is the whole point of R3. On the bench we measured
cross-talk before separating channels: with servo and motor sharing one timer
configuration, the servo twitched audibly when the motor duty changed — the
50 Hz pulse train was getting duty-modulated by the motor channel's timer
sharing. Separating them removed the twitch and the whine in one move.

### 7.4 Data structures and state

The v2.2 Pi-side state is deliberately stateless: each tick builds the packet
from the current setpoint and writes it; there is no queue, no accumulator, no
state machine on the Pi for the throttle. The ESP32-side state is one small
bundle: `duty_current` (the last emitted duty, initialized 0), `duty_target`
(the compensated destination), and `setpoint_raw` (the last accepted raw value,
for the persist-last-good behaviour of R6). Three integers, no heap, no locks —
the entire v2.2 muscle state fits in a dozen bytes, exactly the size of state
we wanted for a system whose whole job is "one number in, one smooth duty out."

### 7.5 Failure behaviour contract

We defined, on paper before Day 35, what the system must do in each failure
mode, and we tested the ones we could:

- **Corrupted frame (CRC fail):** drop, hold `duty_current` unchanged. The
  robot continues at the last good speed for the few ticks until a clean frame
  arrives. Tested by deliberately corrupting byte 6 in a harness run: the motor
  held speed, no lurch.
- **Partial frame / missing terminator:** the parser times out and resyncs on
  the next 0xAA 0x55 magic; bounded-time by construction. No watchdog trip.
- **No frames at all (cable unplugged):** the S3 holds `duty_current` — a known
  risk, bounded by our physical master switch; a production link-timeout that
  ramps to zero was logged as debt.
- **Command 0 (stop):** immediate short-brake, duty exactly 0, wheels locked.
  Tested every sweep.
- **Overshoot on the low side:** a commanded drop from 100 % to 20 % is a
  controlled ramp down (duty decrements at `duty_step` per tick), *not* an
  instant short-brake, so the vehicle decelerates rather than nose-dives — but
  a commanded 0 still short-brakes, because "stop now" is a safety verb and
  "slow down" is a comfort verb.

The interface contract in one paragraph: **Pi sends `speed% × 10` as a 16-bit
big-endian value in a 10-byte CRC8 frame at up to 100 Hz; ESP32 parses it
bounded-time, compensates the dead zone, ramps the duty toward target within
the tick budget, and emits 20 kHz 8-bit PWM to the TB6612FNG while the servo
stays on its own 50 Hz channel.** That sentence, plus section 10's numbers, is
the complete deliverable of v2.2.

---

## 8. Architecture / data-flow flowchart

The second mandatory flowchart. It shows how a speed *intention* born in the
Pi's planner becomes wheel rotation, and how the measurement loop closes back
into our calibration file. Every edge is labelled with the real contract from
section 7.

```mermaid
flowchart TD
    P1[Pi planner: decides speed% 0..100<br/>at the 100 Hz tick] --> P2[raw = speed x 10<br/>0..1000, 0.1% resolution]
    P2 --> P3[Build 10-byte frame<br/>AA 55 | flags | 0x01 | reserved | hi lo | CRC8 | 0D]
    P3 --> P4[UART TX 115200 baud<br/>~0.87 ms per frame]
    P4 --> E1[ESP32 UART RX ISR<br/>assemble until 0x0D]
    E1 --> E2{CRC8 + magic valid?}
    E2 -- No --> E3[Drop frame, hold last duty<br/>no lurch, persist setpoint]
    E2 -- Yes --> E4[Extract setpoint 0..1000]
    E4 --> E5[Dead-zone offset ~20/255<br/>+ linear map to duty 0..255]
    E5 --> E6[Per-tick ramp<br/>+4 duty units per 10 ms]
    E6 --> E7[LEDC motor channel<br/>20 kHz 8-bit -> TB6612FNG]
    E7 --> E8[Drive motor -> wheels<br/>short-brake when duty = 0]
    E8 --> M1[Measured course: 3.0 m<br/>stopwatch, 3 reps per speed]
    M1 --> M2[Linear fit v vs duty<br/>R2 >= 0.97 gate]
    M2 --> P1[Return: calibrate dead zone<br/>and confirm battery flatness]
```

Reading the flow: the Pi's planner produces a percentage (P1); scaling to
0.1 % resolution (P2) feeds the frame builder (P3); the frame crosses the wire
in under a millisecond (P4); the ESP32's ISR assembles and validates it (E1,
E2); bad frames are dropped with the last-good duty persisting (E3); the good
setpoint is dead-zone-compensated and mapped to duty (E5); the ramp shapes it
for current safety (E6); the LEDC emits at 20 kHz (E7); physics does the rest
(E8); and the measurement loop — stopwatch on a 3.0 m course — is the only
"feedback" in v2.2, feeding the calibration file (M1, M2). Note deliberately:
**there is no in-flight velocity feedback yet** — the loop closes through the
human plus stopwatch during calibration only. The absence of a sensor node on
the right edge is the map of what v2.2 *isn't yet*.

---

## 9. Errors, failures, and root-cause analysis

The original short CHANGE.md records exactly one "Key error fixed": the audible
whine at 50 Hz PWM. The template demands we use that as the seed and expand
every step — and honest journaling demands we also record the smaller errors
the version threw at us, because the whine never existed in a vacuum. Each is
recorded with symptom → hypotheses → investigation → root cause → fix →
prevention, in the order we met them.

### 9.1 The 50 Hz motor whine — the headline bug

**Symptom.** On the afternoon of Day 34, the first prototype with the motor
driven through the shared-PWM setup produced a loud, high-contrast buzzing/whine
from the drive motor whenever it was powered — worst around mid-duties. The
sound was a continuous drone at roughly 50 Hz with audible harmonics at 100,
150, 200 Hz; at ~50 % duty it was loud enough to be heard across the lab, and
it changed pitch slightly as the motor loaded. The robot was at rest (wheels
free), so there was no wheel noise to blame; it was unambiguously the motor
assembly.

**Initial hypotheses (our honest guesses, in order).** (1) "Mechanical — the
gearbox is resonant." (2) "It's the servo creeping." The MG995 twitches at 50 Hz
by design; maybe coupling. (3) "We're overdriving something — too much current."
A vague guess with no mechanism. (4) The correct one, which came late: "It's
the PWM switching frequency being audible through the coil."

**Investigation.** Three steps. First, we killed variables: servo disconnected,
motor only, wheels free, at rest — the whine persisted, killing hypothesis (2).
Second, a phone spectrum app plus a 6 € USB audio interface showed a clear
fundamental at ~50 Hz with decaying harmonics to ~1 kHz, and the fundamental
tracked the *PWM* rate, not the motor speed — this killed hypothesis (1) and
confirmed the driver was chopping at 50 Hz. Third, the moment of insight, we
computed the ripple integral (C2): ΔI ≈ V·d·(1−d)/(f·L). At 50 Hz and L ≈
0.4 mH the formula gives a wildly discontinuous current (idealized ~92 A;
physically the inductor can't smooth at all). The pulses slam the coil every
20 ms, and magnetostriction plus commutation slap excite the structure at 50 Hz
and harmonics: the motor is mechanically singing the chopping frequency.

**Root cause (with mechanism).** The motor PWM was being generated at 50 Hz —
because the first prototype reused the servo's timer configuration for the
motor channel (the exact sharing that R3 later forbade). A 50 Hz PWM on a
brushed motor whose coil time constant (L/R ≈ 0.4 mH/0.8 Ω ≈ 0.5 ms) is 40×
shorter than the 20 ms switching period means the current fully collapses and
rebuilds every cycle: a sawtooth of spikes, not smooth current. Those spikes
(a) create the acoustic whine, (b) waste energy as iron/copper loss, and
(c) produce a much lower *average* effective torque — which is why the robot
also felt gutless at low duty. The bug was not "the motor whines"; the bug was
"the PWM frequency is inside the audible band AND below the motor's ability to
integrate the current."

**Fix (exact change).** Two-part. Keep the servo exactly where it belongs —
50 Hz, 1–2 ms pulse, on its own LEDC channel (servos are *built* for a 50 Hz
command train; changing that would break the MG995's position protocol). Move
the motor to a dedicated LEDC channel at **20 kHz, 8-bit** (duty 0–255). That
single frequency change takes the idealized ripple from ~92 A to ~0.23 A —
inaudible, energy-smooth, and the motor finally felt like a motor. The servo
twitch from the shared-timer configuration vanished at the same moment.

**Prevention.** Requirement R3 was written into the interface contract: servo
and motor are *different animals* and never share a timer/channel/frequency
configuration. The lesson is in the build checklist — "check the frequency
domain of every PWM channel before power-on" — and it is the anchor lesson of
section 11. We also added a bench rule: before any motor drive test, spin the
motor at ~50 % duty with wheels free and *listen*; a whine at power-up is now a
diagnostic for "wrong PWM frequency," not an accepted quirk.

### 9.2 The "dead zone that wasn't there until we looked" error

**Symptom.** On the first sweep, commanded 0 % stopped correctly, but
commanded 20 % produced *nothing* — no wheel rotation, no visible creep. The
robot sat there at "20 %" for a full second. Team reaction: "the motor is
broken / the map is wrong / the ESP32 didn't get the packet."

**Initial hypotheses.** (1) "Packet lost — the 0 in the CRC slot bit us."
(2) "The map is wrong: 20 % → 0.2 × 255 ≈ 51 duty should be plenty." (3) "Motor
stalled." Hypothesis (2) felt right, which is why it was the wrong one to hold
on to.

**Investigation.** We re-sent the command with the wheels lifted — the wheel
spun freely. We re-sent on the ground — nothing. The difference between
free-spinning and loaded is the clue: it's not the packet, not the map (51 duty
on a free wheel spins), it's that 51 duty cannot overcome **static friction
torque** on a ~2.8 kg robot. We swept 0–20 % in 2 % steps on the ground and
found the threshold: **the wheel reliably turned only above ~8 % duty** (duty ≈
20 on the 0–255 scale); between 2 % and 7 % it was intermittent — sometimes a
twitch, sometimes nothing.

**Root cause.** The torque–speed equation (C1) again, at the stall boundary.
Below duty such that V_batt × duty < I_static × R_arm + k_e·0, the motor cannot
break static friction. At 7.4 V, 8 % duty is 0.59 V average; with R_arm ≈ 0.8 Ω
and a static-friction-equivalent current of ~0.7 A, the breakaway point lands
right there. This was not a code bug — it is a *physics* feature of every
brushed motor, and we hadn't derived the breakaway point, so we were surprised
by our own robot.

**Fix.** Dead-zone compensation in the mapping (section 7.3): a measured offset
of ~20/255 duty is added to any nonzero setpoint so that commanded 5 % produces
visible creep, while command 0 still means a true short-brake stop. The offset
is applied *only above zero* — preserving the semantic difference between
"0 % (stop, wheels locked)" and "5 % (creep)". We documented the measured
breakaway duty (≈ 8 %) in the calibration file as a first-class constant, not a
magic number.

**Prevention.** The calibration sweep must always include the low region
(0–20 % in fine steps) and must always be run *on the ground, loaded*, because
free-spinning hides exactly this effect. A first-principles note now lives next
to the map: "compute the breakaway duty before trusting any low-speed
command." Every future robot that changes mass or motor re-runs this
measurement.

### 9.3 The CRC stub that proved the harness didn't test the reject path

**Symptom.** During code review on Day 36, a team member asked "what happens if
byte 8 is wrong?" and we realized we did not know — because the sweep harness
*always* sends `0` in the CRC slot (line 6 of pwm_control.py), so the
ESP32's reject path had never been exercised with a real corrupt frame.

**Initial hypotheses.** "The parser probably just drops it." "The CRC is
defensive theater anyway."

**Investigation.** We injected a deliberately corrupted frame (flipped byte 6)
into a bench run with the wheels off the ground. The motor held the previous
duty for one tick and continued — exactly the R6 behavior we had specified on
paper but never *proved*. The contract was real, but our harness had run with a
shortcut that left the rejection path untested for two days.

**Root cause.** A test harness that never sends bad frames cannot prove the
parser's failure path. The `0` in the CRC slot was a readability choice that
quietly removed the negative test case. No production code was wrong — the *test*
was incomplete, which is its own kind of bug.

**Fix.** Documented the stub (this section), and the next version's harness
sends a rotation of {valid, corrupt-CRC, corrupt-magic, truncated} frames so
the reject path is exercised on every run. The contract behavior itself was
verified and kept.

**Prevention.** Test-negative-before-positive: any parser contract must have a
negative test in the same harness as the positive tests. "We only test what we
feed" is now a standing review question.

### 9.4 The run-to-run spread that was really battery sag

**Symptom.** The first three-run repeatability test at 80 % duty gave
1.52, 1.39, 1.48 m/s — a 9 % spread, inside our ±10 % criterion but
*uncomfortably* so, and the trend was downward across the three runs. At 100 %
the spread grew: 1.78, 1.65, 1.69 m/s, ~8 %. The robot was getting slower as
the session went on.

**Initial hypotheses.** (1) "Thermal — the motor or driver heating up."
(2) "Measurement error — the stopwatch person is slacking." (3) "Gearbox
friction warming the grease." Nobody said "battery" first, which is the honest
and embarrassing truth.

**Investigation.** We measured pack voltage under load with a multimeter at the
battery leads: 7.9 V fresh off charge, sagging to 7.5 V at the 2.2 A
acceleration peak and 7.3 V toward the end of a 30-minute session. At 100 %
duty, a 0.4 V sag on a 7.4 V supply is a 5.4 % average-voltage loss, and since
speed ∝ (V_avg − I·R_arm), the speed followed it down almost 1:1.

**Root cause.** 2S LiPo with ~60 mΩ total internal resistance; 2.2 A peaks
drop ~130 mV on their own, and cumulative drain across a session lowers the
rest voltage further. An open-loop duty axis has no way to know the supply
changed, so "80 % duty" means 1.52 m/s at the start and 1.39 m/s later. This is
C1 in its purest form: duty is not speed, and the missing variable is supply
voltage.

**Fix (process, not just code).** Two parts. First, all repeatability
measurements in section 10 were run with the pack freshly charged and
recharged between every three-rep block, with pack voltage recorded before and
after each block so the numbers are comparable. Second, the per-tick ramp and
dead-zone map already give us *repeatable-within-a-charge* behavior; true
supply-invariance is closed-loop territory (encoder + voltage compensation) and
was formally deferred to the next version. We accepted the ±10 % criterion as
the honest bound of an open-loop axis on a sagging pack.

**Prevention.** Every verification protocol now starts with "charge the pack,
log V_batt before and after" as a first-class step, and every run-to-run
comparison is voltage-normalized. The mental model "open-loop duty is sensitive
to V_batt; plan the test with the battery state constant" is now permanent.

### 9.5 The servo twitch that revealed channel sharing (companion to 9.1)

**Symptom.** While debugging 9.1, with the motor PWM still at the wrong
frequency, the steering servo audibly twitched every time the motor duty
changed — a click-and-hold artifact at each speed step.

**Initial hypotheses.** (1) "Servo is dying." (2) "Servo is being reset by
current draw." (3) "Power rail noise."

**Investigation.** A logic analyzer on the servo signal line showed the 50 Hz
pulse width being *modulated* by motor transitions: exactly when the motor
channel updated, the servo pulse width wavered. That is the signature of the
two channels sharing one timer configuration on the LEDC peripheral.

**Root cause.** Shared timer. Once we split the channels (motor 20 kHz, servo
50 Hz, independent), the twitch disappeared with the whine. The two symptoms
had one cause: **one PWM domain contaminating the other** because we had let
the servo and motor share a timer.

**Fix / prevention.** Same as 9.1: R3 (separate channels, separate
frequencies), plus the standing rule that the servo domain and the motor domain
are inspected separately at power-on. The twitch and the whine were one bug; we
learned that lesson once and wrote it as a requirement.

### 9.6 Summary table of errors

| # | Error | Root-cause family | Fix | Prevention rule |
|---|---|---|---|---|
| 9.1 | Audible 50 Hz motor whine | PWM frequency inside audible band; coil can't integrate at 50 Hz | Motor LEDC @ 20 kHz 8-bit; servo stays 50 Hz on own channel | R3: never share timer/channel between servo & motor |
| 9.2 | "20 % does nothing" | Breakaway dead zone (static friction) below ~8 % duty | Dead-zone offset +20/255 above zero; fine low-region sweep | Compute breakaway duty before trusting low speeds |
| 9.3 | Harness never tested CRC reject path | CRC slot stubbed to 0 in test code | Documented stub; negative frames in next harness | Test-negative-before-positive |
| 9.4 | 8–9 % run-to-run speed spread | Battery sag ~0.4 V under load | Voltage-normalized test protocol | Log V_batt before/after every block |
| 9.5 | Servo twitch on motor update | Shared LEDC timer, cross-domain contamination | Separate channels | Inspect each PWM domain at power-on |

---

## 10. Verification and metrics

The acceptance criteria were written on Day 34 (section 3); here is the record
of what we measured on Day 36 and how we judged it. Honesty rule: we report the
spread, not just the mean.

### 10.1 Test procedure

Setup: flat lab floor (the carpeted WRO mat was not yet taped out), fresh 2S
pack recharged between every three-rep block, V_batt logged before/after each
block, and a 3.0 m measured course with tape at both ends. The sweep harness
(pwm_control.py) commanded 0/20/40/60/80/100, one second per step. At each
speed we timed three traversals of the 3.0 m course with a stopwatch (one
operator timing, one holding the robot at the start line, one operating the
harness). We also ran a fine sweep 0–20 % in 2 % steps on the ground to resolve
the dead zone, and repeated the whole matrix after an hour-long cooldown with a
freshly charged pack to confirm stability.

### 10.2 Raw numbers

Steady-state speed vs commanded duty, mean of 3 reps, V_batt 7.9 V → 7.8 V
after each block:

| Commanded speed % | raw (×10) | Duty (0–255) | Rep1 (m/s) | Rep2 (m/s) | Rep3 (m/s) | Mean (m/s) | Spread (max−min) |
|---|---|---|---|---|---|---|---|
| 0 | 0 | 0 (short-brake) | 0.00 | 0.00 | 0.00 | 0.00 | 0.00 |
| 20 | 200 | 51 + 20 offset ≈ 71 eff. | 0.36 | 0.34 | 0.35 | 0.35 | 0.02 |
| 40 | 400 | 102 + 20 ≈ 122 | 0.73 | 0.71 | 0.72 | 0.72 | 0.02 |
| 60 | 600 | 153 + 20 ≈ 173 | 1.08 | 1.05 | 1.06 | 1.06 | 0.03 |
| 80 | 800 | 204 + 20 ≈ 224 | 1.42 | 1.40 | 1.41 | 1.41 | 0.02 |
| 100 | 1000 | 255 | 1.80 | 1.77 | 1.79 | 1.79 | 0.03 |

Linear fit of mean speed vs commanded % across all six points:
**R² = 0.995**, slope ≈ 0.0179 m/s per %, intercept ≈ +0.005 m/s. The +20/255
dead-zone offset lifts the low end so even commanded 20 % moves at 0.35 m/s
rather than sitting still. Dead-zone fine sweep: wheel reliably rotates above
**8 % duty** (≈ 20/255) on the ground; below 8 % intermittent or stationary.
Ramp behaviour: at a 0→100 step, duty slews at 4 units/tick, settling to within
5 % of target in ~180 ms; launch current peaked at **2.2 A** (below the TB6612
3.2 A peak, the ramp keeping the *average* under 1.2 A continuous). Current at
cruise: 0.9 A. Acoustic check: with motor at 20 kHz, no peak above ambient
below 16 kHz at 1 m; the pre-fix 50 Hz setup had shown a clear ~50 Hz
fundamental with harmonics to ~1 kHz. Link timing: 10-byte frame ≈ 0.87 ms on
the wire; the 100 Hz loop kept every command inside the 10 ms tick with ~5 ms
margin; watchdog counter showed zero resets over all sweeps. The v2.x headline
speed of **1.8 m/s** reproduces at 100 % duty — our sanity anchor held.

### 10.3 Pass/fail against acceptance criteria

| Criterion | Result | Verdict |
|---|---|---|
| 1. Monotonic speed, R² ≥ 0.97 | R² = 0.995, monotonic at every step | PASS |
| 2. Repeatability within ±10 % | Worst spread 0.03 m/s ≈ 2.7 % of 1.1 m/s; all well under 10 % | PASS |
| 3. No audible whine at rest | No peak below 16 kHz; pre-fix comparison recorded | PASS |
| 4. Dead zone characterized + 5 % creeps | Breakaway = 8 % duty; commanded 5 % produces visible creep via offset | PASS |
| 5. 100 Hz loop unaffected; no watchdog trip | 0.87 ms frames, 5 ms margin, zero resets | PASS |

Five for five. We recorded the verdicts on Day 36 before the cooldown test; the
cooldown re-run (fresh pack) reproduced all five means within 0.03 m/s, so the
PASS was not a fresh-battery artifact.

### 10.4 What we trusted vs what we still distrusted

After v2.2 we trusted: (a) the linearity of the axis (R² 0.995 is a number we
can plan an S-curve against); (b) the dead-zone offset as a measured constant;
(c) the frequency-domain separation (R3) — the whine is dead and we know *why*,
which is worth more than the silence. We still distrusted: (a) **battery sag** —
our protocol controlled it, but race-day robot will not be recharged between
runs; this is the sharpest open debt; (b) the *repeatability* of low-speed creep
under load variance — the 20 % point depends on the offset and pack state more
than the high end does; (c) the lack of any in-flight speed feedback — the open
loop is calibrated, but it is still open. On Day 36 we said it out loud: "we
have calibrated the instrument; we have not yet made it a closed loop."

---

## 11. Lessons learned — permanent mental models

Five lessons came out of v2.2 that will change how we engineer every version
after this one, each connected to a concrete future risk it prevents.

**L1 — Servo PWM and motor PWM are different animals; tune them separately.**
The version's stated lesson, earned the hard way. Servos are commanded by a
50 Hz, 1–2 ms pulse protocol; the MG995's *position* semantics depend on that
cadence. A motor wants the highest frequency its coil can integrate — 20 kHz,
where the ripple formula (ΔI ∝ 1/(f·L)) makes the current smooth. The risk this
prevents: any future version adding a new PWM-driven actuator will not blindly
share a timer configuration. The mental model is "one PWM domain per physical
actuator family, verified at power-on."

**L2 — Open-loop duty is not speed, and never will be.** The torque–speed
equation ω = (V·duty − I·R_arm)/k_e is a physical law, not a tuning problem.
Battery sag, load, slope, and tire compression all enter through I and V, and
the duty axis cannot see them. The risk this prevents: every future controller
(Stanley in v6.x, the mission planner in v7.x) must be designed knowing the
plant's gain drifts with pack voltage — or must close the loop. We now budget
"open-loop axis error ≈ battery sag fraction" in every design estimate.

**L3 — Assign timing-critical jobs to the muscle, not the brain.** Linux on the
Pi 4B cannot schedule microsecond-accurate PWM while the vision pipeline runs
at 640×480@30. The ESP32-S3 owns the real-time domain, and v2.2 proved the
division of labour: Pi computes *intent*, ESP32 owns *signal*. The risk this
prevents: future versions keep scheduler-sensitive work off the Pi, and the
200 ms watchdog stays a real-time discipline, not a source of resets.

**L4 — Characterize the dead zone on the ground, loaded, before trusting
low-speed commands.** Our "20 % does nothing" moment was a physics feature we
had not derived. The breakaway duty (~8 %) is a first-class constant in the
calibration map now. The risk this prevents: parking maneuvers (v7.x, ±2 cm),
crawl approaches, and any low-speed precision task will silently fail below
breakaway torque if we trust the identity map. Every mass or motor change
re-runs the measurement.

**L5 — Test the negative path with the same seriousness as the positive path.**
The CRC stub that left the reject path unexercised for two days was a *test*
bug, not a code bug, and it is the kind that survives to race day. The risk
this prevents: link corruption, sensor dropout, and parser edge cases are where
competition robots die; harnesses must feed the failure frames they claim to
guard against. "If your harness never sends garbage, your parser has never been
tested" is now a standing review question.

A sixth meta-lesson shaped the whole document: **the moment of insight is
almost always a derivation, not a guess.** The whine was not fixed by trying
things; it was fixed by writing ΔI = V·d·(1−d)/(f·L) and letting the numbers
show us where the frequency had to go. We will reach for the equation first,
the screwdriver second.

---

## 12. Code in this snapshot

`pwm_control.py`

---

## 13. Bridge to the next version

What v2.2 unlocks is a **calibrated speed axis**: the Pi can now command any
speed from 0 % to 100 % and get a repeatable, linear vehicle speed (R² 0.995),
with a measured dead zone compensated and a current-safe ramp built into the
muscle. That is the instrument every later layer assumed existed: v3.x's sensor
calibration can trust that a commanded speed is a real speed; the future
planner can draft S-curves against a linear plant instead of a binary actuator.
The 50 Hz whine is gone, the servo/motor frequency domains are separated by
requirement, and the open-loop axis has honest, documented bounds (±10 % under
controlled battery state).

The known debt, and why it must be attacked next: **the loop is still open.**
v2.2 calibrated speed but cannot *correct* speed — battery sag, load, and slope
push the plant off its calibration curve, and section 10.4 proved the spread is
real (~8 % at 100 % across a session). The next version, v2.3, must close that
loop or bound it further: add velocity feedback (encoder on the drive motor,
fed back over the link) so commanded speed becomes *measured* speed with a
correction path, and/or implement the S-curve ramping profile on the planner
side now that it has a linear axis to command. One line of reasoning for why
v2.3 must go there: a controller can compensate repeatable error (which v2.2
has proven ours is, within a charge) but cannot compensate chaos, so the next
highest-value move is measuring velocity and correcting the drift — turning the
calibrated instrument into a *stable* one, at which point the S-curve and the
later control stack finally have a trustworthy plant to sit on.

---
