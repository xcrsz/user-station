# user-station

GTK user and group management tool for GhostBSD and FreeBSD.

## Description

user-station provides a graphical interface for:

- Creating, editing, and removing users
- Managing groups and group membership
- Assigning explicit UID/GID values
- Managing wheel/operator memberships
- NFS-friendly UID/GID administration

Designed for GhostBSD and FreeBSD, with MATE and XFCE.

## Why UID control matters

FreeBSD systems using NFS identify file ownership by numeric ID, not
by name. If `jane` is UID 1500 on the server and UID 1500 on the
client, ownership displays correctly on both machines. user-station
therefore puts the UID field front and center in the user creation
dialog, pre-filled with the next free UID but always editable.

## Requirements

    pkg install python3 py312-pygobject gtk3 doas

## Running

From source:

    ./bin/user-station

Or install:

    python3 setup.py install
    user-station

## Permissions

Reading account information requires no privileges (the standard
passwd/group databases are consulted via the pwd/grp modules).
Administrative operations (create/modify/delete) are executed through
doas, or run pw directly if user-station is started as root.

Example /usr/local/etc/doas.conf:

    permit persist :wheel

## Features

Current:

- [x] User listing (with system-account toggle and search)
- [x] Group listing
- [x] Create / edit / delete users
- [x] Explicit UID assignment with next-free suggestion
- [x] Primary group and secondary group membership (wheel, operator, ...)
- [x] Password set/change via pw -h 0 (never on the command line)
- [x] Create / edit / delete groups with explicit GIDs
- [x] Duplicate UID/GID and username validation
- [x] /etc/pw.conf awareness (UID/GID ranges, home prefix, default
      shell, default login class, extragroups)
- [x] Login class selection from /etc/login.conf (advanced options)
- [x] ZFS home datasets: create the home as a child dataset of the
      dataset backing the home prefix; dataset-aware deletion

Planned:

- [ ] Per-dataset quota/compression controls at creation time
- [ ] LDAP support
- [ ] Jail management
- [ ] Import/export accounts

## License

BSD 2-Clause License
