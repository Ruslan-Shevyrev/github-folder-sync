import tkinter as tk
import webbrowser
from collections import Counter
from queue import Empty, Queue
from threading import Thread
from tkinter import filedialog, ttk

from comparison import compare


STATUSES = {
    "both": ("Есть в обоих местах", "#20372f", "#b8f5cf"),
    "github": ("Только на GitHub", "#2e3242", "#dcdfeb"),
    "local": ("Только локально", "#432b37", "#ffc4cb"),
}


def configure_theme(root):
    root.configure(background="#101321")
    style = ttk.Style(root)
    style.theme_use("clam")
    style.configure(".", background="#191d30", foreground="#f4f1ff", font=("Segoe UI", 10))
    style.configure("Panel.TFrame", borderwidth=1, relief="solid", bordercolor="#343956")
    style.configure("Heading.TLabel", font=("Segoe UI", 13, "bold"))
    style.configure("Status.TLabel", foreground="#b8b5d0")
    style.configure("TEntry", fieldbackground="#222740", insertcolor="#f4f1ff",
                    bordercolor="#343956", lightcolor="#222740", darkcolor="#222740", padding=(9, 7))
    style.configure("TButton", background="#222740", bordercolor="#343956", padding=(10, 7))
    style.map("TButton", background=[("active", "#343052")], foreground=[("disabled", "#9591ac")])
    style.configure("Accent.TButton", background="#7446ee", bordercolor="#7446ee",
                    padding=(16, 7), font=("Segoe UI", 10, "bold"))
    style.map("Accent.TButton", background=[("disabled", "#222740"), ("active", "#865cff")])
    style.configure("Treeview", background="#101321", fieldbackground="#101321",
                    bordercolor="#343956", rowheight=30)
    style.configure("Treeview.Heading", background="#222740", relief="flat",
                    font=("Segoe UI", 10, "bold"))
    style.map("Treeview.Heading", background=[("active", "#222740")])
    style.map("Treeview", background=[("selected", "#513ca0")],
              foreground=[("selected", "#ffffff")])
    for orientation in ("Vertical", "Horizontal"):
        style.configure(f"{orientation}.TScrollbar", background="#343956", troughcolor="#191d30")


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


def run():
    root = tk.Tk()
    root.title("Папки и репозитории GitHub")
    root.geometry("1080x560")
    root.minsize(760, 360)
    configure_theme(root)

    folder = tk.StringVar()
    login = tk.StringVar()
    status = tk.StringVar(value="Выберите папку и укажите логин GitHub.")
    results = Queue()
    urls = {}

    panel = ttk.Frame(root, style="Panel.TFrame", padding=16)
    panel.pack(fill="both", expand=True, padx=12, pady=12)
    panel.columnconfigure(1, weight=1)
    panel.rowconfigure(4, weight=1)
    ttk.Label(panel, text="Публичные репозитории GitHub", style="Heading.TLabel").grid(
        row=0, column=0, columnspan=3, sticky="w", pady=(0, 14)
    )
    ttk.Label(panel, text="Локальная папка").grid(row=1, column=0, sticky="w")
    folder_input = ttk.Entry(panel, textvariable=folder)
    folder_input.grid(row=1, column=1, sticky="ew", padx=8)
    ttk.Label(panel, text="Логин GitHub").grid(row=2, column=0, sticky="w")
    login_input = ttk.Entry(panel, textvariable=login)
    login_input.grid(row=2, column=1, sticky="ew", padx=8, pady=8)
    if root.tk.call("tk", "windowingsystem") == "win32":
        for entry in (folder_input, login_input):
            entry.bind("<Control-KeyPress>", edit_shortcut_on_windows)

    def choose_folder():
        selected = filedialog.askdirectory(parent=root, title="Выберите папку", mustexist=True)
        if selected:
            folder.set(selected)

    browse = ttk.Button(panel, text="Обзор…", command=choose_folder)
    browse.grid(row=1, column=2, sticky="ew")

    table = ttk.Treeview(panel, columns=("name", "status", "path", "github"), show="headings")
    columns = (
        ("name", "Название", 205),
        ("status", "Статус", 175),
        ("path", "Локальный путь", 295),
        ("github", "Ссылка на GitHub", 285),
    )
    for column, title, width in columns:
        table.heading(column, text=title, anchor="w")
        table.column(column, width=width, minwidth=width, stretch=column in ("path", "github"))
    for key, (_, background, foreground) in STATUSES.items():
        table.tag_configure(key, background=background, foreground=foreground)
    vertical = ttk.Scrollbar(panel, orient="vertical", command=table.yview)
    horizontal = ttk.Scrollbar(panel, orient="horizontal", command=table.xview)
    table.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
    table.grid(row=4, column=0, columnspan=3, sticky="nsew")
    vertical.grid(row=4, column=3, sticky="ns")
    horizontal.grid(row=5, column=0, columnspan=3, sticky="ew")
    ttk.Label(panel, textvariable=status, style="Status.TLabel", wraplength=680).grid(
        row=6, column=0, columnspan=3, sticky="w", pady=(10, 0)
    )

    def open_link(event):
        if table.identify_column(event.x) == "#4":
            url = urls.get(table.identify_row(event.y))
            if url:
                webbrowser.open(url)

    table.bind("<Double-1>", open_link)
    ttk.Label(panel, text="Двойной щелчок по ссылке откроет репозиторий в браузере.",
              style="Status.TLabel").grid(row=3, column=0, columnspan=3, sticky="w", pady=(0, 8))

    def load(path, account):
        try:
            results.put((compare(path, account), None))
        except (ValueError, OSError, TypeError, KeyError) as error:
            results.put((None, str(error)))

    def show_results():
        try:
            rows, error = results.get_nowait()
        except Empty:
            root.after(75, show_results)
            return
        for widget in controls:
            widget.state(["!disabled"])
        if error is not None:
            status.set(error)
            return
        counts = Counter(row.status for row in rows)
        for row in rows:
            item = table.insert("", "end", values=(
                row.name, STATUSES[row.status][0], row.local_path, row.github_url
            ), tags=(row.status,))
            if row.github_url:
                urls[item] = row.github_url
        status.set("  ·  ".join(f"{label} — {counts[key]}" for key, (label, _, _) in STATUSES.items()))

    def submit():
        if button.instate(["disabled"]):
            return
        path, account = folder.get().strip(), login.get().strip()
        for widget in controls:
            widget.state(["disabled"])
        table.delete(*table.get_children())
        urls.clear()
        status.set("Сравниваем папки с публичными репозиториями…")
        Thread(target=load, args=(path, account), daemon=True).start()
        root.after(75, show_results)

    button = ttk.Button(panel, text="Сравнить", style="Accent.TButton", command=submit)
    button.grid(row=2, column=2, sticky="ew")
    controls = (folder_input, login_input, browse, button)
    root.bind("<Return>", lambda _event: submit())
    folder_input.focus_set()
    root.mainloop()
