import tkinter as tk
from tkinter import ttk

import customtkinter as ctk

from .app_theme import WHITE, theme_color
from .dialog_position import center_windows_dialog
from .localization import error_text, tr
from .wide_combobox import WideComboBox


FONT = ("Segoe UI", 13)


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
    cancel = button_widget(actions, text=tr("button.cancel"))
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

        dialog = confirm_action(parent, title, details, tr("button.confirm"), accept, destructive=warning)
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
    cancel = button_widget(actions, text=tr("button.cancel"))
    cancel.pack(side="left", padx=(0, 6))
    save_button = button_widget(actions, text=tr("button.save"), primary=True)
    save_button.pack(side="left")
    close = show_dialog(dialog, focus)
    cancel.configure(command=close)

    def submit():
        try:
            if save():
                close()
        except (OSError, ValueError, RuntimeError) as error:
            modal_message(tr("error.save"), str(error), parent=dialog)
        return "break"

    save_button.configure(command=submit)
    dialog.bind("<Return>", lambda _: submit())
