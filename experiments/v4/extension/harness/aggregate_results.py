#!/usr/bin/env python3
"""只读汇总ext-*，复用旧row规范化；输出仅在extension/results，不执行任何卡。"""
from collections import Counter
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
EXTENSION = HERE.parent
V4 = EXTENSION.parent
OUTPUT = EXTENSION / 'results'
sys.path.insert(0, str(V4 / 'harness'))
import aggregate_results as original

REFERENCE_RUNS = {
    'official-baseline': {'demo': 'r1-harness-demo', 'dev-season': 'r1-official-dev-season'},
    'D-linear': {'demo': 'r4-equivalence-d-demo', 'dev-season': 'r4-equivalence-d-dev-season'},
    'DTGP-frozen02': {'demo': 'r4-dtgp-frozen02-demo', 'dev-season': 'r4-dtgp-frozen02-dev-season'},
}


def stamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_optional(path):
    return json.loads(path.read_text()) if path.is_file() else {}


def enrich(row, raw, index, reference_case=None):
    manifest, config, metrics = (raw[key] or {} for key in ('manifest', 'config', 'metrics'))
    meta = index.get(row['run_id'], {})
    wrapper = manifest.get('extension_wrapper') or {}
    configured_case = config.get('case_id')
    family = row['family'] or 'unspecified'
    variant = row['variant']
    is_verification = row['stage'] in ('N1', 'integration-verification') or row['experiment_category'] == 'control'
    case = reference_case or meta.get('case_id') or configured_case
    if not case:
        case = 'D-linear' if is_verification else family + (':' + str(variant) if variant else '')
    row.update(case_id=case, reference_id=meta.get('reference_id', config.get('reference_id', 'D-linear')),
               analysis_group='N1-verification' if is_verification else row['stage_group'],
               verification_only=is_verification, reused_reference=reference_case is not None,
               declared_stage=row['stage'], simulator_limit=wrapper.get('simulator_limit', (row['concurrency'] or {}).get('simulator_limit')),
               extension_wrapper=wrapper or None,
               reference_run_id=None, reference_total=None, delta_vs_D=None,
               delta_vs_D_available=False, delta_reference_issue=None)
    if row['stage'] in ('N2', 'N3', 'N4', 'N5') and not is_verification:
        row['experiment_category'] = 'strategy' if not reference_case else 'control'
        row['category_evidence'] = '本轮明确N2–N5阶段；control按原manifest/config元数据单列'
        if row['stage'] == 'N5' and case in {'official-baseline', 'D-linear', 'DTGP-frozen02'}:
            row['experiment_category'] = 'control'
            row['category_evidence'] = 'Root冻结N5清单中的三个跨批次/同卡参照'
    row['runner_start_utc'] = manifest.get('runner_start_utc')
    row['runner_pid'] = manifest.get('runner_pid')
    if is_verification and row['experiment_category'] == 'unknown':
        row['experiment_category'] = 'integration-verification'
        row['category_evidence'] = '本轮N1包装动作/分数等价复验，仅验证，不作为独立策略样本'
    return row


def overlap(rows):
    events = []
    intervals = []
    for row in rows:
        if not row.get('runner_start_utc') or not row.get('end_utc'):
            continue
        start = datetime.datetime.fromisoformat(row['runner_start_utc']).timestamp()
        duration = row.get('runtime_seconds')
        if isinstance(duration, (int, float)):
            end = start + duration
        else:
            end = datetime.datetime.fromisoformat(row['end_utc']).timestamp()
        intervals.append({'run_id': row['run_id'], 'runner_pid': row['runner_pid'],
                          'runner_start_utc': row['runner_start_utc'], 'runtime_seconds': duration,
                          'end_is_approximate': True,
                          'reason': 'manifest runtime includes tiny Popen/start/close overhead; peers at lock acquisition are authoritative lock overlap',
                          'slots': (row['concurrency'] or {}).get('slots'),
                          'peers_at_acquisition': (row['concurrency'] or {}).get('peers_at_acquisition', [])})
        events.extend([(start, 1), (end, -1)])
    active = peak = 0
    for _time, increment in sorted(events):
        active += increment
        peak = max(peak, active)
    return {'configured_simulator_limit': 6, 'lock_namespace': str(HERE / '.locks'),
            'max_overlapping_runner_intervals': peak, 'interval_count': len(intervals),
            'intervals': intervals,
            'scope': 'Only extension ext-* real simulations; lease-only cap verification is recorded separately',
            'pace_change_runs': [r['run_id'] for r in rows if (r['pace_change_count'] or 0) > 0]}


