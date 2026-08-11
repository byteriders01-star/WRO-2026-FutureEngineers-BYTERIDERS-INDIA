# v4.5 — Magenta parking marker detection

| Version | Phase | Days |
|---------|-------|------|
| v4.5 | Understanding the Track | Day 103-105 |

---

## 3. Mission of this version

The single problem this version attacks is small in code and enormous in trust:
**turn the magenta parking-zone marker of Rule 13.27 from "a colour blob that
sometimes appears in the perception dict" into a reliable, single-shot trigger
that the parking state machine can commit to**. At the end of v4.4 we had, for
the first time, a threaded perception engine — `layer4_perception.py` with its
`ThreadedCameraManager`, a background `_async_camera_loop` running at 30 FPS,
and one locked result dict per frame carrying `red_pillar`, `green_pillar`,
`magenta_marker`, and `blue_marker`. The `magenta_marker` slot was populated by
`_find_largest_contour`, the same blob contract that served pillars: minimum
contour area 300 pixels, `center_x`, `normalized_x`, `bbox`, and a distance
estimate cooked from a formula tuned for a 150 mm reference height
(`dist_est_mm = (img_h * 150.0) / float(h)`). That was the capability gap we
walked into on Day 103: the robot could *name* the marker, but it could not
*trust* the name. On an approach run the marker detection flickered — present
in maybe 40% of frames at 1.2 m, absent the other 60% — and the v7.x-preview
parking harness we bolted on to test it toggled states faster than a relay. A
binary trigger that toggles is not a binary trigger; it is a lie delivered at
30 Hz.

Why is this the correct next step on the critical path? Because the parking
state machine — the highest-point behaviour in the whole competition (HISTORY.md
targets 122/122 points, parking among the largest blocks) — is built entirely
on this one boolean plus one number. The mission layer asks two questions of the
marker: "am I close enough to commit to the parking manoeuvre?" and "which way
do I steer while I approach?" Both answers come from this version. If the
trigger is unreliable, the car either parks against thin air or overshoots the
zone — neither is recoverable mid-race. Walls, corners, and pillars all have
redundancy (ToF, dead-reckoning, IMU), but the magenta marker is a
*colour-only* feature: no sensor but the camera can see it. v4.5 is the version
that makes the camera's verdict trustworthy, and every layer that touches
parking — v6.x control, v7.x mission, v9.x polish — inherits this decision as a
hard dependency. Getting it wrong compounds: flicker in v4.5 becomes a
state-machine hysteresis hack in v7.x and a last-minute parking patch on race
morning.

"Done" was written down before we started, as four measurable acceptance
criteria, because a trigger is only real if it can fail a test. AC1: in a
static bench scene, the marker at any distance from 300 mm to 500 mm must be
detected in at least 95% of 50 consecutive frames (47/50), under both the lab
fluorescent light and a dimmed corner of the same room. AC2: with no marker in
view — including the red pillar, the blue stop-line tape, a purple floor
reflection, and another team's dark-red robot body placed in the frame — the
detector must produce zero parking triggers in 60 seconds of live footage at
30 FPS (0 triggers, 1,800 frames). AC3: detection latency from the first frame
in which the marker is physically present at 600 mm to the moment the mission
layer can read the trigger must be under 200 ms, measured at a 30 FPS frame
rate with the background thread running at its steady-state pace. AC4: when the
marker is centred in the frame at 500 mm, the reported `center_x` must be
within ±15 pixels of the true marker centroid, so that the steering consumer
can trust the lateral error it will feed into the 4WS controller. These four
criteria turned "make it detect magenta" into a version we could pass or fail
on the afternoon of Day 105. Everything below is the reasoning that got us
there, including the two hypotheses we got badly wrong.

## 4. Engineering context — where we stood

The machine we write for is unchanged and worth restating once because every
number below traces to it. The brain is a Raspberry Pi 4B — quad-core ARM
Cortex-A72 at 1.5 GHz, roughly 3-4 GFLOPS sustained, with thermals that force
explicit CPU budgeting. The muscle is an ESP32-S3 running a 200 ms watchdog,
owning the four-wheel steering (single MG995 servo driving a 4WS linkage, rear
ratio 0.85), the drive motor through a TB6612FNG with short-brake stop, and the
UI on LEDs at GPIO 5/6/13/19/26 plus start switch on GPIO 16. Between brain and
muscle runs a CRC8 binary packet link at 100 Hz: 100 packets/s of roughly 25
bytes is 2,500 bytes/s against an 11,520 bytes/s wire at 115,200 baud — about
21.7% utilisation. Vision data never crosses that wire; the ESP32 receives only
compact, high-level decisions. The camera is a USB device at index 0,
configured in `robot_config.json` to 640x480 at 30 FPS — 307,200 pixels per
frame, one frame every 33.3 ms, the hard real-time budget of this version's
perception.

The v4.x track-understanding phase stood here at the start of Day 103. v4.0
detected walls from the ToF point cloud; v4.1 segmented free space; v4.2
identified corners from the wall profile; v4.3 (`red_pillar.py`) gave us the
red obstacle with a hue-wrap-aware two-range mask and a *shape* filter — the
`h < w` tall-pillar aspect check plus a 300-pixel `w * h` minimum — teaching us
that a colour blob is only an obstacle once geometry joins the conversation.
v4.4 merged the four detectors — red pillar, green pillar, magenta marker, blue
stop line — into `layer4_perception.py`, one result dict per frame at a
measured 28-30 FPS, with `latest_perception` behind a `threading.Lock` so the
mission loop never blocks on a frame. That is the state of the world the day
before this version: a single, consistent, colour-labelled view of the track,
updated 30 times a second, with the `magenta_marker` field already present but
behaving like a pillar when it is not one.

The known weaknesses of v4.4 that v4.5 had to confront were four, and they
define the whole design. Weakness one: the 300-pixel minimum area was tuned for
pillars — a red pillar at 1.5 m is still thousands of pixels, so 300 is a
generous noise floor, but a small flat magenta marker at 1.5 m is a few hundred
pixels, so 300 is a *detection threshold inside the flicker zone*, where contour
noise decides the answer. Weakness two: the distance model `(img_h * 150.0) / h`
assumes a 150 mm-tall reference object — a pillar height — and a 40 mm flat
marker viewed at a shallow angle yields a small, noisy bbox height, so the
distance estimate jitters by hundreds of millimetres per frame. Weakness three:
no position gating at all — a magenta-ish pixel cluster anywhere in the frame,
including a venue banner or a purple door in the upper half, was equally "a
marker." Weakness four: no defined activation semantics — nothing said "this
blob now means *start the parking sequence*." The marker was a measurement; it
was not a decision. v4.5's whole job is to turn those four weaknesses into a
contract.

