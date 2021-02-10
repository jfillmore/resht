#!/bin/bash -u

fail() {
    echo "${1:-command failed}" >&2
    exit 1
}

set -x
cd $(dirname "$0") || fail

set +x
