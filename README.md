# Survey Agent — planning observations under uncertainty

A Python survey-planning agent and research workspace for the **GOSIM 2026
Agentic Observer Challenge**. The task is to choose where to point a simulated
telescope, assign targets to fibres, and choose exposure times while weather,
visibility, required targets, and limited time compete for attention.

This portfolio edition makes the published `dee21c62` implementation easy to
inspect and run. It includes a credential-free demo, reproducible regression
tests, and an evidence-based account of AI-assisted development. It does not
bundle later local strategy or predictor branches.

**Start here:** [run the demo](#run-in-under-a-minute) ·
[read the development case study](docs/portfolio/ai-collaboration.md) ·
[inspect verification](docs/portfolio/verification.md) ·
[中文技术文档](docs/README.md)

## What this project demonstrates

- **Problem formulation:** separate public observations from hidden simulation
  truth, and distinguish a higher local score from evidence of generalisation.
- **Software engineering:** JSONL protocol handling, deterministic fallback,
  bounded model requests, reply validation, and optional redacted audit events.
- **AI-assisted development:** turn questions into bounded tasks, preserve
  experiment and decision records, and verify generated work with executable tests.

The agent builds on the organizers' Python example. Local adaptations include
offline execution, experiment tooling, and model-boundary hardening; this is not
a claim to have invented the upstream planner. The public decision record
documents the project owner's choices about goals and evaluation stages.
Individual coding ownership and any other human team members have not yet been
confirmed for this portfolio. See [contribution evidence](docs/portfolio/ai-collaboration.md#roles-and-attribution).

## Run in under a minute

Use **Python 3.9 or newer**, from this repository's root. No installation, API
key, account, task-card download, or third-party package is required.

```bash
python3 --version
python3 -I -B scripts/demo_offline.py
```

The script feeds synthetic public messages into the existing `agent.py` entry
point. It checks the full response against a checked-in expected transcript.
The five actions are:

```text
wait → wait → observe → wait → finish
```

The report must say `status: pass`, `responses: 5`, `network_attempts: 0`, and
`llm_calls: 0`. Optionally save the response and log into a **new** directory:

```bash
python3 -I -B scripts/demo_offline.py --out demo-result
python3 -I -B -m unittest discover -s experiments/current/tests
```

The demo clears inherited credentials and configuration, explicitly disables
models, and blocks Python socket/HTTP connection attempts. It is a scripted
protocol replay, **not a full simulator run or a score benchmark**. Read the
[fixture walkthrough](examples/offline-demo/README.md) for inputs and limitations.
Running the production entry point directly has different defaults: models are
enabled unless `USE_LLM=0` is set.

## How the agent works

![Public messages enter state tracking and a planner; optional model advice is checked before use, and actions are validated before a JSONL response.](docs/diagrams/portfolio-agent-flow.svg)

The program performs geometric search, fibre assignment, and exposure selection.
The optional model client supplies bounded nightly advice and fault-report
confirmation. Invalid or unavailable advice has rule-based fallback paths;
exceptions or rejected actions at the entry point produce a wait response.
The offline demo uses the program path only.

| Code | Responsibility |
| --- | --- |
| [agent.py](experiments/current/agent/agent.py) | Message loop and final fallback |
| [planner.py](experiments/current/agent/agent_core/planner.py) | Target, pointing, exposure, and program decisions |
| [state.py](experiments/current/agent/agent_core/state.py) | Public catalogue and observation history |
| [llm_client.py](experiments/current/agent/agent_core/llm_client.py) | Request budgets, retries, response parsing |
| [model_audit.py](experiments/current/agent/agent_core/model_audit.py) | Optional audit events and redaction |
| [validation.py](experiments/current/agent/agent_core/validation.py) | Action checks before protocol output |

## Results and limits

| Evidence | What it supports |
| --- | --- |
| Five-response synthetic replay, newly verified | The real message loop handles the demonstrated conditions without a model call |
| 57 tests, newly verified on Python 3.9.6 | Model boundaries, audit behaviour, offline mode, and reproducible regression fixtures |
| [Practice update](docs/releases/2026-10-04-practice-update.md), public commit `dee21c62` | A reviewable implementation change with 53 original boundary/audit tests |
| [Historical strategy report](docs/v4-strategy-study-report.md) | Version-specific offline comparisons, including negative results; not rerun in this edition |
| [Collaboration design](docs/v4-llm-collaboration.md) | A proposed division between numerical tools and model decisions, not measured model benefit |

The historical report records negative total scores even in completed holdout
runs; relative improvements did not establish reliable task completion. The
current demo makes no claim about competition rank, real telescope operation,
production readiness, or an LLM outperforming the program. Strategy-library and
probability-predictor work on later branches is not integrated into this edition.

The older documentation is a research archive. Some links refer to local-only
run evidence that was never published. Use the demo and test commands above for
the verified public reproduction path; the full historical simulator workflow
has not been revalidated here.

## Attribution and reuse

The **GOSIM 2026 Agentic Observer Challenge** organizers supplied the challenge
materials and example projects under **CC BY-NC 4.0**. Local work and upstream
material have different provenance; the repository is not licensed as a whole
under MIT. Preserve [NOTICE.md](NOTICE.md), upstream attribution, and the
[fixture provenance](experiments/current/tests/fixtures/pre-hardening/README.md)
when reusing or redistributing material.
