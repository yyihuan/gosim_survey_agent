#!/usr/bin/env python3
"""逐项导出冻结N5比分和同卡D/旧DTGP分差；不做策略选择或整体分析。"""
import csv
import datetime
import hashlib
import io
import json
from pathlib import Path
import sys

HERE = Path(__file__).resolve().parent
EXTENSION = HERE.parent
V4 = EXTENSION.parent
OUTPUT = EXTENSION / 'results'
sys.path.insert(0, str(V4 / 'harness'))
from aggregate_results import atomic_write, compact


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    plan_path = EXTENSION / 'evaluation/N5_PLAN.json'
    plan = json.loads(plan_path.read_text())
    dataset = json.loads((OUTPUT / 'all_runs.json').read_text())
    source_rows = {row['run_id']: row for row in dataset['rows']}
    case_card = {(row['case_id'], row['card_tree_sha256']): row for row in dataset['rows'] if row['stage'] == 'N5'}
    rows = []
    for planned in plan['runs']:
        row = source_rows[planned['run_id']]
        d = case_card.get(('D-linear', row['card_tree_sha256']))
        dtgp = case_card.get(('DTGP-frozen02', row['card_tree_sha256']))
        comparable_d = row['score_available'] and d and d['score_available']
        comparable_dtgp = row['score_available'] and dtgp and dtgp['score_available']
        result = {key: row.get(key) for key in [
            'run_id', 'stage', 'case_id', 'reference_id', 'variant', 'card', 'card_source', 'card_tree_sha256',
            'card_nights', 'card_targets', 'total', 'score_available', 'components',
            'required_missing', 'coverage_jain', 'targets_observed', 'observe_actions', 'observation_rows',
            'request_issued', 'request_completed', 'report_count', 'report_correct', 'report_false',
            'runtime_seconds', 'runtime_with_setup_seconds', 'accounted_wallclock_seconds', 'agent_wallclock_seconds',
            'global_wallclock_seconds', 'pace_change_count', 'pace_changes', 'pace_minimum_remaining_seconds',
            'run_status', 'evaluation_state', 'full_season_complete', 'termination_reason', 'official_termination_reason',
            'termination_detail', 'exit_code', 'start_utc', 'end_utc', 'source_tree_sha256', 'config_sha256',
            'harness_tree_sha256', 'snapshot_tree_sha256', 'normalized_actions_sha256', 'normalized_score_sha256',
            'concurrency', 'record_issues', 'input_sha256', 'evidence_links']}
        result.update(science=row['components'].get('sum_best_scores'),
                      delta_vs_D=round(row['total'] - d['total'], 6) if comparable_d else None,
                      D_run_id=d['run_id'] if d else None, D_total=d['total'] if d else None,
                      delta_vs_DTGP=round(row['total'] - dtgp['total'], 6) if comparable_dtgp else None,
                      DTGP_run_id=dtgp['run_id'] if dtgp else None, DTGP_total=dtgp['total'] if dtgp else None,
                      relative_run_path='../../runs/' + row['run_id'],
                      frozen_source_matches=row['source_tree_sha256'] == planned['source_tree_sha256'],
                      frozen_config_matches=row['config_sha256'] == planned['config_sha256'],
                      frozen_card_matches=row['card_tree_sha256'] == planned['card_tree_sha256'])
        rows.append(result)
    assert len(rows) == 52 and len({r['run_id'] for r in rows}) == 52
    by_case = {case['case_id']: [r for r in rows if r['case_id'] == case['case_id']] for case in plan['cases']}
    by_card = {card['card_id']: [r for r in rows if r['card'] == card['card_id']] for card in plan['cards']}
    out = {'schema_version': 'v4-extension-N5-results-v1', 'generated_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
           'upstream_commit': plan['upstream_commit'], 'plan_sha256': sha(plan_path),
           'all_runs_sha256': sha(OUTPUT / 'all_runs.json'), 'source_script_sha256': sha(Path(__file__).resolve()),
           'row_count': 52, 'case_count': 13, 'card_count': 4,
           'comparison_boundary': 'Generated local research holdouts only, same-card tree hash. DTGP is the old frozen strategy rerun on these same new cards; no official alpha-delta scores or online submission.',
           'missing_policy': 'Unavailable score/delta stays null; failed and not-run records retained.',
           'inventory': {'complete_full_season': sum(r['full_season_complete'] for r in rows),
                         'scores_available': sum(r['score_available'] for r in rows),
                         'pace_change_runs': [r['run_id'] for r in rows if (r['pace_change_count'] or 0) > 0],
                         'record_issue_runs': [r['run_id'] for r in rows if r['record_issues']],
                         'snapshot_hash_mismatch_runs': [r['run_id'] for r in rows if not all(r[k] for k in ['frozen_source_matches', 'frozen_config_matches', 'frozen_card_matches'])]},
           'rows': rows, 'by_case': by_case, 'by_card': by_card}
    atomic_write(OUTPUT / 'n5_results.json', json.dumps(out, ensure_ascii=False, indent=2) + '\n')
    columns = list(rows[0])
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator='\n'); writer.writeheader()
    for row in rows:
        writer.writerow({k: compact(row[k]) if isinstance(row[k], (dict, list, bool)) else row[k] for k in columns})
    atomic_write(OUTPUT / 'n5_results.csv', stream.getvalue())
    print(compact({'row_count': 52, 'inventory': out['inventory'], 'outputs': ['n5_results.json', 'n5_results.csv']}))


if __name__ == '__main__':
    main()
