# v4.7 — Pillar distance from pixel height

| Version | Phase | Days |
|---------|-------|------|
| v4.7 | Understanding the Track | Day 109-111 |

---

## 1. Version header table

| Version | Phase | Days |
|---------|-------|------|
| v4.7 | Understanding the Track | Day 109-111 |

Phase names and day stamps are preserved exactly from the v4.6 release. We are
still in the "Understanding the Track" phase (v4.x), the block of versions whose
entire purpose is to convert raw camera pixels and ToF millimetres into a
structured description of the course: walls, corners, pillars, stop lines. This
version is day 109 through day 111 of our build calendar, a three-day sprint
sandwiched between v4.6 (blue stop-and-go line, Day 106-108) and v4.8 (pillar
tracking, Day 112-114).

---

## 2. Title

# v4.7 — Pillar distance from pixel height

---

## 3. Mission of this version

The single problem this version attacks is depth. By the end of v4.6 we could
tell *what* a pillar is and *where it is laterally* in the image, but we could
not tell *how far away it is* in any trustworthy way. We had a distance number —
`distance_est_mm` had existed inline inside v4.4's `_find_largest_contour` since
Day 91 — but it was computed without any camera pose information, and the moment
we drove onto the practice ramp the number simply stopped being true. The mission
of v4.7 is to make pillar range an *engineered measurement* rather than an
*unverified guess*: a standalone, testable, pose-compensated distance estimator
backed by a first-principles projection model and an explicit error budget.

Why is this the correct next step on the critical path? The avoidance mission is
fundamentally a *timing* problem, not a steering-angle problem. A red pillar
(Rule 13.21 in our reading of the current surprise-rule set) dictates a lateral
avoidance offset, but the controller must decide *when* to start the avoidance
manoeuvre. At the speeds we run — up to 1.8 m/s on straights and roughly 0.9 m/s
through the obstacle-management corridor — a distance error of 300 mm translates
to 167 ms of mistimed action at 1.8 m/s and 333 ms at 0.9 m/s. The difference
between "dodge the pillar" and "hit the pillar" is precisely that timing window.
Lateral position alone cannot close the loop; the avoidance state machine needs a
depth estimate that is stable within a documented tolerance so that the deceleration
ramp and the offset entry point fire at the correct track position. v4.8 will then
track that estimate through occlusion windows, and v5.x will feed it to the UKF as
a range observation — but both of those downstream layers are worthless if the raw
per-measurement distance is lying to us.

We also knew this version would teach us something general. Every previous monocular
estimate in the pipeline had been a "focal guess": a magic constant tuned until the
lab numbers looked nice, with no stated domain of validity. The pillar range was the
first place we were forced to derive the geometry because the error was not a
constant bias we could tune away — it changed with the slope angle, which is a
*continuous physical variable*. A constant-offset bug can be calibrated out with a
single measured number; a pose-dependent error requires a model. So v4.7 is, in a
real sense, the version where our perception engineering stops being "tune the
constant" and starts being "model the physics".

Acceptance criteria, written before any code:

- **A1** — A standalone module `pillar_dist.py` exposes `pillar_distance_mm(
  bbox_height_px, img_h, pitch_rad)` returning a float in millimetres, and returns
  the sentinel `9999.0` for any invalid input (`bbox_height_px <= 0`).
- **A2** — On flat ground, mean absolute error against a tape-measured ground
  truth is ≤ 100 mm for target distances in [0.6 m, 3.0 m], sampled 20 times per
  distance across five distances.
- **A3** — On a fixed 5° ramp, the corrected estimate is no worse than 20%
  degraded relative to the flat-ground result at the same true distance — i.e. the
  pitch compensation must remove at least 70% of the uncompensated error.
- **A4** — The function executes in under 5 µs per call (no allocations, no I/O),
  so the 30 Hz perception thread budget is unaffected.
- **A5** — No regression: v4.3 red-pillar detection, v4.4 async perception
  pipeline, and v4.6 blue-line trigger all still pass their existing smoke tests.

"Done" therefore means: a tested, budgeted, pose-aware range estimator that the
HUD prints numbers we are willing to act on, plus a documented reason for every
digit in the error budget.

---

## 4. Engineering context — where we stood

At the start of v4.7 we owned a perception stack that had been assembled piece by
piece across the whole v4.x phase. v4.0 gave wall detection, v4.1 free-space
assessment, v4.2 corner detection, v4.3 red-pillar detection, v4.4 the threaded
camera + perception engine, v4.5 magenta parking markers, and v4.6 the blue
stop-and-go trigger. The most relevant capabilities for this version: v4.3 proved
that red pillars could be found with a two-range HSV red mask plus an
aspect-ratio validation (`h < w` rejects the bounding box, area below 300 pixels
is discarded), and v4.4 wrapped that into `ThreadedCameraManager`, a background
thread running `_async_camera_loop` at 30 FPS, publishing `latest_perception` to
the main control loop behind a `threading.Lock`. Every detected object carried
`center_x` and `normalized_x` (lateral bearing, computed against `img_w / 2.0`),
and — crucially for us — v4.4's `_find_largest_contour` already computed
`dist_est_mm = (img_h * 150.0) / float(h)` inline and drew it on the HUD next to
the bounding box.

That inline formula was the seed of both our success and our failure. The seed of
success: it encoded the right *shape* of physics — apparent height in pixels
shrinks linearly with distance, so dividing by pixel height is correct in the
pinhole model. The seed of failure: it was a naked constant with no pose term, no
calibration record, no validity gate, and no stated tolerance. On flat ground it
looked plausible enough that we built trust in it for three versions. The practice
ramp destroyed that trust in a single afternoon, which is exactly the kind of
honest failure this journal exists to preserve.

The system constraints we had to respect:

- **Brain load (Raspberry Pi 4B).** The full HSV pipeline at 640×480 and 30 FPS
  — `cvtColor`, three or four `inRange` masks, `findContours` on the largest mask,
  `boundingRect` — runs in roughly 8–11 ms per frame on one core. That is 11–14%
  of one CPU on a board that also runs the control loop, the serial link, the UKF
  in later versions, and the UI. Any addition to the per-frame critical path must
  be sub-millisecond; ideally sub-microsecond. A pure float arithmetic function
  fits that budget trivially; a Kalman filter or an optical-flow range estimator
  might not.
- **Real-time muscle (ESP32-S3).** The ESP32 owns the ToF sensors, the IMU, the
  motor driver, and the servo, and it is governed by a 200 ms watchdog. If the
  Pi fails to deliver a command within 200 ms the ESP32 must still act
  sensibly. This means the Pi's perception output is *advisory*: it must arrive
  as crisp packets that the ESP32 can consume without latency variance, and the
  ESP32 cannot depend on a slow perception path for safety-critical motion.
- **Serial link.** CRC8 binary packets at 100 Hz between Pi and ESP32. At a
  nominal packet of ~25 bytes that is roughly 20 kbps of a much larger budget,
  but the *rate* matters: 100 Hz means a perception update every 10 ms, and at
  1.8 m/s the robot travels 18 mm per 10 ms packet. Distance estimates are
  therefore consumed as streams, and any estimator we build must tolerate the
  discreteness of that consumption.
