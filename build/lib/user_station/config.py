"""Static configuration for user-station."""

APP_NAME = "user-station"
APP_TITLE = "User Station"

# FreeBSD convention: adduser(8) starts regular accounts at 1001.
FIRST_REGULAR_UID = 1001
FIRST_REGULAR_GID = 1001
MAX_ID = 65533

# Shells offered in the dialog; merged with /etc/shells at runtime.
DEFAULT_SHELLS = [
    "/bin/sh",
    "/bin/csh",
    "/bin/tcsh",
    "/usr/local/bin/bash",
    "/usr/local/bin/zsh",
    "/usr/local/bin/fish",
    "/usr/sbin/nologin",
]

# Groups commonly assigned on FreeBSD/GhostBSD desktops. These are
# only suggestions for ordering; the dialog lists every real group.
SUGGESTED_GROUPS = [
    "wheel",
    "operator",
    "video",
    "webcamd",
    "dialer",
    "games",
]

DEFAULT_HOME_PREFIX = "/home"
