#!/usr/bin/env python3
"""仅汇总现有 run 记录；不导入模拟器、不重提取或修改单次 run。

从工作区根目录执行：
  /usr/bin/python3 -B experiments/v4/harness/aggregate_results.py

输出 results/all_runs.json、all_runs.csv、schema.json。相同入口日后收录新增 R4/R5。
"""
from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import io
import json
import math
import os
import re
from collections import Counter
from pathlib import Path

EXPERIMENT_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_VERSION = 'v4-all-runs-v1'
CATEGORIES = ['R1', 'control', 'intentional-timeout', 'strategy', 'harness-verification',
              'integration-verification', 'unknown']
# 只有已明确记录的验证 fixture，或 manifest/config 显式元数据，能够声明故意超时。
KNOWN_INTENTIONAL_TIMEOUT = 'r1-harness-guard'
EXPECTED_COMPONENTS = ['sum_best_scores', 'required_penalty', 'uniformity_penalty',
                       'report_settlement', 'observation_request_reward']

FIELD_SPECS = {
    'run_id': ('string', 'run 的权威标识；缺失时用目录名。'),
    'run_directory_name': ('string', '实际 run 目录名，不用于覆盖已有 run_id。'),
    'stage': ('string|null', 'manifest.stage 优先，metrics.stage 后备；保留 R2-control 等原值。'),
    'stage_group': ('string|null', '只提取 R1–R5 前缀便于分组，其余保持原阶段。'),
    'experiment_category': ('enum', 'R1/control/intentional-timeout/strategy/harness-verification/integration-verification/unknown。'),
    'category_evidence': ('string', '类别来自哪个显式字段或明确 fixture 规则。'),
    'family': ('string|null', 'config.family 优先；无配置的 R1 根据 agent_kind/source 区分 baseline/idle。'),
    'variant': ('string|null', 'config.variant 或 config.version；缺失不从成绩推断。'),
    'config': ('object|null', '该 run 已归档的完整配置，不解读策略优劣。'),
    'config_source': ('string|null', 'manifest.config_source 的原始配置入口路径。'),
    'agent_source': ('string|null', 'manifest.source 的策略源路径；早期未记录保持 null。'),
    'card': ('string|null', 'manifest/metrics 中 card_source 的末级名称；不打开卡片内容。'),
    'card_source': ('string|null', '记录中的原始数据目录，只作为来源字符串。'),
    'card_tree_sha256': ('string|null', 'run 记录的卡片树散列。'),
    'card_nights': ('number|null', 'metrics.card.night_count。'),
    'card_targets': ('number|null', 'metrics.card.target_count。'),
    'total': ('number|null', 'metrics.total 官方总分；缺失保持 null，不填 0。'),
    'score_available': ('boolean', 'metrics 明确 official_report_available 且有数值 total。'),
    'components': ('object', 'metrics.components 全部官方分项；CSV 同时展开 component_* 列。'),
    'required_missing': ('number|null', 'metrics.counts.required_missing。'),
    'coverage_jain': ('number|null', 'metrics.coverage.jain_from_official_penalty，受官方舍入影响。'),
    'coverage_qualified_targets': ('number|null', '达到公开 factor 阈值的不同有效目标计数；来自已有 metrics。'),
    'coverage_uniformity_bands': ('object|null', '已有 metrics 中各 RA 条带完成率。'),
    'targets_observed': ('number|null', 'metrics.counts.targets_observed，不同观测目标。'),
    'observe_actions': ('number|null', 'metrics.counts.observe_actions，一次 observe 对应一次曝光动作。'),
    'observation_rows': ('number|null', 'metrics.counts.observations，目标观测记录数，区别于曝光动作数。'),
    'decisions': ('number|null', 'metrics.counts.decisions，官方轨迹决策记录数。'),
    'decision_requests': ('number|null', 'metrics.decision_requests，实际 Agent 决策请求数。'),
    'actual_exposure_mean_seconds': ('number|null', '已有 metrics.exposure.actual_seconds.mean。'),
    'actual_exposure_median_seconds': ('number|null', '已有 metrics.exposure.actual_seconds.median。'),
    'actual_exposure_sum_seconds': ('number|null', '已有 metrics.exposure.actual_seconds.sum。'),
    'requested_exposure_mean_seconds': ('number|null', '已有 metrics.exposure.requested_seconds.mean。'),
    'simulated_observe_seconds': ('number|null', '已有 metrics 的实际模拟观测总时间。'),
    'simulated_wait_seconds': ('number|null', '已有 metrics 的模拟等待总时间。'),
    'simulated_span_seconds': ('number|null', '已有 metrics 的模拟轨迹首尾跨度。'),
    'request_issued': ('number|null', 'metrics.counts.observation_requests_issued。'),
    'request_completed': ('number|null', 'metrics.counts.observation_requests_completed。'),
    'report_count': ('number|null', 'metrics.reports.count。'),
    'report_correct': ('number|null', 'metrics.reports.correct。'),
    'report_false': ('number|null', 'metrics.reports.false。'),
    'runtime_seconds': ('number|null', 'manifest.runtime_seconds 优先；含 simulator 外层等待执行，不含 setup/锁等待。'),
    'runtime_with_setup_seconds': ('number|null', 'manifest 对整次 harness 操作的真实耗时，可能含锁等待。'),
    'accounted_wallclock_seconds': ('number|null', '已有 metrics 的官方计时成本。'),
    'agent_wallclock_seconds': ('number|null', '已有 metrics 的 Agent 时间。'),
    'global_wallclock_seconds': ('number|null', '已有 metrics 的每卡总时间预算。'),
    'pace_change_count': ('number|null', '已有 metrics.pace.change_count，不把缺少日志补为 0。'),
    'pace_changes': ('array|null', '已有 metrics.pace.changes_logged。'),
    'pace_telemetry_available': ('boolean|null', '已有 metrics 的透传 telemetry 是否存在。'),
    'pace_minimum_remaining_seconds': ('number|null', '已有 metrics 的最小剩余 wallclock。'),
    'run_status': ('string|null', '原 manifest.status；早期缺失时从 exit/报告推定并明确标记。'),
    'run_status_inferred': ('boolean', 'run_status 是否为汇总器给早期记录的机械推定。'),
    'evaluation_state': ('enum', 'expected-timeout/completed-full-season/completed-early/completed-partial/failed/running/missing-outputs/unknown。'),
    'process_complete': ('boolean', '有终态 status、end_utc 或 exit_code；不是全季科学完成。'),
    'full_season_complete': ('boolean', '有官方分数、exit_code=0、termination_reason=survey_complete。'),
    'intentional_timeout': ('boolean', '类别明确为 intentional-timeout；不会据任意 timeout 猜测。'),
    'termination_reason': ('string|null', 'manifest 优先、metrics 后备，保留外层 guard 与官方原因差异。'),
    'official_termination_reason': ('string|null', 'manifest.official_termination_reason；早期成功记录可由 metrics 原因补齐。'),
    'termination_detail': ('string|null', 'manifest.failure_detail 或已有 metrics 的详细原因。'),
    'exit_code': ('number|null', 'manifest.exit_code 优先，metrics 后备。'),
    'start_utc': ('string|null', 'run 原记录开始时间。'),
    'end_utc': ('string|null', 'run 原记录结束时间。'),
    'python_executable': ('string|null', 'run 原记录实际 Python 路径。'),
    'python_version': ('string|null', 'run 原记录实际版本。'),
    'upstream_commit': ('string|null', 'run 原记录的官方快照 commit。'),
    'provenance_backfilled_after_run': ('boolean|null', '旧 R1 是否明确事后补录来源；缺失不猜测。'),
    'backfill_note': ('string|null', 'manifest 对旧 R1 来源补录的原说明。'),
    'source_tree_sha256': ('string|null', '策略源树散列，不含动态 harness 注入文件。'),
    'effective_agent_tree_sha256': ('string|null', '实际运行 Agent 树散列，可能随路径/注入变化。'),
    'config_sha256': ('string|null', 'run 记录的配置原始字节散列。'),
    'config_file_sha256_now': ('string|null', '本次读取归档 config 文件的实际 SHA-256，供核对。'),
    'config_hash_matches_recorded': ('boolean|null', '当前配置字节与已记录 hash 是否一致；缺失则 null。'),
    'harness_tree_sha256': ('string|null', '运行时记录的 harness 树散列。'),
    'snapshot_tree_sha256': ('string|null', '运行时官方 vendor 树散列。'),
    'normalized_actions_sha256': ('string|null', '已有 metrics 中规范化动作散列。'),
    'normalized_score_sha256': ('string|null', '已有 metrics 中规范化官方报告散列。'),
    'concurrency': ('object|null', 'manifest 记录的槽、peer、load、锁等待等；保留原值。'),
    'record_issues': ('array', '缺失、解析、类型或 hash 问题；问题 run 仍保留一行。'),
    'input_sha256': ('object', '本次读取 manifest/config/metrics 原始字节散列。'),
    'evidence_links': ('object', '相对结果目录的已存在原始证据路径；只链接，不读取卡片或模拟真值。'),
}


