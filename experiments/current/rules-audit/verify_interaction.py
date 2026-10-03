#!/usr/bin/env python3
"""从公开协议驱动未修改官方引擎，核对时间边界与账本规则。"""
from __future__ import annotations
import csv,json,sys,unittest
from datetime import datetime,timedelta,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[3]
SETTINGS=json.loads((ROOT/'experiments/current/environment.json').read_text())
RUNNER=ROOT/SETTINGS['runner']
sys.path.insert(0,str(RUNNER))
from challenge.v4_workflow import V4Workflow
from challenge.v4_scorer import BestLedger, observation_request_status
OUT=Path(__file__).resolve().parent/'evidence'

class RulesEvidence(unittest.TestCase):
    def run_case(self,name,actions):
        initial={};requests=[]
        workflow=V4Workflow(ROOT/SETTINGS['cards']/'L1')
        def initialize(payload): initial.update(payload)
        def decide(message,deadline):
            requests.append(message)
            action=actions(initial,message,len(requests))
            return {'protocol_version':'participant-agent-protocol-v4','message_type':'decision_response',
                    'decision_sequence':message['decision_sequence'],**action}
        out=OUT/name
        out.mkdir(parents=True,exist_ok=False)
        result=workflow.run(decide,out,initialize=initialize)
        (out/'public_requests.json').write_text(json.dumps(requests,ensure_ascii=False,indent=2)+'\n')
        return result, requests, initial

    def test_cross_slot_has_one_response_then_delayed_bulletins(self):
        def actions(initial,msg,n):
            if n==1:return {'action':'wait','duration_seconds':450}
            if n==2:return {'action':'observe','pointing':{'alt_deg':60,'az_deg':0},'assignments':{},'duration_seconds':1800}
            return {'action':'finish'}
        result,requests,_=self.run_case('cross-slot',actions)
        a=datetime.fromisoformat(requests[1]['payload']['now_utc'].replace('Z','+00:00'))
        b=datetime.fromisoformat(requests[2]['payload']['now_utc'].replace('Z','+00:00'))
        self.assertEqual((b-a).total_seconds(),1800)
        self.assertEqual(result['decision_requests'],3)
        self.assertEqual(requests[2]['payload']['last_result']['action'],'observe')
        bullets=[m for m in requests[2]['payload']['new_messages'] if m['record_type']=='bulletin']
        self.assertEqual(len(bullets),2)
        self.assertEqual(requests[2]['payload']['latest_bulletin'],bullets[-1])

    def test_night_end_truncates_to_less_than_minimum_requested(self):
        def actions(initial,msg,n):
            if n==1:
                end=datetime.fromisoformat(initial['survey']['nights'][0]['observing_end_utc'].replace('Z','+00:00'))
                return {'action':'wait','until_utc':(end-timedelta(seconds=30)).isoformat().replace('+00:00','Z')}
            if n==2:return {'action':'observe','pointing':{'alt_deg':60,'az_deg':0},'assignments':{},'duration_seconds':60}
            return {'action':'finish'}
        result,requests,initial=self.run_case('night-end',actions)
        self.assertEqual(requests[2]['payload']['now_utc'],initial['survey']['nights'][0]['observing_end_utc'])
        rows=list(csv.DictReader((OUT/'night-end/decisions.csv').open()))
        observe=[r for r in rows if r['action']=='observe'][0]
        self.assertEqual(int(observe['duration_seconds']),30)
        self.assertGreater(len(rows),result['decision_requests'])
        self.assertEqual(result['termination_reason'],'agent_finished')

    def test_report_same_simulated_time_and_33rd_rejected(self):
        result,requests,_=self.run_case('report-limit',lambda i,m,n:{'action':'report'})
        self.assertEqual(result['termination_reason'],'agent_error')
        self.assertEqual(len(requests),33)
        self.assertEqual(len({m['payload']['now_utc'] for m in requests}),1)
        self.assertEqual(requests[1]['payload']['last_result']['action'],'report')
        self.assertTrue(any(m['record_type']=='report_result' for m in requests[1]['payload']['new_messages']))
        report=result['score_report']
        self.assertEqual(report['counts']['decisions'],32)
        self.assertEqual(report['components']['report_settlement'],-4500)

    def test_best_factor_request_window_and_invalidation(self):
        t=datetime(2026,1,1,tzinfo=timezone.utc);ledger=BestLedger()
        ledger.record(0,'A',.8,1.632,t-timedelta(seconds=1),t+timedelta(seconds=100))
        ledger.record(1,'A',.9,1.53,t,t+timedelta(seconds=200))
        self.assertEqual(ledger.best()['A'],(.8,1.632))
        self.assertEqual(ledger.max_factors()['A'],.9)
        request={'request_id':'R','issued_at_utc':t,'deadline_utc':t+timedelta(seconds=200),
            'target_ids':['A'],'minimum_completed':1,'completion_factor_threshold':.5,'completion_reward':100}
        self.assertEqual(observation_request_status(request,ledger)['reward'],100)
        ledger.invalidate_window(1,2,'loss')
        self.assertEqual(observation_request_status(request,ledger)['reward'],0)
        self.assertEqual(ledger.max_factors()['A'],.8)
        ledger.record(2,'B',.3,.3,t,t+timedelta(seconds=100))
        ledger.record(3,'B',.3,.3,t,t+timedelta(seconds=100))
        self.assertEqual(ledger.max_factors()['B'],.3)

if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,default=OUT,help='new output directory; existing directory is refused')
    OUT=parser.parse_args().out.resolve()
    OUT.mkdir(parents=True,exist_ok=False)
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(RulesEvidence)
    result=unittest.TextTestRunner(verbosity=2).run(suite)
    import hashlib
    record={'upstream_commit':SETTINGS['upstream_commit'],'tests_run':result.testsRun,'passed':result.wasSuccessful(),
        'failures':len(result.failures),'errors':len(result.errors),'script_sha256':hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'engine_files':{str(p.relative_to(RUNNER)):hashlib.sha256(p.read_bytes()).hexdigest() for p in (RUNNER/'challenge').glob('*.py')},
        'scope':'official engine via public messages; scripted empty assignments test boundaries, not strategy quality; no LLM/network'}
    (OUT/'verification.json').write_text(json.dumps(record,ensure_ascii=False,indent=2)+'\n')
    raise SystemExit(0 if result.wasSuccessful() else 1)
