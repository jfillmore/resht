from typing import Union, NamedTuple
import re
import urllib.parse



class ByteSize(NamedTuple):
    num_bytes: int
    unit: str
    value: float

    def __str__(self):
        return f'{self.value} {self.unit}'


class Duration(NamedTuple):
    # the duration in total
    ms: int
    # description, broken out by days/hours/minutes as needed
    desc: str

    def __str__(self):
        return self.desc


class ResponseMeta(NamedTuple):
    duration: Duration
    byte_size: ByteSize
    success: bool
    code: int


class Headers:
    """
    Wrapper around HTTP header management forcing lowercase keys and ensuring duplication.
    """
    def __init__(self, headers: dict = None):
        self._headers = {}
        self.update(headers)

    def as_dict(self):
        return {
            name: val
            for name, val in self._headers.items()
        }

    def get(self, key, default=None):
        key_lower = key.lower()
        if key_lower in self._headers:
            return self._headers[key_lower]
        return default

    def add(self, key:str, val:str, update_only:bool = False):
        key_lower = key.lower()
        if update_only and not self.exists(key_lower):
            raise ValueError(f'No header named "key" exists; cannot add')
        self._headers[key_lower] = val

    def exists(self, key:str) -> bool:
        return key.lower in self._headers

    def remove(self, key:str, ignore_missing=True) -> bool:
        """
        Delete a header and return whether not it was actually deleted.
        """
        key_lower = key.lower()
        if key_lower in self._headers:
            del(self._headers[key_lower])
            return True
        elif not ignore_missing:
            raise ValueError(f'No header named "key" exists; cannot remove')
        return False

    def update(self, headers: dict):
        if not headers:
            return
        for key, val in headers.items():
            self.add(key, val)

    def copy(self):
        return Headers(self._headers.copy())

    def items(self):
        return self._headers.items()


class Response(NamedTuple):
    obj: any
    decoded: any
    data: bytes
    meta: ResponseMeta


class Url(NamedTuple):
    scheme: str
    hostname: str
    port: int
    path: str
    query: str
    params: str
    fragment: str

    def __str__(self):
        url = f'{self.scheme}://{self.hostname}'
        if any([
                (self.scheme == 'https' and self.port != 443),
                (self.scheme == 'http' and self.port != 80),
            ]):
            url+= ':' + str(self.port)
        url += self.path
        if self.params:
            url += f';{self.params}'
        if self.query:
            url += f'?{self.query}'
        if self.fragment:
            url += f'#{self.query}'
        return url

    def validate(self):
        if self.scheme.lower() not in ['http', 'https']:
            raise ValueError('Only HTTP and HTTPS are supported protocols.')
        if self.port < 1 or self.port > 65535:
            raise ValueError(f'Invalid API service port: {port}.')

    @staticmethod
    def parse_str(url_str:str):
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
        if re.match('^\w+://', url_str):
            (scheme, url_str) = url_str.split('://', 1)
            parts['scheme'] = scheme.lower()
        else:
            parts['scheme'] = 'http'
        # check for a path
        if url_str.find('/') == -1:
            hostname = url_str
            url_str = ''
        else:
            (hostname, url_str) = url_str.split('/', 1)
        # do we have a port in the hostname?
        if hostname.find(':') >= 0:
            # chop out the port
           hostname, parts['port'] = hostname.split(':', 1)
        if not hostname:
            hostname = 'localhost'
        parts['hostname'] = hostname.lower()
        # let urlparse do the rest of the work on the path w/ a fake domain
        parsed = urllib.parse.urlparse('http://localhost/' + url_str)
        parts['path'] = parsed.path
        parts['params'] = parsed.params
        parts['query'] = parsed.query
        parts['fragment'] = parsed.fragment
        # normalize a bit and supply any defaults
        if not parts['port']:
            if parts['scheme'] == 'https':
                parts['port'] = 443
            else:
                parts['port'] = 80
        else:
            parts['port'] = int(parts['port'])
        url = Url(**parts)
        url.validate()
        return url
