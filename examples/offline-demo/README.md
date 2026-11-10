# Offline protocol walkthrough

From the repository root, with Python >=3.9:

```bash
python3 -I -B scripts/demo_offline.py
```

`input.jsonl` contains newly constructed public protocol messages, a fictional
site, a single synthetic target, and a scripted storm bulletin. It contains no
task-card truth, private seeds, credentials, or original conversation material.
The target's right ascension was set to the agent's local sidereal angle at the
first observing time so that a useful target is visible in this small example.

| Sequence | Scripted situation | Expected response |
| --- | --- | --- |
| 1 | Decision arrives before initialization | Wait 900 seconds, deterministic fallback |
| 2 | Before the observing night | Wait until 12:00 UTC |
| 3 | Target visible during the night | Observe `demo-target`, 600 seconds, DARK program |
| 4 | Public bulletin reports an all-sky storm | Wait 300 seconds |
| 5 | No observing night remains | Finish |

The actual entry point runs in a child interpreter with a fresh temporary working
directory and a small environment allowlist. Python socket/HTTP connection
attempts are blocked and counted; this is a guard for the trusted Python code,
not an OS sandbox for arbitrary untrusted programs. No `.env` is read, model
credentials are not inherited, and model usage is explicitly disabled.

`expected.json` captures the reviewed response fields. The script compares all
five messages and checks the agent's zero-call finish log. It exits nonzero on
a mismatch, network attempt, missing finish evidence, or child-process failure;
the child has a 15-second timeout. `--out` refuses an existing output directory.

This fixture does not advance an official engine or return scored observations.
The timestamps and bulletin are prescribed inputs; there is no claim that they
are a measured competition trajectory. It exercises one target and one site,
not catalogue-scale performance, all protocol edge cases, or model quality.
