"""Constructed public protocol inputs only; every test blocks outgoing sockets."""
import io
import importlib.util
import json
import math
import os
from pathlib import Path
import socket
import sys
import unittest
import urllib.error
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'experiments/current/agent'))
from agent_core.llm_client import LLMClient
from agent_core.planner import Planner
from agent_core.state import FaultEvidence, SurveyState
from agent_core.geometry import local_sidereal_deg, parse_utc
from agent_core.validation import validate_action


class Clock:
    def __init__(self):
        self.now = 100.0

    def __call__(self):
        return self.now

    def advance(self, seconds):
        self.now += seconds


class Transport:
    """Scripted elapsed time and HTTP body/error; never creates a socket."""
    def __init__(self, clock, replies):
        self.clock = clock
        self.replies = iter(replies)
        self.timeouts = []
        self.bodies = []

    def __call__(self, request, timeout):
        self.timeouts.append(timeout)
        self.bodies.append(json.loads(request.data))
        elapsed, reply = next(self.replies)
        self.clock.advance(elapsed)
        if isinstance(reply, Exception):
            raise reply
        if isinstance(reply, bytes):
            return io.BytesIO(reply)
        body = {'choices': [{'message': {'content': reply}}]}
        return io.BytesIO(json.dumps(body).encode())


class Answers:
    def __init__(self, answers):
        self.answers = iter(answers)
        self.calls = []

    def ask_json(self, prompt, payload, remaining):
        self.calls.append((prompt, payload, remaining))
        return next(self.answers)


def public_state(with_target=False):
    payload = {
        'site': {'latitude_deg': 35.0, 'longitude_deg': 105.0},
        'survey': {'start_utc': '2026-01-01T10:00:00Z',
                   'end_utc': '2026-01-02T20:00:00Z',
                   'nights': [{'observing_start_utc': '2026-01-01T12:00:00Z',
                               'observing_end_utc': '2026-01-01T20:00:00Z'}]},
        'instrument': {'grid_side': 4, 'n_fibers': 16, 'glass_side_deg': .4,
                       'pitch_deg': .5, 'fov_side_deg': 2.},
        'targets': {'columns': [], 'rows': []},
    }
    if with_target:
        ra = local_sidereal_deg(parse_utc('2026-01-01T12:00:00Z'), 105.)
        payload['targets'] = {
            'columns': ['target_id', 'ra_deg', 'dec_deg', 'feature_flux', 'science_weight', 'required'],
            'rows': [['constructed-public-target', ra, 15., .6, 10., True]],
        }
    return SurveyState(payload)


