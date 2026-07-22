"""Privilege handling and process execution.

Reads never require privileges (pwd/grp modules). Writes go through
pw(8), prefixed with doas (or sudo as a fallback) unless we are
already running as root.
"""

import os
import shutil
import subprocess


class AdminError(Exception):
    """Raised when a privileged operation fails or cannot be attempted."""


def find_privilege_tool():
    """Return 'doas' or 'sudo', whichever exists, else None."""
    for tool in ("doas", "sudo"):
        if shutil.which(tool):
            return tool
    return None


def admin_prefix():
    """Command prefix needed to run an administrative command."""
    if hasattr(os, "geteuid") and os.geteuid() == 0:
        return []
    tool = find_privilege_tool()
    if tool is None:
        raise AdminError(
            "Neither doas nor sudo was found.\n\n"
            "Install doas (pkg install doas) and add your account to "
            "wheel with a rule such as:\n\n"
            "    permit persist :wheel"
        )
    return [tool]


def run_admin(command, input_text=None):
    """Run a privileged command; return CompletedProcess."""
    prefix = admin_prefix()
    try:
        return subprocess.run(
            prefix + command,
            capture_output=True,
            text=True,
            input=input_text,
        )
    except OSError as exc:
        raise AdminError("Failed to execute %s: %s" % (command[0], exc))


def check(result, action):
    """Raise AdminError with pw's message if the command failed."""
    if result.returncode != 0:
        detail = (result.stderr or result.stdout or "").strip()
        raise AdminError("%s failed.\n%s" % (action, detail or
                                             "No error output (was the "
                                             "doas password prompt "
                                             "cancelled?)"))
    return result


def read_shells():
    """Valid login shells from /etc/shells (best effort)."""
    shells = []
    try:
        with open("/etc/shells", "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if line and not line.startswith("#"):
                    shells.append(line)
    except OSError:
        pass
    return shells


def read_login_classes(path="/etc/login.conf"):
    """Login class names from /etc/login.conf (best effort).

    Records start in column 0; continuation lines are indented. A
    record head may list several names separated by '|'.
    """
    classes = []
    try:
        with open(path, "r", encoding="utf-8") as fh:
            for line in fh:
                if not line.strip() or line[0] in " \t#":
                    continue
                head = line.split(":", 1)[0]
                for name in head.split("|"):
                    name = name.strip()
                    if name and name not in classes:
                        classes.append(name)
    except OSError:
        pass
    return classes
