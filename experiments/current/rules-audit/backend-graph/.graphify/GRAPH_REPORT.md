# Graph Report - survey-ast-m_hufpjh  (2026-10-03)

## Corpus Check
- Corpus is ~25,105 words - fits in a single context window. You may not need a graph.

## Summary
- 379 nodes · 819 edges · 20 communities detected
- Extraction: 79% EXTRACTED · 21% INFERRED · 0% AMBIGUOUS · INFERRED: 176 edges (avg confidence: 0.5)
- Token cost: 0 input · 0 output
- Edge kinds: calls: 277 · contains: 178 · uses: 176 · method: 105 · rationale_for: 74 · inherits: 5 · imports_from: 4


## Input Scope
- Requested: all
- Resolved: all (source: cli)
- Included files: 18 · Candidates: recursive
- Excluded: 0 untracked · 0 ignored · 0 sensitive · 0 missing committed
## God Nodes (most connected - your core abstractions)
1. `ChallengeScorer` - 36 edges
2. `FiberGrid` - 26 edges
3. `Slot` - 25 edges
4. `TileGeometrySimulator` - 23 edges
5. `WeatherSimulator` - 21 edges
6. `Decision` - 19 edges
7. `WeatherTruth` - 19 edges
8. `Night` - 18 edges
9. `ObservationRequestSimulator` - 17 edges
10. `AgentTermination` - 17 edges

## Surprising Connections (you probably didn't know these)
- `Participant-safe request publication; the pre-generated future stays hidden.` --uses--> `Night`  [INFERRED]
  ../../../../../../private/var/folders/kb/zcxf01xs5p7gmw1kss26fp0h0000gn/T/survey-ast-m_hufpjh/challenge/observation_request_simulator.py → ../../../../../../private/var/folders/kb/zcxf01xs5p7gmw1kss26fp0h0000gn/T/survey-ast-m_hufpjh/challenge/observing_calendar.py
- `Bounded JSON-Lines transport. Isolation is supplied by the Docker launcher.` --uses--> `GlobalDeadlineExpired`  [INFERRED]
  ../../../../../../private/var/folders/kb/zcxf01xs5p7gmw1kss26fp0h0000gn/T/survey-ast-m_hufpjh/project_platform/transport.py → ../../../../../../private/var/folders/kb/zcxf01xs5p7gmw1kss26fp0h0000gn/T/survey-ast-m_hufpjh/challenge/challenge_workflow.py
- `End a normally finished run gracefully: one final "finish" line,         then st` --uses--> `GlobalDeadlineExpired`  [INFERRED]
  ../../../../../../private/var/folders/kb/zcxf01xs5p7gmw1kss26fp0h0000gn/T/survey-ast-m_hufpjh/project_platform/transport.py → ../../../../../../private/var/folders/kb/zcxf01xs5p7gmw1kss26fp0h0000gn/T/survey-ast-m_hufpjh/challenge/challenge_workflow.py
- `Run a persistent command and exchange only public protocol messages.      This c` --uses--> `GlobalDeadlineExpired`  [INFERRED]
  ../../../../../../private/var/folders/kb/zcxf01xs5p7gmw1kss26fp0h0000gn/T/survey-ast-m_hufpjh/project_platform/transport.py → ../../../../../../private/var/folders/kb/zcxf01xs5p7gmw1kss26fp0h0000gn/T/survey-ast-m_hufpjh/challenge/challenge_workflow.py
- `ChallengeWorkflow` --uses--> `ChallengeScorer`  [INFERRED]
  ../../../../../../private/var/folders/kb/zcxf01xs5p7gmw1kss26fp0h0000gn/T/survey-ast-m_hufpjh/challenge/challenge_workflow.py → ../../../../../../private/var/folders/kb/zcxf01xs5p7gmw1kss26fp0h0000gn/T/survey-ast-m_hufpjh/challenge/scoring_core.py

## Communities

### Community 0 - "Community 0"
Cohesion: 0.12
Nodes (23): _azimuth_inside(), _clip(), _default_runtime(), Forecast, generate(), generate_events(), generate_forecasts(), generate_weather() (+15 more)