def main():
    OUTPUT.mkdir(parents=True, exist_ok=True)
    # 永远不调用旧aggregate/main；那两个入口会扫描全部目录并可能重写旧84。
    with (OUTPUT / '.aggregate.lock').open('a+') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        protected_paths = [V4 / 'results/all_runs.json', V4 / 'results/all_runs.csv']
        protected_before = {str(p): sha(p) for p in protected_paths}
        index_record = read_optional(OUTPUT / 'run_index.json')
        index = index_record.get('runs', index_record)
        rows, records, references = [], {}, []
        for run in sorted((V4 / 'runs').glob('ext-*')):
            if not run.is_dir():
                continue
            row, raw = original.normalize_run(run, OUTPUT)
            rows.append(enrich(row, raw, index)); records[run.name] = raw
        # 只有N5真正启动后才补未启动项；草案本身不增加运行数或揭示任何成绩。
        n5_plan = read_optional(EXTENSION / 'evaluation/N5_PLAN.json')
        n5_execution = read_optional(EXTENSION / 'evaluation/N5_execution/status.json')
        if n5_plan.get('status') == 'frozen' and n5_execution.get('started_at_utc'):
            present = {row['run_id'] for row in rows}
            execution_by_run = {record['run_id']: record for record in n5_execution.get('results', [])}
            for planned in n5_plan['runs']:
                if planned['run_id'] in present:
                    continue
                run_dir = V4 / 'runs' / planned['run_id']
                row, raw = original.normalize_run(run_dir, OUTPUT)
                row = enrich(row, raw, index)
                result = execution_by_run.get(planned['run_id'], {})
                row.update(stage='N5', stage_group='N5', declared_stage='N5', analysis_group='N5',
                           experiment_category='strategy', category_evidence='Root frozen N5 manifest; no run started',
                           case_id=planned['case_id'], reference_id=planned['reference_id'],
                           card=planned['card_id'], card_source=planned['card'], card_tree_sha256=planned['card_tree_sha256'],
                           agent_source=planned['agent'], config_source=planned['config'],
                           source_tree_sha256=planned['source_tree_sha256'], config_sha256=planned['config_sha256'],
                           evaluation_state='not-run', run_status='not-run', run_status_inferred=False,
                           verification_only=False, termination_detail=result.get('error', 'Not started yet; frozen batch inventory'),
                           record_issues=['No run directory created; official score is unavailable'], simulator_limit=6)
                row['evidence_links']['N5_execution/status.json'] = os.path.relpath(EXTENSION / 'evaluation/N5_execution/status.json', OUTPUT)
                rows.append(row); records[planned['run_id']] = raw
            rows.sort(key=lambda row: row['run_id'])
        reference_records = {}
        for case, cards in REFERENCE_RUNS.items():
            for _card, run_id in cards.items():
                row, raw = original.normalize_run(V4 / 'runs' / run_id, OUTPUT)
                references.append(enrich(row, raw, index, case))
                reference_records[run_id] = raw
        d_by_card = {r['card_tree_sha256']: r for r in references if r['case_id'] == 'D-linear'}
        # N5开封后，显式case_id=D-linear的新卡控制才成为该卡参照；不借用旧holdout。
        for row in rows:
            if row['case_id'] == 'D-linear' and not row['verification_only'] and row['full_season_complete']:
                d_by_card.setdefault(row['card_tree_sha256'], row)
        for row in rows + references:
            reference = d_by_card.get(row['card_tree_sha256'])
            if reference:
                row.update(reference_run_id=reference['run_id'], reference_total=reference['total'])
                if row['score_available'] and reference['score_available']:
                    row.update(delta_vs_D=round(row['total'] - reference['total'], 6), delta_vs_D_available=True)
            else:
                row['delta_reference_issue'] = 'No completed D-linear reference with the identical card tree hash'
        components = sorted(set(original.EXPECTED_COMPONENTS) | {key for row in rows + references for key in row['components']})
        columns = list(original.FIELD_SPECS)
        insert = columns.index('components') + 1
        columns[insert:insert] = ['component_' + key for key in components]
        extension_fields = ['case_id', 'reference_id', 'analysis_group', 'verification_only', 'reused_reference',
                            'declared_stage', 'reference_run_id', 'reference_total', 'delta_vs_D',
                            'delta_vs_D_available', 'delta_reference_issue', 'simulator_limit',
                            'runner_start_utc', 'runner_pid', 'extension_wrapper']
        columns += extension_fields
        for row in rows + references:
            for key in components:
                row.setdefault('component_' + key, None)
        dataset = {'schema_version': 'v4-extension-all-runs-v1', 'base_row_schema': original.SCHEMA_VERSION,
                   'generated_at_utc': stamp(), 'aggregator_script': os.path.relpath(Path(__file__).resolve(), OUTPUT),
                   'aggregator_sha256': sha(Path(__file__).resolve()), 'original_normalizer_sha256': sha(V4 / 'harness/aggregate_results.py'),
                   'runs_root': str(V4 / 'runs'), 'run_filter': 'ext-* only', 'row_count': len(rows),
                   'inventory_counts': {'by_category': dict(Counter(r['experiment_category'] for r in rows)),
                                        'by_stage': dict(Counter(r['analysis_group'] for r in rows)),
                                        'by_evaluation_state': dict(Counter(r['evaluation_state'] for r in rows)),
                                        'rows_with_record_issues': sum(bool(r['record_issues']) for r in rows)},
                   'rows': rows, 'source_records': records, 'reference_rows': references,
                   'reference_source_records': reference_records,
                   'comparison_policy': 'same-card tree hash, fixed D-linear reference; every iteration/failure retained; reused references are not new runs',
                   'verification_run_ids': [r['run_id'] for r in rows if r['verification_only']],
                   'old_results_sha256': protected_before}
        schema = {'schema_version': dataset['schema_version'], 'base_row_schema': original.SCHEMA_VERSION,
                  'json_file': 'all_runs.json', 'csv_file': 'all_runs.csv', 'reference_csv_file': 'reference_runs.csv',
                  'null_policy': 'JSON null / CSV empty mean missing; 0 remains an actual number; failed rows never filled with 0',
                  'scope': 'ext-* only; old references are read-only in separate reference_rows',
                  'rerun_command': '/usr/bin/python3 -B experiments/v4/extension/harness/aggregate_results.py',
                  'run_index': 'Optional results/run_index.json {runs:{run_id:{case_id,reference_id}}}; explicit metadata overrides config family:variant',
                  'columns': [{'name': key, 'type': original.FIELD_SPECS[key][0], 'description': original.FIELD_SPECS[key][1]}
                              if key in original.FIELD_SPECS else {'name': key, 'type': 'extension or component', 'description': key}
                              for key in columns]}
        original.write_outputs(dataset, schema, columns, OUTPUT)
        # 参照表供HTML直接读取，不混入本轮统计次数。
        import csv, io
        stream = io.StringIO(newline=''); writer = csv.DictWriter(stream, fieldnames=columns, lineterminator='\n')
        writer.writeheader()
        for row in references:
            writer.writerow({key: original.compact(row.get(key)) if isinstance(row.get(key), (dict, list, bool)) else row.get(key) for key in columns})
        original.atomic_write(OUTPUT / 'reference_runs.csv', stream.getvalue())
        original.atomic_write(OUTPUT / 'concurrency.json', json.dumps(overlap(rows), ensure_ascii=False, indent=2) + '\n')
        assert protected_before == {str(p): sha(p) for p in protected_paths}, '旧84汇总出现变化'
    print(original.compact({'row_count': len(rows), 'verification_count': len(dataset['verification_run_ids']),
                            'references': len(references), 'output_root': str(OUTPUT), 'inventory_counts': dataset['inventory_counts']}))


if __name__ == '__main__':
    main()
