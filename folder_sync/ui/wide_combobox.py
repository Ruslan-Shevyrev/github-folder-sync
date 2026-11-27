import tkinter as tk

import customtkinter as ctk


class WideComboBox(ctk.CTkComboBox):
    def _open_dropdown_menu(self):
        # CustomTkinter 5.2.2 uses a native menu sized to its labels.
        values = self.cget("values")
        if not values:
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
