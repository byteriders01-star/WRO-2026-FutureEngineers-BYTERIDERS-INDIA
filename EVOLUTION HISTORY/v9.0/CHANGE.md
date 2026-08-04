v9.0 — Code Documentation Pass (Competition Readiness)
What Changed

Version 9.0 focused on improving code readability and maintainability after several months of rapid feature development.

Between v2 and v8, the robot software gained multiple complex systems including perception, localization, control, state machines, communication protocols, and safety monitoring. While the functionality was complete, many modules lacked proper documentation, making it difficult for new developers or reviewers to understand the design without reading the entire implementation.

A complete documentation pass was performed across all Python files in pi/ and C files in esp/main/.

Documentation Improvements Added
1. Module-Level Documentation

Every source file now contains a header explaining:

Purpose of the module
Inputs and outputs
Main responsibilities
Related modules
Important design decisions
2. Class Documentation

All classes now include documentation describing:

Their role in the system architecture
Interaction with other subsystems
Important configuration parameters
Expected behaviour
3. Function and Method Documentation

Every function now documents:

Purpose
Parameters
Return values
Error handling behaviour
Important edge cases
4. Inline Comments

Complex sections were documented with additional explanations, including:

CRC calculation logic
UKF prediction and update steps
State machine transitions
Sensor filtering
Communication handling

The goal was not to describe what the code does line-by-line, but why the implementation works this way.

5. Constant and Configuration Documentation

All important constants were documented.

Examples:

Sensor thresholds
Control gains
Timing intervals
Communication parameters

Each comment explains the purpose of the value and the expected impact if modified.

6. Architecture References

Added cross-references between related modules.

Example:

# Communication format is defined in protocol.py
# and parsed by packet_handler.py

This makes navigation between subsystems easier.

Errors Encountered and Fixed
Error 1: Stale Comments After Code Changes

During the initial documentation process, comments were written while the codebase was still changing.

For example, pillar_detector.py originally contained:

# Red detection range: H 0-10

Later, the detection logic was improved to handle red hue wrapping:

# Red detection range: H 0-10 and 170-180

The old comment became incorrect and could mislead future developers.

Fix

The documentation process was changed:

Complete all feature development first.
Freeze the codebase.
Create a documentation branch.
Write and verify documentation against the final implementation.

This ensured every comment matched the actual behaviour.

Error 2: Missing Exception Path Documentation

Initial documentation focused mainly on normal execution flow.

For example, the scheduler documentation explained successful task execution but ignored task failures.

The final documentation now includes:

What happens when callbacks fail
Whether tasks are removed or continued
How errors are reported
How recovery is handled

Example:

async def spin_once(self):
    """
    Execute one scheduler cycle.

    For each active task:
    1. Check whether execution period has elapsed.
    2. Calculate timing jitter.
    3. Execute callback.
    4. Catch and log exceptions.
    5. Continue scheduler operation.
    
    Failed tasks are not automatically removed.
    The health monitoring system handles fault decisions.
    """
Error 3: Inconsistent Documentation Style

Different files used different documentation formats:

Google-style docstrings
NumPy-style docstrings
Simple comments

This reduced readability.

Fix

A single documentation standard was selected:

Python

Google-style docstrings
Args:
Returns:
Raises:

C

Structured block comments
@param
@return

Module Headers

Standard 80-character documentation blocks
Alternatives Considered
1. Automatic Documentation Generation

Tools such as Sphinx were considered to generate documentation automatically.

Advantages:

Less manual effort
Generates structured documentation

Disadvantages:

Cannot explain design decisions
Cannot describe hardware constraints
Cannot explain why a particular algorithm was selected

For a robotics competition repository, manually written engineering documentation provides more value.

2. README-First Documentation

Another approach was to document the architecture first and update the code afterwards.

Advantages:

Clear planning approach

Disadvantages:

The software was already developed.
Retrofitting documentation was more practical.
3. Automated Comment Generation

Automatic comment generation was tested on complex files.

While it could describe what the code was doing, it often missed important project-specific decisions, such as:

Why UKF was selected instead of EKF
Why specific sensor thresholds were chosen
Why certain safety checks exist

Final documentation was therefore manually reviewed and rewritten.

Refactoring During Documentation

While reviewing the code, several functions were identified as difficult to understand.

Example:

process_packet() in main.c had grown to approximately 200 lines.

It was divided into smaller helper functions:

Packet validation
Command extraction
Data processing
Response generation

This improved readability and reduced debugging complexity.

Lessons Learned
Documentation should be completed after stabilising the implementation.
Comments must explain design decisions, not just repeat the code.
Exception paths are equally important as normal execution paths.
Consistent documentation style improves maintainability.
Cross-references between modules make large systems easier to navigate.
Clear code structure is more valuable than excessive comments.

Version 9.0 marks the transition from a feature-focused codebase to a competition-ready and maintainable robotics platform.