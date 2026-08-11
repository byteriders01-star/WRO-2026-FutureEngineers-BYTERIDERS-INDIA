# Competition Scoring Map - v9.1
| Rule | Implementation |
|------|----------------|
| 13.21 Red pillar avoidance | layers/layer4_perception.py:82 (two-range red mask) + layer6_mission_manager.py:129 |
| 13.22 Green pillar avoidance | layers/layer4_perception.py:94 |
| 13.27 Magenta parking marker | layers/layer4_perception.py:98 |
| Stop-and-go blue line | layers/layer4_perception.py:106 |
| Emergency brake <180mm | layers/layer6_mission_manager.py:87 |
| 3-lap mission | layers/layer6_mission_manager.py:97 |
| Parallel parking | layers/layer6_mission_manager.py:106 |
| Surprise rule adapter | layers/layer6_mission_manager.py:5 |
| 15s stationary rule | layers/layer6_mission_manager.py:114 |
| Target: 122/122 pts | RELEASE_NOTES.md v9.9 |