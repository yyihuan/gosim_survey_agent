# Case study: making an AI-assisted survey agent verifiable

This account uses published code, tests, and project decision records. It does
not reconstruct private conversations or infer an author's contribution from
the name on a Git commit. The reproducibility repairs at the end were performed
for this portfolio edition on 2026-11-11; they are not retroactive hackathon results.

## The problem and the division of work

A simulated telescope must make useful observations under competing constraints.
Numerical tools can calculate geometry and candidate exposure values. Model
advice introduces a separate engineering problem: a response may arrive late,
contain invalid values, or fail altogether while the agent still owes the
platform a legal action.

The [decision record](../agent-optimizer-decisions.md) documents the owner's
choices: prioritise competition results and reliability, use Codex to drive
local research tools first, and evaluate through simulated development,
public practice cards, then online testing. These are decisions recorded in
the project, not an inference that every proposed stage was completed.

The [outline](../agent-optimizer-outline.md) separates research tasks,
experiment execution, candidate export, and runtime action selection. Its
multi-agent roles and review stages are a design, not proof that all roles
were deployed. Published artifacts support the following concrete account:

| Responsibility | Evidence and scope |
| --- | --- |
| Human direction | Confirmed goals and evaluation stages in the decision record |
| AI-assisted research and engineering | Codex-based workflow described in the outline; code, tests, and research reports are inspectable artifacts |
| Programmatic verification | Fixed public inputs, fake transports, deterministic clocks, and regression comparisons in the tests |
| Runtime model advice | Implemented client and planner integration; optional and disabled in this demonstration |
| Independent review | Proposed in the published outline; this edition does not claim a completed named-model independent review |

## A concrete engineering change: budget and reply handling

Public commit `dee21c623e66073bb4523560e4207ed36d1dc9dd` changes the model client
and planner and adds audit support. Its parent, `fedf2fbc`, supplies a reviewable
before-state. The [release note](../releases/2026-10-04-practice-update.md) limits
the change to model boundaries; core target and geometric search stayed in place.

The useful evidence is behaviour under failure, not the volume of generated code:

| Failure to handle | Implemented behaviour | Executable evidence |
| --- | --- | --- |
| A retry reuses stale time remaining | Deduct elapsed time before another request | `test_retry_deducts_wallclock_elapsed`: timeouts become 10 seconds, then 2 |
| A successful response arrives after its allowance | Discard the late response | `test_late_success_is_not_consumed` |
| A model returns NaN, infinity, or an overflowing number | Reject non-finite values and retain fallback | `test_nonfinite_json_constants_and_overflow_rejected` |
| The first nightly question consumes time needed by the second | Pass fresh remaining time | `test_nightly_second_question_gets_fresh_remaining_seconds` |
| Logs expose request credentials | Redact known secrets in audit data | `test_secret_redaction_for_request_reply_parsed_and_url` |
| Offline changes accidentally alter decisions | Compare constructed trajectories with the frozen old modules | `test_constructed_offline_trajectory_matches_frozen_baseline` |

The first four and the trajectory test live in
[test_llm_boundaries.py](../../experiments/current/tests/test_llm_boundaries.py);
audit tests live in
[test_model_audit.py](../../experiments/current/tests/test_model_audit.py).
Their fake clocks and transports let the failure cases run without paid calls.
These tests establish the specified handling behaviour, not the quality of a
real model's recommendations or measured improvement in competition scores.

## Preserving negative research results

The [historical strategy report](../v4-strategy-study-report.md) retains cases
where improving a local objective did not improve the final task outcome.
Its frozen evaluations still had negative total scores. The portfolio keeps
that limitation visible instead of converting relative gains into a success
claim. Old revealed cards also cannot become a fresh blind test simply by
renaming the experiment.

The broader [program/model collaboration document](../v4-llm-collaboration.md)
is retained as a proposal. AI helping develop the software, a model being called
at runtime, and a model improving measured outcomes are three distinct claims.

## What the portfolio reproduction uncovered

On a clean checkout of `dee21c62`, the 28 boundary tests had one error: the
trajectory comparison loaded an untracked local baseline. The 25 audit tests
passed. Two of the four additional offline tests also relied on local artifacts:
one referenced an omitted upstream path, and another required an old run manifest.

The repairs preserve the test intent:

1. Vendor the two baseline modules from the already-public parent commit. Their
   bytes match the original local reference; hashes and provenance are recorded
   [with the fixture](../../experiments/current/tests/fixtures/pre-hardening/README.md).
2. Test the included fixed upstream snapshot using the active Python interpreter.
3. Create a temporary duplicate-run fixture, require the specific
   `FileExistsError`, verify its manifest remains unchanged, and prohibit process
   launch. An unrelated startup error can no longer make this test pass.

All **57 tests pass** after these repairs. The added five-response demo runs the
unchanged agent entry point with synthetic inputs and zero model calls.
[Verification](verification.md) records the commands and boundaries. This is a
small, concrete example of checking AI-assisted artifacts from a fresh reader's
environment instead of assuming that local success transfers to a public repo.

## Roles and attribution

The project owner confirmed on 2026-11-11 that all local development work was
their own. This was a solo project developed with AI assistance: the owner
directed the research and completed the local implementation, including research
tooling, adaptations, and the hardening change described here. The contribution
statement is based on that direct confirmation; the decision log, code, and tests
provide the technical evidence discussed above.

The organizers supplied the simulation, protocol, and example planner. Their
work remains separately attributed. Solo ownership of the local work does not
imply that every line was manually typed or that upstream code was authored by
the project owner. No new competition-result claim follows from this clarification.

This edition contains an AI-assisted documentation and reproducibility pass.
It has not undergone a separate independent-model review. Organizer materials
and derived example code retain their original attribution and applicable
CC BY-NC 4.0 terms; see [NOTICE](../../NOTICE.md).
