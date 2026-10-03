#!/usr/bin/env python3
"""固定官方生成器构建离线数据；私有配置不输出到模型日志。"""
from __future__ import annotations

import argparse
import copy
import csv
import fcntl
import hashlib
import json
import os
import secrets
import subprocess
import sys
import time
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'experiments/v4/harness'))
from common import file_sha256, tree_manifest, write_json


def verify_vendor(recipe):
    vendor = ROOT / recipe['generator']
    manifest = json.loads((vendor / 'snapshot_manifest.json').read_text())
    if manifest['upstream_commit'] != recipe['upstream_commit']:
        raise ValueError('generator commit mismatch')
    for item in manifest['files']:
        if file_sha256(vendor / item['path']) != item['sha256']:
            raise ValueError('pinned generator changed: ' + item['path'])
    return vendor


def family_entries(recipe):
    result = []
    for series in ('main', 'extension'):
        group = recipe[series]
        for index, family in enumerate(group['families']):
            for replica in range(group['replicates_per_family']):
                result.append({'series': series, 'family_id': f'{series}-{index+1:02d}',
                               'split': family.get('split', group.get('split')),
                               'profile': family, 'replica': replica})
    for index, pair in enumerate(recipe['diagnostic']['pairs']):
        for member, value in enumerate(pair['values']):
            result.append({'series': 'diagnostic', 'family_id': f'pair-{index+1:02d}',
                           'split': 'diagnostic', 'profile': pair,
                           'replica': member, 'axis_value': value})
    for index, entry in enumerate(result, 1):
        entry['card_id'] = f'SIM{index:04d}'
    return result


def assert_grouped(entries):
    groups = {}
    for entry in entries:
        groups.setdefault(entry['family_id'], set()).add(entry['split'])
    if any(len(splits) != 1 for splits in groups.values()):
        raise ValueError('family crosses data split')


