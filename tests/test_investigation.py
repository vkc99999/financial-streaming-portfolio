import json
import os
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from uuid import uuid4

from fastapi import HTTPException
from pydantic import ValidationError
from app.investigation import (Report, ModelFailure, validate_analysis, redact, sanitized,
                              call_model, investigate, get_investigation, database)


def report():
    return Report(request_id=uuid4(), symptom='Invoices stopped arriving',
                  observations=[{'id': 'log1', 'text': 'connection refused'}])


def answer():
    return {'status': 'hypotheses', 'summary': 'Connection failed',
            'likely_causes': [{'explanation': 'The destination may be unavailable',
                              'evidence': [{'observation_id': 'log1', 'quote': 'connection refused'}]}],
            'missing_information': ['Destination status'], 'next_checks': ['Check destination status']}


class InvestigationTests(unittest.TestCase):
    def test_input_limits_and_unique_ids(self):
        for observations in ([], [{'id': 'x', 'text': 'a'}]*2, [{'id': 'x', 'text': 'a'*2001}]):
            with self.assertRaises(ValidationError):
                Report(request_id=uuid4(), symptom='failure', observations=observations)

    def test_citations_must_exist_and_match(self):
        for ident, quote in [('invented', 'connection refused'), ('log1', 'all healthy'), ('log1', '')]:
            data = answer()
            data['likely_causes'][0]['evidence'][0] = {'observation_id': ident, 'quote': quote}
            with self.assertRaises(ValueError):
                validate_analysis(json.dumps(data), sanitized(report()))
        self.assertEqual(validate_analysis(json.dumps(answer()), sanitized(report())), answer())

    def test_insufficient_evidence_has_no_claimed_causes(self):
        data = answer(); data['status'] = 'insufficient_evidence'
        with self.assertRaises(ValueError):
            validate_analysis(json.dumps(data), sanitized(report()))
        data['likely_causes'] = []
        validate_analysis(json.dumps(data), sanitized(report()))

    def test_redaction(self):
        result = redact('password="abc xyz" token=foo Bearer abcdef sk-secret postgresql://user:pass@db')
        for secret in ('abc xyz', 'foo', 'abcdef', 'sk-secret', 'user:pass'):
            self.assertNotIn(secret, result)

    @patch('app.investigation.time.sleep')
    @patch('app.investigation.urllib.request.urlopen')
    def test_transient_retry_and_structured_request(self, urlopen, sleep):
        response = unittest.mock.MagicMock()
        response.__enter__.return_value.read.return_value = json.dumps({
            'status': 'completed', 'output': [{'type': 'message', 'content': [
                {'type': 'output_text', 'text': json.dumps(answer())}]}], 'usage': {'input_tokens': 20}}).encode()
        urlopen.side_effect = [HTTPError('url', 429, 'rate', {}, None), response]
        result, usage, attempts = call_model(sanitized(report()), 'test-model', 'secret')
        self.assertEqual(attempts, 2)
        self.assertEqual(result, answer())
        payload = json.loads(urlopen.call_args.args[0].data)
        self.assertFalse(payload['store'])
        self.assertTrue(payload['text']['format']['strict'])
        self.assertNotIn('tools', payload)

    @patch('app.investigation.urllib.request.urlopen')
    def test_auth_failure_not_retried(self, urlopen):
        urlopen.side_effect = HTTPError('url', 401, 'secret provider body', {}, None)
        with self.assertRaises(ModelFailure) as caught:
            call_model(sanitized(report()), 'test', 'secret')
        self.assertEqual(caught.exception.code, 'provider_rejected')
        self.assertEqual(urlopen.call_count, 1)

    @patch('app.investigation.time.sleep')
    @patch('app.investigation.urllib.request.urlopen', side_effect=TimeoutError)
    def test_timeout_is_bounded(self, urlopen, sleep):
        with self.assertRaises(ModelFailure) as caught:
            call_model(sanitized(report()), 'test', 'secret')
        self.assertEqual(caught.exception.code, 'provider_timeout')
        self.assertEqual(urlopen.call_count, 2)

    @patch('app.investigation.urllib.request.urlopen')
    def test_refusal_and_invalid_json(self, urlopen):
        for content, expected in [([{'type': 'refusal'}], 'model_refusal'),
                                  ([{'type': 'output_text', 'text': '{}'}], 'invalid_output')]:
            urlopen.return_value.__enter__.return_value.read.return_value = json.dumps({
                'status': 'completed', 'output': [{'type': 'message', 'content': content}]}).encode()
            with self.assertRaises(ModelFailure) as caught:
                call_model(sanitized(report()), 'test', 'secret')
            self.assertEqual(caught.exception.code, expected)


