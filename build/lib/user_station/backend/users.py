"""User account operations.

Reads use the pwd/grp modules (no privileges needed). Writes shell
out to pw(8) through backend.system.run_admin.
"""

import grp
import pwd
import re
from dataclasses import dataclass, field

from .. import config
from .system import run_admin, check


USERNAME_RE = re.compile(r"^[a-z_][a-z0-9._-]*\$?$")
MAX_USERNAME_LEN = 32


@dataclass
class UserRecord:
    name: str
    uid: int
    gid: int
    comment: str
    home: str
    shell: str
    groups: list = field(default_factory=list)  # secondary groups


def _secondary_membership():
    """Map username -> sorted list of secondary group names."""
    members = {}
    for g in grp.getgrall():
        for m in g.gr_mem:
            members.setdefault(m, set()).add(g.gr_name)
    return {name: sorted(gs) for name, gs in members.items()}


def list_users(include_system=False):
    """Return a list of UserRecord, sorted by UID."""
    secondary = _secondary_membership()
    records = []
    for p in pwd.getpwall():
        if not include_system:
            if p.pw_uid < config.FIRST_REGULAR_UID or p.pw_uid > config.MAX_ID:
                continue
        records.append(UserRecord(
            name=p.pw_name,
            uid=p.pw_uid,
            gid=p.pw_gid,
            comment=p.pw_gecos.split(",")[0],
            home=p.pw_dir,
            shell=p.pw_shell,
            groups=secondary.get(p.pw_name, []),
        ))
    records.sort(key=lambda r: r.uid)
    return records


def get_user(username):
    try:
        p = pwd.getpwnam(username)
    except KeyError:
        return None
    return UserRecord(
        name=p.pw_name,
        uid=p.pw_uid,
        gid=p.pw_gid,
        comment=p.pw_gecos.split(",")[0],
        home=p.pw_dir,
        shell=p.pw_shell,
        groups=_secondary_membership().get(p.pw_name, []),
    )


def username_exists(name):
    try:
        pwd.getpwnam(name)
        return True
    except KeyError:
        return False


def uid_owner(uid):
    """Return the username holding this UID, or None."""
    try:
        return pwd.getpwuid(uid).pw_name
    except KeyError:
        return None


def next_free_uid(start=None):
    """Lowest unused UID at or above the regular-account floor."""
    start = start if start is not None else config.FIRST_REGULAR_UID
    used = {p.pw_uid for p in pwd.getpwall()}
    uid = start
    while uid in used and uid <= config.MAX_ID:
        uid += 1
    return uid


def validate_username(name):
    """Return a list of problems (empty if valid)."""
    problems = []
    if not name:
        problems.append("Username is required.")
        return problems
    if len(name) > MAX_USERNAME_LEN:
        problems.append("Username must be at most %d characters."
                        % MAX_USERNAME_LEN)
    if not USERNAME_RE.match(name):
        problems.append(
            "Username must start with a lowercase letter or underscore "
            "and contain only lowercase letters, digits, '.', '-' or '_'.")
    return problems


def add_user(name, uid, comment="", home=None, shell=None,
             primary_group=None, groups=None, create_home=True,
             password=None):
    """Create a user with pw useradd.

    primary_group None lets pw create a per-user group with the same
    name (FreeBSD default). An explicit UID is always passed: on NFS
    networks the numeric ID is what controls access, so we never let
    it be implicit.
    """
    cmd = ["pw", "useradd", "-n", name, "-u", str(uid)]
    if comment:
        cmd += ["-c", comment]
    if home:
        cmd += ["-d", home]
    if shell:
        cmd += ["-s", shell]
    if primary_group:
        cmd += ["-g", primary_group]
    if groups:
        cmd += ["-G", ",".join(groups)]
    if create_home:
        cmd += ["-m"]
    if password:
        cmd += ["-h", "0"]
        result = run_admin(cmd, input_text=password + "\n")
    else:
        cmd += ["-h", "-"]  # lock password until one is set
        result = run_admin(cmd)
    return check(result, "Creating user '%s'" % name)


def modify_user(name, uid=None, comment=None, home=None, shell=None,
                primary_group=None, groups=None):
    """Change account fields with pw usermod.

    groups (a list) replaces the full secondary group set; pass None
    to leave membership untouched.
    """
    cmd = ["pw", "usermod", "-n", name]
    changed = False
    if uid is not None:
        cmd += ["-u", str(uid)]
        changed = True
    if comment is not None:
        cmd += ["-c", comment]
        changed = True
    if home is not None:
        cmd += ["-d", home]
        changed = True
    if shell is not None:
        cmd += ["-s", shell]
        changed = True
    if primary_group is not None:
        cmd += ["-g", primary_group]
        changed = True
    if groups is not None:
        cmd += ["-G", ",".join(groups)]
        changed = True
    if not changed:
        return None
    return check(run_admin(cmd), "Modifying user '%s'" % name)


def set_password(name, password):
    """Set a password via stdin (-h 0), never on the command line."""
    result = run_admin(["pw", "usermod", "-n", name, "-h", "0"],
                       input_text=password + "\n")
    return check(result, "Setting password for '%s'" % name)


def delete_user(name, remove_home=False):
    cmd = ["pw", "userdel", "-n", name]
    if remove_home:
        cmd += ["-r"]
    return check(run_admin(cmd), "Deleting user '%s'" % name)
