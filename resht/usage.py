from typing import NamedTuple


class UsageHint(NamedTuple):
    args: str
    params: str
    data_paths: str
    shell: str
    examples: str

    def help(self):
        return ''.join([
            self.args,
            self.params,
            self.data_paths,
            self.shell,
            self.examples,
        ])


usage_args = """
USAGE: resht HTTP-VERB|COMMAND API_PATH [API_PARAMS] [ARGUMENTS]

ARGUMENTS
---------------------------------------------------------------------------

HTTP OPTIONS (each may be specified multiple times)
   -f, --form               Override default of sending JSON data
   -H, --header HEADER      HTTP header (e.g. 'Foo: bar') .
   -Q, --query QUERY_DATA   Query data to include (e.g. foo=bar&food=yummy).
   -d, --data NAME[+]=PATH  Store response data; '+' also adds variable to the env


OTHER OPTIONS
   -B, --basic USER:PASS    HTTP basic authentication.
   -c, --color              Color formatted JSON responses (default=True).
   -C, --no-color           Do not color formatted JSON responses.
   -h, --help               This information.
   -I, --invert             Invert colors in formatted JSON responses.
       --insecure           Do not valid SSL certificates (danger!)
   -j, --json STRING        Append JSON-encoded list to API parameters.
   -q, --quiet              Do not print API return response.
   -r, --raw                Don't format response data; return raw response.
   -s, --shell              Shell mode for running multiple APIs within a session.
   -u, --url URL            URL to the API location (default: https://localhost/).
   -v, --verbose            Print verbose debugging info to stderr.
   -x, --extract PATH       Parse JSON to return specific data; may be repeated.
   -X, --exclude PATH       Exclude specified path from JSON data; may be repeated.
   > FILE                   Write API response to specified file.
   >> FILE                  Append API response to specified file.
"""

usage_params = \
"""
API PARAMS
---------------------------------------------------------------------------
Dictionaries can be created on demand using dot notation. Multiple params within the same dictionary will merge together. Values are always encoded as strings unless ":=" is used to assign the value.

   foo                      {"foo": true}
   ^foo                     {"foo": false}
   foo=bar                  {"foo": "bar"}
   foo.bar=3 foo.bard=abc   {"foo": {"bar": "3", "bard": "abc"}}
   foo:='{"bar":3}'         {"foo": {"bar": 3}}
   foo.bar:=3.14            {"foo": {"bar": 3.14}}

Variables in memory (e.g. shown by 'data' command) may be referenced using "+=" as the operator.
"""

usage_data_paths = \
"""
JSON PATHS  (--extract, --exclude, --data)
---------------------------------------------------------------------------
The JSON data can be filtered based on index, key matches, ranges, etc.

    Arrays:
        By Index:
         - 'foo/0', 'foo/2', 'foo/-1' (last item)
        By Range:
         - 'foo/:' or 'foo/*' (all items within the array),
         - 'foo/2:', 'foo/:2', 'foo/1:5', 'foo/-2:' (last 2),
         - 'foo/:-2' (all but last two),
         - 'foo/1:-3' (between first and up until 3rd to last)
    Dictionaries:
        Regular Expressions:
         - 'foo/b..?r' = foo/bar, foo/beer
         - 'foo/bar/.*[pP]assw(or)?d' == anything within foo/bar that looks like a password
"""


usage_shell = \
"""
SHELL COMMANDS
---------------------------------------------------------------------------
   HTTP_VERB REL_URL [PARAMS] Perform an HTTP(S) request
   cd                         Change the base URL (e.g. "cd customers/8; cd ../9").
   help                       This information.
   quit                       Adios! (quit shell).
   headers [key=val, -key]    List, set, or clear headers.
   set [PARAMS]               List or set configuration options.
   sh EXPR                    Run a BASH shell command.
"""

# TODO:
# !python expr               Execute a python expression
# \HTTP_VERB ... (no extra stuff for this one command)
# env -i or such to clear

usage_examples = \
"""
EXAMPLES:
---------------------------------------------------------------------------
    rest-cli -u https://foo.com/api -s
    > get site/foo.com -v
    > post site -j domain=foo.com
    > cd site/foo.com
    > get ./
"""


hints = UsageHint(
    usage_args,
    usage_params,
    usage_data_paths,
    usage_shell,
    usage_examples,
)
