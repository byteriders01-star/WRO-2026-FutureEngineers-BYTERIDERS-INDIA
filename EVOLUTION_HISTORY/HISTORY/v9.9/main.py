"""
======================================================================================
  WRO 2026 AUTONOMOUS 4WS — MAIN ENTRY POINT
  Raspberry Pi 4B  ·  ESP32-S3  ·  Single Servo Mechanical 4WS
======================================================================================

5-LED BOOT SEQUENCE (all green, OFF = problem)
─────────────────────────────────────────────
  Power ON (Switch 1):
    LED1 ON  → main.py started
    LED2 ON  → sensors healthy
    LED3 ON  → camera healthy
    LED4 ON  → ESP32 serial alive
    LED5 OFF → not racing yet

  Switch 2 pressed (Race Start):
    LED5 BLINKS 2 Hz → robot racing

  Mid-race fault:
    That LED goes OFF instantly:
      LED2 OFF → sensor timeout
      LED3 OFF → camera lost
      LED4 OFF → serial lost (emergency stop)
      LED5 OFF → race loop stopped
======================================================================================
"""
import time
import os
import sys
import logging

sys.path.append(os.path.dirname(__file__))

from layers.layer0_system_manager  import SystemManager
from layers.layer1_sensors          import SensorLayer
from layers.layer2_time_sync        import TimeSyncLayer
from layers.layer3_sensor_fusion    import SensorFusionLayer
from layers.layer4_perception       import PerceptionLayer
from layers.layer5_localization     import LocalizationLayer
from layers.layer6_mission_manager  import MissionManagerLayer
from layers.layer7_path_planner     import PathPlannerLayer
from layers.layer8_trajectory_opt   import TrajectoryOptimizationLayer
from layers.layer9_kinematics_4ws   import Kinematics4WSLayer
from layers.layer10_controller      import MotionControllerLayer

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "robot_config.json")

SERIAL_FAULT_THRESHOLD = 5   # Consecutive TX failures before declaring serial lost


# ─────────────────────────────────────────────────────────────────────────────
# BOOT HELPERS
# ─────────────────────────────────────────────────────────────────────────────

def _check_sensor_flags(raw: dict) -> tuple[bool, str]:
    """Returns (all_ok, status_string). Failed sensor → flag=False, never blocks."""
    flags = raw.get("flags", {})
    parts = []
    all_ok = True
    for key, label in [("front_ok", "Front"),
                       ("left_ok",  "Left"),
                       ("right_ok", "Right"),
                       ("mpu_ok",   "MPU")]:
        ok = flags.get(key, False)
        parts.append(f"{label}={'✓' if ok else '✗'}")
        if not ok:
            all_ok = False
    return all_ok, "  ".join(parts)


