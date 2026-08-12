# WRO 2026 - ERROR CATALOG

The phase-by-phase catalog of every error this build hit, with what happened,
why it happened, the investigation (for the big ones), and the fix.

**Every entry is real.** The catalog is generated from the CHANGE.md history
chapters in `other/history/vX.Y/CHANGE.md` (section 9 of each chapter, "Errors,
failures, and root-cause analysis", and section 5.3, "Alternatives considered",
for the rejected designs) plus the engineering documentation
(`ENGINEERING_DOCUMENTATION.md`, `ENGINEERING_PARAMETER_JUSTIFICATION.md`).
Nothing was invented to fill a quota; the numbers below are the actual counts
of the documented errors.

## The nine phases

| File | Phase | Versions | Errors | E-range | BIG | SMALL |
|------|-------|----------|--------|---------|-----|-------|
| `v1-boot-and-ssh.txt` | BOOT AND SSH | v1.0 - v1.9 | 53 | E0001 - E0053 | 11 | 42 |
| `v2-drive-and-motor.txt` | DRIVE AND MOTOR | v2.0 - v2.9 | 64 | E0001 - E0064 | 11 | 53 |
| `v3-imu-sensors.txt` | IMU AND SENSORS | v3.0 - v3.9 | 63 | E0001 - E0063 | 12 | 51 |
| `v4-perception.txt` | PERCEPTION | v4.0 - v4.9 | 72 | E0001 - E0072 | 10 | 62 |
| `v5-localization.txt` | LOCALIZATION | v5.0 - v5.9 | 75 | E0001 - E0075 | 10 | 65 |
| `v6-control.txt` | CONTROL | v6.0 - v6.9 | 81 | E0001 - E0081 | 11 | 70 |
| `v7-mission.txt` | MISSION | v7.0 - v7.9 | 81 | E0001 - E0081 | 10 | 71 |
| `v8-integration.txt` | INTEGRATION | v8.0 - v8.9 | 76 | E0001 - E0076 | 11 | 65 |
| `v9-final-pipeline.txt` | FINAL PIPELINE | v9.0 - v9.9 | 50 | E0001 - E0050 | 12 | 38 |

## Totals

| Metric | Value |
|--------|-------|
| Errors documented across all versions | **615** |
| BIG errors (needed an investigation) | 98 |
| SMALL errors (one-line fixes) | 517 |
| Chapters parsed | 90 (v1.0 - v9.9) |
| Source | `other/history/vX.Y/CHANGE.md` sections 9 and 5.3, plus the engineering documentation |

## Entry anatomy

Every entry in the phase files looks like this (E0001 of phase 1, real):

```
E0001 | v1.0 | BIG | Found Day 2 | Fixed in 1 day | after creating the repo structure
File : skeleton_main.py
Error : ModuleNotFoundError: No module named 'layers'
Terminal : after creating the repo structure

WHAT HAPPENED
On Day 2, after creating the repo structure, we launched the
entry script through our launcher — a shell wrapper that
`cd`'d to the robot home directory and invoked the Python
module by `-m` form. The interpreter aborted before printing
anything: `ModuleNotFoundError: No module named 'layers'`,
with the traceback pointing at the `import layers` line in
our working-tree main.py. The crash was total and immediate:
exit code 1, zero output. The same file, run as `python3
main.py` from inside the project root, worked fine. That
split behavior — works from one directory, dies from another
— was the most important clue we almost missed.

WHY IT HAPPENED
Python resolves imports by walking `sys.path` in order:
`sys.path[0]` first, then `PYTHONPATH` entries, then the
standard library, then site-packages. The crucial detail is
what occupies `sys.path[0]`, and it is decided by *how the
interpreter was launched*, not by where the code lives. When
a script is run directly (`python3 file.py`), Python inserts
the directory containing the script — the project root, in
our case — as `sys.path[0]`. When a module is run with `-m`,
Python inserts the *current working directory*. When a file
is imported rather than run, the top-level script's
directory rules and the imported module is found relative to
the importing script. Our launcher used the `-m` form from a
home directory, so `sys.path[0]` was the home directory; the
project root — and therefore the `layers/` package nested
under it — was simply not on the search path at all. The
interpreter reported "no module named layers" with perfect
accuracy: there was no such module *on its path*. The
mechanism is subtle because it is silent in the happy case:
from the project root both invocation styles happen to work,
which is exactly why the bug survived until the launcher
came along. Two mechanical details of the root cause are
worth pinning down because they generalize to every Python
tool this team will write. First, the empty string: when
Python is launched with `-c` or interactively, `sys.path[0]`
is the empty string, which the interpreter resolves to "the
current working directory" at the moment each import is
looked up — meaning even interactive sessions are
cwd-sensitive, and our early guess that the environment was
the problem was backwards in the interesting direction: the
environment was not missing something, the *launch* was
supplying the wrong something. Second, the
relative-`__file__` caveat: under `python3 -m module`,
`__file__` can arrive as a relative path, so
`os.path.dirname(__file__)` resolves against the process cwd
at run time rather than being handed an absolute path. In
our layout it still resolved to the project root, which is
why the append worked on every tested launch path — but the
transferable lesson is that a path anchored on `__file__` is
only as absolute as the interpreter's invocation, and entry
scripts that may be launched under `-m` should harden the
anchor with `os.path.abspath` as insurance. We kept the
committed one-liner exactly as written because every launch
style we could produce in the lab resolved to a correct
absolute anchor, and we logged the abspath hardening as a
low-cost review item for the first real launcher in v2.

INVESTIGATION (only for BIG errors)
We stopped guessing and started measuring the search path
itself. The decisive experiment: run `python3 -c "import
sys; print(sys.path)"` and compare `sys.path[0]` under four
invocation styles. Under ...

