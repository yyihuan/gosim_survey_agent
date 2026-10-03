#!/usr/bin/env python3
"""读取官方前端已经公开的匿名接口；只收集四张 v4 练习卡和公开练习榜。"""
import base64
import concurrent.futures
import csv
import datetime
import hashlib
import json
import pathlib
import re
import statistics
import urllib.error
import urllib.parse
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parent
UPSTREAM = ROOT.parents[2] / 'research/2026-10-02/upstream'
CARDS = ('alpha', 'beta', 'gamma', 'delta')
PUBLIC_COLUMNS = ('id,slug,name,description,weather_public,forecasts_public,events_public,'
                  'tiles_public,is_active,n_slots,n_nights,n_tiles,n_targets,n_requests,'
                  'global_wallclock_seconds,contract,created_at')
source = (ROOT / 'public-source/supabase-HbgHf8cp.js').read_text()
HOST = next(u for u in re.findall(r'https://[a-z0-9]+\.supabase\.co', source)
            if 'placeholder' not in u)
KEY = re.findall(r'eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+', source)[0]
claims = json.loads(base64.urlsafe_b64decode(KEY.split('.')[1] + '==='))
assert claims.get('role') == 'anon', '只允许公开前端的 anon 权限'
START = datetime.datetime.now(datetime.timezone.utc).isoformat()


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def request(path, payload=None):
    body = json.dumps(payload).encode() if payload is not None else None
    headers = {'apikey': KEY, 'Authorization': 'Bearer ' + KEY}
    if body is not None:
        headers['Content-Type'] = 'application/json'
    req = urllib.request.Request(HOST + path, data=body, headers=headers)
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=25) as response:
                return response.read(), {'url': HOST + path, 'http_status': response.status,
                                         'retrieved_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
        except urllib.error.HTTPError as exc:
            return exc.read(), {'url': HOST + path, 'http_status': exc.code,
                                'retrieved_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat()}
        except Exception:
            if attempt:
                raise


def api_json(name, path, payload=None):
    raw, evidence = request(path, payload)
    data = json.loads(raw)
    save_json(ROOT / 'api-snapshots' / (name + '.json'), {**evidence, 'payload': data})
    if evidence['http_status'] != 200:
        raise RuntimeError(str(evidence))
    return data


def list_folder(pair):
    card, folder = pair
    return card, folder, api_json(card + '-' + folder + '-listing',
                                  '/storage/v1/object/list/scenarios',
                                  {'prefix': 'v4-practice-' + card + '/' + folder,
                                   'limit': 1000, 'offset': 0,
                                   'sortBy': {'column': 'name', 'order': 'asc'}})


def download(item):
    card, key = item
    path = '/storage/v1/object/scenarios/v4-practice-' + card + '/' + key
    raw, evidence = request(path)
    if evidence['http_status'] != 200:
        raise RuntimeError(str(evidence))
    target = ROOT / 'cards' / card / key
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and target.read_bytes() != raw:
        raise RuntimeError('公开文件已改变，拒绝覆盖：' + str(target))
    target.write_bytes(raw)
    return {'card_id': card, 'relative_path': key, 'local_path': str(target.relative_to(ROOT)),
            'bytes': len(raw), 'sha256': hashlib.sha256(raw).hexdigest(), **evidence}


def rows(path):
    # 只允许读取公开 CSV；truth 文件仅下载与计算散列。
    assert 'truth' not in path.parts
    with path.open() as handle:
        return list(csv.DictReader(handle))


def metadata(card, files):
    base = ROOT / 'cards' / card
    configs = {p.stem: json.loads(p.read_text()) for p in (base / 'config').glob('*.json')}
    scenario = configs['v4_scenario']
    fiber = configs['v4_fiber_config']
    targets = rows(base / 'public/targets.csv')
    nights = rows(base / 'public/v4_night_calendar.csv')
    footprint = rows(base / 'public/footprint.csv')
    facts = json.loads((UPSTREAM / 'cards' / ('v4-practice-' + card) / 'card.json').read_text())
    manifest = {f['relative_path']: f['sha256'] for f in files}
    checksum = hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest()
    # 官方 runner 的三个入口配置，以及 public/truth 文件集；不加载 runner/评分器。
    required = {'config/v4_scenario.json', 'config/v4_fiber_config.json', 'config/v4_score_config.json',
                'public/targets.csv', 'public/footprint.csv', 'public/v4_night_calendar.csv',
                'public/v4_bulletins.jsonl', 'public/v4_forecasts.jsonl',
                'truth/v4_weather_truth.csv', 'truth/v4_slots.csv', 'truth/v4_events.csv',
                'truth/v4_earthquake_effects.csv', 'truth/v4_observation_requests.jsonl'}
    return {'card_id': card, 'slug': 'v4-practice-' + card, 'file_count': len(files),
            'bytes': sum(f['bytes'] for f in files), 'manifest_sha256': checksum,
            'official_facts_checksum': facts['checksum'], 'checksum_matches_official': checksum == facts['checksum'],
            'required_files_complete': required.issubset(manifest), 'missing_required': sorted(required-set(manifest)),
            'public_metadata': {'n_targets': len(targets),
                'n_required': sum(r['required'] == 'true' for r in targets), 'n_nights': len(nights),
                'first_night': nights[0]['night_date'], 'last_night': nights[-1]['night_date'],
                'n_regions': len({r['component_id'] for r in footprint}),
                'site': scenario['site'], 'instrument': fiber,
                'minimum_altitude_deg': scenario['minimum_altitude_deg'], 'limits': scenario['limits'],
                'stress_enabled': scenario['stress']['enabled'], 'area_deg2_official_facts': facts['area']},
            'files': files}


def collect_boards():
    competition = api_json('current_competition', '/rest/v1/rpc/current_competition', {})
    select = ('*,observer_settings:observer_phase_settings(projects_enabled,local_sessions_enabled,daily_batches,sealed),'
              'phase_scenarios(scenario_id,scenarios(' + PUBLIC_COLUMNS + '))')
    query = urllib.parse.urlencode({'select': select, 'slug': 'in.(practice,practice-projects)', 'order': 'sort_order.asc'})
    phases = api_json('public-practice-phases', '/rest/v1/phases?' + query)
    boards = []
    for phase in phases:
        settings = phase.get('observer_settings') or {}
        if settings.get('sealed') or phase.get('leaderboard_mode') == 'hidden':
            continue
        scenarios = [link['scenarios'] for link in phase['phase_scenarios'] if link.get('scenarios')]
        if settings.get('projects_enabled') or settings.get('local_sessions_enabled'):
            first = api_json(phase['slug'] + '-card-board', '/rest/v1/rpc/observer_card_board',
                             {'p_phase': phase['id'], 'p_scenario_slug': None, 'p_limit': 500})
            if first.get('layout') in ('cards', 'cards_overall'):
                cards = first.get('cards') or []
                # 仅请求网页公开返回、且在明确四张练习卡白名单中的卡片。
                allowed = {'v4-practice-' + card for card in CARDS}
                entries = [first]
                for card in cards:
                    if card['slug'] in allowed and first.get('scenario') != card['slug']:
                        entries.append(api_json(phase['slug'] + '-' + card['slug'] + '-board',
                                                '/rest/v1/rpc/observer_card_board',
                                                {'p_phase': phase['id'], 'p_scenario_slug': card['slug'], 'p_limit': 500}))
                for entry in entries:
                    boards.append({'phase_slug': phase['slug'], 'version': 'v4' if any(c['slug'] in allowed for c in cards) else 'unknown',
                                   'scope': entry.get('scenario') or 'overall', 'layout': entry.get('layout'),
                                   'rows': entry.get('rows') or [], 'cards': cards})
            else:
                boards.append({'phase_slug': phase['slug'], 'version': 'unknown', 'scope': 'overall',
                               'layout': first.get('layout'), 'rows': first.get('rows') or []})
        else:
            for scenario in sorted(scenarios, key=lambda s: (-int(s.get('n_nights') or 0), s['slug'])):
                entry = api_json(phase['slug'] + '-' + scenario['slug'] + '-board', '/rest/v1/rpc/leaderboard',
                                 {'p_phase_slug': phase['slug'], 'p_limit': 500, 'p_scenario_slug': scenario['slug']})
                boards.append({'phase_slug': phase['slug'], 'version': 'v3', 'scope': scenario['slug'],
                               'layout': 'per_scenario', 'rows': entry})
    for board in boards:
        scores = [float(r['total_score']) for r in board['rows']]
        board['statistics'] = {'n_teams_visible': len(scores), 'median_total_score': statistics.median(scores) if scores else None,
                               'min_total_score': min(scores) if scores else None, 'max_total_score': max(scores) if scores else None,
                               'requested_limit': 500, 'limit_reached': len(scores) >= 500}
    result = {'started_at_utc': START, 'finished_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
              'current_competition': competition, 'phases': phases, 'boards': boards,
              'scope_note': '公开接口；v4每队选择整体均分最高的完整评估，各卡榜使用该同一批次各卡成绩，非逐卡历史最高，也非所有提交的分布。overall为该批次多卡均分。v3每场景榜为每队该场景历史最高。'}
    save_json(ROOT / 'leaderboard.json', result)
    columns = ['version', 'phase_slug', 'scope', 'rank', 'team_id', 'team_name', 'total_score', 'submission_count', 'observer_batch_id', 'scored_at']
    with (ROOT / 'leaderboard.csv').open('w') as handle:
        out = csv.DictWriter(handle, fieldnames=columns); out.writeheader()
        for b in boards:
            for row in b['rows']:
                out.writerow({k: (b.get(k) if k in b else row.get(k)) for k in columns})
    return boards


def main():
    pairs = [(card, folder) for card in CARDS for folder in ('config', 'public', 'truth')]
    listings = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        for card, folder, items in pool.map(list_folder, pairs):
            listings[(card, folder)] = items
    todo = []
    for (card, folder), items in listings.items():
        for item in items:
            if (item.get('id') or item.get('metadata')) and re.fullmatch(r'[A-Za-z0-9_.-]+', item['name']) and '..' not in item['name']:
                todo.append((card, folder + '/' + item['name']))
    with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
        files = list(pool.map(download, todo))
    cards = [metadata(card, [f for f in files if f['card_id'] == card]) for card in CARDS]
    inventory = {'started_at_utc': START, 'finished_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                 'upstream_commit': '18be105bc517938c8341ad79646cf397e3293016',
                 'source_page': 'https://create.gosim.org/survey26/platform/resources',
                 'api_discovered_from': 'public-source/leaderboard-index.html -> public-source/supabase-HbgHf8cp.js',
                 'permission': '公开前端 anon，不使用账号、用户 session 或服务端凭据',
                 'truth_policy': '下载与 SHA-256；不解析或分析 truth 内容', 'cards': cards,
                 'distinct_cards_by_manifest': len({c['manifest_sha256'] for c in cards})}
    save_json(ROOT / 'inventory.json', inventory)
    print('CHECKPOINT cards:', [(c['card_id'], c['file_count'], c['required_files_complete'], c['checksum_matches_official']) for c in cards], flush=True)
    boards = collect_boards()
    print('boards:', [(b['version'], b['scope'], b['statistics']) for b in boards], flush=True)


if __name__ == '__main__':
    main()
