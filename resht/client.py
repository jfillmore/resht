"""
Client for talking to a webserver.
"""

# TODO:
# - JSON body for GET requests

from collections import namedtuple
from typing import Union
import base64
import http.cookies
import json
import re
import ssl
import sys
import time
import urllib.parse
import urllib.request

from . import dbg
from . import util


Response = namedtuple('Response', ['obj', 'decoded', 'data'])


class HttpError(Exception):
    """
    HTTP return code 300-399. Base class for all other HTTP exceptions.
    """
    def __init__(self, error, response: Response):
        self.response = response
        super().__init__(error)


class UserHttpError(HttpError):
    """
    HTTP return code 400-499.
    """
    pass


class ServerHttpError(HttpError):
    """
    HTTP return code >= 500
    """
    pass


class RestClient:
    """
    Client for talking to a web server using RESTful methods.
    """
    def __init__(
            self, base_url:str = 'localhost', insecure:bool = False,
            basic_auth:str = None
        ):
        # the base URL information for construction API requests
        self.base_url = None
        self.cookies = {}  # session cookie cache
        # if set, an oauth/basic authentication header will be included in each request
        self.oauth = None
        self.basic_auth = None
        self.set_base_url(base_url)
        self.ssl_ctx = ssl.create_default_context()
        if insecure:
            self.ssl_ctx.check_hostname = False
            self.ssl_ctx.verify_mode = ssl.CERT_NONE
        if basic_auth:
            self.set_basic_auth(basic_auth)

    @staticmethod
    def merge_headers(base_headers: dict, new_headers:dict = None):
        """
        Returns merged headers with all header names lower-cased to avoid
        duplicates from mixed upper/lower casing.
        """
        merged = {
            name.lower(): val
            for name, val in base_headers.items()
        }
        if not new_headers:
            return merged
        for name, val in new_headers.items():
            merged[name.lower()] = val
        return merged

    def build_url(self, path:str, query:str = None) -> str:
        """
        Returns the full URL with the path given and any query string
        parameters to add. If the path contains a query string the additional
        query param values will overwrite them.
        """
        path = util.pretty_path(
            '/'.join(['', self.base_url['path'], path]),
            True,
            False
        )
        port = self.base_url['port']
        if port == 80 or port == 443:
            port = ''
        else:
            port = ':' + str(port)
        url = '%s://%s%s%s' % (
            self.base_url['scheme'], self.base_url['hostname'], port, path
        )
        # has the base URL been set to include query params?
        if self.base_url['query']:
            url = self.merge_url_query(url, self.base_url['query'])
        # add in manually passed query args
        if query:
            url = self.merge_url_query(url, query)
        return url

    def parse_url(self, url) -> dict:
        """
        Parses a URL into its components. Allows as little information as
        possible (e.g. just a port, just a path), defaulting to
        http://localhost:80/.
        """
        # urlparse just doesn't do it the "right" way...
        # check for protocol and strip it off if found
        parts = {
            'scheme': None,
            'hostname': None,
            'port': None,
            'path': None,
            'params': None,
            'query': None,
            'fragment': None
        }
        # parse out the scheme, if present
        if re.match('^\w+://', url):
            (scheme, url) = url.split('://', 1)
            parts['scheme'] = scheme.lower()
        else:
            parts['scheme'] = 'http'
        # check for a path
        if url.find('/') == -1:
            hostname = url
            url = ''
        else:
            (hostname, url) = url.split('/', 1)
        # do we have a port in the hostname?
        if hostname.find(':') >= 0:
            # chop out the port
            hostname, parts['port'] = hostname.split(':', 1)
        if not hostname:
            hostname = 'localhost'
        parts['hostname'] = hostname.lower()
        # let urlparse do the rest of the work on the path w/ a fake domain
        parsed = urllib.parse.urlparse('http://localhost/' + url)
        parts['path'] = parsed.path
        parts['params'] = parsed.params
        parts['query'] = parsed.query
        parts['fragment'] = parsed.fragment
        return parts

    def set_base_url(self, base_url):
        """
        Sets the base URL for requests. Assumes http://localhost by default.
        """
        if not base_url:
            raise ValueError('Invalid API URL: %s.' % base_url)
        url = self.parse_url(base_url)
        if url['scheme'] not in ['http', 'https']:
            raise ValueError('Only HTTP and HTTPS are supported protocols.')
        self.base_url = url
        if url['port']:
            self.set_port(url['port'])
        else:
            if url['scheme'] == 'https':
                self.set_port(443)
            else:
                self.set_port(80)

    def set_basic_auth(self, basic_auth:str):
        self.basic_auth = basic_auth

    def set_port(self, port):
        """
        Set the port that will be used for requests.
        """
        port = int(port)
        if port >= 0 and port <= 65535:
            self.base_url['port'] = port
        else:
            raise ValueError('Invalid API service port: %s.' % port)

    def head(self, *req_args, **req_kwargs):
        """
        Perform a HEAD request with the provided query string parameters.
        """
        return self.request('GET', *req_args, **req_kwargs)

    def get(self, *req_args, **req_kwargs):
        """
        Perform a GET request with the provided query string parameters.
        """
        return self.request('GET', *req_args, **req_kwargs)

    def post(self, *req_args, **req_kwargs):
        """
        Perform a POST request with the supplied parameters as the payload.
        Defaults to JSON encoding.
        """
        return self.request('POST', *req_args, **req_kwargs)

    def patch(self, *req_args, **req_kwargs):
        """
        Perform a PATCH request with the supplied parameters as the payload.
        Defaults to JSON encoding.
        """
        return self.request('PATCH', *req_args, **req_kwargs)

    def put(self, *req_args, **req_kwargs):
        """
        Perform a PUT request with the supplied parameters as the payload.
        Defaults to JSON encoding.
        """
        return self.request('PUT', *req_args, **req_kwargs)

    def options(self, *req_args, **req_kwargs):
        """
        Perform a OPTIONS request with the supplied parameters as the payload.
        Defaults to JSON encoding.
        """
        return self.request('OPTIONS', *req_args, **req_kwargs)

    def delete(self, *req_args, **req_kwargs):
        """
        Perform a DELETE request with the supplied parameters as the payload.
        Defaults to JSON encoding.
        """
        return self.request('DELETE', *req_args, **req_kwargs)

    def request(
            self,
            method:str,
            path:str,
            body:Union[dict,str] = None,
            query:Union[dict,list,str] = None,
            headers:dict = None,
            verbose:bool = False,
            full:bool = False,
            basic_auth:str = None,
            pre_formatted_body:bool = False,
        ):
        """
        Perform an arbitrary HTTP request. If the base URL and/or path contain
        query string parameters they will all be merged together. GET and HEAD
        requests automatically treat any body params as query params, but other
        methods will encode them into the request body.

        The request body is encoded as JSON by default, form data if if the
        content type header is set to "application/x-www-form-urlencoded", or
        unencoded if the content type header is set to something else.

        Returns the decoded response body, or a Response object if "full" is
        requested.
        """
        # normalize the API parameters
        if method is None or method == '':
            method = 'get'
        method = method.upper()
        if path == '' or path is None:
            path = '/'
        if body is None:
            body = {}
        if isinstance(query, list):
            query = '&'.join(query)
        elif isinstance(query, dict):
            query = self.build_query(query)
        # TODO: allow params to be in the request body (e.g. like ElasticSearch prefers)
        if method in ['GET', 'HEAD'] and body:
            query = self.merge_query(self.build_query(body), query)

        url = self.build_url(path, query)
        request_args = {
            # to ensure we're always normalized we never set 'em directly
            'headers': self.merge_headers({
                'content-Type': 'application/json',
                'accept': 'application/json',
            }),
        }

        # request headers (misc, cookies, auth, etc)
        cookies = []
        for name in self.cookies:
            cookies.append('='.join([name, self.cookies[name]]))
        if cookies:
            request_args['headers'] = self.merge_headers(
                request_args['headers'],
                {'cookie': '&'.join(cookies)}
            )
        if basic_auth or self.basic_auth:
            if not basic_auth:
                basic_auth = self.basic_auth
            auth_header = 'Basic ' + \
                base64.b64encode(basic_auth.encode('utf-8')).decode('ascii')
            request_args['headers'] = self.merge_headers(
                request_args['headers'],
                {'authorization': auth_header},
            )
        if headers:
            # always ensure passed headers override anything we did
            request_args['headers'] = self.merge_headers(
                request_args['headers'],
                headers,
            )

        # request body, automatically encoding if needed
        if method in ['GET', 'HEAD']:
            req_body = ''
        else:
            if pre_formatted_body:
                req_body = body
            else:
                req_content_type = self.get_header(
                    request_args['headers'],
                    'content-type',
                )
                if req_content_type.startswith('application/json'):
                    req_body = json.dumps(body).encode('utf-8')
                elif req_content_type == 'application/x-www-form-urlencoded':
                    req_body = urllib.parse.urlencode(body)
                else:
                    # assume its already been encoded
                    req_body = body
            request_args['data'] = req_body

        # fire away!
        if verbose:
            dbg.log(
                'Request:',
                data=' %s %s' % (method.upper(), url),
                data_inline=True
            )
            if req_body:
                dbg.log('Request Body: ', data=req_body, data_inline=True)
            if request_args['headers']:
                dbg.log('Request Headers:', data=request_args['headers'])
            if self.cookies:
                dbg.log('Request Cookies:', data=self.cookies)
        request = urllib.request.Request(url, **request_args)
        try:
            response = urllib.request.urlopen(request, context=self.ssl_ctx)
        except urllib.request.HTTPError as error_resp:
            response = error_resp
        if verbose:
            dbg.log('Response Status: ', data=response.status, data_inline=True)
            dbg.log('Response Headers:', data={
                    name: val
                    for name, val in response.headers.items()
                }
            )

        # track any cookies we get back; ignore the path as a temp hack :/
        for hdr_name, hdr_value in response.headers.items():
            if hdr_name.lower() == 'set-cookie':
                cookies = http.cookies.BaseCookie(hdr_value)
                for name in cookies:
                    self.cookies[name] = cookies[name].value

        # automatically decode the response body based on content-type
        # if we know the type of charset, perform the decoding automatically
        resp_content_type = response.headers.get('Content-Type')
        resp_data = response.read()
        if resp_data and resp_content_type and ';' in resp_content_type:
            charset = resp_content_type.split(';')[1].strip()
            if '=' in charset:
                resp_data = resp_data.decode(charset.split('=')[1])
        if resp_content_type and resp_content_type.startswith('application/json'):
            try:
                decoded = json.loads(resp_data)
            except:
                raise ValueError('Failed to decode API response\n' + str(resp_data)[:128])
        else:
            decoded = resp_data

        # handle any HTTP response errors
        response = Response(obj=response, decoded=decoded, data=resp_data)
        if response.obj.status < 200 or response.obj.status >= 400:
            error_cls = HttpError
            if response.obj.status >= 500:
                error_cls = ServerHttpError
            elif response.obj.status >= 400:
                error_cls = UserHttpError
            raise error_cls(
                '"%s %s" failed (%s)' % (
                    method, path, response.obj.status
                ),
                response,
            )

        return response if full else decoded

    @classmethod
    def build_query_obj(cls, query, keep_blanks=True):
        """
        Translates a query string into an object. If multiple keys are used the
        values will be contained in an array.
        """
        obj = urllib.parse.parse_qs(query, keep_blank_values=keep_blanks)
        # all objects are lists by default, but it's probably more conventional to flatten single-item arrays
        new_obj = {}
        for key in obj:
            if len(obj[key]) == 1:
                new_obj[key] = obj[key][0]
            else:
                new_obj[key] = obj[key]
        return new_obj

    @classmethod
    def build_query(cls, params, topkey=''):
        """
        Mimics the behaviour of http_build_query PHP function (e.g. arrays will
        be encoded as foo[0]=bar, booleans as 0/1).
        """
        if len(params) == 0:
            return ""
        result = ""
        # is a dictionary?
        if isinstance(params, dict):
            for key in params.keys():
                newkey = urllib.parse.quote(key)
                if topkey != '':
                    newkey = topkey + urllib.parse.quote('[' + key + ']')
                if isinstance(params[key], dict):
                    result += cls.build_query(params[key], newkey)
                elif isinstance(params[key], list):
                    i = 0
                    for val in params[key]:
                        result += newkey + urllib.parse.quote('[' + str(i) + ']') \
                            + "=" + urllib.parse.quote(str(val)) + "&"
                        i = i + 1
                # boolean should have special treatment as well
                elif isinstance(params[key], bool):
                    result += newkey + "=" + urllib.parse.quote(str(int(params[key]))) + "&"
                # assume string (integers and floats work well)
                else:
                    result += newkey + "=" + urllib.parse.quote(str(params[key])) + "&"
        # remove the last '&'
        if result and topkey == '' and result[-1] == '&':
            result = result[:-1]
        return result

    @classmethod
    def merge_query(cls, query1: str, query2: str = None):
        """
        Merge two query strings together. Discards any leading '?' characters.
        """
        if query1.startswith('?'):
            query1 = query1[1:]
        if not query2:
            return query1
        elif query2.startswith('?'):
            query2 = query2[1:]
        return '&'.join([query1, query2])

    @classmethod
    def merge_url_query(cls, url: str, query: str):
        """
        Update a URL to add or append a query string.
        """
        if url.find('?') >= 0:
            url, existing_query = url.split('?', 1)
            query = cls.merge_query(existing_query, query)
        return '?'.join((url, query.strip('?'))).rstrip('?')

    @classmethod
    def get_header(cls, headers: dict, header: str):
        """
        Read a header from the given list (ignoring case) and return the value.
        Returns None if not found, or optionally the value given.
        """
        for key in headers:
            if key.lower() == header.lower():
                return headers[key]
        return None
