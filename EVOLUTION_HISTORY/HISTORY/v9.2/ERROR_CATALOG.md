# Error Catalog - v9.2
| # | Symptom | Root cause | Fixed in |
|---|---------|-----------|----------|
| 1 | I2C bus contention | 3x VL53 share 0x29 | v1.6 XSHUT sequencing |
| 2 | Left/Right range +50mm error | mounting offset | v3.5 -50mm offset |
| 3 | Front ranging slow | default budget 100ms | v3.5 33ms budget |
| 4 | Motor forward only | ENA on non-PWM pin | v1.3 |
| 5 | Lost first serial byte | stale RX buffer | v1.5 flush |
| 6 | Servo jitter extremes | out-of-range pulses | v1.4 limit +/-35 |
| 7 | Red not detected | hue wrap at 0 | v3.7 two ranges |
| 8 | Lap double count | no cooldown | v7.2 15s + 800mm |
| 9 | UKF wrong weights | typo Merked/Merwe | v5.4 |
| 10 | STBY read fault | floating pin | v9.7 pull-up |