class Boundaries(unittest.TestCase):
    def setUp(self):
        self.clock = Clock()
        for context in (
            patch.dict(os.environ, {'USE_LLM': '1', 'OPENAI_API_KEY': 'fake-local-test'}, clear=True),
            patch('agent_core.llm_client.time.monotonic', self.clock),
            patch.object(socket.socket, 'connect', side_effect=AssertionError('network forbidden')),
            patch.object(socket.socket, 'connect_ex', side_effect=AssertionError('network forbidden')),
            patch('socket.create_connection', side_effect=AssertionError('network forbidden')),
        ):
            context.start()
            self.addCleanup(context.stop)

    def planner(self, replies):
        p = Planner(public_state())
        p.llm = Answers(replies)
        return p

    def night(self, p, seconds=900):
        p._night_advice(p.state.nights[0][0], {'wallclock': {'remaining_seconds': seconds}})

    def report(self, p, reply):
        p.llm = Answers([reply])
        p.suspicion_hours = [0.0, 6.0]
        p.state.fault_evidence = lambda: FaultEvidence(.4, 1., .4, 20, 2, 20, 8, 8)
        return p._maybe_report(12.0, {'wallclock': {'remaining_seconds': 900}})

    def ask(self, replies, remaining=900, **options):
        transport = Transport(self.clock, replies)
        client = LLMClient(**options)
        with patch('urllib.request.urlopen', transport):
            result = client.ask_json('test prompt', {'public': True}, remaining)
        return result, client, transport

    def test_normal_night_merges_and_consumes_public_inputs(self):
        p = self.planner([{'avoid_directions': ['ne'], 'duration_scale': 1.2},
                          {'avoid_directions': ['S'], 'duration_scale': .8}])
        p._last_forecast_notices = [{'nights': ['2026-01-01'], 'direction': 'NE'},
                                   {'nights': ['2026-01-02'], 'direction': 'W'}]
        p.total_hit, p.total_assigned = 3, 4
        self.night(p)
        self.assertEqual(p.state.extra_avoid, {'NE', 'S'})
        self.assertAlmostEqual(p.state.duration_scale, 1.)
        self.assertEqual(p.llm.calls[0][1]['forecast_notices_for_tonight'], p._last_forecast_notices[:1])
        self.assertEqual(p.llm.calls[1][1]['hit_rate_so_far'], .75)
        self.assertLess(p._direction_factor(40, 45), 1.)

    def test_bad_direction_containers_do_not_crash_or_coerce(self):
        for bad in (3, True, 'NE', {'N': True}, None):
            with self.subTest(bad=bad):
                p = self.planner([{'avoid_directions': bad}, None])
                self.night(p)
                self.assertEqual(p.state.extra_avoid, set())
                self.assertEqual(p.state.duration_scale, 1.)

    def test_bad_direction_elements_are_ignored(self):
        p = self.planner([{'avoid_directions': ['ne', [], {}, None, 1, True, 'bad']}, None])
        self.night(p)
        self.assertEqual(p.state.extra_avoid, {'NE'})

    def test_non_dict_suggestions_fall_back(self):
        for bad in ([1], 'N', 2, True):
            with self.subTest(bad=bad):
                p = self.planner([bad, None])
                self.night(p)
                self.assertEqual(p.state.extra_avoid, set())
                self.assertEqual(p.state.duration_scale, 1.)

    def test_bad_scales_do_not_dilute_valid_peer(self):
        for bad in (float('nan'), float('inf'), -float('inf'), True, '1.2', None,
                    [], {}, 10 ** 400):
            with self.subTest(bad=repr(bad)):
                p = self.planner([{'duration_scale': bad}, {'duration_scale': 1.2}])
                self.night(p)
                self.assertAlmostEqual(p.state.duration_scale, 1.2)
                self.assertTrue(math.isfinite(p.state.duration_scale))

    def test_finite_scales_keep_existing_clamps(self):
        for value, expected in ((-10, .7), (2, 1.4), (1.3, 1.3)):
            p = self.planner([{'duration_scale': value}, None])
            self.night(p)
            self.assertEqual(p.state.duration_scale, expected)

    def test_empty_and_unavailable_suggestions_reset_night_defaults(self):
        p = self.planner([{}, None])
        p.state.extra_avoid, p.state.duration_scale = {'N'}, 1.3
        self.night(p)
        self.assertEqual(p.state.extra_avoid, set())
        self.assertEqual(p.state.duration_scale, 1.)

    def test_report_boolean_verdict_and_illegal_verdict_fallback(self):
        for reply in ({'report': True}, {'report': False}, None, {}, {'report': 'false'},
                      {'report': 0}, {'report': []}, {'report': float('nan')}, ['report']):
            with self.subTest(reply=reply):
                p = self.planner([])
                result = self.report(p, reply)
                if reply == {'report': False} and isinstance(reply.get('report'), bool):
                    self.assertIsNone(result)
                    self.assertEqual(p.reports, 0)
                else:
                    result = validate_action(result, p.state)
                    self.assertEqual(result['action'], 'report')
                    self.assertEqual(result['decision_source'], 'llm-confirmed' if reply == {'report': True} else 'rule')

    def test_report_trigger_requires_repeated_spaced_public_evidence(self):
        p = self.planner([{'report': True}])
        p.state.fault_evidence = lambda: FaultEvidence(.4, 1., .4, 20, 2, 20, 8, 8)
        payload = {'wallclock': {'remaining_seconds': 900}}
        for hours in (0., 2., 6., 8.):
            self.assertIsNone(p._maybe_report(hours, payload))
        self.assertEqual(len(p.llm.calls), 0)
        self.assertEqual(p._maybe_report(12., payload)['action'], 'report')
        self.assertEqual(len(p.llm.calls), 1)
        self.assertIsNone(p._maybe_report(13., payload))

    def test_normal_http_object_and_markdown_wrapper(self):
        for reply in ('{"duration_scale": 1.2}', '```json\n{"duration_scale": 1.2}\n```'):
            result, client, t = self.ask([(1., reply)])
            self.assertEqual(result, {'duration_scale': 1.2})
            self.assertEqual(client.calls_made, 1)
            self.assertEqual(client.spent_seconds, 1.)
            self.assertEqual(t.bodies[0]['messages'][1]['content'], '{"public": true}')

    def test_nonfinite_json_constants_and_overflow_rejected(self):
        for value in ('NaN', 'Infinity', '-Infinity', '1e400', '-1e400'):
            with self.subTest(value=value):
                result, client, _ = self.ask([(0., '{"duration_scale": ' + value + '}')], max_retries=1)
                self.assertIsNone(result)
                self.assertEqual(client.calls_made, 1)

    def test_illegal_http_content_and_envelopes_fall_back(self):
        for reply in ('not json', '{oops}', '[{"report": true}]', 'null', [], {}, 2,
                      b'{}', b'{"choices": []}', b'{"choices": null}'):
            with self.subTest(reply=reply):
                result, _, _ = self.ask([(0., reply)], max_retries=1)
                self.assertIsNone(result)

    def test_errors_and_timeouts_recover_then_use_rules(self):
        result, client, t = self.ask([(2., urllib.error.URLError('fake')), (2., TimeoutError()),
                                     (1., '{"report": true}')])
        self.assertEqual(result, {'report': True})
        self.assertEqual(client.calls_made, 3)
        self.assertEqual(client.spent_seconds, 5.)
        self.assertEqual(t.timeouts, [12., 12., 12.])
        result, client, _ = self.ask([(1., TimeoutError())] * 3)
        self.assertIsNone(result)
        self.assertEqual(client.calls_made, 3)

    def test_retry_deducts_wallclock_elapsed(self):
        result, client, t = self.ask([(8., TimeoutError()), (2., '{"report": true}')], remaining=70.)
        self.assertEqual(result, {'report': True})
        self.assertEqual(t.timeouts, [10., 2.])
        self.assertEqual(client.spent_seconds, 10.)

    def test_retry_does_not_start_after_wallclock_reserve(self):
        result, client, t = self.ask([(9., TimeoutError())], remaining=70.)
        self.assertIsNone(result)
        self.assertEqual(t.timeouts, [10.])
        self.assertEqual(client.calls_made, 1)

    def test_total_budget_and_call_cap_apply_across_questions(self):
        transport = Transport(self.clock, [(3., TimeoutError()), (2., '{"report": true}')])
        client = LLMClient(total_budget_seconds=5., max_calls=2)
        with patch('urllib.request.urlopen', transport):
            self.assertEqual(client.ask_json('', {}, 900), {'report': True})
            self.assertIsNone(client.ask_json('', {}, 900))
        self.assertEqual(transport.timeouts, [5., 2.])
        self.assertEqual(client.calls_made, 2)

    def test_total_time_budget_alone_stops_new_questions(self):
        transport = Transport(self.clock, [(2., '{"report": true}')])
        client = LLMClient(total_budget_seconds=3., max_calls=100)
        with patch('urllib.request.urlopen', transport):
            self.assertEqual(client.ask_json('', {}, 900), {'report': True})
            self.assertIsNone(client.ask_json('', {}, 900))
        self.assertEqual(client.calls_made, 1)
        self.assertEqual(transport.timeouts, [3.])

    def test_decoder_recursion_error_falls_back(self):
        # Parser nesting limits differ across Python versions; inject the failure
        # itself rather than declaring a particular valid JSON depth illegal.
        with patch('agent_core.llm_client._load_json', side_effect=RecursionError('constructed decoder limit')):
            result, _, _ = self.ask([(0., '{}')], max_retries=1)
        self.assertIsNone(result)

    def test_call_cap_stops_retries(self):
        result, client, t = self.ask([(1., TimeoutError())], max_calls=1)
        self.assertIsNone(result)
        self.assertEqual(client.calls_made, 1)
        self.assertEqual(len(t.timeouts), 1)

    def test_exhausted_or_invalid_wallclock_never_opens_transport(self):
        for remaining in (0, -1, 60, 61.49, float('nan'), float('inf'), True, None, '900', 10 ** 400):
            with self.subTest(remaining=repr(remaining)):
                result, client, t = self.ask([], remaining=remaining)
                self.assertIsNone(result)
                self.assertEqual(client.calls_made, 0)
                self.assertEqual(t.timeouts, [])

    def test_late_success_is_not_consumed(self):
        result, client, t = self.ask([(13., '{"report": false}')], remaining=72., max_retries=1)
        self.assertIsNone(result)
        self.assertEqual(client.spent_seconds, 13.)
        self.assertEqual(t.timeouts, [12.])

    def test_nightly_second_question_gets_fresh_remaining_seconds(self):
        p = Planner(public_state())
        transport = Transport(self.clock, [(8., '{}'), (1., '{}')])
        with patch('urllib.request.urlopen', transport):
            self.night(p, 70.)
        self.assertEqual(transport.timeouts, [10., 2.])

    def test_forecast_survives_bulletin_transport_failure(self):
        p = Planner(public_state())
        transport = Transport(self.clock, [(1., '{"avoid_directions":["NE"],"duration_scale":1.2}'),
                                           (1., TimeoutError()), (1., '{oops}'),
                                           (1., urllib.error.URLError('fake'))])
        with patch('urllib.request.urlopen', transport):
            self.night(p)
        self.assertEqual(p.state.extra_avoid, {'NE'})
        self.assertEqual(p.state.duration_scale, 1.2)
        self.assertEqual(p.llm.calls_made, 4)

    def test_report_timeout_uses_legal_rule_action(self):
        p = Planner(public_state())
        p.suspicion_hours = [0., 6.]
        p.state.fault_evidence = lambda: FaultEvidence(.4, 1., .4, 20, 2, 20, 8, 8)
        transport = Transport(self.clock, [(1., TimeoutError())] * 3)
        with patch('urllib.request.urlopen', transport):
            action = validate_action(p._maybe_report(12., {'wallclock': {'remaining_seconds': 900}}), p.state)
        self.assertEqual(action['action'], 'report')
        self.assertEqual(action['decision_source'], 'rule')
        self.assertEqual(p.llm.calls_made, 3)

    def test_same_decision_night_calls_exhaust_report_budget(self):
        p = Planner(public_state())
        p.suspicion_hours = [-10., -4.]
        p.state.fault_evidence = lambda: FaultEvidence(.4, 1., .4, 20, 2, 20, 8, 8)
        transport = Transport(self.clock, [(8., '{}'), (1., '{}')])
        payload = {'now_utc': '2026-01-01T12:00:00Z', 'wallclock': {'remaining_seconds': 70.}}
        with patch('urllib.request.urlopen', transport):
            action = validate_action(p.decide(payload), p.state)
        self.assertEqual(action['action'], 'report')
        self.assertEqual(action['decision_source'], 'rule')
        self.assertEqual(transport.timeouts, [10., 2.])

    def test_cpu_work_before_first_call_is_charged_to_decision(self):
        p = Planner(public_state())
        p.state.on_messages = lambda *args: self.clock.advance(9.)
        transport = Transport(self.clock, [])
        with patch('urllib.request.urlopen', transport):
            action = validate_action(p.decide({'now_utc': '2026-01-01T12:00:00Z',
                                              'wallclock': {'remaining_seconds': 70.}}), p.state)
        self.assertEqual(action['action'], 'wait')
        self.assertEqual(transport.timeouts, [])

    def test_offline_decide_is_legal_and_zero_transport(self):
        with patch.dict(os.environ, {'USE_LLM': '0', 'OPENAI_API_KEY': 'fake-local-test'}, clear=True):
            p = Planner(public_state())
            with patch('urllib.request.urlopen', side_effect=AssertionError('HTTP forbidden')):
                action = validate_action(p.decide({'now_utc': '2026-01-01T12:00:00Z',
                                                  'wallclock': {'remaining_seconds': 900}}), p.state)
        self.assertEqual(action['action'], 'wait')
        self.assertEqual(p.llm.calls_made, 0)
        self.assertEqual(p.state.duration_scale, 1.)

    def test_constructed_offline_trajectory_matches_frozen_baseline(self):
        baseline = ROOT / 'experiments/current/development/round-1/baseline-source/agent_core'
        modules = {}
        for name in ('llm_client', 'planner'):
            spec = importlib.util.spec_from_file_location('agent_core._t2_baseline_' + name, baseline / (name + '.py'))
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)
            modules[name] = module
        modules['planner'].LLMClient = modules['llm_client'].LLMClient
        with patch.dict(os.environ, {'USE_LLM': '0'}, clear=True):
            candidate = Planner(public_state(with_target=True))
            reference = modules['planner'].Planner(public_state(with_target=True))
            kinds = set()
            with patch('urllib.request.urlopen', side_effect=AssertionError('HTTP forbidden')):
                for now in ('2026-01-01T11:00:00Z', '2026-01-01T12:00:00Z',
                            '2026-01-01T12:10:00Z', '2026-01-01T19:59:30Z', '2026-01-02T20:00:00Z'):
                    payload = {'now_utc': now, 'wallclock': {'remaining_seconds': 900}}
                    actual = validate_action(candidate.decide(payload), candidate.state)
                    expected = validate_action(reference.decide(payload), reference.state)
                    self.assertEqual(actual, expected)
                    candidate.note_action(actual)
                    reference.note_action(expected)
                    kinds.add(actual['action'])
            self.assertEqual(kinds, {'wait', 'observe', 'finish'})
            self.assertEqual(candidate.llm.calls_made, 0)
            self.assertEqual(reference.llm.calls_made, 0)


if __name__ == '__main__':
    unittest.main()
