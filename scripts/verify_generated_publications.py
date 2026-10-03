#!/usr/bin/env python3
"""官方生成器独立重推天气、消息和请求；只输出通过/失败。"""
from __future__ import annotations
import argparse,json,sys,tempfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'experiments/current/generator_vendor/149c659'))
from challenge import v4_weather_simulator as weather, v4_observation_requests as requests

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--card',type=Path,required=True);p.add_argument('--spec',type=Path,required=True)
    a=p.parse_args()
    with tempfile.TemporaryDirectory(prefix='survey-check-') as tmp:
        out=Path(tmp)
        weather.generate(a.spec/'v4_weather_config.json',out)
        spec=json.loads((a.spec/'card.json').read_text())
        cat=json.loads((a.spec/'v4_catalog_config.json').read_text())
        score=json.loads((a.spec/'v4_score_config.json').read_text())
        fiber=json.loads((a.spec/'v4_fiber_config.json').read_text())
        request_settings=dict(spec['observation_requests'])
        threshold=score['observation_requests']['completion_factor_threshold']
        request_settings.update(completion_factor_threshold=threshold,
            minimum_feature_flux=threshold*score['flux_zero_point']*score['exposure_zero_point_seconds']/fiber['exposure']['max_duration_seconds'])
        requests.generate_requests(seed=cat['seed'],targets_csv=a.card/'public/targets.csv',
            night_calendar_csv=out/'v4_night_calendar.csv',slots_csv=out/'v4_slots.csv',
            site=cat['site'],minimum_altitude_deg=cat['observability']['minimum_altitude_deg'],
            output_path=out/'v4_observation_requests.jsonl',settings=request_settings,
            flux_zero_point=score['flux_zero_point'],exposure_zero_point_seconds=score['exposure_zero_point_seconds'],
            min_duration_seconds=fiber['exposure']['min_duration_seconds'],max_duration_seconds=fiber['exposure']['max_duration_seconds'])
        for folder in ('public','truth'):
            for path in (a.card/folder).iterdir():
                if path.name in ('targets.csv','footprint.csv'):continue
                assert path.read_bytes()==(out/path.name).read_bytes(),path.name
    return 0
if __name__=='__main__':raise SystemExit(main())
