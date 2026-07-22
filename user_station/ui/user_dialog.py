"""Create/edit user dialog.

The UID field sits directly under the username with a next-free
suggestion and a reminder that NFS matches ownership by numeric ID.
"""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from .. import config
from ..backend import system as be_system

PER_USER_GROUP = "(new group named after the user)"


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

        group_names = group_names or []
        grid = Gtk.Grid(row_spacing=6, column_spacing=12)
        grid.set_border_width(12)
        self._row = 0

        # Username
        self.username = Gtk.Entry()
        self.username.set_activates_default(True)
        self._attach(grid, "Username:", self.username)

        # UID, prominent and always editable
        adj = Gtk.Adjustment(value=next_uid or config.FIRST_REGULAR_UID,
                             lower=0, upper=config.MAX_ID,
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

        # Shell
        self.shell = Gtk.ComboBoxText.new_with_entry()
        shells = list(dict.fromkeys(
            be_system.read_shells() + config.DEFAULT_SHELLS))
        for s in shells:
            self.shell.append_text(s)
        self.shell.set_active(0)
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

        # Secondary groups
        frame = Gtk.Frame(label="Additional groups")
        self.group_store = Gtk.ListStore(bool, str)
        current = set(user.groups) if user else set()
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

        box = self.get_content_area()
        box.set_spacing(8)
        box.pack_start(grid, False, False, 0)
        box.pack_start(frame, True, True, 6)

        if mode == "create":
            self.username.connect("changed", self._on_username_changed)
        else:
            self._fill_from(user, group_names)

        self.show_all()

    # -- helpers ---------------------------------------------------

    def _attach(self, grid, label, widget):
        lab = Gtk.Label(label=label, xalign=1.0)
        grid.attach(lab, 0, self._row, 1, 1)
        widget.set_hexpand(True)
        grid.attach(widget, 1, self._row, 1, 1)
        self._row += 1

    def _on_group_toggled(self, renderer, path):
        self.group_store[path][0] = not self.group_store[path][0]

    def _on_username_changed(self, entry):
        name = entry.get_text().strip()
        self.home.set_text(
            "%s/%s" % (config.DEFAULT_HOME_PREFIX, name) if name else "")

    def _fill_from(self, user, group_names):
        self.username.set_text(user.name)
        self.username.set_sensitive(False)
        self.uid.set_value(user.uid)
        self.fullname.set_text(user.comment)
        self.home.set_text(user.home)
        # primary group
        from ..backend import groups as be_groups
        primary_name = be_groups.group_name_for_gid(user.gid)
        if primary_name in group_names:
            self.primary.set_active(group_names.index(primary_name))
        # shell: select or type into the entry
        entry = self.shell.get_child()
        entry.set_text(user.shell)

    def get_data(self):
        primary = self.primary.get_active_text()
        if primary == PER_USER_GROUP:
            primary = None
        groups = [row[1] for row in self.group_store if row[0]]
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
        }