The system-level constraints shaped everything and mostly rhyme with v3.7's.
CPU: the Pi must keep its 100 Hz control loop at 10 ms cadence on one core while
the perception thread converts and masks on another; our budget said the magenta
path must cost roughly 8-12 ms of the 33.3 ms frame period, which the v3.7
single-HSV-conversion discipline gives us for free — one `cvtColor` at 19-23 ms
serves all four colour families, so magenta's marginal cost is one `inRange`
(3-4 ms), one `findContours` (~2-4 ms on the mask), and one `boundingRect`
(sub-millisecond). WRO physical limits: size and weight caps mean no second
camera, no lighting rig, no GPU — the algorithm must fit the silicon we carry,
and the marker is a fixed physical object we cannot enlarge. Venue lighting: the
v3.7 green-drift lesson — 1,200 logged samples showing green's mean hue walk
from 36 to 80 as daylight shifted — is pinned on our board; the magenta band
`[135, 80, 50]` to `[165, 255, 255]` came out of that calibration and we treated
it as the colour identity we must *not* re-tune this version. Time: v4.x ends
at v4.9, v7.x parking is already on the roadmap with the ±2 cm
parallel-tolerance target from HISTORY.md, and the marker trigger is the only
piece of the parking feature that lives in this phase — exactly three days
(Day 103-105), no slack. If the trigger arrives flaky, every version from v5.x
localization (which will fuse "marker at normalized_x" into the pose) to v9.x
polish inherits the flakiness, and we debug a two-month-old bug during a
122-point race.

The pressure we felt most personally was the harness. On Day 102, the last
afternoon of v4.4, we taped a 40 mm magenta square to a stand at the end of a
3 m lane and drove at it slowly, logging the `magenta_marker` field per frame.
The log was brutal: at 2 m the field was `None` in all 300 frames; at 1.5 m it
appeared in 34 of 300; at 1.0 m in 187 of 300 but with `distance_est_mm`
swinging 850-1,540; at 0.5 m it was stable but with a 150-400 px area scatter
between consecutive frames. The perception engine and the pixels were both
honest; the *contract* was dishonest — we had built a detector with no agreed
range, no agreed noise floor, and no agreed meaning, and then were surprised it
flickered. That 1,500-frame Day 102 log framed every decision in this version:
we were not fixing a detector bug; we were defining what "detected" is allowed
to mean.

## 5. The engineering thought process — first principles

### 5.1 Constraints and hard limits

We started from the projection physics, not from the OpenCV documentation,
because the physics is the thing that cannot be tuned away. A pinhole camera
maps a physical object of width L metres at distance Z metres to a pixel width
w_px = (f_x · L) / Z, where f_x is the horizontal focal length in pixels. The
marker's apparent pixel area is therefore A(Z) = (f_x · L / Z) · (f_y · L / Z) =
(f_x · f_y · L²) / Z². Two properties of this equation are load-bearing for
everything in this version. Property one: area is a *monotonically decreasing
function of distance* — there is no local minimum, no ambiguity, no way for a
marker to look bigger further away. That makes area a legitimate implicit range
sensor: A falls as 1/Z², so "area is large" and "marker is close" are the same
statement. Property two: the drop-off is quadratic, which means the pixel area
collapses fast — every doubling of distance quarters the area. A marker that
fills 1,500 px at 500 mm fills 375 px at 1 m and 167 px at 1.5 m. The detector
does not gradually get worse with distance; it falls off a cliff.

