```
USAGE: resht HTTP-VERB PATH [API_PARAMS] [ARGUMENTS]

JSON-oriented REST API client with shell mode for session-based flows.

EXAMPLES:
---------------------------------------------------------------------------
    $ resht -u https://example.com/api get foo x=1
    {...}

    $ resht -u https://example.com/api/
    > get site/foo.com -v
    > post site -j domain=foo.com
    > cd site/foo.com
    > get ./

ARGUMENTS
---------------------------------------------------------------------------

    REQUEST ARGS
   -B, --basic USER:PASS    HTTP basic authentication.
   -d, --data DATA          Set request body to the string given; cannot be
                            used with API params or --json
   -H, --header HEADER      HTTP header (e.g. 'Foo: bar', repeatable)
   -I, --insecure           Do not valid SSL certificates (dangerous!)
   -Q, --query QUERY_DATA   Extra query data to merge
                            (e.g. "foo=bar&food=yummy", repeatable).
   -f, --form               Override default of sending JSON data
   -j, --json STRING        Merge JSON-encoded string into API params (repeatable)
   -u, --url URL            Base URL for API requests (default: https://localhost/).


    MISC ARGS
   -h, --help               This information.
   -s, --shell              Start shell mode; run initial API
   -v, --verbose            Print verbose debugging info to stderr.

    OUTPUT ARGS:
   -c, --color              Color formatted JSON responses (default=True).
   -C, --no-color           Do not color formatted JSON responses.
   -r, --raw                Don't format response data; return raw response.
   -x, --extract PATH       Parse JSON to return specific data; may be repeated.
   -X, --exclude PATH       Exclude specified path from JSON data; may be repeated.
   > FILE                   Write API response to specified file.
   >> FILE                  Append API response to specified file.

API PARAMS
---------------------------------------------------------------------------
    API parameters are defined through a terse dotted notation making nested
    objects easy to quickly define. Non-boolean values are assigned using
    the delimiter "=" (string) or ":=" (JSON encoded).

    Arrays must be created using ":=" or using "-d|--data".

    BOOLEANS:
       foo                      {"foo": true}
       foo.bar                  {"foo": {"bar": true}}
       ^foo                     {"foo": false}
       !foo                     {"foo": false}

    STRINGS:
       foo=bar                  {"foo": "bar"}
       foo.bar=3 foo.bard=abc   {"foo": {"bar": "3", "bard": "abc"}}

    OTHER (RAW JSON):
       foo:='{"bar":3}'         {"foo": {"bar": 3}}
       foo.bar:=3.14            {"foo": {"bar": 3.14}}

JSON PATHS  (-x|--extract, -X|--exclude)
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
         - 'foo/bar/.*[pP]assw(or)?d' == anything within foo/bar like a password

SHELL COMMANDS
---------------------------------------------------------------------------
   HTTP_VERB URL [PARAMS]     Perform request
   cd                         Change the base URL (e.g. "cd customers/8; cd ../9").
   help                       This information.
   quit                       Adios! (quit shell).
   headers [key=val, -key]    List, set, or clear headers.
   set [PARAMS]               List or set configuration options.
   sh EXPR                    Run a BASH shell command.
```
