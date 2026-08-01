v8.7 — Real-Time Control Loop and Multi-Rate Updates
What Changed

As the robot software became more advanced, different modules required different update frequencies. Motor control and odometry needed fast, consistent updates for smooth driving, while computer vision naturally ran slower because each camera frame required OpenCV processing.

To improve responsiveness, I reorganized the software so that each subsystem runs at its own update rate while the main control loop always executes at a fixed frequency. The controller continuously uses the latest available sensor and perception data instead of waiting for every module to finish.

The final update rates are:

Module	Update Rate
Motor Control	100 Hz
Wheel Encoders	100 Hz
IMU	100 Hz
Odometry	100 Hz
State Machine	50 Hz
Camera Processing	15–20 FPS
Obstacle Detection	15–20 FPS
Parking Detection	15–20 FPS
Logging	1 Hz
The Problem

Initially, every module was executed sequentially inside one loop.

Read Sensors
↓
Capture Camera Frame
↓
Run OpenCV
↓
Detect Obstacles
↓
Update State Machine
↓
Calculate Steering
↓
Send Motor Commands

This worked well until image processing became expensive. Depending on the scene, OpenCV sometimes required 40–60 ms to process a frame. During this time the controller could not update the steering commands.

A timing log showed the issue clearly:

Control Loop

Cycle 1 : 10 ms
Cycle 2 : 11 ms
Cycle 3 : 49 ms
Cycle 4 : 10 ms
Cycle 5 : 51 ms
Cycle 6 : 10 ms

Whenever perception became slower, the steering controller also became slower because it was forced to wait for image processing to complete. This occasionally caused the robot to overshoot corners.

Investigation

I profiled the execution time of every module.

Wheel Encoder Update      0.2 ms
IMU Update                0.5 ms
Odometry                  0.7 ms
Stanley Controller        0.6 ms
Motor Output              0.3 ms

Camera Capture            8 ms
OpenCV Processing        32 ms
Obstacle Detection       11 ms

The controller itself was very fast. Almost all of the delay came from computer vision.

The important realization was that steering does not require a brand-new camera image every control cycle. The camera naturally produces only about 15–20 frames per second, while the controller can safely run at 100 Hz using the latest available perception result.

The Fix

Instead of forcing the controller to wait for the camera, I separated the perception updates from the control loop.

Whenever a new camera frame is processed, the perception module updates the latest obstacle and parking information. The controller simply reads the newest available data every cycle.

Camera
   │
OpenCV
   │
Latest Detection
   │
───────────────
100 Hz Control Loop
Read Sensors
Update Odometry
Read Latest Detection
Calculate Steering
Drive Motors
───────────────

This keeps steering updates consistent even if computer vision occasionally takes longer than expected.

Frame Validation

To prevent using outdated vision data, every processed frame stores a timestamp.

frame_age = current_time - detection.timestamp

if frame_age > 0.20:
    detection.valid = False

If a camera frame is older than 200 ms, the controller ignores it until a newer frame becomes available. During that time the robot continues driving using odometry and lane tracking.

Alternatives Considered
Alternative 1 – Single Control Loop

Simple to implement, but camera processing blocks steering updates whenever image processing becomes slow.

Alternative 2 – Multi-threading

Running perception and control in separate threads improves responsiveness but introduces synchronization complexity and possible race conditions.

Alternative 3 – Lower Camera Resolution

Reducing image resolution increases frame rate but decreases obstacle detection accuracy.

Alternative 4 – Independent Update Rates (Chosen)

Each subsystem runs at the rate it naturally requires while the controller always executes at a fixed frequency using the latest available data. This keeps steering smooth without sacrificing perception accuracy.

Testing

The new architecture was tested over multiple continuous runs.

Metric	Before	After
Control Loop	10–55 ms	Stable 10 ms
Camera Frame Rate	15 FPS	15–20 FPS
Steering Delay	Noticeable	Negligible
Missed Control Updates	Frequent	None Observed
Corner Tracking	Occasional Overshoot	Consistent

The robot maintained stable steering even when OpenCV processing time varied significantly.

Stats
Lines of code: 147 (scheduler.py)
Main Control Loop: 100 Hz
Camera Processing: 15–20 FPS
State Machine: 50 Hz
Logging: 1 Hz
Maximum Valid Frame Age: 200 ms

The controller now operates independently of camera processing delays, resulting in smoother steering and more reliable navigation.

Lessons Learned

Not every subsystem should run at the same frequency. Fast control loops and slower perception systems can work together effectively as long as the controller always has access to the latest valid information. Separating the timing of perception from motor control greatly improved the robot's responsiveness while keeping the software architecture simple and deterministic.