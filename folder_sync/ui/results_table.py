import tkinter as tk
from tkinter import font as tkfont
import webbrowser
from pathlib import Path
import customtkinter as ctk

from .app_theme import theme_color
from .localization import error_text, tr


COLUMNS = (
    ("number", "\u2116", 45),
    ("refresh", "", 42),
    ("sync", "", 42),
    ("name", "column.name", 150),
    ("status", "column.status", 0),
    ("visibility", "column.visibility", 85),
    ("branches", "column.branches", 0),
    ("path", "column.local_path", 155),
    ("github", "column.github_url", 145),
    ("delete", "", 42),
)

BUTTON_SIZE = 32
COMMIT_GAP = 8
FLEXIBLE_COLUMNS = {"name", "path", "github"}


BRANCH_LABELS = {
    "ahead": ("branch.github_behind", "yellow"),
    "behind": ("branch.local_behind", "yellow"),
    "equal": ("branch.equal", "green"),
    "local": ("branch.local_only", "yellow"),
    "github": ("branch.github_only", "yellow"),
    "diverged": ("branch.diverged", "gray"),
    "unknown": ("branch.incomplete", "gray"),
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
        def scrollbar_changed(scrollbar, first, last):
            if self.tooltip is not None and self.tooltip_view != (self.canvas.canvasx(0), self.canvas.canvasy(0)):
                self.hide_tooltip()
            scrollbar.set(first, last)

        self.canvas.configure(yscrollcommand=lambda a, b: scrollbar_changed(vertical, a, b),
                              xscrollcommand=lambda a, b: scrollbar_changed(horizontal, a, b))
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
        text_font = tkfont.Font(root=self.canvas, family="Segoe UI", size=12)
        heading_font = tkfont.Font(root=self.canvas, family="Segoe UI", size=12, weight="bold")
        widest_label = max(text_font.measure(tr(key)) for key in
                           ("status.both", "status.github_only", "status.local_only"))
        # Two 8px margins, a 16px icon and a 5px gap before the label.
        status_width = max(16 + heading_font.measure(tr("column.status")), 37 + widest_label)
        self.base_columns = tuple((key, title, status_width if key == "status" else width)
                                  for key, title, width in COLUMNS)
        self.branch_header_width = heading_font.measure(tr("column.branches")) + 18
        self.branch_widths = {}
        self.base_columns = tuple((key, title, self.branch_header_width if key == "branches" else width)
                                  for key, title, width in self.base_columns)
        self.columns = self.base_columns
        self.row_data = {}
        self.item_bindings = {}
        self.action_styles = {}
        directory = Path(__file__).resolve().parents[2] / "assets" / "icons"
        theme = ctk.get_appearance_mode().lower()
        self.branch_icons = {
            name: tk.PhotoImage(master=self.canvas, file=directory / f"branch-{name}-{theme}.png")
            for name in ("branch", "match", "warning", "unknown")
        }
        self.status_icons = {
            key: tk.PhotoImage(master=self.canvas, file=directory / f"status-{key}-{theme}.png")
            for key in ("both", "github", "local")
        }
        self.button_faces = {
            style: tk.PhotoImage(master=self.canvas, file=directory / f"button-{theme}-{style}.png")
            for style in ("normal", "hover", "download", "download-hover", "disabled", "trash", "trash-hover")
        }
        self.icons = {
            name: (tk.PhotoImage(master=self.canvas, file=directory / f"{name}-{theme}.png"),
                   tk.PhotoImage(master=self.canvas, file=directory / f"{name}-disabled.png"))
            for name in ("refresh", "download", "delete")
        }
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

    def schedule_resize(self, _event=None):
        if self.resize_job is not None:
            self.after_cancel(self.resize_job)
        self.resize_job = self.after(60, self.resize_columns)

    def resize_columns(self):
        self.resize_job = None
        branch_width = max(self.branch_header_width, max(self.branch_widths.values(), default=0))
        base = [(key, title, branch_width if key == "branches" else width)
                for key, title, width in self.base_columns]
        minimum = sum(width for _, _, width in base)
        available = max(minimum, self.canvas.winfo_width())

        space = available - minimum
        weight = sum(width for column, _, width in self.base_columns if column in FLEXIBLE_COLUMNS)
        columns = []
        allocated = 0
        consumed = 0
        for column, title, width in base:
            if column in FLEXIBLE_COLUMNS:
                consumed += width
                target = space * consumed // weight
                width += target - allocated
                allocated = target
            columns.append((column, title, width))
        if list(self.columns) == columns:
            return
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
            self.action_styles.pop(item, None)
            for target, sequence, token in self.item_bindings.pop(item, ()):
                self.canvas.tag_unbind(target, sequence, token)
        self.canvas.delete(tag)

    def clear(self):
        self.row_data.clear()
        self.branch_widths.clear()
        self.schedule_resize()
        self.reset_canvas()
        self.canvas.xview_moveto(0)
        self.canvas.yview_moveto(0)

    def reset_canvas(self):
        self.hide_tooltip()
        self.delete_items("all")
        self.canvas.configure(cursor="")
        self.width = sum(width for _, _, width in self.columns)
        self.bottom = 42
        self.rows = {}
        self.canvas.create_rectangle(0, 0, self.width, self.bottom, fill=theme_color("header"), outline="")
        x = 0
        for column, title, width in self.columns:
            if column == "number":
                self.text(x + width / 2, self.bottom / 2, tr(title), theme_color("text"), bold=True, anchor="center")
            else:
                self.text(x + 8, 10, tr(title), theme_color("text"), width - 16, bold=True)
            x += width
            self.canvas.create_line(x, 0, x, self.bottom, fill=theme_color("table_border"))
        self.canvas.configure(scrollregion=(0, 0, self.width, self.bottom))

    def text(self, x, y, label, color, width=None, *, bold=False, anchor="nw"):
        font = ("Segoe UI", 12, "bold" if bold else "normal")
        return self.canvas.create_text(x, y, anchor=anchor, text=label, fill=color, width=width or 0,
                                       font=font)

    def add(self, row, status):
        self.row_data[row.name] = (row, status)
        self.paint_next_row(row, status)
        self.schedule_resize()
        self.canvas.configure(scrollregion=(0, 0, self.width, self.bottom))

    def paint_next_row(self, row, status):
        top = self.bottom
        tag, self.bottom, index = self.draw_row(row, status, top, len(self.rows) + 1)
        self.rows[row.name] = (tag, top, self.bottom, index)

    def update_row(self, name, row=None, status=None):
        self.schedule_resize()
        self.branch_widths.pop(name, None)
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
        backdrop = self.canvas.create_rectangle(0, top, self.width, top, fill=theme_color("table"), outline="")
        x = 0
        bottom = top + 58
        centered_cells = []
        edges = []
        values = {"number": str(number), "name": row.name, "status": tr(label),
                  "visibility": row.visibility.capitalize() if row.github_url else "",
                  "path": row.local_path, "github": row.github_url.removeprefix("https://github.com/")}
        sync_buttons = []
        refresh_cell = None
        sync_x = 0
        for column, _, width in self.columns:
            cell = None
            value = values.get(column)
            if column == "sync":
                sync_x = x + (width - BUTTON_SIZE) / 2
            elif column == "refresh" and self.on_refresh is not None:
                button = self.draw_button(x + (width - BUTTON_SIZE) / 2, top + 6, "refresh", lambda: self.on_refresh(row),
                                 hint=tr("button.refresh"))
                refresh_cell = cell = f"button-{button}"
            elif column == "delete" and row.local_path and self.on_delete is not None:
                button = self.draw_button(x + (width - BUTTON_SIZE) / 2, top + 6, "delete", lambda: self.on_delete(row),
                                 hint=tr("button.delete"))
                cell = f"button-{button}"
            elif column == "branches":
                bottom = max(bottom, self.draw_branches(row, x + 8, top + 6, sync_x, sync_buttons) + 6)
            elif column == "status":
                item = self.text(x + 29, top + 6, value, foreground)
                _, upper, right, lower = self.canvas.bbox(item)
                badge = self.rounded_box(x + 3, upper - 3, right + 4, lower + 3, fill=background)
                self.canvas.tag_lower(badge, item)
                icon = self.canvas.create_image(x + 16, (upper + lower) // 2, image=self.status_icons[row.status])
                cell = f"badge-{badge}"
                for part in (badge, icon, item):
                    self.canvas.addtag_withtag(cell, part)
                bottom = max(bottom, lower + 7)
            elif value:
                if column == "github" and row.github_url:
                    value = "↗ " + value
                color = theme_color("link") if column == "github" else theme_color("text")
                if column == "number":
                    item = self.text(x + width / 2, top + 6, value, color, anchor="n")
                else:
                    item = self.text(x + 8, top + 6, value, color, width - 16)
                cell = item
                bottom = max(bottom, self.canvas.bbox(item)[3] + 7)
                if column == "number":
                    number_item = item
                if column == "github" and row.github_url:
                    self.bind_link(item, lambda url=row.github_url: webbrowser.open(url))
                elif column == "path" and row.local_path and self.on_open_folder is not None:
                    self.bind_link(item, lambda path=value: self.on_open_folder(path))
            if cell is not None:
                centered_cells.append(cell)
            x += width
            edges.append(x)
        if len(sync_buttons) == 1:
            centered_cells.append(f"button-{sync_buttons[0]}")
        elif sync_buttons and refresh_cell:
            centered_cells.remove(refresh_cell)
            first_middle = sync_buttons[(len(sync_buttons) - 1) // 2]
            last_middle = sync_buttons[len(sync_buttons) // 2]
            middle_y = (self.canvas.bbox(first_middle)[1] + self.canvas.bbox(last_middle)[1]) // 2
            self.canvas.move(refresh_cell, 0, middle_y - self.canvas.bbox(refresh_cell)[1])
        for cell in centered_cells:
            _, upper, _, lower = self.canvas.bbox(cell)
            self.canvas.move(cell, 0, (top + bottom - upper - lower) // 2)
        for edge in edges[:-1]:
            self.canvas.create_line(edge, top, edge, bottom, fill=theme_color("table_border"))
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

    def show_tooltip(self, target, text, *, monospace=False):
        self.hide_tooltip()
        tooltip = tk.Toplevel(self.canvas, background=theme_color("table_border"))
        self.tooltip = tooltip
        self.tooltip_view = self.canvas.canvasx(0), self.canvas.canvasy(0)
        tooltip.withdraw()
        tooltip.wm_overrideredirect(True)
        font = ("Consolas" if monospace else "Segoe UI", 12)
        ctk.CTkLabel(tooltip, text=text, font=font, fg_color=theme_color("field")).pack(padx=6, pady=2)
        tooltip.update_idletasks()
        if self.tooltip is not tooltip:
            return
        left, top, _, bottom = self.canvas.bbox(target)
        origin_x, origin_y = self.canvas.winfo_rootx(), self.canvas.winfo_rooty()
        x = origin_x + left - self.canvas.canvasx(0)
        y = origin_y + bottom - self.canvas.canvasy(0) + 4
        right_limit = origin_x + self.canvas.winfo_width() - tooltip.winfo_reqwidth()
        x = max(origin_x, min(x, right_limit))
        if y + tooltip.winfo_reqheight() > origin_y + self.canvas.winfo_height():
            y = max(origin_y, origin_y + top - self.canvas.canvasy(0) - tooltip.winfo_reqheight() - 4)
        tooltip.geometry(f"+{int(x)}+{int(y)}")
        tooltip.deiconify()

    def draw_commit(self, x, y, side, commit, color):
        item = self.text(x, y, f"{side} ({commit[:12]})", theme_color(f"branch_{color}"))
        self.bind_item(item, item, "<Enter>", lambda event: self.show_tooltip(item, commit, monospace=True))
        self.bind_item(item, item, "<Leave>", self.hide_tooltip)
        return item

    def register_action(self, tag):
        self.canvas.addtag_withtag("row-action", tag)
        for item in self.canvas.find_withtag(tag):
            option = "image" if self.canvas.type(item) == "image" else "fill"
            normal = self.canvas.itemcget(item, option)
            disabled = self.canvas.itemcget(item, "disabled" + option)
            self.action_styles[item] = (option, normal, disabled)
            if not self.actions_enabled:
                self.canvas.itemconfigure(item, state="disabled", **{option: disabled})

    def set_actions_enabled(self, enabled):
        self.actions_enabled = enabled
        state = "normal" if enabled else "disabled"
        # Tk can keep a pressed item as current and skip its disabled fill.
        for item, (option, normal, disabled) in self.action_styles.items():
            self.canvas.itemconfigure(item, state=state, **{option: normal if enabled else disabled})
        if not enabled:
            self.hide_tooltip()
            self.canvas.configure(cursor="")

    def rounded_box(self, x, y, right, bottom, **colors):
        radius = 6
        return self.canvas.create_polygon(
            x, y + radius, x, y, x + radius, y, right - radius, y, right, y,
            right, y + radius, right, bottom - radius, right, bottom, right - radius, bottom,
            x + radius, bottom, x, bottom, x, bottom - radius, smooth=True, **colors,
        )

    def draw_button(self, x, y, icon, command=None, *, hint=""):
        x, y = round(x), round(y)
        face, hover_face = {
            "refresh": ("normal", "hover"),
            "download": ("download", "download-hover"),
            "delete": ("trash", "trash-hover"),
        }[icon]
        normal = self.button_faces[face]
        active = self.button_faces[hover_face]
        disabled = self.button_faces["disabled"]
        button = self.canvas.create_image(x, y, anchor="nw", image=normal if command else disabled,
                                          disabledimage=disabled)
        tag = f"button-{button}"
        self.canvas.addtag_withtag(tag, button)
        normal_icon, disabled_icon = self.icons[icon]
        self.canvas.create_image(x + BUTTON_SIZE / 2, y + BUTTON_SIZE / 2,
                                 image=normal_icon if command else disabled_icon,
                                 disabledimage=disabled_icon, tags=tag)
        if command is None:
            return button
        self.register_action(tag)

        def hover(face, cursor):
            if self.actions_enabled:
                self.canvas.itemconfigure(button, image=face)
                self.canvas.configure(cursor=cursor)

        def enter(event):
            if self.actions_enabled:
                hover(active, "hand2")
                self.show_tooltip(button, hint)

        def leave(_event):
            hover(normal, "")
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
            hint = tr("branch.fetch_hint")
        else:
            hint = "git pull"
        if branch is not None:
            hint += tr("branch.line", branch_name=branch.name)
        return self.draw_button(x, y, "download", lambda: self.on_sync(row, branch), hint=hint)

    def draw_branches(self, row, x, y, sync_x, sync_buttons):
        # Measure the actual unwrapped items, including icons, arrows and both cell margins.
        right = x
        def bounds(item):
            nonlocal right
            _, _, item_right, bottom = self.canvas.bbox(item)
            right = max(right, item_right)
            self.branch_widths[row.name] = right - x + 16
            return item_right, bottom

        if not row.local_path and row.github_url and not row.branches and not row.branch_error:
            label = self.text(x, y, tr("repo.clone_title"), theme_color("text"))
            bottom = bounds(label)[1]
            if self.on_sync is not None:
                button = self.draw_download(row, None, sync_x, y)
                sync_buttons.append(button)
                bottom = max(bottom, self.canvas.bbox(button)[3])
            return bottom
        if row.branch_error or not row.branches:
            can_fix = row.origin_mismatch and self.on_fix_origin is not None
            color = theme_color("link") if can_fix else theme_color("branch_gray")
            item = self.text(x, y, error_text(row.branch_error) or "—", color)
            if can_fix:
                self.canvas.itemconfigure(item, disabledfill=theme_color("disabled_icon"))
                self.register_action(item)
                self.bind_link(item, lambda: self.on_fix_origin(row) if self.actions_enabled else None)
            return bounds(item)[1]
        for branch in row.branches:
            detail, color = BRANCH_LABELS.get(branch.status, BRANCH_LABELS["unknown"])
            branch_top = y
            symbol = {"green": "match", "gray": "unknown"}.get(color, "warning")
            for icon, label, ink in (("branch", branch.name, theme_color("text")),
                                     (symbol, tr(detail), theme_color(f"branch_{color}"))):
                self.canvas.create_image(x, y + 2, anchor="nw", image=self.branch_icons[icon])
                item = self.text(x + 21, y, label, ink, bold=icon == "branch")
                y = max(y + 18, bounds(item)[1])
            local = remote = color
            if branch.status == "ahead":
                remote = "red"
            elif branch.status == "behind":
                local = "red"
            items = []
            if branch.local_commit:
                items.append(self.draw_commit(x, y, tr("branch.local_commit"), branch.local_commit,
                                              local))
            else:
                items.append(self.text(x, y, tr("branch.local_commit"), theme_color("branch_gray")))
            remote_x = bounds(items[-1])[0] + COMMIT_GAP
            if branch.status in {"behind", "ahead", "github", "local"}:
                inbound = branch.status in {"behind", "github"}
                items.append(self.text(remote_x, y, "←" if inbound else "→",
                                       theme_color("arrow"), bold=True))
                remote_x = bounds(items[-1])[0] + COMMIT_GAP
            if branch.remote_commit:
                items.append(self.draw_commit(remote_x, y, "GitHub", branch.remote_commit,
                                              remote))
            else:
                items.append(self.text(remote_x, y, "GitHub", theme_color("branch_gray")))
            branch_bottom = max(bounds(item)[1] for item in items)
            button_y = (branch_top + branch_bottom - BUTTON_SIZE) / 2
            if branch.status in {"behind", "github"} and self.on_sync is not None:
                button = self.draw_download(row, branch, sync_x, button_y)
            else:
                button = self.draw_button(sync_x, button_y, "download")
            sync_buttons.append(button)
            y = branch_bottom + 5
        return y
