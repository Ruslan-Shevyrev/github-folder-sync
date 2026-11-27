import tkinter as tk
from tkinter import ttk

import customtkinter as ctk

from ..comparison import validate_login
from ..comparison_cache import save_preferences
from ..settings import load_settings, validate_token_reference
from .app_theme import theme_color
from .dialogs import (
    button_widget, create_dialog, dialog_actions, dialog_entry, label_widget, modal_message, show_dialog,
)
from .localization import tr


TOKEN_HELP_LINES = (
    "token.help_required",
    "token.help_title",
    "token.help_access",
    "token.variable_hint",
)


def token_help(parent, container):
    tooltip = None

    def hide(_event=None):
        nonlocal tooltip
        if tooltip is not None:
            tooltip.destroy()
            tooltip = None

    def show(event):
        nonlocal tooltip
        if tooltip is not None:
            return
        tooltip = tk.Toplevel(parent, background=theme_color("border"))
        tooltip.withdraw()
        tooltip.overrideredirect(True)
        frame = ctk.CTkFrame(tooltip, fg_color=theme_color("field"), corner_radius=0)
        frame.pack(padx=1, pady=1)
        label_widget(frame, text="\n".join(map(tr, TOKEN_HELP_LINES)), justify="left", anchor="w").pack(
            padx=10, pady=5
        )
        tooltip.update_idletasks()
        tooltip.geometry(f"+{event.x_root + 12}+{event.y_root + 18}")
        tooltip.deiconify()

    def open_help():
        hide()
        modal_message(tr(TOKEN_HELP_LINES[0]), "\n".join(map(tr, TOKEN_HELP_LINES[1:])), parent=parent, heading=False)

    button = ctk.CTkButton(container, text="?", width=22, height=22, corner_radius=11,
                           border_width=1, border_color=theme_color("border"), fg_color=theme_color("field"),
                           hover_color=theme_color("hover"), text_color=theme_color("text"), font=("Segoe UI", 13, "bold"),
                           command=open_help)
    button.bind("<Enter>", show, add="+")
    button.bind("<Leave>", hide, add="+")
    button.pack(side="left", padx=(7, 0))


def user_dialog(parent, on_save, *, login="", token=""):
    title = tr("user.edit") if login else tr("user.add")
    dialog, frame = create_dialog(parent, title)
    label_widget(frame, text=tr("user.username")).grid(row=0, column=0, sticky="w")
    entry = dialog_entry(frame, login)
    entry.grid(row=1, column=0, sticky="ew", pady=(6, 10))
    token_heading = ctk.CTkFrame(frame, fg_color="transparent")
    token_heading.grid(row=2, column=0, sticky="w")
    label_widget(token_heading, text=tr("token.optional")).pack(side="left")
    token_help(dialog, token_heading)
    token_row = ctk.CTkFrame(frame, fg_color="transparent")
    token_row.grid(row=3, column=0, sticky="ew", pady=(6, 12))
    token_row.columnconfigure(0, weight=1)
    token_input = dialog_entry(token_row, token)
    token_input.configure(show="*", width=308)
    token_input.grid(row=0, column=0, sticky="ew")

    def toggle_token():
        reveal = bool(token_input.cget("show"))
        token_input.configure(show="" if reveal else "*")
        eye.configure(fg_color=theme_color("hover") if reveal else theme_color("field"))

    eye = ctk.CTkButton(token_row, text="\U0001f441", width=34, height=34, corner_radius=8,
                        border_width=1, border_color=theme_color("border"), fg_color=theme_color("field"),
                        hover_color=theme_color("hover"), text_color=theme_color("text"), font=("Segoe UI Symbol", 16),
                        command=toggle_token)
    eye.grid(row=0, column=1, padx=(8, 0))
    dialog_actions(dialog, frame, 4, entry, lambda: on_save(entry.get().strip(), token_input.get().strip()))


def save_user(preferences_path, name, token):
    validate_login(name)
    validate_token_reference(token)
    data = load_settings(preferences_path)
    existing = next((user for user in data["users"] if user.casefold() == name.casefold()), None)
    if existing is None:
        data["users"][name] = {}
    if token:
        data["users"][existing or name]["token"] = token
    if existing is None or token:
        save_preferences(preferences_path, data)
    return data, existing or name


