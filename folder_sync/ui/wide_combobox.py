import tkinter as tk
from pathlib import Path

import customtkinter as ctk


class WideComboBox(ctk.CTkComboBox):
    def __init__(self, *args, **kwargs):
        self._chevron_images = {}
        self._chevron_item = None
        super().__init__(*args, **kwargs)

    def _draw(self, no_color_updates=False):
        super()._draw(no_color_updates)
        self._canvas.itemconfigure("dropdown_arrow", state="hidden")
        variant = "disabled" if self._state == tk.DISABLED else self._get_appearance_mode()
        size = 24 if self._apply_widget_scaling(16) >= 20 else 16
        key = (variant, size)
        if key not in self._chevron_images:
            path = Path(__file__).resolve().parents[2] / "assets" / "icons" / f"chevron-{variant}-{size}.png"
            self._chevron_images[key] = tk.PhotoImage(master=self._canvas, file=path)
        x = round(self._apply_widget_scaling(self._current_width - self._current_height / 2))
        y = round(self._apply_widget_scaling(self._current_height / 2))
        if self._chevron_item is None:
            # Use the same hover and click bindings as the rest of the dropdown button.
            self._chevron_item = self._canvas.create_image(x, y, tags=("right_parts",))
        self._canvas.coords(self._chevron_item, x, y)
        self._canvas.itemconfigure(self._chevron_item, image=self._chevron_images[key])
        self._canvas.tag_raise(self._chevron_item)

    def _open_dropdown_menu(self):
        values = self.cget("values")
        if self._state == tk.DISABLED or not values:
            return

        previous_grab = self.grab_current()
        menu = tk.Toplevel(self, background=self._apply_appearance_mode(self.cget("border_color")))
        menu.withdraw()
        menu.overrideredirect(True)
        menu.transient(self.winfo_toplevel())

        height = min(len(values), 8)
        items = tk.Listbox(
            menu, height=height, exportselection=False, activestyle="none",
            background=self._apply_appearance_mode(self.cget("dropdown_fg_color")), foreground=self._apply_appearance_mode(self.cget("dropdown_text_color")),
            selectbackground=self._apply_appearance_mode(self.cget("dropdown_hover_color")), selectforeground=self._apply_appearance_mode(self.cget("dropdown_text_color")),
            borderwidth=0, highlightthickness=0, font=("Segoe UI", 13),
        )
        if len(values) > height:
            scrollbar = ctk.CTkScrollbar(menu, orientation="vertical", command=items.yview)
            scrollbar.pack(side="right", fill="y", padx=(0, 1), pady=1)
            items.configure(yscrollcommand=scrollbar.set)
        items.pack(side="left", fill="both", expand=True, padx=1, pady=1)
        items.insert("end", *values)
        current = self.get()
        index = values.index(current) if current in values else 0
        items.selection_set(index)
        items.activate(index)
        items.see(index)

        def close():
            menu.destroy()
            if previous_grab is not None and previous_grab.winfo_exists():
                previous_grab.grab_set()
            self.focus_set()

        def choose(index):
            value = values[index]
            close()
            self._dropdown_callback(value)
            return "break"

        def choose_selected(_event):
            selection = items.curselection()
            return choose(selection[0] if selection else items.index("active"))

        def choose_clicked(event):
            index = items.nearest(event.y)
            bounds = items.bbox(index)
            if bounds and bounds[1] <= event.y < bounds[1] + bounds[3]:
                return choose(index)
            return "break"

        def dismiss_outside(event):
            x, y = menu.winfo_rootx(), menu.winfo_rooty()
            if not (x <= event.x_root < x + menu.winfo_width()
                    and y <= event.y_root < y + menu.winfo_height()):
                close()
                return "break"

        items.bind("<ButtonRelease-1>", choose_clicked)
        items.bind("<Return>", choose_selected)
        menu.bind("<Escape>", lambda _: close())
        menu.bind("<ButtonPress-1>", dismiss_outside)
        menu.update_idletasks()
        x = self.winfo_rootx()
        y = self.winfo_rooty() + self.winfo_height()
        menu_height = menu.winfo_reqheight()
        if y + menu_height > self.winfo_vrooty() + self.winfo_vrootheight():
            y = self.winfo_rooty() - menu_height
        menu.geometry(f"{self.winfo_width()}x{menu_height}+{x}+{y}")
        menu.deiconify()
        menu.grab_set()
        items.focus_set()
