#!/usr/bin/env python3
"""数据集验收：完整性、家族隔离、配对、复现、拒绝错误输入和运行证据。"""
from __future__ import annotations
import argparse
import csv
import json
import shutil
import subprocess
import sys
import tempfile
from collections import Counter,defaultdict
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments/v4/harness'))
from common import tree_manifest,file_sha256,write_json
SETTINGS=json.loads((ROOT/'experiments/current/environment.json').read_text())
sys.path.insert(0,str(ROOT/SETTINGS['runner']))
from challenge.v4_workflow import V4Workflow

def rows(path):
    with path.open() as handle:return list(csv.DictReader(handle))

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--dataset',default='sim-v1-20261003')
    a=p.parse_args()
    dataset=ROOT/'experiments/current/datasets'/a.dataset
    m=json.loads((dataset/'manifest.json').read_text())
    assert len(m['cards'])==72 and m['status']=='structurally_validated'
    checks={}
    expected={'development':24,'selection':12,'frozen':12,'astronomy_extension':12,'diagnostic':12}
    assert dict(Counter(c['split'] for c in m['cards']))==expected
    groups=defaultdict(set);by_group=defaultdict(list)
    seeds=defaultdict(list)
    for c in m['cards']:
        assert c['status']=='validated'
        card=dataset/'cards'/c['card_id']
        assert tree_manifest(card)['tree_sha256']==c['tree_sha256']
        assert json.loads((dataset/'validation'/c['card_id']/'checks.json').read_text())['passed']
        groups[c['family_id']].add(c['split']);by_group[c['family_id']].append(c)
        spec=dataset/'private/specs'/c['card_id']
        for name in ('v4_catalog_config.json','v4_weather_config.json'):
            cfg=json.loads((spec/name).read_text())
            assert cfg['seed'].bit_length()>64
            seeds[(name,cfg['seed'])].append(c)
        runtime=json.loads((card/'config/v4_scenario.json').read_text())
        assert runtime['name']==c['card_id'] and runtime['task_card']['card_id']==c['card_id']
        assert runtime['limits']['global_wallclock_seconds']==900
    assert all(len(s)==1 for s in groups.values())
    for records in seeds.values():
        assert len(records)==1 or (len(records)==2 and records[0]['series']=='diagnostic'
                                  and records[0]['family_id']==records[1]['family_id'])
    checks['all_72_integrity_and_validation']=True
    checks['family_grouping_and_independent_random_streams']=True
    recipe=json.loads((ROOT/'experiments/current/dataset_recipe_v1.json').read_text())
    for index,pair in enumerate(recipe['diagnostic']['pairs'],1):
        records=by_group[f'pair-{index:02d}']
        cards=[dataset/'cards'/r['card_id'] for r in records]
        for filename in ('public/footprint.csv','public/v4_night_calendar.csv',
                         'config/v4_fiber_config.json','config/v4_score_config.json'):
            assert (cards[0]/filename).read_bytes()==(cards[1]/filename).read_bytes()
        first,second=[rows(card/'public/targets.csv') for card in cards]
        if pair['axis']=='flux_scale':
            ratio=pair['values'][1]/pair['values'][0]
            for x,y in zip(first,second):
                assert {k:v for k,v in x.items() if k!='feature_flux'}=={k:v for k,v in y.items() if k!='feature_flux'}
                assert abs(float(x['feature_flux'])*ratio-float(y['feature_flux']))<2e-8
        else: assert first==second
    checks['six_pairs_keep_sky_dates_and_unrelated_catalog_fields']=True
    private=dataset/'private'
    assert (private.stat().st_mode & 0o777)==0o700
    assert all((p.stat().st_mode & 0o077)==0 for p in (private/'specs').rglob('*.json'))
    checks['private_specs_mode_700_600_not_same_user_sandbox']=True
    with tempfile.TemporaryDirectory(prefix='survey-acceptance-') as temp:
        tmp=Path(temp)
        command=('import sys; from pathlib import Path; sys.path.insert(0,sys.argv[1]); '
                 'from challenge.v4_bundle import build_spec_bundle; '
                 'build_spec_bundle(Path(sys.argv[3]),Path(sys.argv[2]))')
        result=subprocess.run([sys.executable,'-B','-c',command,
            str(ROOT/recipe['generator']),str(private/'specs/SIM0001'),str(tmp/'replica')],
            capture_output=True,text=True,env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'},timeout=120)
        assert result.returncode==0,'reproduction failed (private details suppressed)'
        assert tree_manifest(tmp/'replica')['tree_sha256']==tree_manifest(dataset/'cards/SIM0001')['tree_sha256']
        checks['same_spec_reproduces_entire_card_byte_for_byte']=True
        # Official loader must reject missing and escaping products; use fresh throwaway copies.
        for case in ('missing','outside'):
            bad=tmp/case;shutil.copytree(tmp/'replica',bad)
            config_path=bad/'config/v4_scenario.json'
            cfg=json.loads(config_path.read_text())
            cfg['products']['targets_csv']='../public/missing.csv' if case=='missing' else str(dataset/'cards/SIM0001/public/targets.csv')
            config_path.chmod(0o644);config_path.write_text(json.dumps(cfg))
            try:V4Workflow(bad)
            except ValueError:pass
            else:raise AssertionError('official loader accepted bad product path')
        checks['official_loader_rejects_missing_and_outside_products']=True
        # Tools must refuse an existing dataset and a frozen scoring request.
        for command in ([sys.executable,'-B',str(ROOT/'scripts/build_simulation_dataset.py'),'--pilot-only'],
                        [sys.executable,'-B',str(ROOT/'scripts/run_simulation_dataset.py'),
                         '--dataset',a.dataset,'--batch-id','should-refuse-frozen','--split','frozen']):
            result=subprocess.run(command,capture_output=True,text=True,timeout=30)
            assert result.returncode!=0
        assert not (dataset/'batches/should-refuse-frozen').exists()
        checks['existing_dataset_and_frozen_scoring_refused']=True
    pilot=json.loads((dataset/'batches/dataset-v1-pilot/summary.json').read_text())
    assert pilot['passed'] and len(pilot['results'])==6
    for result in pilot['results']:
        run=ROOT/SETTINGS['runs']/result['run_id']
        run_manifest=json.loads((run/'manifest.json').read_text())
        process=subprocess.run(['/bin/ps','-p',str(run_manifest['runner_pid']),'-o','command='],
                               capture_output=True,text=True)
        assert str(run) not in process.stdout,'owned runner process is still alive'
        log=(run/'output/agent.log').read_text()
        assert 'llm_calls=0' in log
        assert not any(s in log for s in ('failed to initialize','planner error',
                          'planner produced an invalid action','error during finish logging'))
        assert result['termination_reason']=='survey_complete'
    checks['six_offline_complete_runs_no_llm_or_agent_errors']=True
    checks['owned_runner_processes_exited']=True
    frozen_paths={str((dataset/'cards'/c['card_id']).resolve()) for c in m['cards'] if c['split']=='frozen'}
    for path in (ROOT/SETTINGS['runs']).glob('*/manifest.json'):
        run=json.loads(path.read_text())
        assert run.get('card_source') not in frozen_paths,'frozen card was scored'
    checks['frozen_cards_have_no_registered_candidate_runs']=True
    result={'schema_version':'survey-dataset-acceptance-v1','passed':True,'checks':checks,
            'split_counts':expected,'dataset_manifest_sha256':file_sha256(dataset/'manifest.json'),
            'upstream_commit':m['upstream_commit'],'acceptance_script_sha256':file_sha256(Path(__file__)),
            'scope':'72 structural checks and six non-frozen complete runs; no online scoring or OS-enforced blind test'}
    write_json(dataset/'acceptance.json',result)
    print(json.dumps({'dataset_id':a.dataset,'passed':True,'checks':len(checks),'split_counts':expected}))
    return 0
if __name__=='__main__':raise SystemExit(main())
