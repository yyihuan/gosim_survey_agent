"""本切片的低成本边界检查；只使用构造的公开输入。"""
import datetime
import json
import os
import pathlib
import sys
import tempfile
from types import SimpleNamespace

sys.dont_write_bytecode = True
sys.path.insert(0, str(pathlib.Path(__file__).parent / 'source'))
from cw_policy import CWPolicy

date = lambda text: datetime.datetime.fromisoformat(text.replace('Z', '+00:00'))
planner = SimpleNamespace(ra=[0.1, 9.9, 10.1, 359.9], factor=[0.7, 0.7, 0, 0],
                          nights=[(date('2026-10-02T00:00:00Z'), date('2026-10-02T09:00:00Z'))],
                          ids=['A', 'B', 'C', 'D'], index_of={'A':0, 'B':1, 'C':2, 'D':3})
init = {'scoring': {'uniformity': {'ra_band_width_deg':10, 'observed_factor_threshold':0.5}}}


def policy(config):
    path = pathlib.Path(scratch) / 'config.json'
    path.write_text(json.dumps(config))
    os.environ['EXPERIMENT_CONFIG_PATH'] = str(path)
    return CWPolicy(planner, init, lambda message: None)


with tempfile.TemporaryDirectory() as scratch:
    control = policy({'C':{'enabled':False}, 'W':{'enabled':False}})
    control.begin_plan(date('2026-10-02T00:00:00Z'), None, 0)
    assert control.multiplier(2, 40, 315) == 1.0
    c = policy({'C':{'enabled':True,'strength':0.6}, 'W':{'enabled':False}})
    c.begin_plan(date('2026-10-02T00:00:00Z'), None, 0)
    assert c.multiplier(0, 40, 315) == 1.0
    assert abs(c.multiplier(2, 40, 315)-1.2) < 1e-12
    assert c.multiplier(3, 40, 315) == c.multiplier(2, 40, 315)
    assert all(1.0 <= value <= 1.6 for value in c.c_multipliers.values())
    planner.factor[2] = 0.5
    c.begin_plan(date('2026-10-02T00:15:00Z'), None, 0)
    assert c.multiplier(2, 40, 315) == 1.0
    assert c.multiplier(3, 40, 315) > 1.2
    w = policy({'C':{'enabled':False},'W':{'enabled':True,'penalty_fraction':0.2}})
    w.on_messages([{'record_type':'forecast','issued_at_utc':'2026-10-02T00:00:00Z', 'notices':[
        {'event_kind':'haze','direction':'NW','nights':['2026-10-01']},
        {'event_kind':'rain','direction':'ALL','nights':['2026-10-01']},
        {'event_kind':'overcast','direction':'E','nights':['2026-10-02']}]}])
    w.begin_plan(date('2026-10-01T23:59:00Z'), None, 0)
    assert w.forecast_directions == set()
    assert w.multiplier(0, 40, 315) == 1.0
    w.begin_plan(date('2026-10-02T00:00:00Z'), None, 0)
    assert w.forecast_directions == {'NW'}
    assert w.multiplier(0, 40, 315) == 0.8
    assert w.multiplier(0, 75, 315) == 1.0
    assert w.multiplier(0, 40, 90) == 1.0
    w.on_messages([{'record_type':'forecast','issued_at_utc':'2026-10-02T01:00:00Z','notices':[
        {'event_kind':'rain','direction':'ALL','nights':['2026-10-01']}]}])
    w.begin_plan(date('2026-10-02T01:00:00Z'), None, 0)
    assert w.forecast_directions == set()
    assert w.multiplier(0, 40, 315) == 1.0
print(json.dumps({'status':'pass','checks':['control identity','RA wrap and C bounded soft debt',
                                         'factor threshold updates C debt','future forecasts rejected',
                                         'forecast night filtering','W bounded directional penalty',
                                         'ALL does not stop or penalize whole sky','latest forecast supersedes older']}))
