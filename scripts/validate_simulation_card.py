#!/usr/bin/env python3
"""可信数据校验程序；模型只接收公开统计及通过状态，不输出原始隐藏数据。"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SETTINGS = json.loads((ROOT/'experiments/current/environment.json').read_text())
sys.path.insert(0,str(ROOT/SETTINGS['runner']))
from challenge.v4_workflow import V4Workflow
from challenge.tile_geometry_simulator import _local_sidereal_deg, _sun_equatorial_deg


def parse(t): return datetime.fromisoformat(t.replace('Z','+00:00'))
def digest(p): return hashlib.sha256(p.read_bytes()).hexdigest()
def write(p,value): p.write_text(json.dumps(value,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def longest_window(target, nights, site):
    lat,dec=map(math.radians,(site['latitude_deg'],target['dec_deg']))
    c=(math.sin(math.radians(30))-math.sin(lat)*math.sin(dec))/(math.cos(lat)*math.cos(dec))
    if c>=1:return 0.0
    half=180.0 if c<=-1 else math.degrees(math.acos(c))
    longest=0.0
    for night in nights:
        start,end=parse(night['observing_start_utc']),parse(night['observing_end_utc'])
        lst=_local_sidereal_deg(start,site['longitude_deg'])
        lst_end=lst+(end-start).total_seconds()*360.98564736629/86400
        transit=(target['ra_deg']-lst)%360+lst
        for center in (transit-360,transit,transit+360):
            overlap=max(0,min(lst_end,center+half)-max(lst,center-half))
            longest=max(longest,overlap*86400/360.98564736629)
    return longest


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--card',type=Path,required=True)
    parser.add_argument('--spec',type=Path,required=True)
    parser.add_argument('--out',type=Path,required=True)
    args=parser.parse_args(); args.out.mkdir(parents=True,exist_ok=True)
    workflow=V4Workflow(args.card)
    payload=workflow.initialize_payload(900)
    checks={'official_bundle_validation':True}
    baseline=ROOT/SETTINGS['cards']/'L1/config'
    for name in ('v4_fiber_config.json','v4_score_config.json'):
        # JSON semantic equality accepts harmless formatting differences.
        assert json.loads((args.card/'config'/name).read_text())==json.loads((baseline/name).read_text()),name
    checks['instrument_and_scoring_match_official']=True
    config=json.loads((args.spec/'v4_catalog_config.json').read_text())
    targets=[dict(zip(payload['targets']['columns'],row)) for row in payload['targets']['rows']]
    nights=payload['survey']['nights']; slots=workflow.scenario.slots
    assert len(targets)==config['targets']['total_count']
    required=sum(t['required'] for t in targets)
    assert required==round(len(targets)*config['targets']['required_fraction'])
    assert len(payload['footprint'])==3 and all(len(p['vertices'])==40 for p in payload['footprint'])
    assert sum(n['slot_count'] for n in nights)==len(slots)
    assert len(workflow.scenario.bulletins)==len(slots)
    windows=[longest_window(t,nights,payload['site']) for t in targets]
    assert min(windows)>=60, 'target has no legal public-night exposure window'
    checks['catalog_and_public_night_geometry']=True
    for slot,bulletin in zip(slots,workflow.scenario.bulletins):
        assert parse(bulletin['issued_at_utc'])==slot.start_utc
        midpoint=slot.start_utc+(slot.end_utc-slot.start_utc)/2
        ra,dec=_sun_equatorial_deg(midpoint)
        h=math.radians((_local_sidereal_deg(midpoint,payload['site']['longitude_deg'])-ra)%360)
        lat=math.radians(payload['site']['latitude_deg']); d=math.radians(dec)
        altitude=math.degrees(math.asin(math.sin(lat)*math.sin(d)+math.cos(lat)*math.cos(d)*math.cos(h)))
        assert altitude <= -18+0.01
        assert all(n['event_kind'] not in ('instrument_fault','data_loss','pointing_offset') for n in bulletin['notices'])
    for forecast in workflow.scenario.forecasts:
        assert all(n['event_kind'] not in ('earthquake','instrument_fault','data_loss','pointing_offset') for n in forecast['notices'])
    checks['publication_visibility_and_astronomical_nights']=True
    # Request windows and target IDs are checked by the unmodified official loader.
    # Strengthen its per-target oracle with continuous public-night geometry.
    by_id={t['target_id']:t for t in targets}
    requests=workflow.scenario.observation_requests
    for request in requests:
        selected_nights=[n for n in nights if parse(n['observing_start_utc'])>=request['issued_at_utc']
                        and parse(n['observing_end_utc'])<=request['deadline_utc']]
        reachable=0
        for target_id in request['target_ids']:
            t=by_id[target_id]
            need=max(60,request['completion_factor_threshold']*payload['scoring']['flux_zero_point']
                     *payload['scoring']['exposure_zero_point_seconds']/t['feature_flux'])
            reachable += need<=3600 and longest_window(t,selected_nights,payload['site'])+0.1>=need
        assert reachable>=request['minimum_completed']
    checks['request_ideal_geometry_not_weather_feasibility']=True
    summary={'card_id':payload['task_card']['card_id'],'targets':len(targets),'required':required,
             'nights':len(nights),'observing_hours':len(slots)/4,
             'class_counts':dict(Counter(t['target_class'] for t in targets)),
             'longest_window_seconds_min':round(min(windows),1),
             'instrument_and_scoring_match_official':True}
    # Full publication/truth consistency is verified in a separate generator process.
    vendor=ROOT/'experiments/current/generator_vendor/149c659'
    import subprocess
    result=subprocess.run([sys.executable,'-B',str(ROOT/'scripts/verify_generated_publications.py'),
                           '--card',str(args.card),'--spec',str(args.spec)],
                          capture_output=True,text=True,timeout=120)
    if result.returncode: raise ValueError('generated publications/truth disagree; '+result.stderr[-500:])
    checks['rederived_weather_events_publications_and_requests']=True
    write(args.out/'public_summary.json',summary)
    write(args.out/'checks.json',{'passed':True,'checks':checks,'scope':'structural/geometry validation; no candidate score',
                               'upstream_commit':SETTINGS['upstream_commit'],'validator_sha256':digest(Path(__file__))})
    return 0


if __name__=='__main__':raise SystemExit(main())
