# -*- coding: utf-8 -*-
"""Страница «База знаний»."""

import tkinter as tk
from tkinter import ttk


class KnowledgePage(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, style="Page.TFrame")
        self.app = app
        self.theme = self.app.theme
        self._build()
        self.refresh_list()

    def _build(self):
        colors = self.theme.colors
        top = ttk.Frame(self, style="Page.TFrame")
        top.pack(fill="x", padx=12, pady=(12, 6))

        tk.Label(top, text="Поиск:", bg=colors["bg"], fg=colors["text"]).pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.refresh_list())
        ent = ttk.Entry(top, textvariable=self.search_var, width=36)
        ent.pack(side="left", padx=6)

        tk.Label(top, text="Категория:", bg=colors["bg"], fg=colors["text"]).pack(
            side="left", padx=(10, 0))
        self.cat_var = tk.StringVar(value="Все категории")
        combo = ttk.Combobox(top, textvariable=self.cat_var, state="readonly",
                             values=["Все категории"] + list(self.app.content.categories), width=16)
        combo.pack(side="left", padx=6)
        combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_list())

        ttk.Button(top, text="Сбросить",
                   command=self.reset_filter).pack(side="left", padx=6)
        self.count_label = tk.Label(top, text="", bg=colors["bg"], fg=colors["muted"])
        self.count_label.pack(side="right")

        # Таблица советов
        table_frame = ttk.Frame(self, style="Page.TFrame")
        table_frame.pack(fill="both", expand=True, padx=12)
        self.tree = ttk.Treeview(table_frame, columns=("cat", "title", "sched"),
                                 show="headings", selectmode="browse")
        self.tree.heading("cat", text="Категория")
        self.tree.heading("title", text="Совет")
        self.tree.heading("sched", text="Когда / как часто")
        self.tree.column("cat", width=120, anchor="w")
        self.tree.column("title", width=420, anchor="w")
        self.tree.column("sched", width=260, anchor="w")
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        # Детали выбранного совета
        self.detail = tk.Text(self, height=12, wrap="word", relief="groove", bd=1,
                              padx=10, pady=8, font=self.theme.font(10),
                              bg=colors["card"], fg=colors["text"], state="disabled")
        self.detail.pack(fill="x", padx=12, pady=(6, 12))

    def reset_filter(self):
        self.search_var.set("")
        self.cat_var.set("Все категории")
        self.refresh_list()

    def refresh_list(self):
        query = self.search_var.get().strip()
        cat = self.cat_var.get()

        if query:
            tips = [hit.tip for hit in self.app.index.search(query)]
        else:
            tips = list(self.app.content.tips)
        if cat != "Все категории":
            tips = [t for t in tips if t.cat == cat]

        self.tree.delete(*self.tree.get_children())
        for tip in tips:
            self.tree.insert("", "end", iid=tip.id, values=(tip.cat, tip.title, tip.sched))
        self.count_label.config(text=f"Найдено: {len(tips)}")

    def on_select(self, _event=None):
        sel = self.tree.selection()
        if not sel:
            return
        tip = self.app.content.tip(sel[0])
        self.detail.config(state="normal")
        self.detail.delete("1.0", "end")
        color = self.app.content.cat_colors.get(tip.cat, "#333333")
        self.detail.tag_configure("cat", foreground=color,
                                  font=self.theme.font(10, "bold"))
        self.detail.tag_configure("h", font=self.theme.font(12, "bold"))
        self.detail.tag_configure("lab", foreground=self.theme.colors["muted"],
                                  font=self.theme.font(9, "bold"))
        self.detail.insert("end", tip.title + "\n\n", "h")
        self.detail.insert("end", f"[{tip.cat}]  ", "cat")
        self.detail.insert("end", tip.text + "\n\n")
        self.detail.insert("end", "Когда / как часто: ", "lab")
        self.detail.insert("end", tip.sched + "\n")
        self.detail.insert("end", "Источник: ", "lab")
        self.detail.insert("end", tip.source + "\n")
        self.detail.config(state="disabled")
