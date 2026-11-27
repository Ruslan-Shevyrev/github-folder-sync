import tkinter as tk
from pathlib import Path
from tkinter import filedialog, ttk

import customtkinter as ctk

from ..comparison_cache import cache_for_profile, save_preferences
from ..settings import load_settings
from .app_theme import WHITE, theme_color
from .dialogs import (
    FONT, button_widget, combo_widget, create_dialog, dialog_actions, dialog_entry,
    label_widget, modal_message, show_dialog,
)
from .localization import tr


def profile_dialog(parent, profile, on_save, *, users=(), name="", is_default=False, editing=False):
    title = tr('Редактирование профиля') if editing else tr('Сохранение профиля')
    dialog, frame = create_dialog(parent, title)
    frame.columnconfigure(1, weight=1)
    name_input = dialog_entry(frame, name)
    path_input = dialog_entry(frame, profile["folder"], readonly=not editing)
    if editing:
        account_input = combo_widget(frame, values=sorted(users, key=str.casefold))
        account_input.set(profile["login"])
    else:
        account_input = dialog_entry(frame, profile["login"], readonly=True)
    for row, (label, field) in enumerate((
        (tr('Имя профиля'), name_input),
        (tr('Пользователь GitHub'), account_input),
        (tr('Локальная папка'), path_input),
    )):
        label_widget(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=(0, 8))
        field.grid(row=row, column=1, sticky="ew", pady=(0, 8))

    if editing:
        def browse():
            path = filedialog.askdirectory(parent=dialog, mustexist=True)
            if path:
                path_input.delete(0, "end")
                path_input.insert(0, path)

        button_widget(frame, text=tr('Обзор…'), command=browse).grid(row=2, column=2, padx=(8, 0), pady=(0, 8))

    default = tk.BooleanVar(master=dialog, value=is_default)
    ctk.CTkCheckBox(frame, font=FONT, fg_color=theme_color("accent"), hover_color=theme_color("accent_hover"), checkmark_color=WHITE, border_color=theme_color("border"), text_color=theme_color("text"), text=tr('Настройки по умолчанию'), variable=default).grid(
        row=3, column=1, sticky="w", pady=(0, 10)
    )
    dialog_actions(dialog, frame, 4, name_input, lambda: on_save(
        name_input.get().strip(), account_input.get(), path_input.get().strip(), default.get()
    ))


def save_profile(parent, preferences_path, name, account, folder_path, default, *, original=None):
    if not name:
        raise ValueError(tr('Введите имя профиля.'))
    if not folder_path:
        raise ValueError(tr('Укажите локальную папку.'))
    data = load_settings(preferences_path)
    if account not in data["users"]:
        raise ValueError(tr('Выберите сохранённого пользователя GitHub.'))
    profiles = data["profiles"]
    if original is not None and original not in profiles:
        raise ValueError(tr('Этот профиль уже удалён.'))
    if name in profiles and name != original:
        if original is not None:
            raise ValueError(tr('Профиль с таким именем уже существует.'))
        if not modal_message(
            tr('Профиль уже существует'), tr('Заменить профиль «{name}»?', name=name), parent=parent.grab_current(), question=True
        ):
            return False
    path = str(Path(folder_path).expanduser().absolute())
    renamed = None
    profile = {"folder": path, "login": account}
    if original is not None and original != name:
        previous = profiles.pop(original)
        if Path(previous["folder"]).expanduser().absolute() == Path(path) and previous["login"] == account:
            renamed = (
                cache_for_profile(preferences_path, original, previous, data["users"]),
                cache_for_profile(preferences_path, name, profile, data["users"]),
            )
    profiles[name] = profile
    if default:
        data["default_profile"] = name
    elif data["default_profile"] in (name, original):
        data["default_profile"] = None
    save_preferences(preferences_path, data, renamed)
    return data


def add_profile(root, preferences_path, path, account, on_change):
    if not path or not account:
        modal_message(tr('Сохранение профиля'), tr('Укажите папку и выберите пользователя GitHub.'), parent=root)
        return
    def save(name, login, folder, default):
        data = save_profile(root, preferences_path, name, login, folder, default)
        if data is False:
            return False
        on_change(data, name=name)
        return True

    profile_dialog(root, {"folder": path, "login": account}, save)


