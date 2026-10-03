import json
import os
from pathlib import Path
import subprocess
import sys
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
        result=subprocess.run(['/usr/bin/python3','-B',str(ROOT/'research/2026-10-03/examples/python/agent.py')],
                              input='',capture_output=True,text=True,env={'PATH':'/usr/bin:/bin'})
        self.assertEqual(result.returncode,1)
        self.assertIn('missing API key',result.stderr)
        self.assertEqual(result.stdout,'')

    def test_duplicate_run_refused(self):
        path=ROOT/'experiments/current/runs/migration-python-L1/manifest.json'
        before=path.read_bytes()
        result=subprocess.run(['/usr/bin/python3','-B',str(ROOT/'scripts/run_current.py'),
                               '--run-id','migration-python-L1'],capture_output=True,text=True)
        self.assertNotEqual(result.returncode,0)
        self.assertEqual(path.read_bytes(),before)

if __name__=='__main__': unittest.main()