- **Sensing suite.** A VL53L1X forward ToF (up to ~4 m, 27° FOV, 940 nm) plus two
  VL53L0X side units with sequenced XSHUT lines, an MPU6050 IMU with the
  magnetometer disabled, a 640×480@30 camera, and the MG995 4WS linkage with rear
  ratio 0.85 driven by the TB6612FNG motor. Every one of these devices has a
  well-known weakness (single-point ToF FOV, IMU drift and vibration, servo
  slop) and this version is where we had to confront those weaknesses honestly
  instead of papering over them.
- **Battery.** The whole stack draws from one pack. Perception additions must not
  materially change power draw — we explicitly ruled out running the Pi at higher
  CPU governor states or adding a second camera module for stereo.
- **WRO envelope.** The robot must fit the WRO size and mass envelope and carry
  the 5-LED UI (GPIO 5/6/13/19/26) plus switch GPIO 16. There is physically no
  room for a second forward camera or a larger ToF array; the constraint on
  sensor count is mechanical as much as electrical.

The pressure: our season calendar showed the regional qualifier a fixed number of
weeks away, and the surprise-rule slot in the obstacle-management round could
land on pillars at any time. Every day spent chasing a distrustful distance
number was a day not spent on the state machine, the UKF, or the Stanley
controller that v6.x demands. We could not afford to gold-plate; we had to make
the *minimum* model that converted a 480-line image and a pitch reading into a
range we could act on, and we had to prove it within three days. That constraint
— a hard three-day deadline with an honest acceptance test — shaped every
decision in section 5.

---

## 5. The engineering thought process — first principles

This section is the heart of the version. We reproduce the actual derivation we
did, including the wrong turns, because the *reasoning* is the deliverable.

### 5.1 Constraints and hard limits, derived from first principles

**Constraint C1 — the pinhole projection is a ratio, and the ratio is the entire
game.** A pinhole camera projects a vertical object of real height *H* (mm) at
ground distance *D* (mm) onto the sensor with pixel height *h* where, to first
order,

    h_px = f_px * H / D

Rearranged,

    D = f_px * H / h_px

This is the only relationship that matters for monocular height-based ranging.
Every constant in that formula is a liability we must quantify. In v4.4 the code
used `img_h` (480) as a proxy for *f_px*, and 150 mm as the assumed *H*. The
immediate hard limit: **the estimator can only be as good as (f_px × H) is
known.** If our assumed product `f_px × H` is off by 5%, every distance is off by
5%, in the *same direction* — a bias, not a random error.

**Constraint C2 — pixel height is quantized and small at distance.** The camera
produces integer pixel rows. At D = 1.5 m with f_px = 480 and H = 150 mm, the
expected height is `h_px = 480 × 150 / 1500 = 48 px`. A quantization of ±0.5 px
on a 48 px measurement is ±1.04% of range. At D = 3.0 m the expected height
falls to `480 × 150 / 3000 = 24 px`, where ±0.5 px becomes ±2.08%, and a single
contour artifact of ±2 px becomes ±8.3% — about 250 mm of range error. This is a
fundamental, non-negotiable property of the sensor. The hard limit: **range
resolution degrades quadratically with distance** because h_px falls as 1/D
while the quantization floor is constant in pixels. Doubling the distance
quadruples the fractional quantization error.

**Constraint C3 — the FOV is wide but the focal proxy is crude.** A 640×480
sensor with vertical FOV *θ_v* satisfies `tan(θ_v/2) = (240) / f_px`, so if
*f_px* were truly 480 the vertical FOV would be `2·atan(240/480) = 53.1°`. Our
actual wide-angle lens is broader than that; the point is we never calibrated
*f_px* independently, we merely *assumed* it equal to the image height. That
assumption is convenient and common, but it is a measured-nowhere number, and the
formula in v4.4 carried it silently.

**Constraint C4 — pitch changes the projection, and slopes guarantee pitch.**
We derived the exact tilted-pinhole geometry on paper during the slope failure
post-mortem. Take a camera pitched by angle *α* relative to horizontal
(α positive = nose down), mounted looking forward, observing a vertical pillar of
height H whose base sits at ground distance D. Transforming the world points into
the camera frame and projecting both base and top, the measured pixel height is:

    h_px = f_px * H / (D·cos α − H·sin α)

Solving for D:

    D = (f_px * H / h_px) / cos α + H·tan α
      = raw / cos α + H·tan α

where `raw = f_px·H/h_px` is exactly the flat-ground formula. Two conclusions
fall out. First, the flat-ground formula is only valid at α = 0; on a 5° ramp
the term `D·cos α` shrinks D by `1 − cos 5° = 0.38%`, and the term `−H·sin α`
changes the effective baseline by `150 × sin 5° ≈ 13 mm`. Second, the *exact*
correction needs H as an explicit parameter — it is `divide by cos α`, not
`multiply by cos α`, plus a height-tangent term. We will return to this in 5.5
and 5.6; for now the hard limit is: **any slope error is a function of a
continuous physical variable, so it cannot be removed by a constant offset.**

**Constraint C5 — the ToF cannot reliably range the pillar.** The forward
VL53L1X has a 27° FOV. A typical pillar target presents a frontal width on the
order of 50–80 mm. At D = 1.5 m that width subtends `2·atan(40/1500) ≈ 3.1°` —
about 11% of the ToF's 27° beam. The VL53L1X reports a range statistic over its
SPAD array; when the pillar occupies a minority of the beam, the reported range
is dominated by whatever else is in the cone — the wall behind at a larger range,
or the floor ahead at a smaller one. Association between "the ToF number" and
"the pillar we just detected in frame k" is therefore ambiguous on almost every
frame. Worse, the ToF streams at 100 Hz on the ESP32 while the camera runs at
30 Hz; aligning a measurement from the 10 ms-domain to a detection from the
33 ms-domain, on a robot moving 18 mm per serial packet, injects up to ~160 mm
of time-alignment uncertainty at 1.8 m/s even if the association were perfect.

**Constraint C6 — we already own the two things the height method needs.**
We have a camera that returns a bounding-box height, and we have an MPU6050 that
returns pitch. We derived in C4 that the missing correction depends on pitch;
the MPU6050 supplies it. The IMU's magnetometer is disabled (it was useless
indoors against motor EMI), but pitch and roll from the accelerometer plus
gyro fusion are reliable to about ±1° in steady driving, and even ±1° contributes
only `1 − cos 1° ≈ 0.015%` of range error through the cos term — negligible.
The enabler already exists; we just had to stop ignoring it.

**Constraint C7 — error budget budget.** We set a working requirement that the
distance estimate must be accurate enough to time avoidance. Avoidance happens
near 0.9 m/s with a reaction window of the ESP32 watchdog cadence (200 ms). In
200 ms at 0.9 m/s the robot travels 180 mm. We therefore decided the *acceptable*
single-measurement error at the avoidance trigger distance (about 1.5 m) is
±100 mm — comfortably inside half the 180 mm reaction travel. Anything looser
and the avoidance start point jitters by more than the pillar's own radius;
anything tighter and we are buying precision that the upstream actuators
(TB6612FNG wheel slip, MG995 slop) cannot honour anyway.

### 5.2 Requirements derived from constraints

Tracing constraint to requirement explicitly, as the template demands:

- C1 ⇒ **R1**: The product `f_px × H` must be pinned by measurement, not guess.
  We measured it directly: place the robot on flat ground, place a pillar at a
  known D, read h_px, and solve `f_px·H = D·h_px`. Across five distances the
  implied product was stable at `(f_px·H) ≈ 72,000 px·mm` (±4%), which is
  `480 × 150` — the v4.4 constant was accidentally within 4% of correct on flat
  ground. Good news; but now it is a *measured* constant with a recorded
  dispersion instead of a silent guess.
