#!/usr/bin/env python3
"""核对当前迁移证据，不重跑模拟，不重评分。"""
from __future__ import annotations
import difflib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'experiments/v4/harness'))
from common import file_sha256, tree_manifest, write_json


def main():
    current=ROOT/'experiments/current'
    settings=json.loads((current/'environment.json').read_text())
    snapshot_root=(ROOT/settings['snapshot_manifest']).parent
    snapshot=json.loads((snapshot_root/'snapshot_manifest.json').read_text())
    checks={'snapshot_examples_unchanged':tree_manifest(snapshot_root/'examples')['tree_sha256']==snapshot['examples']['tree_sha256'],
            'snapshot_docs_unchanged':tree_manifest(snapshot_root/'docs')['tree_sha256']==snapshot['docs']['tree_sha256']}
    commands=[['/usr/bin/python3','-B',str(ROOT/settings['runner']/'verify_engine.py')],
              ['/usr/bin/python3','-B','-m','unittest','discover','-s',str(current/'tests'),'-v']]
    check_results=[]
    for i,command in enumerate(commands):
        result=subprocess.run(command,cwd=ROOT,capture_output=True,text=True)
        (current/f'validation-check-{i}.log').write_text(result.stdout+result.stderr)
        check_results.append({'command':command,'exit_code':result.returncode,'log':f'validation-check-{i}.log'})
        checks[f'command_{i}_passed']=result.returncode==0
    frozen=json.loads((ROOT/'experiments/v4/manual_card_evaluation/selection_frozen.json').read_text())
    protected={path:file_sha256(ROOT/path)==digest for path,digest in frozen['protected_old_artifact_sha256'].items()}
    checks['protected_old_artifacts_unchanged']=all(protected.values())
    checks['old_vendor_unchanged']=tree_manifest(ROOT/'experiments/v4/vendor/starter_kit_v4')['tree_sha256']==frozen['vendor_tree_sha256']
    checks['old_harness_unchanged']=tree_manifest(ROOT/'experiments/v4/harness')['tree_sha256']==frozen['harness_tree_sha256']
    ids=['migration-python-L1','migration-python-L1-repeat','migration-python-L2','migration-python-L3','migration-python-L4','migration-old-D-L1','migration-guard-timeout','rules-refresh-python-L1']
    rows=[]
    live=[]
    for name in ids:
        run=current/'runs'/name
        manifest=json.loads((run/'manifest.json').read_text())
        metrics=json.loads((run/'metrics.json').read_text())
        log=(run/'output/agent.log').read_text(errors='replace') if (run/'output/agent.log').exists() else ''
        rows.append({'run_id':name,'status':manifest['status'],'total':metrics['total'],
                     'termination_reason':manifest.get('termination_reason'),'runtime_seconds':manifest.get('runtime_seconds'),
                     'required_missing':metrics.get('counts',{}).get('required_missing'),
                     'counts':metrics.get('counts'), 'source_tree_sha256':manifest.get('source_tree_sha256'),
                     'card_tree_sha256':manifest.get('card_tree_sha256'),
                     'planner_error_present':'planner error' in log or 'failed to initialize' in log or 'invalid action' in log,
                     'zero_llm_calls_logged':'llm_calls=0' in log,
                     'evidence_path':str(run.relative_to(ROOT))})
        for pidfile,key in ((run/'manifest.json','runner_pid'),(run/'output/proxy_pid.json','proxy_pid')):
            if pidfile.exists():
                pid=json.loads(pidfile.read_text()).get(key)
                if pid:
                    command=subprocess.run(['ps','-p',str(pid),'-o','command='],capture_output=True,text=True).stdout.strip()
                    if str(run) in command: live.append({'pid':pid,'command':command})
    all_ps=subprocess.run(['ps','-axo','pid=,command='],capture_output=True,text=True).stdout
    residual=[line.strip() for line in all_ps.splitlines() if str(current/'runs') in line]
    checks['owned_processes_exited']=not live and not residual
    checks['four_cards_complete']=all(r['status']=='completed' and r['termination_reason']=='survey_complete' for r in rows[:5])
    checks['new_planner_no_exceptions']=all(not r['planner_error_present'] for r in rows[:5])
    checks['offline_calls_zero']=all(r['zero_llm_calls_logged'] for r in rows[:5])
    checks['legacy_D_compatible']=rows[5]['status']=='completed' and rows[5]['termination_reason']=='survey_complete'
    checks['guard_has_no_complete_score']=rows[6]['status']=='guard_timeout' and rows[6]['total'] is None
    one=current/'runs'/ids[0]/'output'
    repeat=current/'runs'/ids[1]/'output'
    equivalence={name:file_sha256(one/name)==file_sha256(repeat/name) for name in ('actions.jsonl','decisions.csv','observations.csv','score_report.json')}
    checks['L1_repeat_byte_identical']=all(equivalence.values())
    refreshed=current/'runs/rules-refresh-python-L1/output'
    checks['latest_L1_byte_identical']=all(file_sha256(one/name)==file_sha256(refreshed/name) for name in equivalence)
    checks['latest_L1_complete']=rows[-1]['status']=='completed' and rows[-1]['termination_reason']=='survey_complete'
    checks['latest_L1_zero_llm_calls']=rows[-1]['zero_llm_calls_logged'] and not rows[-1]['planner_error_present']
    upstream=snapshot_root/'examples/python'
    work=current/'agent'
    diffs=[]
    changed=[]
    for p in sorted(upstream.rglob('*')):
        if p.is_file():
            rel=p.relative_to(upstream)
            q=work/rel
            if p.read_bytes()!=q.read_bytes():
                changed.append(str(rel))
                diffs.extend(difflib.unified_diff(p.read_text().splitlines(True),q.read_text().splitlines(True),fromfile='upstream/'+str(rel),tofile='working/'+str(rel)))
    (current/'upstream-local.patch').write_text(''.join(diffs))
    result={'schema_version':'survey-migration-validation-v1','upstream_commit':snapshot['upstream_commit'],
            'checks':checks,'passed':all(checks.values()),'runs':rows,'repeat_file_checks':equivalence,
            'protected_old_artifacts':protected,'commands':check_results,'local_modified_files':changed,
            'working_agent_tree_sha256':tree_manifest(work)['tree_sha256'],'residual_processes':residual,
            'limitations':['local scores only','LLM not called','public L cards are not blind holdout','Python 3.12 platform image not run','process isolation is not OS filesystem or network sandbox']}
    write_json(current/'validation-current.json',result)
    print(json.dumps({'passed':result['passed'],'checks':checks},ensure_ascii=False))
    return 0 if result['passed'] else 1

if __name__=='__main__': raise SystemExit(main())
