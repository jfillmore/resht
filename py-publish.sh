#!/bin/bash -u

BASE_DIR=$(cd $(dirname "$0") && pwd -P)
SCRIPT_NAME=$(basename "$0")


# functions
# ==========================================

fail() {
    echo -e "\033[1;31m${1:-\ncommand failed}\033[0m" >&2
    exit 1
}

usage() {
    echo -e "\033[1;37mUsage: $SCRIPT_NAME [test|live]\033[0m" >&2
}

cmd() {
    if [ $DRYRUN -eq 1 ]; then
        echo -e "\033[0;33;40m# $(printf "'%s' " "$@")\033[0;0m" >&2
    else
        [ $VERBOSE -eq 1 ] \
            && echo -e "\033[0;33;40m# $(printf "'%s' " "$@")\033[0;0m" >&2
        "$@"
    fi
}

prompt_yn() {
    local msg="${1:-confinue?}"
    local resp=''
    while [ "$resp" != 'y' -a "$resp" != 'n' ]; do
        read -n 1 -p "$msg (y|n) > " resp
        echo >&2
    done
    [ "$resp" = 'y' ] && return 0 || return 1
}


# collect args
# ==========================================

[ $# -eq 0 ] && {
    usage
    fail "Missing environment to publish to"
}


VERBOSE=0
DRYRUN=0

upload_only=0
upload_args=(
    upload
)
build_only=0
build_dir=dist
env=


while [ $# -gt 0 ]; do
    arg="$1"
    shift
    case "$arg" in
        --dry-run|-d)
            DRYRUN=1
            ;;
        --verbose|-v)
            VERBOSE=1
            ;;
        --help|-h)
            usage
            exit
            ;;
        --build-only|-b)
            [ $upload_only -eq 1 ] && fail "Cannot use --build-only and --upload-only together"
            build_only=1
            ;;
        --upload-only|-u)
            [ $build_only -eq 1 ] && fail "Cannot use --build-only and --upload-only together"
            upload_only=1
            ;;
        *)
            [ -n "$env" ] && fail "Env of '$env' already given"
            [ "$arg" = test -o "$arg" = live ] || {
                usage
                fail "Invalid environment"
            }
            env="$arg"
            ;;
    esac
done

[ "$env" = test ] && {
    upload_args+=(--repository testpypi)
    build_dir=dist-test
}


# script body
# ==========================================

[ $VERBOSE -eq 1 ] && set -x

cd "$BASE_DIR" || fail

build_version=$(python3 -m build --version) \
    || fail "Please install 'build': python3 -m pip install -r requirements-build.txt"
twine_version=$(python3 -m twine --version) \
    || fail "Please install 'twine': python3 -m pip install -r requirements-build.txt"

[ $upload_only -eq 0 ] && {
    echo -e "\033[0;33mBuilding to \033[1m"$(pwd -P)/$build_dir"\033[0;33m using \033[1m$build_version\033[0m" >&2
    python3 -m build --outdir "$build_dir" || fail
}

[ $build_only -eq 0 ] && {
    echo -e "\033[0;33mSending to PyPI: \033[1m${upload_args[@]}\033[0m" >&2
    python3 -m twine "${upload_args[@]}" "$build_dir"/* || fail
}

[ $VERBOSE -eq 1 ] && set -x
exit 0
