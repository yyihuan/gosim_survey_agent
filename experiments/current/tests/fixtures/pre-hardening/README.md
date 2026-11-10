# Frozen regression reference

These two files are byte-for-byte copies from public commit `fedf2fbc`, the parent
of the model-boundary hardening change `dee21c62`. They also match the original
local-only baseline used by the trajectory test. Do not edit them to make tests pass.

| Original path under `experiments/current/agent/agent_core/` | SHA-256 |
| --- | --- |
| `llm_client.py` | `b822e085a981b80f9a724f02c3fa66a7ea3b65f38f111c963a68f50f98da8326` |
| `planner.py` | `a7447798f19d0dbc82ef39cc6d523826d17bd91278a6e1aca0b85aa0674377ad` |

The test loads them only to compare offline decisions with the current planner.
Other modules come from the current agent. This is a two-module regression
reference, not an independent historical installation. All model transport is
disabled in this comparison. Attribution and third-party terms remain governed by
[NOTICE](../../../../../NOTICE.md); these copies do not acquire a new license.
