from contextlib import contextmanager
from itertools import product
from unittest.mock import (
    patch,
    MagicMock,
    )
import functools
import json
import io
import re
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
        if key_lower in self.headers:
            return self.headers[key_lower]
        return default

    def items(self):
        return self.headers.items()


class MockResponse:
    def __init__(
            self,
            status_code:int = 200,
            body:bytes = b'{}',
            content_type:str = 'application/json; charset=utf-8',
            headers:dict = None,
        ):
        self.status_code = status_code
        self.body = body
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
        urlopen_rv.body = MagicMock(return_value=self.body)
        urlopen_rv.headers = Headers({
            'content-type': self.content_type,
        })
        def read_body(*nargs, **kwargs):
            return io.BytesIO(self.body).read(*nargs, **kwargs)
        urlopen_rv.read = read_body
        return self

    @staticmethod
    def _desc(val):
        str_val = str(val)
        if len(str_val) > 80:
            return str_val[0:32] + '...' + str_val[:32]
        return str_val

    def get_call_arg(self, mock_name:str, name:str, pos:int):
        """
        Try to return an argument first by name, and if not passed as a kwarg
        then we return it by position.
        """
        mock = self.mocks[mock_name]
        if name in mock.call_args.kwargs:
            return mock.call_args.kwargs[name]
        return mock.call_args.args[pos]

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

    @property
    def last_req_data(self):
        return self.get_call_arg('Request', 'data', 2)

    def __exit__(self, *nargs, **kwargs):
        for patch in self.patches.values():
            patch.stop()
        self.mocks = None


