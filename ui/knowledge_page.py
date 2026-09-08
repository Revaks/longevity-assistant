# -*- coding: utf-8 -*-
"""Страница «База знаний»: советы + полные тексты книг (вкладка «Книги»).

Советы — структурированные короткие рекомендации по четырём категориям.
Книги — отрывки из «120 лет жизни», «Мозга долгожителя» и «Кишечника
долгожителя»; ищутся BM25-движком (или гибридом BM25 + вектора Ollama).
"""

import re
import tkinter as tk
from tkinter import ttk

from longevity.search import BookSearch

from .rag import BOOKS_PAGE_LIMIT


class KnowledgePage(ttk.Frame):
    def __init__(self, master, app):
        super().__init__(master, style="Page.TFrame")
        self.app = app
        self.theme = self.app.theme
        # Ретривер появляется у реального приложения; в тестах страницы его
        # нет — тогда поиск по книгам работает на локальном BM25-индексе.
        retriever = getattr(app, "retriever", None)
        self._book_search = (retriever.search_bm25
                             if retriever is not None else BookSearch(app.content).search)
        self._build()
        self.refresh_list()
        self.refresh_books()
        retriever = getattr(app, "retriever", None)
        if retriever is not None and hasattr(retriever, "subscribe"):
            retriever.subscribe(self._on_retriever_change)

    def _build(self):
        colors = self.theme.colors
        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True, padx=8, pady=(8, 4))

        tips_tab = ttk.Frame(notebook, style="Page.TFrame")
        notebook.add(tips_tab, text="Советы")
        self._tips_tab = tips_tab
        self._build_tips_tab(tips_tab, colors)

        books_tab = ttk.Frame(notebook, style="Page.TFrame")
        notebook.add(books_tab, text="Книги")
        self._books_tab = books_tab
        self._build_books_tab(books_tab, colors)

    # -- вкладка «Советы» -------------------------------------------------
    def _build_tips_tab(self, parent, colors):
        top = ttk.Frame(parent, style="Page.TFrame")
        top.pack(fill="x", padx=12, pady=(10, 6))

        tk.Label(top, text="Поиск:", bg=colors["bg"], fg=colors["text"]).pack(side="left")
        self.search_var = tk.StringVar()
        self.search_var.trace_add("write", lambda *a: self.refresh_list())
        ent = ttk.Entry(top, textvariable=self.search_var, width=32)
        ent.pack(side="left", padx=6)

        tk.Label(top, text="Категория:", bg=colors["bg"], fg=colors["text"]).pack(
            side="left", padx=(10, 0))
        self.cat_var = tk.StringVar(value="Все категории")
        combo = ttk.Combobox(top, textvariable=self.cat_var, state="readonly",
                             values=["Все категории"] + list(self.app.content.categories),
                             width=15)
        combo.pack(side="left", padx=6)
        combo.bind("<<ComboboxSelected>>", lambda e: self.refresh_list())

        ttk.Button(top, text="Сбросить",
                   command=self.reset_filter).pack(side="left", padx=6)
        self.count_label = tk.Label(top, text="", bg=colors["bg"], fg=colors["muted"])
        self.count_label.pack(side="right")

        table_frame = ttk.Frame(parent, style="Page.TFrame")
        table_frame.pack(fill="both", expand=True, padx=12)
        self.tree = ttk.Treeview(table_frame, columns=("cat", "title", "sched"),
                                 show="headings", selectmode="browse")
        self.tree.heading("cat", text="Категория")
        self.tree.heading("title", text="Совет")
        self.tree.heading("sched", text="Когда / как часто")
        self.tree.column("cat", width=120, anchor="w")
        self.tree.column("title", width=400, anchor="w")
        self.tree.column("sched", width=240, anchor="w")
        vsb = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=vsb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self.on_select)

        self.detail = tk.Text(parent, height=11, wrap="word", relief="groove", bd=1,
                              padx=10, pady=8, font=self.theme.font(10),
                              bg=colors["card"], fg=colors["text"], state="disabled")
        self.detail.pack(fill="x", padx=12, pady=(6, 10))

    # -- вкладка «Книги» ---------------------------------------------------
    def _build_books_tab(self, parent, colors):
        top = ttk.Frame(parent, style="Page.TFrame")
        top.pack(fill="x", padx=12, pady=(10, 6))

        tk.Label(top, text="Поиск по книгам:", bg=colors["bg"],
                 fg=colors["text"]).pack(side="left")
        self.books_var = tk.StringVar()
        self.books_var.trace_add("write", lambda *a: self.refresh_books())
        ent = ttk.Entry(top, textvariable=self.books_var, width=32)
        ent.pack(side="left", padx=6)
        self.books_hybrid_var = tk.BooleanVar(value=False)
        self.hybrid_check = ttk.Checkbutton(
            top, text="Смысловой поиск (Ollama)",
            variable=self.books_hybrid_var, command=self.refresh_books)
        self.hybrid_check.pack(side="left", padx=(4, 0))
        ttk.Button(top, text="Сбросить",
                   command=self.reset_books).pack(side="left", padx=6)
        self.books_status = tk.Label(top, text="", bg=colors["bg"], fg=colors["muted"])
        self.books_status.pack(side="right")
        self.books_count = tk.Label(top, text="", bg=colors["bg"], fg=colors["muted"])
        self.books_count.pack(side="right", padx=8)

        table_frame = ttk.Frame(parent, style="Page.TFrame")
        table_frame.pack(fill="both", expand=True, padx=12)
        self.books_tree = ttk.Treeview(table_frame, columns=("book", "section"),
                                       show="headings", selectmode="browse")
        self.books_tree.heading("book", text="Книга")
        self.books_tree.heading("section", text="Раздел")
        self.books_tree.column("book", width=200, anchor="w")
        self.books_tree.column("section", width=560, anchor="w")
        vsb = ttk.Scrollbar(table_frame, orient="vertical",
                            command=self.books_tree.yview)
        self.books_tree.configure(yscrollcommand=vsb.set)
        self.books_tree.pack(side="left", fill="both", expand=True)
        vsb.pack(side="right", fill="y")
        self.books_tree.bind("<<TreeviewSelect>>", self.on_book_select)

        self.book_detail = tk.Text(parent, height=11, wrap="word", relief="groove",
                                   bd=1, padx=10, pady=8, font=self.theme.font(10),
                                   bg=colors["card"], fg=colors["text"],
                                   state="disabled")
        self.book_detail.pack(fill="x", padx=12, pady=(6, 10))
        self._update_books_status()

    def _update_books_status(self):
        retriever = getattr(self.app, "retriever", None)
        hybrid_ready = retriever is not None and retriever.vector_ready
        # «Смысловой поиск» доступен только при готовом векторном кэше.
        try:
            self.hybrid_check.config(state="normal" if hybrid_ready else "disabled")
        except tk.TclError:
            pass
        if not hybrid_ready:
            self.books_hybrid_var.set(False)
        if retriever is None:
            self.books_status.config(text="Поиск по отрывкам (BM25)")
        elif hybrid_ready:
            self.books_status.config(text=f"BM25 + вектора ({retriever.model})")
        elif retriever.busy:
            self.books_status.config(text=retriever.status)
        elif retriever.model:
            self.books_status.config(text="Индексация ещё не завершена — поиск BM25")
        else:
            self.books_status.config(text="Поиск по отрывкам (BM25)")

    def _on_retriever_change(self, _retriever):
        try:
            self._update_books_status()
        except tk.TclError:
            pass

    # -- действия: советы --------------------------------------------------
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
            self.tree.insert("", "end", iid=tip.id,
                             values=(tip.cat, tip.title, tip.sched))
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

    # -- действия: книги ----------------------------------------------------
    def reset_books(self):
        self.books_var.set("")
        self.refresh_books()

    def refresh_books(self):
        query = self.books_var.get().strip()
        self.books_tree.delete(*self.books_tree.get_children())
        content = self.app.content

        def row(passage):
            try:
                book_title = content.book(passage.book).title
            except KeyError:
                book_title = passage.book
            self.books_tree.insert("", "end", iid=passage.id,
                                   values=(book_title, passage.section or "—"))

        if not query:
            # Как и вкладка «Советы»: без запроса показываем всё, поиск сужает.
            for passage in content.passages:
                row(passage)
            self.books_count.config(text=f"Отрывков: {len(content.passages)}")
            return

        hits = self._search_books(query)
        for hit in hits:
            row(hit.passage)
        mode = "гибрид" if self._hybrid_active() else "BM25"
        self.books_count.config(text=f"Найдено: {len(hits)} ({mode})")

    def _hybrid_active(self) -> bool:
        """Гибридный поиск (BM25 + вектора) включён и возможен."""
        retriever = getattr(self.app, "retriever", None)
        return bool(self.books_hybrid_var.get()
                    and retriever is not None and retriever.vector_ready)

    def _search_books(self, query: str):
        limit = BOOKS_PAGE_LIMIT
        if self._hybrid_active():
            retriever = getattr(self.app, "retriever", None)
            return retriever.search(query, limit=limit, prefer_vector=True)
        return self._book_search(query, limit=limit)

    def on_book_select(self, _event=None):
        sel = self.books_tree.selection()
        if not sel:
            return
        passage = self.app.content.passage(sel[0])
        self.book_detail.config(state="normal")
        self.book_detail.delete("1.0", "end")
        self.book_detail.tag_configure("h", font=self.theme.font(12, "bold"))
        self.book_detail.tag_configure("lab", foreground=self.theme.colors["muted"],
                                       font=self.theme.font(9, "bold"))
        try:
            book_title = self.app.content.book(passage.book).title
        except KeyError:
            book_title = passage.book
        self.book_detail.insert("end", f"{book_title}\n", "h")
        if passage.section:
            self.book_detail.insert("end", passage.section + "\n", "lab")
        self.book_detail.insert("end", "\n" + passage.text + "\n")
        self._highlight_terms(self.book_detail, self.books_var.get())
        self.book_detail.config(state="disabled")

    def _highlight_terms(self, widget, query: str) -> None:
        """Подсветить вхождения слов запроса в тексте отрывка."""
        widget.tag_configure("hl", background="#fde68a")
        for token in re.findall(r"[А-Яа-яЁёA-Za-z0-9]{3,}", query):
            start = "1.0"
            while True:
                pos = widget.search(token, start, stopindex="end", nocase=True)
                if not pos:
                    break
                end = widget.index(f"{pos}+{len(token)}c")
                widget.tag_add("hl", pos, end)
                start = end