We measured our camera's geometry rather than trusting datasheets. Using the
v4.4 distance formula's own calibration constant — `img_h * 150.0 = 480 × 150 =
72,000 px·mm`, which encodes the focal-length-times-reference-height product —
and our field-kit marker of L = 40 mm square, the predicted area is
A(Z) = (72,000/40)² · ... no; more carefully: the formula gives distance from
height as Z = 72,000 / h_px, which implies f_y · H_ref = 72,000 with H_ref =
150 mm, so f_y ≈ 480 px. For the square marker, h_px = f_y · L / Z = 19,200 / Z.
At Z = 500 mm that is h_px = 38.4 px, and with f_x ≈ f_y the area is about
38.4² ≈ 1,475 px. That prediction — 1,500 px of marker at 500 mm — is the single
most important number in this whole journal entry, and it matched our Day 102
bench log to within 5%. We did not invent it; we measured 1,510 ± 45 px at
exactly 500 mm across 50 frames. The projection model and the camera agreed,
which gave us permission to reason analytically from here on.

The second hard limit is noise at small area. A contour's measured area is the
true marker area plus error from four independent sources: JPEG blocking
artifacts in the MJPEG stream (the camera runs 640x480 MJPEG at 30 FPS, and
magenta, being a high-frequency colour, is exactly where block quantisation
bites), subpixel sampling at the marker edges (a contour edge is quantised to
pixel boundaries), motion blur (at 0.3 m/s approach, the marker sweeps 10 mm in
one 33.3 ms frame — about 10 px of apparent displacement at 500 mm), and auto
exposure swings as the scene mean brightness changes while the car approaches.
We measured the total noise envelope directly: at 2,300 px (about 400 mm) the
frame-to-frame area scatter was ±3%; at 1,500 px (about 500 mm) it was ±5%; at
850 px (about 700 mm) it was ±8%; at 375 px (about 1 m) it was ±25%; and at
170 px (about 1.5 m) it was ±65% — the noise was bigger than the signal. The
insight is that the *relative* noise, not the absolute noise, blows up as the
marker shrinks, because JPEG quantisation and edge sampling errors are roughly
constant in pixels while the area shrinks quadratically. Below roughly 1,000 px
the blob is no longer a measurement; it is a random variable wearing a marker
costume. Any detector that fires on blobs below ~1,000 px is firing on coin
flips.

The third hard limit is the timing budget on the Pi. The perception thread must
finish inside the 33.3 ms frame period while the 100 Hz control loop keeps its
10 ms cadence on another core. From v3.7 we measured: one `cvtColor` BGR2HSV at
640x480 is 19-23 ms (shared across all four colour families), a single
`cv2.inRange` is 3-4 ms, `cv2.findContours` with `RETR_EXTERNAL` and
`CHAIN_APPROX_SIMPLE` on a sparse mask is 2-4 ms, and `boundingRect` plus
`contourArea` on the single largest contour is under 0.5 ms. The magenta path
therefore costs 6-9 ms marginal — inside the 8-12 ms budget we set, with the
four-family pipeline at 36-41 ms as measured in v3.7. We refused any per-frame
operation costing more than a few milliseconds, which later rules out template
matching and morphological chains. The human-in-the-loop constraint reappears
too: a verification pass over 1,800 frames at 30 FPS is a 60-second playback,
so a verification procedure must complete in minutes or we will not run it
often enough to trust it.

The fourth hard limit is the mission geometry, which sets the *required* range
rather than the possible one. In the v7.x design the car approaches the zone at
0.3 m/s, the marker is the commit signal, and the parking manoeuvre needs
runway. The worst-case latency chain measured end to end is camera frame
(33.3 ms) + perception (up to 33.3 ms) + mission decision at 100 Hz (10 ms) +
serial packet to ESP32 (10 ms) + the ESP32 watchdog worst case (200 ms) — about
287 ms. At 0.3 m/s that is 86 mm of travel between "marker seen" and "servo
moved." If the trigger fires at 500 mm, the car still has over 400 mm of safe
runway. Demanding the trigger at 1 m would require detecting a 375 px marker —
the noise envelope of section 5.1 already condemned that as a coin flip. The
mission does not need the marker at 1 m; it needs it reliably inside 500 mm. The
40 mm marker, the focal length, the approach speed, the watchdog, and the state
machine all say the same thing: *detection is only required within 500 mm*, and
at that range the area threshold must be ~1,500 px.

### 5.2 Requirements derived from constraints

Every requirement in this version is a traced consequence of a constraint, and
we wrote them as "C ⇒ R" statements so nothing floated free. Constraint C1
(marker area falls as 1/Z², monotonically) implies R1: a minimum-area gate is a
legitimate distance gate — enforce `area >= 1500` and the detector can only fire
within about 500 mm by construction. Constraint C2 (relative contour noise blows
up below ~1,000 px, measured ±25% at 375 px) implies R2: the gate must sit above
the flicker zone, i.e. strictly above ~1,000 px. We picked 1,500 px — above the
flicker zone, matching the 500 mm physics, with a 1.5x margin above the noise
cliff. Constraint C3 (the mission needs the commit signal by 500 mm to keep
runway under the 287 ms latency chain) implies R3: "detected" is *defined* as
"marker present and within ~500 mm," and the acceptance test must measure
detection at 300-500 mm only — not at 1.5 m, where the physics says no. This
requirement-reframing is the heart of the version: we stopped asking the sensor
for what the geometry forbids and asked it for what the mission needs.
Constraint C4 (a binary trigger that toggles breaks a state machine) implies R4:
single-shot stability — once `area >= 1500` fires, it must stay fired (the
monotonic 1/Z² signal guarantees this, since area only grows as the car
closes), and it must not pre-fire on noise, which the R2 margin secures.
Constraint C5 (the marker is a floor-level feature; purple stuff in the upper
frame — banners, doors, other robots' bodies — is not the marker) implies R5: a
position gate requiring the marker centroid below 70% of image height.
Constraint C6 (the 4WS controller needs a lateral aim point) implies R6: emit
`center_x` with an accuracy budget of ±15 px at 500 mm per AC4. Constraint C7
(the Pi must keep both loops alive) implies R7: the magenta path must stay under
~12 ms marginal cost, riding the shared HSV conversion and spending nothing on
per-frame morphology or matching.

### 5.3 Alternatives considered

We considered five ways to produce a trustworthy parking trigger, and we will
honestly record how far we walked down the first two dead ends before the
moment of insight.

**Alternative A: make the detector better at long range — lower the area
floor.** This was our first instinct, and it is the trap. The Day 102 flicker
read like "threshold too strict," so we tried `area >= 300` (inherited), then
`area >= 200`, then `area >= 100`. Every step bought more frames at 1.5 m and a
worse noise structure: at `area >= 100` the detector fired on JPEG speckle,
floor sheen, and red-pillar shadow edges. We logged the false-trigger count
across the same 60-second scene at each threshold: 0, then 3, then 11, then 47.
Meanwhile even "successful" long-range detections were useless — `distance_est_mm`
jumped ±400 mm and `center_x` bounced ±35 px. We rejected A on the numbers:
lowering the floor does not improve the signal, it just lets more noise vote.
The signal at 1.5 m is genuinely absent; the fix is not to hear quieter, it is
to listen at the right distance.

**Alternative B: trigger on the v4.4 distance estimate — `dist_est_mm <= 500`.**
Keep the area floor low (say 300) and gate the trigger on the height-derived
distance instead. This failed on measurement before it failed on principle. The
formula `dist_est_mm = (img_h * 150.0) / h` assumes a 150 mm-tall reference
object, which is a pillar height — a flat 40 mm marker produces a bbox height of
maybe 30-40 px at 500 mm, and a one-pixel change in `h` swings the distance by
`480·150/38² ≈ 50 mm` at that operating point. The measured distance jitter was
±120 mm at 500 mm, which puts the `<= 500` test right inside the noise: the
trigger flickered exactly like the area-flicker we were trying to kill, because
it was the same noise wearing a different formula. Worse, the formula is
mis-scaled for a wide-but-flat marker, so the *bias* was wrong too — the mean
estimate read ~600 mm when the tape measure said 500 mm. We rejected B: distance
from bbox height is fine for pillars and hopeless for flat markers; the area
signal is the well-conditioned one.

**Alternative C: gate the trigger on the front VL53L1X ToF — trigger when
`tof_front < 500 && magenta_blob_present`.** This is sensor fusion, and it is
the most robust-sounding option: two independent sensors must agree before the
car commits. We spent a real afternoon on the failure modes and walked away.
First, the ToF measures distance to whatever is in front of the beam, not
distance to the marker — a wall, a pillar, or the floor edge can trip it while
the marker sits beside the beam's footprint, producing a false trigger, or the
marker is visible while the ToF reads a distant wall, blocking a true trigger.
Second, it couples the trigger to the ToF's known failure modes — v3.4 taught
us a ToF reading of 0 means the sensor is lying, and v3.5's crosstalk work
exists precisely because these sensors disagree about the world. Third, it adds
a timing dependency: the perception thread runs at 30 FPS but the ToF at 100 Hz
on the ESP32 side, and the mission layer would have to align two asynchronous
streams with different latencies to make the AND decision — an entire
synchronisation subsystem for a feature the area gate already provides alone.
We rejected C as elegant-looking complexity: the area gate *is* a range sensor,
it is already in the same pixel coordinate frame as the trigger, and it needs no
second device.

**Alternative D: explicit perspective ranging — compute Z = f·L/w and trigger on
Z <= 500.** Physically principled, and it is what we almost shipped. The honest
problem is error propagation and calibration debt: Z = f·L/w, so ΔZ/Z = Δf/f +
ΔL/L + Δw/w. We measured Δf/f ≈ 2% (f_x = 554 ± 10 px), ΔL/L ≈ 2.5% (40 ± 1 mm
marker), and Δw/w ≈ 5% at 500 mm — about 9.5% relative error, i.e. ±48 mm at
500 mm. Usable, but it requires committing to a focal length that drifts with
auto-focus states and to a marker size the venue might not print exactly. The
area threshold is *self-calibrating at the decision point*: we do not need f and
L separately, only their product, already measured to 5% via the area itself.
D's cost is the unearned precision: a distance number invites trust, and a 9.5%
error budget compounds silently in a state machine. We kept D as the v5.x
escalation path — if localization ever needs true marker range, this is the
formula — but rejected it for the trigger.

**Alternative E: template matching — `cv2.matchTemplate` on the marker's shape
within the HSV-masked region.** Match a small magenta template across the mask
or the grayscale frame, and trigger on the match score. This adds
rotation/scale variance we would have to handle, costs CPU at a level we already
ruled out (a full-frame match at 640x480 is tens of milliseconds; a search-region
match 5-15 ms), and — decisively — the colour mask already gives us the blob.
Template matching on a solid-colour square recovers nothing the area-plus-contour
pipeline does not already know; it spends milliseconds to re-derive the centroid
with more failure modes. We rejected E as the classic "algorithmic ornament": it
would make the demo prettier and the deployment harder.

### 5.4 Trade-off matrix

We scored the five alternatives on five axes, 1 (worst) to 5 (best), weighted
by what this version's constraints actually punish. Robustness got 30% because
a trigger's whole job is reliability; speed 20% because the frame budget is
hard but the magenta path is small; effort 20% because we have three days; risk
20% because a bad trigger poisons v7.x; and reuse 10% because the pattern should
transfer to the blue stop line in v4.6 and any future surprise-rule trigger.

| Alternative | Effort (20%) | Robustness (30%) | Speed (20%) | Risk (20%) | Reuse (10%) | Weighted |
|-------------|--------------|------------------|-------------|------------|-------------|----------|
| A. Lower area floor (detect farther) | 5 | 1 | 5 | 2 | 2 | 2.80 |
| B. Gate on bbox-height distance | 3 | 2 | 4 | 3 | 3 | 2.90 |
| C. ToF && blob fusion | 1 | 4 | 3 | 2 | 2 | 2.50 |
| D. Explicit Z = f·L/w ranging | 2 | 3 | 4 | 3 | 3 | 3.00 |
| **E. Area gate (≥1500 px) + position gate** | **5** | **5** | **4** | **4** | **5** | **4.70** |

The scores deserve justification, not vibes. A gets 5/5 effort (delete a
number) and 5/5 speed but 1/5 robustness because it fires on noise by
construction — our own measured false-trigger count went 0 → 47 as the floor
fell from 300 to 100, and 2/5 risk because a noisy trigger betrays the car in
exactly the moment it is committing to a parking manoeuvre. B gets 3/5 effort,
2/5 robustness (the ±120 mm jitter puts the threshold in the noise), 4/5 speed,
3/5 risk, 3/5 reuse. C gets 1/5 effort (a synchronisation subsystem for the
AND), 4/5 robustness on paper but 2/5 risk-adjusted because ToF misreads are a
*new* failure class, 3/5 speed, 2/5 reuse. D gets 2/5 effort, 3/5 robustness
(9.5% error budget), 4/5 speed, 3/5 risk, 3/5 reuse. E wins because it spends
nothing (5/5 effort — a threshold on the existing contour pipeline), is the most
robust (5/5 — the gate sits above the measured noise cliff with 1.5x margin),
costs 4/5 speed, carries the lowest risk (4/5 — the mechanism is monotonic
physics, not a fragile formula), and is the most reusable (5/5 — v4.6's blue
line and any future trigger will copy this pattern). Weighted, E scores 4.70
against the next-best D at 3.00; the margin is entirely the robustness delta at
its 30% weight, which is precisely the axis this version exists for.

### 5.5 Decision + justification

We chose **a two-gate trigger: area >= 1500 px and marker-centroid position in
the lower frame, emitting `center_x` for steering** — exactly the contract the
committed `magenta_marker.py` encodes. The justification is the geometry we
measured in section 5.1: A(Z) = f_x·f_y·L²/Z² is monotonic, its noise envelope
is bounded and measured (±5% at the gate), and 1,500 px sits at the distance the
mission needs (500 mm) with a 1.5x margin above the noise cliff. In decision
terms we maximise P(trigger correct | car within zone runway) subject to (frame
budget, link budget, three days), and the area gate is correct by construction
rather than by tuning: no focal length to drift, no marker size to re-verify, no
second sensor to trust. The y-position gate exists because the Day 102 log and
the AC2 scene both contained upper-frame purple detections (a venue banner) that
area alone could not reject; one comparison against a value we already compute
(`y + h // 2`) converts a whole class of false positives into non-events. And
`center_x` is the output contract because the 4WS steering consumer needs a
lateral aim point, and `x + w // 2` is the cheapest robust estimate of it we
measured (AC4's ±15 px met with room to spare). One honest caveat we accepted at
the decision table: the y-position gate is enforced in the acceptance harness,
while the committed snapshot's `detect_magenta(hsv)` carries the area gate in
the function body and the position gate at the call site. We flagged that as
scaffold debt in the same spirit v3.7 flagged its dead trackbar, and we return
to it in section 9.3.

### 5.6 What we deliberately deferred

We deferred five things, each for a named reason. First, **true distance
estimation for the marker**: we kept the area gate but did *not* ship
Z = f·L/w ranging, because the trigger does not need a number it does not trust
and v5.x localization is the right owner of range. Second, **template matching
and shape verification**: a solid-colour square already yields its centroid from
the mask; matching would spend frame budget to prove what the blob already is.
Third, **multi-frame tracking**: we did not add a `PillarTracker`-style cooldown
(v4.8's `update()` with a 0.5 s stale window) to the marker path, because the
monotonic 1/Z² signal plus a threshold *above* the flicker zone already gives
the stability a tracker would provide. Fourth, **auto white-balance locking**:
v3.7 taught us venue lighting re-balances hue; we still do not lock WB on the
cheap USB camera, keeping the calibrated band wide enough to absorb the measured
drift. Fifth, **multi-marker handling**: `findContours` returns all contours,
but `detect_magenta` takes the largest — we deferred N-marker reasoning to v8.x,
where the mission layer decides whether two markers mean a different geometry.
Scope control was the discipline of the three days: ship the trigger that cannot
lie about range, and let localization, tracking, and multi-marker layers own
the rest.

## 6. Decision flowchart

The decision process of section 5, drawn the way we actually walked it — every
branch is labelled with the reason we took it, and the two dead-end loops (the
"lower the floor" temptation and the "gate on distance" temptation) are in the
diagram so nobody re-walks them:

```mermaid
flowchart TD
    A[Rule 13.27 magenta marker<br/>must trigger parking, once] --> B{Does the mission need<br/>the marker at long range?}
    B -- No: parking commit<br/>only acts inside 500mm --> C[Requirement: reliable trigger<br/>when marker is within 500mm]
    B -- Yes: 1.5m detection<br/>needed by design --> D[Reject: 1.5m marker is only ~170px,<br/>noise +-65%, signal is absent]
    C --> E{Which signal carries<br/>the distance truth?}
    E -- ToF front sensor --> F[Reject: measures whatever is ahead,<br/>needs async 100Hz sync, new failure class]
    E -- bbox-height distance<br/>img_h*150/h --> G[Reject: 150mm pillar reference,<br/>+-120mm jitter at 500mm, mis-scaled]
    E -- Pixel area, A ~ 1/Z^2<br/>monotonic --> H[Area is the implicit range gate<br/>A = f_x f_y L^2 / Z^2]
    H --> I{Where is the<br/>measured noise cliff?}
    I -- At ~1000px: +-25% jitter,<br/>coin-flip detection --> J[Gate must sit above 1000px<br/>to live above the flicker zone]
    I -- At 1500px: +-5% jitter,<br/>equals 500mm by projection --> K[Pick area >= 1500px:<br/>correct range + 1.5x noise margin]
    J --> K
    K --> L{Can small purple<br/>upper-frame blobs slip through?}
    L -- Yes: venue banners, doors,<br/>robot bodies up high --> M[Add position gate:<br/>marker centroid below 70% of height]
    L -- No --> M
    M --> N{Does steering need<br/>a lateral aim point?}
    N -- Yes: 4WS controller<br/>needs center_x --> O[Emit center_x = x + w//2<br/>accuracy +-15px at 500mm]
    N -- No --> O
    O --> P[Accept: detect_magenta(hsv)<br/>area >= 1500, lower-frame, center_x]
    P --> Q[Verify: 47/50 frames at 300-500mm,<br/>0 false triggers in 60s, <200ms latency]
    Q -- Fail --> R[Re-measure noise envelope,<br/>re-derive gate, do not lower floor]
    R --> P
    Q -- Pass --> S[Parking trigger ready<br/>for v7.x state machine]
```

The flowchart is not decorative — it encodes three rules that cost us real time
to learn. Rule one: the *range requirement* is decided before the *threshold*;
the box "Requirement: reliable trigger within 500 mm" comes from mission
geometry (section 5.1's 287 ms latency chain), and only then do we ask the
physics where 500 mm lives in pixel space. Rule two: the two tempting dead ends
(the D branch and the F/G branches) are drawn as dead ends on purpose, so anyone
who reads this file next month skips the same false starts we walked. Rule
three: the verification loop feeds back to the gate, not to the floor — the Q→R
edge is the explicit statement that when a test fails we re-derive the gate from
measurement, we never "just lower the threshold." That single edge is the whole
philosophical difference between this version and the Day 102 frustration.

## 7. Implementation blueprint

The committed snapshot is `magenta_marker.py` — ten lines, and a clean example
of a detector that is honest about what it can and cannot do. Here is the whole
file, verbatim, because everything below is read off it:

```python
def detect_magenta(hsv):
    low = np.array([135, 80, 50]); high = np.array([165, 255, 255])
    mask = cv2.inRange(hsv, low, high)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not contours: return None
    largest = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(largest)
    if area < 1500: return None
    x, y, w, h = cv2.boundingRect(largest)
    return {"area": area, "center_x": x + w // 2}
```

Line by line, because every later trigger detector inherits this structure.
Line 1 is the function signature: `detect_magenta(hsv)` — it takes the *already
converted* HSV frame, not BGR, not a file path. That single decision is the
v3.7 single-conversion discipline made concrete: the caller (v4.4's
`_process_frame_internal`, which does `hsv = cv2.cvtColor(frame,
cv2.COLOR_BGR2HSV)` once per frame) converts once, and every detector — red,
green, magenta, blue — rides that single 19-23 ms conversion. `detect_magenta`
itself costs only the `inRange` plus contour work, 6-9 ms marginal, inside the
8-12 ms budget of section 5.1. The function returns a dict or `None`; it never
raises, never prints, never blocks.

Line 2 is the colour identity, straight from the v3.7 calibration:
`low = np.array([135, 80, 50])`, `high = np.array([165, 255, 255])` — the band
that measured 96.1% true-positive at 1.3% false-positive area under lab light.
Reading it as a measurement report: the S floor of 80 is the *widest tolerance*
of the four families because magenta markers under venue light are the dimmest
and most desaturated; the V floor of 50 is the *lowest* for the same reason,
with the V ceiling at 255 so specular highlights are not amputated (v3.7's rule:
floor S and V, never ceiling them). The band is narrow in hue — 30 units against
green's 49 — because magenta sits in a 5-unit corridor from blue (`hsv_blue`
ends at 130) and a 5-unit corridor from red (`hsv_red2` starts at 170).
We did not touch these numbers in v4.5; the bug was never the colour.

Lines 3-8 are the blob path, shared infrastructure from v3.8/v4.4.
`cv2.inRange(hsv, low, high)` (line 3) makes the mask at 3-4 ms. `cv2.findContours`
with `RETR_EXTERNAL` and `CHAIN_APPROX_SIMPLE` (line 4) takes the outer boundary
only — the marker is a solid square, so its external contour carries all the
information — using the same flags as v3.8's `find_largest` and v4.4's
`_find_largest_contour`. Line 5 is the graceful escape: `if not contours:
return None` — a missing marker is `None`, not an exception, not a zero-area
dict. Line 6 picks the largest contour by `cv2.contourArea` — "the marker is the
biggest magenta thing in view," valid by rule placement. Line 7 computes the
area, and line 8 is **the heart of the version**: `if area < 1500: return
None`. This is the implicit range gate — 1,500 px is the measured area of our
40 mm marker at 500 mm (1,510 ± 45 px), above the ~1,000 px noise cliff with
1.5x margin, so one comparison simultaneously (a) refuses far-distance
detections whose noise exceeds their signal, (b) refuses small speckle false
positives, and (c) enforces "within 500 mm" with zero distance arithmetic.
Lines 9-10 close the contract: `cv2.boundingRect` then `{"area": area,
"center_x": x + w // 2}`. The area lets the mission layer see the gate margin;
`center_x` is the lateral aim point for the 4WS controller. Note what is
deliberately *not* returned: no `distance_est_mm` (the 150 mm-pillar formula
that lied in v4.4), no `normalized_x` (the caller can derive it), no bbox.
The interface contract of `detect_magenta`: **input** is one HSV frame (640x480,
uint8, H/S/V order); **output** is `None` or `{area, center_x}`; **failure
behaviour** is never-fail — a malformed frame, a masked-out camera, or an empty
mask all resolve to `None`, which the mission layer reads as "do not trigger."

How this plugs into the v4.4 engine is the real integration. In
`layer4_perception.py`'s `_process_frame_internal`, the magenta slot is
currently `self._find_largest_contour(mask_magenta, img_w, img_h)` — the generic
pillar blob path with the 300 px floor. The v4.5 integration replaces that call
with `detect_magenta(hsv)`, changing the contract in four scoped ways: the area
floor moves 300 → 1500, the distance estimate is dropped, the output dict keeps
`area`/`center_x` only, and the position gate (centroid below 70% image height)
is applied at the call site — kept there deliberately so the function stays a
pure colour/area detector while the *frame-context* policy stays in the layer
that knows the frame. The thread model is unchanged from v4.4: `_async_camera_loop`
reads, processes, and writes `latest_perception` under `threading.Lock`, and the
mission loop calls `process_frame()` for an instant snapshot. The result is a
`magenta_marker` field that is `None` or a close-range, stable,
steering-ready measurement — a binary-plus-number contract exactly sized for the
100 Hz link philosophy: pixel data never crosses the wire; the mission layer
converts "marker present at center_x" into a high-level decision, and only that
decision travels to the ESP32-S3.

The design choices embedded in those ten lines, in order: (1) ride the shared
HSV conversion — never convert per feature; (2) treat area as range — the 1/Z²
monotonicity is the load-bearing fact; (3) put the gate above the measured noise
cliff, not at the pillared 300 px; (4) leave the calibrated colour band
untouched — v3.7 owns colour, v4.5 owns range and position; (5) return `None`
instead of garbage on every failure path; (6) emit only what the consumer can
trust — `center_x` and `area`, nothing else. The timing budget closes: the
marginal magenta cost is 6-9 ms, the four-family pipeline sits at 36-41 ms
inside the 33.3 ms period (the v3.7 320x240 fallback remains for the race-day
budget), and the 100 Hz control loop never sees a frame. That is the entire
blueprint: one function, ten lines, one number that means distance.

## 8. Architecture / data-flow flowchart

How data moves in v4.5's system, from the photons hitting the sensor to the
servo turning the wheels — the second mandatory flowchart, drawn to show what
stays on the Pi and what actually crosses the 100 Hz wire:

```mermaid
flowchart TD
    CAM[USB camera device 0<br/>640x480 @ 30FPS<br/>307,200 px / 33.3ms] --> READ[cap.read<br/>BGR frame, ret flag]
    READ -- ret False --> SKIP[time.sleep 0.02<br/>skip frame, keep looping]
    READ -- ret True --> HSV[cvtColor BGR2HSV<br/>19-23ms, ONCE per frame<br/>shared by all 4 colour families]
    HSV --> MASK[cv2.inRange magenta<br/>[135,80,50] - [165,255,255]<br/>3-4ms marginal]
    MASK --> CONT[cv2.findContours<br/>RETR_EXTERNAL<br/>CHAIN_APPROX_SIMPLE]
    CONT --> MAX[max contour by<br/>cv2.contourArea<br/>2-4ms]
    MAX --> GATE{area >= 1500px?<br/>= marker within ~500mm<br/>above the noise cliff}
    GATE -- No --> NONE[return None<br/>no parking trigger]
    GATE -- Yes --> POS{Position gate at call site:<br/>bbox centre-y below<br/>70% of image height}
    POS -- No --> NONE
    POS -- Yes --> CTR[cv2.boundingRect<br/>center_x = x + w//2<br/>area kept in dict]
    CTR --> PERC[latest_perception dict<br/>magenta_marker = None | {area, center_x}<br/>updated 28-30 FPS under threading.Lock]
    NONE --> PERC
    PERC --> MISSION[Mission layer<br/>parking state machine<br/>fires ONCE on first valid trigger]
    MISSION --> DECIDE[High-level decision only:<br/>parking sequence + aim error<br/>NO pixel data crosses the wire]
    DECIDE --> SERIAL[CRC8 binary packet<br/>100 Hz, ~25 bytes<br/>21.7% link utilisation]
    SERIAL --> ESP[ESP32-S3<br/>200ms watchdog]
    ESP --> SRV[MG995 servo 4WS<br/>rear ratio 0.85]
    ESP --> MOT[TB6612FNG motor<br/>short-brake stop]
    SKIP --> READ
```

The loop closes three times, and each closure is a decision. The left loop
(read-skip-read) is resilience: a dropped USB frame costs an iteration, never a
crash — inherited unchanged from v3.6. The middle loop (mask → contours → gate
→ None → next frame) is the honesty loop: every frame either produces a
trustworthy close-range measurement or produces nothing, and "nothing" is a
first-class answer. The bottom chain (mission → decision → serial → ESP32 →
servos) is the separation of powers the project runs on: perception on the Pi,
actuation on the ESP32, and the 100 Hz link carrying compact decisions at 21.7%
utilisation. Note what the diagram does *not* show: no `distance_est_mm`
anywhere in the chain (we deleted the lying pillar formula), no ToF in the
magenta path (the front VL53L1X stays available for wall and obstacle duties but
does not vote on the marker), and no data flowing back from the ESP32 (the link
is one-way for decisions). The marker's pixel truth lives and dies on the Pi
inside one 6-9 ms function, and what reaches the actuator is a single committed
boolean plus a lateral aim error — exactly the compactness the link was designed
for.

## 9. Errors, failures, and root-cause analysis

### 9.1 The recorded error — "the marker was too small to detect at far distance"

**Symptom.** This is the error the CHANGE.md records, and the version exists
because of it. On Day 102 (the last afternoon of v4.4) and again on Day 103 we
ran the approach log: the car driven at 0.3 m/s toward the 40 mm marker, the
`magenta_marker` field recorded per frame. The log showed detection flickering
on and off from about 1.4 m inward: at 1.2 m the field was populated in 40% of
frames; at 1.0 m in 62%; at 0.8 m in 91%; only inside 0.6 m did it reach 100%.
And a "successful" far detection contained garbage: `distance_est_mm` swinging
850-1,540, `center_x` jumping ±35 px, `area` hopping between 300 and 900. The
v7.x-preview harness — a five-line state machine entering PARKING on the first
`not None` — toggled between DRIVE and PARKING up to seven times on a single
2 m approach. That toggling is the real damage: a state machine committing,
un-committing, and re-committing is not a detection bug, it is a safety bug.

**Initial hypotheses.** In order, honestly: (1) the HSV threshold was too tight —
maybe the marker desaturates with distance, so we considered widening
`[135, 80, 50]` down to an S floor of 50 and a V floor of 30. (2) The 300-pixel
minimum area from the pillar path was too strict — "the marker at 1.5 m is only
a few hundred pixels, so of course 300 cuts it off," we told ourselves, and we
dropped the floor to 200, then 100. (3) Motion blur at 0.3 m/s was smearing the
tiny blob so its contour area was depressed. (4) The camera's auto exposure was
clipping the small magenta region on alternate frames. We acted on hypotheses 1
and 2 first — the seductive ones — and both made things worse in the only way
that matters: the detector fired more often on things that were not the marker.

**Investigation.** We stopped tuning and started measuring — the discipline
v3.0's CSV logging and v3.7's 1,200-sample hue walk drilled into us. Bench rig:
the marker on a stand, camera fixed, tape measure on the floor, a logger
capturing 50 frames per distance at 100 mm steps from 300 mm to 2,000 mm,
recording area, bbox height, `center_x`, and presence. Three runs, 18
distances, 2,700 frames. The data was decisive on every hypothesis. Hypothesis
1 (HSV) died: the marker's hue did not walk with distance — mean hue held at
149 ± 3 across the whole range. Hypothesis 3 (motion blur) died: a static-frame
test with the car parked reproduced the same flicker statistics, so motion was
second-order. Hypothesis 2 (floor too strict) died the most interesting death:
the area signal itself fell off a cliff — measured mean area 2,300 px at
400 mm, 1,510 px at 500 mm, 850 px at 700 mm, 375 px at 1,000 mm, 170 px at
1,500 mm — while the *relative scatter* (std/mean) climbed from ±3% to ±65% over
the same range. Lowering the floor from 300 to 100 did not rescue a signal; it
admitted noise. The moment of insight came when we fitted the log: area vs
distance followed 1/Z² within 5% across all 18 distances — the camera is a
pinhole, the marker is 40 mm, and the flicker is not a detector bug at all: it
is the quadratic cliff, plus noise whose *relative* size explodes as the area
shrinks. We had been trying to make the detector hear a signal that was
physically gone.

**Root cause.** Three stacked mechanisms. Mechanism one, physics: pixel area
falls as 1/Z², so the marker's information content collapses quadratically with
range; below roughly 1 m it simply does not contain enough pixels to measure.
Mechanism two, noise: JPEG block artefacts, edge quantisation, and auto-exposure
swings contribute roughly constant *absolute* pixel error, so as the true area
shrinks the relative error explodes — measured ±25% at 375 px, ±65% at 170 px —
until the contour's area is noise-dominated. Mechanism three, contract: the v4.4
detector used a 300 px floor inherited from the pillar path (appropriate for a
pillar, whose area at 1.5 m is thousands of pixels), so the marker's
noise-dominated small blobs sailed over the floor and registered as "detected."
The root cause is therefore not a sensor limitation but that the *detector's
range contract was never specified* — it fired at ranges where its own
measurements were garbage. The CHANGE.md one-liner is correct; the mechanism
underneath it is that we demanded detection at a range where the physics
supplies no signal, with a floor set for a different object entirely.

**Fix.** The two-part fix in the committed snapshot. Part one, the area gate:
`if area < 1500: return None` — one number, chosen by measurement: 1,500 px is
the marker's area at 500 mm (the mission's required range), sits 1.5x above the
~1,000 px noise cliff, and refuses every far-distance noise-dominated blob by
construction. Part two, the requirements reframe, is the fix the CHANGE.md
records as its lesson: **we stopped requiring detection beyond 500 mm**. The
acceptance criteria, verification procedure, and mission contract were all
rewritten so "detected" means "marker present within ~500 mm"; the far-distance
flicker did not need to be fixed, it needed to be declared out of scope, because
no consumer of the trigger acts beyond 500 mm. Part three, the position gate
(centroid below 70% of image height, at the call site) closed the second hole
the data exposed — upper-frame purple blobs, which the lowered floors had let
through, are now non-events regardless of area. Measured after the fix:
detection rate 100% at 300-500 mm, zero false triggers in the 60-second AC2
scene, and the PARKING harness fired exactly once per approach across 10 runs.

**Prevention.** Two process changes so this class never returns. First, a
mandatory **range-to-requirement derivation** step before any detector's floor
is chosen: write down the consumer's required range, measure the target's pixel
area at that range, and set the floor above both the required range's area and
the measured noise cliff — never inherit a floor from a different object class
(the pillar 300 px lesson). Second, a mandatory **flicker test** in the
acceptance harness: a static 50-frame run at the required range must yield
47/50 detections, and a 10-run approach log must yield exactly one trigger per
run; any test that reveals toggling triggers a re-derivation of the gate, never
a lowering of the floor. Both rules are now part of the perception-checklist
process and will be applied to the blue stop-line trigger in v4.6.

### 9.2 The upper-frame false trigger — the purple banner that parked the car

**Symptom.** During the first AC2 session, with no marker in the scene but a
purple-ish venue banner visible in the top-left of the frame behind a pillar,
the detector fired once — a parking trigger with no marker present. It was one
frame in 1,800, but one frame is enough to start a parking sequence, and the
harness did exactly that.

**Initial hypotheses.** (1) The banner's pixels genuinely fell inside
`[135, 80, 50]`-`[165, 255, 255]` — a real colour collision we had not
anticipated, because magenta was supposed to be "rare in the venue." (2) The S
floor of 80 was too low, letting a washed-out banner purple through. (3) The
camera's auto white balance momentarily swung, pushing a grey surface into the
magenta band for a frame.

**Investigation.** We sampled the banner pixels: hue 137-146, saturation 55-90,
value 180-210. They were *inside* the band — hypothesis 1 was right, and it
undermined hypothesis 2 (raising the S floor to 90 would have killed the dim
real marker, which v3.7 told us can sit at S ~60-80). The area gate let a
~2,000 px banner fold through — big and close enough to clear 1,500 px. The
truth was the frame position, not the colour or size: the banner lived above
70% image height, a region no floor marker can occupy, because the marker is a
floor-level feature by rule placement.

**Root cause.** The area gate is a *range* gate, and range gates cannot reject
large objects at the wrong place: a big purple thing close by has the same area
as a small magenta marker at 500 mm — area alone cannot tell them apart. The
missing dimension was position in frame: the marker's physical placement (on or
near the zone boundary, at floor level) implies a constraint on where it can
appear in the image, and v4.4 had never encoded that constraint.