class TestHelpers:
    @staticmethod
    def req_methods(base_url='example.com', skip_methods=None):
        client = RestClient(base_url)
        http_verbs = ['get', 'post', 'put', 'patch', 'delete']
        for http_verb in http_verbs:
            if skip_methods and http_verb in skip_methods:
                continue
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
            with MockResponse() as mock_resp:
                client.get('/')

    def test_verbs(self):
        """
        All HTTP methods with no query string, extra headers, or special bodies.
        """
        with MockResponse() as mock_resp:
            for calls, req_method in enumerate(self.req_methods()):
                req_method('/')
                # +1 for the call we just did
                self.assertEqual(calls + 1, mock_resp.mocks['urlopen'].call_count)
                self.assertEqual(calls + 1, mock_resp.mocks['Request'].call_count)

    def test_paths(self):
        """
        Lots of HTTP request paths for each HTTP method.
        """
        client = RestClient('example.com')
        paths = [
            '', '/', '/path', '//path', '/path/', '/path/path',
            '/path/path//path/',
        ]
        with MockResponse() as mock_resp:
            for req_method in self.req_methods():
                for path in paths:
                    req_method(path)
                    url = mock_resp.get_call_arg('Request', 'url', 0)
                    clean_path = '/' + re.sub(f'/+', '/', path.lstrip('/'))
                    self.assertTrue(
                        url.endswith(clean_path),
                        f'Expected URL "{url}" to end with path "{clean_path}"'
                    )

    def test_query_string(self):
        """
        Query string params show up for each HTTP method, whether passed as a
        string, list of strings, or dict of key/value pairs.
        """
        paths = [
            '', '/', '/path', '//path', '/path/', '/path/path',
            '/path/path//path/',
        ]
        query_lists = {
            '': ['?', '',],
            'foo=bar': ['?foo=bar', ['foo=bar'], {'foo': 'bar'}],
            'foo': ['?foo', 'foo'],
            'foo=bar&food=barn': [
                'foo=bar&food=barn',
                ['foo=bar', 'food=barn'],
                {'foo': 'bar', 'food': 'barn'},
            ],
        }
        with MockResponse() as mock_resp:
            permutations = product(self.req_methods(), paths)
            for req_method, path in permutations:
                for to_match, query_list in query_lists.items():
                    for query_param in query_list:
                        req_method(path, query=query_param)
                        url = mock_resp.get_call_arg('Request', 'url', 0)
                        if to_match:
                            self.assertTrue(
                                f'?{to_match}' in url,
                                f'Failed to find "{to_match}" in URL param "{url}"'
                            )
                        else:
                            self.assertTrue(
                                '?' not in url,
                                f'Found unexpected query params in URL "{url}"'
                            )

    def test_query_string_merge(self):
        """
        Having a base URL or request URL with query parameters properly merge
        when params are also included with the request.
        """
        with MockResponse() as mock_resp:
            for req_method in self.req_methods():
                req_method('/?foo=bar', query='food=barn')
                url = mock_resp.get_call_arg('Request', 'url', 0)
                url_path, url_query = url.split('?')
                url_query_parts = set(url_query.split('&'))
                self.assertEqual({'foo=bar', 'food=barn'}, url_query_parts)
            for req_method in self.req_methods('example.com/?foo=bar'):
                req_method('/?food=barn')
                url = mock_resp.get_call_arg('Request', 'url', 0)
                url_path, url_query = url.split('?')
                url_query_parts = set(url_query.split('&'))
                self.assertEqual({'foo=bar', 'food=barn'}, url_query_parts)
            for req_method in self.req_methods('example.com/?foo=bar'):
                req_method('/?food=barn', query='fool=bard')
                url = mock_resp.get_call_arg('Request', 'url', 0)
                url_path, url_query = url.split('?')
                url_query_parts = set(url_query.split('&'))
                self.assertEqual({'foo=bar', 'food=barn', 'fool=bard'}, url_query_parts)

    def test_request_body(self):
        """
        All body-friendly (e.g. all but HEAD... and GET for now) HTTP methods
        accept a request body.
        """
        with MockResponse() as mock_resp:
            for req_method in self.req_methods(skip_methods=['head', 'get']):
                req_method('/', params={'foo': 'bar'})
                self.assertEqual(b'{"foo": "bar"}', mock_resp.last_req_data)

    def test_req_content_types(self):
        """
        Various content types have the request body concoded properly for all
        body-friendly HTTP methods, regardless of header name casing.
        """
        params = {'foo': 'bar'}
        params_json = json.dumps(params).encode('utf-8')
        params_form = 'foo=bar'
        json_header_arg_list = [
            None,
            {'content-type': 'application/json'},
            {'content-type': 'application/json; charset=utf-8'},
        ]
        # vary case on form data so we aren't testing default encoding behavior
        form_header_arg_list = [
            {'content-type': 'application/x-www-form-urlencoded'},
            {'Content-Type': 'application/x-www-form-urlencoded'},
        ]
        with MockResponse() as mock_resp:
            for req_method in self.req_methods(skip_methods=['head', 'get']):
                # application/json types
                for header_arg in json_header_arg_list:
                    req_method('/', params=params, headers=header_arg)
                    self.assertEqual(params_json, mock_resp.last_req_data)
                # form data
                for header_arg in form_header_arg_list:
                    req_method( '/', params=params, headers=header_arg)
                    self.assertEqual(params_form, mock_resp.last_req_data)


    def test_resp_content_types(self):
        """
        Various response content types get decoded automatically, if
        recognnized.
        """
        resp_data = b'{"foo": "bar"}'
        resp_data_obj = json.loads(resp_data.decode('utf-8'))
        bodies = {
            'application/json': resp_data_obj,
            'application/json; charset=utf-8': resp_data_obj,
            'text/plain': resp_data,
            'foo/bar': resp_data,
        }
        for content_type, to_match in bodies.items():
            with MockResponse(body=resp_data, content_type=content_type) as mock_resp:
                for req_method in self.req_methods(skip_methods=['head']):
                    self.assertEqual(
                        req_method('/', params=resp_data_obj),
                        to_match,
                        f'failed to decode "{content_type}" properly',
                    )

    def test_basic_auth(self):
        pass

    def test_headers(self):
        pass

    #def test_files(self):
    #    pass
