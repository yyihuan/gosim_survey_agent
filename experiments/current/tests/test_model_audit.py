"""Constructed public fixtures, injected transport, and explicit socket denial."""
import io
import json
import os
from pathlib import Path
import socket
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'experiments/current/agent'))
from agent_core.llm_client import LLMClient
from agent_core.model_audit import JsonlAuditSink, sanitize
from agent_core.planner import Planner
from agent_core.state import SurveyState, FaultEvidence


def public_state():
    return SurveyState({
        'site': {'latitude_deg': 35., 'longitude_deg': 105.},
        'survey': {'start_utc': '2026-01-01T10:00:00Z', 'end_utc': '2026-01-02T20:00:00Z',
                   'nights': [{'observing_start_utc': '2026-01-01T12:00:00Z',
                               'observing_end_utc': '2026-01-01T20:00:00Z'}]},
        'instrument': {'grid_side': 4, 'n_fibers': 16, 'glass_side_deg': .4,
                       'pitch_deg': .5, 'fov_side_deg': 2.},
        'targets': {'columns': [], 'rows': []}})


class Clock:
    def __init__(self):
        self.now = 100.

    def __call__(self):
        return self.now


class FakeTransport:
    def __init__(self, replies, clock):
        self.replies = iter(replies)
        self.clock = clock
        self.bodies = []

    def __call__(self, request, timeout):
        self.bodies.append(json.loads(request.data))
        elapsed, reply = next(self.replies)
        self.clock.now += elapsed
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, bytes):
            return io.BytesIO(reply)
        if isinstance(reply, str):
            reply = {'choices': [{'message': {'content': reply}}]}
        return io.BytesIO(json.dumps(reply).encode())


