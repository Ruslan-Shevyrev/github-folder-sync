import tkinter as tk
import webbrowser
from tkinter import ttk


COLUMNS = (
    ("number", "\u2116", 45),
    ("refresh", "", 42),
    ("sync", "", 42),
    ("delete", "", 42),
    ("name", "Название", 190),
    ("status", "Статус", 160),
    ("branches", "Ветки", 560),
    ("path", "Локальный путь", 265),
    ("github", "Ссылка на GitHub", 290),
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
    def __init__(self, parent, on_sync=None, on_refresh=None, on_delete=None):
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
        self.on_sync = on_sync
        self.on_refresh = on_refresh
        self.on_delete = on_delete
        self.clear()

    def scroll(self, event):
        self.canvas.yview_scroll(-int(event.delta / 120), "units")
        return "break"

    def clear(self):
        self.hide_commit()
        self.canvas.delete("all")
        self.canvas.configure(cursor="")
        self.width = sum(width for _, _, width in COLUMNS)
        self.bottom = 34
        self.rows = {}
        self.canvas.create_rectangle(0, 0, self.width, self.bottom, fill="#222740", outline="")
        x = 0
        for _, title, width in COLUMNS:
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
        top = self.bottom
        tag, self.bottom, index = self.draw_row(row, status, top, len(self.rows) + 1)
        self.rows[row.name] = (tag, top, self.bottom, index)
        self.canvas.configure(scrollregion=(0, 0, self.width, self.bottom))

    def update_row(self, name, row=None, status=None):
        old_tag, top, old_bottom, index = self.rows[name]
        view_top = self.canvas.canvasy(0)
        number = self.canvas.itemcget(index, "text")
        self.hide_commit()
        self.canvas.delete(old_tag)
        self.canvas.configure(cursor="")
        if row is None:
            del self.rows[name]
            bottom = top
        else:
            tag, bottom, index = self.draw_row(row, status, top, number)
            self.rows[name] = (tag, top, bottom, index)
        delta = bottom - old_bottom
        if delta:
            for position, (key, (tag, row_top, row_bottom, index)) in enumerate(self.rows.items(), 1):
                if key != name and row_top >= old_bottom:
                    self.canvas.move(tag, 0, delta)
                    self.rows[key] = (tag, row_top + delta, row_bottom + delta, index)
                    if row is None:
                        self.canvas.itemconfigure(index, text=position)
            self.bottom += delta
            self.canvas.configure(scrollregion=(0, 0, self.width, self.bottom))
            if view_top >= old_bottom:
                view_top += delta
            self.canvas.yview_moveto(view_top / self.bottom)

    def draw_row(self, row, status, top, number):
        label, background, foreground = status
        backdrop = self.canvas.create_rectangle(0, top, self.width, top, fill=background, outline="")
        x = 0
        bottom = top + 34
        values = {"number": str(number), "name": row.name, "status": label,
                  "path": row.local_path, "github": row.github_url}
        sync_x = 0
        for column, _, width in COLUMNS:
            value = values.get(column)
            if column == "sync":
                sync_x = x + 7
            elif column == "refresh" and self.on_refresh is not None:
                self.draw_button(x + 7, top + 6, "↻", 28, lambda: self.on_refresh(row))
            elif column == "delete" and row.local_path and self.on_delete is not None:
                self.draw_button(x + 7, top + 6, None, 28, lambda: self.on_delete(row),
                                 background="#813c51", active="#a24f67", icon=self.draw_trash_icon)
            elif column == "branches":
                bottom = max(bottom, self.draw_branches(row, x + 8, top + 6, width - 16, sync_x) + 6)
            elif value:
                item = self.text(x + 8, top + 6, value, foreground, width - 16)
                bottom = max(bottom, self.canvas.bbox(item)[3] + 7)
                if column == "number":
                    number_item = item
                if column == "github":
                    self.canvas.tag_bind(item, "<Double-1>", lambda _, url=value: webbrowser.open(url))
            x += width
        self.canvas.coords(backdrop, 0, top, self.width, bottom)
        last_item = self.canvas.create_line(0, bottom, self.width, bottom, fill="#343956")
        tag = f"row-{backdrop}"
        for item in range(backdrop, last_item + 1):
            self.canvas.addtag_withtag(tag, item)
        return tag, bottom + 1, number_item


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

    def draw_trash_icon(self, x, y, tag):
        self.canvas.create_line(x - 7, y - 4, x + 7, y - 4, fill="#ffffff", tags=tag)
        self.canvas.create_line(x - 3, y - 4, x - 3, y - 7, x + 3, y - 7, x + 3, y - 4,
                                fill="#ffffff", tags=tag)
        self.canvas.create_line(x - 5, y - 2, x - 4, y + 7, x + 4, y + 7, x + 5, y - 2,
                                fill="#ffffff", tags=tag)

    def draw_button(self, x, y, label, width, command, *, background="#7446ee", active="#865cff", icon=None):
        button = self.canvas.create_rectangle(x, y, x + width, y + 23, fill=background, outline="")
        tag = f"button-{button}"
        self.canvas.addtag_withtag(tag, button)
        center_x, center_y = x + width / 2, y + 11
        if icon is None:
            self.canvas.create_text(center_x, center_y, text=label, fill="#ffffff",
                                    font=("Segoe UI", 10, "bold"), tags=tag)
        else:
            icon(center_x, center_y, tag)

        def hover(color, cursor):
            self.canvas.itemconfigure(button, fill=color)
            self.canvas.configure(cursor=cursor)

        self.canvas.tag_bind(tag, "<Enter>", lambda _: hover(active, "hand2"))
        self.canvas.tag_bind(tag, "<Leave>", lambda _: hover(background, ""))
        self.canvas.tag_bind(tag, "<Button-1>", lambda _: command())
        return button

    def draw_download(self, row, branch, x, y):
        return self.draw_button(x, y, "↓", 28, lambda: self.on_sync(row, branch))

    def draw_branches(self, row, x, y, width, sync_x):
        if not row.local_path and row.github_url and not row.branches and not row.branch_error:
            label = self.text(x, y, "Клонировать репозиторий", "#f4f1ff", width)
            bottom = self.canvas.bbox(label)[3]
            if self.on_sync is not None:
                button = self.draw_download(row, None, sync_x, y)
                bottom = max(bottom, self.canvas.bbox(button)[3])
            return bottom
        if row.branch_error or not row.branches:
            item = self.text(x, y, row.branch_error or "—", BRANCH_COLORS["gray"], width)
            return self.canvas.bbox(item)[3]
        for branch in row.branches:
            side_width = 175
            arrow_width = 30
            name_width = width - 2 * side_width - arrow_width
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
            if not branch.local_commit:
                items.append(self.text(x + name_width, y, "Локально —", BRANCH_COLORS["gray"]))
            if branch.status in {"behind", "ahead", "github", "local"}:
                inbound = branch.status in {"behind", "github"}
                items.append(self.text(x + name_width + side_width, y, "←" if inbound else "→",
                                       "#85839e", bold=True))
                if inbound and self.on_sync is not None:
                    items.append(self.draw_download(row, branch, sync_x, y))
            remote_x = x + name_width + side_width + arrow_width
            if branch.remote_commit:
                items.append(self.draw_commit(remote_x, y, "GitHub", branch.remote_commit,
                                              remote, side_width - 8))
            else:
                items.append(self.text(remote_x, y, "GitHub —", BRANCH_COLORS["gray"]))
            y = max(self.canvas.bbox(item)[3] for item in items) + 2
        return y