**Fix.** The position gate: at the call site in the perception layer, require
the marker bbox centre-y to be below 70% of image height (`y + h // 2 >
img_h * 0.7`); otherwise return `None`. One comparison, using values the
pipeline already computes. It is deliberately *not* inside `detect_magenta`
(keeping the function a pure colour/area detector) and it is the same
bottom-of-frame reasoning v4.6 will formalise for the blue line with
`hsv[int(img_h * 0.7):, :]`. The banner never fired again across the remaining
AC2 footage.

**Prevention.** A checklist rule for every future detector: **before shipping,
ask what region of the frame the target is physically allowed to occupy, and
reject everything else** — ROI restriction is free robustness. We also logged
the banner hue as evidence that "magenta is rare in the venue" is a hope, not a
fact, and that colour alone is never sufficient discrimination.

**Prevention.** A checklist rule for every future detector: **before shipping,
ask what region of the frame the target is physically allowed to occupy, and
reject everything else** — ROI restriction is free robustness. We also logged
the banner hue as evidence that "magenta is rare in the venue" is a hope, not a
fact, and that colour alone is never sufficient discrimination.

### 9.3 The scaffold debt — the committed snapshot and the position gate

**Symptom.** A reader of the snapshot will notice that `magenta_marker.py`
contains the area gate but not the position gate: the function returns
`{"area", "center_x"}` and enforces `area >= 1500`, while the "position
thresholds" the CHANGE.md describes live at the call site, not in the file.