class ModelAudit(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        self.events, self.logs = [], []
        for context in (
            patch.dict(os.environ, {'USE_LLM': '1', 'OPENAI_API_KEY': 'fake-local-audit'}, clear=True),
            patch('agent_core.llm_client.time.monotonic', self.clock),
            patch.object(socket.socket, 'connect', side_effect=AssertionError('network forbidden')),
            patch.object(socket.socket, 'connect_ex', side_effect=AssertionError('network forbidden')),
            patch('socket.create_connection', side_effect=AssertionError('network forbidden')),
            patch('urllib.request.urlopen', side_effect=AssertionError('real transport forbidden')),
        ):
            context.start()
            self.addCleanup(context.stop)

    def client(self, replies, **options):
        transport = FakeTransport(replies, self.clock)
        return LLMClient(log=self.logs.append, audit_sink=self.events.append,
                         transport=transport, **options), transport

    def results(self):
        return [e for e in self.events if e['event_type'] == 'model_result']

    def consumption(self):
        return [e for e in self.events if e['event_type'] == 'model_consumption']

    def night(self, replies):
        planner = Planner(public_state())
        planner.llm, transport = self.client([(1., r) for r in replies], max_retries=1)
        planner._night_advice(planner.state.nights[0][0], {'wallclock': {'remaining_seconds': 900}})
        return planner, transport

    def test_actual_prompt_and_wire_body_preserved(self):
        client, transport = self.client([(1., '```json\n{"report": true}\n```')])
        result = client.ask_json('actual prompt', {'public_notice': ['NE']}, 900)
        request, reply = self.events
        self.assertEqual(request['request'], transport.bodies[0])
        self.assertEqual(request['request']['messages'][0]['content'], 'actual prompt')
        self.assertEqual(request['request']['temperature'], 0)
        self.assertEqual(request['request']['max_tokens'], 250)
        self.assertEqual(reply['raw_content'], '```json\n{"report": true}\n```')
        self.assertEqual(reply['parsed'], result)
        self.assertEqual(reply['parse_status'], 'parsed')
        self.assertEqual(reply['request_id'], request['request_id'])
        self.assertEqual(reply['latency_seconds'], 1.)
        self.assertIsNone(reply['usage'])
        self.assertEqual(reply['transport_mode'], 'fake')

    def test_usage_allowlist_and_private_provider_fields_elided(self):
        client, _ = self.client([(1., {'choices': [{'message': {
            'content': '{"report":true}', 'reasoning_content': 'hidden-thought',
            'thinking': 'hidden-thinking'}}], 'usage': {'prompt_tokens': 4, 'completion_tokens': 2,
            'total_tokens': 6, 'reasoning_tokens': 99, 'headers': 'hidden-header'}})])
        client.ask_json('', {}, 900)
        self.assertEqual(self.results()[0]['usage'], {'prompt_tokens': 4, 'completion_tokens': 2, 'total_tokens': 6})
        text = json.dumps(self.events)
        for forbidden in ('hidden-thought', 'hidden-thinking', 'hidden-header', 'reasoning_tokens'):
            self.assertNotIn(forbidden, text)

    def test_invalid_reply_preserves_visible_content_and_retries(self):
        client, _ = self.client([(1., 'broken reply'), (2., '{"report":false}')])
        self.assertEqual(client.ask_json('', {}, 900), {'report': False})
        first, second = self.results()
        self.assertEqual(first['raw_content'], 'broken reply')
        self.assertEqual(first['parse_status'], 'invalid_json')
        self.assertIsNone(first['parsed'])
        self.assertEqual(first['outcome'], 'failed')
        self.assertEqual(first['question_id'], second['question_id'])
        self.assertNotEqual(first['request_id'], second['request_id'])
        self.assertEqual([first['attempt_number'], second['attempt_number']], [1, 2])
        self.assertEqual(second['calls_made'], 2)

    def test_timeout_retry_and_fixed_error_without_exception_text(self):
        client, _ = self.client([(1., TimeoutError('password=do-not-echo')), (1., '{}')])
        self.assertEqual(client.ask_json('', {}, 900), {})
        self.assertEqual(self.results()[0]['error_type'], 'TimeoutError')
        self.assertIsNone(self.results()[0]['raw_content'])
        self.assertNotIn('do-not-echo', json.dumps(self.events) + str(self.logs))

    def test_all_retries_fail_without_secret_error_log(self):
        client, transport = self.client([(1., ValueError('secret=never-echo'))] * 3)
        self.assertIsNone(client.ask_json('', {}, 900))
        self.assertEqual(len(transport.bodies), 3)
        self.assertEqual(len(self.results()), 3)
        self.assertNotIn('never-echo', str(self.logs) + json.dumps(self.events))

    def test_unknown_usage_is_null_not_zero(self):
        client, _ = self.client([(1., {'choices': [{'message': {'content': '{}'}}],
            'usage': {'total_tokens': -1, 'prompt_tokens': True, 'completion_tokens': 'unknown'}})])
        client.ask_json('', {}, 900)
        self.assertIsNone(self.results()[0]['usage'])

    def test_late_parsed_reply_is_failed_and_not_adopted(self):
        client, _ = self.client([(13., '{"report":true}')], max_retries=1)
        self.assertIsNone(client.ask_json('', {}, 900))
        reply = self.results()[0]
        self.assertEqual(reply['parsed'], {'report': True})
        self.assertEqual(reply['parse_status'], 'parsed')
        self.assertEqual(reply['outcome'], 'failed')
        self.assertEqual(reply['error_type'], 'TimeoutError')

    def test_cap_and_time_budget_skip_without_transport(self):
        for options, reason in (({'max_calls': 0}, 'call_cap_reached'),
                                ({'total_budget_seconds': 0}, 'time_budget_exhausted')):
            with self.subTest(reason=reason):
                self.events.clear()
                client, transport = self.client([], **options)
                self.assertIsNone(client.ask_json('', {}, 900))
                self.assertEqual(transport.bodies, [])
                self.assertEqual(self.events[0]['reason'], reason)
                self.assertIsNone(self.events[0]['request_id'])
                self.assertEqual(client.calls_made, 0)

    def test_cap_after_retry_preserves_failed_request_reference(self):
        client, _ = self.client([(1., TimeoutError())], max_calls=1)
        self.assertIsNone(client.ask_json('', {}, 900))
        self.assertEqual(self.events[-1]['reason'], 'call_cap_reached')
        self.assertEqual(self.events[-1]['request_id'], self.results()[0]['request_id'])

    def test_offline_even_with_fake_key_is_zero_requests(self):
        with patch.dict(os.environ, {'USE_LLM': '0', 'OPENAI_API_KEY': 'fake-local-audit'}, clear=True):
            client, transport = self.client([])
            self.assertIsNone(client.ask_json('', {}, 900))
        self.assertEqual(transport.bodies, [])
        self.assertEqual(self.events[0]['transport_mode'], 'offline')
        self.assertEqual(self.events[0]['reason'], 'offline')
        self.assertEqual(client.calls_made, 0)

    def test_default_sink_is_optional(self):
        transport = FakeTransport([(1., '{}')], self.clock)
        client = LLMClient(transport=transport)
        self.assertEqual(client.ask_json('', {}, 900), {})
        self.assertIsNone(client.audit_sink)

    def test_nonfinite_and_invalid_envelopes_are_json_safe(self):
        for reply in ('{"duration_scale":NaN}', '{"duration_scale":1e400}', b'{}',
                      b'{"choices":[]}', b'{"choices":[{"message":{"content":null}}]}'):
            with self.subTest(reply=reply):
                client, _ = self.client([(1., reply)], max_retries=1)
                self.assertIsNone(client.ask_json('', {'public_number': float('inf')}, 900))
                json.dumps(self.events, allow_nan=False)
        self.assertIsNone(sanitize({'x': float('nan')})['x'])

    def test_secret_redaction_for_request_reply_parsed_and_url(self):
        client, _ = self.client([(1., json.dumps({'report': True, 'note': 'fake-local-audit sk-ABC123fake',
            'api_key': 'unrecognized-hidden-value', 'nested': {'password': 'other-secret'},
            'reasoning': 'private-thought'}))])
        client.base_url = 'https://user:url-password@example.invalid/v1?access_token=url-token'
        client.ask_json('fake-local-audit sk-PROMPT-secret',
                        {'public': 'Bearer test-only-token', 'secret': 'hidden-payload'}, 900)
        text = json.dumps(self.events)
        for forbidden in ('fake-local-audit', 'sk-ABC123fake', 'unrecognized-hidden-value',
                          'other-secret', 'private-thought', 'sk-PROMPT-secret',
                          'test-only-token', 'hidden-payload', 'url-password', 'url-token'):
            self.assertNotIn(forbidden, text)
        self.assertNotIn('url-password', client.safe_text(client.base_url))
        self.assertNotIn('url-token', client.safe_text(client.base_url))

    def test_wrapped_json_private_fields_removed_but_ordinary_raw_preserved(self):
        for reply in ('```json\n{"report":true,"thinking":{"text":"hidden-private"},'
                      '"password":"hidden-password"}\n```',
                      'visible prefix {"report":true,"reasoning_content":"hidden-private"} suffix'):
            with self.subTest(reply=reply):
                client, _ = self.client([(1., reply)])
                client.ask_json('', {}, 900)
                text = json.dumps(self.events)
                self.assertNotIn('hidden-private', text)
                self.assertNotIn('hidden-password', text)

    def test_malformed_private_reply_is_redacted_without_guessing_boundaries(self):
        client, _ = self.client([(1., '{"thinking":"private-value", broken')], max_retries=1)
        self.assertIsNone(client.ask_json('', {}, 900))
        self.assertEqual(self.results()[0]['raw_content'], '[REDACTED_PRIVATE_CONTENT]')
        self.assertNotIn('private-value', json.dumps(self.events))

    def test_forbidden_card_fields_never_enter_sink_from_nested_payload(self):
        client, _ = self.client([(1., '{}')])
        client.ask_json('constructed public prompt', {'public': {'notice': 'NE',
            'truth': {'future': 'constructed-forbidden-truth'},
            'nested': {'private_seed': 'constructed-forbidden-seed',
                       'full_hidden_card': {'data': 'constructed-forbidden-card'}}}}, 900)
        text = json.dumps(self.events)
        for value in ('constructed-forbidden-truth', 'constructed-forbidden-seed',
                      'constructed-forbidden-card'):
            self.assertNotIn(value, text)
        self.assertIn('NE', text)

    def test_forbidden_card_fields_never_enter_sink_from_json_wrapped_reply(self):
        for wrapper in (lambda value: json.dumps(value),
                        lambda value: '```json\n' + json.dumps(value) + '\n```',
                        lambda value: json.dumps(json.dumps(value))):
            with self.subTest(wrapper=wrapper):
                self.events.clear()
                forbidden = {'truth': 'constructed-reply-truth',
                             'private_seed': 'constructed-reply-seed',
                             'full hidden card': {'x': 'constructed-reply-card'}}
                reply = wrapper({'report': True, 'nested': forbidden,
                                 'wrapped': json.dumps(forbidden)})
                client, _ = self.client([(1., reply)], max_retries=1)
                client.ask_json('', {}, 900)
                text = json.dumps(self.events)
                for value in ('constructed-reply-truth', 'constructed-reply-seed',
                              'constructed-reply-card'):
                    self.assertNotIn(value, text)

    def test_forbidden_field_names_in_malformed_reply_are_redacted(self):
        client, _ = self.client([(1., '{"truth":"constructed-future", broken')], max_retries=1)
        client.ask_json('', {}, 900)
        self.assertNotIn('constructed-future', json.dumps(self.events))
        self.assertEqual(self.results()[0]['raw_content'], '[REDACTED_PRIVATE_CONTENT]')

    def test_planner_constructor_sink_injection_and_offline_consumption(self):
        with patch.dict(os.environ, {'USE_LLM': '0'}, clear=True):
            transport = FakeTransport([], self.clock)
            planner = Planner(public_state(), model_audit_sink=self.events.append,
                              model_transport=transport)
            planner._night_advice(planner.state.nights[0][0], {'wallclock': {'remaining_seconds': 900}})
        self.assertEqual(transport.bodies, [])
        self.assertEqual([e['outcome'] for e in self.consumption()], ['rule_fallback'] * 2)
        self.assertTrue(all(e['request_id'] is None for e in self.consumption()))

    def test_planner_initial_log_redacts_endpoint_and_model_secrets(self):
        with patch.dict(os.environ, {'USE_LLM': '0', 'OPENAI_API_KEY': 'fake-local-audit',
            'OPENAI_MODEL': 'model-fake-local-audit',
            'OPENAI_BASE_URL': 'https://user:endpoint-secret@example.invalid/v1?key=query-secret'}, clear=True):
            Planner(public_state(), log=self.logs.append)
        for value in ('fake-local-audit', 'endpoint-secret', 'query-secret'):
            self.assertNotIn(value, str(self.logs))

    def test_sink_failure_does_not_trigger_retries_or_echo(self):
        for fail_at, expected_calls in ((1, 0), (2, 1)):
            with self.subTest(fail_at=fail_at):
                count = [0]
                def sink(event):
                    count[0] += 1
                    if count[0] == fail_at:
                        raise ValueError('secret-output-must-not-escape')
                transport = FakeTransport([(1., '{}')], self.clock)
                client = LLMClient(log=self.logs.append, audit_sink=sink, transport=transport)
                self.assertIsNone(client.ask_json('', {}, 900))
                self.assertIsNone(client.ask_json('', {}, 900))
                self.assertEqual(len(transport.bodies), expected_calls)
                self.assertEqual(client.transport_calls_made, expected_calls)
                self.assertTrue(client.audit_failed)
        self.assertNotIn('secret-output-must-not-escape', str(self.logs))

    def test_night_adoption_and_partial_fields_use_correct_request(self):
        planner, _ = self.night(['{"avoid_directions":["NE"],"duration_scale":1.2}',
                                '{"avoid_directions":["S",3],"duration_scale":"bad"}'])
        a, b = self.consumption()
        self.assertEqual([a['outcome'], b['outcome']], ['adopted', 'partially_adopted'])
        self.assertEqual([a['request_id'], b['request_id']], [r['request_id'] for r in self.results()])
        self.assertEqual(planner.state.extra_avoid, {'NE', 'S'})
        self.assertEqual(planner.state.duration_scale, 1.2)

    def test_missing_fields_clamps_and_rejection(self):
        for advice, expected in (({'duration_scale': 1.2}, 'partially_adopted'),
                                 ({'avoid_directions': ['N']}, 'partially_adopted'),
                                 ({'avoid_directions': [], 'duration_scale': 2}, 'partially_adopted'),
                                 ({'avoid_directions': 3, 'duration_scale': 'bad'}, 'rejected'),
                                 ({}, 'rule_fallback')):
            with self.subTest(advice=advice):
                self.events.clear()
                self.night([json.dumps(advice), 'not json'])
                self.assertEqual(self.consumption()[0]['outcome'], expected)
                self.assertEqual(self.consumption()[1]['outcome'], 'rule_fallback')

    def test_fault_verdict_adoption_veto_and_rule_fallback(self):
        for reply, expected in (('{"report":true}', 'adopted'), ('{"report":false}', 'adopted'),
                                ('{"report":true,"extra":1}', 'partially_adopted'),
                                ('{"report":"false"}', 'rejected'), ('broken', 'rule_fallback')):
            with self.subTest(reply=reply):
                self.events.clear()
                planner = Planner(public_state())
                planner.llm, _ = self.client([(1., reply)], max_retries=1)
                planner.suspicion_hours = [0., 6.]
                planner.state.fault_evidence = lambda: FaultEvidence(.4, 1., .4, 20, 2, 20, 8, 8)
                action = planner._maybe_report(12., {'wallclock': {'remaining_seconds': 900}})
                event = self.consumption()[0]
                self.assertEqual(event['outcome'], expected)
                self.assertEqual(event['request_id'], self.results()[0]['request_id'])
                if reply == '{"report":false}':
                    self.assertIsNone(action)
                    self.assertEqual(event['reason'], 'model_veto_applied')
                else:
                    self.assertEqual(action['action'], 'report')

    def test_jsonl_exclusive_append_flush_and_private_fields(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'audit.jsonl'
            with JsonlAuditSink(path) as sink:
                sink({'event_type': 'fixture', 'secret': 'must-not-write', 'x': float('inf')})
                sink({'event_type': 'fixture2'})
                records = [json.loads(line) for line in path.read_text().splitlines()]
                self.assertEqual(len(records), 2)
                self.assertIsNone(records[0]['x'])
                self.assertNotIn('must-not-write', path.read_text())
                self.assertNotEqual(records[0]['event_id'], records[1]['event_id'])
            with self.assertRaises(FileExistsError):
                JsonlAuditSink(path)


if __name__ == '__main__':
    unittest.main()
