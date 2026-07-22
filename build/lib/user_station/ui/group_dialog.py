"""Create/edit group dialog with explicit GID control."""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from .. import config


class GroupDialog(Gtk.Dialog):
    def __init__(self, parent, mode="create", group=None,
                 usernames=None, next_gid=None):
        title = ("Create Group" if mode == "create"
                 else "Edit Group: %s" % group.name)
        super().__init__(title=title, transient_for=parent, modal=True)
        self.mode = mode
        self.add_button("_Cancel", Gtk.ResponseType.CANCEL)
        self.add_button("_OK", Gtk.ResponseType.OK)
        self.set_default_response(Gtk.ResponseType.OK)

        usernames = usernames or []
        grid = Gtk.Grid(row_spacing=6, column_spacing=12)
        grid.set_border_width(12)

        self.name = Gtk.Entry()
        self.name.set_activates_default(True)
        grid.attach(Gtk.Label(label="Group name:", xalign=1.0), 0, 0, 1, 1)
        self.name.set_hexpand(True)
        grid.attach(self.name, 1, 0, 1, 1)

        adj = Gtk.Adjustment(value=next_gid or config.FIRST_REGULAR_GID,
                             lower=0, upper=config.MAX_ID,
                             step_increment=1, page_increment=100)
        self.gid = Gtk.SpinButton(adjustment=adj, numeric=True)
        grid.attach(Gtk.Label(label="GID:", xalign=1.0), 0, 1, 1, 1)
        grid.attach(self.gid, 1, 1, 1, 1)

        hint = Gtk.Label(xalign=0)
        hint.set_markup(
            "<small>Keep GIDs identical across machines that share "
            "files over NFS.</small>")
        grid.attach(hint, 1, 2, 1, 1)

        frame = Gtk.Frame(label="Members")
        self.member_store = Gtk.ListStore(bool, str)
        current = set(group.members) if group else set()
        for name in usernames:
            self.member_store.append([name in current, name])
        view = Gtk.TreeView(model=self.member_store)
        view.set_headers_visible(False)
        toggle = Gtk.CellRendererToggle()
        toggle.connect("toggled", self._on_toggled)
        view.append_column(Gtk.TreeViewColumn("", toggle, active=0))
        view.append_column(
            Gtk.TreeViewColumn("User", Gtk.CellRendererText(), text=1))
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

        if mode == "edit":
            self.name.set_text(group.name)
            self.name.set_sensitive(False)
            self.gid.set_value(group.gid)

        self.show_all()

    def _on_toggled(self, renderer, path):
        self.member_store[path][0] = not self.member_store[path][0]

    def get_data(self):
        return {
            "name": self.name.get_text().strip(),
            "gid": self.gid.get_value_as_int(),
            "members": [row[1] for row in self.member_store if row[0]],
        }