@unittest.skipUnless(os.getenv('RUN_INCIDENT_DB_TESTS') == '1', 'Requires dedicated incident test database')
class InvestigationDatabaseTests(unittest.TestCase):
    @patch.dict(os.environ, {'OPENAI_API_KEY': 'fake-test-key', 'OPENAI_MODEL': 'mock-model'})
    @patch('app.investigation.call_model')
    def test_persistence_idempotency_and_conflict(self, model):
        model.return_value = (answer(), {'input_tokens': 20}, 1)
        body = report()
        first = investigate(body)
        self.assertEqual(first['status'], 'completed')
        self.assertEqual(get_investigation(body.request_id)['result'], answer())
        self.assertEqual(investigate(body)['id'], first['id'])
        self.assertEqual(model.call_count, 1)
        body.symptom = 'Different report'
        with self.assertRaises(HTTPException) as caught:
            investigate(body)
        self.assertEqual(caught.exception.status_code, 409)

    @patch.dict(os.environ, {'OPENAI_API_KEY': 'fake', 'OPENAI_MODEL': 'mock-model'})
    @patch('app.investigation.call_model', side_effect=ModelFailure('invalid_output'))
    def test_failure_saved_without_provider_body(self, model):
        body = report(); row = investigate(body)
        self.assertEqual(row['status'], 'failed')
        self.assertEqual(row['error_code'], 'invalid_output')
        self.assertIsNone(row['result'])
        investigate(body)
        self.assertEqual(model.call_count, 1)

    def test_role_cannot_delete_or_create_tables(self):
        import psycopg
        for query in ('DELETE FROM investigation', 'CREATE TABLE forbidden(id int)'):
            with self.assertRaises(psycopg.errors.InsufficientPrivilege), database() as conn:
                conn.execute(query)

@unittest.skipUnless(os.getenv('RUN_INCIDENT_DB_TESTS') == '1', 'Requires dedicated incident test database')
class InvestigationHTTPTests(unittest.TestCase):
    @patch.dict(os.environ, {'API_KEY': 'local-test-key', 'OPENAI_API_KEY': 'fake', 'OPENAI_MODEL': 'mock-model'})
    @patch('app.investigation.call_model')
    def test_http_auth_validation_and_saved_result(self, model):
        import socket
        import threading
        import time
        import urllib.request
        import uvicorn
        from app.investigation import app
        model.return_value = (answer(), {}, 1)
        sock = socket.socket(); sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
        server = uvicorn.Server(uvicorn.Config(app, log_level='critical'))
        thread = threading.Thread(target=server.run, kwargs={'sockets': [sock]}, daemon=True)
        thread.start()
        try:
            for _ in range(100):
                if server.started: break
                time.sleep(0.02)
            self.assertTrue(server.started)
            def request(path, data=None, auth=True):
                headers = {'Content-Type': 'application/json'}
                if auth: headers['X-API-Key'] = 'local-test-key'
                req = urllib.request.Request(f'http://127.0.0.1:{port}'+path,
                    data=json.dumps(data).encode() if data is not None else None, headers=headers)
                with urllib.request.urlopen(req, timeout=5) as response:
                    return json.load(response)
            with self.assertRaises(HTTPError) as caught:
                request('/health', auth=False)
            self.assertEqual(caught.exception.code, 401)
            self.assertEqual(request('/health')['status'], 'ok')
            with self.assertRaises(HTTPError) as caught:
                request('/investigations', {'symptom': 'bad'})
            self.assertEqual(caught.exception.code, 422)
            body = report().model_dump(mode='json')
            row = request('/investigations', body)
            self.assertEqual(row['status'], 'completed')
            self.assertEqual(request('/investigations/'+row['id'])['result'], answer())
        finally:
            server.should_exit = True
            thread.join(5)
            sock.close()
