# Verification record — portfolio edition

Verified on **2026-11-11**, macOS, Python **3.9.6**. The branch starts from
`dee21c623e66073bb4523560e4207ed36d1dc9dd`, the locally recorded published
baseline. The remote Git HEAD could not be confirmed: GitHub DNS failed in the
sandbox, and the read-only escalation's automatic approval review timed out.
The browser-accessible repository page showed three commits and the same
practice-update overview, but that cached page is not proof of the current HEAD.

## Reproduce

From the repository root, use Python >=3.9:

```bash
python3 -I -B scripts/demo_offline.py
python3 -I -B -m unittest discover -s experiments/current/tests
```

| Check | Observed result | Evidence |
| --- | --- | --- |
| Full current test directory | 57 tests, OK | [test log](evidence/unit-tests.log) |
| Clean Git export without `.git` or untracked artifacts | Demo and all 57 tests pass | [export checks](evidence/clean-export.json) |
| Synthetic protocol replay | Five expected responses; zero model calls and connection attempts | [report](evidence/demo/report.json), [responses](evidence/demo/responses.jsonl), [agent log](evidence/demo/agent.stderr.log) |
| Inherited configuration isolation | Dummy key, model-enabled setting, endpoint override and trace path did not affect the offline run; no trace file created | [checks](evidence/checks.json) |
| Existing output directory | Rejected with exit 2 | [checks](evidence/checks.json) |
| Diagram source freshness | Paired SVG rendered and README reference checked using document-diagrams | [source](../diagrams/portfolio-agent-flow.mmd), [SVG](../diagrams/portfolio-agent-flow.svg) |

The default shell's `python3` was Python 3.7 and could not run the production
agent. Verification therefore used the installed Python 3.9.6 interpreter. The
demo now exits with a direct minimum-version message on older interpreters.
Other operating systems and supported Python versions have not been tested here.

The 57 tests include the original 28 model-boundary tests, 25 audit tests, and
four offline tests. The demo is separate, not counted as five additional unit
tests. The unchanged agent source can be checked with:

```bash
git diff dee21c62 -- experiments/current/agent
```

## Reproducibility repairs

The initial clean checkout did not reproduce the historical all-pass statement:
one boundary test lacked its local-only frozen reference, and two offline tests
depended on omitted local paths or run artifacts. This edition:

- includes two exact public-parent source files as a frozen test fixture;
- points the upstream key-requirement test at the included official snapshot;
- creates the duplicate-run fixture in a temporary directory and checks the
  specific refusal before process launch.

The [fixture record](../../experiments/current/tests/fixtures/pre-hardening/README.md)
lists hashes and provenance. Existing historical release notes have not been
rewritten to conceal the reproduction failures.

## Publication scope and screening

The source working directory had many uncommitted artifacts and a local main
89 commits ahead of its recorded public remote. This edition was prepared in an
isolated checkout of the published baseline. Those later commits and uncommitted
artifacts are not ancestors or contents of the portfolio change.

A pattern-based pass inspected all **1,029 unique blobs across three commits**
reachable from that selected baseline. No private-key headers or selected
GitHub, OpenAI-style or AWS access-key patterns matched. **313 blobs contained
machine-local paths.** These are pre-existing publication issues, not a claim
that every path is secret. No history rewrite was performed. Pattern screening
cannot establish the absence of every credential or private detail.

The new portfolio material uses relative file links and synthetic inputs. It
does not include private conversations, real credentials, later experiment logs,
or hidden task-card truth. Third-party attribution and NOTICE remain in place;
test copies retain the original provenance. This work does not assign a blanket
MIT license. The owner confirmed on 2026-11-11 that all local development was
their own; the [contribution statement](ai-collaboration.md#roles-and-attribution)
now identifies this as a solo project developed with AI assistance. That
clarification does not change upstream attribution or licensing.

## What remains unverified

- The exact current remote HEAD and integration with later local branches.
- Full simulator performance, competition ranking, real-model benefit, and
  deployment on the competition platform.
- Historical run artifacts omitted from the public repository.
- A complete public-history privacy audit and an independent-model review.

No real model call, platform operation, push, or remote tag was made in this
portfolio pass. The demo and tests are locally usable without those actions.
