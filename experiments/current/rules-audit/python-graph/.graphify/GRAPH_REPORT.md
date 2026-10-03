# Graph Report - survey-ast-3vwnl94o  (2026-10-03)

## Corpus Check
- Corpus is ~8,054 words - fits in a single context window. You may not need a graph.

## Summary
- 133 nodes · 205 edges · 10 communities detected
- Extraction: 80% EXTRACTED · 20% INFERRED · 0% AMBIGUOUS · INFERRED: 40 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output
- Edge kinds: method: 43 · contains: 40 · uses: 40 · calls: 37 · rationale_for: 36 · imports_from: 5 · inherits: 4


## Input Scope
- Requested: all
- Resolved: all (source: cli)
- Included files: 11 · Candidates: recursive
- Excluded: 0 untracked · 0 ignored · 0 sensitive · 0 missing committed
## God Nodes (most connected - your core abstractions)
1. `SurveyState` - 18 edges
2. `Planner` - 17 edges
3. `ScoringModel` - 13 edges
4. `LLMClient` - 12 edges
5. `FiberGrid` - 11 edges
6. `TraceLog` - 11 edges
7. `PendingPrediction` - 11 edges
8. `Moon` - 10 edges
9. `Decision logic: pick a pointing, fill the 16 fibres, choose exposure length and` - 5 edges
10. `A human-readable rendering of a bulletin's notices, for the LLM call that reads` - 5 edges

## Surprising Connections (you probably didn't know these)
- `Planner` --uses--> `Moon`  [INFERRED]
  ../../../../../../private/var/folders/kb/zcxf01xs5p7gmw1kss26fp0h0000gn/T/survey-ast-3vwnl94o/agent_core/planner.py → ../../../../../../private/var/folders/kb/zcxf01xs5p7gmw1kss26fp0h0000gn/T/survey-ast-3vwnl94o/agent_core/geometry.py
- `Planner` --uses--> `LLMClient`  [INFERRED]
  ../../../../../../private/var/folders/kb/zcxf01xs5p7gmw1kss26fp0h0000gn/T/survey-ast-3vwnl94o/agent_core/planner.py → ../../../../../../private/var/folders/kb/zcxf01xs5p7gmw1kss26fp0h0000gn/T/survey-ast-3vwnl94o/agent_core/llm_client.py
- `Planner` --uses--> `TraceLog`  [INFERRED]
  ../../../../../../private/var/folders/kb/zcxf01xs5p7gmw1kss26fp0h0000gn/T/survey-ast-3vwnl94o/agent_core/planner.py → ../../../../../../private/var/folders/kb/zcxf01xs5p7gmw1kss26fp0h0000gn/T/survey-ast-3vwnl94o/agent_core/memory.py
- `Planner` --uses--> `PendingPrediction`  [INFERRED]
  ../../../../../../private/var/folders/kb/zcxf01xs5p7gmw1kss26fp0h0000gn/T/survey-ast-3vwnl94o/agent_core/planner.py → ../../../../../../private/var/folders/kb/zcxf01xs5p7gmw1kss26fp0h0000gn/T/survey-ast-3vwnl94o/agent_core/state.py
- `FaultEvidence` --uses--> `ScoringModel`  [INFERRED]
  ../../../../../../private/var/folders/kb/zcxf01xs5p7gmw1kss26fp0h0000gn/T/survey-ast-3vwnl94o/agent_core/state.py → ../../../../../../private/var/folders/kb/zcxf01xs5p7gmw1kss26fp0h0000gn/T/survey-ast-3vwnl94o/agent_core/scoring.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.10
Nodes (10): FiberGrid, n x n square fibres; fibre 0 bottom-left, rows along +altitude, columns along +a, -> (fiber id, margin in degrees to the glass edge), or (None, negative margin), FaultEvidence, _mod(), Survey state: the target catalogue, learned sky-quality scale, and per-target pr, Indices within `radius` degrees of (ra, dec), using the 1-degree declination-ban, First/last night index on which each target has >=20 minutes above the limit. (+2 more)

### Community 1 - "Community 1"
Cohesion: 0.11
Nodes (21): altaz_to_radec(), _julian_date(), local_sidereal_deg(), lunar_factor(), max_hour_angle_deg(), moon_radec(), normalized_airmass(), radec_to_altaz() (+13 more)

