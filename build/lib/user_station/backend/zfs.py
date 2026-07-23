"""ZFS home dataset support.

When the home prefix (e.g. /home) is the mountpoint of a ZFS
dataset, user-station can create each new home directory as a child
dataset, so every account gets its own snapshots, quotas and
properties. Listing datasets is unprivileged; create, destroy and
chown go through doas.
"""

import os
import shutil
import subprocess

from .system import run_admin, check


def zfs_available():
    return shutil.which("zfs") is not None


def _list_datasets():
    """Return [(name, mountpoint)] from unprivileged zfs list."""
    if not zfs_available():
        return []
    try:
        result = subprocess.run(
            ["zfs", "list", "-H", "-o", "name,mountpoint"],
            capture_output=True, text=True)
    except OSError:
        return []
    if result.returncode != 0:
        return []
    rows = []
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) == 2:
            rows.append((parts[0], parts[1]))
    return rows


def dataset_at(path):
    """Dataset whose mountpoint is exactly this path, or None.

    Also tries the resolved path, covering the classic FreeBSD
    /home -> /usr/home symlink.
    """
    if not path:
        return None
    datasets = _list_datasets()
    for name, mountpoint in datasets:
        if mountpoint == path:
            return name
    real = os.path.realpath(path)
    if real != path:
        for name, mountpoint in datasets:
            if mountpoint == real:
                return name
    return None


def home_parent_dataset(home_prefix):
    """Dataset backing the home prefix (e.g. zroot/home for /home)."""
    return dataset_at(home_prefix)


def create_home_dataset(parent, username):
    """zfs create parent/username; the mountpoint is inherited, so
    the child lands at <parent mountpoint>/<username>."""
    name = "%s/%s" % (parent, username)
    check(run_admin(["zfs", "create", name]),
          "Creating ZFS dataset '%s'" % name)
    return name


def destroy_dataset(name):
    check(run_admin(["zfs", "destroy", "-r", name]),
          "Destroying ZFS dataset '%s'" % name)


def chown_recursive(path, uid, gid):
    check(run_admin(["chown", "-R", "%d:%d" % (uid, gid), path]),
          "Setting ownership on '%s'" % path)
