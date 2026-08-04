# v8.5 — Full Parking Detector

## Diary Entry — 2026-04-18

Today I completed the parking detection module for our WRO 2026 robot. The new module, `parking_detector.py`, is responsible for detecting the parking markers, estimating the parking zone geometry, checking parking alignment, and providing the information required by the parking controller.

The detector uses the downward-facing camera to locate magenta parking markers. When four markers are detected, it computes the parking zone center and orientation. If only two or three markers are visible, the detector estimates the parking zone using the known parking dimensions instead of failing immediately.

## The Problem

During indoor testing the detector worked reliably. However, on the competition track, shadows occasionally reduced the visibility of the magenta markers.

Typical logs looked like this:

```text
[PARKING_DETECTOR] WARN: Only 2 markers detected
[PARKING_DETECTOR] WARN: Estimating parking zone
[PARKING_DETECTOR] WARN: Marker detection temporarily lost
```

The downward camera uses a fixed exposure under normal operation. When the robot entered darker regions of the track, the image became too dark and marker detection occasionally failed.

## The Solution

I implemented a simple adaptive exposure mechanism.

If no markers are detected for a configurable amount of time, the exposure compensation is increased until the configured maximum value is reached. As soon as markers are detected again, the exposure returns to its default value.

```python
if elapsed > self.config.exposure_adapt_delay_s:
    self._exposure_comp = min(
        self._exposure_comp + 1.0,
        self.config.max_exposure_comp,
    )
```

To improve robustness, the detector also supports partial observations.

- 4 markers → full parking zone computation
- 2–3 markers → estimated parking zone
- Fewer than 2 markers → detection fails

This allows the parking controller to continue operating even when one or two markers are temporarily hidden.

## Alternatives Considered

### 1. Infrared markers

Infrared markers would be less sensitive to visible-light changes but require additional hardware and sensors.

### 2. Ultrasonic localization

Ultrasonic sensors could estimate parking boundaries, but their beam width is too large for accurate parking alignment.

### 3. Retry-only approach

Continuously retrying marker detection without changing camera exposure is simple but does not solve prolonged shadow conditions.

The adaptive exposure approach was selected because it requires no additional hardware and integrates easily with the existing vision pipeline.

## Testing

Testing included:

- Detection with four visible markers
- Detection with three visible markers
- Detection with two visible markers
- Temporary marker loss
- Exposure recovery after prolonged detection failure

The detector successfully switched between full detection and estimated detection while automatically restoring the default exposure after markers became visible again.

## Statistics

- Module: `parking_detector.py`
- Adaptive exposure support
- Partial marker estimation supported
- Parallel parking threshold: 20 mm
- Default exposure adaptation delay: 2 seconds

## Lessons Learned

Lighting conditions have a significant impact on vision-based systems. A simple adaptive exposure mechanism greatly improves robustness without increasing system complexity. Supporting partial marker observations also makes the parking detector more tolerant of temporary occlusions during competition runs.

— 2026-04-18, signing off.