### Community 1 - "Community 1"
Cohesion: 0.13
Nodes (17): ChallengeWorkflow, GlobalDeadlineExpired, load_workflow_config(), _public_weather(), Global-wallclock workflow joining all example3 simulator interfaces., Add current visit progress to time-safe request publications., Night-start publication: acknowledged unrepaired fault, or a one-shot 'instrumen, Validate one response; malformed report entries are dropped (counted), never the (+9 more)

### Community 2 - "Community 2"
Cohesion: 0.11
Nodes (22): altaz_to_radec(), altitude_ok(), Classification, load_config(), main(), min_altitude_during(), _parse_utc(), radec_to_altaz() (+14 more)

### Community 3 - "Community 3"
Cohesion: 0.19
Nodes (7): ChallengeScorer, _coverage_evenness(), load_decisions(), load_score_config(), load_tile_anomalies(), load_tile_values(), score_files()

### Community 4 - "Community 4"
Cohesion: 0.22
Nodes (18): ObservationRequest, Night, Slot, Authoritative replay engine for example3 decisions., How evenly the finished tiles are spread over the survey regions, as Jain's fair, Hidden per-tile truth multiplier; the published tile_science_value stays untagge, Best-program score a repeat observation started at the cursor would earn under t, Book one participant report at cursor time as_of; never touches the cursor. (+10 more)

### Community 5 - "Community 5"
Cohesion: 0.15
Nodes (13): ExecutionError, JsonlTransport, Bounded JSON-Lines transport. Isolation is supplied by the Docker launcher., End a normally finished run gracefully: one final "finish" line,         then st, Run a persistent command and exchange only public protocol messages.      This c, agent_environment(), load_card(), load_dotenv() (+5 more)

### Community 6 - "Community 6"
Cohesion: 0.19
Nodes (17): _angular_separation_deg(), _assign_required(), build_catalog(), completable_nights(), _default_simulator(), generate_catalog(), geometry_sample(), geometry_sample_without_lunar() (+9 more)

### Community 7 - "Community 7"
Cohesion: 0.11
Nodes (16): azimuth_inside(), _lunar_geometry(), lunar_quality_factor(), observation_request_status(), One target's capped contribution for one exposure.      `segments` are the expos, Compute one request's current completion and reward from the valid ledger., Jain-index penalty over RA bands: r_k = observed fraction (factor >= 0.5) per ba, Instrument-fault reporting settlement (+reward / false-report penalty, v3-style) (+8 more)

### Community 8 - "Community 8"
Cohesion: 0.23
Nodes (18): build_calendar(), _ceil_epoch(), _crossing(), _equatorial_altitude_deg(), _floor_epoch(), generate(), _julian_date(), load_config() (+10 more)

### Community 9 - "Community 9"
Cohesion: 0.27
Nodes (16): _data_loss_plan(), _format_utc(), _load_agent(), load_scenario(), main(), _parse_utc(), _pointing_offset(), _read_csv() (+8 more)

### Community 10 - "Community 10"
Cohesion: 0.15
Nodes (8): Slot-aligned site weather with independent repair state for each fault event., Compatibility view for the single-fault case., Yield (seconds, SlotTruth) overlap pieces of [start, end) against the slots., Start a new false-report allowance after a correct report., Repair a correct report; penalize false reports after the free threshold., Effective instrument efficiency for a slot, undoing a repaired fault., Program-band quality with time-resolved target lunar factor and airmass., WeatherTruth

### Community 11 - "Community 11"
Cohesion: 0.14
Nodes (7): Run the card; returns the workflow result (also written to workflow_result.json), _read_csv(), replay(), result_summary(), _utc(), V4Workflow, validate_bundle()

### Community 12 - "Community 12"
Cohesion: 0.13
Nodes (11): anomaly_mechanics_enabled(), derive_stream_seed(), parse_utc(), Versioned file contracts and shared serialization helpers for example3., Parse the contract UTC timestamp form and require an aware value., Write UTF-8 text with LF line endings on every platform, so generated files hash, 128-bit seed for one named RNG stream, from sha256("<seed>:<stream>")., Seed of one simulator RNG stream: ``seed + legacy_offset`` unless hashed derivat (+3 more)

