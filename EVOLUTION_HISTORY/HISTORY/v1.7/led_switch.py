import time
try:
    import board, digitalio
    def led(pin):
        l = digitalio.DigitalInOut(pin); l.direction = digitalio.Direction.OUTPUT; return l
    sw = digitalio.DigitalInOut(board.D16)
    sw.direction = digitalio.Direction.INPUT; sw.pull = digitalio.Pull.UP
    leds = [led(getattr(board, f"D{p}")) for p in (5, 6, 13, 19, 26)]
    for l in leds: l.value = True; time.sleep(0.1)
    for l in leds: l.value = False
    last = sw.value
    while True:
        v = sw.value
        if v != last:
            last = v
            if not v: print("SWITCH 2 PRESSED")
        time.sleep(0.05)
except ImportError:
    print("SIMULATION: switch would start race")