import tkinter as tk
from collections import Counter
from dataclasses import replace
from queue import Empty, Queue
from threading import Thread
from tkinter import filedialog, ttk
from pathlib import Path
import re
import os
import webbrowser

import customtkinter as ctk

from branches import BranchError, github_repository
from localization import LANGUAGES, error_text, set_language, tr
from comparison_cache import load_cache, profile_cache_path, save_cache
from dialog_position import center_windows_dialog, set_windows_titlebar_theme
from comparison import compare, delete_local_folder, refresh_repository, validate_login, with_branches
from git_sync import change_origin, clone_from_github, corrected_origin, read_local_origin, sync_from_github
from settings import load_settings, resolve_token, save_settings, settings_path, validate_token_reference
from results_table import ResultsTable
from app_theme import THEMES, WHITE, set_theme, theme_color
from wide_combobox import WideComboBox


STATUSES = {
    "both": "Есть в обоих местах",
    "github": "Только на GitHub",
    "local": "Только локально",
}


FONT = ("Segoe UI", 13)


def status_style(key):
    return STATUSES[key], theme_color(f"{key}_bg"), theme_color(f"{key}_fg")


def button_widget(parent, *, primary=False, **options):
    return ctk.CTkButton(
        parent, font=FONT, text_color=WHITE if primary else theme_color("text"), text_color_disabled=theme_color("disabled_text"),
        fg_color=theme_color("accent") if primary else theme_color("field"), hover_color=theme_color("accent_hover") if primary else theme_color("hover"),
        border_width=0 if primary else 1, border_color=theme_color("border"), corner_radius=8,
        width=110, height=34, **options
    )


def entry_widget(parent, **options):
    return ctk.CTkEntry(parent, font=FONT, text_color=theme_color("text"), fg_color=theme_color("field"), border_color=theme_color("border"),
                        border_width=1, corner_radius=8, height=34, **options)


def combo_widget(parent, **options):
    return WideComboBox(
        parent, font=FONT, dropdown_font=FONT, text_color=theme_color("text"), fg_color=theme_color("field"), border_color=theme_color("border"),
        button_color=theme_color("field"), button_hover_color=theme_color("hover"), dropdown_fg_color=theme_color("field"),
        dropdown_hover_color=theme_color("hover"), dropdown_text_color=theme_color("text"),
        border_width=1, corner_radius=8, height=34, state="readonly", **options
    )


def label_widget(parent, *, heading=False, muted=False, **options):
    return ctk.CTkLabel(
        parent, font=("Segoe UI", 21, "bold") if heading else FONT,
        text_color=theme_color("muted") if muted else theme_color("text"), **options
    )


def configure_theme(root):
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", background=theme_color("panel"), foreground=theme_color("text"), font=("Segoe UI", 10))
    style.configure("Treeview", background=theme_color("table"), fieldbackground=theme_color("table"),
                    foreground=theme_color("text"), rowheight=27)
    style.configure("Treeview.Heading", background=theme_color("header"), foreground=theme_color("text"),
                    bordercolor=theme_color("table_border"), lightcolor=theme_color("header"), darkcolor=theme_color("header"))
    style.map("Treeview.Heading", background=[("pressed", theme_color("header_pressed")), ("active", theme_color("header_hover"))],
              foreground=[("pressed", theme_color("text")), ("active", theme_color("text"))])
    style.map("Treeview", background=[("selected", theme_color("selection"))],
              foreground=[("selected", "#ffffff")])


WINDOWS_EDIT_SHORTCUTS = {
    0x41: "<<SelectAll>>",  # A
    0x43: "<<Copy>>",   # C
    0x56: "<<Paste>>",  # V
    0x58: "<<Cut>>",    # X
}


def edit_shortcut_on_windows(event):
    # Windows virtual key codes stay the same when the keyboard layout changes.
    action = WINDOWS_EDIT_SHORTCUTS.get(event.keycode)
    if action:
        event.widget.event_generate(action)
        return "break"


def create_dialog(parent, title, *, resizable=False):
    dialog = ctk.CTkToplevel(parent, fg_color=theme_color("panel"))
    dialog.withdraw()
    dialog.title(title)
    dialog.transient(parent)
    dialog.resizable(resizable, resizable)
    frame = ctk.CTkFrame(dialog, fg_color="transparent")
    frame.pack(fill="both", expand=True, padx=16, pady=16)
    return dialog, frame


