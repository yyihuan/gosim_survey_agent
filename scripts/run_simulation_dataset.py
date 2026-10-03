#!/usr/bin/env python3
"""模拟数据批量离线运行；复用当前入口，两槽并发，构建阶段拒绝冻结组。"""
from __future__ import annotations
import argparse
import concurrent.futures
import json
import os
import re
import subprocess
import sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments/v4/harness'))
from common import tree_manifest,write_json,file_sha256

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset',default='sim-v1-20261003')
    p.add_argument('--batch-id',required=True)
    p.add_argument('--pilot',action='store_true')
    p.add_argument('--split',choices=['development','selection','astronomy_extension','diagnostic'],default='development')
    p.add_argument('--resume',action='store_true')
    a=p.parse_args()
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,50}',a.batch_id):p.error('invalid batch-id')
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,70}',a.dataset):p.error('invalid dataset-id')
    dataset=ROOT/'experiments/current/datasets'/a.dataset
    manifest=json.loads((dataset/'manifest.json').read_text())
    records=[c for c in manifest['cards'] if (c['card_id'] in manifest['pilot_ids'] if a.pilot else c['split']==a.split)]
    if any(c['split']=='frozen' for c in records):p.error('construction/development tools cannot score frozen cards')
    if any(c.get('status')!='validated' for c in records):p.error('card has not passed structural validation')
    batch=dataset/'batches'/a.batch_id
    if batch.exists() and not a.resume:p.error('batch already exists; resume or choose another ID')
    batch.mkdir(parents=True,exist_ok=True)
    settings=json.loads((ROOT/'experiments/current/environment.json').read_text())
    agent_hash=tree_manifest(ROOT/settings['agent'])['tree_sha256']
    binding={'dataset_id':a.dataset,'batch_id':a.batch_id,'card_ids':[c['card_id'] for c in records],
             'agent_tree_sha256':agent_hash,'environment_sha256':file_sha256(ROOT/'experiments/current/environment.json'),
             'purpose':'construction pilot' if a.pilot else a.split,
             'llm_enabled':False,'network_calls_authorized':False}
    binding_path=batch/'binding.json'
    if binding_path.exists() and json.loads(binding_path.read_text())!=binding:
        raise ValueError('batch binding changed; choose a new batch ID')
    write_json(binding_path,binding)
    def run(c):
        card=dataset/'cards'/c['card_id']
        if tree_manifest(card)['tree_sha256']!=c['tree_sha256']:raise ValueError('card integrity changed')
        run_id=a.batch_id+'-'+c['card_id']
        run_root=ROOT/settings['runs']/run_id
        if run_root.exists():
            previous=json.loads((run_root/'manifest.json').read_text())
            if previous['source_tree_sha256']!=agent_hash or previous['card_tree_sha256']!=c['tree_sha256']:
                raise ValueError('existing run binding mismatch')
            if previous['status']!='completed':raise ValueError('previous failed run retained; choose a new batch ID')
        else:
            result=subprocess.run([settings['python'],'-B',str(ROOT/'scripts/run_current.py'),
                                   '--run-id',run_id,'--card',str(card)],
                                  env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'},
                                  capture_output=True,text=True,timeout=1100)
            (batch/(c['card_id']+'.runner.log')).write_text(result.stdout+result.stderr)
            if result.returncode:raise ValueError('run failed: '+run_id)
        metrics=json.loads((run_root/'metrics.json').read_text())
        workflow=json.loads((run_root/'output/workflow_result.json').read_text())
        log=(run_root/'output/agent.log').read_text()
        report=json.loads((run_root/'output/score_report.json').read_text())
        record={'card_id':c['card_id'],'run_id':run_id,'metrics_path':str((run_root/'metrics.json').relative_to(ROOT)),
                'termination_reason':workflow['termination_reason'],'total':report['total'],
                'counts':report['counts'],'llm_calls_zero':'llm_calls=0' in log,
                'agent_errors':any(marker in log for marker in ('failed to initialize','planner error',
                    'planner produced an invalid action','error during finish logging')),
                'run_manifest_sha256':file_sha256(run_root/'manifest.json')}
        record['passed']=record['termination_reason']=='survey_complete' and record['llm_calls_zero'] and not record['agent_errors'] and metrics['total'] is not None
        write_json(batch/(c['card_id']+'.json'),record)
        print(json.dumps({'card_id':c['card_id'],'passed':record['passed'],'termination_reason':record['termination_reason']}),flush=True)
        return record
    with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
        results=list(pool.map(run,records))
    write_json(batch/'summary.json',{'binding':binding,'passed':all(r['passed'] for r in results),'results':results,
                                   'scope':'complete offline integration; not strategy selection or online score'})
    return 0 if all(r['passed'] for r in results) else 1
if __name__=='__main__':raise SystemExit(main())