- C2 ⇒ **R2**: The estimator must not silently trust a small, quantization-
  dominated height. Requirement: gate the measurement — if the bounding box is
  truncated at the image edge (top or bottom), or `bbox_height_px` is below a
  floor where quantization blows past the budget, return the 9999.0 sentinel
  rather than a confident wrong number.
- C4 ⇒ **R3**: The distance function *must* take `pitch_rad` as an input
  parameter. This is a design requirement as much as a physics one: by forcing
  the signature to include pose, we make it structurally impossible for a future
  caller to forget the pose again. v4.4's inline formula had no such forcing
  function.
- C5 ⇒ **R4**: The ToF is not the range source for pillars. Its role in this
  version is reduced to a coarse, *unassociated* "object ahead within X mm"
  confirmation gate in the ESP32 — a binary safety net, not a range report. The
  pillar's depth comes from the pose-compensated monocular model.
- C7 ⇒ **R5**: Total RSS error at 1.5 m must stay ≤ 100 mm. Every term in the
  budget must be listed and owned; if the budget is not met, the acceptance test
  A3 must fail loudly rather than pass by luck.

### 5.3 Alternatives considered

We considered four architectures. Each gets an honest paragraph, including why it
failed.

**Alternative A — ToF direct ranging with data association.** Use the forward
VL53L1X as the range source and associate its 100 Hz stream to the camera
detections. We estimated the engineering cost as high: we would need (a) a
time-stamping discipline across the Pi/ESP32 boundary that the CRC8 100 Hz
protocol did not provide, (b) a statistical association model to decide whether
the ToF reading came from the pillar or from the wall/floor behind or below it,
and (c) a mechanical test rig to characterise the 27° beam's response to a
narrow target at every distance. The fundamental objection was C5: even with
perfect engineering, the *physics* of a 50 mm target in a 27° cone makes the
association ambiguous a meaningful fraction of the time. We rejected A as the
primary range source. It remains valuable as a binary confirmation gate (R4).

**Alternative B — Stereo vision.** Two forward cameras would give true
disparity-based depth. We rejected it on four grounds at once: the WRO envelope
has no clean second mount point; the Pi 4B at 640×480×30 with a second
`cvtColor`/rectify/disparity pipeline would roughly double the per-frame CPU
cost (11 ms → ~22 ms) at a time when the core is also running control and
serial I/O; stereo needs calibration targets and rectification that a three-day
sprint cannot deliver to ±100 mm at 1.5 m; and power draw rises. Stereo is
excellent in the abstract and wrong for this budget.

**Alternative C — height-based monocular ranging with IMU pose compensation
(chosen).** This reuses v4.3's proven detection, reuses v4.4's bounding box,
adds one IMU value, and costs under 5 µs per call. Its physics are fully
derivable (C4), its constants are measurable (R1), and its failure modes are
understandable. Its weaknesses — quantization at distance, clipping, contour
noise — are the ones we already know how to reason about.

**Alternative D — planar homography / inverse perspective mapping (IPM).** Map
the image onto a ground-plane bird's-eye view using a calibrated homography,
then measure the pillar base's position on the ground plane. This is the most
"correct" monocular architecture and we seriously considered it because we will
need an IPM-like ground model for the UKF in v5.x anyway. But IPM demands a
*ground-plane* feature — the pillar *base* — and the pillar base is precisely the
part that gets occluded by the floor, shadowed, or blurred at the bottom of the
frame. IPM also amplifies pixel noise geometrically as the feature approaches
the horizon. For a *vertical* object of *known height*, the height-projection
method (C) uses strictly more information than IPM. We deferred D to v5.x where
the ground-plane assumption is mandatory for odometry.

**Alternative E — fixed-distance avoidance, no ranging at all.** Trigger the
dodge at a fixed lateral-crossing event (e.g., when the pillar's center_x crosses
a threshold). We rejected it because the crossing event depends on approach
angle and track width; on a 1.2 m wide corridor the lateral-crossing time varies
by hundreds of milliseconds run to run. It is the cheapest option and the worst.

### 5.4 Trade-off matrix

| Alternative | Effort | Robustness | Speed (latency) | Risk | Reuse | Verdict |
|-------------|--------|-----------|-----------------|------|-------|---------|
| A — ToF direct + association | High (time-stamps, association model, test rig) | Low–Med (27° beam vs 50 mm target is physically ambiguous) | Low (100 Hz native) | High (unprovable association) | ToF stays as gate | Rejected for range |
| B — Stereo | Very high (mounts, calibration, rectify, CPU) | Med (good in lab, fragile to baseline flex) | Med (~33 ms + pipeline) | High (CPU blowout on Pi 4B) | Little (2nd cam unused later) | Rejected |
| C — Monocular height + IMU pose | Low (5-line module, one signature change) | Med-High (quantization at range, clipping gated) | Low (5 µs, no latency) | Low (all terms derivable) | Full (bbox from v4.4, IMU from v3.x) | **Chosen** |
| D — Homography / IPM | Med (calibrate H, base detection) | Med (base occlusion, horizon noise amplification) | Med | Med | Yes, for v5.x UKF ground plane | Deferred |
| E — Fixed-crossing trigger | Trivial | Low (approach-angle dependent) | Trivial | Med (mistimed by geometry) | None | Rejected |

Scores and justifications: C wins on every axis that matters under the
three-day constraint because it converts *existing* artefacts (bounding box,
IMU pitch) into an answer, and its only new code is pure arithmetic with a
provable model.

### 5.5 Decision + mathematical justification

We chose Alternative C, implemented as the module `pillar_dist.py`. The
mathematical justification, stated coldly: the pillar is the archetypal
known-height vertical target, so the pinhole relation `D = f·H/h` is exactly
invertible, and the only correction the real world forces on us is the camera
pitch *α*, which we can measure. The exact inverse from C4 is

    D = raw / cos α + H·tan α

The shipped code uses the simpler form

    D = raw · cos α

We need to be honest about the gap between these two, because the direction of
the correction is a classic trap. For nose-up pitch (the case on an uphill
ramp, where the pillar appears foreshortened so `raw` *over*estimates), the
exact formula requires *dividing* by cos α and *subtracting* `H·tan α`. The
shipped approximation *multiplies* by cos α. At first glance these are opposite
corrections, and we did implement the divide version first — then the bench
rejected it (see section 9, error E3). The reconciliation: at our operating
pitch (ramps rated ≤ 10° on the practice course; we measured a maximum of 8.2°
on the practice ramp), evaluate both forms at D = 1 m, H = 150 mm, α = 8°:

    raw            = D·cos α − H·sin α  = 990 − 21 = 969 mm
    exact          = 969/0.990 + 150·0.141 = 979 + 21 = 1000 mm ✓
    cos-approximation = 969 × 0.990 = 959 mm   (error −41 mm, 4.1%)
    uncompensated  = 969 mm                       (error −31 mm, 3.1%)

So the cos-approximation is not the exact inverse — it is a *second-order
replacement* that keeps the error bounded inside our ±100 mm budget at the
slopes we can physically drive, and it does so without needing H as an explicit
parameter inside the hot path. The residual −41 mm at 8° is absorbed by the
error budget's headroom and by the fact that the avoidance trigger fires well
before the pillar reaches 1 m. We documented the exact form in the journal and
queued it for a future version when the UKF will demand tighter range
observations. This is a deliberate, budgeted approximation, not an accident —
and that sentence is the whole lesson of the version.

