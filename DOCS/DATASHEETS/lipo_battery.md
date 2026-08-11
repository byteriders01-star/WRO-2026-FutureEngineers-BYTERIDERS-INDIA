<!--
=============================================================================
WRO 2026 — 4WS AWD Autonomous Robot
File: docs/datasheets/lipo_battery.md
Component: LiPo 3S battery (power source)
=============================================================================
-->

# LiPo 3S Battery

The single power source. Everything draws from it through the
protection chain (switch → fuse → polarity protection → cutoff).

## Specs

| Parameter       | Value                                   |
| --------------- | --------------------------------------- |
| Chemistry       | LiPo 3S (3 cells in series)             |
| Nominal voltage | 11.1 V (3.7 V per cell)                 |
| Capacity        | 2000 mAh                                |
| Energy          | 22.2 Wh                                 |
| C-rating        | 25C → ~50 A burst                       |
| Cutoff voltage  | 3.3 V/cell → 9.9 V total (buzzer warns) |
| Weight          | ~100 g (fits the 1.5 kg limit)          |
| Connector       | XT60                                    |

## Power Rail Connection

* Battery → main switch → 10A fuse → polarity protection → three rails
  (motor / 5V / servo). See `POWER_DISTRIBUTION.md` Section 2.
* Motor rail receives the battery voltage directly.
* 5V rail is generated using a dedicated buck converter.
* Servo rail is regulated separately as required.

## Protection Notes

* Below 3.3 V/cell, the LiPo may be permanently damaged — the low-voltage
  cutoff + buzzer is mandatory, not optional.
* Runtime estimate: ~35–40 min of mixed driving at ~18.2 W average load;
  a 3-minute WRO round uses less than 10%.
* Store at ~3.8 V/cell; charge only with a LiPo balance charger.
* Do not connect the 3S battery directly to 5V or 3.3V electronics.
* Verify that all motor, regulator, and servo components are rated for the
  3S battery voltage before operation.

## Official Datasheet

* None — generic 3S LiPo. Use the manufacturer's charge/discharge
  specifications for the exact pack.
