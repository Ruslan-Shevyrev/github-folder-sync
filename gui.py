import tkinter as tk
from collections import Counter
from dataclasses import replace
from queue import Empty, Queue
from threading import Thread
from tkinter import filedialog, ttk
from pathlib import Path

import customtkinter as ctk

from branches import BranchError
from dialog_position import center_windows_dialog
from comparison import compare, delete_local_folder, refresh_repository, validate_login, with_branches
from git_sync import clone_from_github, sync_from_github
from settings import load_settings, save_settings, settings_path
from results_table import ResultsTable


STATUSES = {
    "both": ("Есть в обоих местах", "#20372f", "#b8f5cf"),
    "github": ("Только на GitHub", "#2e3242", "#dcdfeb"),
    "local": ("Только локально", "#432b37", "#ffc4cb"),
}


BACKGROUND = "#111522"
PANEL = "#191e2f"
FIELD = "#23283c"
BORDER = "#42495f"
TEXT = "#f4f2fb"
MUTED = "#b9bdd1"
ACCENT = "#7446ee"
FONT = ("Segoe UI", 13)


def button_widget(parent, *, primary=False, **options):
    return ctk.CTkButton(
        parent, font=FONT, text_color=TEXT, text_color_disabled="#9398ad",
        fg_color=ACCENT if primary else FIELD, hover_color="#895dff" if primary else "#353d55",
        border_width=0 if primary else 1, border_color=BORDER, corner_radius=8,
        width=110, height=34, **options
    )


def entry_widget(parent, **options):
    return ctk.CTkEntry(parent, font=FONT, text_color=TEXT, fg_color=FIELD, border_color=BORDER,
                        border_width=1, corner_radius=8, height=34, **options)


def combo_widget(parent, **options):
    return ctk.CTkComboBox(
        parent, font=FONT, dropdown_font=FONT, text_color=TEXT, fg_color=FIELD, border_color=BORDER,
        button_color=FIELD, button_hover_color="#353d55", dropdown_fg_color=FIELD,
        dropdown_hover_color="#353d55", dropdown_text_color=TEXT,
        border_width=1, corner_radius=8, height=34, state="readonly", **options
    )


def label_widget(parent, *, heading=False, muted=False, **options):
    return ctk.CTkLabel(
        parent, font=("Segoe UI", 21, "bold") if heading else FONT,
        text_color=MUTED if muted else TEXT, **options
    )


def configure_theme(root):
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", background="#191d30", foreground="#f4f1ff", font=("Segoe UI", 10))
    style.configure("Treeview", background="#101321", fieldbackground="#101321",
                    foreground="#f4f1ff", rowheight=27)
    style.configure("Treeview.Heading", background="#222740", foreground="#f4f1ff",
                    bordercolor="#343956", lightcolor="#222740", darkcolor="#222740")
    style.map("Treeview.Heading", background=[("pressed", "#4a347a"), ("active", "#343052")],
              foreground=[("pressed", "#f4f1ff"), ("active", "#f4f1ff")])
    style.map("Treeview", background=[("selected", "#513ca0")],
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
    dialog = ctk.CTkToplevel(parent, fg_color=PANEL)
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
    cancel = button_widget(actions, text="Отмена")
    cancel.pack(side="left", padx=(0, 6))
    confirm = button_widget(actions, text=button_text, primary=True)
    if destructive:
        confirm.configure(fg_color="#983c53", hover_color="#b94c67")
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


def modal_message(title, details, *, parent, question=False, warning=False):
    answer = False
    if question:
        def accept():
            nonlocal answer
            answer = True

        dialog = confirm_action(parent, title, details, "Подтвердить", accept, destructive=warning)
    else:
        dialog, frame = create_dialog(parent, title)
        label_widget(frame, text=title, heading=True).pack(anchor="w", pady=(0, 10))
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
    cancel = button_widget(actions, text="Отмена")
    cancel.pack(side="left", padx=(0, 6))
    save_button = button_widget(actions, text="Сохранить", primary=True)
    save_button.pack(side="left")
    close = show_dialog(dialog, focus)
    cancel.configure(command=close)

    def submit():
        try:
            if save():
                close()
        except (OSError, ValueError, RuntimeError) as error:
            modal_message("Не удалось сохранить", str(error), parent=dialog)
        return "break"

    save_button.configure(command=submit)
    dialog.bind("<Return>", lambda _: submit())


def user_dialog(parent, on_save, *, login=""):
    title = "Редактирование пользователя" if login else "Добавить пользователя"
    dialog, frame = create_dialog(parent, title)
    label_widget(frame, text="Логин GitHub").grid(row=0, column=0, sticky="w")
    entry = dialog_entry(frame, login)
    entry.grid(row=1, column=0, sticky="ew", pady=(6, 10))
    dialog_actions(dialog, frame, 2, entry, lambda: on_save(entry.get().strip()))


def profile_dialog(parent, profile, on_save, *, users=(), name="", is_default=False, editing=False):
    title = "Редактирование профиля" if editing else "Сохранение профиля"
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
        ("Имя профиля", name_input),
        ("Пользователь GitHub", account_input),
        ("Локальная папка", path_input),
    )):
        label_widget(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=(0, 8))
        field.grid(row=row, column=1, sticky="ew", pady=(0, 8))

    if editing:
        def browse():
            path = filedialog.askdirectory(parent=dialog, mustexist=True)
            if path:
                path_input.delete(0, "end")
                path_input.insert(0, path)

        button_widget(frame, text="Обзор…", command=browse).grid(row=2, column=2, padx=(8, 0), pady=(0, 8))

    default = tk.BooleanVar(master=dialog, value=is_default)
    ctk.CTkCheckBox(frame, font=FONT, fg_color=ACCENT, hover_color="#895dff", border_color=BORDER, text_color=TEXT, text="Настройки по умолчанию", variable=default).grid(
        row=3, column=1, sticky="w", pady=(0, 10)
    )
    dialog_actions(dialog, frame, 4, name_input, lambda: on_save(
        name_input.get().strip(), account_input.get(), path_input.get().strip(), default.get()
    ))