def _probe_serial(layer10_ctrl: MotionControllerLayer) -> bool:
    """Send a zero-command packet to check ESP32 serial is alive."""
    try:
        layer10_ctrl.transmit_command(servo_angle_deg=0.0, motor_speed=0.0)
        time.sleep(0.05)
        return True
    except Exception as exc:
        logging.error(f"[MAIN] ESP32 serial probe failed: {exc}")
        return False


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────
def main():
    print("=" * 70)
    print("   WRO 2026  ·  4WS AUTONOMOUS ROBOT  ·  SYSTEM BOOT           ")
    print("=" * 70)

    # ── Layer 0: System Manager ───────────────────────────────────────────
    sys_mgr       = SystemManager(CONFIG_PATH)
    led_mgr       = sys_mgr.led_mgr
    switch_poller = sys_mgr.switch_poller
    config        = sys_mgr.config
    loop_freq     = config.get("system", {}).get("loop_frequency_hz", 100)
    target_dt     = 1.0 / loop_freq

    # ── LED1 ON immediately (system is alive) ─────────────────────────────
    led_mgr.set_system(True)
    logging.info("[MAIN] ▶ LED1 ON  — System booting…")

    # ── Instantiate all layers (non-blocking) ─────────────────────────────
    layer1_sensors = SensorLayer(config)          # async I2C poll thread starts
    layer2_tsync   = TimeSyncLayer(buffer_size=50)
    layer3_fusion  = SensorFusionLayer(config)
    layer4_percep  = PerceptionLayer(config)      # async vision thread starts
    layer5_local   = LocalizationLayer(config)
    layer6_mission = MissionManagerLayer(config)
    layer7_path    = PathPlannerLayer(config)
    layer8_traj    = TrajectoryOptimizationLayer(config)
    layer9_kin     = Kinematics4WSLayer(config)
    layer10_ctrl   = MotionControllerLayer(config)

    # Allow sensor/camera threads to settle
    time.sleep(0.6)

    # ── Phase 2a: Sensor Health Check → LED2 ─────────────────────────────
    raw = layer1_sensors.read_sensors()
    sensors_ok, sensor_desc = _check_sensor_flags(raw)
    logging.info(f"[MAIN] Sensor Status: {sensor_desc}")

    if sensors_ok:
        sys_mgr.set_sensor_health(True)    # LED2 ON  ✓
        logging.info("[MAIN] ▶ LED2 ON  — Sensors OK")
    else:
        sys_mgr.set_sensor_health(False)   # LED2 OFF ✗  (degraded, not halt)
        logging.warning("[MAIN] ⚠ LED2 OFF — Sensor(s) degraded — continuing with last-known values")

    # ── Phase 2b: Camera Health Check → LED3 ─────────────────────────────
    # PerceptionLayer reports readiness via is_ready() flag
    camera_ok = getattr(layer4_percep, "is_ready", lambda: True)()
    if camera_ok:
        sys_mgr.set_camera_health(True)    # LED3 ON  ✓
        logging.info("[MAIN] ▶ LED3 ON  — Camera OK")
    else:
        sys_mgr.set_camera_health(False)   # LED3 OFF ✗
        logging.warning("[MAIN] ⚠ LED3 OFF — Camera not available — vision fallback active")

    # ── Phase 2c: ESP32 Serial Health Check → LED4 ───────────────────────
    serial_ok = _probe_serial(layer10_ctrl)
    if serial_ok:
        sys_mgr.set_serial_health(True)    # LED4 ON  ✓
        logging.info("[MAIN] ▶ LED4 ON  — ESP32 Serial link alive")
    else:
        sys_mgr.set_serial_health(False)   # LED4 OFF ✗  → HALT
        logging.critical("[MAIN] ✗ LED4 OFF — ESP32 NOT CONNECTED! Fix serial and reboot.")
        logging.critical("[MAIN] LED1 = ON (system running), LED4 = OFF (no ESP32) → HALTED")
        while True:
            time.sleep(1.0)   # Hold here; operator must fix hardware

    # ── Phase 3: All LEDs 1-4 ON — Wait for Switch 2 ─────────────────────
    logging.info("[MAIN] ▶ LED1-LED4 all ON — Ready! Waiting for Switch 2 (Race Start)…")

    while True:
        if switch_poller.is_pressed():
            logging.info("[MAIN] ▶ Switch 2 PRESSED — RACE START!")
            led_mgr.start_race()           # LED5 blinks 2 Hz
            logging.info("[MAIN] ▶ LED5 BLINKING — Race Active")
            break
        time.sleep(0.05)

    # ── Phase 4: 100 Hz Race Control Loop ─────────────────────────────────
    commanded_steering_rad = 0.0
    commanded_speed        = 0.0
    sys_mgr.running        = True
    serial_fail_count      = 0

    try:
        while sys_mgr.running:
            loop_start = time.time()

            # ── Non-blocking sensor fetch ─────────────────────────────────
            raw        = layer1_sensors.read_sensors()
            perception = layer4_percep.process_frame(frame=None)
            flags      = raw.get("flags", {})

            front_ok = flags.get("front_ok", True)
            left_ok  = flags.get("left_ok",  True)
            right_ok = flags.get("right_ok", True)
            mpu_ok   = flags.get("mpu_ok",   True)

            # ── LED2: update live sensor health ───────────────────────────
            sensors_now_ok = front_ok and left_ok and right_ok and mpu_ok
            if sensors_now_ok != sys_mgr.health_status["sensors_ok"]:
                sys_mgr.set_sensor_health(sensors_now_ok)
                if not sensors_now_ok:
                    logging.warning(
                        f"[MAIN] LED2 OFF — Sensor timeout: "
                        f"F={'✓' if front_ok else '✗'}  "
                        f"L={'✓' if left_ok  else '✗'}  "
                        f"R={'✓' if right_ok else '✗'}  "
                        f"MPU={'✓' if mpu_ok  else '✗'}"
                    )
                else:
                    logging.info("[MAIN] LED2 ON — Sensors recovered")

            # ── LED3: camera health check ─────────────────────────────────
            cam_ok = perception.get("camera_ok", True)
            if cam_ok != sys_mgr.health_status["camera_ok"]:
                sys_mgr.set_camera_health(cam_ok)

            # ── Layer 2: Time-Sync ────────────────────────────────────────
            layer2_tsync.push_frame(raw, perception)
            synced_frame = layer2_tsync.get_latest_frame()

            # ── Layer 3: EKF Sensor Fusion ────────────────────────────────
            fused_state = layer3_fusion.update(
                synced_frame, commanded_speed, commanded_steering_rad
            )

            # ── Layer 5: Localization ─────────────────────────────────────
            localization = layer5_local.update(fused_state, raw)

            # ── Layer 6: Mission Manager & Surprise Rules ─────────────────
            mission_status = layer6_mission.update_state(perception, raw, localization)

            # ── Layer 7: Path Planning ────────────────────────────────────
            path_plan = layer7_path.plan_path(localization, mission_status)

            # ── Layer 8: Trajectory Optimization ─────────────────────────
            traj_opt = layer8_traj.optimize(path_plan, raw, mission_status)

            # ── Layer 10: Stanley Controller ─────────────────────────────
            ctrl_output = layer10_ctrl.compute_control(localization, path_plan, traj_opt)
            commanded_steering_rad = ctrl_output["desired_steering_rad"]
            commanded_speed        = ctrl_output["target_speed"]

            # ── Layer 9: 4WS Kinematic Model ─────────────────────────────
            kin_output      = layer9_kin.compute_steering(commanded_steering_rad)
            servo_angle_deg = kin_output["servo_angle_deg"]

            # ── Transmit to ESP32 → LED4 health ──────────────────────────
            try:
                layer10_ctrl.transmit_command(servo_angle_deg, commanded_speed)
                if serial_fail_count > 0:
                    # Recovered from serial fault
                    sys_mgr.set_serial_health(True)
                    logging.info("[MAIN] LED4 ON — Serial link recovered")
                serial_fail_count = 0

            except Exception as tx_err:
                serial_fail_count += 1
                logging.error(
                    f"[MAIN] Serial TX error #{serial_fail_count}: {tx_err}"
                )
                if serial_fail_count >= SERIAL_FAULT_THRESHOLD:
                    sys_mgr.set_serial_health(False)   # LED4 OFF
                    led_mgr.stop_race()                 # LED5 OFF
                    logging.critical(
                        "[MAIN] LED4 OFF + LED5 OFF — ESP32 lost! Emergency Stop."
                    )
                    # Loop continues trying to recover serial link
                continue

            # ── Performance counters ──────────────────────────────────────
            sys_mgr.update_performance()

            # ── 100 Hz timing ─────────────────────────────────────────────
            elapsed    = time.time() - loop_start
            sleep_time = target_dt - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

            # ── Heartbeat log every 0.5 s ─────────────────────────────────
            if sys_mgr.loop_counts % 50 == 0:
                logging.info(
                    f"FPS:{sys_mgr.get_fps():.1f}  "
                    f"Latency:{sys_mgr.get_average_latency_ms():.2f}ms  "
                    f"State:{mission_status['state']}  "
                    f"Servo:{servo_angle_deg:.1f}°  Speed:{commanded_speed:.1f}%  │  "
                    f"LED2={'ON' if sys_mgr.health_status['sensors_ok'] else 'OFF'}  "
                    f"LED3={'ON' if sys_mgr.health_status['camera_ok']  else 'OFF'}  "
                    f"LED4={'ON' if sys_mgr.health_status['serial_ok']  else 'OFF'}  │  "
                    f"F:{raw['front_mm']:.0f}mm  "
                    f"L:{raw['left_mm']:.0f}mm  "
                    f"R:{raw['right_mm']:.0f}mm"
                )

    except KeyboardInterrupt:
        logging.info("[MAIN] KeyboardInterrupt — shutting down.")

    finally:
        sys_mgr.running = False
        layer1_sensors.stop()
        layer4_percep.stop()
        try:
            layer10_ctrl.transmit_command(0.0, 0.0)
        except Exception:
            pass
        sys_mgr.shutdown()   # All 5 LEDs OFF
        logging.info("[MAIN] System terminated. All 5 LEDs OFF.")


if __name__ == "__main__":
    main()
