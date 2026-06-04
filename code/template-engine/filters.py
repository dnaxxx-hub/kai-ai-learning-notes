def do_upper(s):
    return str(s).upper()


def do_lower(s):
    return str(s).lower()


def do_capitalize(s):
    return str(s).capitalize()


def do_title(s):
    return str(s).title()


def do_trim(s):
    return str(s).strip()


def do_length(s):
    return len(str(s))


def do_default(value, default=''):
    return value if value else default


def do_join(value, sep=''):
    return sep.join(str(v) for v in value) if isinstance(value, (list, tuple)) else str(value)


def do_safe(s):
    return s


default_filters = {
    'upper': do_upper,
    'lower': do_lower,
    'capitalize': do_capitalize,
    'title': do_title,
    'trim': do_trim,
    'length': do_length,
    'default': do_default,
    'join': do_join,
    'safe': do_safe,
}
