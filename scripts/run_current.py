#!/usr/bin/env python3
"""当前官方示例的离线实验入口；历史运行器只提供共享隔离工具。"""
from __future__ import annotations
import argparse
import json
import math
import os
import platform
import shutil
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'experiments/v4/harness'))
from common import SimulatorLease, copy_snapshot, file_sha256, tree_manifest, write_json
from metrics import extract
from run import select_entry, stop_owned_processes, terminate_signal, utc_now, validate_environment


def main(argv=None):
    env_path = ROOT / 'experiments/current/environment.json'
    settings = json.loads(env_path.read_text())
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run-id', required=True)
    parser.add_argument('--card', default='L1', help='L1–L4，或完整卡目录')
    parser.add_argument('--agent', type=Path, default=ROOT / settings['agent'])
    parser.add_argument('--entry')
    parser.add_argument('--config', type=Path)
    parser.add_argument('--wallclock', type=float, default=900)
    parser.add_argument('--process-timeout', type=float)
    parser.add_argument('--exclusive', action='store_true')
    args = parser.parse_args(argv)
    import re
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,127}', args.run_id):
        parser.error('run-id 不符合目录名规范')
    timeout = args.process_timeout if args.process_timeout is not None else min(args.wallclock, 900) + 120
    if not all(math.isfinite(v) and v > 0 for v in (args.wallclock, timeout)):
        parser.error('时间上限必须为有限正数')
    signal.signal(signal.SIGTERM, terminate_signal)
    source, entry = select_entry(args.agent.resolve(), args.entry)
    card = ROOT / settings['cards'] / args.card if args.card in ('L1','L2','L3','L4') else Path(args.card).resolve()
    if not (card / 'config/v4_scenario.json').is_file():
        parser.error('卡片缺少 config/v4_scenario.json')
    config_bytes = args.config.read_bytes() if args.config else b'{}\n'
    config = json.loads(config_bytes)
    if not isinstance(config, dict):
        parser.error('配置必须为 JSON 对象')
    environment = validate_environment(config.get('environment', {}))
    snapshot = json.loads((ROOT / settings['snapshot_manifest']).read_text())
    examples = (ROOT / settings['snapshot_manifest']).parent / 'examples'
    if tree_manifest(examples)['tree_sha256'] != snapshot['examples']['tree_sha256']:
        parser.error('官方快照散列已变化')
    runner = ROOT / settings['runner'] / 'run_local.py'
    python = settings['python']
    run = ROOT / settings['runs'] / args.run_id
    run.mkdir(parents=True, exist_ok=False)
    manifest = {'schema_version':'survey-current-run-v1','run_id':args.run_id,'stage':'migration',
        'status':'setup','start_utc':utc_now(),'upstream_commit':settings['upstream_commit'],
        'environment_sha256':file_sha256(env_path),'source':str(source),'source_entry':str(entry),
        'card_source':str(card),'python_version':subprocess.check_output([python,'--version'],text=True).strip(),
        'python_executable':python,'platform':platform.platform(),'llm_enabled':False,
        'network_calls_authorized':False,'agent_environment':environment,
        'requested_wallclock_seconds':args.wallclock,'process_timeout_seconds':timeout,
        'runner_sha256':file_sha256(runner),'engine_manifest_sha256':file_sha256(runner.parent/'ENGINE_MANIFEST.json'),
        'harness_sha256':file_sha256(Path(__file__)),
        'shared_helpers_tree_sha256':tree_manifest(ROOT/'experiments/v4/harness')['tree_sha256']}
    output = run/'output'
    output.mkdir()
    proxy = run/'agent/_harness_proxy.py'
    process = None
    started = None
    result_code = 1
    write_json(run/'manifest.json',manifest)
    try:
        for src, dest, name in ((source,run/'source_snapshot','source'),(card,run/'card_snapshot','card')):
            record = copy_snapshot(src,dest)
            write_json(run/(name+'_manifest.json'),record)
            manifest[name+'_tree_sha256'] = record['tree_sha256']
        copy_snapshot(run/'source_snapshot',run/'agent',readonly=False)
        if proxy.exists() or (proxy.parent/'_harness_proxy_config.json').exists():
            raise ValueError('Agent 使用了 harness 保留文件名')
        (run/'config.json').write_bytes(config_bytes)
        (run/'config.json').chmod(0o444)
        (run/'agent/experiment_config.json').write_bytes(config_bytes)
        environment['EXPERIMENT_CONFIG_PATH'] = os.path.relpath(run/'agent/experiment_config.json',(run/'agent'/entry).parent)
        shutil.copy2(ROOT/'experiments/v4/harness/protocol_proxy.py',proxy)
        write_json(proxy.parent/'_harness_proxy_config.json',{'entry':str(run/'agent'/entry),
                   'telemetry_path':str(output/'protocol_telemetry.jsonl')})
        (run/'tmp').mkdir()
        (run/'work').mkdir()
        command = [python,'-B',str(runner),'--card',str(run/'card_snapshot'),
                   '--agent',__import__('shlex').join([python,'-B',str(proxy)]),
                   '--agent-cwd',str(proxy.parent),'--out',str(output),
                   '--wallclock',str(args.wallclock),'--inherit-env','--quiet']
        manifest.update({'card_snapshot':str(run/'card_snapshot'),'config_sha256':file_sha256(run/'config.json'),
                         'effective_agent_tree_sha256':tree_manifest(proxy.parent)['tree_sha256'],
                         'command':command,'cwd':str(run/'work'),'agent_cwd':str(proxy.parent),
                         'status':'waiting_for_lock'})
        write_json(run/'manifest.json',manifest)
        # --inherit-env 只继承这里构造的白名单，而非用户 shell；快照排除 .env。
        clean_env = {'PATH':'/usr/bin:/bin:/usr/sbin:/sbin','TMPDIR':str(run/'tmp'),
                     'LANG':'C.UTF-8','LC_ALL':'C.UTF-8',**environment}
        with SimulatorLease(args.run_id,exclusive=args.exclusive) as lease:
            manifest.update({'concurrency':lease.conditions,'status':'running','runner_start_utc':utc_now()})
            started = time.monotonic()
            with (run/'runner_stdout.json').open('w') as stdout, (run/'runner_stderr.log').open('w') as stderr:
                process = subprocess.Popen(command,cwd=run/'work',env=clean_env,stdout=stdout,stderr=stderr,
                                           start_new_session=True,pass_fds=lease.fds)
                manifest['runner_pid'] = process.pid
                write_json(run/'manifest.json',manifest)
                try:
                    result_code = process.wait(timeout=timeout)
                    manifest['status'] = 'completed' if result_code == 0 else 'runner_error'
                except subprocess.TimeoutExpired:
                    stop_owned_processes(process,output,proxy)
                    manifest.update({'status':'guard_timeout','termination_reason':'harness_guard_timeout'})
                    result_code = 124
                except BaseException:
                    stop_owned_processes(process,output,proxy)
                    raise
                finally:
                    manifest['runtime_seconds'] = time.monotonic()-started
    except KeyboardInterrupt:
        manifest.update({'status':'interrupted','termination_reason':'harness_interrupted'})
        result_code = 130
    except Exception as exc:
        manifest.update({'status':'harness_error','failure_detail':f'{type(exc).__name__}: {exc}'})
    finally:
        if process is not None:
            if process.poll() is None:
                stop_owned_processes(process,output,proxy)
            manifest['exit_code'] = process.returncode
        manifest['end_utc'] = utc_now()
        workflow = output/'workflow_result.json'
        if workflow.is_file():
            manifest['official_termination_reason'] = json.loads(workflow.read_text())['termination_reason']
            manifest.setdefault('termination_reason',manifest['official_termination_reason'])
        write_json(run/'manifest.json',manifest)
        metrics = extract(run)
        if manifest['status'] != 'completed':
            # 截断运行的部分报告保留原件，不能作为完整策略分数。
            metrics['partial_total'] = metrics['total']
            metrics['total'] = None
        write_json(run/'metrics.json',metrics)
        print(json.dumps({'run_id':args.run_id,'status':manifest['status'],'total':metrics['total'],
                         'termination_reason':manifest.get('termination_reason'),
                         'runtime_seconds':manifest.get('runtime_seconds')},ensure_ascii=False))
    return result_code if result_code >= 0 else 1

if __name__ == '__main__':
    raise SystemExit(main())
