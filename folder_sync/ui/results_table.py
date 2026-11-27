import tkinter as tk
import webbrowser
import customtkinter as ctk

from .app_theme import theme_color
from .localization import error_text, tr


COLUMNS = (
    ("number", "\u2116", 45),
    ("refresh", "", 42),
    ("sync", "", 42),
    ("delete", "", 42),
    ("name", "Название", 190),
    ("status", "Статус", 160),
    ("visibility", "Видимость", 108),
    ("branches", "Ветки", 560),
    ("path", "Локальный путь", 265),
    ("github", "Ссылка на GitHub", 290),
)

FLEXIBLE_COLUMNS = {"name", "status", "branches", "path", "github"}


BRANCH_LABELS = {
    "equal": ("совпадает", "green"),
    "local": ("только локально", "yellow"),
    "github": ("только на GitHub", "yellow"),
    "diverged": ("ветки разошлись", "gray"),
    "unknown": ("неполная история", "gray"),
}


class ResultsTable(ctk.CTkFrame):
    def __init__(self, parent, on_sync=None, on_refresh=None, on_delete=None,
                 on_fix_origin=None, on_open_folder=None):
        super().__init__(parent, fg_color=theme_color("table_frame"), border_color=theme_color("table_border"),
                         border_width=1, corner_radius=10)
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)
        self.canvas = tk.Canvas(self, background=theme_color("table"), highlightthickness=0)
        vertical = ctk.CTkScrollbar(self, orientation="vertical", command=self.canvas.yview)
        horizontal = ctk.CTkScrollbar(self, orientation="horizontal", command=self.canvas.xview)
        self.canvas.configure(yscrollcommand=vertical.set, xscrollcommand=horizontal.set)
        self.canvas.grid(row=0, column=0, sticky="nsew", padx=(3, 0), pady=(3, 0))
        vertical.grid(row=0, column=1, sticky="ns", padx=2, pady=3)
        horizontal.grid(row=1, column=0, sticky="ew", padx=3, pady=2)
        self.canvas.bind("<MouseWheel>", self.scroll)
        self.tooltip = None
        self.on_sync = on_sync
        self.on_refresh = on_refresh
        self.on_delete = on_delete
        self.on_fix_origin = on_fix_origin
        self.on_open_folder = on_open_folder
        self.actions_enabled = True
        self.columns = COLUMNS
        self.row_data = {}
        self.item_bindings = {}
        self.action_fills = {}
        self.resize_job = None
        self.clear()
        self.canvas.bind("<Configure>", self.schedule_resize)

    def destroy(self):
        if self.resize_job is not None:
            self.after_cancel(self.resize_job)
        super().destroy()

    def scroll(self, event):
        self.canvas.yview_scroll(-int(event.delta / 120), "units")
        return "break"

    def schedule_resize(self, _event):
        if self.resize_job is not None:
            self.after_cancel(self.resize_job)
        self.resize_job = self.after(60, self.resize_columns)

    def resize_columns(self):
        self.resize_job = None
        minimum = sum(width for _, _, width in COLUMNS)
        available = max(minimum, self.canvas.winfo_width())
        if available == self.width:
            return

        space = available - minimum
        weight = sum(width for column, _, width in COLUMNS if column in FLEXIBLE_COLUMNS)
        columns = []
        allocated = 0
        consumed = 0
        for column, title, width in COLUMNS:
            if column in FLEXIBLE_COLUMNS:
                consumed += width
                target = space * consumed // weight
                width += target - allocated
                allocated = target
            columns.append((column, title, width))
        self.columns = columns

        left, top = self.canvas.canvasx(0), self.canvas.canvasy(0)
        anchor = next(
            ((name, top - row_top) for name, (_, row_top, bottom, _) in self.rows.items()
             if row_top <= top < bottom),
            None,
        )
        self.reset_canvas()
        for row, status in self.row_data.values():
            self.paint_next_row(row, status)
        self.canvas.configure(scrollregion=(0, 0, self.width, self.bottom))
        if anchor is not None:
            name, offset = anchor
            _, row_top, bottom, _ = self.rows[name]
            top = min(row_top + offset, bottom - 1)
        self.canvas.xview_moveto(left / self.width)
        self.canvas.yview_moveto(top / self.bottom)

    def bind_item(self, item, target, sequence, callback):
        token = self.canvas.tag_bind(target, sequence, callback)
        self.item_bindings.setdefault(item, []).append((target, sequence, token))

    def bind_link(self, item, command):
        self.bind_item(item, item, "<Enter>", lambda _: self.canvas.configure(cursor="hand2"))
        self.bind_item(item, item, "<Leave>", lambda _: self.canvas.configure(cursor=""))
        self.bind_item(item, item, "<Button-1>", lambda _: command())

    def delete_items(self, tag):
        for item in self.canvas.find_withtag(tag):
            self.action_fills.pop(item, None)
            for target, sequence, token in self.item_bindings.pop(item, ()):
                self.canvas.tag_unbind(target, sequence, token)
        self.canvas.delete(tag)

    def clear(self):
        self.row_data.clear()
        self.reset_canvas()
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)

    def reset_canvas(self):
        self.hide_tooltip()
        self.delete_items("all")
        self.canvas.configure(cursor="")
        self.width = sum(width for _, _, width in self.columns)
        self.bottom = 34
        self.rows = {}
        self.canvas.create_rectangle(0, 0, self.width, self.bottom, fill=theme_color("header"), outline="")
        x = 0
        for _, title, width in self.columns:
            self.text(x + 8, 7, tr(title), theme_color("text"), width - 16, bold=True)
            x += width
        self.canvas.configure(scrollregion=(0, 0, self.width, self.bottom))

    def text(self, x, y, label, color, width=None, *, bold=False):
        font = ("Segoe UI", 12, "bold" if bold else "normal")
        return self.canvas.create_text(x, y, anchor="nw", text=label, fill=color, width=width or 0,
                                       font=font)

    def add(self, row, status):
        self.row_data[row.name] = (row, status)
        self.paint_next_row(row, status)
        self.canvas.configure(scrollregion=(0, 0, self.width, self.bottom))

    def paint_next_row(self, row, status):
        top = self.bottom
        tag, self.bottom, index = self.draw_row(row, status, top, len(self.rows) + 1)
        self.rows[row.name] = (tag, top, self.bottom, index)

    def update_row(self, name, row=None, status=None):
        old_tag, top, old_bottom, index = self.rows[name]
        view_top = self.canvas.canvasy(0)
        number = self.canvas.itemcget(index, "text")
        self.hide_tooltip()
        self.delete_items(old_tag)
        self.canvas.configure(cursor="")
        if row is None:
            del self.row_data[name]
            del self.rows[name]
            bottom = top
        else:
            self.row_data[name] = (row, status)
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
        values = {"number": str(number), "name": row.name, "status": tr(label),
                  "visibility": row.visibility.capitalize() or "—",
                  "path": row.local_path, "github": row.github_url}
        sync_x = 0
        for column, _, width in self.columns:
            value = values.get(column)
            if column == "sync":
                sync_x = x + 7
            elif column == "refresh" and self.on_refresh is not None:
                self.draw_button(x + 7, top + 6, "↻", 28, lambda: self.on_refresh(row),
                                 hint=tr("Обновить"))
            elif column == "delete" and row.local_path and self.on_delete is not None:
                self.draw_button(x + 7, top + 6, None, 28, lambda: self.on_delete(row),
                                 hint=tr("Удалить"), background=theme_color("delete"), active=theme_color("delete_hover"), icon=self.draw_trash_icon)
            elif column == "branches":
                bottom = max(bottom, self.draw_branches(row, x + 8, top + 6, width - 16, sync_x) + 6)
            elif value:
                color = theme_color("link") if column == "github" else foreground
                item = self.text(x + 8, top + 6, value, color, width - 16)
                bottom = max(bottom, self.canvas.bbox(item)[3] + 7)
                if column == "number":
                    number_item = item
                if column == "github":
                    self.bind_link(item, lambda url=value: webbrowser.open(url))
                elif column == "path" and self.on_open_folder is not None:
                    self.bind_link(item, lambda path=value: self.on_open_folder(path))
            x += width
        self.canvas.coords(backdrop, 0, top, self.width, bottom)
        last_item = self.canvas.create_line(0, bottom, self.width, bottom, fill=theme_color("table_border"))
        tag = f"row-{backdrop}"
        for item in range(backdrop, last_item + 1):
            self.canvas.addtag_withtag(tag, item)
        return tag, bottom + 1, number_item


    def hide_tooltip(self, _event=None):
        if self.tooltip is not None:
            self.tooltip.destroy()
            self.tooltip = None

    def show_tooltip(self, event, text, *, monospace=False):
        self.hide_tooltip()
        tooltip = tk.Toplevel(self.canvas, background=theme_color("table_border"))
        self.tooltip = tooltip
        tooltip.wm_overrideredirect(True)
        font = ("Consolas" if monospace else "Segoe UI", 12)
        ctk.CTkLabel(tooltip, text=text, font=font, fg_color=theme_color("field")).pack(padx=6, pady=2)
        tooltip.update_idletasks()
        x = min(event.x_root + 12, tooltip.winfo_screenwidth() - tooltip.winfo_reqwidth())
        y = min(event.y_root + 18, tooltip.winfo_screenheight() - tooltip.winfo_reqheight())
        tooltip.geometry(f"+{max(0, x)}+{max(0, y)}")

    def draw_commit(self, x, y, side, commit, color, width):
        item = self.text(x, y, f"{side} ({commit[:12]})", theme_color(f"branch_{color}"), width)
        self.bind_item(item, item, "<Enter>", lambda event: self.show_tooltip(event, commit, monospace=True))
        self.bind_item(item, item, "<Leave>", self.hide_tooltip)
        return item

    def register_action(self, tag):
        self.canvas.addtag_withtag("row-action", tag)
        for item in self.canvas.find_withtag(tag):
            normal = self.canvas.itemcget(item, "fill")
            disabled = self.canvas.itemcget(item, "disabledfill")
            self.action_fills[item] = (normal, disabled)
            if not self.actions_enabled:
                self.canvas.itemconfigure(item, state="disabled", fill=disabled)

    def set_actions_enabled(self, enabled):
        self.actions_enabled = enabled
        state = "normal" if enabled else "disabled"
        # Tk can keep a pressed item as current and skip its disabled fill.
        for item, (normal, disabled) in self.action_fills.items():
            self.canvas.itemconfigure(item, state=state, fill=normal if enabled else disabled)
        if not enabled:
            self.hide_tooltip()
            self.canvas.configure(cursor="")

    def draw_trash_icon(self, x, y, tag):
        self.canvas.create_line(x - 7, y - 4, x + 7, y - 4, fill="#ffffff", disabledfill=theme_color("disabled_icon"), tags=tag)
        self.canvas.create_line(x - 3, y - 4, x - 3, y - 7, x + 3, y - 7, x + 3, y - 4,
                                fill="#ffffff", disabledfill=theme_color("disabled_icon"), tags=tag)
        self.canvas.create_line(x - 5, y - 2, x - 4, y + 7, x + 4, y + 7, x + 5, y - 2,
                                fill="#ffffff", disabledfill=theme_color("disabled_icon"), tags=tag)

    def draw_button(self, x, y, label, width, command, *, hint, background=None,
                    active=None, icon=None):
        background = background or theme_color("accent")
        active = active or theme_color("accent_hover")
        radius = 5
        right, bottom = x + width, y + 23
        button = self.canvas.create_polygon(
            x, y + radius, x, y, x + radius, y, right - radius, y, right, y,
            right, y + radius, right, bottom - radius, right, bottom, right - radius, bottom,
            x + radius, bottom, x, bottom, x, bottom - radius, smooth=True, fill=background, disabledfill=theme_color("disabled_fill"),
        )
        tag = f"button-{button}"
        self.canvas.addtag_withtag(tag, button)
        center_x, center_y = x + width / 2, y + 11
        if icon is None:
            self.canvas.create_text(center_x, center_y, text=label, fill="#ffffff", disabledfill=theme_color("disabled_icon"),
                                    font=("Segoe UI", 10, "bold"), tags=tag)
        else:
            icon(center_x, center_y, tag)
        self.register_action(tag)

        def hover(color, cursor):
            if self.actions_enabled:
                self.canvas.itemconfigure(button, fill=color)
                self.canvas.configure(cursor=cursor)

        def enter(event):
            if self.actions_enabled:
                hover(active, "hand2")
                self.show_tooltip(event, hint)

        def leave(_event):
            hover(background, "")
            self.hide_tooltip()

        def click(_event):
            if self.actions_enabled:
                self.hide_tooltip()
                command()

        self.bind_item(button, tag, "<Enter>", enter)
        self.bind_item(button, tag, "<Leave>", leave)
        self.bind_item(button, tag, "<Button-1>", click)
        return button

    def draw_download(self, row, branch, x, y):
        if not row.local_path:
            hint = "git clone"
        elif branch.status == "github":
            hint = tr("git fetch — создать локальную ветку")
        else:
            hint = "git pull"
        if branch is not None:
            hint += tr("\nВетка: {branch_name}", branch_name=branch.name)
        return self.draw_button(x, y, "↓", 28, lambda: self.on_sync(row, branch), hint=hint)

    def draw_branches(self, row, x, y, width, sync_x):
        if not row.local_path and row.github_url and not row.branches and not row.branch_error:
            label = self.text(x, y, tr("Клонировать репозиторий"), theme_color("text"), width)
            bottom = self.canvas.bbox(label)[3]
            if self.on_sync is not None:
                button = self.draw_download(row, None, sync_x, y)
                bottom = max(bottom, self.canvas.bbox(button)[3])
            return bottom
        if row.branch_error or not row.branches:
            can_fix = row.origin_mismatch and self.on_fix_origin is not None
            color = theme_color("link") if can_fix else theme_color("branch_gray")
            item = self.text(x, y, error_text(row.branch_error) or "—", color, width)
            if can_fix:
                self.canvas.itemconfigure(item, disabledfill=theme_color("disabled_icon"))
                self.register_action(item)
                self.bind_link(item, lambda: self.on_fix_origin(row) if self.actions_enabled else None)
            return self.canvas.bbox(item)[3]
        for branch in row.branches:
            side_width = 175
            arrow_width = 30
            name_width = width - 2 * side_width - arrow_width
            label = branch.name
            if branch.status in BRANCH_LABELS:
                detail, color = BRANCH_LABELS[branch.status]
                label = f"{label} · {tr(detail)}"
                foreground = theme_color(f"branch_{color}")
                local = remote = color
            else:
                foreground = theme_color("text")
                local = "yellow" if branch.status == "ahead" else "red"
                remote = "red" if branch.status == "ahead" else "yellow"

            items = [self.text(x, y, label, foreground, name_width - 8)]
            if branch.local_commit:
                items.append(self.draw_commit(x + name_width, y, tr("Локально"), branch.local_commit,
                                              local, side_width - 8))
            if not branch.local_commit:
                items.append(self.text(x + name_width, y, tr("Локально —"), theme_color("branch_gray")))
            if branch.status in {"behind", "ahead", "github", "local"}:
                inbound = branch.status in {"behind", "github"}
                items.append(self.text(x + name_width + side_width, y, "←" if inbound else "→",
                                       theme_color("arrow"), bold=True))
                if inbound and self.on_sync is not None:
                    items.append(self.draw_download(row, branch, sync_x, y))
            remote_x = x + name_width + side_width + arrow_width
            if branch.remote_commit:
                items.append(self.draw_commit(remote_x, y, "GitHub", branch.remote_commit,
                                              remote, side_width - 8))
            else:
                items.append(self.text(remote_x, y, "GitHub —", theme_color("branch_gray")))
            y = max(self.canvas.bbox(item)[3] for item in items) + 2
        return y
