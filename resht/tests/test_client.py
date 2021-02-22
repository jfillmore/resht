from contextlib import contextmanager
from itertools import product
from unittest.mock import (
    patch,
    MagicMock,
    )
import functools
import unittest

from resht.client import RestClient


class Headers:
    def __init__(self, headers: dict = None):
        self.headers = {}
        if headers:
            for key, val in headers.items():
                self.headers[key.lower()] = val

    def get(self, key, default=None):
        key_lower = key.lower()
        if key_lower in self.headers[key.lower()]:
            return self.headers[key_lower]
        return default

    def items(self):
        return self.headers.items()


class MockResponse:
    def __init__(
            self,
            status_code:int = 200,
            return_body:bytes = b'',
            content_type:str = 'application/json; charset=utf-8',
            headers:dict = None,
        ):
        self.status_code = status_code
        self.return_body = return_body
        self.content_type = content_type
        self.headers = headers or {}
        self.mocks = None  # created for each 'with' block
        self.patches = {
            'urlopen': patch('urllib.request.urlopen'),
            'Request': patch('urllib.request.Request'),
        }

    def __enter__(self):
        self.mocks = {}
        for name, patch in self.patches.items():
            self.mocks[name] = patch.start()
        urlopen_rv = self.mocks['urlopen'].return_value
        urlopen_rv.status = self.status_code
        urlopen_rv.body = MagicMock(return_value=self.return_body)
        urlopen_rv.headers = Headers({
            'content-type': self.content_type,
            })
        return self

    @staticmethod
    def _desc(val):
        str_val = str(val)
        if len(str_val) > 80:
            return str_val[0:32] + '...' + str_val[:32]
        return str_val

    def call_args_error(self, mock_name:str, args:dict = None):
        """
        For the patch given, ensure some arg were passed (either by keyword or
        positional). Assumes all arg values are unique. Returns an error message
        for the first missing arg or None if all are present.
        """
        mock = self.mocks[mock_name]
        for name, val in args.items():
            kwargs = mock.call_args.kwargs
            if name in kwargs:
                if val != kwargs[name]:
                    return 'found kwargs {} but values mismatched (expected: "{}", got: "{}"))'.format(
                            name, self._desc(val), self._desc(kwargs[name]),
                            )
                return False
            if val in mock.call_args.args:
                return False
            return 'failed to find arg by name "{}" or value "{}"'.format(
                name, self._desc(val)
            )

    def __exit__(self, *nargs, **kwargs):
        for patch in self.patches.values():
            patch.stop()
        self.mocks = None


class TestHelpers:
    @staticmethod
    def req_methods():
        client = RestClient('example.com')
        http_verbs = ['get', 'post', 'put', 'patch', 'delete']
        for http_verb in http_verbs:
            yield getattr(client, http_verb)


class TestClient(unittest.TestCase, TestHelpers):
    def test_base_url(self):
        client = RestClient()
        base_base_urls = [
            ':', '&', '|', '',
            'ftp://foo', '//foo', 'foo:',
            23, None, True, False,
            ':65536', ':0',
            'https://', 'http://foo:65536', 'htps:/foo',
            ]
        good_base_urls = [
            ':65535', ':1', 'locahost:1',
            'foo', 'example.com',
            'https://foo', 'https://foo', 'https://foo:80/', 'https://foo:80',
            '/api/v1', '/',
            'https://foo/', 'https://foo/bar', 'https://foo:80/barn/yard',
            ]
        with self.assertRaises(ValueError):
            for bad_url in base_base_urls:
                client.set_base_url(bad_url)
        for good_url in good_base_urls:
            client.set_base_url(good_url)
            with MockResponse(200, b'ok') as mock_resp:
                client.get('/')

    def test_verbs(self):
        """
        Checks all HTTP methods with no query string, extra headers, or
        special bodies.
        """
        with MockResponse() as mock_resp:
            for calls, req_method in enumerate(self.req_methods()):
                req_method('/')
                # +1 for the call we just did
                self.assertEqual(calls + 1, mock_resp.mocks['urlopen'].call_count)
                self.assertEqual(calls + 1, mock_resp.mocks['Request'].call_count)

    def test_paths(self):
        """
        Verifies lots of HTTP request paths for each HTTP method.
        """
        client = RestClient('example.com')
        paths = ['', '/', '/foo', '//foo', '/foo/', '/foo/foo', '/foo/foo//foo/']
        with MockResponse() as mock_resp:
            for req_method in self.req_methods():
                for path in paths:
                    req_method(path)
                    full_path = client.build_url(path)
                    error = mock_resp.call_args_error('Request', {'url': full_path})
                    self.assertFalse(error, error)

    def test_query_string(self):
        """
        Verifies query string params show up for each HTTP method.
        """
        paths = [
            '', '/', '/foo', '//foo', '/foo/', '/foo/foo', '/foo/foo//foo/',
            ]
        query_params = [
            '?', '?foo=bar', '?foo', 'foo', 'foo=bar&food=barn',
            ['foo=bar'], [], ['foo=bar', 'food=barn'],
            {'foo': 'bar'}, {'foo': 'bar', 'food': 'barn'},
            ]
        with MockResponse() as mock_resp:
            permutations = product(self.req_methods(), paths, query_params)
            for req_method, path, query_param in permutations:
                req_method(path, query=query_param)

    def test_json_body(self):
        pass

    def test_req_content_types(self):
        pass

    def test_resp_content_types(self):
        pass

    def test_basic_auth(self):
        pass

    def test_headers(self):
        pass

    #def test_files(self):
    #    pass