def compact(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def reject_nonfinite(word):
    raise ValueError('JSON 非有限数值常量: ' + word)


def read_record(path, label, issues, hashes):
    if not path.is_file():
        issues.append(label + ': missing')
        return None
    try:
        raw = path.read_bytes()
        hashes[label] = hashlib.sha256(raw).hexdigest()
        value = json.loads(raw, parse_constant=reject_nonfinite)
        if not isinstance(value, dict):
            issues.append(label + ': expected object')
            return None
        return value
    except (OSError, UnicodeError, ValueError) as exc:
        issues.append(label + ': ' + type(exc).__name__ + ': ' + str(exc))
        return None


def nested(data, *keys):
    for key in keys:
        if not isinstance(data, dict):
            return None
        data = data.get(key)
    return data


def first(*values):
    return next((value for value in values if value is not None), None)


def classify(run_id, manifest, config, stage):
    for source, record in [('manifest', manifest), ('config', config)]:
        value = record.get('experiment_category')
        if value in CATEGORIES:
            return value, source + '.experiment_category'
        if record.get('intentional_timeout') is True:
            return 'intentional-timeout', source + '.intentional_timeout=true'
    if (run_id == KNOWN_INTENTIONAL_TIMEOUT and stage == 'harness-verification'
            and str(manifest.get('source', '')).endswith('/harness/fixtures/slow_agent')):
        return 'intentional-timeout', '已记录 r1-harness-guard + harness-verification + slow_agent fixture'
    if ('control' in str(stage).lower() or 'control' in str(config.get('family', '')).lower()):
        return 'control', 'stage/config.family 明确 control'
    if stage == 'R1':
        return 'R1', 'manifest/metrics.stage=R1'
    if re.match(r'^R[2-5](?:$|[-_])', str(stage)):
        return 'strategy', 'manifest/metrics.stage 为 R2–R5，且未标记 control'
    if stage == 'harness-verification':
        return 'harness-verification', 'stage=harness-verification，未声明故意超时'
    if stage == 'integration-verification':
        return 'integration-verification', 'stage=integration-verification，仅迁移等价验证，不混入策略实验'
    return 'unknown', '类别元数据不足，不从分数或 timeout 猜测'


def family_name(manifest, config, stage):
    if config.get('family') is not None:
        value = config['family']
        return '+'.join(map(str, value)) if isinstance(value, list) else str(value)
    if manifest.get('agent_kind'):
        return str(manifest['agent_kind'])
    source = str(manifest.get('source', ''))
    if stage == 'R1' and source.endswith('/agents/official/baseline'):
        return 'baseline'
    if stage == 'R1' and source.endswith('/agents/official/idle'):
        return 'idle'
    return None


def normalize_run(run, output_root):
    issues, hashes = [], {}
    raw_manifest = read_record(run/'manifest.json', 'manifest', issues, hashes)
    raw_config = read_record(run/'config.json', 'config', issues, hashes)
    raw_metrics = read_record(run/'metrics.json', 'metrics', issues, hashes)
    manifest, config, metrics = raw_manifest or {}, raw_config or {}, raw_metrics or {}
    stage = first(manifest.get('stage'), metrics.get('stage'))
    run_id = first(manifest.get('run_id'), metrics.get('run_id'), manifest.get('name'), run.name)
    category, category_evidence = classify(run_id, manifest, config, stage)
    card_source = first(manifest.get('card_source'), nested(metrics, 'card', 'source'))
    card = Path(card_source).name if card_source else None
    total = metrics.get('total')
    score_available = (metrics.get('official_report_available') is True
                       and isinstance(total, (int, float)) and not isinstance(total, bool)
                       and math.isfinite(total))
    exit_code = first(manifest.get('exit_code'), metrics.get('exit_code'))
    termination = first(manifest.get('termination_reason'), metrics.get('termination_reason'))
    status = manifest.get('status')
    status_inferred = status is None and exit_code == 0 and score_available
    if status_inferred:
        status = 'completed'
    process_complete = (status in {'completed', 'guard_timeout', 'runner_error', 'harness_error', 'interrupted'}
                        or manifest.get('end_utc') is not None or exit_code is not None)
    full_season = score_available and exit_code == 0 and termination == 'survey_complete'
    if category == 'intentional-timeout' and (termination == 'harness_guard_timeout' or status == 'guard_timeout'):
        evaluation_state = 'expected-timeout'
    elif full_season:
        evaluation_state = 'completed-full-season'
    elif score_available and exit_code == 0 and termination == 'agent_finished':
        evaluation_state = 'completed-early'
    elif status in {'setup', 'waiting_for_lock', 'running'} and not process_complete:
        evaluation_state = 'running'
    elif (exit_code is not None and exit_code != 0) or status in {'guard_timeout', 'runner_error', 'harness_error', 'interrupted'} or termination in {'agent_error', 'harness_error', 'harness_interrupted'}:
        evaluation_state = 'failed'
    elif score_available and exit_code == 0:
        evaluation_state = 'completed-partial'
    elif process_complete and not score_available:
        evaluation_state = 'missing-outputs'
    else:
        evaluation_state = 'unknown'
    config_hash = first(manifest.get('config_sha256'), nested(metrics, 'provenance', 'config_sha256'))
    actual_config_hash = hashes.get('config')
    config_match = actual_config_hash == config_hash if actual_config_hash and config_hash else None
    if config_match is False:
        issues.append('config: SHA-256 differs from recorded hash')
    for key in ['run_id', 'stage', 'total', 'exit_code']:
        recorded = manifest.get(key)
        measured = metrics.get(key)
        if recorded is not None and measured is not None and recorded != measured:
            issues.append(key + ': manifest/metrics values differ')
    links = {}
    evidence_files = ['manifest.json', 'config.json', 'metrics.json', 'source_manifest.json', 'card_manifest.json',
                      'runner_stdout.json', 'runner_stderr.log', 'mechanism_metrics.json',
                      'output/score_report.json', 'output/workflow_result.json', 'output/actions.jsonl',
                      'output/decisions.csv', 'output/observations.csv', 'output/messages.jsonl',
                      'output/agent.log', 'output/protocol_telemetry.jsonl']
    for name in evidence_files:
        path = run/name
        if path.is_file():
            links[name] = os.path.relpath(path.resolve(), output_root.resolve())
    components = metrics.get('components') or {}
    if not isinstance(components, dict):
        issues.append('metrics.components: expected object')
        components = {}
    row = {
        'run_id': run_id, 'run_directory_name': run.name, 'stage': stage,
        'stage_group': re.match(r'^R[1-5]', str(stage)).group(0) if re.match(r'^R[1-5]', str(stage)) else stage,
        'experiment_category': category, 'category_evidence': category_evidence,
        'family': family_name(manifest, config, stage), 'variant': first(config.get('variant'), config.get('version')),
        'config': raw_config, 'config_source': manifest.get('config_source'), 'agent_source': manifest.get('source'),
        'card': card, 'card_source': card_source,
        'card_tree_sha256': first(manifest.get('card_tree_sha256'), nested(metrics, 'card', 'tree_sha256')),
        'card_nights': nested(metrics, 'card', 'night_count'), 'card_targets': nested(metrics, 'card', 'target_count'),
        'total': total, 'score_available': score_available, 'components': components,
        'required_missing': nested(metrics, 'counts', 'required_missing'),
        'coverage_jain': nested(metrics, 'coverage', 'jain_from_official_penalty'),
        'coverage_qualified_targets': nested(metrics, 'coverage', 'qualified_target_count'),
        'coverage_uniformity_bands': nested(metrics, 'coverage', 'uniformity_bands'),
        'targets_observed': nested(metrics, 'counts', 'targets_observed'),
        'observe_actions': nested(metrics, 'counts', 'observe_actions'),
        'observation_rows': nested(metrics, 'counts', 'observations'),
        'decisions': nested(metrics, 'counts', 'decisions'), 'decision_requests': metrics.get('decision_requests'),
        'actual_exposure_mean_seconds': nested(metrics, 'exposure', 'actual_seconds', 'mean'),
        'actual_exposure_median_seconds': nested(metrics, 'exposure', 'actual_seconds', 'median'),
        'actual_exposure_sum_seconds': nested(metrics, 'exposure', 'actual_seconds', 'sum'),
        'requested_exposure_mean_seconds': nested(metrics, 'exposure', 'requested_seconds', 'mean'),
        'simulated_observe_seconds': nested(metrics, 'exposure', 'simulated_observe_seconds'),
        'simulated_wait_seconds': nested(metrics, 'exposure', 'simulated_wait_seconds'),
        'simulated_span_seconds': nested(metrics, 'exposure', 'simulated_span_seconds'),
        'request_issued': nested(metrics, 'counts', 'observation_requests_issued'),
        'request_completed': nested(metrics, 'counts', 'observation_requests_completed'),
        'report_count': nested(metrics, 'reports', 'count'), 'report_correct': nested(metrics, 'reports', 'correct'),
        'report_false': nested(metrics, 'reports', 'false'),
        'runtime_seconds': first(manifest.get('runtime_seconds'), metrics.get('runtime_seconds')),
        'runtime_with_setup_seconds': first(manifest.get('runtime_with_setup_seconds'), metrics.get('runtime_with_setup_seconds')),
        'accounted_wallclock_seconds': metrics.get('accounted_wallclock_seconds'),
        'agent_wallclock_seconds': metrics.get('agent_wallclock_seconds'),
        'global_wallclock_seconds': metrics.get('global_wallclock_seconds'),
        'pace_change_count': nested(metrics, 'pace', 'change_count'),
        'pace_changes': nested(metrics, 'pace', 'changes_logged'),
        'pace_telemetry_available': nested(metrics, 'pace', 'telemetry_available'),
        'pace_minimum_remaining_seconds': nested(metrics, 'pace', 'minimum_remaining_wallclock_seconds'),
        'run_status': status, 'run_status_inferred': status_inferred, 'evaluation_state': evaluation_state,
        'process_complete': process_complete, 'full_season_complete': full_season,
        'intentional_timeout': category == 'intentional-timeout', 'termination_reason': termination,
        'official_termination_reason': first(manifest.get('official_termination_reason'),
                                            metrics.get('termination_reason') if score_available and exit_code == 0 else None),
        'termination_detail': first(manifest.get('failure_detail'), metrics.get('termination_detail')),
        'exit_code': exit_code, 'start_utc': manifest.get('start_utc'), 'end_utc': manifest.get('end_utc'),
        'provenance_backfilled_after_run': manifest.get('provenance_backfilled_after_run'),
        'backfill_note': manifest.get('backfill_note'),
        'config_file_sha256_now': actual_config_hash, 'config_hash_matches_recorded': config_match,
        'normalized_actions_sha256': nested(metrics, 'hashes', 'normalized_actions_sha256'),
        'normalized_score_sha256': nested(metrics, 'hashes', 'normalized_score_sha256'),
        'concurrency': first(manifest.get('concurrency'), nested(metrics, 'provenance', 'concurrency')),
        'record_issues': issues, 'input_sha256': hashes, 'evidence_links': links,
    }
    for key in ['python_executable', 'python_version', 'upstream_commit', 'source_tree_sha256',
                'effective_agent_tree_sha256', 'config_sha256', 'harness_tree_sha256', 'snapshot_tree_sha256']:
        row[key] = first(manifest.get(key), nested(metrics, 'provenance', key))
    for key, value in row['components'].items():
        row['component_' + key] = value
    # 保留完整输入，未来新增指标不会因当前平面 schema 而丢失。
    return row, {'manifest': raw_manifest, 'config': raw_config, 'metrics': raw_metrics}


def aggregate(runs_root, output_root):
    snapshot_started = datetime.datetime.now(datetime.timezone.utc).isoformat()
    rows, raw_records = [], {}
    for run in sorted(runs_root.iterdir(), key=lambda p: p.name) if runs_root.exists() else []:
        if not run.is_dir():
            continue
        row, raw = normalize_run(run, output_root)
        rows.append(row)
        raw_records[run.name] = raw
    components = sorted(set(EXPECTED_COMPONENTS) | {key for row in rows for key in row['components']})
    columns = list(FIELD_SPECS)
    index = columns.index('components') + 1
    columns[index:index] = ['component_' + key for key in components]
    for row in rows:
        for key in components:
            row.setdefault('component_' + key, None)
    dataset = {
        'schema_version': SCHEMA_VERSION,
        'snapshot_started_at_utc': snapshot_started,
        'generated_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'aggregator_script': os.path.relpath(Path(__file__).resolve(), output_root.resolve()),
        'aggregator_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'runs_root': str(runs_root.resolve()), 'row_count': len(rows),
        'inventory_counts': {'by_category': dict(Counter(r['experiment_category'] for r in rows)),
                             'by_evaluation_state': dict(Counter(r['evaluation_state'] for r in rows)),
                             'rows_with_record_issues': sum(bool(r['record_issues']) for r in rows)},
        'rows': rows, 'source_records': raw_records,
    }
    schema = {
        'schema_version': SCHEMA_VERSION, 'description': '仅标准化已有 run 记录，不执行模拟或总体分析。',
        'json_file': 'all_runs.json', 'csv_file': 'all_runs.csv',
        'csv_encoding': 'UTF-8', 'row_order': 'run 目录名字典序，所有目录保留，不按成绩筛选。',
        'null_policy': 'JSON null 与 CSV 空单元格均表示缺失；数值 0 保持 0；对象/数组 CSV 为紧凑 JSON。',
        'categories': CATEGORIES,
        'evaluation_states': ['expected-timeout', 'completed-full-season', 'completed-early', 'completed-partial', 'failed',
                              'running', 'missing-outputs', 'unknown'],
        'source_precedence': 'manifest 提供执行与 hash；config 提供原始策略参数；metrics 提供官方分数及派生指标。完整输入在 source_records。',
        'scope': '仅读取 run 根目录 manifest/config/metrics；证据只检查存在并链接，不读取 card_snapshot、data/cards 或保留集内容。',
        'rerun_command': '/usr/bin/python3 -B experiments/v4/harness/aggregate_results.py',
        'no_simulator_execution': True,
        'columns': [{'name': name, 'type': FIELD_SPECS[name][0], 'description': FIELD_SPECS[name][1]}
                    if name in FIELD_SPECS else {'name': name, 'type': 'number|null',
                    'description': 'metrics.components.' + name[len('component_'):] + ' 官方原值，单位分。'}
                    for name in columns],
    }
    return dataset, schema, columns


def atomic_write(path, content):
    temporary = path.with_name('.' + path.name + '.tmp-' + str(os.getpid()))
    temporary.write_text(content, encoding='utf-8')
    os.replace(temporary, path)


def write_outputs(dataset, schema, columns, output_root):
    output_root.mkdir(parents=True, exist_ok=True)
    stream = io.StringIO(newline='')
    writer = csv.DictWriter(stream, fieldnames=columns, lineterminator='\n')
    writer.writeheader()
    for row in dataset['rows']:
        writer.writerow({key: compact(row.get(key)) if isinstance(row.get(key), (dict, list, bool))
                         else row.get(key) for key in columns})
    atomic_write(output_root/'all_runs.json', json.dumps(dataset, ensure_ascii=False, indent=2, allow_nan=False)+'\n')
    atomic_write(output_root/'all_runs.csv', stream.getvalue())
    atomic_write(output_root/'schema.json', json.dumps(schema, ensure_ascii=False, indent=2, allow_nan=False)+'\n')


def selftest():
    import tempfile
    with tempfile.TemporaryDirectory(prefix='v4-aggregate-selftest-') as scratch:
        root, output = Path(scratch)/'runs', Path(scratch)/'results'
        def fixture(name, manifest, metrics, config=None):
            run = root/name; run.mkdir(parents=True)
            for filename, value in [('manifest.json', manifest), ('metrics.json', metrics), ('config.json', config or {})]:
                (run/filename).write_text(json.dumps(value)+'\n')
        fixture('r1-harness-guard', {'run_id':'r1-harness-guard','stage':'harness-verification',
                'source':'/example/harness/fixtures/slow_agent','status':'guard_timeout','exit_code':-15,
                'termination_reason':'harness_guard_timeout'}, {'official_report_available':False,'total':None})
        fixture('real-strategy-timeout', {'stage':'R4','status':'guard_timeout','exit_code':-15,
                'termination_reason':'harness_guard_timeout'}, {'official_report_available':False,'total':None}, {'family':['D','P']})
        fixture('legacy-idle', {'stage':'R1','agent_kind':'idle','exit_code':0,'termination_reason':'agent_finished'},
                {'official_report_available':True,'total':-6200.0,'components':{'required_penalty':-6000.0}})
        fixture('new-control', {'stage':'R5-control','status':'completed','exit_code':0,'termination_reason':'survey_complete'},
                {'official_report_available':True,'total':0.0}, {'family':'control'})
        missing = root/'partial-run'; missing.mkdir(); (missing/'manifest.json').write_text('{invalid')
        dataset, schema, columns = aggregate(root, output)
        rows = {r['run_directory_name']:r for r in dataset['rows']}
        assert len(rows) == 5
        assert rows['r1-harness-guard']['evaluation_state']=='expected-timeout'
        assert rows['r1-harness-guard']['experiment_category']=='intentional-timeout'
        assert rows['real-strategy-timeout']['evaluation_state']=='failed'
        assert rows['real-strategy-timeout']['experiment_category']=='strategy'
        assert rows['real-strategy-timeout']['family']=='D+P'
        assert rows['real-strategy-timeout']['total'] is None
        assert rows['legacy-idle']['evaluation_state']=='completed-early'
        assert rows['legacy-idle']['family']=='idle' and rows['legacy-idle']['run_status_inferred']
        assert rows['new-control']['experiment_category']=='control' and rows['new-control']['total']==0.0
        assert rows['partial-run']['record_issues'] and rows['partial-run']['total'] is None
        assert not rows['partial-run']['full_season_complete']
        write_outputs(dataset, schema, columns, output)
        csv_rows = list(csv.DictReader((output/'all_runs.csv').open()))
        assert len(csv_rows)==5 and next(r for r in csv_rows if r['run_directory_name']=='real-strategy-timeout')['total']==''
        assert next(r for r in csv_rows if r['run_directory_name']=='new-control')['total']=='0.0'
        before = {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
        again, _schema, _columns = aggregate(root, output)
        assert again['rows']==dataset['rows']
        after = {p.relative_to(root).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in root.rglob('*') if p.is_file()}
        assert before==after
    print(compact({'status':'pass','checks':['expected versus strategy timeout','legacy idle normalization',
                'R5 control and combination metadata','partial invalid records preserved','zero versus null CSV',
                'repeatable rows and read-only inputs']}))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--runs-root', type=Path, default=EXPERIMENT_ROOT/'runs')
    parser.add_argument('--output-root', type=Path, default=EXPERIMENT_ROOT/'results')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        selftest()
        return 0
    # 同一目标目录串行生成，避免两个汇总命令交错发布 CSV/JSON。
    import fcntl
    args.output_root.mkdir(parents=True, exist_ok=True)
    with (args.output_root/'.aggregate.lock').open('a+') as lock:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX)
        dataset, schema, columns = aggregate(args.runs_root, args.output_root)
        write_outputs(dataset, schema, columns, args.output_root)
    print(compact({'schema_version':SCHEMA_VERSION,'row_count':dataset['row_count'],
                   'inventory_counts':dataset['inventory_counts'],'output_root':str(args.output_root.resolve())}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
