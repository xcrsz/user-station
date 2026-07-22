"""Group operations. Reads via grp module, writes via pw(8)."""

import grp
import re
from dataclasses import dataclass, field

from .. import config
from . import pwconf
from .system import run_admin, check


GROUPNAME_RE = re.compile(r"^[a-z_][a-z0-9._-]*$")


@dataclass
class GroupRecord:
    name: str
    gid: int
    members: list = field(default_factory=list)


def list_groups(include_system=False):
    records = []
    for g in grp.getgrall():
        if not include_system:
            if g.gr_gid < pwconf.min_gid() or g.gr_gid > pwconf.max_gid():
                # Always show the groups admins actually assign.
                if g.gr_name not in config.SUGGESTED_GROUPS:
                    continue
        records.append(GroupRecord(
            name=g.gr_name,
            gid=g.gr_gid,
            members=sorted(g.gr_mem),
        ))
    records.sort(key=lambda r: r.gid)
    return records


def all_group_names():
    return sorted(g.gr_name for g in grp.getgrall())


def group_exists(name):
    try:
        grp.getgrnam(name)
        return True
    except KeyError:
        return False


def gid_owner(gid):
    try:
        return grp.getgrgid(gid).gr_name
    except KeyError:
        return None


def group_name_for_gid(gid):
    return gid_owner(gid)


def next_free_gid(start=None):
    """Lowest unused GID inside the pw.conf mingid..maxgid range."""
    start = start if start is not None else pwconf.min_gid()
    ceiling = pwconf.max_gid()
    used = {g.gr_gid for g in grp.getgrall()}
    gid = start
    while gid in used and gid <= ceiling:
        gid += 1
    return gid


def validate_groupname(name):
    problems = []
    if not name:
        problems.append("Group name is required.")
        return problems
    if len(name) > 32:
        problems.append("Group name must be at most 32 characters.")
    if not GROUPNAME_RE.match(name):
        problems.append(
            "Group name must start with a lowercase letter or underscore "
            "and contain only lowercase letters, digits, '.', '-' or '_'.")
    return problems


def add_group(name, gid, members=None):
    cmd = ["pw", "groupadd", name, "-g", str(gid)]
    if members:
        cmd += ["-M", ",".join(members)]
    return check(run_admin(cmd), "Creating group '%s'" % name)


def modify_group(name, gid=None, members=None):
    """members (a list) replaces the full member set; None leaves it."""
    cmd = ["pw", "groupmod", name]
    changed = False
    if gid is not None:
        cmd += ["-g", str(gid)]
        changed = True
    if members is not None:
        cmd += ["-M", ",".join(members)]
        changed = True
    if not changed:
        return None
    return check(run_admin(cmd), "Modifying group '%s'" % name)


def delete_group(name):
    return check(run_admin(["pw", "groupdel", name]),
                 "Deleting group '%s'" % name)
