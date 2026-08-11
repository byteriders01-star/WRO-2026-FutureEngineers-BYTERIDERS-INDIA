# Cleanup Notes - v9.5
- removed: logs/, *.csv, *.npz calibration captures
- moved: all calibration to utils/calibrate_imu.py, utils/calibrate_hsv.py
- .gitignore covers __pycache__, logs, csv
- git status --porcelain verified clean
- kept: real bugs documented in ERROR_CATALOG.md v9.2