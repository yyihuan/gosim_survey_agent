#!/usr/bin/env python3
"""执行Root冻结的52项N5清单；各方案并行，方案内四卡串行，同一六槽锁。"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import signal
import sys
import threading
import time

HERE = Path(__file__).resolve().parent
EXTENSION = HERE.parent
V4 = EXTENSION.parent
WORKSPACE = V4.parents[1]
sys.path.insert(0, str(V4 / 'harness'))
from common import tree_manifest, write_json


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def location(value):
    path = Path(value)
    return path.resolve() if path.is_absolute() else (WORKSPACE / path).resolve()


def config_hash(value):
    return sha(location(value)) if value else hashlib.sha256(b'{}\n').hexdigest()


def command(run):
    result = ['/usr/bin/python3', '-B', str(HERE / 'run_one.py'), '--run-id', run['run_id'],
              '--stage', 'N5', '--agent', str(location(run['agent'])), '--card', str(location(run['card'])),
              '--wallclock', '900']
    if run.get('config'):
        result += ['--config', str(location(run['config']))]
    return result


def preflight(plan, *, executing=False):
    assert plan['schema_version'] == 'v4-extension-N5-plan-v1'
    assert plan['case_count'] == 13 and plan['run_count'] == 52
    assert plan['simulator_limit'] == 6 and plan['wallclock_seconds'] == 900 and plan['USE_LLM'] == '0'
    runs = plan['runs']; assert len(runs) == 52
    assert len({r['run_id'] for r in runs}) == 52
    expected = {c['case_id'] for c in plan['cases']}
    assert len(expected) == 13 and {r['case_id'] for r in runs} == expected
    assert {r['stage'] for r in runs} == {'N5'}
    assert all(r['run_id'].startswith('ext-n5-') for r in runs)
    assert tree_manifest(V4 / 'harness')['tree_sha256'] == plan['harness_tree_sha256']
    assert tree_manifest(V4 / 'vendor/starter_kit_v4')['tree_sha256'] == plan['vendor_tree_sha256']
    assert all(sha(HERE / name) == value for name, value in plan['wrapper_source_sha256'].items())
    for case in plan['cases']:
        assert tree_manifest(location(case['agent']))['tree_sha256'] == case['source_tree_sha256'], case['case_id']
        assert config_hash(case['config']) == case['config_sha256'], case['case_id']
        assert all(item.get('full_season_complete') and item.get('source_matches_current') and
                   item.get('config_matches_current') for item in case['development_evidence']), case['case_id']
    allowed_cards = {'ext-holdout-' + letter for letter in 'abcd'}
    assert {card['card_id'] for card in plan['cards']} == allowed_cards
    for card in plan['cards']:
        path = location(card['card'])
        assert path.parent == (EXTENSION / 'data/cards').resolve() and path.name == card['card_id']
        assert tree_manifest(path)['tree_sha256'] == card['card_tree_sha256'], card['card_id']
    for run in runs:
        assert run['card_id'] in allowed_cards
        assert not (V4 / 'runs' / run['run_id']).exists(), '既有run不覆盖：' + run['run_id']
    if executing:
        assert plan['status'] == 'frozen' and plan.get('authorized') is True, '必须先收到Root明确冻结授权'
    return {'passed': True, 'case_count': 13, 'run_count': 52, 'card_count': 4,
            'all_source_config_card_hashes_match': True, 'old_harness_and_vendor_match': True,
            'no_run_started': True, 'authorization_checked': executing}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, default=EXTENSION / 'evaluation/N5_PLAN.json')
    parser.add_argument('--validate-only', action='store_true', help='只读核对草案或冻结清单；不启动卡，不写授权')
    args = parser.parse_args()
    plan_path = args.plan.resolve()
    assert plan_path.parent == (EXTENSION / 'evaluation').resolve(), '清单必须位于extension/evaluation'
    plan = json.loads(plan_path.read_text())
    checked = preflight(plan, executing=not args.validate_only)
    if args.validate_only:
        print(json.dumps({'plan': str(plan_path), 'plan_sha256': sha(plan_path), **checked}, ensure_ascii=False))
        return 0
    authorization = json.loads((EXTENSION / 'evaluation/N5_AUTHORIZATION.json').read_text())
    assert authorization['authorized_by'] == 'Root' and authorization['plan_sha256'] == sha(plan_path)
    assert set(authorization['authorized_run_ids']) == {r['run_id'] for r in plan['runs']}
    if authorization.get('batch_source_sha256'):
        assert authorization['batch_source_sha256'] == sha(Path(__file__).resolve())
    batch = EXTENSION / 'evaluation/N5_execution'
    batch.mkdir(exist_ok=False)
    (batch / 'logs').mkdir()
    (batch / 'results').mkdir()
    (batch / 'plan.json').write_bytes(plan_path.read_bytes())
    (batch / 'plan.json').chmod(0o444)
    (batch / 'authorization.json').write_bytes((EXTENSION / 'evaluation/N5_AUTHORIZATION.json').read_bytes())
    protected = {name: sha(V4 / 'results' / name) for name in ['all_runs.json', 'all_runs.csv']}
    started = time.monotonic()
    status = {'schema_version': 'v4-extension-N5-execution-v1', 'status': 'running',
              'started_at_utc': now(), 'plan_sha256': sha(plan_path), 'batch_source_sha256': sha(Path(__file__).resolve()),
              'simulator_limit': 6, 'strategy_groups': 13, 'per_group_card_order': [c['card_id'] for c in plan['cards']],
              'per_group_cards_serial': True, 'case_groups_scheduled_together': True,
              'command': [sys.executable, '-B', str(Path(__file__).resolve()), *sys.argv[1:]],
              'cwd': str(Path.cwd()), 'old_results_sha256_before': protected, 'results': []}
    write_json(batch / 'status.json', status)
    record_lock = threading.Lock()
    running_lock = threading.Lock()
    running = set()
    cancelled = threading.Event()

    def stop_batch(_signum, _frame):
        cancelled.set()
        with running_lock:
            for process in list(running):
                if process.poll() is None:
                    process.send_signal(signal.SIGTERM)
        raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, stop_batch)
    signal.signal(signal.SIGINT, stop_batch)

    def save_result(result):
        write_json(batch / 'results' / (result['run_id'] + '.json'), result)
        with record_lock:
            status['results'].append(result)
            write_json(batch / 'status.json', status)
            with (batch / 'execution.jsonl').open('a') as stream:
                stream.write(json.dumps(result, ensure_ascii=False) + '\n')

    def run_group(case_id):
        for run in [r for r in plan['runs'] if r['case_id'] == case_id]:
            cmd = command(run)
            result = {'run_id': run['run_id'], 'case_id': case_id, 'reference_id': run['reference_id'],
                      'card_id': run['card_id'], 'command': cmd, 'started_at_utc': now(), 'status': 'not-run',
                      'score': None, 'error': None}
            try:
                if cancelled.is_set():
                    raise RuntimeError('batch cancelled before this run started')
                assert tree_manifest(location(run['agent']))['tree_sha256'] == run['source_tree_sha256']
                assert config_hash(run['config']) == run['config_sha256']
                assert tree_manifest(location(run['card']))['tree_sha256'] == run['card_tree_sha256']
                with (batch / 'logs' / (run['run_id'] + '.log')).open('w') as log:
                    with running_lock:
                        if cancelled.is_set():
                            raise RuntimeError('batch cancelled before process creation')
                        process = subprocess.Popen(cmd, cwd=WORKSPACE, stdout=log, stderr=subprocess.STDOUT,
                                                   start_new_session=True)
                        running.add(process)
                    try:
                        process.wait()
                    finally:
                        with running_lock:
                            running.discard(process)
                result.update(exit_code=process.returncode, status='completed' if process.returncode == 0 else 'failed')
                run_dir = V4 / 'runs' / run['run_id']
                if (run_dir / 'manifest.json').is_file():
                    manifest = json.loads((run_dir / 'manifest.json').read_text())
                    metrics = json.loads((run_dir / 'metrics.json').read_text())
                    checks = {'source': manifest.get('source_tree_sha256') == run['source_tree_sha256'],
                              'config': manifest.get('config_sha256') == run['config_sha256'],
                              'card': manifest.get('card_tree_sha256') == run['card_tree_sha256']}
                    result.update(score=metrics.get('total'), termination_reason=manifest.get('termination_reason'),
                                  runtime_seconds=manifest.get('runtime_seconds'),
                                  full_season_complete=manifest.get('termination_reason') == 'survey_complete' and process.returncode == 0,
                                  pace_change_count=metrics.get('pace', {}).get('change_count'),
                                  archived_hash_checks=checks)
                    assert all(checks.values()), 'run snapshot differs from frozen manifest'
            except Exception as error:
                result['error'] = type(error).__name__ + ': ' + str(error)
                if (V4 / 'runs' / run['run_id']).exists():
                    result['status'] = 'failed'
            result['finished_at_utc'] = now()
            save_result(result)
            print(json.dumps({key: result.get(key) for key in ['run_id', 'status', 'score', 'runtime_seconds', 'error']}, ensure_ascii=False), flush=True)

    try:
        # 全部13方案一同调度；每方案至多一个模拟器，由同一lease限制全局≤6。
        with ThreadPoolExecutor(max_workers=13) as executor:
            futures = [executor.submit(run_group, c['case_id']) for c in plan['cases']]
            for future in as_completed(futures):
                future.result()
        status['postflight'] = {
            'old_results_unchanged': protected == {name: sha(V4 / 'results' / name) for name in protected},
            'harness_unchanged': tree_manifest(V4 / 'harness')['tree_sha256'] == plan['harness_tree_sha256'],
            'vendor_unchanged': tree_manifest(V4 / 'vendor/starter_kit_v4')['tree_sha256'] == plan['vendor_tree_sha256'],
            'sources_unchanged': all(tree_manifest(location(c['agent']))['tree_sha256'] == c['source_tree_sha256'] for c in plan['cases']),
            'configs_unchanged': all(config_hash(c['config']) == c['config_sha256'] for c in plan['cases']),
            'cards_unchanged': all(tree_manifest(location(c['card']))['tree_sha256'] == c['card_tree_sha256'] for c in plan['cards']),
            'wrapper_unchanged': all(sha(HERE / name) == value for name, value in plan['wrapper_source_sha256'].items()),
        }
        status.update(status='completed', finished_at_utc=now(), runtime_seconds=time.monotonic() - started,
                      result_count=len(status['results']), full_season_count=sum(r.get('full_season_complete', False) for r in status['results']),
                      error_count=sum(r['status'] != 'completed' or bool(r['error']) for r in status['results']))
        assert len(status['results']) == 52
        assert all(status['postflight'].values()), status['postflight']
    except BaseException as error:
        status.update(status='interrupted_or_batch_error', error=type(error).__name__ + ': ' + str(error), finished_at_utc=now())
        raise
    finally:
        write_json(batch / 'status.json', status)
        subprocess.run(['/usr/bin/python3', '-B', str(HERE / 'aggregate_results.py')], cwd=WORKSPACE, check=False)
    print(json.dumps({key: status.get(key) for key in ['status', 'result_count', 'full_season_count', 'error_count', 'runtime_seconds']}, ensure_ascii=False))
    return 0 if status['error_count'] == 0 else 1


if __name__ == '__main__':
    raise SystemExit(main())