### Community 2 - "Community 2"
Cohesion: 0.16
Nodes (14): Moon, Moon position/illumination at one instant, for a given local sidereal time (the, LLMClient, One HTTP attempt. Raises on any problem; the caller retries or gives up., One planning question, answered as exactly one JSON object. Retries up to, An optional, best-effort decision trace log.  Night-to-night and run-wide memory, TraceLog, Decision logic: pick a pointing, fill the 16 fibres, choose exposure length and (+6 more)

### Community 3 - "Community 3"
Cohesion: 0.21
Nodes (3): _az_distance(), _bulletin_text(), Planner

### Community 4 - "Community 4"
Cohesion: 0.20
Nodes (4): Scoring estimates built only from the PUBLIC parts of initialize.payload.scoring, Reads the public scoring config once and offers factor/score/band estimates., A per-second "quality model" for a target: lunar factor / (q0 * airmass^beta)., ScoringModel

### Community 5 - "Community 5"
Cohesion: 0.31
Nodes (9): ActionRejected, fallback_action(), Validate a decision_response before it goes to stdout, and provide a determinist, Always-valid, always-safe action: wait one slot. Works even before the     agent, Return a sanitized copy of `action` containing only protocol-legal fields,     o, validate_action(), _validate_observe(), _validate_wait() (+1 more)

### Community 6 - "Community 6"
Cohesion: 0.32
Nodes (7): log(), Transport layer for participant-agent-protocol-v4: one JSON object per line.  Re, Write one diagnostic line to stderr. Never raises., Yield parsed JSON objects from an iterable of lines, skipping blanks.      A lin, Write one decision_response line for `decision_sequence`, keeping only     the f, read_messages(), send_response()

### Community 7 - "Community 7"
Cohesion: 0.29
Nodes (5): MissingAPIKeyError, A tiny OpenAI-compatible chat client, configured through environment variables., Raise MissingAPIKeyError if neither OPENAI_API_KEY nor KIMI_API_KEY is set., require_api_key(), RuntimeError

### Community 8 - "Community 8"
Cohesion: 1.00
Nodes (2): collect(), main()

### Community 9 - "Community 9"
Cohesion: 1.00
Nodes (1): Modules for the python-agent example: protocol I/O, state tracking, sky geometry

## Knowledge Gaps
- **27 isolated node(s):** `Modules for the python-agent example: protocol I/O, state tracking, sky geometry`, `Sky geometry for the survey: the public formulas from the participant guide (pro`, `Equatorial -> horizontal coordinates for a given local sidereal time.`, `Horizontal -> equatorial coordinates (the inverse of radec_to_altaz).`, `Largest |hour angle| (deg) at which a source stays at or above min_alt (0 = neve` (+22 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 8`** (2 nodes): `collect()`, `main()`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 9`** (1 nodes): `Modules for the python-agent example: protocol I/O, state tracking, sky geometry`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `FiberGrid` connect `Community 0` to `Community 1`, `Community 2`?**
  _High betweenness centrality (0.255) - this node is a cross-community bridge._
- **Why does `SurveyState` connect `Community 0` to `Community 4`?**
  _High betweenness centrality (0.215) - this node is a cross-community bridge._
- **Why does `PendingPrediction` connect `Community 2` to `Community 3`, `Community 0`, `Community 4`?**
  _High betweenness centrality (0.211) - this node is a cross-community bridge._
- **Are the 2 inferred relationships involving `SurveyState` (e.g. with `FiberGrid` and `ScoringModel`) actually correct?**
  _`SurveyState` has 2 INFERRED edges - model-reasoned connections that need verification._
- **Are the 4 inferred relationships involving `Planner` (e.g. with `Moon` and `LLMClient`) actually correct?**
  _`Planner` has 4 INFERRED edges - model-reasoned connections that need verification._
- **Are the 6 inferred relationships involving `ScoringModel` (e.g. with `FaultEvidence` and `PendingPrediction`) actually correct?**
  _`ScoringModel` has 6 INFERRED edges - model-reasoned connections that need verification._
- **Are the 7 inferred relationships involving `LLMClient` (e.g. with `Planner` and `Decision logic: pick a pointing, fill the 16 fibres, choose exposure length and`) actually correct?**
  _`LLMClient` has 7 INFERRED edges - model-reasoned connections that need verification._