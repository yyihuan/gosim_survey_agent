#!/usr/bin/env python3
"""按本轮预注册规格生成封存卡；复用官方生成器和已有只读完整性检查。"""
import datetime
import hashlib
import importlib.util
import json
from pathlib import Path
import sys
import time

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent
V4 = ROOT.parents[1]
WORKSPACE = V4.parents[1]
PLAN_PATH = ROOT / 'generated-cards-plan.json'
PLAN = json.loads(PLAN_PATH.read_text())
SOURCE = WORKSPACE / PLAN['source_path']
loader = importlib.util.spec_from_file_location('original_registered_generator', V4 / 'data/generate_registered.py')
original = importlib.util.module_from_spec(loader)
loader.loader.exec_module(original)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def timestamp():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def main():
    paths = sorted((SOURCE / 'challenge').rglob('*.py')) + sorted((SOURCE / 'challenge/reference/v4').glob('*.json'))
    paths += [V4 / 'data/generate_registered.py']
    before = {str(p.relative_to(WORKSPACE)): sha(p) for p in paths}
    assert original.SOURCE == SOURCE
    assert all(json.loads(p.read_text()) == json.loads((V4 / 'vendor/starter_kit_v4/cards/demo/config' / p.name).read_text())
               for p in (SOURCE / 'challenge/reference/v4').glob('*score*.json'))
    record = {'started_at_utc': timestamp(), 'command': [sys.executable, '-B', str(Path(__file__).resolve())],
              'python_version': sys.version, 'plan_sha256': sha(PLAN_PATH), 'source_sha256_before': before,
              'builds': [], 'holdouts_run': False, 'truth_contents_analyzed': False}
    save(ROOT / 'generation-record.json', record)
    cards = []
    for spec in PLAN['specs']:
        assert hashlib.sha256(json.dumps(spec, sort_keys=True, separators=(',', ':')).encode()).hexdigest() == PLAN['spec_sha256'][spec['card_id']]
        started = time.monotonic()
        output = ROOT / 'cards' / spec['card_id']
        original.build_card_bundle(output, spec)
        inventory = original.inspect(output, spec)
        inventory['spec_sha256'] = PLAN['spec_sha256'][spec['card_id']]
        inventory['evaluation_status'] = 'unopened'
        cards.append(inventory)
        save(ROOT / (spec['card_id'] + '-inventory.json'), inventory)
        record['builds'].append({'card_id': spec['card_id'], 'elapsed_seconds': time.monotonic() - started,
                                'result': 'generated_and_complete_bundle_verified'})
        save(ROOT / 'generation-record.json', record)
        print(json.dumps({'card_id': spec['card_id'], 'file_count': inventory['file_count'],
                          'night_count': inventory['public_metadata']['n_nights'],
                          'target_count': inventory['public_metadata']['n_targets'],
                          'bundle_manifest_sha256': inventory['manifest_sha256']}), flush=True)
    after = {str(p.relative_to(WORKSPACE)): sha(p) for p in paths}
    assert before == after
    assert len({c['manifest_sha256'] for c in cards}) == 4
    # 封存包括config/public/truth；只保留文件名与散列，不查看真值内容。
    for card in cards:
        folder = WORKSPACE / card['local_path']
        for path in folder.rglob('*'):
            if path.is_file():
                path.chmod(0o444)
        for path in sorted(folder.rglob('*'), reverse=True):
            if path.is_dir():
                path.chmod(0o555)
        folder.chmod(0o555)
    record.update(finished_at_utc=timestamp(), source_sha256_after=after, sources_unchanged=True, exit_code=0)
    save(ROOT / 'generation-record.json', record)
    save(ROOT / 'inventory.json', {'schema_version': 'v4-extension-card-inventory-v1',
         'status': 'four_complete_bundles_sealed_unopened', 'generated_at_utc': timestamp(),
         'upstream_commit': PLAN['upstream_commit'], 'plan_sha256': sha(PLAN_PATH), 'groups': PLAN['groups'],
         'cards': cards, 'holdouts_run': False, 'truth_contents_analyzed': False,
         'run_gate': 'extension/evaluation/N5_AUTHORIZATION.json must be written after explicit Root freeze'})


if __name__ == '__main__':
    main()