def show_dialog(dialog, focus):
    previous_grab = dialog.grab_current()

    def close():
        dialog.destroy()
        if previous_grab is not None:
            previous_grab.grab_set()

    dialog.protocol("WM_DELETE_WINDOW", close)
    dialog.bind("<Escape>", lambda _: close())
    dialog.update_idletasks()
    x = (dialog.winfo_screenwidth() - dialog.winfo_reqwidth()) // 2
    y = (dialog.winfo_screenheight() - dialog.winfo_reqheight()) // 2
    dialog.geometry(f"+{max(0, x)}+{max(0, y)}")
    dialog.deiconify()
    dialog.update_idletasks()
    if dialog.tk.call("tk", "windowingsystem") == "win32":
        center_windows_dialog(dialog)
    dialog.grab_set()
    focus.focus_set()
    return close


def confirm_action(parent, title, details, button_text, on_confirm, *, destructive=False, on_cancel=None):
    dialog, frame = create_dialog(parent, title)
    frame.columnconfigure(0, weight=1)
    label_widget(frame, text=title, heading=True).grid(row=0, column=0, sticky="w", pady=(0, 10))
    label_widget(frame, text=details, muted=True,
                 justify="left", anchor="w", wraplength=460).grid(row=1, column=0, sticky="ew")
    actions = ctk.CTkFrame(frame, fg_color="transparent")
    actions.grid(row=2, column=0, sticky="e", pady=(16, 0))
    cancel = button_widget(actions, text=tr('Отмена'))
    cancel.pack(side="left", padx=(0, 6))
    confirm = button_widget(actions, text=button_text, primary=True)
    if destructive:
        confirm.configure(fg_color=theme_color("danger"), hover_color=theme_color("danger_hover"))
    confirm.pack(side="left")

    close = show_dialog(dialog, cancel)

    def dismiss():
        close()
        if on_cancel is not None:
            on_cancel()

    cancel.configure(command=dismiss)
    dialog.protocol("WM_DELETE_WINDOW", dismiss)
    dialog.bind("<Escape>", lambda _: dismiss())

    def submit():
        close()
        on_confirm()

    confirm.configure(command=submit)
    return dialog


def modal_message(title, details, *, parent, question=False, warning=False, heading=True):
    details = error_text(details)
    answer = False
    if question:
        def accept():
            nonlocal answer
            answer = True

        dialog = confirm_action(parent, title, details, tr('Подтвердить'), accept, destructive=warning)
    else:
        dialog, frame = create_dialog(parent, title)
        label_widget(frame, text=title, heading=heading).pack(anchor="w", pady=(0, 10))
        label_widget(frame, text=details, muted=True, justify="left", wraplength=460).pack(anchor="w")
        ok = button_widget(frame, text="OK", primary=True)
        ok.pack(anchor="e", pady=(16, 0))
        close = show_dialog(dialog, ok)
        ok.configure(command=close)
        dialog.bind("<Return>", lambda _: close())
    parent.wait_window(dialog)
    return answer


def dialog_entry(frame, value="", *, readonly=False):
    entry = entry_widget(frame, width=350)
    entry.insert(0, value)
    if readonly:
        entry.configure(state="readonly")
    if frame.tk.call("tk", "windowingsystem") == "win32":
        entry.bind("<Control-KeyPress>", edit_shortcut_on_windows)
    return entry


def dialog_actions(dialog, frame, row, focus, save):
    actions = ctk.CTkFrame(frame, fg_color="transparent")
    actions.grid(row=row, column=0, columnspan=3, sticky="e")
    cancel = button_widget(actions, text=tr('Отмена'))
    cancel.pack(side="left", padx=(0, 6))
    save_button = button_widget(actions, text=tr('Сохранить'), primary=True)
    save_button.pack(side="left")
    close = show_dialog(dialog, focus)
    cancel.configure(command=close)

    def submit():
        try:
            if save():
                close()
        except (OSError, ValueError, RuntimeError) as error:
            modal_message(tr('Не удалось сохранить'), str(error), parent=dialog)
        return "break"

    save_button.configure(command=submit)
    dialog.bind("<Return>", lambda _: submit())


