"""Create/edit user dialog.

The UID field sits directly under the username with a next-free
suggestion and a reminder that NFS matches ownership by numeric ID.
Defaults (home prefix, shell, login class, extra groups, UID range)
come from /etc/pw.conf when present. Advanced options hold the login
class and ZFS home dataset controls.
"""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from .. import config
from ..backend import pwconf
from ..backend import system as be_system
from ..backend import zfs as be_zfs

PER_USER_GROUP = "(new group named after the user)"
KEEP_CLASS = "(keep current / system default)"


class UserDialog(Gtk.Dialog):
    def __init__(self, parent, mode="create", user=None,
                 group_names=None, next_uid=None):
        title = ("Create User" if mode == "create"
                 else "Edit User: %s" % user.name)
        super().__init__(title=title, transient_for=parent, modal=True)
        self.mode = mode
        self.user = user
        self.add_button("_Cancel", Gtk.ResponseType.CANCEL)
        self.add_button("_OK", Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)

        self._conf = pwconf.load()
        self._home_prefix = pwconf.home_prefix(self._conf)

        group_names = group_names or []
        grid = Gtk.Grid(row_spacing=6, column_spacing=12)
        grid.set_border_width(12)
        self._row = 0

        # Username
        self.username = Gtk.Entry()
        self.username.set_activates_default(True)
        self._attach(grid, "Username:", self.username)

        # UID, prominent and always editable; range from pw.conf
        adj = Gtk.Adjustment(
            value=next_uid or pwconf.min_uid(self._conf),
            lower=0, upper=pwconf.max_uid(self._conf),
            step_increment=1, page_increment=100)
        self.uid = Gtk.SpinButton(adjustment=adj, numeric=True)
        self._attach(grid, "UID:", self.uid)
        hint = Gtk.Label(xalign=0)
        hint.set_markup(
            "<small>NFS matches file ownership by numeric UID/GID, not "
            "by name.\nUse the same UID on every machine that shares "
            "this account's files.</small>")
        grid.attach(hint, 1, self._row, 1, 1)
        self._row += 1

        # Full name
        self.fullname = Gtk.Entry()
        self._attach(grid, "Full name:", self.fullname)

        # Primary group
        self.primary = Gtk.ComboBoxText()
        if mode == "create":
            self.primary.append_text(PER_USER_GROUP)
        for name in group_names:
            self.primary.append_text(name)
        self.primary.set_active(0)
        self._attach(grid, "Primary group:", self.primary)

        # Shell (default from pw.conf if it names one)
        self.shell = Gtk.ComboBoxText.new_with_entry()
        shells = list(dict.fromkeys(
            be_system.read_shells() + config.DEFAULT_SHELLS))
        default_shell = pwconf.default_shell(self._conf)
        if default_shell and default_shell not in shells:
            shells.insert(0, default_shell)
        for s in shells:
            self.shell.append_text(s)
        self.shell.set_active(
            shells.index(default_shell) if default_shell in shells else 0)
        self._attach(grid, "Shell:", self.shell)

        # Home
        self.home = Gtk.Entry()
        self._attach(grid, "Home directory:", self.home)

        self.create_home = Gtk.CheckButton(label="Create home directory")
        self.create_home.set_active(True)
        if mode == "create":
            grid.attach(self.create_home, 1, self._row, 1, 1)
            self._row += 1

        # Password
        pw_label = ("Password:" if mode == "create"
                    else "New password:")
        self.pw1 = Gtk.Entry(visibility=False)
        self.pw2 = Gtk.Entry(visibility=False)
        self.pw1.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        self.pw2.set_input_purpose(Gtk.InputPurpose.PASSWORD)
        self._attach(grid, pw_label, self.pw1)
        self._attach(grid, "Confirm:", self.pw2)
        pw_hint = Gtk.Label(xalign=0)
        if mode == "create":
            pw_hint.set_markup(
                "<small>Leave blank to create the account with the "
                "password locked.</small>")
        else:
            pw_hint.set_markup(
                "<small>Leave blank to keep the current "
                "password.</small>")
        grid.attach(pw_hint, 1, self._row, 1, 1)
        self._row += 1

        # Secondary groups (pw.conf extragroups pre-checked on create)
        frame = Gtk.Frame(label="Additional groups")
        self.group_store = Gtk.ListStore(bool, str)
        if user:
            current = set(user.groups)
        elif mode == "create":
            current = set(pwconf.extra_groups(self._conf))
        else:
            current = set()
        ordered = ([g for g in config.SUGGESTED_GROUPS
                    if g in group_names] +
                   [g for g in group_names
                    if g not in config.SUGGESTED_GROUPS])
        for name in ordered:
            self.group_store.append([name in current, name])
        view = Gtk.TreeView(model=self.group_store)
        view.set_headers_visible(False)
        toggle = Gtk.CellRendererToggle()
        toggle.connect("toggled", self._on_group_toggled)
        view.append_column(Gtk.TreeViewColumn("", toggle, active=0))
        view.append_column(
            Gtk.TreeViewColumn("Group", Gtk.CellRendererText(), text=1))
        scrolled = Gtk.ScrolledWindow()
        scrolled.set_policy(Gtk.PolicyType.NEVER,
                            Gtk.PolicyType.AUTOMATIC)
        scrolled.set_min_content_height(140)
        scrolled.add(view)
        frame.add(scrolled)

        # Advanced options: login class + ZFS home dataset
        advanced = self._build_advanced(mode)

        box = self.get_content_area()
        box.set_spacing(8)
        box.pack_start(grid, False, False, 0)
        box.pack_start(frame, True, True, 6)
        box.pack_start(advanced, False, False, 0)

        if mode == "create":
            self.username.connect("changed", self._on_username_changed)
        else:
            self._fill_from(user, group_names)

        self.show_all()

    # -- advanced options ------------------------------------------

    def _build_advanced(self, mode):
        expander = Gtk.Expander(label="Advanced options")
        agrid = Gtk.Grid(row_spacing=6, column_spacing=12)
        agrid.set_border_width(12)

        # Login class from /etc/login.conf, default from pw.conf
        self.login_class = Gtk.ComboBoxText.new_with_entry()
        self.login_class.append_text(KEEP_CLASS)
        for cls in be_system.read_login_classes():
            self.login_class.append_text(cls)
        default_cls = pwconf.default_class(self._conf)
        if mode == "create" and default_cls:
            self.login_class.get_child().set_text(default_cls)
        else:
            self.login_class.set_active(0)
        agrid.attach(Gtk.Label(label="Login class:", xalign=1.0),
                     0, 0, 1, 1)
        self.login_class.set_hexpand(True)
        agrid.attach(self.login_class, 1, 0, 1, 1)
        cls_hint = Gtk.Label(xalign=0)
        cls_hint.set_markup(
            "<small>Classes come from /etc/login.conf and control "
            "resource limits and environment.</small>")
        agrid.attach(cls_hint, 1, 1, 1, 1)

        # ZFS home dataset (create mode only)
        self.zfs_parent = None
        self.zfs_home = Gtk.CheckButton()
        if mode == "create":
            if be_zfs.zfs_available():
                self.zfs_parent = be_zfs.home_parent_dataset(
                    self._home_prefix)
            if self.zfs_parent:
                self.zfs_home.set_label(
                    "Create home as ZFS dataset (%s/<username>)"
                    % self.zfs_parent)
                self.zfs_home.connect("toggled", self._on_zfs_toggled)
            else:
                self.zfs_home.set_label(
                    "Create home as ZFS dataset (unavailable: %s is "
                    "not a ZFS mountpoint)" % self._home_prefix)
                self.zfs_home.set_sensitive(False)
            agrid.attach(self.zfs_home, 1, 2, 1, 1)
            zfs_hint = Gtk.Label(xalign=0)
            zfs_hint.set_markup(
                "<small>A per-user dataset gets its own snapshots, "
                "quota and properties, inherited from the "
                "parent.</small>")
            agrid.attach(zfs_hint, 1, 3, 1, 1)

        expander.add(agrid)
        return expander

    # -- helpers ---------------------------------------------------

    def _attach(self, grid, label, widget):
        lab = Gtk.Label(label=label, xalign=1.0)
        grid.attach(lab, 0, self._row, 1, 1)
        widget.set_hexpand(True)
        grid.attach(widget, 1, self._row, 1, 1)
        self._row += 1

    def _on_group_toggled(self, renderer, path):
        self.group_store[path][0] = not self.group_store[path][0]

    def _on_zfs_toggled(self, button):
        # pw -m must still populate skel files into the mounted
        # dataset, so home creation stays on.
        if button.get_active():
            self.create_home.set_active(True)
            self.create_home.set_sensitive(False)
        else:
            self.create_home.set_sensitive(True)

    def _on_username_changed(self, entry):
        name = entry.get_text().strip()
        self.home.set_text(
            "%s/%s" % (self._home_prefix, name) if name else "")

    def _fill_from(self, user, group_names):
        self.username.set_text(user.name)
        self.username.set_sensitive(False)
        self.uid.set_value(user.uid)
        self.fullname.set_text(user.comment)
        self.home.set_text(user.home)
        from ..backend import groups as be_groups
        primary_name = be_groups.group_name_for_gid(user.gid)
        if primary_name in group_names:
            self.primary.set_active(group_names.index(primary_name))
        entry = self.shell.get_child()
        entry.set_text(user.shell)

    def get_data(self):
        primary = self.primary.get_active_text()
        if primary == PER_USER_GROUP:
            primary = None
        groups = [row[1] for row in self.group_store if row[0]]
        login_class = self.login_class.get_child().get_text().strip()
        if login_class == KEEP_CLASS:
            login_class = ""
        return {
            "name": self.username.get_text().strip(),
            "uid": self.uid.get_value_as_int(),
            "comment": self.fullname.get_text().strip(),
            "primary_group": primary,
            "shell": self.shell.get_child().get_text().strip(),
            "home": self.home.get_text().strip(),
            "create_home": self.create_home.get_active(),
            "password": self.pw1.get_text(),
            "password_confirm": self.pw2.get_text(),
            "groups": groups,
            "login_class": login_class or None,
            "zfs_dataset": (self.zfs_parent is not None
                            and self.zfs_home.get_active()),
            "zfs_parent": self.zfs_parent,
        }
