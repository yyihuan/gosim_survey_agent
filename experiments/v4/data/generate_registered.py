#!/usr/bin/env python3
"""按主 Agent 预注册 spec 使用未改官方生成器；不执行策略或读取 truth 内容分析。"""
import csv
import datetime
import hashlib
import json
import pathlib
import sys
import time

sys.dont_write_bytecode = True
ROOT = pathlib.Path(__file__).resolve().parent
WORKSPACE = ROOT.parents[2]
PLAN = json.loads((ROOT / 'generated-cards-plan.json').read_text())
SOURCE = WORKSPACE / PLAN['source_path']
sys.path.insert(0, str(SOURCE))
from challenge.v4_bundle import build_card_bundle


def hash_file(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, obj):
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n')


def public_rows(path):
    assert 'truth' not in path.parts
    with path.open() as stream:
        return list(csv.DictReader(stream))


def inspect(root, spec):
    scenario = json.loads((root / 'config/v4_scenario.json').read_text())
    fiber = json.loads((root / 'config/v4_fiber_config.json').read_text())
    score = json.loads((root / 'config/v4_score_config.json').read_text())
    assert scenario['schema_version'] == 'v4-scenario-v1'
    assert fiber['schema_version'] == 'v4-fiber-map-v1'
    assert fiber['field']['n_fibers'] == 16
    assert scenario['limits']['global_wallclock_seconds'] == 900
    assert scenario['stress']['enabled'] == spec['stress']
    assert hash_file(root / 'config/v4_score_config.json') == hash_file(SOURCE / 'challenge/reference/v4/v4_score_config.json')
    products = {key: (root / 'config' / value).resolve() for key, value in scenario['products'].items()}
    if spec['stress']:
        products['stress_events_csv'] = (root / 'config' / scenario['stress']['stress_events_csv']).resolve()
    assert all(p.is_file() and root.resolve() in p.parents for p in products.values())
    files = [{'relative_path': p.relative_to(root).as_posix(), 'bytes': p.stat().st_size,
              'sha256': hash_file(p)} for p in sorted(root.rglob('*')) if p.is_file()]
    assert len(files) == (14 if spec['stress'] else 13)
    targets = public_rows(root / 'public/targets.csv')
    nights = public_rows(root / 'public/v4_night_calendar.csv')
    footprint = public_rows(root / 'public/footprint.csv')
    assert len(targets) == spec['targets']
    assert len(nights) == 14
    manifest = {f['relative_path']: f['sha256'] for f in files}
    return {'card_id': spec['card_id'], 'source_type': 'registered_official_generator',
            'local_path': str(root.relative_to(WORKSPACE)), 'complete_bundle_verified': True,
            'schema_checked': ['public config schema names', 'scenario product path existence',
                               '16 fibers', '900-second budget', 'stress flag', 'public target/night counts',
                               'score config unchanged SHA-256'],
            'file_count': len(files), 'bytes': sum(f['bytes'] for f in files),
            'manifest_sha256': hashlib.sha256(json.dumps(manifest, sort_keys=True).encode()).hexdigest(),
            'public_metadata': {'n_targets': len(targets), 'n_required': sum(r['required']=='true' for r in targets),
                                'n_nights': len(nights), 'first_night': nights[0]['night_date'],
                                'last_night': nights[-1]['night_date'],
                                'n_regions': len({r['component_id'] for r in footprint}),
                                'site': scenario['site'], 'instrument': fiber,
                                'minimum_altitude_deg': scenario['minimum_altitude_deg'],
                                'limits': scenario['limits'], 'stress_enabled': scenario['stress']['enabled'],
                                'area_deg2_spec': spec['area_deg2'], 'score_schema': score.get('schema_version')},
            'files': files}


def main():
    sources = [SOURCE / 'challenge/v4_bundle.py', *sorted((SOURCE / 'challenge/reference/v4').glob('*.json'))]
    before = {str(p.relative_to(WORKSPACE)): hash_file(p) for p in sources}
    cards = []
    evidence = {'started_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                'command': '/usr/bin/python3 experiments/v4/data/generate_registered.py',
                'python_version': sys.version, 'plan_sha256': hash_file(ROOT / 'generated-cards-plan.json'),
                'source_sha256_before': before, 'builds': []}
    save(ROOT / 'generation-record.json', evidence)
    for spec in PLAN['specs']:
        started = time.monotonic()
        out = ROOT / 'cards' / spec['card_id']
        build_card_bundle(out, spec)
        item = inspect(out, spec)
        cards.append(item)
        evidence['builds'].append({'card_id': spec['card_id'], 'elapsed_seconds': time.monotonic()-started,
                                  'result': 'generated_and_schema_inventory_verified'})
        save(ROOT / 'generation-record.json', evidence)
        save(ROOT / (spec['card_id'] + '-inventory.json'), item)
        print('CHECKPOINT', item['card_id'], item['public_metadata']['n_nights'], item['public_metadata']['n_targets'],
              item['manifest_sha256'], flush=True)
    after = {str(p.relative_to(WORKSPACE)): hash_file(p) for p in sources}
    assert before == after, '官方源文件或参考参数改变'
    assert len({c['manifest_sha256'] for c in cards}) == len(cards)
    evidence.update(finished_at_utc=datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    source_sha256_after=after, sources_unchanged=True, exit_code=0)
    save(ROOT / 'generation-record.json', evidence)
    discovery = json.loads((ROOT / 'inventory-public-discovery.json').read_text())
    inventory = {'recorded_at_utc': evidence['finished_at_utc'], 'status': 'ready_registered_local_data',
                 'upstream_commit': PLAN['upstream_commit'], 'groups': PLAN['groups'],
                 'authoritative_plan': 'generated-cards-plan.json', 'truth_policy': 'Generated by official environment; only hashes/inventory, no truth analysis or score run.',
                 'independent_complete_new_bundles_verified': len(cards), 'cards': cards,
                 'existing_demo': discovery['existing_demo'],
                 'official_public_download_status': 'blocked_public_backend; evidence retained in inventory-public-discovery.json and api-snapshots/'}
    save(ROOT / 'inventory.json', inventory)


if __name__ == '__main__':
    main()