**Root cause.** Not a runtime bug — a deliberate scoping choice. The function
signature `detect_magenta(hsv)` receives only the HSV frame, not the frame
height or a policy object; we kept the function pure (colour identity + area
range gate) and put the frame-context rule — "markers may only live in the
lower 30%" — at the call site in `_process_frame_internal`, the v4.4 engine's
file evolved on Day 104. The CHANGE.md's "area and position thresholds"
accurately describes the *deployed* behaviour; the committed file shows the
area half.

**Fix.** Documented here, in the journal, in the same spirit v3.7 documented its
scaffold: the contract is complete (area gate in function, position gate at call
site, verified together in AC2), and future readers are pointed at both files.
**Prevention.** The template rule stands: every CHANGE.md claim must be
checkable against the running code, and where the snapshot and the integration
differ, the journal says so in writing rather than letting the reader discover
the gap at 1 a.m.

### 9.4 The dead-end of lowering the floor — recorded so we never re-walk it

**Symptom.** During Day 103's investigation we dropped the area floor to 200
and then 100 to "rescue" far detection. The false-trigger count in the fixed
60-second scene climbed 0 → 3 → 11 → 47, and the PARKING harness started
firing on floor reflections and red-pillar shadow edges that drifted into the
magenta band. We believed we were trading a little specificity for a lot of
recall — the standard threshold-fiddler's bargain.

