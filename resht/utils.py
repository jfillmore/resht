import decimal
import functools
import re

from . import types


def get_args(my_args:dict = None, args:dict = None, merge: bool = False) -> dict:
    """
    Returns a dict of args based on the initial args given in `my_args`.
    Ignores extra args in `args` unless `merge` is set.
    """
    final_args = my_args.copy()
    if not args:
        return final_args
    for arg, val in args.items():
        if arg in my_args or merge:
            final_args[arg] = val
    return final_args


def pretty_path(path, absolute=False, no_trailing=True):
    if no_trailing:
        path = path.rstrip('/')
    if absolute:
        path = '/' + path
    regex = re.compile(r'/+')
    path = regex.sub('/', path)
    return path


def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


def get_duration(ms:int) -> types.Duration:
    """
    Describe a time specified in duration of milliseconds, as an absolute value
    (e.g. negatives are treated as positive).
    """
    ms = abs(ms)
    duration = functools.partial(types.Duration, ms=ms)
    dec_p2 = decimal.Decimal('0.00')

    if ms < 1000:
        return duration(desc=f'{ms}ms')
    secs = ms / 1000
    if secs < 60:
        return duration(
            desc=str(decimal.Decimal(secs).quantize(dec_p2)) + 's'
        )
    # don't worry about MS precision as we go up
    secs = int(secs)
    mins = int(secs / 60)
    secs -= mins * 60
    if mins < 60:
        return duration(desc=f'{mins}m, {secs}m')
    hours = int(mins / 60)
    mins -= hours * 60
    if hours < 24:
        return duration(desc=f'{hours}h, {mins}m, {secs}s')
    days = int(hours / 24)
    hours -= days * 24
    return duration(desc=f'{days}d, {hours}h, {mins}m, {secs}s')


def get_byte_size(val, precision:int = 2) -> types.ByteSize:
    """
    Describe, with arbitrary precision, bytes up to the PB range. Uses a base
    of 1000, not 1024.
    """
    units = ['B', 'KB', 'MB', 'GB', 'TB', 'PB']
    prev_limit = 0
    best_unit = None
    remainder = val
    for i, unit in enumerate(units):
        best_unit = unit
        unit_limit = 10 ** ((i + 1) * 3)
        if remainder < unit_limit:
            break
        prev_limit = unit_limit
    if prev_limit:
        remainder = round(remainder / prev_limit, precision)
    return types.ByteSize(value=remainder, unit=best_unit, num_bytes=val)
