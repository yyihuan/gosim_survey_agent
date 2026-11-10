#!/usr/bin/env python3
"""Replay synthetic protocol messages through the unchanged agent. No dependencies."""
import argparse
import contextlib
import json
import os
from pathlib import Path
import runpy
import subprocess
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / 'examples/offline-demo'


def worker():
    attempts = []

    def blocked(*args, **kwargs):
        attempts.append(True)
        raise RuntimeError('network disabled by offline demo')

    sys.path.insert(0, str(ROOT / 'experiments/current/agent'))
    with contextlib.ExitStack() as stack:
        for target in ('socket.socket.connect', 'socket.socket.connect_ex',
                       'socket.create_connection', 'urllib.request.urlopen'):
            stack.enter_context(patch(target, blocked))
        try:
            runpy.run_path(str(ROOT / 'experiments/current/agent/agent.py'), run_name='__main__')
        finally:
            print('demo_network_attempts=' + str(len(attempts)), file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, help='new directory for replay evidence')
    args = parser.parse_args()
    if args.out and args.out.exists():
        parser.error('--out must name a new directory')
    with tempfile.TemporaryDirectory(prefix='survey-demo-') as sandbox:
        # Do not inherit API keys, endpoint overrides, trace paths or Python hooks.
        env = {'USE_LLM': '0', 'PATH': os.defpath, 'HOME': sandbox,
               'TMPDIR': sandbox, 'LANG': 'C', 'SYSTEMROOT': os.environ.get('SYSTEMROOT', '')}
        completed = subprocess.run(
            [sys.executable, '-I', '-B', str(Path(__file__).resolve()), '--worker'],
            input=(FIXTURE / 'input.jsonl').read_text(), text=True, capture_output=True,
            cwd=sandbox, env=env, timeout=15, check=True)
    responses = [json.loads(line) for line in completed.stdout.splitlines()]
    expected = json.loads((FIXTURE / 'expected.json').read_text())
    if responses != expected:
        raise RuntimeError('Protocol output differs from examples/offline-demo/expected.json')
    if 'demo_network_attempts=0' not in completed.stderr or 'llm_calls=0' not in completed.stderr:
        raise RuntimeError('Missing zero-network / zero-model-call evidence')
    if any(s in completed.stderr for s in ('failed to initialize', 'planner error', 'invalid action')):
        raise RuntimeError('Agent reported an unexpected error')
    report = {'status': 'pass', 'fixture': 'synthetic-public-protocol',
              'actions': [r['action'] for r in responses], 'responses': len(responses),
              'network_attempts': 0, 'llm_calls': 0,
              'scope': 'protocol replay; no official simulator or score'}
    if args.out:
        args.out.mkdir(parents=True, exist_ok=False)
        (args.out / 'responses.jsonl').write_text(completed.stdout)
        (args.out / 'agent.stderr.log').write_text(completed.stderr)
        (args.out / 'report.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    if sys.version_info < (3, 9):
        raise SystemExit('The offline demo requires Python 3.9 or newer.')
    if sys.argv[1:] == ['--worker']:
        worker()
    else:
        main()
