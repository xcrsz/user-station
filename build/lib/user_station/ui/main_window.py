"""Main window: Users and Groups tabs backed by the real system
databases, with toolbar actions wired to pw(8)."""

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk

from .. import config, VERSION
from ..backend import users as be_users
from ..backend import groups as be_groups
from ..backend.system import AdminError
from .user_dialog import UserDialog
from .group_dialog import GroupDialog


class MainWindow(Gtk.Window):
    def __init__(self):
        super().__init__(title="%s %s" % (config.APP_TITLE, VERSION))
        self.set_default_size(950, 620)
        self.show_system = False

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.add(vbox)
        vbox.pack_start(self._build_toolbar(), False, False, 0)

        self.notebook = Gtk.Notebook()
        vbox.pack_start(self.notebook, True, True, 0)

        self.notebook.append_page(self._build_users_page(),
                                  Gtk.Label(label="Users"))
        self.notebook.append_page(self._build_groups_page(),
                                  Gtk.Label(label="Groups"))

        self.statusbar = Gtk.Statusbar()
        self.status_ctx = self.statusbar.get_context_id("main")
        vbox.pack_start(self.statusbar, False, False, 0)

        self.refresh()

    # -- construction ---------------------------------------------

    def _build_toolbar(self):
        bar = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=6)
        bar.set_border_width(6)

        for label, cb in (("Add", self.on_add),
                          ("Edit", self.on_edit),
                          ("Delete", self.on_delete),
                          ("Refresh", lambda b: self.refresh())):
            btn = Gtk.Button(label=label)
            btn.connect("clicked", cb)
            bar.pack_start(btn, False, False, 0)

        self.search = Gtk.SearchEntry()
        self.search.set_placeholder_text("Filter by name...")
        self.search.connect("search-changed", self._on_search)
        bar.pack_start(self.search, True, True, 12)

        toggle = Gtk.CheckButton(label="Show system accounts")
        toggle.connect("toggled", self._on_show_system)
        bar.pack_end(toggle, False, False, 0)
        return bar

    def _build_users_page(self):
        # name, uid, gid, full name, home, shell, groups
        self.user_store = Gtk.ListStore(str, int, int, str, str, str, str)
        self.user_filter = self.user_store.filter_new()
        self.user_filter.set_visible_func(self._user_visible)
        self.user_view = Gtk.TreeView(model=self.user_filter)
        self.user_view.connect("row-activated",
                               lambda *a: self.on_edit(None))
        for i, title in enumerate(("Username", "UID", "GID", "Full name",
                                   "Home", "Shell", "Groups")):
            col = Gtk.TreeViewColumn(title, Gtk.CellRendererText(), text=i)
            col.set_sort_column_id(i)
            col.set_resizable(True)
            self.user_view.append_column(col)
        scrolled = Gtk.ScrolledWindow()
        scrolled.add(self.user_view)
        return scrolled

    def _build_groups_page(self):
        # name, gid, members
        self.group_store = Gtk.ListStore(str, int, str)
        self.group_filter = self.group_store.filter_new()
        self.group_filter.set_visible_func(self._group_visible)
        self.group_view = Gtk.TreeView(model=self.group_filter)
        self.group_view.connect("row-activated",
                                lambda *a: self.on_edit(None))
        for i, title in enumerate(("Group", "GID", "Members")):
            col = Gtk.TreeViewColumn(title, Gtk.CellRendererText(), text=i)
            col.set_sort_column_id(i)
            col.set_resizable(True)
            self.group_view.append_column(col)
        scrolled = Gtk.ScrolledWindow()
        scrolled.add(self.group_view)
        return scrolled

    # -- filtering -------------------------------------------------

    def _needle(self):
        return self.search.get_text().strip().lower()

    def _user_visible(self, model, it, data):
        needle = self._needle()
        if not needle:
            return True
        return (needle in model[it][0].lower()
                or needle in model[it][3].lower())

    def _group_visible(self, model, it, data):
        needle = self._needle()
        if not needle:
            return True
        return (needle in model[it][0].lower()
                or needle in model[it][2].lower())

    def _on_search(self, entry):
        self.user_filter.refilter()
        self.group_filter.refilter()

    def _on_show_system(self, toggle):
        self.show_system = toggle.get_active()
        self.refresh()

    # -- data ------------------------------------------------------

    def refresh(self):
        self.user_store.clear()
        users = be_users.list_users(self.show_system)
        for u in users:
            self.user_store.append([u.name, u.uid, u.gid, u.comment,
                                    u.home, u.shell, ", ".join(u.groups)])
        self.group_store.clear()
        groups = be_groups.list_groups(self.show_system)
        for g in groups:
            self.group_store.append([g.name, g.gid,
                                     ", ".join(g.members)])
        self.statusbar.pop(self.status_ctx)
        self.statusbar.push(
            self.status_ctx,
            "%d users, %d groups  |  next free UID: %d, GID: %d"
            % (len(users), len(groups),
               be_users.next_free_uid(), be_groups.next_free_gid()))

    def _selected(self, view, column=0):
        model, it = view.get_selection().get_selected()
        if it is None:
            return None
        return model[it][column]

    def _on_users_tab(self):
        return self.notebook.get_current_page() == 0

    # -- dialogs / feedback ---------------------------------------

    def error(self, message):
        dlg = Gtk.MessageDialog(transient_for=self, modal=True,
                                message_type=Gtk.MessageType.ERROR,
                                buttons=Gtk.ButtonsType.OK,
                                text=message)
        dlg.run()
        dlg.destroy()

    # -- actions ---------------------------------------------------

    def on_add(self, button):
        if self._on_users_tab():
            self._add_user()
        else:
            self._add_group()

    def on_edit(self, button):
        if self._on_users_tab():
            self._edit_user()
        else:
            self._edit_group()

    def on_delete(self, button):
        if self._on_users_tab():
            self._delete_user()
        else:
            self._delete_group()

    # -- user actions ----------------------------------------------

    def _validate_user_data(self, data, mode, original=None):
        problems = []
        if mode == "create":
            problems += be_users.validate_username(data["name"])
            if not problems and be_users.username_exists(data["name"]):
                problems.append("User '%s' already exists." % data["name"])
        owner = be_users.uid_owner(data["uid"])
        if owner and (original is None or owner != original.name):
            problems.append("UID %d is already used by '%s'."
                            % (data["uid"], owner))
        if data["password"] != data["password_confirm"]:
            problems.append("Passwords do not match.")
        if not data["home"]:
            problems.append("Home directory is required.")
        if not data["shell"]:
            problems.append("Shell is required.")
        return problems

    def _add_user(self):
        dlg = UserDialog(self, mode="create",
                         group_names=be_groups.all_group_names(),
                         next_uid=be_users.next_free_uid())
        try:
            while dlg.run() == Gtk.ResponseType.OK:
                data = dlg.get_data()
                problems = self._validate_user_data(data, "create")
                if problems:
                    self.error("\n".join(problems))
                    continue
                try:
                    be_users.add_user(
                        name=data["name"], uid=data["uid"],
                        comment=data["comment"], home=data["home"],
                        shell=data["shell"],
                        primary_group=data["primary_group"],
                        groups=data["groups"],
                        create_home=data["create_home"],
                        password=data["password"] or None)
                except AdminError as exc:
                    self.error(str(exc))
                    continue
                break
        finally:
            dlg.destroy()
        self.refresh()

    def _edit_user(self):
        name = self._selected(self.user_view)
        if not name:
            self.error("Select a user first.")
            return
        user = be_users.get_user(name)
        if user is None:
            self.refresh()
            return
        dlg = UserDialog(self, mode="edit", user=user,
                         group_names=be_groups.all_group_names())
        try:
            while dlg.run() == Gtk.ResponseType.OK:
                data = dlg.get_data()
                problems = self._validate_user_data(data, "edit",
                                                    original=user)
                if problems:
                    self.error("\n".join(problems))
                    continue
                try:
                    be_users.modify_user(
                        name=user.name,
                        uid=(data["uid"]
                             if data["uid"] != user.uid else None),
                        comment=(data["comment"]
                                 if data["comment"] != user.comment
                                 else None),
                        home=(data["home"]
                              if data["home"] != user.home else None),
                        shell=(data["shell"]
                               if data["shell"] != user.shell else None),
                        primary_group=data["primary_group"],
                        groups=data["groups"])
                    if data["password"]:
                        be_users.set_password(user.name, data["password"])
                except AdminError as exc:
                    self.error(str(exc))
                    continue
                break
        finally:
            dlg.destroy()
        self.refresh()

    def _delete_user(self):
        name = self._selected(self.user_view)
        if not name:
            self.error("Select a user first.")
            return
        dlg = Gtk.MessageDialog(
            transient_for=self, modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text="Delete user '%s'?" % name)
        dlg.format_secondary_text(
            "The account and its group memberships will be removed.")
        remove_home = Gtk.CheckButton(
            label="Also delete the home directory")
        box = dlg.get_message_area()
        box.pack_start(remove_home, False, False, 0)
        remove_home.show()
        response = dlg.run()
        wipe = remove_home.get_active()
        dlg.destroy()
        if response != Gtk.ResponseType.OK:
            return
        try:
            be_users.delete_user(name, remove_home=wipe)
        except AdminError as exc:
            self.error(str(exc))
        self.refresh()

    # -- group actions ---------------------------------------------

    def _all_usernames(self):
        return [u.name for u in be_users.list_users(include_system=True)]

    def _validate_group_data(self, data, mode, original=None):
        problems = []
        if mode == "create":
            problems += be_groups.validate_groupname(data["name"])
            if not problems and be_groups.group_exists(data["name"]):
                problems.append("Group '%s' already exists."
                                % data["name"])
        owner = be_groups.gid_owner(data["gid"])
        if owner and (original is None or owner != original.name):
            problems.append("GID %d is already used by '%s'."
                            % (data["gid"], owner))
        return problems

    def _add_group(self):
        dlg = GroupDialog(self, mode="create",
                          usernames=self._all_usernames(),
                          next_gid=be_groups.next_free_gid())
        try:
            while dlg.run() == Gtk.ResponseType.OK:
                data = dlg.get_data()
                problems = self._validate_group_data(data, "create")
                if problems:
                    self.error("\n".join(problems))
                    continue
                try:
                    be_groups.add_group(data["name"], data["gid"],
                                        members=data["members"])
                except AdminError as exc:
                    self.error(str(exc))
                    continue
                break
        finally:
            dlg.destroy()
        self.refresh()

    def _edit_group(self):
        name = self._selected(self.group_view)
        if not name:
            self.error("Select a group first.")
            return
        record = None
        for g in be_groups.list_groups(include_system=True):
            if g.name == name:
                record = g
                break
        if record is None:
            self.refresh()
            return
        dlg = GroupDialog(self, mode="edit", group=record,
                          usernames=self._all_usernames())
        try:
            while dlg.run() == Gtk.ResponseType.OK:
                data = dlg.get_data()
                problems = self._validate_group_data(data, "edit",
                                                     original=record)
                if problems:
                    self.error("\n".join(problems))
                    continue
                try:
                    be_groups.modify_group(
                        record.name,
                        gid=(data["gid"]
                             if data["gid"] != record.gid else None),
                        members=data["members"])
                except AdminError as exc:
                    self.error(str(exc))
                    continue
                break
        finally:
            dlg.destroy()
        self.refresh()

    def _delete_group(self):
        name = self._selected(self.group_view)
        if not name:
            self.error("Select a group first.")
            return
        dlg = Gtk.MessageDialog(
            transient_for=self, modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.OK_CANCEL,
            text="Delete group '%s'?" % name)
        dlg.format_secondary_text(
            "Users whose primary group this is will prevent deletion; "
            "reassign them first.")
        response = dlg.run()
        dlg.destroy()
        if response != Gtk.ResponseType.OK:
            return
        try:
            be_groups.delete_group(name)
        except AdminError as exc:
            self.error(str(exc))
        self.refresh()