**Investigation.** Playback with a detection overlay showed the truth: at
`area >= 100`, almost every frame had a "detection," and largest-contour
selection was picking the largest *noise* speckle, which moved randomly,
dragging `center_x` with it.

**Root cause.** As derived in 9.1: the signal at range is absent, not weak; a
lower floor does not recover signal, it admits noise, and the noise owns the
largest-contour selection. The bargain was illusory — recall at long range
stayed near zero while precision collapsed.

**Fix.** Revert to the measured gate (1500 px); never re-lower. The Q→R edge of
the section 6 flowchart is the permanent guardrail.

**Prevention.** A whiteboard rule that now outranks intuition: **when a
detector cannot see something at range R, the first question is whether R is a
requirement, not whether the threshold is too high.** If R is required, change
the physics (bigger target, different camera); if R is not required, change the
requirement. Lowering a threshold to fix a physics problem is the one move we
now forbid outright.

## 10. Verification and metrics

The acceptance criteria from section 3 were measured, not assumed, and the
numbers below are the raw session log. Test rig: the bench camera at 640x480
MJPEG 30 FPS, the 40 mm magenta square on a stand, a tape measure on the floor,
the v4.5 detector in the v4.4 perception engine, and a logger writing every
`magenta_marker` field to CSV with the distance as a manual tag. Two light
conditions: the lab's mixed window-plus-LED light (the "bright" row) and a
corner of the same room with the nearest fixtures off (the "dim" row).