def make_spec(recipe, entry, streams):
    from challenge import v4_weather_simulator as weather_generator
    from challenge.tile_geometry_simulator import _local_sidereal_deg
    reference = ROOT / recipe['generator'] / 'challenge/reference/v4'
    def load(name):
        return json.loads((reference / name).read_text())
    catalog = load('v4_catalog_config.json')
    weather = load('v4_weather_config.json')
    # Current public fibre/score files are the authority; avoid reference defaults drift.
    settings = json.loads((ROOT / 'experiments/current/environment.json').read_text())
    card_root = ROOT / settings['cards'] / 'L1/config'
    fiber = json.loads((card_root / 'v4_fiber_config.json').read_text())
    score = json.loads((card_root / 'v4_score_config.json').read_text())
    profile = entry['profile']
    diag = entry['series'] == 'diagnostic'
    start = date.fromisoformat(recipe['diagnostic']['start'] if diag else profile['start'])
    # Dates vary within a family; paired diagnostics retain identical dates.
    if not diag:
        start += timedelta(days=entry['replica'] * 2)
    n_nights = recipe['diagnostic']['nights'] if diag else profile['nights']
    end = start + timedelta(days=n_nights)
    for cfg in (catalog, weather):
        cfg['site'] = copy.deepcopy(fiber['site'])
        cfg['seed_derivation'] = 'sha256-v1'
    catalog['seed'] = streams['catalog']
    weather['seed'] = streams['weather']
    catalog['observability'].update(start_date=str(start), end_date=str(end),
                                    minimum_altitude_deg=30.0, sun_altitude_limit_deg=-18.0)
    weather['survey'].update(start_date=str(start), end_date=str(end), slot_seconds=900,
                            sun_altitude_limit_deg=-18.0)
    nights, slots = weather_generator.build_nights(weather)
    hours = len(slots) / 4
    target_count = int(round(hours * recipe['main']['targets_per_night_hour'] / 100)) * 100
    midpoint = slots[len(slots)//2].timestamp_utc + timedelta(hours=3)
    central_ra = _local_sidereal_deg(midpoint, fiber['site']['longitude_deg'])
    catalog['footprint'].update(total_area_deg2=target_count / profile.get('density', 5.0),
        n_components=3, vertices_per_component=40,
        component_centers=[[(central_ra-48)%360, -20], [central_ra%360, -48],
                           [(central_ra+48)%360, -18]], component_area_weights=[0.36, 0.34, 0.30])
    catalog['targets'].update(total_count=target_count,
        required_fraction=profile.get('required_fraction', 0.05),
        clustered_fraction=profile.get('clustered_fraction', 0.25),
        n_cluster_centers=max(30, round(target_count/60)))
    counts = {'rainy': 2, 'cloudy': 3, 'smoggy': 2, 'cold_wave': 2, 'tornado': 0}
    if profile.get('heavy'):
        counts.update(rainy=3, cloudy=5, smoggy=3, cold_wave=4, tornado=1)
    for kind, count in counts.items():
        weather['weather_events']['conditions'][kind]['count'] = count
    weather['rocket_launch']['count'] = 2
    weather['earthquake']['count'] = 2 if profile.get('heavy') else 1
    weather['instrument_fault']['count'] = 1
    stress = profile.get('stress', False)
    flux_scale = profile.get('flux_scale', 1.0)
    if 'correlation' in profile:
        weather['quality']['night_correlation'] = profile['correlation']
        weather['quality']['slot_correlation'] = profile['correlation']
    if entry['series'] == 'extension':
        weather['quality']['seeing_arcsec']['nominal'] = recipe['extension']['seeing_nominal_arcsec']
        # Rare contest hazards are explicitly absent here; no empirical hazard-rate claim.
        weather['earthquake']['count'] = 0
        weather['rocket_launch']['count'] = 0
        weather['instrument_fault']['count'] = 0
        weather['weather_events']['conditions']['cold_wave']['count'] = 0
        weather['weather_events']['conditions']['smoggy']['count'] = 0
    if diag:
        axis, value = profile['axis'], entry['axis_value']
        if axis == 'flux_scale': flux_scale = value
        elif axis == 'seeing': weather['quality']['seeing_arcsec']['nominal'] = value
        elif axis == 'correlation':
            weather['quality']['night_correlation'] = value
            weather['quality']['slot_correlation'] = value
        elif axis == 'rain_duration': weather['weather_events']['conditions']['rainy']['duration_slots'] = value
        elif axis == 'fault_count': weather['instrument_fault']['count'] = value
        elif axis == 'stress': stress = value
        else: raise ValueError('unsupported diagnostic axis')
    for model in catalog['targets']['models'].values():
        model['flux_median'] *= flux_scale
    weather['stress_tests']['enabled'] = bool(stress)
    weather['stress_tests']['data_loss']['window_max_fraction'] = profile.get('loss_max', 0.05)
    card = {'name': entry['card_id'], 'card_id': entry['card_id'],
            'scenario_slug': entry['card_id'].lower(), 'phase': 'synthetic-offline',
            'stress': bool(stress), 'wallclock_seconds': 900,
            'observation_requests': {'count': profile.get('request_count', 2)}}
    return {'card.json': card, 'v4_catalog_config.json': catalog,
            'v4_weather_config.json': weather, 'v4_fiber_config.json': fiber,
            'v4_score_config.json': score}


def freeze_card(path):
    for child in path.rglob('*'):
        if child.is_file(): child.chmod(0o444)
    # Read-only is an integrity convention, not an OS sandbox for the same user.


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recipe', type=Path, default=ROOT/'experiments/current/dataset_recipe_v1.json')
    parser.add_argument('--pilot-only', action='store_true')
    parser.add_argument('--resume', action='store_true')
    args = parser.parse_args(argv)
    recipe = json.loads(args.recipe.read_text())
    vendor = verify_vendor(recipe)
    sys.path.insert(0, str(vendor))
    from challenge.v4_bundle import build_spec_bundle
    dataset = ROOT / 'experiments/current/datasets' / recipe['dataset_id']
    dataset.mkdir(parents=True, exist_ok=True)
    with (dataset/'build.lock').open('a') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest_path = dataset/'manifest.json'
        if manifest_path.exists() and not args.resume:
            parser.error('dataset exists; use --resume to verify and continue')
        if not manifest_path.exists():
            entries = family_entries(recipe)
            assert_grouped(entries)
            private = dataset/'private'
            private.mkdir(mode=0o700)
            specs = private/'specs'; specs.mkdir(mode=0o700)
            streams_by_family = {}
            records = []
            for entry in entries:
                # Pair members share streams; every other sky/weather draw is independent.
                key = entry['family_id'] if entry['series']=='diagnostic' else entry['card_id']
                streams = streams_by_family.setdefault(key, {'catalog': secrets.randbits(128),
                                                             'weather': secrets.randbits(128)})
                config_dir = specs/entry['card_id']; config_dir.mkdir(mode=0o700)
                for name, config in make_spec(recipe, entry, streams).items():
                    write_json(config_dir/name, config); (config_dir/name).chmod(0o600)
                records.append({k:entry[k] for k in ('card_id','series','family_id','split')})
            write_json(private/'entries.json', entries); (private/'entries.json').chmod(0o600)
            manifest = {'schema_version':'survey-synthetic-dataset-v1', 'dataset_id':recipe['dataset_id'],
                        'upstream_commit':recipe['upstream_commit'], 'recipe_sha256':file_sha256(args.recipe),
                        'generator_manifest_sha256':file_sha256(vendor/'snapshot_manifest.json'),
                        'status':'building', 'cards':records,
                        'access_boundary':'protocol-only research policy; same-user OS isolation not implemented',
                        'freeze_policy':'no candidate scoring on frozen cards during construction',
                        'pilot_ids':recipe['pilot_ids']}
            write_json(manifest_path, manifest)
        else:
            manifest = json.loads(manifest_path.read_text())
            if manifest['recipe_sha256'] != file_sha256(args.recipe):
                raise ValueError('recipe changed; create a new dataset version')
            if manifest['generator_manifest_sha256'] != file_sha256(vendor/'snapshot_manifest.json'):
                raise ValueError('generator version changed')
        for record in manifest['cards']:
            if args.pilot_only and record['card_id'] not in recipe['pilot_ids']: continue
            card = dataset/'cards'/record['card_id']
            if record.get('status') == 'validated':
                if tree_manifest(card)['tree_sha256'] != record['tree_sha256']:
                    raise ValueError('immutable card changed: '+record['card_id'])
                continue
            started = time.monotonic()
            if card.exists():
                # Completed generation with interrupted validation can resume; incomplete
                # directories are preserved, never silently replaced with another seed.
                if not (card/'config/v4_scenario.json').exists():
                    raise ValueError('incomplete card retained; inspect before recovery: '+record['card_id'])
            else:
                build_spec_bundle(card, dataset/'private/specs'/record['card_id'])
            validation = dataset/'validation'/record['card_id']
            validation.parent.mkdir(exist_ok=True)
            process = subprocess.run([sys.executable,'-B',str(ROOT/'scripts/validate_simulation_card.py'),
                '--card',str(card),'--spec',str(dataset/'private/specs'/record['card_id']),
                '--out',str(validation)], env={'PATH':'/usr/bin:/bin','LANG':'C.UTF-8'},
                stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=120)
            if process.returncode:
                (dataset/'private'/f'{record["card_id"]}-validation-error.log').write_text(process.stderr)
                record['status']='validation_failed'; write_json(manifest_path,manifest)
                raise ValueError('validation failed; details retained privately: '+record['card_id'])
            summary = json.loads((validation/'public_summary.json').read_text())
            freeze_card(card)
            record.update(status='validated', tree_sha256=tree_manifest(card)['tree_sha256'],
                          target_count=summary['targets'], required_count=summary['required'],
                          nights=summary['nights'], observing_hours=summary['observing_hours'],
                          generation_validation_seconds=round(time.monotonic()-started,3))
            write_json(manifest_path,manifest)
            print(json.dumps({'card_id':record['card_id'],'split':record['split'],'status':'validated',
                              'seconds':record['generation_validation_seconds']}),flush=True)
        manifest['status'] = 'structurally_validated' if all(x.get('status')=='validated' for x in manifest['cards']) else 'pilot_built'
        manifest['builder_sha256'] = file_sha256(Path(__file__))
        manifest['validator_sha256'] = file_sha256(ROOT/'scripts/validate_simulation_card.py')
        write_json(manifest_path, manifest)
        print(json.dumps({'dataset_id':manifest['dataset_id'],'status':manifest['status'],
                          'validated_cards':sum(x.get('status')=='validated' for x in manifest['cards'])}),flush=True)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
