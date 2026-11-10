import json
import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'experiments/current/agent'))
from agent_core.llm_client import LLMClient, MissingAPIKeyError, require_api_key

class OfflineBoundary(unittest.TestCase):
    def test_offline_never_attempts_http_with_inherited_key(self):
        with patch.dict(os.environ,{'USE_LLM':'0','OPENAI_API_KEY':'fake-test-key'},clear=True):
            require_api_key()
            client=LLMClient()
            with patch.object(client,'_attempt',side_effect=AssertionError('unexpected network')):
                self.assertIsNone(client.ask_json('test',{},900))
            self.assertEqual(client.calls_made,0)
            self.assertEqual(client.spent_seconds,0)

    def test_online_still_requires_key(self):
        with patch.dict(os.environ,{},clear=True):
            with self.assertRaises(MissingAPIKeyError): require_api_key()

    def test_upstream_unmodified_fails_without_key(self):
        result=subprocess.run([sys.executable,'-E','-s','-B',str(ROOT/'research/2026-10-03/latest-149c659/examples/python/agent.py')],
                              input='',capture_output=True,text=True,env={'PATH':'/usr/bin:/bin'})
        self.assertEqual(result.returncode,1)
        self.assertIn('missing API key',result.stderr)
        self.assertEqual(result.stdout,'')

    def test_duplicate_run_refused(self):
        spec = importlib.util.spec_from_file_location('demo_test_runner', ROOT/'scripts/run_current.py')
        runner = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(runner)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            settings_dir = root/'experiments/current'
            settings_dir.mkdir(parents=True)
            (root/'cards/L1/config').mkdir(parents=True)
            (root/'cards/L1/config/v4_scenario.json').write_text('{}')
            (root/'examples').mkdir()
            (root/'snapshot.json').write_text(json.dumps({'examples': runner.tree_manifest(root/'examples')}))
            settings = {'agent': str(ROOT/'experiments/current/agent'), 'cards': 'cards',
                        'snapshot_manifest': 'snapshot.json', 'runner': 'unused-runner',
                        'python': sys.executable, 'runs': 'runs'}
            (settings_dir/'environment.json').write_text(json.dumps(settings))
            path = root/'runs/duplicate/manifest.json'
            path.parent.mkdir(parents=True)
            before = b'{"sentinel": "must remain unchanged"}\n'
            path.write_bytes(before)
            with patch.object(runner, 'ROOT', root), patch.object(runner.signal, 'signal'), \
                    patch.object(runner.subprocess, 'Popen', side_effect=AssertionError('must not launch')):
                with self.assertRaises(FileExistsError):
                    runner.main(['--run-id', 'duplicate'])
            self.assertEqual(path.read_bytes(), before)

if __name__=='__main__': unittest.main()
