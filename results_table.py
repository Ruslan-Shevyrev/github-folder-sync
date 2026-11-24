import tkinter as tk
import webbrowser
from tkinter import ttk


COLUMNS = (
    ("Название", 190),
    ("Статус", 160),
    ("Ветки", 530),
    ("Локальный путь", 265),
    ("Ссылка на GitHub", 290),
)

BRANCH_COLORS = {
    "green": "#83eca4",
    "yellow": "#ffe08a",
    "red": "#ff999f",
    "gray": "#c3c6d2",
}

BRANCH_LABELS = {
    "equal": ("совпадает", "green"),
    "local": ("только локально", "yellow"),
    "github": ("только на GitHub", "yellow"),
    "diverged": ("ветки разошлись", "gray"),
    "unknown": ("неполная история", "gray"),
}


class ResultsTable(ttk.Frame):
    def __init__(self, parent):
        super().__init__(parent)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, background="#101321", highlightthickness=0)
        vertical = ttk.Scrollbar(self, orient="vertical", command=self.canvas.yview)
        horizontal = ttk.Scrollbar(self, orient="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.canvas.grid(row=0, column=0, sticky="nsew")
        vertical.grid(row=0, column=1, sticky="ns")
        horizontal.grid(row=1, column=0, sticky="ew")
        self.canvas.bind("<MouseWheel>", self.scroll)
        self.commit_tooltip = None
        self.clear()

    def scroll(self, event):
        self.canvas.yview_scroll(-int(event.delta / 120), "units")
        return "break"

    def clear(self):
        self.hide_commit()
        self.canvas.delete("all")
        self.width = sum(width for _, width in COLUMNS)
        self.bottom = 34
        self.canvas.create_rectangle(0, 0, self.width, self.bottom, fill="#222740", outline="")
        x = 0
        for title, width in COLUMNS:
            self.text(x + 8, 7, title, "#f4f1ff", width - 16, bold=True)
            x += width
        self.canvas.configure(scrollregion=(0, 0, self.width, self.bottom))
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)

    def text(self, x, y, label, color, width=None, *, bold=False):
        font = ("Segoe UI", 10, "bold" if bold else "normal")
        return self.canvas.create_text(x, y, anchor="nw", text=label, fill=color, width=width or 0,
                                       font=font)

    def add(self, row, status):
        label, background, foreground = status
        top = self.bottom
        backdrop = self.canvas.create_rectangle(0, top, self.width, top, fill=background, outline="")
        x = 0
        bottom = top + 32
        for index, (value, (_, width)) in enumerate(zip(
            (row.name, label, "", row.local_path, row.github_url), COLUMNS
        )):
            if index == 2:
                bottom = max(bottom, self.draw_branches(row, x + 8, top + 6, width - 16) + 6)
            elif value:
                item = self.text(x + 8, top + 6, value, foreground, width - 16)
                bottom = max(bottom, self.canvas.bbox(item)[3] + 7)
                if index == 4:
                    self.canvas.tag_bind(item, "<Double-1>", lambda _, url=value: webbrowser.open(url))
            x += width
        self.canvas.coords(backdrop, 0, top, self.width, bottom)
        self.canvas.create_line(0, bottom, self.width, bottom, fill="#343956")
        self.bottom = bottom + 1
        self.canvas.configure(scrollregion=(0, 0, self.width, self.bottom))

    def hide_commit(self, _event=None):
        if self.commit_tooltip is not None:
            self.commit_tooltip.destroy()
            self.commit_tooltip = None

    def show_commit(self, event, commit):
        self.hide_commit()
        tooltip = tk.Toplevel(self.canvas, background="#343956")
        self.commit_tooltip = tooltip
        tooltip.wm_overrideredirect(True)
        ttk.Label(tooltip, text=commit, padding=(8, 4)).pack(padx=1, pady=1)
        tooltip.update_idletasks()
        x = min(event.x_root + 12, tooltip.winfo_screenwidth() - tooltip.winfo_reqwidth())
        y = min(event.y_root + 18, tooltip.winfo_screenheight() - tooltip.winfo_reqheight())
        tooltip.geometry(f"+{max(0, x)}+{max(0, y)}")

    def draw_commit(self, x, y, side, commit, color, width):
        item = self.text(x, y, f"{side} ({commit[:12]})", BRANCH_COLORS[color], width)
        self.canvas.tag_bind(item, "<Enter>", lambda event: self.show_commit(event, commit))
        self.canvas.tag_bind(item, "<Leave>", self.hide_commit)
        return item

    def draw_branches(self, row, x, y, width):
        if row.branch_error or not row.branches:
            item = self.text(x, y, row.branch_error or "—", BRANCH_COLORS["gray"], width)
            return self.canvas.bbox(item)[3]
        for branch in row.branches:
            side_width = 175
            name_width = width - 2 * side_width
            label = branch.name
            if branch.status in BRANCH_LABELS:
                detail, color = BRANCH_LABELS[branch.status]
                label = f"{label} · {detail}"
                foreground = BRANCH_COLORS[color]
                local = remote = color
            else:
                foreground = "#f4f1ff"
                local = "yellow" if branch.status == "ahead" else "red"
                remote = "red" if branch.status == "ahead" else "yellow"

            items = [self.text(x, y, label, foreground, name_width - 8)]
            if branch.local_commit:
                items.append(self.draw_commit(x + name_width, y, "Локально", branch.local_commit,
                                              local, side_width - 8))
            if branch.remote_commit:
                offset = side_width if branch.local_commit else 0
                items.append(self.draw_commit(x + name_width + offset, y, "GitHub", branch.remote_commit,
                                              remote, side_width - 8))
            y = max(self.canvas.bbox(item)[3] for item in items) + 2
        return y