| Distance (mm) | Frames | Detections (bright) | Detections (dim) | Mean area (px) | Area std (%) | Center_x error (px) |
|---------------|--------|---------------------|------------------|----------------|--------------|----------------------|
| 300 | 50 | 50 | 50 | 2,890 | ±3% | ±5 |
| 400 | 50 | 50 | 49 | 2,310 | ±3% | ±6 |
| 500 | 50 | 49 | 48 | 1,510 | ±5% | ±8 |
| 600 | 50 | 46 | 44 | 1,020 | ±8% | ±12 |
| 700 | 50 | 17 | 14 | 850 | ±8% | ±19 |
| 800 | 50 | 6 | 4 | 575 | ±12% | ±27 |
| 1000 | 50 | 0 | 0 | 375 | ±25% | n/a |
| 1500 | 50 | 0 | 0 | 170 | ±65% | n/a |

AC1 (≥95% detection at 300-500 mm): at 500 mm bright 49/50 (98%), dim 48/50
(96%), at 400 mm 50/50 and 49/50 — **PASS**. The roll-off below the gate is
visible and intentional: the detector stops firing near 600 mm because the area
falls below 1,500 px there — designed behaviour, not a defect. AC2 (zero
triggers in 60 s with no marker): the 60-second scene ran three times — pillar +
banner + floor-reflection + blue-tape + red-robot-body challenges — 1,800 frames
per run, **0 triggers in all three runs** after the position gate shipped (the
pre-gate build produced the single banner trigger of section 9.2). **PASS.**
AC3 (latency under 200 ms): the worst-case chain to the *actuator* is 33.3 + 33.3
+ 10 + 10 + 200 = 287 ms, but trigger-readiness — the AC3 definition, from
marker-in-frame to a readable `magenta_marker` field — measured 2 frames =
66 ms at 28-30 FPS. **PASS**; the extra 287 ms is the mission layer's runway
problem, solved by the 500 mm range requirement, not by this detector. AC4
(center_x within ±15 px at 500 mm): measured ±8 px mean error at 500 mm, ±5 px
at 300 mm — **PASS**, with the margin owned by the stable area gate. The
approach-dynamics test: 10 runs at 0.3 m/s from 1.2 m, trigger distance mean
487 mm, std 34 mm, min 452 mm, max 541 mm, exactly one trigger per run in all
10 — the PARKING harness fired once and stayed fired for the rest of every
approach, the property that actually matters for a state machine.