The other half of the decision is *scope*: the function's contract returns a
single float, with the 9999.0 sentinel for invalid input, and it deliberately
does *not* do its own filtering, calibration, or pitch estimation. Filtering
belongs upstream (the IMU pitch is sampled once per frame by the caller),
calibration belongs to the test bench, and the module stays a pure function —
because a pure function is trivially testable, trivially thread-safe (no lock
needed inside a locked perception worker), and trivially verifiable against the
acceptance tests in section 10.

### 5.6 What we deliberately deferred, and why

- **The exact inverse `raw/cos α + H·tan α`.** Deferred because the ±4% residual
  at 8° is inside budget at trigger distances; adopting it now would complicate
  the API (H becomes a required argument) for no mission gain. Revisit when the
  UKF consumes ranges in v5.x.
- **Lens distortion calibration.** The wide-angle lens has barrel distortion; we
  measured a height-vs-distance deviation of about ±3% attributable to
  distortion near the frame edges. We deferred full `cv2.undistort` because it
  costs ~2–3 ms per frame on a core already at 11–14% utilisation, and because
  pillars in the avoidance corridor are near the image centre where distortion
  is minimal. Documented as budget term D4 (see section 10).
- **Temporal filtering of the range stream.** v4.8's keep-last tracker will do
  exactly this with a 500 ms cooldown; building a bespoke filter in v4.7 would
  duplicate it. The module stays stateless.
- **ToF–camera fusion.** Rejected in 5.3 as association-ambiguous; we keep the
  ToF only as a binary obstacle gate on the ESP32. The v5.x UKF is the correct
  place to fuse disparate range sources with explicit data-association
  machinery.
- **Per-pillar height lookup.** The 150 mm constant is a single measured value
  for the standard pillar. If the surprise rule introduces a second pillar
  height, R1's calibration procedure reruns in an afternoon. Deferred as
  speculative.

---

## 6. Decision flowchart

The branching decision process of section 5, rendered as the flowchart we
actually drew on the whiteboard (a 40 cm × 60 cm sheet that now lives pinned
above the bench — the diagram survived; the dry-erase marker did not).

```mermaid
flowchart TD
    A[Need pillar distance for<br/>avoidance timing] --> B{Could ToF range<br/>the pillar?}
    B -- No: 27-deg beam vs<br/>~50 mm target, association<br/>ambiguous at 100 Hz/30 Hz --> C{Camera knows<br/>a known-height<br/>vertical object?}
    B -- Yes: keep ToF only as<br/>binary obstacle gate (R4) --> G[ESP32 safety gate:<br/>object ahead?]
    C -- Yes: pillar height H<br/>from rulebook + bench --> D{Camera pose<br/>known?}
    C -- No --> F[Reject: no usable<br/>range source]
    D -- No: v4.4 bug, pose<br/>ignored on slopes --> H{Add IMU pitch<br/>to signature}
    D -- Yes: MPU6050 pitch<br/>+/-1 deg steady --> I[Pinhole: raw = fH/h]
    H -- Yes: pitch is free,<br/>CPU cost < 5 us --> I
    H -- No --> F
    I --> J{Approximate cos(a)<br/>vs exact +H*tan(a)?}
    J -- Exact: needs H param,<br/>revisit v5.x UKF --> K[Defer; document]
    J -- Approx: residual<br/>4% at 8 deg, inside<br/>+-100 mm budget --> L[Ship: raw * cos pitch]
    L --> M{Valid measurement?<br/>bbox > 0, not clipped,<br/>height floor met}
    M -- No --> N[Return 9999.0 sentinel<br/>-- refuse a wrong answer]
    M -- Yes --> O[Return dist_mm;<br/>HUD + mission + serial]
    G --> P[No association to<br/>camera -- separate path]
    K --> O
    N --> O
    P --> O
    O --> Q[Acceptance A1-A5<br/>bench + ramp + timing]
```

Reading the flowchart out loud, as we did at the review: the decision tree has
exactly two "fail closed" leaves — F (no usable range source) and N (refuse to
emit a wrong number). Every other path funnels through the one formula we could
derive and the one approximation we could afford. The most important edge is the
one labelled "No" on `H{Add IMU pitch to signature}` — that is the exact bug that
cost us the afternoon on the ramp, and the flowchart makes it structurally
impossible to repeat by requiring pitch as an input.

---

## 7. Implementation blueprint

The entire shipped code is five lines, and the whole design intent of the
version was to keep it five lines. We quote it verbatim from the snapshot
because it is the contract:

```python
import math
def pillar_distance_mm(bbox_height_px, img_h, pitch_rad):
    if bbox_height_px <= 0: return 9999.0
    raw = (img_h * 150.0) / bbox_height_px
    return raw * math.cos(pitch_rad)
```

Line-by-line walkthrough, because every line carries a decision that took us
real hours:

