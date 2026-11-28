import os
import re
import tkinter as tk
import webbrowser
from collections import Counter
from dataclasses import replace
from pathlib import Path
from queue import Empty, Queue
from threading import Thread
from tkinter import filedialog

import customtkinter as ctk

from ..branches import BranchError, github_repository
from ..comparison import compare, delete_local_folder, refresh_repository, with_branches
from ..comparison_cache import cache_for_profile, load_cache, reconcile_cache, save_cache, sync_cache_locations
from ..git_sync import change_origin, clone_from_github, corrected_origin, read_local_origin, sync_from_github
from ..settings import load_settings, resolve_token, save_settings, settings_path
from .app_theme import THEMES, WHITE, set_theme, theme_color
from .dialog_position import set_windows_titlebar_theme
from .dialogs import (
    FONT, button_widget, combo_widget, configure_theme, confirm_action, edit_shortcut_on_windows,
    entry_widget, label_widget, modal_message,
)
from .localization import DEFAULT_LANGUAGE, LANGUAGES, error_text, set_language, tr
from .profiles import add_profile, open_profiles
from .results_table import ResultsTable
from .users import add_user, open_users


STATUSES = {
    "both": "status.both",
    "github": "status.github_only",
    "local": "status.local_only",
}


def status_style(key):
    return STATUSES[key], theme_color(f"{key}_bg"), theme_color(f"{key}_fg")


class MainWindow(ctk.CTk):
    def _windows_set_titlebar_icon(self):
        # Keep the application icon set by iconphoto in run().
        pass

    def _windows_set_titlebar_color(self, color_mode):
        # CustomTkinter 5.2.2 normally withdraws the window to repaint its frame.
        set_windows_titlebar_theme(self, color_mode.lower() == "dark")


def run():
    path = settings_path()
    try:
        preferences = load_settings(path)
        sync_cache_locations(path, preferences)
        reconcile_cache(path, preferences)
    except (OSError, ValueError):
        preferences = {}
    language = preferences.get("language")
    theme = preferences.get("theme")
    if theme not in THEMES:
        theme = "Dark"
    if not isinstance(language, str) or language not in LANGUAGES:
        language = DEFAULT_LANGUAGE
    set_theme(theme)
    ctk.set_appearance_mode(theme)
    root = MainWindow(fg_color=theme_color("background"))
    icon_path = Path(__file__).resolve().parents[2] / "assets" / "sync-icon.png"
    root.iconphoto(True, tk.PhotoImage(master=root, file=str(icon_path)))
    root.geometry("1080x560")
    root.minsize(760, 360)
    snapshot = None
    while True:
        set_language(language)
        set_theme(theme)
        ctk.set_appearance_mode(theme)
        root.configure(fg_color=theme_color("background"))
        configure_theme(root)
        result = run_window(root, language, theme, path, snapshot)
        if result is None:
            break
        language, theme, snapshot = result