TOKEN_HELP_LINES = (
    "Необходимо для приватных токенов",
    "Fine-grained personal access tokens",
    "Read access to code and metadata",
    "Токен или v{ИМЯ_ПЕРЕМЕННОЙ}",
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
    title = tr('Редактирование пользователя') if login else tr('Добавить пользователя')
    dialog, frame = create_dialog(parent, title)
    label_widget(frame, text=tr('Логин GitHub')).grid(row=0, column=0, sticky="w")
    entry = dialog_entry(frame, login)
    entry.grid(row=1, column=0, sticky="ew", pady=(6, 10))
    token_heading = ctk.CTkFrame(frame, fg_color="transparent")
    token_heading.grid(row=2, column=0, sticky="w")
    label_widget(token_heading, text=tr('Токен GitHub (необязательно)')).pack(side="left")
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


class MainWindow(ctk.CTk):
    def _windows_set_titlebar_color(self, color_mode):
        # CustomTkinter 5.2.2 normally withdraws the window to repaint its frame.
        set_windows_titlebar_theme(self, color_mode.lower() == "dark")


def run():
    try:
        preferences = load_settings(settings_path())
    except (OSError, ValueError):
        preferences = {}
    language = preferences.get("language")
    theme = preferences.get("theme")
    if theme not in THEMES:
        theme = "Dark"
    if language not in ("ru", "en"):
        language = "ru"
    set_theme(theme)
    ctk.set_appearance_mode(theme)
    root = MainWindow(fg_color=theme_color("background"))
    root.geometry("1080x560")
    root.minsize(760, 360)
    snapshot = None
    while True:
        set_language(language)
        set_theme(theme)
        ctk.set_appearance_mode(theme)
        root.configure(fg_color=theme_color("background"))
        configure_theme(root)
        result = run_window(root, language, theme, snapshot)
        if result is None:
            break
        language, theme, snapshot = result


def run_window(root, language, theme, snapshot=None):
    root.title(tr('Папки и репозитории GitHub'))
    folder = tk.StringVar()
    login = tk.StringVar()
    profile_name = tk.StringVar()
    status = tk.StringVar(value=tr('Выберите папку и сохранённого пользователя GitHub.'))
    preferences_path = settings_path()
    try:
        preferences = load_settings(preferences_path)
    except (OSError, ValueError) as error:
        preferences = {"users": {}, "profiles": {}, "default_profile": None}
        status.set(tr('Не удалось прочитать настройки: {error}', error=error_text(str(error))))
    results = Queue()
    counts = Counter()
    all_rows = {}
    only_problems = tk.BooleanVar(master=root, value=False)
    compared = None
    active_cache = None
    from_cache = False

    next_window = None

    def switch_appearance(key, value):
        nonlocal next_window
        new_language = value if key == "language" else language
        new_theme = value if key == "theme" else theme
        if (new_language, new_theme) == (language, theme):
            return
        try:
            data = load_settings(preferences_path)
            data[key] = value
            save_settings(preferences_path, data)
        except (OSError, ValueError) as error:
            language_display.set(LANGUAGES[language])
            theme_display.set(theme)
            modal_message(tr("Не удалось сохранить"), str(error), parent=root)
            return
        next_window = (new_language, new_theme, {
            "folder": folder.get(), "login": login.get(), "profile": profile_name.get(),
            "only_problems": only_problems.get(), "rows": list(all_rows.values()),
            "cached": from_cache, "compared": compared, "cache": active_cache,
        })
        root.quit()

    panel = ctk.CTkFrame(root, fg_color=theme_color("panel"), corner_radius=12, border_width=1, border_color=theme_color("panel_border"))
    panel.pack(fill="both", expand=True, padx=12, pady=12)
    panel.grid_propagate(False)
    panel.columnconfigure(1, weight=1)
    panel.rowconfigure(6, weight=1)
    appearance = ctk.CTkFrame(panel, fg_color="transparent")
    appearance.grid(row=0, column=2, sticky="e", padx=(0, 16), pady=(14, 12))
    language_display = tk.StringVar(master=root, value=LANGUAGES[language])
    language_codes = {label: code for code, label in LANGUAGES.items()}
    language_picker = combo_widget(
        appearance, variable=language_display, values=list(language_codes), width=135,
        command=lambda chosen: switch_appearance("language", language_codes[chosen]),
    )
    language_picker.pack(side="left")
    theme_display = tk.StringVar(master=root, value=theme)
    theme_picker = combo_widget(appearance, variable=theme_display, values=list(THEMES), width=105,
                                command=lambda chosen: switch_appearance("theme", chosen))
    theme_picker.pack(side="left", padx=(8, 0))
    label_widget(panel, text=tr('Репозитории GitHub'), heading=True).grid(
        row=0, column=0, columnspan=3, sticky="w", padx=(16, 0), pady=(14, 12)
    )
    label_widget(panel, text=tr('Пользователь GitHub')).grid(row=1, column=0, sticky="w", padx=(16, 4))
    login_input = combo_widget(panel, variable=login, values=[])
    login_input.grid(row=1, column=1, sticky="ew", padx=8)
    label_widget(panel, text=tr('Локальная папка')).grid(row=2, column=0, sticky="w", padx=(16, 4))
    folder_input = entry_widget(panel, textvariable=folder)
    folder_input.grid(row=2, column=1, sticky="ew", padx=8, pady=8)
    if root.tk.call("tk", "windowingsystem") == "win32":
        folder_input.bind("<Control-KeyPress>", edit_shortcut_on_windows)

    label_widget(panel, text=tr('Профиль')).grid(row=3, column=0, sticky="w", padx=(16, 4))
    profile_input = combo_widget(panel, variable=profile_name, values=[])
    profile_input.grid(row=3, column=1, sticky="ew", padx=8)

    def refresh_choices():
        login_input.configure(values=sorted(preferences["users"], key=str.casefold))
        profile_input.configure(values=sorted(preferences["profiles"], key=str.casefold))

    def apply_profile(_event=None):
        profile = preferences["profiles"].get(profile_name.get())
        if profile:
            folder.set(profile["folder"])
            login.set(profile["login"])
            show_profile_cache()

    def add_user(name, token):
        nonlocal preferences
        validate_login(name)
        validate_token_reference(token)
        data = load_settings(preferences_path)
        existing = next((user for user in data["users"] if user.casefold() == name.casefold()), None)
        if existing is None:
            data["users"][name] = {}
        if token:
            data["users"][existing or name]["token"] = token
        if existing is None or token:
            save_settings(preferences_path, data)
        preferences = data
        refresh_choices()
        login.set(existing or name)
        profile_name.set("")
        status.set(tr('Пользователь выбран.'))
        return True

    def open_users():
        nonlocal preferences
        try:
            preferences = load_settings(preferences_path)
        except (OSError, ValueError) as error:
            modal_message(tr('Не удалось открыть список пользователей'), str(error), parent=root)
            return
        refresh_choices()
        dialog, frame = create_dialog(root, tr('Просмотр пользователей'), resizable=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        table = ttk.Treeview(frame, columns=("login",), show="headings", selectmode="browse", height=8)
        table.heading("login", text=tr('Пользователь GitHub'), anchor="w")
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
                    raise ValueError(tr('Этот пользователь больше не сохранён.'))
                if any(user != original and user.casefold() == name.casefold() for user in users):
                    raise ValueError(tr('Пользователь с таким логином уже сохранён.'))
                if name != original:
                    users[name] = users.pop(original)
                    for profile in data["profiles"].values():
                        if profile["login"] == original:
                            profile["login"] = name
                if token:
                    users[name]["token"] = token
                else:
                    users[name].pop("token", None)
                save_settings(preferences_path, data)
                preferences = data
                if login.get() == original:
                    login.set(name)
                refresh_choices()
                refresh(name)
                status.set(tr('Логин «{name}» сохранён.', name=name))
                return True

            user_dialog(dialog, save, login=original, token=preferences["users"][original].get("token", ""))

        def delete():
            nonlocal preferences
            selection = table.selection()
            if not selection:
                return
            name = selection[0]
            if not modal_message(
                tr('Удаление пользователя'),
                tr('Удалить пользователя «{name}» и все связанные с ним профили?', name=name),
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
                save_settings(preferences_path, data)
            except (OSError, ValueError) as error:
                modal_message(tr('Не удалось удалить пользователя'), str(error), parent=dialog)
                return
            preferences = data
            if login.get() == name:
                login.set("")
            if profile_name.get() not in data["profiles"]:
                profile_name.set("")
            refresh_choices()
            refresh(login.get())
            status.set(tr('Пользователь «{name}» и его профили удалены.', name=name))

        def edit_row(event):
            item = table.identify_row(event.y)
            if item:
                table.selection_set(item)
                edit()

        edit_button = button_widget(actions, text=tr('Редактировать'), command=edit)
        edit_button.pack(side="left")
        delete_button = button_widget(actions, text=tr('Удалить'), command=delete)
        delete_button.pack(side="left", padx=6)
        close_button = button_widget(actions, text=tr('Закрыть'))
        close_button.pack(side="right")
        table.bind("<<TreeviewSelect>>", update_actions)
        table.bind("<Double-1>", edit_row)
        refresh(login.get())
        close_button.configure(command=show_dialog(dialog, table))

    def save_profile(name, account, folder_path, default, *, original=None):
        nonlocal preferences
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
                tr('Профиль уже существует'), tr('Заменить профиль «{name}»?', name=name), parent=root.grab_current(), question=True
            ):
                return False
        path = str(Path(folder_path).expanduser().absolute())
        if original is not None and original != name:
            del profiles[original]
        profiles[name] = {"folder": path, "login": account}
        if default:
            data["default_profile"] = name
        elif data["default_profile"] in (name, original):
            data["default_profile"] = None
        save_settings(preferences_path, data)
        preferences = data
        refresh_choices()
        if original is None or profile_name.get() == original:
            profile_name.set(name)
            apply_profile()
        status.set(tr('Профиль «{name}» сохранён.', name=name))
        return True

    def open_profile_dialog():
        path = folder.get().strip()
        account = login.get()
        if not path or not account:
            modal_message(tr('Сохранение профиля'), tr('Укажите папку и выберите пользователя GitHub.'), parent=root)
            return
        profile_dialog(root, {"folder": path, "login": account}, save_profile)

    def open_profiles():
        nonlocal preferences
        try:
            preferences = load_settings(preferences_path)
        except (OSError, ValueError) as error:
            modal_message(tr('Не удалось открыть профили'), str(error), parent=root)
            return
        refresh_choices()
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
                if save_profile(name, account, path, default, original=original):
                    refresh(name)
                    return True
                return False

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
                save_settings(preferences_path, data)
            except (OSError, ValueError) as error:
                modal_message(tr('Не удалось удалить профиль'), str(error), parent=dialog)
                return
            preferences = data
            if profile_name.get() == name:
                profile_name.set("")
            refresh_choices()
            refresh()
            status.set(tr('Профиль «{name}» удалён.', name=name))

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
        refresh(profile_name.get())
        close_button.configure(command=show_dialog(dialog, table))

    add_button = button_widget(panel, text=tr('Добавить пользователя'), command=lambda: user_dialog(root, add_user))
    add_button.grid(row=1, column=2, sticky="ew", padx=(0, 16))
    save_button = button_widget(panel, text=tr('Сохранить как профиль'), command=open_profile_dialog)
    save_button.grid(row=3, column=2, sticky="ew", padx=(0, 16))
    navigation = ctk.CTkFrame(panel, fg_color="transparent")
    navigation.grid(row=4, column=1, sticky="e", padx=8, pady=(8, 0))
    users_button = button_widget(navigation, text=tr('Просмотр пользователей'), command=open_users)
    users_button.pack(side="left", padx=(0, 6))
    profiles_button = button_widget(navigation, text=tr('Просмотр профилей'), command=open_profiles)
    profiles_button.pack(side="left")
    profile_input.configure(command=apply_profile)
    refresh_choices()

    def choose_folder():
        selected = filedialog.askdirectory(parent=root, title=tr('Выберите папку'), mustexist=True)
        if selected:
            folder.set(selected)

    browse = button_widget(panel, text=tr('Обзор…'), command=choose_folder)
    browse.grid(row=2, column=2, sticky="ew", padx=(0, 16))

    def current_token():
        return resolve_token(preferences["users"].get(login.get(), {}).get("token", ""))

    def can_update_row():
        nonlocal compared
        if button.cget("state") == "disabled":
            return False
        try:
            token = current_token()
        except ValueError as error:
            modal_message("GitHub", str(error), parent=root)
            return False
        selection = (folder.get().strip(), login.get())
        if compared is None or compared[:2] != selection or compared[2] not in (None, token):
            modal_message(tr('Сравнение устарело'), tr('Сначала повторите сравнение для выбранных настроек.'),
                                parent=root)
            return False
        compared = (*selection, token)
        return True

    def set_busy(busy):
        for widget in controls:
            state = "disabled" if busy else ("readonly" if widget in (login_input, profile_input, language_picker, theme_picker) else "normal")
            widget.configure(state=state)
        folder_input.configure(text_color=theme_color("disabled_text") if busy else theme_color("text"))
        table.set_actions_enabled(not busy)

    def show_loader(action):
        loader_label.configure(text=action)
        loader_group.grid()
        loader.start()

    def run_row_action(row, action, operation=None):
        base_path, account, token = compared
        set_busy(True)
        status.set(row.name)
        show_loader(action)

        def worker():
            errors = []
            if operation is not None:
                try:
                    operation()
                except (BranchError, OSError, ValueError) as error:
                    errors.append(error_text(str(error)))
            try:
                updated = refresh_repository(base_path, account, row.name, token)
            except (OSError, ValueError, TypeError, KeyError) as error:
                errors.append(error_text(str(error)))
                updated = row
                if operation is not None:
                    candidate = Path(base_path).expanduser().absolute() / row.name
                    local_path = str(candidate) if candidate.is_dir() else ""
                    updated = replace(row, local_path=local_path, branches=(),
                                      branch_error="Не удалось перепроверить ветки.", mismatched_origin="")
                    if not updated.local_path and not updated.github_url:
                        updated = None
            results.put(("row_updated", (row, updated, "\n".join(errors))))

        Thread(target=worker, daemon=True).start()
        root.after(75, show_results)

    def request_refresh(row):
        if can_update_row():
            run_row_action(row, tr('Обновление строки'))

    def request_delete(row):
        if not can_update_row() or not row.local_path:
            return
        path = Path(row.local_path)
        base_path = compared[0]
        set_busy(True)
        confirm_action(
            root, tr('Удаление локальной папки'),
            tr('Папка, все её файлы и локальные коммиты будут удалены безвозвратно.\n\n{path}', path=path),
            tr('Удалить'),
            lambda: run_row_action(row, tr('Удаление'), lambda: delete_local_folder(base_path, path)),
            destructive=True, on_cancel=lambda: set_busy(False),
        )

    def request_sync(row, branch):
        if not can_update_row():
            return
        if row.local_path:
            destination = Path(row.local_path)
            action = tr('Создать локальную ветку') if branch.status == "github" else tr('Обновить через git pull')
            operation = sync_from_github
            progress_text = tr('Создание ветки') if branch.status == "github" else tr('Мерж (git pull)')
            button_text = tr('Создать ветку') if branch.status == "github" else tr('Обновить')
        else:
            destination = Path(compared[0]).expanduser().absolute() / row.name
            action = tr('Клонировать репозиторий')
            operation = clone_from_github
            progress_text = tr('Клонирование')
            button_text = tr('Клонировать')
        branch_line = tr('\nВетка: {branch_name}', branch_name=branch.name) if branch else ""
        set_busy(True)
        confirm_action(
            root, action, f"{row.name}{branch_line}\n\n{destination}", button_text,
            lambda: run_row_action(row, progress_text, lambda: operation(destination, row.github_url, branch, compared[2])),
            on_cancel=lambda: set_busy(False),
        )

    def request_fix_origin(row):
        if not can_update_row() or not row.origin_mismatch:
            return
        path = Path(row.local_path)
        try:
            current = read_local_origin(path)
            if not current or github_repository(current) == github_repository(row.github_url):
                request_refresh(row)
                return
            target = corrected_origin(row.github_url, current)
        except (BranchError, OSError) as error:
            modal_message(tr('Не удалось определить адрес'), str(error), parent=root)
            return
        display_origin = re.sub(r"(?<=://)[^/\s@]+@", "***@", current)
        command = f'git remote set-url origin "{target}"'
        set_busy(True)
        confirm_action(
            root, tr('Исправление origin'),
            tr('Текущий origin:\n{display_origin}\n\nКоманда:\n{command}', display_origin=display_origin, command=command),
            tr('ОК'),
            lambda: run_row_action(row, tr('Исправление origin'), lambda: change_origin(path, current, target)),
            on_cancel=lambda: set_busy(False),
        )

    def open_local_folder(path):
        try:
            if not Path(path).is_dir():
                raise FileNotFoundError(tr('Папка недоступна: {path}', path=path))
            if hasattr(os, "startfile"):
                os.startfile(path)
            else:
                webbrowser.open(Path(path).as_uri())
        except OSError as error:
            modal_message(tr('Не удалось открыть папку'), str(error), parent=root)

    table = ResultsTable(panel, on_sync=request_sync, on_refresh=request_refresh, on_delete=request_delete,
                         on_fix_origin=request_fix_origin, on_open_folder=open_local_folder)
    table.grid(row=6, column=0, columnspan=3, sticky="nsew", padx=16)
    status_line = ctk.CTkFrame(panel, fg_color="transparent")
    status_line.grid(row=7, column=0, columnspan=3, sticky="ew", padx=16, pady=(8, 12))
    status_line.columnconfigure(0, weight=1)
    label_widget(status_line, textvariable=status, muted=True, wraplength=680).grid(
        row=0, column=0, sticky="w"
    )
    loader_group = ctk.CTkFrame(status_line, fg_color="transparent")
    loader_group.grid(row=0, column=1, padx=(12, 0))
    loader = ctk.CTkProgressBar(loader_group, mode="indeterminate", width=140, fg_color=theme_color("field"), progress_color=theme_color("accent"))
    loader.pack(side="left")
    loader_label = label_widget(loader_group, text="")
    loader_label.pack(side="left", padx=(10, 0))
    loader_group.grid_remove()

    table_notes = ctk.CTkFrame(panel, fg_color="transparent")
    table_notes.grid(row=5, column=0, columnspan=3, sticky="ew", padx=16, pady=(5, 5))
    cache_notice = label_widget(table_notes, text=tr('Данные из кэша'), muted=True)
    cache_notice.configure(text_color=theme_color("branch_red"))
    cache_notice.grid(row=0, column=1, sticky="w", padx=(12, 0))
    cache_notice.grid_remove()
    problem_filter = ctk.CTkCheckBox(
        table_notes, text=tr('Требуют внимания'), variable=only_problems, font=FONT, text_color=theme_color("text"),
        fg_color=theme_color("accent"), hover_color=theme_color("accent_hover"), checkmark_color=WHITE, border_color=theme_color("border"), command=lambda: redraw_rows(),
    )
    problem_filter.grid(row=0, column=0, sticky="w")

    def is_visible(row):
        return not only_problems.get() or (
            row.status != "both" or bool(row.branch_error)
            or any(branch.status != "equal" for branch in row.branches)
        )

    def add_result(row):
        all_rows[row.name] = row
        counts[row.status] += 1
        if is_visible(row):
            table.add(row, status_style(row.status))

    def redraw_rows():
        table.clear()
        for row in all_rows.values():
            if is_visible(row):
                table.add(row, status_style(row.status))

    def reset_results():
        all_rows.clear()
        counts.clear()
        table.clear()

    def selected_cache_path():
        name = profile_name.get()
        profile = preferences["profiles"].get(name)
        if not profile or login.get() != profile["login"]:
            return None
        path = folder.get().strip()
        if not path or Path(path).expanduser().absolute() != Path(profile["folder"]).expanduser().absolute():
            return None
        authenticated = bool(preferences["users"].get(login.get(), {}).get("token"))
        return profile_cache_path(preferences_path, name, path, login.get(), authenticated)

    def summary_text():
        return "  ·  ".join(f"{tr(label)}: {counts[key]}" for key, label in STATUSES.items())

    def show_profile_cache():
        nonlocal compared, active_cache, from_cache
        from_cache = False
        compared = None
        active_cache = None
        reset_results()
        cache_notice.grid_remove()
        path = selected_cache_path()
        rows = load_cache(path) if path is not None else None
        table.set_actions_enabled(True)
        if rows is None:
            status.set(tr('Нажмите «Сравнить», чтобы получить данные.'))
            return
        compared = (folder.get().strip(), login.get(), None)
        active_cache = path
        from_cache = True
        for row in rows:
            add_result(row)
        cache_notice.grid()
        status.set(summary_text())

    def remember_table():
        if active_cache is None:
            return ""
        try:
            save_cache(active_cache, all_rows.values())
        except OSError:
            return tr('  ·  Не удалось сохранить кэш.')
        return ""

    def load(path, account, token):
        try:
            rows = compare(path, account, token)
            for row in rows:
                results.put(("row", with_branches(row, token)))
            results.put(("done", None))
        except (ValueError, OSError, TypeError, KeyError) as error:
            results.put(("error", str(error)))

    def show_results():
        for _ in range(30):
            try:
                kind, value = results.get_nowait()
            except Empty:
                break
            if kind == "row":
                add_result(value)
                status.set(tr('Обработано репозиториев: {count}', count=sum(counts.values())))
                continue
            loader.stop()
            loader_group.grid_remove()
            set_busy(False)
            if kind == "row_updated":
                previous, updated, error = value
                if updated is not previous:
                    counts[previous.status] -= 1
                    if updated is None:
                        all_rows.pop(previous.name, None)
                    else:
                        all_rows[previous.name] = updated
                        counts[updated.status] += 1
                    if previous.name in table.rows:
                        if updated is not None and is_visible(updated):
                            table.update_row(previous.name, updated, status_style(updated.status))
                        else:
                            table.update_row(previous.name)
                    elif updated is not None and is_visible(updated):
                        redraw_rows()
                if error:
                    status.set(error)
                    modal_message(tr('Не удалось завершить действие'), error, parent=root)
                    return
            if kind == "error":
                if active_cache is not None and active_cache.is_file():
                    show_profile_cache()
                status.set(error_text(value))
            else:
                status.set(summary_text() + remember_table())
            return
        root.after(75, show_results)

    def submit():
        nonlocal compared, active_cache, from_cache
        if button.cget("state") == "disabled":
            return
        path, account = folder.get().strip(), login.get()
        if not path or not account:
            status.set(tr('Укажите папку и выберите сохранённого пользователя GitHub.'))
            return
        try:
            token = current_token()
        except ValueError as error:
            status.set(error_text(str(error)))
            return
        set_busy(True)
        compared = (path, account, token)
        active_cache = selected_cache_path()
        from_cache = False
        cache_notice.grid_remove()
        reset_results()
        status.set(tr('Сравниваем папки с репозиториями GitHub…'))
        show_loader(tr('Сравнение'))
        Thread(target=load, args=(path, account, token), daemon=True).start()
        root.after(75, show_results)

    button = button_widget(panel, text=tr('Сравнить'), primary=True, command=submit)
    button.grid(row=4, column=2, sticky="ew", padx=(0, 16), pady=(8, 0))
    controls = (folder_input, login_input, profile_input, browse, add_button, save_button,
                profiles_button, users_button, problem_filter, language_picker, theme_picker, button)
    if snapshot is not None:
        folder.set(snapshot["folder"])
        login.set(snapshot["login"])
        profile_name.set(snapshot["profile"])
        only_problems.set(snapshot["only_problems"])
        compared = snapshot["compared"]
        active_cache = snapshot["cache"]
        for row in snapshot["rows"]:
            add_result(row)
        from_cache = snapshot["cached"]
        if from_cache:
            cache_notice.grid()
        if snapshot["rows"] or compared is not None:
            status.set(summary_text())
    elif preferences["default_profile"]:
        profile_name.set(preferences["default_profile"])
        apply_profile()
    root.bind("<Return>", lambda _event: submit())
    login_input.focus_set()
    if snapshot is None and root.tk.call("tk", "windowingsystem") == "win32":
        def maximize_on_map(event):
            if event.widget is root:
                root.unbind("<Map>", startup_binding)
                root.after_idle(root.state, "zoomed")

        # CustomTkinter restores the window while setting up the Windows title bar.
        startup_binding = root.bind("<Map>", maximize_on_map, add="+")
    root.mainloop()
    if next_window is not None:
        panel.destroy()
    return next_window
