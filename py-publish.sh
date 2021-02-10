#!/bin/bash -u

fail() {
    echo "${1:-command failed}" >&2
    exit 1
}

usage() {
    echo "Usage: $(basename $0) [test|live]" >&2
}

[ $# -eq 1 ] || {
    usage
    fail "Missing environment to publish to"
}
[ "$1" = test -o "$1" = live ] || {
    usage
    fail "Invalid environment"
}
upload_args=(
    upload
)
build_dir=dist
[ "$1" = test ] && {
    upload_args+=(--repository testpypi)
    build_dir=dist-test
}


set -x
cd $(dirname "$0") || fail
python3 -m build --outdir "$build_dir" || fail
python3 -m twine "${upload_args[@]}" "$build_dir"/* || fail
set +x