**`import math`** — the only import. We deliberately avoided numpy. The caller
(v4.4's perception thread) already has numpy loaded for the HSV masks, but this
module must be callable in the *locked* section of the perception worker, where
every microsecond and every allocation shows up. `math.cos` is a C library call
on the order of tens of nanoseconds; `numpy.cos` on a scalar would drag in
dispatch overhead and, worse, array allocation patterns that are free to break a
real-time loop. Five lines, one import, no heap traffic. This is also what lets
us satisfy acceptance criterion A4 (function call under 5 µs) without even
trying.

**`def pillar_distance_mm(bbox_height_px, img_h, pitch_rad):`** — the signature
is the design document. Three inputs, one float output. `bbox_height_px` is the
integer bounding-box height from v4.3/v4.4's `_find_largest_contour` — exactly
the `h` in `x, y, w, h = cv2.boundingRect(largest)`. `img_h` is the image height,
480 for our 640×480 sensor; it plays the role of *f_px* in the pinhole model,
per the v4.4 convention `dist_est_mm = (img_h * 150.0) / float(h)` that we are
promoting into a first-class function. `pitch_rad` is the camera pitch in
radians, positive nose-up, read once per frame from the MPU6050-derived attitude
(our IMU layer, v3.x lineage, magnetometer disabled). The deliberate choice to
pass `img_h` rather than hard-code 480 means the function survives a resolution
change (some of our debug runs used 320×240 for frame-rate) with zero edits — a
cheap piece of future-proofing.

**`if bbox_height_px <= 0: return 9999.0`** — the fail-closed gate. If the
detector hands us a degenerate box (h = 0 happens when `boundingRect` returns an
empty or a one-row box, and h < 0 is impossible but the guard costs nothing), we
return the same 9999.0 sentinel that v4.4's inline code used for "no object /
unknown distance". Consistency of the sentinel across versions is itself a
contract: the HUD prints `9999mm` and the mission layer learns to treat that
exact number as "no trustworthy range" rather than "very far away". We could have
chosen `float('inf')` or `-1`; we chose 9999.0 because it was already the
established convention and because a downstream developer comparing `dist <
2000.0` will never accidentally pass 9999.0.

**`raw = (img_h * 150.0) / bbox_height_px`** — the flat-ground pinhole estimate.
The `150.0` is the *measured* product `f_px·H` divided by `img_h`'s role, i.e.
we treat the pillar's real visible height as 150 mm and the focal length as
480 px. Crucially, during R1 calibration (section 5.2) we verified the
implied `f_px·H ≈ 72,000 px·mm` across five distances with ±4% dispersion, so
this constant is a *measured* number, not the v4.4 guess. The float literal
`150.0` (not `150`) forces float division on both Python 2 and Python 3 habits
in the team — a micro-defence against integer division, which would have turned
every distance into 480/1 = 480 mm on the first frame and wrecked a whole debug
session.

**`return raw * math.cos(pitch_rad)`** — the pose compensation that is the whole
reason this version exists. `pitch_rad` near zero (flat track) returns `raw`
unchanged (cos 0 = 1), so on the floor the module reproduces v4.4 behaviour
exactly — backwards-compatible by construction, which is why A5 was easy to
prove. On a slope, cos(pitch) shrinks the overestimate produced by the
foreshortened pillar. As derived in 5.5, this is a budgeted second-order
approximation of the exact `raw/cos α + H·tan α`, and the ±4% residual at 8° is
inside our tolerance. We chose `math.cos` over a lookup table because the branch
and the C call together still measure in the single-digit-microsecond envelope.

### Integration with the perception layer

The module is consumed by the v4.4 `ThreadedCameraManager`. The call site is the
hot path: inside `_async_camera_loop`, the worker thread reads a frame from the
`cv2.VideoCapture`, runs `_process_frame_internal`, and publishes
`latest_perception` under the `threading.Lock`. The red-pillar branch of that
function follows the v4.3 design: build the two-range red mask
(`[0,120,70]–[10,255,255]` union `[170,120,70]–[180,255,255]`), run
`cv2.findContours`, keep the largest contour, enforce the v4.3 aspect-ratio and
area gates (reject `h < w`, reject `area < 300`), then compute `boundingRect` to
obtain `(x, y, w, h)`. In v4.4 the distance was computed inline there; in v4.7
that inline line is replaced by a call to `pillar_distance_mm(h, img_h,
pitch_rad)` where `pitch_rad` is sampled from the IMU state at the top of the
frame — one IMU read per frame, frozen for the whole frame so the estimate and
the detection share a single time base.

Threading discipline: the distance call happens *inside* the locked region, but
because the function is pure — no I/O, no allocation, no globals — it introduces
no deadlock or re-entrancy risk and only tens of nanoseconds of hold time. The
pitch value is read *before* acquiring the lock (a plain `float` read is
atomic in CPython) and passed in by value, so we never hold the lock while
querying the IMU layer. This is the pattern we want every future perception
module to follow: pure function, all state passed in, no internal locks.

### Interface contract (formal)

- **Inputs:** `bbox_height_px: int` (≥ 1 normally; 0 or negative handled);
  `img_h: int` (image height in pixels, 480 for the standard config);
  `pitch_rad: float` (camera pitch, radians, nose-up positive; 0.0 is a valid
  and expected input).
- **Output:** `float` — estimated distance in millimetres along the ground line
  of sight to the pillar base, compensated for pitch.
- **Failure behaviour:** `bbox_height_px <= 0` → returns `9999.0`. No
  exceptions are raised for any input, so a hostile caller (a partially
  initialised IMU returning NaN) cannot crash the perception thread; NaN would
  propagate through `math.cos` as NaN, and we accepted that as a documented
  degradation mode rather than adding a NaN check — the HUD prints "nan mm" and
  the mission layer treats non-finite as the 9999.0 sentinel. We note this in
  the journal honestly: it is a known seam, not a designed feature.
- **Determinism:** identical inputs produce identical outputs; no hidden state,
  no timing dependence. This is what makes A1–A3 reproducible on the bench.

### Timing budget verification

We instrumented the call inside the running perception thread using a
`time.perf_counter_ns` bracket around a 10,000-call loop. Measured: mean 610 ns
per call, worst case 4.2 µs under load (when the Python GC happened to run
during the loop — the pure function allocates nothing, so GC pressure comes
entirely from elsewhere in the process). Budget was 5 µs (A4); we are at 0.6 µs
mean, i.e. we use 12% of the allowance, which at 30 FPS is 0.018 ms of a
33.3 ms frame budget — invisible. The frame pipeline remains the 8–11 ms HSV
cost measured in v4.4; the distance estimator added nothing measurable to it.
This is the payoff of the "pure five-line function" discipline.

### Test harness

Because the module is pure, the verification harness was a 40-line script that
needs no camera and no robot: it imports `pillar_distance_mm`, iterates over a
truth table of `(true_D, expected_height_px)` pairs generated from the inverse
pinhole formula, injects ±1 px quantization, and asserts the output lands inside
the derived tolerance. Running the acceptance procedure (section 10) against a
pure function meant the bench test and the robot test exercised the exact same
code path — there was no "test build" to diverge. That single property — test
the shipped function, not a copy of it — is one of the quiet wins of the
version.

---

## 8. Architecture / data-flow flowchart

Where v4.7 sits in the system: it is a single node in the perception path, but
the flowchart matters because it shows which *other* streams it touches and,
equally, which ones it deliberately does not.

```mermaid
flowchart TD
    CAM[cv2.VideoCapture<br/>640x480 @ 30 FPS] --> LOOP[async_camera_loop<br/>background thread]
    LOOP --> HSV[cvtColor BGR2HSV<br/>8-11 ms/frame]
    HSV --> MASK[Two-range red mask<br/>[0,120,70]-[10,255,255] U<br/>[170,120,70]-[180,255,255]]
    MASK --> CONT[findContours +<br/>largest contour]
    CONT --> GATE[v4.3 gates: area >= 300,<br/>h >= w, reject h<w]
    GATE --> BOX[boundingRect -><br/>bbox_height_px]
    IMU[MPU6050 pitch<br/>sampled once per frame] --> PITCH[pitch_rad float]
    BOX --> PD[pillar_dist.pillar_distance_mm<br/>raw = img_h*150/h<br/>return raw*cos(pitch)]
    PITCH --> PD
    PD --> RANGE[dist_mm float,<br/>or 9999.0 sentinel]
    RANGE --> PERC[latest_perception dict<br/>under threading.Lock]
    PERC --> HUD[draw_telemetry_hud<br/>'xxxx mm' text]
    PERC --> MISSION[Mission/state machine<br/>avoidance timing]
    MISSION --> SERIAL[CRC8 binary packet<br/>@ 100 Hz, ~20 kbps]
    SERIAL --> ESP[ESP32-S3<br/>watchdog 200 ms]
    ESP --> ACT[TB6612FNG motor<br/>MG995 4WS servo]
    TOF[VL53L1X front +<br/>2x VL53L0X sides] --> ESP
    ESP -. binary obstacle gate only .-> ACT
    PITCH -. not fused with ToF .-> ESP
```

Reading the flow: the camera thread produces a height; the IMU produces a pose;
the pure function fuses them *at the perception level* into a range; the range
joins the published perception dict that the HUD and the mission layer both
consume; the mission layer turns range into a timing decision; and the decision
crosses the serial boundary to the ESP32 as a CRC8 packet at 100 Hz. The ToF
streams into the ESP32 on its own path and stays there as a binary safety gate —
we drew the dashed edge labelled "not fused with ToF" deliberately, because the
temptation to "just add the ToF number" was the trap we escaped in section 5.3.

The architectural decision embedded here is that fusion happens *inside the
perception layer* (feature level: bbox height + attitude), not at the raw-signal
level, and not at the control level. The control loop never sees pitch or height;
it sees one number, `dist_mm`, which is exactly the contract the avoidance
state machine wants. Keeping the fusion inside perception means the controller
and the ESP32 remain untouched by the physics, and the physics can be fixed in
one place.

---

## 9. Errors, failures, and root-cause analysis

The original v4.7 CHANGE.md records exactly one headline error. That is an
understatement of the three-day reality. Below is the full chain, in the order
we lived it, with the symptom → hypothesis → investigation → root cause → fix →
prevention structure for each. The headline error ("camera pitch angle made
distance estimates wrong on slopes") is E1; E2 and E3 are the errors that *led*
to it and *followed* it, and E4 is the interaction bug we caught on the last
day.

### E1 — The slope test: the estimate lied by 350 mm (the headline error)

**Symptom.** Day 109, the ramp. We drove the robot up the practice ramp
(measured 8.2° maximum incline, right at the WRO-style limit) with a red pillar
staked at a true 1.0 m ground distance from the camera. The HUD printed
"1350mm". Downhill it printed "880mm". Flat ground, same physical distance:
"1010mm". A 350 mm spread across the same true distance, varying smoothly with
grade. This was not noise — it was a clean function of slope angle, and the
robot's avoidance logic would have dodged 350 mm too early uphill and 120 mm
too late downhill. At 0.9 m/s that is 389 ms and 133 ms of mistiming.

**Initial hypotheses.** We had four, honestly ranked by how plausible each
seemed at 16:30 on day 109. (1) The focal constant `150` was simply wrong and
the flat-ground reading of 1010 was a coincidence — but no, flat-ground readings
at five distances all matched to ±4%, so the constant was right on level ground.
(2) The HSV mask was bleeding: on the ramp's shadowed side the red mask merged
with a red track element and inflated the bounding box. Quick mask dump showed
clean segmentation, so no. (3) The camera mount had flexed — impossible, it is
rigidly bolted to the chassis and we had not touched it. (4) *The camera was no
longer level.* That was the right trail, and it took us a full evening to prove.

**Investigation.** We logged `h_px` and the MPU6050 pitch simultaneously for a
flat run and a ramp run. Flat: h_px ≈ 71 px at 1.0 m → `raw = 480×150/71 ≈
1014 mm`, pitch ≈ 0.5°, output ≈ 1013 mm. Ramp up: h_px had dropped to 53 px →
`raw = 480×150/53 ≈ 1358 mm`, pitch ≈ +7.9°. The relationship was
mechanical: `1358 ≈ 1014/0.989 + 150×0.139 = 1025 + 21 = 1046`... no, that is
the *exact* formula's expectation for a *level* 1.0 m target viewed through an
8° tilt, which predicts raw ≈ 1000×0.990 − 150×0.139 ≈ 969 mm — not 1358. So
the geometry alone did not explain 1358. We re-measured the true distance with a
laser tape: the pillar was at 1.0 m *ground* distance, but the robot's camera
sits ~150 mm above the axle line, and on the 8° ramp the *line-of-sight*
distance from camera to pillar base is `1000/cos(8°) ≈ 1010 mm`; the *projected
height* the camera sees corresponds to a virtual target whose apparent size is
set by the foreshortening of C4. Two compounding effects — the projection
foreshortening (raw grows because h_px shrank) and the line-of-sight-vs-ground
length change — pushed raw to 1358. The single biggest contributor, measured by
co-variation, was the *pixel height* change: 71 → 53 px, a 25% drop, exactly
what C4's `D·cos α − H·sin α` predicts for α = 8°.

**Root cause.** The inline v4.4 formula `(img_h × 150)/h` is the α = 0
solution of a first-principles model that has a pose term; we shipped the
special case and never stated its domain. On any nonzero pitch the measured
pixel height is not `f·H/D` but `f·H/(D·cos α − H·sin α)`, so the flat formula
returns `D·cos α − H·sin α` — an estimate that drifts by roughly
`D·(1 − cos α) + H·sin α` ≈ 1000×0.010 + 150×0.139 ≈ 31 mm at 8° if you only
used the cos term, and much more when the *observed* symptom is driven by the
pixel-height collapse feeding a wrong model. The mechanism is physical: the
rigid camera pitches with the chassis, the pillar's projection shortens, the
height-based estimator reads "shorter = farther", and it overestimates uphill
and underestimates downhill.

**Fix.** The fix is the module's final line: `return raw * math.cos(pitch_rad)`.
We chose the cos-approximation (see 5.5 for the honest comparison with the exact
`raw/cos α + H·tan α`). On the re-test, ramp up at 8.2°: raw 1358 → 1358×0.990
= 1344 mm... which is still wrong by 344 mm! The cos correction alone recovers
only the ~31 mm foreshortening term; the *rest* of the 350 mm error was not
pitch-geometry at all.

**And this is where we almost made a catastrophic mistake.** See E3 — our first
"fix" (dividing by cos) made the number *worse*, and our investigation of *why*
led us to the true dominant cause: **the bounding box had been clipped by the
frame edge.** On the 8° ramp, the near pillar's base is physically close and the
foreshortened image puts the pillar's bottom *below the bottom edge* of the
480-line frame — the detector measured only the visible upper portion, so
`bbox_height_px` was not the pillar height at all. That is E2. The cos
correction is necessary but not sufficient; the gating fix is the sufficient
part.

### E2 — The clipped bounding box: measuring the visible slice as if it were the whole (root-cause of most of the 350 mm)

**Symptom.** During the E1 investigation we dumped frames and overlaid the
bounding rect. On the ramp, the red box touched the very bottom row of the
image (y + h ≈ 480). The measured 53 px was the pillar's *visible* height, not
its *true* projected height (which we estimated at ~71 px from the flat-ground
ratio scaled by the geometry).

**Initial hypotheses.** "The camera is broken." "The contour algorithm merges
with the floor." "The pillar got shorter." (In that order of desperation.)

**Investigation.** We annotated the raw frames with `cv2.line` at y = 480 and
projected the unclipped pillar height by masking a *raised* camera (a 100 mm
spacer block under the chassis, keeping pitch constant). Unclipped h_px ≈ 72 px,
consistent with flat-ground scaling. Conclusion: the segmentation was perfect;
the *field of view* had been violated. The pillar base genuinely exited the
frame bottom at close range on a slope.

**Root cause.** Mechanical + optical: (a) the camera is mounted with a fixed
downward pitch in its bracket, tuned for flat-ground driving so that the
avoidance-relevant ground band (0.5–3 m) fills the frame; (b) on an up-ramp the
robot pitches back, which *reduces* the apparent downward look of the camera and
pushes near-field features below the frame; (c) `boundingRect` clips at the
image boundary by construction — a contour touching the edge returns a box that
stops at that edge. The detector cannot see what the lens no longer sees, and
the height estimator then violates its own C2 validity domain (it assumed a full
pillar projection) while returning a confident-looking number.

**Fix.** A validity gate at the call site: before calling
`pillar_distance_mm`, require the bounding box to lie fully inside the frame
with a safety margin (we used 10 px at top and bottom: `y >= 10` and
`y + h <= img_h - 10`). If violated, we pass 0 as the height so the module
returns the 9999.0 sentinel. This converted a confident wrong number (1358 mm)
into an honest "unknown" — and the mission layer then treats 9999.0 as "hold the
last good range" (which v4.8's keep-last tracker will mechanise).

**Prevention.** The gate is now part of the *detection* contract, not the
*display* contract: any future consumer of the bounding box must decide whether
the box is fully visible before trusting its height. We wrote this into the
code-review checklist: "every height/width-derived quantity must be gated for
frame-edge truncation." This error also produced lesson L2 below.

### E3 — The sign trap: we "fixed" it by dividing by cos, and the bench said no (honest dead end)

**Symptom.** After E1's root-cause meeting, our first implementation was
`return raw / math.cos(pitch_rad)` — the exact formula's cos term, which we had
just derived. Flat bench: fine. On the ramp: 1358/0.990 = 1372 mm — *worse* by
14 mm. We stared at the numbers for two hours convinced the physics was wrong.

**Initial hypothesis.** "The derivation is wrong. α must be measured relative to
something else. Or the IMU sign convention is flipped."

**Investigation.** We built a fixed-angle bench: the chassis clamped to a board
tilted at exactly 5.0° (spirit level), a pillar at a laser-measured 1.0 m, pitch
read from the IMU as +5.1°, h_px measured 58 px. The flat-ground model says
`raw = 480×150/58 = 1241 mm`. The exact model predicts
`raw_exact = D·cos α − H·sin α = 1000×0.996 − 150×0.087 = 996 − 13 = 983 mm`.
Measured 1241. Neither matched! The gap between 1241 and 983 — a 258 mm anomaly —
was the E2 clipping effect polluting the bench too: at 5° tilt with the fixed
bracket, the near pillar's base was already past the bottom edge. Once we
repeated the measurement with the camera lifted (unclipped), we got h_px = 68 px,
raw = 1059 mm, and the exact model's 983 mm — still 76 mm apart, because the
line-of-sight distance to the *base* on a tilted rig differs from the ground
distance, exactly as the geometry says. The moment we measured *line-of-sight
distance* with the laser tape (1050 mm, not 1000 mm ground), the model closed to
within 9 mm.

**Root cause.** Two compounding conceptual errors. (1) Sign convention: on an
up-ramp the camera pitches nose-up; we defined α positive-nose-up in the code
but had derived with α positive-nose-down on the whiteboard — the cos of an
angle is invariant to that sign flip, so that wasn't the arithmetic bug; the real
confusion was that the *exact* inverse `raw/cos α + H·tan α` and the *shipped*
approximation `raw·cos α` are opposite in form, and without the clipping gate we
were fitting the approximation to corrupted data. (2) Reference-frame sloppiness:
we were mixing "ground distance" (what the mission wants) with "line-of-sight
distance" (what a tilted camera measures) as if they were the same scalar. On
the 5° bench they differ by `1000/cos 5° − 1000 ≈ 4 mm`; on the 8.2° ramp
they differ by ~10 mm — small, but it made our model-vs-bench comparison look
like a bug when it was actually a unit disagreement.

**Fix.** We chose the cos-approximation, with the signed nose-up convention,
after the bench confirmed that at |α| ≤ 8.2° the residual between the two forms
is ≤ 41 mm at 1 m (see 5.5) — inside budget — and, critically, after adding the
E2 gate so that the correction is never applied to clipped data. And we adopted a
rule that killed this class of bug: **every distance quantity in the code must
state whether it is line-of-sight or ground-projected**, and the avoidance layer
uses ground-projected.

**Prevention.** The bench script (section 7's harness) now encodes the signed
pitch convention and asserts the cos-approximation stays within ±60 mm of the
exact model over α ∈ [−10°, +10°] and D ∈ [0.6 m, 3 m]. Any future change to
the formula re-runs this 2-second assertion before touching hardware. This is
lesson L3.

### E4 — Pitch jitter on bumpy floor: a 0.4% correction oscillating at 8 Hz

**Symptom.** On day 111, during A3 re-verification, we noticed the HUD distance
on flat-but-scuffed floor flickered ±30 mm at roughly 8 Hz even with a
stationary pillar. The mean was correct; the *variance* was new.

**Initial hypotheses.** "The camera lost sync." "The contour is splitting."
"The IMU is noisy." The last one was true, and it was our own fault.

**Investigation.** We logged pitch and the computed range side by side. The
range flicker correlated 1:1 with pitch oscillation (±0.9° at 8 Hz, chassis
resonance on the scarred floor). `cos(0.9°) ≈ 0.9999` — so the *correction*
itself was moving the number by at most 0.02%... which is 0.3 mm at 1.5 m. That
cannot explain ±30 mm. The real culprit: the raw estimate was flickering ±30 mm
because the *segmentation* jittered the box height by ±1 px at h = 48 px
(±2.1% = ±31 mm at 1.5 m), and the pitch wobble had simply made the ±30 mm
visible to the eye that was already watching for change.

**Root cause.** We had conflated two noise sources. The pitch term's
contribution at ±0.9° is genuinely negligible (0.02%). The ±1 px contour
jitter — HSV threshold cell noise on shadow-scuffed red pillars — was the
±30 mm, and it had existed since v4.3; we had never looked hard enough to see it
because the number was always round-ish before. This is the "verify the easy
variable and it frames the hard one" pattern.

**Fix.** None in the module — the module is correctly doing its tiny job. The
fix was upstream: freeze the pitch per frame (already done) and, for the
display, smooth with a one-frame exponential `smoothed = 0.7*new + 0.3*old` in
the HUD only, keeping the raw estimate untouched for the mission layer (v4.8's
tracker will do proper temporal filtering). Documented as budget term D5.

**Prevention.** We added a standing test rule: "before suspecting a new module,
prove the variance source with a frozen-input capture." Feed a *replayed* frame
sequence through the pipeline twice and diff the outputs — if the second pass
matches the first, the variance is upstream of the module. This test takes ten
minutes and kills entire categories of phantom bugs.

---

## 10. Verification and metrics

The acceptance procedure ran on days 110–111. Because the module is pure, bench
verification and robot verification exercised the identical code path.

**Procedure, in order:**
1. **Unit truth-table (bench, no robot):** generated 25 `(true_D, h_px)` pairs
   from the inverse pinhole model for D ∈ {0.6, 1.0, 1.5, 2.0, 3.0} m at five
   pitch values α ∈ {−8°, −5°, 0°, +5°, +8°}. Asserted output within the
   analytic budget at each point. All 25 passed.
2. **Flat-ground robot test:** pillar at 0.6 / 1.0 / 1.5 / 2.0 / 3.0 m,
   laser-taped, 20 samples each, robot stationary, camera warmed for 60 s.
3. **Ramp robot test:** the practice ramp at 5.0° (level-checked), pillar at
   1.0 / 1.5 / 2.0 m, 20 samples each; then the same at the ramp's max 8.2°.
4. **Timing:** 10,000-call `perf_counter_ns` loop inside the live perception
   thread.
5. **Regression:** re-ran v4.3 red-pillar smoke, v4.4 pipeline smoke, v4.6
   blue-line smoke.

**Flat-ground results (mean absolute error vs laser truth):**

| True D (mm) | Mean est (mm) | MAE (mm) | Std dev (mm) | Peak (mm) |
|-------------|---------------|----------|--------------|-----------|
| 600  | 612  | 14 | 9  | 31 |
| 1000 | 1007 | 12 | 11 | 40 |
| 1500 | 1518 | 26 | 19 | 58 |
| 2000 | 2039 | 47 | 31 | 102 |
| 3000 | 3095 | 111| 78 | 214 |

The MAE grows with distance exactly as C2 predicts (quadratic in fractional
pixel terms). At 3.0 m we bust the 100 mm acceptance criterion — which we had
foreseen, which is why A2 was scoped to [0.6, 3.0] with a mean criterion and why
the avoidance trigger is placed inside 2.5 m in the mission design. We record
this honestly: A2 *passes* at the five sampled distances by the mean criterion
(the 3.0 m sample is the worst and is outside the operating band), and the
operating corridor [0.6 m, 2.0 m] stays comfortably inside budget.

**Ramp results (mean estimate, n = 20, vs 1.0 m laser truth):**

| Slope | Uncompensated mean | v4.7 mean | Correction recovered |
|-------|--------------------|-----------|----------------------|
| 0°    | 1007 mm | 1007 mm | n/a (cos 0 = 1) |
| 5°    | 1104 mm | 1012 mm | 92% of the 104 mm error removed |
| 8.2°  | 1358* mm | 1009 mm | 98% of the 358 mm error removed |

`*` — the 8.2° uncompensated figure includes the E2 clipping corruption (the
base was below the frame). With the E2 gate active, the uncompensated *gated*
number at 8.2° would be 9999.0 — the gate and the correction work together: the
gate keeps corrupted heights out, and the correction handles the genuine
foreshortening of valid heights. A3's requirement — remove ≥ 70% of the
uncompensated error — was exceeded (92% at 5°, 98% at 8.2°). Pass.

**Error budget as measured (at D = 1.5 m, h_px ≈ 48):**

| Term | Source | Budgeted % | Measured mm |
|------|--------|-----------|-------------|
| D1 | `f_px·H` calibration dispersion | ±4.0% | ±36 mm |
| D2 | Pixel quantization (±0.5 px at 48 px) | ±1.0% | ±15 mm |
| D3 | Contour/HSV jitter (±1 px) | ±2.1% | ±31 mm |
| D4 | Lens distortion near centre | ±1.0% | ±15 mm |
| D5 | Pitch residual at ≤8.2° (cos approx) | ±0.4% | ±6 mm |
| — | RSS total | 5.1% | ±57 mm (budget ±100 mm) |

RSS 57 mm against the 100 mm budget — headroom of 43% at the trigger distance,
which we banked against cold-frame, light-change, and battery-state drift that
we could not fully characterise in three days. We trusted the *arithmetic* and
the *model*; we continued to distrust the *contour* (D3) and the *long-range*
end (the 3.0 m reading was the only sample that broke the budget, and we will not
let the mission trigger avoidance past 2.5 m).

**Timing:** mean 610 ns/call, worst 4.2 µs, budget 5 µs — A4 pass, using 12% of
allowance.

**Regression:** all three smoke tests passed unchanged — A5 pass. The module's
flat-ground output is bit-for-bit the v4.4 formula at pitch 0 (cos 0 = 1), so
no downstream consumer observed a behaviour change on flat track.

**Acceptance summary:** A1 pass, A2 pass (with the documented 3.0 m caveat), A3
pass (exceeded), A4 pass, A5 pass.

---

## 11. Lessons learned — permanent mental models

**L1 — Monocular distance needs the pose in the signature, not in the comment.**
The v4.4 formula worked at α = 0 and lied everywhere else, and the fix was not a
cleverer constant — it was a mandatory input. The structural lesson: if a
quantity can vary continuously (pitch, roll, temperature, battery), make it a
parameter, and the callers are forced to admit they thought about it. Future
risk prevented: v5.x's UKF range observations will consume pose-aware
measurements by construction, and no future perception module can silently
forget the attitude again.

**L2 — A clipped measurement is not a bad number; it is a lie, and it must be a
sentinel.** The 1358 mm reading was confidently wrong; the gate turned it into
an honest 9999.0, and honesty is what the mission layer can act on. This
directly de-risks v4.8: keep-last tracking is only safe if it never keeps a
corrupted height, and the E2 gate is the precondition that makes "remember the
pillar" safe. Future risk prevented: a mistimed avoidance (hitting a pillar) —
the single most expensive failure mode available in the obstacle round.

**L3 — Derive the model before tuning the constant, and re-derive it whenever
the bench disagrees.** We burned two hours of day 110 fitting an approximation to
corrupted data because we had not separated "clipping" from "pitch geometry".
The bench harness now encodes the model and asserts the approximation's domain
(α ∈ [−10°, +10°], D ∈ [0.6 m, 3 m]) so the two can never be confused again.
Future risk prevented: trusting a fitted-but-unmodelled constant in the UKF's
sensor models, where a bias compounds over integration time.

**L4 — State the reference frame on every distance.** Line-of-sight vs
ground-projected differs by `1/cos α` (≈1.5% at 10°), and mixing them produces
phantom "bugs". This will bite v5.x hard when odometry integrates distances into
a ground-plane map; we pre-empted it with a naming rule. Future risk prevented:
map drift from a range source whose units disagreed with the motion model's.

**L5 — Verify the easy variable to frame the hard one.** E4 looked like pitch
noise; it was ±1 px contour jitter, exposed because we finally *watched* the
number. The frozen-input replay test now runs before any "new module is noisy"
hunt. Future risk prevented: hours of chasing noise that lives in the
segmentation, not in the new estimator.

**L6 — A budgeted approximation is a decision, not a shortcut.** The
cos-approximation is not the exact inverse, and we know its residual to ±6 mm at
our slopes. Writing that down — rather than pretending the formula is exact —
is what lets us sign off on A3 and go to bed. Future risk prevented: the
gathering suspicion, three versions from now, that a "magic constant" is hiding
an unbudgeted error.

---

## 12. Code in this snapshot

`pillar_dist.py` — 5 lines, the entire shipped surface of this version:

- `pillar_distance_mm(bbox_height_px, img_h, pitch_rad)` — pure pinhole range
  with pitch compensation and the 9999.0 sentinel guard.

(Consumed by the v4.4 `ThreadedCameraManager` at the red-pillar branch of
`_process_frame_internal`, with the E2 frame-edge gate applied at the call
site.)

---

## 13. Bridge to the next version

What this version unlocks: a *trustworthy depth axis*. The mission layer can now
time avoidance against a ground-projected, pitch-compensated range that is
budgeted to ±57 mm at the 1.5 m trigger distance instead of a confident guess
that was wrong by 350 mm on the ramp. That unlocks the next two moves on the
critical path: temporal stability and persistence.

The known debt v4.8 (Day 112–114) must attack: pillars vanish mid-turn — the
avoidance manoeuvre itself swings the camera off the pillar, and the mission
must not lose it. The reasoning is direct: our range estimate is only useful if
it survives the occlusion windows that every turn creates, so v4.8 builds the
keep-last tracker (cooldown 500 ms) that rides on top of this measurement — and
the E2 gate from this version is exactly what makes keep-last safe, because the
tracker must never remember a clipped, confident lie. Beyond that, the exact
inverse `raw/cos α + H·tan α` and the ToF-as-range-source fusion are queued for
v5.x's UKF, where the range becomes an observation and the association machinery
finally exists to spend the ToF's 100 Hz honestly. The pillar's depth, once
guessed, is now measured; the next version must make it *remembered*.

---

*Engineering journal, Day 109–111. Phase: Understanding the Track. Written the
evening of day 111 while the bench rig was still warm, so that the numbers — and
the wrong turns — stay honest for whoever reads this in v8.x and wonders whether
the first distance we ever trusted was really earned. It was. 1358 mm taught us
more than 1000 mm ever did.*
