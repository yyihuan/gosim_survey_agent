#!/usr/bin/env python3
# coding: utf-8
"""只读整理已授权 N4 四组合的官方输出与机制日志，不运行/重评分。"""
from pathlib import Path
from collections import Counter, defaultdict
import csv
import hashlib
import json
import statistics

V4 = Path(__file__).resolve().parents[3]
OWN = V4 / 'extension/agents/combined'


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def required_retries(run, actions):
    required = {r['target_id'] for r in csv.DictReader((run / 'card_snapshot/public/targets.csv').open())
                if r['required'] == 'true'}
    hits = defaultdict(dict)
    for h in csv.DictReader((run / 'output/observations.csv').open()):
        if h['valid'] == 'true':
            hits[int(h['observe_index'])][h['target_id']] = float(h['factor'])
    attempts, best, retry_targets = Counter(), defaultdict(float), set()
    retries = failures = 0
    for index, action in enumerate(a for a in actions if a['action'] == 'observe'):
        for target in action['assignments'].values():
            if target in required:
                if attempts[target] and best[target] < .5:
                    retries += 1
                    retry_targets.add(target)
                failures += hits[index].get(target, 0) < .5
                attempts[target] += 1
        for target, factor in hits[index].items():
            best[target] = max(best[target], factor)
    return {'official_required_retry_assignments': retries,
            'official_required_retry_targets': len(retry_targets),
            'official_required_below_threshold_or_missed_attempts': failures}


def main():
    rows = []
    for case in ('fe', 'fm', 'fq', 'fmq'):
        for card in ('demo', 'dev-season'):
            run = V4 / 'runs' / f'ext-n4-{case}-{card}'
            metrics = json.loads((run / 'metrics.json').read_text())
            manifest = json.loads((run / 'manifest.json').read_text())
            text = (run / 'output/agent.log').read_text()
            mfj = [json.loads(line[5:]) for line in text.splitlines() if line.startswith('mfj: ')]
            heq = [json.loads(line[5:]) for line in text.splitlines() if line.startswith('heq: ')]
            counters = Counter()
            for record in heq:
                counters.update(record['stats'])
            observes = [record for record in mfj if record['action'] == 'observe']
            fields = {key: sum(record.get(key, 0) for record in mfj) for key in
                      ('f_generated_fields', 'f_retained_fields', 'f_evaluated_fields',
                       'f_changed_from_potential_best', 'm_evaluations',
                       'm_proxy_positive_actual_zero', 'm_matched_evaluations',
                       'm_mismatch_evaluations', 'm_selected_banked_targets',
                       'm_selected_predicted_science_gain')}
            fields['f_selected_potential_rank_distribution'] = dict(Counter(
                str(record.get('f_selected_potential_rank')) for record in observes))
            fields['m_feedback_updates'] = max((p.get('m_feedback_updates', 0) for p in mfj), default=0)
            fields['m_resync_count'] = max((p.get('m_resync_count', 0) for p in mfj), default=0)
            margins = [p['q_margin'] for p in heq if p['action'] == 'observe']
            actions = [json.loads(line) for line in (run / 'output/actions.jsonl').read_text().splitlines()]
            mechanism = {'mfj_logged_plans': len(mfj), 'heq_logged_plans': len(heq),
                         'mfj': fields, 'heq_counters': dict(counters),
                         'e_selected_new_duration_count': sum(p['action'] == 'observe' and
                                                               p['e_selected_new_duration'] for p in heq),
                         'q_margin_min': min(margins) if margins else None,
                         'q_margin_mean_observe': statistics.mean(margins) if margins else None,
                         'q_margin_discounted_plans': sum(p['q_margin'] < 1 for p in heq),
                         'q_protected_required_selected': sum(p['q_protected_required_selected'] for p in heq)}
            mechanism.update(required_retries(run, actions))
            control = json.loads((V4 / 'runs' / f'ext-n2-heq-neutral-{card}' / 'metrics.json').read_text())
            row = {'case': case.upper(), 'card': card, 'run_id': run.name, 'total': metrics['total'],
                   'delta_total_vs_D': metrics['total'] - control['total'],
                   'components': metrics['components'], 'counts': metrics['counts'],
                   'J': metrics['coverage']['jain_from_official_penalty'],
                   'requests': metrics['requests'], 'reports': metrics['reports'],
                   'exposure': metrics['exposure'], 'runtime_seconds': metrics['runtime_seconds'],
                   'agent_wallclock_seconds': metrics['agent_wallclock_seconds'],
                   'accounted_wallclock_seconds': metrics['accounted_wallclock_seconds'],
                   'termination_reason': metrics['termination_reason'], 'exit_code': metrics['exit_code'],
                   'pace': metrics['pace'], 'internal_errors': [s for s in text.splitlines() if 'baseline: error' in s],
                   'source_tree_sha256': manifest['source_tree_sha256'], 'config_sha256': manifest['config_sha256'],
                   'config': json.loads((run / 'config.json').read_text()), 'mechanism': mechanism,
                   'metrics_path': str(run / 'metrics.json'), 'output_path': str(run / 'output')}
            rows.append(row)
    for row in rows:
        fm = next(r for r in rows if r['case'] == 'FM' and r['card'] == row['card'])
        if row['case'] == 'FMQ':
            row['delta_total_vs_FM'] = row['total'] - fm['total']
    registered = json.loads((OWN / 'validation/n4-registration.json').read_text())
    source = Path(registered['source'])
    result = {'schema_version': 'extension-n4-results-v1', 'runs': rows,
              'definitions': {'scores': '官方原值；J来自官方penalty反推，受六位舍入影响。',
                              'evaluation_counters': 'F预览与最终计划都会调用M/Q/E检查；候选量是函数评估次数，不是独立目标。E extra是最终场的额外时长数，各门槛candidate是全部预览累计。',
                              'retry': 'required再次赋值且此前有效观测最高factor<0.5；factor使用收到的官方观测CSV，无truth。',
                              'failed_attempt': 'required当次赋值未命中、无效或factor<0.5，包括已达标后的浅曝。'},
              'postcheck': {'source_unchanged': {p.name: digest(p) for p in source.iterdir() if p.is_file()} == registered['source_files_sha256'],
                            'configs_unchanged': all(digest(Path(c['path'])) == c['sha256'] for c in registered['configurations']),
                            'all_complete': all(r['exit_code'] == 0 and r['termination_reason'] == 'survey_complete' for r in rows),
                            'all_pace_zero': all(r['pace']['change_count'] == 0 for r in rows),
                            'no_internal_errors': all(not r['internal_errors'] for r in rows)}}
    (OWN / 'validation/n4-results.json').write_text(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True) + '\n')
    flat = [{key: row[key] for key in ('run_id', 'case', 'card', 'total', 'delta_total_vs_D', 'J', 'runtime_seconds', 'source_tree_sha256', 'config_sha256')}
            for row in rows]
    for row, full in zip(flat, rows):
        row.update(full['components']); row['required_missing'] = full['counts']['required_missing']
        row['mean_exposure_seconds'] = full['exposure']['actual_seconds']['mean']
    with (OWN / 'validation/n4-results.csv').open('w', newline='') as handle:
        writer = csv.DictWriter(handle, fieldnames=list(flat[0])); writer.writeheader(); writer.writerows(flat)
    print(json.dumps({'runs': flat, 'postcheck': result['postcheck']}, ensure_ascii=False))
    assert all(result['postcheck'].values())


if __name__ == '__main__':
    main()