def run_window(root, language, theme, preferences_path, snapshot=None):
    root.title(tr("window.title"))
    folder = tk.StringVar()
    login = tk.StringVar()
    profile_name = tk.StringVar()
    status = tk.StringVar(value=tr("compare.initial"))
    try:
        preferences = load_settings(preferences_path)
    except (OSError, ValueError) as error:
        preferences = {"users": {}, "profiles": {}, "default_profile": None}
        status.set(tr("error.read_settings", error=error_text(str(error))))
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
            modal_message(tr("error.save"), str(error), parent=root)
            return
        next_window = (new_language, new_theme, {
            "folder": folder.get(), "login": login.get(), "profile": profile_name.get(),
            "only_problems": only_problems.get(), "rows": list(all_rows.values()),
            "expanded": expanded, "cached": from_cache, "compared": compared, "cache": active_cache,
        })
        root.quit()

    panel = ctk.CTkFrame(root, fg_color=theme_color("background"), corner_radius=0)
    panel.pack(fill="both", expand=True)
    panel.grid_propagate(False)
    panel.columnconfigure(1, weight=1)
    panel.rowconfigure(6, weight=1)
    appearance = ctk.CTkFrame(panel, fg_color="transparent")
    appearance.grid(row=0, column=2, sticky="e", padx=(0, 16), pady=(14, 12))
    language_display = tk.StringVar(master=root, value=LANGUAGES[language])
    language_codes = {label: code for code, label in LANGUAGES.items()}
    language_picker = combo_widget(
        appearance, variable=language_display, values=list(language_codes), width=96,
        command=lambda chosen: switch_appearance("language", language_codes[chosen]),
    )
    language_picker.pack(side="left")
    theme_display = tk.StringVar(master=root, value=theme)
    theme_picker = combo_widget(appearance, variable=theme_display, values=list(THEMES), width=105,
                                command=lambda chosen: switch_appearance("theme", chosen))
    theme_picker.pack(side="left", padx=(8, 0))
    ctk.CTkLabel(panel, text=tr("window.heading"), font=("Segoe UI", 32, "bold"),
                 text_color=theme_color("text")).grid(
        row=0, column=0, columnspan=2, sticky="w", padx=(20, 0), pady=(16, 18)
    )
    profile_bar = ctk.CTkFrame(panel, fg_color=theme_color("field"), corner_radius=9,
                              border_width=1, border_color=theme_color("border"))
    profile_bar.grid(row=1, column=0, columnspan=3, sticky="ew", padx=16)
    details = ctk.CTkFrame(panel, fg_color="transparent")
    details.grid(row=2, column=0, columnspan=3, sticky="ew", pady=(8, 0))
    details.columnconfigure(1, weight=1)
    expanded = snapshot["expanded"] if snapshot else not preferences.get("default_profile")

    def update_summary(*_):
        selection = " · ".join(filter(None, (profile_name.get(), login.get())))
        title = tr("profile.label")
        disclosure.configure(text=("▾  " if expanded else "▸  ") + title + (f": {selection}" if selection else ""))

    def toggle_details():
        nonlocal expanded
        expanded = not expanded
        if expanded:
            details.grid()
        else:
            details.grid_remove()
        update_summary()

    disclosure = button_widget(profile_bar, text="", command=toggle_details)
    disclosure.configure(anchor="w", font=("Segoe UI", 16), height=40, fg_color="transparent", border_width=0)
    disclosure.pack(side="left", fill="x", expand=True, padx=6, pady=4)
    if not expanded:
        details.grid_remove()
    update_summary()
    summary_traces = [(var, var.trace_add("write", update_summary)) for var in (profile_name, login)]

    label_widget(details, text=tr("user.github")).grid(row=1, column=0, sticky="w", padx=(16, 4))
    login_input = combo_widget(details, variable=login, values=[])
    login_input.grid(row=1, column=1, sticky="ew", padx=8)
    label_widget(details, text=tr("folder.local")).grid(row=2, column=0, sticky="w", padx=(16, 4))
    folder_input = entry_widget(details, textvariable=folder)
    folder_input.grid(row=2, column=1, sticky="ew", padx=8, pady=8)
    if root.tk.call("tk", "windowingsystem") == "win32":
        folder_input.bind("<Control-KeyPress>", edit_shortcut_on_windows)

    label_widget(details, text=tr("profile.label")).grid(row=3, column=0, sticky="w", padx=(16, 4))
    profile_input = combo_widget(details, variable=profile_name, values=[])
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

    def users_changed(data, original=None, name=None):
        nonlocal preferences
        preferences = data
        if original is None and name is not None:
            login.set(name)
            profile_name.set("")
            status.set(tr("user.selected"))
        elif original is not None and name is None:
            if login.get() == original:
                login.set("")
                profile_name.set("")
                show_profile_cache()
            elif profile_name.get() and profile_name.get() not in data["profiles"]:
                profile_name.set("")
                show_profile_cache()
            status.set(tr("user.deleted", name=original))
        elif original is not None:
            if login.get() == original and name != original:
                login.set(name)
                if profile_name.get():
                    show_profile_cache()
            status.set(tr("user.saved", name=name))
        refresh_choices()

    def profiles_changed(data, original=None, name=None):
        nonlocal preferences
        preferences = data
        refresh_choices()
        if name is not None:
            if original is None or profile_name.get() == original:
                profile_name.set(name)
                apply_profile()
            status.set(tr("profile.saved", name=name))
        elif original is not None:
            if profile_name.get() == original:
                profile_name.set("")
                show_profile_cache()
            status.set(tr("profile.deleted", name=original))

    add_button = button_widget(details, text=tr("user.add"), command=lambda: add_user(root, preferences_path, users_changed))
    add_button.grid(row=1, column=2, sticky="ew", padx=(0, 16))
    save_button = button_widget(details, text=tr("button.save_profile"), command=lambda: add_profile(
        root, preferences_path, folder.get().strip(), login.get(), profiles_changed
    ))
    save_button.grid(row=3, column=2, sticky="ew", padx=(0, 16))
    navigation = ctk.CTkFrame(details, fg_color="transparent")
    navigation.grid(row=4, column=1, sticky="e", padx=8, pady=(8, 0))
    users_button = button_widget(navigation, text=tr("user.view"), command=lambda: open_users(
        root, preferences_path, login.get(), users_changed
    ))
    users_button.pack(side="left", padx=(0, 6))
    profiles_button = button_widget(navigation, text=tr("profile.view"), command=lambda: open_profiles(
        root, preferences_path, profile_name.get(), profiles_changed
    ))
    profiles_button.pack(side="left")
    profile_input.configure(command=apply_profile)
    refresh_choices()

    def choose_folder():
        selected = filedialog.askdirectory(parent=root, title=tr("folder.choose"), mustexist=True)
        if selected:
            folder.set(selected)

    browse = button_widget(details, text=tr("button.browse"), command=choose_folder)
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
            modal_message(tr("compare.outdated"), tr("compare.repeat_required"),
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
            run_row_action(row, tr("progress.row_refresh"))

    def request_delete(row):
        if not can_update_row() or not row.local_path:
            return
        path = Path(row.local_path)
        base_path = compared[0]
        set_busy(True)
        confirm_action(
            root, tr("folder.delete_title"),
            tr("folder.delete_confirm", path=path),
            tr("button.delete"),
            lambda: run_row_action(row, tr("progress.delete"), lambda: delete_local_folder(base_path, path)),
            destructive=True, on_cancel=lambda: set_busy(False),
        )

    def request_sync(row, branch):
        if not can_update_row():
            return
        if row.local_path:
            destination = Path(row.local_path)
            action = tr("branch.create_local") if branch.status == "github" else tr("branch.pull_title")
            operation = sync_from_github
            progress_text = tr("progress.create_branch") if branch.status == "github" else tr("progress.pull")
            button_text = tr("branch.create") if branch.status == "github" else tr("button.refresh")
        else:
            destination = Path(compared[0]).expanduser().absolute() / row.name
            action = tr("repo.clone_title")
            operation = clone_from_github
            progress_text = tr("progress.clone")
            button_text = tr("repo.clone")
        branch_line = tr("branch.line", branch_name=branch.name) if branch else ""
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
            modal_message(tr("error.origin_address"), str(error), parent=root)
            return
        display_origin = re.sub(r"(?<=://)[^/\s@]+@", "***@", current)
        command = f'git remote set-url origin "{target}"'
        set_busy(True)
        confirm_action(
            root, tr("origin.fix"),
            tr("origin.command", display_origin=display_origin, command=command),
            tr("button.ok"),
            lambda: run_row_action(row, tr("origin.fix"), lambda: change_origin(path, current, target)),
            on_cancel=lambda: set_busy(False),
        )

    def open_local_folder(path):
        try:
            if not Path(path).is_dir():
                raise FileNotFoundError(tr("error.folder_unavailable", path=path))
            if hasattr(os, "startfile"):
                os.startfile(path)
            else:
                webbrowser.open(Path(path).as_uri())
        except OSError as error:
            modal_message(tr("error.open_folder"), str(error), parent=root)

    table = ResultsTable(panel, on_sync=request_sync, on_refresh=request_refresh, on_delete=request_delete,
                         on_fix_origin=request_fix_origin, on_open_folder=open_local_folder)
    table.grid(row=6, column=0, columnspan=3, sticky="nsew", padx=16)
    status_line = ctk.CTkFrame(panel, fg_color=theme_color("field"), border_color=theme_color("border"), border_width=1)
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
    table_notes.grid(row=5, column=0, columnspan=3, sticky="ew", padx=16, pady=(14, 14))
    cache_notice = label_widget(table_notes, text=tr("cache.notice"), muted=True)
    cache_notice.configure(text_color=theme_color("branch_red"))
    cache_notice.grid(row=0, column=1, sticky="w", padx=(12, 0))
    cache_notice.grid_remove()
    problem_filter = ctk.CTkCheckBox(
        table_notes, text=tr("filter.attention"), variable=only_problems, font=FONT, text_color=theme_color("text"),
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
        return cache_for_profile(preferences_path, name, profile, preferences["users"])

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
            status.set(tr("compare.load_prompt"))
            return
        compared = (folder.get().strip(), login.get(), None)
        active_cache = path
        from_cache = True
        for row in rows:
            add_result(row)
        cache_notice.grid()
        status.set(summary_text())

    def remember_table():
        if active_cache is None or active_cache != selected_cache_path():
            return ""
        try:
            save_cache(active_cache, all_rows.values())
        except OSError:
            return tr("cache.save_error")
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
                status.set(tr("progress.checked", count=sum(counts.values())))
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
                    modal_message(tr("error.action_failed"), error, parent=root)
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
            status.set(tr("error.folder_and_saved_user_required"))
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
        status.set(tr("progress.comparing"))
        show_loader(tr("progress.compare"))
        Thread(target=load, args=(path, account, token), daemon=True).start()
        root.after(75, show_results)

    button = button_widget(profile_bar, text=tr("button.compare"), primary=True, command=submit)
    button.pack(side="right", padx=8, pady=6)
    controls = (disclosure, folder_input, login_input, profile_input, browse, add_button, save_button,
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
    if expanded:
        login_input.focus_set()
    if snapshot is None and root.tk.call("tk", "windowingsystem") == "win32":
        def maximize_on_map(event):
            if event.widget is root:
                root.unbind("<Map>", startup_binding)
                root.after_idle(root.state, "zoomed")

        # CustomTkinter restores the window while setting up the Windows title bar.
        startup_binding = root.bind("<Map>", maximize_on_map, add="+")
    root.mainloop()
    for variable, trace in summary_traces:
        variable.trace_remove("write", trace)
    if next_window is not None:
        panel.destroy()
    return next_window