FIX (took N days)
The exact change, committed as line 2 of `skeleton_main.py`:
`sys.path.append(os.path.dirname(__file__))`, placed after
the stdlib imports and before any project import. Why this
is correct: `__file__...
```

Field mapping (all from the real chapter text):

| Catalog field | Source in the chapter |
|---------------|-----------------------|
| `Found Day N` | the `Day N` mention in the error's Symptom |
| `File` | the code file(s) named in the error's text; else the version's snapshot files |
| `Error` | the first error text quoted in the error's text |
| `Terminal` | where the error was observed, from the Symptom text |
| `WHAT HAPPENED` | the chapter's `**Symptom.**` paragraph |
| `WHY IT HAPPENED` | the chapter's `**Root cause.**` paragraph |
| `INVESTIGATION` | the chapter's `**Investigation.**` paragraph (BIG entries only) |
| `FIX` | the chapter's `**Fix.**` paragraph |
| `SMALL` vs `BIG` | BIG = the version's flagged/primary/headline errors; SMALL = the rest |

## How it was built

1. `python issues/scripts/error_catalog_data.py` - reads the 90 chapters and
   extracts every error block (heading, day, symptom, hypotheses, investigation,
   root cause, fix, prevention), the rejected designs of section 5.3, and the
   documented errors of the engineering documentation, into
   `issues/scripts/error_catalog.json`.
2. `python issues/scripts/error_catalog_generator.py` - writes the nine phase
   files and this README from that JSON.
3. `python issues/scripts/error_catalog_reader.py` - read-only helpers to query
   the catalog (totals, per-version summaries, keyword search).

## Honest gaps

- Every chapter yields at least one entry, but the extraction strength varies
  with the chapter's own format. Chapters that labeled every section
  (`**Symptom.**`, `**Root cause.**`, ...) yield fully split entries;
  chapters written as prose or with combined labels (v2.1, v3.1, v4.4) yield
  entries whose WHY/FIX text carries the chapter's wording as-is.
- "Fixed in N days" is derived from the version's recorded day span, not from
  a per-error fix log (the chapters do not log fix timestamps).
- 11 chapters carry no version title (v1.3, v1.5, v2.1, v2.8, v2.9, v3.0, v3.3, v3.6, v3.8, v4.1, v4.4); those files show the version number in the heading.
- The engineering-documentation entries sit under "## THE ENGINEERING
  DOCUMENTATION" at the end of each phase file. The docs do not log days, so
  those entries show "Found Day n/a | Fixed in n/a" and FIX without a day count.
- Each phase file targets 230 real errors where the source material allows;
  the per-file totals above are the actual counts of what the sources document.
