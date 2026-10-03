"""从 R2 C/W 自有 run 的官方指标和标准错误诊断提取机制反馈。"""
import argparse
import json
from pathlib import Path


def extract(run):
    metrics = json.loads((run/'metrics.json').read_text())
    records = []
    errors = []
    for line in (run/'output/agent.log').read_text().splitlines():
        if line.startswith('cw: '):
            records.append(json.loads(line[4:]))
        elif 'baseline: error ' in line:
            errors.append(line)
    plans = len(records)
    candidates = sum(r['candidate_count'] for r in records)
    selected = sum(r['selected_count'] for r in records)
    triggered_c = sum(r['c_boosted_candidates'] > 0 for r in records)
    triggered_w = sum(r['w_penalized_candidates'] > 0 for r in records)
    c_candidates = sum(r['c_boosted_candidates'] for r in records)
    w_candidates = sum(r['w_penalized_candidates'] for r in records)
    c_selected = sum(r['c_boosted_selected'] for r in records)
    w_selected = sum(r['w_penalized_selected'] for r in records)
    return {'run_id': metrics['run_id'], 'plans': plans, 'candidate_evaluations': candidates,
            'selected_assignments': selected, 'baseline_internal_errors': errors,
            'C': {'triggered_plans': triggered_c, 'plan_trigger_rate': triggered_c/plans if plans else None,
                  'boosted_candidate_evaluations': c_candidates,
                  'candidate_trigger_rate': c_candidates/candidates if candidates else None,
                  'boosted_selected_assignments': c_selected,
                  'selected_trigger_rate': c_selected/selected if selected else None,
                  'maximum_multiplier_seen': max((r['c_max_multiplier'] for r in records), default=None)},
            'W': {'triggered_plans': triggered_w, 'plan_trigger_rate': triggered_w/plans if plans else None,
                  'penalized_candidate_evaluations': w_candidates,
                  'candidate_trigger_rate': w_candidates/candidates if candidates else None,
                  'penalized_selected_assignments': w_selected,
                  'selected_trigger_rate': w_selected/selected if selected else None,
                  'plans_with_matching_forecast_directions': sum(bool(r['forecast_directions']) for r in records),
                  'forecast_directions_seen': sorted({d for r in records for d in r['forecast_directions']}),
                  'forecasts_received': max((r['forecasts_received'] for r in records),default=None)},
            'definitions': {'plans': 'planner.plan 调用数；不包含基线先行白昼/关闭等待或 report',
                            'candidate_evaluations': '每次规划 achievable 缓存中唯一候选的计数，跨规划重复计数',
                            'selected': '每个 observe 最终 assignments 的目标数，跨观测重复计数',
                            'forecast_trigger': '已收到且匹配本夜的方向在本次规划命中候选；不是实际天气命中率',
                            'errors': '官方 Agent 异常后回退等待的标准错误记录'}}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('run',type=Path)
    args = parser.parse_args()
    result = extract(args.run)
    (args.run/'mechanism_metrics.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps(result,ensure_ascii=False))


if __name__ == '__main__':
    main()
