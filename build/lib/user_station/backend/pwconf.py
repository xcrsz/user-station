"""Best-effort parser for /etc/pw.conf (see pw.conf(5)).

pw(8) consults this file for its defaults. user-station respects the
same settings so the GUI and the command line agree on UID/GID
ranges, the home prefix, the default shell and login class, and the
extra groups assigned to new accounts. A missing file or missing
keys fall back to the values in config.py.
"""

import os

from .. import config

PW_CONF = "/etc/pw.conf"

_LIST_KEYS = {"shells", "extragroups"}
_INT_KEYS = {"minuid", "maxuid", "mingid", "maxgid",
             "expire_days", "password_days"}


def _unquote(token):
    token = token.strip()
    if len(token) >= 2 and token[0] == '"' and token[-1] == '"':
        token = token[1:-1]
    return token


def load(path=PW_CONF):
    """Parse pw.conf into a dict. Unknown keys are kept as strings."""
    conf = {}
    try:
        with open(path, "r", encoding="utf-8") as fh:
            lines = fh.readlines()
    except OSError:
        return conf
    for line in lines:
        line = line.split("#", 1)[0].strip()
        if not line or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip().lower()
        value = value.strip()
        if key in _LIST_KEYS:
            items = [_unquote(v) for v in value.split(",")]
            conf[key] = [v for v in items if v]
        elif key in _INT_KEYS:
            try:
                conf[key] = int(_unquote(value))
            except ValueError:
                pass
        else:
            conf[key] = _unquote(value)
    return conf


def min_uid(conf=None):
    conf = load() if conf is None else conf
    return conf.get("minuid", config.FIRST_REGULAR_UID)


def max_uid(conf=None):
    conf = load() if conf is None else conf
    return conf.get("maxuid", config.MAX_ID)


def min_gid(conf=None):
    conf = load() if conf is None else conf
    return conf.get("mingid", config.FIRST_REGULAR_GID)


def max_gid(conf=None):
    conf = load() if conf is None else conf
    return conf.get("maxgid", config.MAX_ID)


def home_prefix(conf=None):
    conf = load() if conf is None else conf
    return conf.get("home") or config.DEFAULT_HOME_PREFIX


def default_class(conf=None):
    conf = load() if conf is None else conf
    return conf.get("defaultclass", "")


def extra_groups(conf=None):
    conf = load() if conf is None else conf
    return conf.get("extragroups", [])


def default_shell(conf=None):
    """pw.conf stores the shell as a basename ('sh'); resolve it
    against /etc/shells and the configured defaults."""
    conf = load() if conf is None else conf
    shell = conf.get("defaultshell", "")
    if not shell:
        return None
    if "/" in shell:
        return shell
    from .system import read_shells
    for candidate in read_shells() + config.DEFAULT_SHELLS:
        if os.path.basename(candidate) == shell:
            return candidate
    return shell