### Community 13 - "Community 13"
Cohesion: 0.20
Nodes (12): FiberGrid, Square fiber-grid field on a gnomonic plane centered at the actual pointing., (increasing-alt, increasing-az) tangent-plane offsets, in degrees., Grid-cell lookup in tangent-plane offsets; seams belong to one cell., AgentTermination, ProtocolViolation, Organizer verification: re-run a recorded ``actions.jsonl`` against the bundle., Small database summary for a v4 run (``observer_finish_run`` reads score.total). (+4 more)

### Community 14 - "Community 14"
Cohesion: 0.28
Nodes (12): DataLossPlan, _integer(), InvalidAgentAction, normalize_action(), _number(), The agent's action violates the action contract. The run ends as agent_error and, Validate one agent action and return its normalized form; raises InvalidAgentAct, Raised by an agent callable (e.g. the platform transport adapter) to stop the ru (+4 more)

### Community 15 - "Community 15"
Cohesion: 0.32
Nodes (12): _chronological(), cross_validate_generator_configs(), _finite(), Consistency checks on a loaded ``v4_runner.Scenario``; raises ValueError., Raise ValueError unless the generator configs of one card agree with each other., _same_site(), _site_tuple(), validate_fiber_config() (+4 more)

### Community 16 - "Community 16"
Cohesion: 0.17
Nodes (6): BestLedger, LedgerEntry, Raw per-target contributions with replayable best-score settlement., target_id -> (factor, score) of its best valid contribution (max score)., Largest valid exposure factor for each target, independent of score bonuses., Largest valid factors from exposures wholly contained in one request window.

### Community 17 - "Community 17"
Cohesion: 0.31
Nodes (7): generate(), generate_schedule(), load_config(), load_request_tiles(), load_requests(), main(), _weighted_choice()

### Community 18 - "Community 18"
Cohesion: 1.00
Nodes (1): Filesystem defaults for the vendored challenge environment (example3 contract).

### Community 19 - "Community 19"
Cohesion: 1.00
Nodes (1): Additive project submission and execution platform.  Legacy submissions and thei

## Knowledge Gaps
- **41 isolated node(s):** `Versioned file contracts and shared serialization helpers for example3.`, `128-bit seed for one named RNG stream, from sha256("<seed>:<stream>").`, `Seed of one simulator RNG stream: ``seed + legacy_offset`` unless hashed derivat`, `The single switch: a scenario opts into the anomaly mechanics through its score`, `Parse the contract UTC timestamp form and require an aware value.` (+36 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **Thin community `Community 18`** (1 nodes): `Filesystem defaults for the vendored challenge environment (example3 contract).`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.
- **Thin community `Community 19`** (1 nodes): `Additive project submission and execution platform.  Legacy submissions and thei`
  Too small to be a meaningful cluster - may be noise or needs more connections extracted.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `GlobalDeadlineExpired` connect `Community 1` to `Community 3`, `Community 5`?**
  _High betweenness centrality (0.448) - this node is a cross-community bridge._
- **Why does `V4Workflow` connect `Community 11` to `Community 13`, `Community 5`?**
  _High betweenness centrality (0.444) - this node is a cross-community bridge._
- **Why does `Public card metadata (task_card) from config/v4_scenario.json -- same shape the` connect `Community 5` to `Community 11`?**
  _High betweenness centrality (0.427) - this node is a cross-community bridge._
- **Are the 16 inferred relationships involving `ChallengeScorer` (e.g. with `ChallengeWorkflow` and `GlobalDeadlineExpired`) actually correct?**
  _`ChallengeScorer` has 16 INFERRED edges - model-reasoned connections that need verification._
- **Are the 14 inferred relationships involving `FiberGrid` (e.g. with `AgentTermination` and `DataLossPlan`) actually correct?**
  _`FiberGrid` has 14 INFERRED edges - model-reasoned connections that need verification._
- **Are the 20 inferred relationships involving `Slot` (e.g. with `ChallengeScorer` and `Decision`) actually correct?**
  _`Slot` has 20 INFERRED edges - model-reasoned connections that need verification._
- **Are the 18 inferred relationships involving `TileGeometrySimulator` (e.g. with `ChallengeScorer` and `Decision`) actually correct?**
  _`TileGeometrySimulator` has 18 INFERRED edges - model-reasoned connections that need verification._