def open_profiles(root, preferences_path, selected_profile, on_change):
    try:
        preferences = load_settings(preferences_path)
    except (OSError, ValueError) as error:
        modal_message(tr('Не удалось открыть профили'), str(error), parent=root)
        return
    on_change(preferences)
    dialog, frame = create_dialog(root, tr('Просмотр профилей'), resizable=True)
    frame.columnconfigure(0, weight=1)
    frame.rowconfigure(0, weight=1)
    table = ttk.Treeview(frame, columns=("name", "login", "folder", "default"), show="headings",
                         selectmode="browse", height=8)
    columns = (
        ("name", tr('Имя профиля'), 150),
        ("login", tr('Пользователь GitHub'), 160),
        ("folder", tr('Локальная папка'), 300),
        ("default", tr('По умолчанию'), 110),
    )
    for column, label, width in columns:
        table.heading(column, text=label, anchor="w")
        table.column(column, width=width, minwidth=width, stretch=column == "folder")
    vertical = ctk.CTkScrollbar(frame, orientation="vertical", command=table.yview)
    horizontal = ctk.CTkScrollbar(frame, orientation="horizontal", command=table.xview)
    table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
    table.grid(row=0, column=0, sticky="nsew")
    vertical.grid(row=0, column=1, sticky="ns")
    horizontal.grid(row=1, column=0, sticky="ew")
    actions = ctk.CTkFrame(frame, fg_color="transparent")
    actions.grid(row=2, column=0, sticky="ew", pady=(10, 0))

    def refresh(selected=None):
        table.delete(*table.get_children())
        for name in sorted(preferences["profiles"], key=str.casefold):
            profile = preferences["profiles"][name]
            default = tr('Да') if name == preferences["default_profile"] else "—"
            table.insert("", "end", iid=name, values=(name, profile["login"], profile["folder"], default))
        if selected is not None and table.exists(selected):
            table.selection_set(selected)
            table.focus(selected)
            table.see(selected)
        update_actions()

    def update_actions(_event=None):
        state = "normal" if table.selection() else "disabled"
        edit_button.configure(state=state)
        delete_button.configure(state=state)

    def edit():
        selection = table.selection()
        if not selection:
            return
        original = selection[0]

        def save(name, account, path, default):
            nonlocal preferences
            data = save_profile(dialog, preferences_path, name, account, path, default, original=original)
            if data is False:
                return False
            preferences = data
            on_change(data, original, name)
            refresh(name)
            return True

        profile_dialog(dialog, preferences["profiles"][original], save, name=original,
                       users=preferences["users"], is_default=preferences["default_profile"] == original,
                       editing=True)

    def delete():
        nonlocal preferences
        selection = table.selection()
        if not selection:
            return
        name = selection[0]
        if not modal_message(tr('Удаление профиля'), tr('Удалить профиль «{name}»?', name=name), parent=dialog, question=True, warning=True):
            return
        try:
            data = load_settings(preferences_path)
            data["profiles"].pop(name, None)
            if data["default_profile"] == name:
                data["default_profile"] = None
            save_preferences(preferences_path, data)
        except (OSError, ValueError) as error:
            modal_message(tr('Не удалось удалить профиль'), str(error), parent=dialog)
            return
        preferences = data
        on_change(data, original=name)
        refresh()

    edit_button = button_widget(actions, text=tr('Редактировать'), command=edit)
    edit_button.pack(side="left")
    delete_button = button_widget(actions, text=tr('Удалить'), command=delete)
    delete_button.pack(side="left", padx=6)
    close_button = button_widget(actions, text=tr('Закрыть'))
    close_button.pack(side="right")
    table.bind("<<TreeviewSelect>>", update_actions)

    def edit_row(event):
        item = table.identify_row(event.y)
        if item:
            table.selection_set(item)
            edit()

    table.bind("<Double-1>", edit_row)
    refresh(selected_profile)
    close_button.configure(command=show_dialog(dialog, table))