def run():
    ctk.set_appearance_mode("dark")
    root = ctk.CTk(fg_color=BACKGROUND)
    root.title("Папки и репозитории GitHub")
    root.geometry("1080x560")
    root.minsize(760, 360)
    configure_theme(root)

    folder = tk.StringVar()
    login = tk.StringVar()
    profile_name = tk.StringVar()
    status = tk.StringVar(value="Выберите папку и сохранённого пользователя GitHub.")
    preferences_path = settings_path()
    try:
        preferences = load_settings(preferences_path)
    except (OSError, ValueError) as error:
        preferences = {"users": [], "profiles": {}, "default_profile": None}
        status.set(f"Не удалось прочитать настройки: {error}")
    results = Queue()
    counts = Counter()
    compared = None

    panel = ctk.CTkFrame(root, fg_color=PANEL, corner_radius=12, border_width=1, border_color="#30374d")
    panel.pack(fill="both", expand=True, padx=12, pady=12)
    panel.grid_propagate(False)
    panel.columnconfigure(1, weight=1)
    panel.rowconfigure(6, weight=1)
    label_widget(panel, text="Публичные репозитории GitHub", heading=True).grid(
        row=0, column=0, columnspan=3, sticky="w", padx=(16, 0), pady=(14, 12)
    )
    label_widget(panel, text="Пользователь GitHub").grid(row=1, column=0, sticky="w", padx=(16, 4))
    login_input = combo_widget(panel, variable=login, values=[])
    login_input.grid(row=1, column=1, sticky="ew", padx=8)
    label_widget(panel, text="Локальная папка").grid(row=2, column=0, sticky="w", padx=(16, 4))
    folder_input = entry_widget(panel, textvariable=folder)
    folder_input.grid(row=2, column=1, sticky="ew", padx=8, pady=8)
    if root.tk.call("tk", "windowingsystem") == "win32":
        folder_input.bind("<Control-KeyPress>", edit_shortcut_on_windows)

    label_widget(panel, text="Профиль").grid(row=3, column=0, sticky="w", padx=(16, 4))
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

    def add_user(name):
        nonlocal preferences
        validate_login(name)
        data = load_settings(preferences_path)
        existing = next((user for user in data["users"] if user.casefold() == name.casefold()), None)
        if existing is None:
            data["users"].append(name)
            save_settings(preferences_path, data)
        preferences = data
        refresh_choices()
        login.set(existing or name)
        profile_name.set("")
        status.set("Пользователь выбран.")
        return True

    def open_users():
        nonlocal preferences
        try:
            preferences = load_settings(preferences_path)
        except (OSError, ValueError) as error:
            modal_message("Не удалось открыть список пользователей", str(error), parent=root)
            return
        refresh_choices()
        dialog, frame = create_dialog(root, "Просмотр пользователей", resizable=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        table = ttk.Treeview(frame, columns=("login",), show="headings", selectmode="browse", height=8)
        table.heading("login", text="Пользователь GitHub", anchor="w")
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

            def save(name):
                nonlocal preferences
                validate_login(name)
                data = load_settings(preferences_path)
                users = data["users"]
                if original not in users:
                    raise ValueError("Этот пользователь больше не сохранён.")
                if any(user != original and user.casefold() == name.casefold() for user in users):
                    raise ValueError("Пользователь с таким логином уже сохранён.")
                if name != original:
                    users[users.index(original)] = name
                    for profile in data["profiles"].values():
                        if profile["login"] == original:
                            profile["login"] = name
                    save_settings(preferences_path, data)
                preferences = data
                if login.get() == original:
                    login.set(name)
                refresh_choices()
                refresh(name)
                status.set(f"Логин «{name}» сохранён.")
                return True

            user_dialog(dialog, save, login=original)

        def delete():
            nonlocal preferences
            selection = table.selection()
            if not selection:
                return
            name = selection[0]
            if not modal_message(
                "Удаление пользователя",
                f"Удалить пользователя «{name}» и все связанные с ним профили?",
                parent=dialog, question=True, warning=True,
            ):
                return
            try:
                data = load_settings(preferences_path)
                data["users"] = [user for user in data["users"] if user != name]
                data["profiles"] = {
                    key: profile for key, profile in data["profiles"].items()
                    if profile["login"] != name
                }
                if data["default_profile"] not in data["profiles"]:
                    data["default_profile"] = None
                save_settings(preferences_path, data)
            except (OSError, ValueError) as error:
                modal_message("Не удалось удалить пользователя", str(error), parent=dialog)
                return
            preferences = data
            if login.get() == name:
                login.set("")
            if profile_name.get() not in data["profiles"]:
                profile_name.set("")
            refresh_choices()
            refresh(login.get())
            status.set(f"Пользователь «{name}» и его профили удалены.")

        def edit_row(event):
            item = table.identify_row(event.y)
            if item:
                table.selection_set(item)
                edit()

        edit_button = button_widget(actions, text="Редактировать", command=edit)
        edit_button.pack(side="left")
        delete_button = button_widget(actions, text="Удалить", command=delete)
        delete_button.pack(side="left", padx=6)
        close_button = button_widget(actions, text="Закрыть")
        close_button.pack(side="right")
        table.bind("<<TreeviewSelect>>", update_actions)
        table.bind("<Double-1>", edit_row)
        refresh(login.get())
        close_button.configure(command=show_dialog(dialog, table))

    def save_profile(name, account, folder_path, default, *, original=None):
        nonlocal preferences
        if not name:
            raise ValueError("Введите имя профиля.")
        if not folder_path:
            raise ValueError("Укажите локальную папку.")
        data = load_settings(preferences_path)
        if account not in data["users"]:
            raise ValueError("Выберите сохранённого пользователя GitHub.")
        profiles = data["profiles"]
        if original is not None and original not in profiles:
            raise ValueError("Этот профиль уже удалён.")
        if name in profiles and name != original:
            if original is not None:
                raise ValueError("Профиль с таким именем уже существует.")
            if not modal_message(
                "Профиль уже существует", f"Заменить профиль «{name}»?", parent=root.grab_current(), question=True
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
        status.set(f"Профиль «{name}» сохранён.")
        return True

    def open_profile_dialog():
        path = folder.get().strip()
        account = login.get()
        if not path or not account:
            modal_message("Сохранение профиля", "Укажите папку и выберите пользователя GitHub.", parent=root)
            return
        profile_dialog(root, {"folder": path, "login": account}, save_profile)

    def open_profiles():
        nonlocal preferences
        try:
            preferences = load_settings(preferences_path)
        except (OSError, ValueError) as error:
            modal_message("Не удалось открыть профили", str(error), parent=root)
            return
        refresh_choices()
        dialog, frame = create_dialog(root, "Просмотр профилей", resizable=True)
        frame.columnconfigure(0, weight=1)
        frame.rowconfigure(0, weight=1)
        table = ttk.Treeview(frame, columns=("name", "login", "folder", "default"), show="headings",
                             selectmode="browse", height=8)
        columns = (
            ("name", "Имя профиля", 150),
            ("login", "Пользователь GitHub", 160),
            ("folder", "Локальная папка", 300),
            ("default", "По умолчанию", 110),
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
                default = "Да" if name == preferences["default_profile"] else "—"
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
            if not modal_message("Удаление профиля", f"Удалить профиль «{name}»?", parent=dialog, question=True, warning=True):
                return
            try:
                data = load_settings(preferences_path)
                data["profiles"].pop(name, None)
                if data["default_profile"] == name:
                    data["default_profile"] = None
                save_settings(preferences_path, data)
            except (OSError, ValueError) as error:
                modal_message("Не удалось удалить профиль", str(error), parent=dialog)
                return
            preferences = data
            if profile_name.get() == name:
                profile_name.set("")
            refresh_choices()
            refresh()
            status.set(f"Профиль «{name}» удалён.")

        edit_button = button_widget(actions, text="Редактировать", command=edit)
        edit_button.pack(side="left")
        delete_button = button_widget(actions, text="Удалить", command=delete)
        delete_button.pack(side="left", padx=6)
        close_button = button_widget(actions, text="Закрыть")
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

    add_button = button_widget(panel, text="Добавить пользователя", command=lambda: user_dialog(root, add_user))
    add_button.grid(row=1, column=2, sticky="ew", padx=(0, 16))
    save_button = button_widget(panel, text="Сохранить", command=open_profile_dialog)
    save_button.grid(row=3, column=2, sticky="ew", padx=(0, 16))
    navigation = ctk.CTkFrame(panel, fg_color="transparent")
    navigation.grid(row=4, column=1, sticky="e", padx=8, pady=(8, 0))
    users_button = button_widget(navigation, text="Просмотр пользователей", command=open_users)
    users_button.pack(side="left", padx=(0, 6))
    profiles_button = button_widget(navigation, text="Просмотр профилей", command=open_profiles)
    profiles_button.pack(side="left")
    profile_input.configure(command=apply_profile)
    refresh_choices()
    if preferences["default_profile"]:
        profile_name.set(preferences["default_profile"])
        apply_profile()

    def choose_folder():
        selected = filedialog.askdirectory(parent=root, title="Выберите папку", mustexist=True)
        if selected:
            folder.set(selected)

    browse = button_widget(panel, text="Обзор…", command=choose_folder)
    browse.grid(row=2, column=2, sticky="ew", padx=(0, 16))

    def can_update_row():
        if button.cget("state") == "disabled":
            return False
        if compared != (folder.get().strip(), login.get()):
            modal_message("Сравнение устарело", "Сначала повторите сравнение для выбранных настроек.",
                                parent=root)
            return False
        return True

    def set_busy(busy):
        for widget in controls:
            state = "disabled" if busy else ("readonly" if widget in (login_input, profile_input) else "normal")
            widget.configure(state=state)
        folder_input.configure(text_color="#9398ad" if busy else TEXT)
        table.set_actions_enabled(not busy)

    def show_loader(action):
        loader_label.configure(text=action)
        loader_group.grid()
        loader.start()

    def run_row_action(row, action, operation=None):
        base_path, account = compared
        set_busy(True)
        status.set(row.name)
        show_loader(action)

        def worker():
            errors = []
            if operation is not None:
                try:
                    operation()
                except (BranchError, OSError, ValueError) as error:
                    errors.append(str(error))
            try:
                updated = refresh_repository(base_path, account, row.name)
            except (OSError, ValueError, TypeError, KeyError) as error:
                errors.append(str(error))
                updated = row
                if operation is not None:
                    candidate = Path(base_path).expanduser().absolute() / row.name
                    local_path = str(candidate) if candidate.is_dir() else ""
                    updated = replace(row, local_path=local_path, branches=(),
                                      branch_error="Не удалось перепроверить ветки.")
                    if not updated.local_path and not updated.github_url:
                        updated = None
            results.put(("row_updated", (row, updated, "\n".join(errors))))

        Thread(target=worker, daemon=True).start()
        root.after(75, show_results)

    def request_refresh(row):
        if can_update_row():
            run_row_action(row, "Обновление строки")

    def request_delete(row):
        if not can_update_row() or not row.local_path:
            return
        path = Path(row.local_path)
        base_path = compared[0]
        set_busy(True)
        confirm_action(
            root, "Удаление локальной папки",
            f"Папка, все её файлы и локальные коммиты будут удалены безвозвратно.\n\n{path}",
            "Удалить",
            lambda: run_row_action(row, "Удаление", lambda: delete_local_folder(base_path, path)),
            destructive=True, on_cancel=lambda: set_busy(False),
        )

    def request_sync(row, branch):
        if not can_update_row():
            return
        if row.local_path:
            destination = Path(row.local_path)
            action = "Создать локальную ветку" if branch.status == "github" else "Обновить через git pull"
            operation = sync_from_github
            progress_text = "Создание ветки" if branch.status == "github" else "Мерж (git pull)"
            button_text = "Создать ветку" if branch.status == "github" else "Обновить"
        else:
            destination = Path(compared[0]).expanduser().absolute() / row.name
            action = "Клонировать репозиторий"
            operation = clone_from_github
            progress_text = "Клонирование"
            button_text = "Клонировать"
        branch_line = f"\nВетка: {branch.name}" if branch else ""
        set_busy(True)
        confirm_action(
            root, action, f"{row.name}{branch_line}\n\n{destination}", button_text,
            lambda: run_row_action(row, progress_text, lambda: operation(destination, row.github_url, branch)),
            on_cancel=lambda: set_busy(False),
        )

    table = ResultsTable(panel, on_sync=request_sync, on_refresh=request_refresh, on_delete=request_delete)
    table.grid(row=6, column=0, columnspan=3, sticky="nsew", padx=16)
    status_line = ctk.CTkFrame(panel, fg_color="transparent")
    status_line.grid(row=7, column=0, columnspan=3, sticky="ew", padx=16, pady=(8, 12))
    status_line.columnconfigure(0, weight=1)
    label_widget(status_line, textvariable=status, muted=True, wraplength=680).grid(
        row=0, column=0, sticky="w"
    )
    loader_group = ctk.CTkFrame(status_line, fg_color="transparent")
    loader_group.grid(row=0, column=1, padx=(12, 0))
    loader = ctk.CTkProgressBar(loader_group, mode="indeterminate", width=140, fg_color=FIELD, progress_color=ACCENT)
    loader.pack(side="left")
    loader_label = label_widget(loader_group, text="")
    loader_label.pack(side="left", padx=(10, 0))
    loader_group.grid_remove()

    label_widget(panel, text="Двойной щелчок по ссылке откроет репозиторий в браузере.",
              muted=True).grid(row=5, column=0, columnspan=3, sticky="w", padx=16, pady=(5, 5))

    def load(path, account):
        try:
            rows = compare(path, account)
            for row in rows:
                results.put(("row", with_branches(row)))
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
                table.add(value, STATUSES[value.status])
                counts[value.status] += 1
                status.set(f"Проверяем ветки… Обработано репозиториев: {sum(counts.values())}")
                continue
            loader.stop()
            loader_group.grid_remove()
            set_busy(False)
            if kind == "row_updated":
                previous, updated, error = value
                if updated is not previous:
                    counts[previous.status] -= 1
                    if updated is None:
                        table.update_row(previous.name)
                    else:
                        table.update_row(previous.name, updated, STATUSES[updated.status])
                        counts[updated.status] += 1
                if error:
                    status.set(error)
                    modal_message("Не удалось завершить действие", error, parent=root)
                    return
            summary = "  ·  ".join(f"{label} — {counts[key]}" for key, (label, _, _) in STATUSES.items())
            status.set(value if kind == "error" else summary)
            return
        root.after(75, show_results)

    def submit():
        nonlocal compared
        if button.cget("state") == "disabled":
            return
        path, account = folder.get().strip(), login.get()
        if not path or not account:
            status.set("Укажите папку и выберите сохранённого пользователя GitHub.")
            return
        set_busy(True)
        compared = (path, account)
        table.clear()
        counts.clear()
        status.set("Сравниваем папки с публичными репозиториями…")
        show_loader("Сравнение")
        Thread(target=load, args=(path, account), daemon=True).start()
        root.after(75, show_results)

    button = button_widget(panel, text="Сравнить", primary=True, command=submit)
    button.grid(row=4, column=2, sticky="ew", padx=(0, 16), pady=(8, 0))
    controls = (folder_input, login_input, profile_input, browse, add_button, save_button, profiles_button, users_button, button)
    root.bind("<Return>", lambda _event: submit())
    login_input.focus_set()
    if root.tk.call("tk", "windowingsystem") == "win32":
        def maximize_on_map(event):
            if event.widget is root:
                root.unbind("<Map>", startup_binding)
                root.after_idle(root.state, "zoomed")

        # CustomTkinter restores the window while setting up the Windows title bar.
        startup_binding = root.bind("<Map>", maximize_on_map, add="+")
    root.mainloop()
