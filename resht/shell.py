#!/usr/bin/python -tt

"""
Shell for interacting with a RESTful server.
"""

# FIXME: color vs no_color arg handling

from collections import namedtuple
from traceback import print_exception
import json
import os
import os.path
import re
import shlex
import shutil
import socket
import subprocess
import sys
import traceback
import typing

# import hacks!
os.environ['TERM'] = 'linux'
import readline

from . import jsonx
from . import client
from . import dbg
from . import usage
from . import types
from . import utils


class UserError(Exception):
    pass


class Shell:
    """
    Shell for interacting with REST client.
    """
    aliases = {
        'del': 'delete',
        'opts': 'options',
        'opt': 'options',
        '?': 'help'
    }
    http_methods = (
        'head',
        'get',
        'post',
        'put',
        'patch',
        'delete',
        'options'
    )
    commands = (
        'cd',
        'env',
        'headers',
        'help',
        'quit',
        'set',
        'sh',
    )
    _env = {
        'cwd': '/',  # where in the URL we are operating
        'last_cwd': '/',
        'histfile': None,
        'vars': {}  # automatically added to each API call
    }
    decode = json.JSONDecoder().decode
    encode = json.JSONEncoder().encode

    def __init__(self, argv):
        self.last_rv = False
        self.env(
            'histfile',
            os.path.join(os.path.expanduser('~'), '.resht_history')
        )
        self.default_headers = types.Headers()
        self.runtime_args = {
            'color': sys.stdout.isatty(),
            'formatted': True,
            'insecure': False,
            'base_url': 'https://localhost:443',
            'verbose': False,
        }
        self.interactive = False

        args = self.parse_cmd(argv)
        # seed our defaults based on whatever was passed initially
        self.runtime_args = utils.get_args(self.runtime_args, args)
        self.default_headers.update(args['headers'])
        self.client = client.RestClient(args['base_url'], args['insecure'])

        if args['help']:
            self.print_help()
            return
        if args['shell']:
            self.start(cmd=argv)
        elif not args['verb']:
            # nothing given, but not in shell mode... offer help!
            self.print_help()
            self.last_rv = 1
        else:
            # just do a one-off command
            self.exec_cmd(cmd=argv, print_meta=args['verbose'])

    def start(
            self,
            cmd = None,
            read_history:bool = True,
        ):
        # prepare the shell
        self.interactive = True
        if not cmd:
            self.print_help(shell=True)
        if read_history:
            try:
                readline.read_history_file(self.env('histfile'))
            except:
                pass

        # run APIs/commands, handling specific exceptions until the user quits
        loop = True
        while loop:
            try:
                # run a command by default to start if needed
                if cmd:
                    self.exec_cmd(cmd, print_meta=True)
                    cmd = None
                self.send_prompt()
                self.exec_cmd(
                    input(),
                    print_meta=True,
                )
            except KeyboardInterrupt:
                pass
                loop = False
            except EOFError as e:
                pass
                loop = False
            except ValueError as e:
                dbg.log('Input error: ' + str(e) + '\n', symbol='!', color='0;31', no_color=not self.runtime_args['color'])
            except UserError as e:
                dbg.log(str(e) + '\n', symbol='!', color='0;31', no_color=not self.runtime_args['color'])
            except Exception as e:
                print_exception(*sys.exc_info())
                dbg.log(str(e) + '\n', symbol='!', color='0;31', no_color=not self.runtime_args['color'])
        self.stop()
        return self.last_rv

    def stop(self):
        readline.write_history_file(self.env('histfile'))
        self.interactive = False

    def send_prompt(self, last_resp_meta=None):
        # TODO:
        # - show current settings (e.g. verbose)
        # - show default headers
        # - show default vars/etc
        #
        # e.g.
        # [+ {status_code}] / counters
        # [! {type}] / counters
        # [env: 0
        # [http://localhost:8123/ - /foo/bar] >
        #
        lines = []

        if last_resp_meta:
            self._print_response_meta(last_resp_meta)
        lines.append(''.join([
            '\033[0;35m',
            '[',
            '\033[1;35m',
            str(self.client.base_url),
            ' - ',
            self.env('cwd'),
            '\033[0;35m',
            '] ',
            '\033[1;37m',
            '\033[0;0m'
        ]))
        sys.stdout.write('\n'.join(lines) + '\n')

    def print_help(self, shell=False):
        if shell:
            dbg.log(usage.hints.shell, no_color=True, symbol='')
        else:
            dbg.log(usage.hints.help(), no_color=True, symbol='')

    @staticmethod
    def _split_arg(token:str) -> list:
        """
        Split out any combined arguments (e.g.-rf -> -r -f) for easier parsing.
        """
        if len(token) < 3 or token[0] != '-' or token[1] == '-':
            return [token]
        return [
            f'-{char}'
            for char in token[1:]
        ]

    def parse_cmd(self, expr):
        # TODO: clean this up so we're more explicit about what we're doing: an API request or shell command, and where to find args
        # some args have defaults based on our runtime args
        args = {
            'FILES': [],
            'api_args': {},
            'basic_auth': None,
            'cmd_args': [],
            'color': self.runtime_args['color'],
            'exclude': [],
            'extract': [],
            'formatted': self.runtime_args['formatted'],
            'headers': self.default_headers.copy(),
            'help': False,
            'insecure': False,
            'invert_color': False,
            'path': None,
            'query': [],
            'redir_type': None,
            'shell': False,
            'stdout_redir': None,
            'base_url': self.runtime_args['base_url'],
            'verb': None,
            'verbose': False,
        }
        if isinstance(expr, str):
            tokens = shlex.split(expr)
        else:
            tokens = expr  # already a list

        i = 0
        # iterate through each paramter and handle it
        while i < len(tokens):
            token = tokens[i]
            # check for short combined params (e.g. -rf); commands never have these
            if args['verb'] is None or args['verb'] in self.http_methods:
                expanded = self._split_arg(token)
                token = expanded[0]
                tokens.extend(expanded[1:])

            if not token:
                pass

            if token == '>' or token[0] == '>' or token == '>>':
                # output redirection! woot
                if token == '>' or token == '>>':
                    i += 1
                    if token == '>':
                        args['redir_type'] = 'w'
                    else:
                        args['redir_type'] = 'a'
                    if i == len(tokens):
                        raise Exception("Missing file path to output result to.")
                    args['stdout_redir'] = tokens[i]
                else:
                    if len(token) > 1 and token[0:2] == '>>':
                        args['stdout_redir'] = token[2:]
                        args['redir_type'] = 'a'
                    else:
                        args['stdout_redir'] = token[1:]
                        args['redir_type'] = 'w'
            elif token == '-B' or token == '--basic':
                i += 1
                if i == len(tokens):
                    raise Exception("Missing HTTP basic auth user/pass parameter.")
                if ':' not in tokens[i]:
                    raise Exception("Expected HTTP basic auth in format 'user:pass'.")
                args['basic_auth'] = tokens[i]
            elif token == '-F' or token == '--file':
                i += 1
                if i == len(tokens):
                    raise Exception("Missing value for file to upload.")
                # collect up the name
                if tokens[i].find('=') == -1 or tokens[i].find('&') != -1:
                    raise Exception("Invalid file name=file_path pair.")
                (name, path) = tokens[i].split('=', 1)
                # make sure the file exists
                if not os.path.isfile(path):
                    raise Exception("Unable to either read or locate file '%s." % path)
                args['FILES'][name] = path
                raise Exception("Not supported at the moment")
            elif token == '-Q' or token == '--query':
                i += 1
                if i == len(tokens):
                    raise Exception("Missing query name=value pair.")
                # make sure we have a valid pair
                if tokens[i].find('=') == -1 or tokens[i].find('&') != -1:
                    raise Exception("Invalid query name=value pair.")
                args['query'].append(tokens[i])
            elif token == '-i' or token == '--invert':
                args['invert_color'] = True
            elif token == '--insecure':
                args['insecure'] = True
            elif token == '-c' or token == '--color':
                args['color'] = True
            elif token == '-C' or token == '--no-color':
                args['color'] = False
            elif token == '-v' or token == '--verbose':
                args['verbose'] = True
            elif token == '-f' or token == '--form':
                args['headers'].add('content-type', 'application/x-www-form-urlencoded')
            elif token == '-h' or token == '--help':
                args['help'] = True
            elif token == '-H' or token == '--header':
                i += 1
                if i == len(tokens):
                    raise Exception("Missing value for HTTP header.")
                hdr_parts = tokens[i].split(': ', 1)
                if len(hdr_parts) != 2:
                    raise Exception(f'Invalid HTTP header: "{tokens[i]}"')
                args['headers'].add(hdr_parts[0], hdr_parts[1])
            elif token == '-s' or token == '--shell':
                args['shell'] = True
            elif token == '-j' or token == '--json':
                i += 1
                if i == len(tokens):
                    raise Exception("Missing value for JSON API params.")
                try:
                    api_args = self.decode(tokens[i])
                    if isinstance(api_args, dict):
                        args['api_args'].update(api_args)
                    else:
                        raise UserError("JSON values must be a dictionary of arguments.")
                except UserError as e:
                    dbg.log(f'Invalid JSON: {e}')
                    raise e
                except Exception as e:
                    dbg.log(f'Invalid JSON: {e}')
                    raise UserError(e)
            elif token == '-r' or token == '--raw':
                args['formatted'] = False
            elif token == '--url' or token == '-u':
                i += 1
                if i == len(tokens):
                    raise Exception("Missing value for --url.")
                args['base_url'] = tokens[i]
            elif token == '-x' or token == '--extract':
                i += 1
                if i == len(tokens):
                    raise Exception("Missing value for --extract.")
                args['extract'].append(tokens[i])
            elif token == '-X' or token == '--exclude':
                i += 1
                if i == len(tokens):
                    raise Exception("Missing value for --exclude.")
                args['exclude'].append(tokens[i])
            else:
                # we always pick up the command/method first
                if args['verb'] is None:
                    args['verb'] = token.lower()
                    # process any aliases
                    if args['verb'] in self.aliases:
                        args['verb'] = self.aliases[args['verb']]
                elif args['verb'] in self.http_methods and args['path'] is None:
                    # collect the API -- unless this is a internal command
                    args['path'] = utils.pretty_path(self.parse_path(token), False, False)
                else:
                    # anything else is a parameter
                    if args['verb'] in self.http_methods:
                        # get the name/value
                        args['api_args'] = self.parse_param(token, args['api_args'])
                    else:
                        args['cmd_args'].append(token)
            i += 1
        return args

    def exec_cmd(self, cmd, print_meta: bool = False) \
            -> typing.Union[types.Response, bool]:
        """
        Parse a shell command to either run an internal command or perform an
        HTTP request. Returns True if a command was successfully parsed, false
        if the user wants to quit, or throws an exception with a syntax or
        run-time/request error.

        Commands/requests are executed using the current environment and/or
        base arguments.

        By default, responses are printed to standard-out based on the run-time
        parameters. Output can be piped to write/append files like a normal
        shell (e.g. if using inside the rest shell).
        """
        # collect up the command parts
        args = self.parse_cmd(cmd)
        # not writing to a file by default
        file = None
        # run the command or API
        # FIXME: clean up error handling and printing the response
        answer = None
        if not args['verb'] and self.interactive:
            raise UserError('No API or command given')
        if args['verb'] in self.http_methods:
            # run an API
            try:
                args['api_args'].update(self.env('vars'))
                answer = self.client.request(
                    method=args['verb'],
                    path=self.parse_path(args['path']),
                    body=args['api_args'],
                    query=args['query'],
                    headers=args['headers'],
                    verbose=args['verbose'],
                    basic_auth=args['basic_auth'],
                    full=True,
                    insecure=args['insecure'],
                    base_url=args['base_url'],
                    no_color=not args['color'],
                )
                response = answer.decoded
                response_status = None
                success = True
            except client.HttpError as e:
                success = False
                response_status = str(e)
                response = e.response.decoded
                answer = e.response
            except Exception as e:
                response_status = str(e)
                response = None
                success = False
                answer = None
            # prep response redirection, since it worked
            if args['stdout_redir'] is not None:
                try:
                    file = open(args['stdout_redir'], args['redir_type'])
                except IOError as e:
                    dbg.log('Failed to write response: ' + e + '\n', symbol='!', no_color=not args['color'])
                    return answer
        else:
            try:
                return self.run_shell_cmd(args['verb'], args['cmd_args'])
            except UserError as ex:
                response = None
                success = False
                answer = None
                response_status = '[' + type(ex).__name__ + '] ' + str(ex)
            except Exception as ex:
                code_trace = dbg.CodeTrace.from_exception(ex)
                response_status = '[' + code_trace.error_type + '] ' + code_trace.error
                response = [
                    frame._asdict()
                    for frame in code_trace.frames
                ]
                success = False
                answer = None
                if args['verbose']:
                    print_exception(*sys.exc_info())

        # adjust the response object as requested
        self.last_rv = int(not success)
        if answer and (args['extract'] or args['exclude']):
            # handle HTML vs JSON differently
            content_type = answer.obj.headers.get('Content-Type')
            to_store = {}
            if content_type.startswith("application/json"):
                try:
                    response = jsonx.extract(
                        response,
                        extract=args['extract'],
                        exclude=args['exclude'],
                        raw=True,
                    )
                    # if we only had one match return it instead of a single-element array for cleanliness
                    if len(response) == 1:
                        response = response[0]
                except:
                    (exc_type, exc_msg, exc_tb) = sys.exc_info()
                    dbg.log('%s\n' % exc_msg, symbol='!', no_color=not args['color'])
                    return True
        self._print_response(
            success,
            response,
            response_status,
            formatted=args['formatted'],
            color=args['color'],
            invert_color=args['invert_color'],
            stdout_redir=args['stdout_redir'],
            redir_type=args['redir_type'],
            file=file
        )
        if print_meta and isinstance(answer, types.Response):
            self._print_response_meta(answer.meta)
        if self.interactive:
            sys.stdout.write(
                '\033[1;4;30;40m' + (' ' * shutil.get_terminal_size().columns) + '\033[0m\n'
            )
        return answer

    def _print_response_meta(self, resp_meta: types.ResponseMeta):
        if resp_meta.success:
            code_color = '\033[0;30;42m'
            msg_color = '\033[4;32;40m'
        else:
            code_color = '\033[0;30;41m'
            msg_color = '\033[4;31;40m'
        sys.stderr.write(''.join([
            code_color,
            ' ' + str(resp_meta.code) + ' ',
            msg_color,
            ' ',
            resp_meta.duration.desc,
            ' / ',
            str(resp_meta.byte_size),
            '\033[0m',
        ]) + '\n')

    def _print_response(self, success, response, status=None, **args):
        # FIXME: untangle this crap
        if success:
            if response is not None:
                if 'stdout_redir' in args and args['stdout_redir'] is not None:
                    args['file'].write(dbg.obj2str(response, color=False))
                    args['file'].close()
                else:
                    if isinstance(response, str):
                        # FIXME: print full response string if its a command error vs API error
                        if args.get('formatted'):
                            chars_to_print = min(len(response), 256)
                            dbg.log(
                                '# %d/%d chars%s\n' % (
                                    chars_to_print,
                                    len(response),
                                    (
                                        ", use --raw|-r to see full output"
                                        if chars_to_print < len(response)
                                        else ""
                                    )
                                ),
                                no_color=not args.get('color')
                            )
                            print(response[0:chars_to_print])
                        else:
                            print(response)
                    else:
                        if args.get('formatted'):
                            dbg.pretty_print(
                                response,
                                color=args.get('color'),
                                invert_color=args.get('invert_color')
                            )
                        else:
                            print(json.dumps(response, indent=4, sort_keys=True))
        else:
            if isinstance(response, str):
                if args['formatted']:
                    chars_to_print = min(len(response), 256)
                    dbg.log(
                        '%s (%d/%d chars)\n:%s' % (
                            status,
                            chars_to_print,
                            len(response),
                            response[0:chars_to_print],
                        ),
                        symbol='!',
                        color='1;31',
                        no_color=not args.get('color'),
                    )
                else:
                    dbg.log(
                        '%s:\n\033[0m%s' % (
                            status, response
                        ),
                        symbol='!',
                        color='1;31',
                        no_color=not args.get('color'),
                    )
            else:
                dbg.log(
                    '%s:' % (status),
                    symbol='!',
                    color='1;31',
                    no_color=not args.get('color'),
                )
                if response is not None:
                    if args.get('formatted'):
                        dbg.pretty_print(
                            response,
                            color=args.get('color'),
                            invert_color=args.get('invert_color')
                        )
                    else:
                        print(json.dumps(response, indent=4, sort_keys=True))

    def env(self, key, value=None):
        """
        Fetch or set a value from the environment.
        """
        key = key.lower()
        if key in self._env:
            if value is None:
                return self._env[key]
            else:
                # remember the last dir when changing it
                if key == 'cwd':
                    self._env['last_cwd'] = self._env['cwd']
                self._env[key] = value
                return value

    def parse_param(self, str, params:dict = None, single=False) -> typing.Union[dict,tuple]:
        """
        Parse a CLI parameter, optionally merging it with existing passed
        parameters.

        Parameter encoding:

        'foo', '!foo', '^foo'
            Bare word are treated as boolean values. True by default, false if
            starting with an exclaimation point or carrot.

        'foo=bar', 'foo=0', 'foo.bar=42'
            Assign the string value to the key specified. If the key contains
            dots then objects will be created automatically.

        'foo:=3', 'foo.bar:=["a", "b", "c"]'
            Assign the JSON-encoded values to the key specified.
        """
        if not params:
            params = {}
        elif single:
            raise Exception('Cannot merge in params when parsing a single value')
        param_parts = str.split('=', 1)
        key = param_parts[0]
        # no value given? treat it as a boolean
        if len(param_parts) == 1:
            if key.startswith('^') or key.startswith('!'):
                value = False
                key = key[1:]
            else:
                value = True
        else:
            value = param_parts.pop()
            # check to see if we have a JSON value or are fetching from memory
            if key.endswith(':'):  # e.g. 'foo:={"bar":42}'
                value = self.decode(value)
                key = key.rstrip(':')
        # check the name to see if we have a psuedo array
        # (e.g. 'foo.bar=3' => 'foo = {"bar": 3}')
        if '.' in key:
            if single:
                raise Exception('Nested objects not allowed when parsing a single value')
            # break the array into the parts
            p_parts = key.split('.')
            key = p_parts.pop()
            param_ptr = params
            for p_part in p_parts:
                if not p_part in param_ptr:
                    param_ptr[p_part] = {}
                param_ptr = param_ptr[p_part]
            param_ptr[key] = value
        else:
            params[key] = value
        return (key, value,) if single else params

    def parse_path(self, path=''):
        """
        Returns a path that may contain relative references (e.g.  "../foo")
        based on our current path.
        """
        # no path? go to our last working dir
        if path == '-':
            return self._env['last_cwd']
        if not path:
            return self.env('cwd')
        # make sure the path is formatted pretty
        path = utils.pretty_path(path, False, False)
        # parse the dir path for relative portions
        trailing = path.endswith('/')
        if path.startswith('/'):
            cur_dirs = ['/']
        else:
            cur_dirs = self.env('cwd').split('/')
        dirs = path.split('/')
        for name in dirs:
            if name == '' or name == '.':
                # blanks can creep in on absolute paths, no worries
                continue
            rel_depth = 0
            if name == '..':
                if not len(cur_dirs):
                    raise Exception("URI is out of bounds: \"%s\"." % (path))
                cur_dirs.pop()
            else:
                cur_dirs.append(name)
        # always end up with an absolute path
        final_path = utils.pretty_path('/'.join(cur_dirs), True, False)
        if trailing and not final_path.endswith('/'):
            final_path = final_path + '/'
        return final_path

    def set_runtime_arg(self, name: str, val: any):
        if name not in self.runtime_args:
            raise Exception(f'Unrecognized configuration option: "{name}"')
        # bool-ish arg handling
        if name in ['formatted', 'insecure', 'verbose', 'color']:
            if val in ['1', 'True', 'true', 't']:
                val = True
            elif val in ['0', 'False', 'false', 'f']:
                val = False
            else:
                val = bool(val)
        elif name == 'base_url':
            self.client.set_base_url(val)
        self.runtime_args[name] = val

    def run_shell_cmd(self, cmd, params=None) -> types.Response:
        """
        Run a command using the specified parameters.
        """
        if params is None:
            params = []
        if cmd == 'set':
            # break the array into the parts
            if not params:
                self._print_response(
                    success=True,
                    response=self.runtime_args,
                    color=self.runtime_args['color'],
                    formatted=True,
                )
            # allow multiple runtime args to be set at once
            for param in params:
                self.set_runtime_arg(*self.parse_param(param, single=True))
        elif cmd == 'debug':
            import pdb
            pdb.set_trace()
        elif cmd == 'cd':
            path = ''
            if len(params):
                path = params[0]
            self.env('cwd', self.parse_path(path))
        elif cmd == 'headers':
            if not params:
                dbg.pretty_print(self.default_headers.as_dict())
            for param in params:
                if param.startswith('-'):
                    name = param[1:]
                    removed = self.default_headers.remove(name)
                    if removed:
                        sys.stdout.write(f'\033[1;37mHeader "{name}" cleared\033[0m')
                    else:
                        sys.stdout.write(f'H\033[1;37meader "{name}" was already clear\033[0m')

                else:
                    name, val = self.parse_param(param, single=True)
                    self.default_headers.add(name, val)
                    sys.stdout.write(f'\033[1;32m+{name}\033[0m\n')
            sys.stdout.write('\n')
        elif cmd == 'quit':
            return types.Response(success=False)
        elif cmd == 'help':
            self.print_help(shell=True)
        elif cmd == 'sh':
            # TODO: format better
            proc = subprocess.Popen(params)
        else:
            raise UserError('Unrecognized command: "%s". Enter "help" or ? for help.' % (cmd))
        return True
