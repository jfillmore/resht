#!/bin/bash -u

BASE_DIR=$(cd $(dirname "$0") && pwd -P)

fail() {
    echo "${1-$SCRIPT_NAME command failed}" >&2
    exit ${2:-1}
}


cd "$BASE_DIR" || fail
python3 -m unittest discover resht/ "test_*.py" "$@" || fail 'Tests failed'