def add_user(root, preferences_path, on_change):
    def save(name, token):
        data, login = save_user(preferences_path, name, token)
        on_change(data, name=login)
        return True

    user_dialog(root, save)


def open_users(root, preferences_path, selected_user, on_change):
    try:
        preferences = load_settings(preferences_path)
    except (OSError, ValueError) as error:
        modal_message(tr("error.open_users"), str(error), parent=root)
        return
    on_change(preferences)
    dialog, frame = create_dialog(root, tr("user.view"), resizable=True)
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(0, weight=1)
    table = ttk.Treeview(frame, columns=("login",), show="headings", selectmode="browse", height=8)
    table.heading("login", text=tr("user.github"), anchor="w")
    table.column("login", width=360, minwidth=180)
    scrollbar = ctk.CTkScrollbar(frame, orientation="vertical", command=table.yview)
    table.configure(yscrollcommand=scrollbar.set)
    table.grid(row=0, column=0, sticky="nsew")
    scrollbar.grid(row=0, column=1, sticky="ns")
    actions = ctk.CTkFrame(frame, fg_color="transparent")
    actions.grid(row=1, column=0, sticky="ew", pady=(10, 0))

    def update_actions(_event=None):
        state = "normal" if table.selection() else "disabled"
        edit_button.configure(state=state)
        delete_button.configure(state=state)

    def refresh(selected):
        table.delete(*table.get_children())
        for user in sorted(preferences["users"], key=str.casefold):
            table.insert("", "end", iid=user, values=(user,))
        if selected and table.exists(selected):
            table.selection_set(selected)
            table.focus(selected)
            table.see(selected)
        update_actions()

    def edit():
        selection = table.selection()
        if not selection:
            return
        original = selection[0]

        def save(name, token):
            nonlocal preferences
            validate_login(name)
            validate_token_reference(token)
            data = load_settings(preferences_path)
            users = data["users"]
            if original not in users:
                raise ValueError(tr("error.user_missing"))
            if any(user != original and user.casefold() == name.casefold() for user in users):
                raise ValueError(tr("error.user_exists"))
            if name != original:
                users[name] = users.pop(original)
                for profile in data["profiles"].values():
                    if profile["login"] == original:
                        profile["login"] = name
            if token:
                users[name]["token"] = token
            else:
                users[name].pop("token", None)
            save_preferences(preferences_path, data)
            preferences = data
            on_change(data, original, name)
            refresh(name)
            return True

        user_dialog(dialog, save, login=original, token=preferences["users"][original].get("token", ""))

    def delete():
        nonlocal preferences
        selection = table.selection()
        if not selection:
            return
        name = selection[0]
        if not modal_message(
            tr("user.delete_title"),
            tr("user.delete_confirm", name=name),
            parent=dialog, question=True, warning=True,
        ):
            return
        try:
            data = load_settings(preferences_path)
            data["users"].pop(name, None)
            data["profiles"] = {
                key: profile for key, profile in data["profiles"].items()
                if profile["login"] != name
            }
            if data["default_profile"] not in data["profiles"]:
                data["default_profile"] = None
            save_preferences(preferences_path, data)
        except (OSError, ValueError) as error:
            modal_message(tr("error.delete_user"), str(error), parent=dialog)
            return
        preferences = data
        on_change(data, original=name)
        refresh(None)

    def edit_row(event):
        item = table.identify_row(event.y)
        if item:
            table.selection_set(item)
            edit()

    edit_button = button_widget(actions, text=tr("button.edit"), command=edit)
    edit_button.pack(side="left")
    delete_button = button_widget(actions, text=tr("button.delete"), command=delete)
    delete_button.pack(side="left", padx=6)
    close_button = button_widget(actions, text=tr("button.close"))
    close_button.pack(side="right")
    table.bind("<<TreeviewSelect>>", update_actions)
    table.bind("<Double-1>", edit_row)
    refresh(selected_user)
    close_button.configure(command=show_dialog(dialog, table))