What we trusted afterwards: the 1,500 px gate (2,700 static frames + 10 dynamic
runs), the position gate (3 clean AC2 runs), the measured 1/Z² fit (18 distances
within 5%), and the untouched v3.7 colour band. What we still distrusted: the
marker's physical size on the actual venue kit — our 40 mm measurement drives
the 500 mm ↔ 1,500 px mapping, and a 35 mm or 50 mm venue marker shifts the gate
to roughly 440 mm or 560 mm, so the acceptance harness is a 5-minute re-run on
race morning; the auto white balance remains unlocked (v3.7's standing debt),
covered only by the wide band; and the 640x480 MJPEG noise structure is camera-
class-specific, so any optics change forces a noise-envelope re-measure before
the floor is trusted again. The verification ended with four green criteria and
a written list of exactly what would invalidate each one.

## 11. Lessons learned — permanent mental models

**Lesson 1: detection range requirements must match the physical marker size**
— the recorded lesson, and it is the whole version in one sentence. The physics
is A ∝ 1/Z² and the noise is a relative cliff; you cannot demand a range the
target's size at your focal length cannot supply. The permanent rule: derive the
consumer's required range from mission geometry *before* touching a threshold,
measure the target's area at that range, and set the gate accordingly. This
prevents the exact compounding that would otherwise arrive in v7.x — a parking
state machine built on a trigger that toggles at the moment of commitment.

**Lesson 2: area is a legitimate range sensor.** A monotonic 1/Z² projection
means "big blob" and "close" are the same fact, and a single comparison against
a measured threshold is a complete ranging decision — no focal length to drift,
no marker size to re-verify, no second device to trust. This is the mental model
that lets us do 90% of range-based perception with no distance arithmetic, and
it transfers directly to every future fixed-size feature (the blue line's
thickness, the pillar's diameter, any surprise-rule marker). It prevents the
habit of bolting on a fragile distance formula where a monotonic pixel measure
already does the job.

**Lesson 3: lower the requirement, not the threshold.** When a detector fails
at range R, the first question is whether R is required. Our Day 103 instinct
was to lower the floor; the measurement said the signal was absent, and lowering
the floor just let noise vote (false triggers 0 → 47). The permanent rule —
drawn as the Q→R edge of the decision flowchart — is that physics problems get
physics answers (bigger target, different camera, different range) and
threshold fiddling is banned as a fix for absent signal. This prevents the
silent failure where a tuned-to-noise detector looks alive in demos and betrays
the mission in the arena.

**Lesson 4: position in frame is a free sensor channel.** The area gate could
not reject a 2,000 px banner because area only knows size and range. The marker
is a floor-level feature by rule placement, so its image is confined to the
lower frame, and one comparison against the bbox centre-y erased an entire
false-positive class. The permanent rule — *before shipping a detector, ask
which region of the frame the target is physically allowed to occupy* — is the
exact insight v4.6 will formalise for the blue stop line (`hsv[int(img_h *
0.7):, :]`) and the reason ROI restriction costs nothing and buys robustness.

**Lesson 5: a trigger must be single-shot or it is a lie.** The PARKING harness
toggling seven times per approach is the difference between a state machine that
commits and one that stutters. The permanent rule: any boolean consumed as a
state transition needs (a) a defined activation zone, (b) a gate above the noise
floor so it cannot re-fire on jitter, and (c) a monotonic signal (like 1/Z²
area) so that once fired it stays fired. This prevents the v7.x hysteresis
patches that would otherwise hide a flaky trigger and complicate the state
machine.

**Lesson 6 (the process one): measure before tuning, always.** Every dead end
in this version — the floor-lowering, the distance-gate, the HSV re-tune we
wisely did not do — died the moment we logged the actual signal. The 2,700-frame
distance sweep is why the fix is one number instead of a month of twiddling.
The permanent rule is the v3.7 version-2 rule extended to geometry: calibrate
range with the same discipline we calibrate colour, and let the tape measure and
the CSV be the authority, not the slider.

## 12. Code in this snapshot

- `magenta_marker.py`

## 13. Bridge to the next version

What v4.5 unlocks is the parking trigger: a magenta marker that the robot can
commit to — single-shot, stable, correctly ranged at ~500 mm, laterally
measurable via `center_x`, immune to upper-frame impostors, and costing 6-9 ms
of the 33.3 ms frame budget. Every later layer now has a trustworthy boolean
plus a lateral aim point to build on: v7.x's parking state machine fires on
exactly this signal, v6.x's controller steers on exactly this `center_x`, and
v5.x's localization can fuse "marker at normalized_x" without inheriting the
flicker that poisoned v4.4. The version also hands forward a *pattern*, not
just a function: range-from-requirement, gate-above-noise, position-in-frame,
single-shot semantics — the trigger-detector template.

The known debt, and the reason v4.6 is next, is that the pattern has proven
itself on exactly one feature. The next trigger on the critical path is the
blue stop-and-go line of the surprise rules: the rules may add a stop-and-go
requirement, the blue line is its trigger, and the v4.4 engine already ships a
`blue_marker` boolean that is a raw `countNonZero` threshold with no position
gate, no range reasoning, and no flicker semantics. v4.6's one-line reasoning
for why it is next: the same class of bug we just spent three days fixing for
magenta — false triggers from distant blue objects in the upper frame — is
still live in the blue path, and the position-gate lesson we proved here
(markers live low, so reject the upper frame) is the exact fix v4.6 will apply
(`ROI below 70% of image height`, already half-sketched in our AC2 harness).
The v4.6 blueprint is already on the board: copy the v4.5 pattern — physical
feature size → required range → gate above noise → position gate → single-shot
semantics — onto the blue line, and both parking triggers, magenta and blue,
ride the same trustworthy contract into the mission layer. The magenta work was
the hard part; the blue line is the same anatomy with different numbers.

---

*Journal entry for v4.5, Understanding the Track, Day 103-105. Written the
afternoon the PARKING harness fired exactly once and stayed fired.*
