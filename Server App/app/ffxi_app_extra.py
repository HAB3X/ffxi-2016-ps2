#!/usr/bin/env python3
"""FFXI 2016 Server App - extra windows: Moderation (roles), Chat rules (word filter, spam, scheduled messages, chat history,
filter log) and the "/" command helper of the world chat box. Fan Project by Habex. Standard library only."""
import os, re, threading, time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk


def _C():
    import ffxi_server_app as A
    return A.C, A.RoundButton, A.TITLE


# ======================================================================== "/" command helper (autocomplete)
class CommandHelper:
    """A suggestion list over the chat box: commands after "/", player names after "@" or as the first word,
    zones for /tp, items for /give, jobs for /job, roles for /promote. Up/Down choose, Tab or Enter take it."""
    ROWS = 8

    def __init__(self, app, entry, anchor):
        C, _, _ = _C()
        self.app, self.entry, self.anchor = app, entry, anchor
        self.items = []          # (insert text, label)
        self.sel = 0
        self.top = 0
        self.moved = False
        self.ctx = None
        self.frame = tk.Frame(anchor, bg=C['line'], bd=0)
        self.rows = []
        for i in range(self.ROWS):
            lab = tk.Label(self.frame, text='', anchor='w', bg=C['card'], fg=C['text'], padx=10, pady=4,
                           font=(app.f.mono_s[0], app.f.s(12)), cursor='hand2')
            lab.bind('<Button-1>', lambda e, i=i: self._click(i))
            self.rows.append(lab)
        self.item_cache = {}
        self.pending = None
        e = entry
        e.bind('<KeyRelease>', self.on_key, add='+')
        e.bind('<Down>', lambda ev: self.move(1))
        e.bind('<Up>', lambda ev: self.move(-1))
        e.bind('<Tab>', lambda ev: self.accept() or 'break')
        e.bind('<Escape>', lambda ev: self.hide())

    def visible(self):
        return bool(self.frame.winfo_ismapped())

    def hide(self):
        if self.visible():
            self.frame.place_forget()
        self.moved = False

    def _paint(self):
        C, _, _ = _C()
        n = min(self.ROWS, len(self.items))
        if self.sel < self.top:
            self.top = self.sel
        if self.sel >= self.top + n:
            self.top = self.sel - n + 1
        for i, lab in enumerate(self.rows):
            k = self.top + i
            if i < n and k < len(self.items):
                lab.config(text=self.items[k][1], bg=C['sel'] if k == self.sel else C['card'])
                lab.pack(fill='x', padx=1, pady=(1 if i == 0 else 0, 1))
            else:
                lab.pack_forget()

    def show(self, items):
        self.items = items[:40]
        if not self.items:
            return self.hide()
        self.sel, self.top, self.moved = 0, 0, False
        self._paint()
        self.frame.place(in_=self.anchor, relx=0, rely=1.0, anchor='sw', relwidth=1.0, y=-2)
        self.frame.lift()

    def _click(self, i):
        self.sel = self.top + i
        self.accept()
        self.entry.focus_force()

    def move(self, d):
        if not self.visible():
            return None
        self.sel = max(0, min(len(self.items) - 1, self.sel + d))
        self.moved = True
        self._paint()
        return 'break'

    def wants_enter(self):
        """Enter takes the suggestion only after the arrow keys were used (otherwise it sends)."""
        return self.visible() and self.moved

    def accept(self):
        if not self.visible() or not self.items:
            return False
        ins, _ = self.items[self.sel]
        text = self.entry.get()
        start = self.ctx[0] if self.ctx else len(text)
        new = text[:start] + ins
        self.entry.delete(0, 'end')
        self.entry.insert(0, new)
        self.entry.icursor('end')
        self.hide()
        self.app.root.after(10, self.update)
        return True

    def on_key(self, ev):
        if ev.keysym in ('Up', 'Down', 'Tab', 'Return', 'KP_Enter', 'Escape', 'Shift_L', 'Shift_R'):
            return
        self.update()

    # ---- suggestions
    def _players(self, part):
        on = list(self.app.prev_online or {})
        allc = sorted(self.app.char_names or [])
        p = part.lstrip('@').lower()
        out, seen = [], set()
        for n in on + allc:
            if n.lower().startswith(p) and n.lower() not in seen:
                seen.add(n.lower())
                out.append((n + ' ', ('%-16s %s' % (n, 'online' if n in on else ''))))
        return out

    def update(self):
        import server_admin as sa
        text = self.entry.get()
        if not text.startswith('/'):
            m = re.search(r'@(\w*)$', text)
            if m:
                self.ctx = (m.start(), 'player')
                return self.show(self._players(m.group(1)))
            return self.hide()
        words = text[1:].split(' ')
        if len(words) == 1:
            w = words[0].lower()
            self.ctx = (1, 'cmd')
            items = [(k + ' ', '/%-9s %-24s %s' % (k, sa.USAGE[k], v[1])) for k, v in sa.COMMANDS.items() if k.startswith(w)]
            items += [(k + ' ', '/%-9s %-24s %s' % (k, sa.USAGE[k], v[1])) for k, v in sa.COMMANDS.items() if len(w) >= 2 and w in k and not k.startswith(w)]
            return self.show(items)
        cmd = words[0].lower()
        if cmd not in sa.COMMANDS:
            return self.hide()
        kinds = sa.COMMANDS[cmd][0]
        idx = len(words) - 2                                  # which argument is being typed
        cur = words[-1]
        start = len(text) - len(cur)
        if cur.startswith('@') or (idx == 0 and kinds and kinds[0] == 'player'):
            self.ctx = (start, 'player')
            return self.show(self._players(cur))
        kind = kinds[min(idx, len(kinds) - 1)] if kinds else None
        if kind in ('dest', 'item', 'role'):                  # these may have spaces: everything after the player name
            head = '/' + cmd + ' ' + words[1] + ' '
            part = text[len(head):]
            start = len(head)
            if kind == 'dest':
                self.ctx = (start, 'dest')
                items = [(n + ' ', '%-16s online player' % n) for n, _ in [(x, 0) for x in (self.app.prev_online or {})]
                         if part and n.lower().startswith(part.lower())]
                items += [(n, n) for _, n in sa.match_zones(part, 12)] if part else []
                return self.show(items)
            if kind == 'role':
                import server_roles as sr
                self.ctx = (start, 'role')
                return self.show([(r, r) for r in sr.load()['roles'] if r.lower().startswith(part.lower())])
            self.ctx = (start, 'item')
            self._items_async(part)
            return None
        if kind == 'job':
            self.ctx = (start, 'job')
            return self.show([(k + ' ', '%s  %s' % (k, v)) for k, v in sa.JOB_NAMES.items()
                              if k.lower().startswith(cur.lower()) or v.lower().startswith(cur.lower())])
        return self.hide()

    def _items_async(self, part):
        key = part.strip().lower()
        if len(key) < 2:
            return self.hide()
        if key in self.item_cache:
            return self.show(self.item_cache[key])
        self.pending = key

        def work():
            import server_admin as sa
            try:
                res = [(n + ' ', '%-28s #%d' % (n, i)) for i, n in sa.match_items(key)]
            except Exception:                                # noqa: BLE001
                res = []
            self.item_cache[key] = res
            self.app.root.after(0, lambda: self.pending == key and self.show(res))
        threading.Thread(target=work, daemon=True).start()


# ======================================================================== shared bits
def _win(app, title, w=900, h=640, parent=None):
    C, _, TITLE = _C()
    if parent is not None:                                   # shown as a page inside the main window
        return parent
    d = tk.Toplevel(app.root)
    d.title(title + ' (Fan Project by Habex)')
    d.configure(bg=C['bg'])
    d.transient(app.root)
    d.geometry('%dx%d' % (app.f.s(w), app.f.s(h)))
    d.minsize(app.f.s(700), app.f.s(480))
    return d


def _check(app, parent, text, var):
    import ffxi_server_app as A
    return A.Check(parent, text=text, variable=var, font=app.f.small)


class Scrolled(tk.Frame):
    """A frame with a vertical scrollbar (mouse wheel works) for long checkbox lists."""

    def __init__(self, master, bg):
        super().__init__(master, bg=bg)
        self.cv = tk.Canvas(self, bg=bg, highlightthickness=0, bd=0)
        sb = ttk.Scrollbar(self, orient='vertical', command=self.cv.yview, style='Vertical.TScrollbar')
        self.inner = tk.Frame(self.cv, bg=bg)
        self.win = self.cv.create_window(0, 0, window=self.inner, anchor='nw')
        self.cv.configure(yscrollcommand=sb.set)
        self.cv.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        self.inner.bind('<Configure>', lambda e: self.cv.configure(scrollregion=self.cv.bbox('all')))
        self.cv.bind('<Configure>', lambda e: self.cv.itemconfigure(self.win, width=e.width))
        for w in (self.cv, self.inner):
            w.bind('<Enter>', lambda e: self.cv.bind_all('<MouseWheel>', self._wheel))
            w.bind('<Leave>', lambda e: self.cv.unbind_all('<MouseWheel>'))

    def _wheel(self, e):
        d = e.delta
        if abs(d) >= 120:
            d = d / 120
        self.cv.yview_scroll(int(-d), 'units')


# ======================================================================== Roles
class RolesWindow:
    def __init__(self, app, parent=None):
        import server_roles as sr
        C, RB, TITLE = _C()
        self.app, self.sr = app, sr
        f = app.f
        self.d = d = _win(app, 'Roles', 960, 680, parent)
        top = tk.Frame(d, bg=C['bg'])
        top.pack(fill='both', expand=True, padx=0 if parent is not None else 20, pady=0 if parent is not None else 16)
        left = tk.Frame(top, bg=C['card'])
        left.pack(side='left', fill='y')
        app.L(left, 'Roles', f.h2, bg=C['card']).pack(anchor='w', padx=14, pady=(12, 6))
        self.lb = tk.Listbox(left, width=24, bg=C['card'], fg=C['text'], selectbackground=C['sel'], highlightthickness=0, bd=0,
                             activestyle='none', font=f.body, exportselection=False)
        self.lb.pack(fill='both', expand=True, padx=8)
        self.lb.bind('<<ListboxSelect>>', lambda e: self.pick())
        RB(left, '+  New role', self.new, C['accent'], f.h3, height=f.s(38), radius=10, bg=C['card']).pack(fill='x', padx=10, pady=10)
        self.members = app.L(left, '', f.tiny, fg=C['soft'], bg=C['card'], justify='left', wraplength=f.s(200), anchor='w')
        self.members.pack(fill='x', padx=12, pady=(0, 12))

        right = tk.Frame(top, bg=C['card'])
        right.pack(side='left', fill='both', expand=True, padx=(14, 0))
        hr = tk.Frame(right, bg=C['card'])
        hr.pack(fill='x', padx=14, pady=(12, 6))
        app.L(hr, 'Name', f.h3, bg=C['card']).pack(side='left')
        self.name = app.entry(hr, width=28)
        self.name.pack(side='left', padx=10, ipady=f.s(5))
        self.allvar = tk.IntVar()
        _check(app, hr, 'Select all', self.allvar).pack(side='right')
        self.allvar.trace_add('write', lambda *a: self.set_all(self.allvar.get()))
        app.L(right, 'Tick the in-game "!" commands this role may use. Players without a role cannot use any.', f.tiny,
              fg=C['faint'], bg=C['card'], anchor='w').pack(fill='x', padx=14)
        self.sc = Scrolled(right, C['card'])
        self.sc.pack(fill='both', expand=True, padx=8, pady=8)
        self.vars = {}
        self.groupvars = []
        for g, items in sr.grouped():
            gf = tk.Frame(self.sc.inner, bg=C['card'])
            gf.pack(fill='x', pady=(8, 2), padx=6)
            gv = tk.IntVar()
            _check(app, gf, g, gv).pack(side='left')
            gf.winfo_children()[0].config(font=f.h3)
            names = [n for n, _, _ in items]
            gv.trace_add('write', lambda *a, gv=gv, names=names: self._set(names, gv.get()))
            self.groupvars.append(gv)
            grid = tk.Frame(self.sc.inner, bg=C['card'])
            grid.pack(fill='x', padx=26)
            for i, (n, perm, desc) in enumerate(items):
                v = tk.IntVar()
                self.vars[n] = v
                cb = _check(app, grid, '!%s' % n if n != 'chatrules' else 'Manage chat rules', v)
                cb.grid(row=i, column=0, sticky='w')
                app.L(grid, desc, f.tiny, fg=C['faint'], bg=C['card'], anchor='w').grid(row=i, column=1, sticky='w', padx=(10, 0))
        br = tk.Frame(right, bg=C['card'])
        br.pack(fill='x', padx=14, pady=(0, 12))
        RB(br, 'Save role', self.save, C['accent'], f.h3, height=f.s(40), width=f.s(140), bg=C['card']).pack(side='right')
        RB(br, 'Delete role', self.delete, C['grey'], f.h3, height=f.s(40), width=f.s(140), bg=C['card']).pack(side='right', padx=8)
        self.msg = app.L(br, '', f.small, fg=C['soft'], bg=C['card'])
        self.msg.pack(side='left')
        self.current = None
        self.refresh()
        if self.lb.size():
            self.lb.selection_set(0)
            self.pick()
        else:
            self.new()

    def _set(self, names, on):
        for n in names:
            self.vars[n].set(1 if on else 0)

    def set_all(self, on):
        for v in self.vars.values():
            v.set(1 if on else 0)

    def refresh(self):
        self.data = self.sr.load()
        self.lb.delete(0, 'end')
        for r in sorted(self.data['roles']):
            self.lb.insert('end', ' ' + r)

    def pick(self):
        sel = self.lb.curselection()
        if not sel:
            return
        r = self.lb.get(sel[0]).strip()
        self.current = r
        self.name.delete(0, 'end')
        self.name.insert(0, r)
        cmds = set(self.data['roles'].get(r, []))
        for n, v in self.vars.items():
            v.set(1 if n in cmds else 0)
        mem = [c for c, rr in self.data['members'].items() if rr == r]
        self.members.config(text='Members of %s:\n%s' % (r, ', '.join(mem) if mem else 'nobody yet\n(right-click a player > Promote)'))
        self.msg.config(text='')

    def new(self):
        self.current = None
        self.lb.selection_clear(0, 'end')
        self.name.delete(0, 'end')
        self.name.insert(0, 'Moderator' if 'Moderator' not in self.data['roles'] else 'New role')
        self.set_all(False)
        self.members.config(text='')
        self.name.focus_set()

    def save(self):
        C, _, TITLE = _C()
        cmds = [n for n, v in self.vars.items() if v.get()]
        name = self.name.get().strip()
        try:
            self.sr.save_role(name, cmds, self.current)
        except Exception as e:                               # noqa: BLE001
            self.msg.config(text=str(e), fg=C['red'])
            return
        self.current = name
        self.refresh()
        idx = sorted(self.data['roles']).index(name)
        self.lb.selection_set(idx)
        self.pick()
        self.msg.config(text='Saved: %d commands. It applies in the game within a few seconds.' % len(cmds), fg=C['green'])
        self.app.chat_add('admin', 'Role "%s" saved (%d commands).' % (name, len(cmds)))
        self.app.kick.set()

    def delete(self):
        _, _, TITLE = _C()
        if not self.current:
            return
        if not messagebox.askyesno(TITLE, 'Delete the role "%s"? Its members lose their commands.' % self.current, parent=self.d):
            return
        gone = self.sr.delete_role(self.current)
        self.app.chat_add('admin', 'Role "%s" deleted%s.' % (self.current, ' (removed from %s)' % ', '.join(gone) if gone else ''))
        self.refresh()
        self.new()
        self.app.kick.set()


# ======================================================================== Chat rules
class ChatRulesWindow:
    def __init__(self, app, tab=0, player=None, parent=None):
        import server_chat as ch
        C, RB, TITLE = _C()
        self.app, self.ch = app, ch
        f = app.f
        self.d = d = _win(app, 'Chat rules', 980, 700, parent)
        st = ttk.Style(d)
        st.configure('ffxi.TNotebook', background=C['bg'], borderwidth=0, bordercolor=C['bg'], lightcolor=C['bg'], darkcolor=C['bg'],
                     tabmargins=(0, 0, 0, 0))
        st.configure('ffxi.TNotebook.Tab', background=C['bg'], foreground=C['soft'], padding=(f.s(16), f.s(8)), font=f.small,
                     borderwidth=0, bordercolor=C['bg'], lightcolor=C['bg'], darkcolor=C['bg'], focuscolor=C['card'])
        st.map('ffxi.TNotebook.Tab', background=[('selected', C['card']), ('active', C['hover'])],
               foreground=[('selected', C['text'])], lightcolor=[('selected', C['card'])], bordercolor=[('selected', C['card'])])
        self.nb = ttk.Notebook(d, style='ffxi.TNotebook')
        self.nb.pack(fill='both', expand=True, padx=0 if parent is not None else 16, pady=0 if parent is not None else 14)
        self.rules = ch.load_rules()
        self._words_tab()
        self._spam_tab()
        self._sched_tab()
        self._history_tab(player)
        self._hits_tab()
        self.nb.select(tab)

    def _tab(self, title):
        C, _, _ = _C()
        fr = tk.Frame(self.nb, bg=C['card'])
        self.nb.add(fr, text=title)
        return fr

    # ---- word filter
    def _words_tab(self):
        C, RB, _ = _C()
        app, f = self.app, self.app.f
        fr = self._tab('Word filter')
        top = tk.Frame(fr, bg=C['card'])
        top.pack(fill='x', padx=14, pady=(12, 4))
        self.enabled = tk.IntVar(value=1 if self.rules.get('enabled', True) else 0)
        _check(app, top, 'Chat rules are on', self.enabled).pack(side='left')
        app.L(top, 'Lists', f.h3, bg=C['card']).pack(side='left', padx=(30, 6))
        self.list_names = [l['name'] for l in self.rules['lists']]
        self.list_var = tk.StringVar(value=self.list_names[0] if self.list_names else '')
        self.list_menu = tk.OptionMenu(top, self.list_var, *(self.list_names or ['']), command=lambda v: self.show_list())
        self.list_menu.config(bg=C['input'], fg=C['text'], activebackground=C['sel'], activeforeground='white', highlightthickness=0, bd=0, relief='flat', font=f.small, indicatoron=0, padx=12, pady=6)
        self.list_menu['menu'].config(bg=C['card2'], fg=C['text'], activebackground=C['sel'], bd=0)
        self.list_menu.pack(side='left')
        RB(top, '+ New list', self.new_list, C['grey'], f.small, height=f.s(30), width=f.s(100), radius=8, bg=C['card']).pack(side='left', padx=8)
        RB(top, 'Delete list', self.del_list, C['grey'], f.small, height=f.s(30), width=f.s(100), radius=8, bg=C['card']).pack(side='left')
        body = tk.Frame(fr, bg=C['card'])
        body.pack(fill='both', expand=True, padx=14, pady=6)
        lw = tk.Frame(body, bg=C['card'])
        lw.pack(side='left', fill='y')
        self.list_on = tk.IntVar()
        _check(app, lw, 'This list is on', self.list_on).pack(anchor='w')
        app.L(lw, 'Words (one per line)', f.small, fg=C['soft'], bg=C['card']).pack(anchor='w', pady=(6, 2))
        self.words = tk.Text(lw, width=26, height=18, bg=C['input'], fg=C['text'], insertbackground=C['text'], relief='flat',
                             font=f.mono_s, highlightthickness=1, highlightbackground=C['line'])
        self.words.pack(fill='y', expand=True)
        rw = tk.Frame(body, bg=C['card'])
        rw.pack(side='left', fill='both', expand=True, padx=(18, 0))
        app.L(rw, 'When a word is found', f.h3, bg=C['card']).pack(anchor='w')
        self.act = {}
        for k, label in self.ch.ACTIONS:
            v = tk.IntVar()
            self.act[k] = v
            _check(app, rw, label, v).pack(anchor='w', pady=1)
        row = tk.Frame(rw, bg=C['card'])
        row.pack(anchor='w', pady=(8, 0))
        app.L(row, 'Strikes before the ban', f.small, fg=C['soft'], bg=C['card']).pack(side='left')
        self.strikes = app.entry(row, width=4)
        self.strikes.pack(side='left', padx=8, ipady=3)
        app.L(rw, 'Warning text', f.small, fg=C['soft'], bg=C['card']).pack(anchor='w', pady=(10, 2))
        self.warn = app.entry(rw, width=50)
        self.warn.pack(fill='x', ipady=f.s(5))
        app.L(rw, 'Matching ignores capitals and catches repeated letters, dots or spaces between letters and numbers used '
                  'as letters (f.u.c.k, fuuuck, sh1t).', f.tiny, fg=C['faint'], bg=C['card'], justify='left',
              wraplength=f.s(460), anchor='w').pack(fill='x', pady=(12, 0))
        arow = tk.Frame(rw, bg=C['card'])
        arow.pack(fill='x', pady=(14, 0))
        app.L(arow, 'Keep chat history for', f.small, fg=C['soft'], bg=C['card']).pack(side='left')
        self.days = app.entry(arow, width=5)
        self.days.pack(side='left', padx=6, ipady=3)
        self.days.insert(0, str(self.rules.get('archive_days', 90)))
        app.L(arow, 'days', f.small, fg=C['soft'], bg=C['card']).pack(side='left')
        bot = tk.Frame(fr, bg=C['card'])
        bot.pack(fill='x', padx=14, pady=(4, 12))
        self.wmsg = app.L(bot, '', f.small, fg=C['soft'], bg=C['card'])
        self.wmsg.pack(side='left')
        RB(bot, 'Save', self.save_words, C['accent'], f.h3, height=f.s(40), width=f.s(120), bg=C['card']).pack(side='right')
        self.cur_list = None
        self.show_list()

    def _find_list(self, name):
        return next((l for l in self.rules['lists'] if l['name'] == name), None)

    def _store_list(self):
        l = self._find_list(self.cur_list) if self.cur_list else None
        if not l:
            return
        l['on'] = bool(self.list_on.get())
        l['words'] = [w.strip() for w in self.words.get('1.0', 'end').splitlines() if w.strip()]
        l['actions'] = [k for k, v in self.act.items() if v.get()]
        l['warn_text'] = self.warn.get().strip()
        try:
            l['strikes'] = max(1, int(self.strikes.get()))
        except ValueError:
            l['strikes'] = 3

    def show_list(self):
        self._store_list()
        l = self._find_list(self.list_var.get())
        self.cur_list = l['name'] if l else None
        if not l:
            return
        self.list_on.set(1 if l.get('on', True) else 0)
        self.words.delete('1.0', 'end')
        self.words.insert('1.0', '\n'.join(l.get('words', [])))
        for k, v in self.act.items():
            v.set(1 if k in l.get('actions', []) else 0)
        self.warn.delete(0, 'end')
        self.warn.insert(0, l.get('warn_text', ''))
        self.strikes.delete(0, 'end')
        self.strikes.insert(0, str(l.get('strikes', 3)))

    def _rebuild_menu(self):
        m = self.list_menu['menu']
        m.delete(0, 'end')
        for n in [l['name'] for l in self.rules['lists']]:
            m.add_command(label=n, command=lambda n=n: (self.list_var.set(n), self.show_list()))

    def new_list(self):
        name = self.app.ask('New word list', 'A name for the list (e.g. "Spoilers"):')
        if not name or self._find_list(name):
            return
        self._store_list()
        self.rules['lists'].append({'name': name, 'on': True, 'words': [], 'actions': ['replace'], 'warn_text': '', 'strikes': 3})
        self._rebuild_menu()
        self.list_var.set(name)
        self.cur_list = None
        self.show_list()

    def del_list(self):
        _, _, TITLE = _C()
        if not self.cur_list or not messagebox.askyesno(TITLE, 'Delete the list "%s"?' % self.cur_list, parent=self.d):
            return
        self.rules['lists'] = [l for l in self.rules['lists'] if l['name'] != self.cur_list]
        self.cur_list = None
        self._rebuild_menu()
        self.list_var.set(self.rules['lists'][0]['name'] if self.rules['lists'] else '')
        self.show_list()

    def save_words(self):
        C, _, _ = _C()
        self._store_list()
        self.rules['enabled'] = bool(self.enabled.get())
        try:
            self.rules['archive_days'] = max(1, int(self.days.get()))
        except ValueError:
            pass
        self._store_spam()
        self.ch.save_rules(self.rules)
        self.wmsg.config(text='Saved. It applies to the next chat line.', fg=C['green'])
        self.smsg.config(text='Saved.', fg=C['green'])
        self.app.chat_add('admin', 'Chat rules saved.')

    # ---- spam
    def _spam_tab(self):
        C, RB, _ = _C()
        app, f = self.app, self.app.f
        fr = self._tab('Spam')
        sp = self.rules['spam']
        box = tk.Frame(fr, bg=C['card'])
        box.pack(fill='x', padx=18, pady=16)
        self.sp_on = tk.IntVar(value=1 if sp.get('on') else 0)
        _check(app, box, 'Limit how fast players can talk', self.sp_on).grid(row=0, column=0, columnspan=4, sticky='w', pady=(0, 10))
        self.sp_ent = {}
        for i, (k, a, b) in enumerate([('max_messages', 'At most', 'messages'), ('per_seconds', 'in', 'seconds'),
                                       ('max_repeats', 'Same message at most', 'times in a row'), ('mute_minutes', 'Mute time', 'minutes')]):
            app.L(box, a, f.small, fg=C['soft'], bg=C['card']).grid(row=1 + i, column=0, sticky='w', pady=3)
            e = app.entry(box, width=6)
            e.grid(row=1 + i, column=1, sticky='w', padx=8, ipady=3)
            e.insert(0, str(sp.get(k, '')))
            app.L(box, b, f.small, fg=C['soft'], bg=C['card']).grid(row=1 + i, column=2, sticky='w')
            self.sp_ent[k] = e
        app.L(box, 'Then', f.h3, bg=C['card']).grid(row=6, column=0, sticky='w', pady=(14, 4))
        self.sp_act = {}
        for i, (k, label) in enumerate(self.ch.SPAM_ACTIONS):
            v = tk.IntVar(value=1 if k in sp.get('actions', []) else 0)
            self.sp_act[k] = v
            _check(app, box, label, v).grid(row=7 + i, column=0, columnspan=3, sticky='w')
        app.L(box, 'Warning text', f.small, fg=C['soft'], bg=C['card']).grid(row=13, column=0, sticky='w', pady=(12, 2))
        self.sp_warn = app.entry(box, width=50)
        self.sp_warn.grid(row=14, column=0, columnspan=4, sticky='we', ipady=f.s(5))
        self.sp_warn.insert(0, sp.get('warn_text', ''))
        bot = tk.Frame(fr, bg=C['card'])
        bot.pack(side='bottom', fill='x', padx=14, pady=12)
        self.smsg = app.L(bot, '', f.small, fg=C['soft'], bg=C['card'])
        self.smsg.pack(side='left')
        RB(bot, 'Save', self.save_words, C['accent'], f.h3, height=f.s(40), width=f.s(120), bg=C['card']).pack(side='right')

    def _store_spam(self):
        sp = self.rules['spam']
        sp['on'] = bool(self.sp_on.get())
        for k, e in self.sp_ent.items():
            try:
                sp[k] = max(1, int(e.get()))
            except ValueError:
                pass
        sp['actions'] = [k for k, v in self.sp_act.items() if v.get()]
        sp['warn_text'] = self.sp_warn.get().strip()

    # ---- scheduled messages
    def _sched_tab(self):
        C, RB, _ = _C()
        app, f = self.app, self.app.f
        fr = self._tab('Scheduled messages')
        form = tk.Frame(fr, bg=C['card'])
        form.pack(fill='x', padx=16, pady=(14, 6))
        app.L(form, 'Message', f.small, fg=C['soft'], bg=C['card']).grid(row=0, column=0, sticky='w')
        self.s_text = app.entry(form, width=60)
        self.s_text.grid(row=0, column=1, columnspan=5, sticky='we', ipady=f.s(5), padx=8)
        app.L(form, 'First time', f.small, fg=C['soft'], bg=C['card']).grid(row=1, column=0, sticky='w', pady=8)
        self.s_when = app.entry(form, width=18)
        self.s_when.grid(row=1, column=1, sticky='w', padx=8, ipady=3)
        self.s_when.insert(0, time.strftime('%Y-%m-%d %H:%M', time.localtime(time.time() + 600)))
        app.L(form, 'Repeat every', f.small, fg=C['soft'], bg=C['card']).grid(row=1, column=2, sticky='w')
        self.s_rep = app.entry(form, width=6)
        self.s_rep.grid(row=1, column=3, sticky='w', padx=6, ipady=3)
        self.s_rep.insert(0, '0')
        self.s_unit = tk.StringVar(value='minutes')
        om = tk.OptionMenu(form, self.s_unit, 'minutes', 'hours')
        om.config(bg=C['input'], fg=C['text'], activebackground=C['sel'], highlightthickness=0, bd=0, relief='flat', font=f.small, indicatoron=0, padx=10, pady=4)
        om.grid(row=1, column=4, sticky='w')
        app.L(form, '(0 = only once)', f.tiny, fg=C['faint'], bg=C['card']).grid(row=1, column=5, sticky='w', padx=6)
        form.grid_columnconfigure(1, weight=1)
        br = tk.Frame(fr, bg=C['card'])
        br.pack(fill='x', padx=16)
        self.s_edit = None
        RB(br, 'Add / save', self.s_save, C['accent'], f.small, height=f.s(34), width=f.s(110), radius=9, bg=C['card']).pack(side='left')
        RB(br, 'Delete', self.s_delete, C['grey'], f.small, height=f.s(34), width=f.s(90), radius=9, bg=C['card']).pack(side='left', padx=8)
        RB(br, 'New', self.s_new, C['grey'], f.small, height=f.s(34), width=f.s(80), radius=9, bg=C['card']).pack(side='left')
        self.s_msg = app.L(br, '', f.small, fg=C['soft'], bg=C['card'])
        self.s_msg.pack(side='left', padx=12)
        tf = tk.Frame(fr, bg=C['card'])
        tf.pack(fill='both', expand=True, padx=16, pady=12)
        self.s_tree = ttk.Treeview(tf, columns=('next', 'repeat', 'text'), show='headings', height=8)
        for c, t, w in (('next', 'Next', 150), ('repeat', 'Repeats', 110), ('text', 'Message', 500)):
            self.s_tree.heading(c, text=t, anchor='w')
            self.s_tree.column(c, width=f.s(w), anchor='w', stretch=(c == 'text'))
        self.s_tree.pack(fill='both', expand=True)
        self.s_tree.bind('<<TreeviewSelect>>', lambda e: self.s_pick())
        self.s_fill()

    def s_fill(self):
        t = self.s_tree
        t.delete(*t.get_children())
        for it in sorted(self.ch.load_schedule(), key=lambda i: i.get('next') or 0):
            rep = float(it.get('repeat_minutes') or 0)
            rtxt = 'once' if not rep else ('every %g h' % (rep / 60) if rep >= 60 and rep % 60 == 0 else 'every %g min' % rep)
            nxt = time.strftime('%Y-%m-%d %H:%M', time.localtime(it['next'])) if it.get('on', True) else 'sent'
            t.insert('', 'end', iid=it['id'], values=(nxt, rtxt, it.get('text', '')))

    def s_pick(self):
        sel = self.s_tree.selection()
        if not sel:
            return
        it = next((i for i in self.ch.load_schedule() if i['id'] == sel[0]), None)
        if not it:
            return
        self.s_edit = it['id']
        self.s_text.delete(0, 'end')
        self.s_text.insert(0, it.get('text', ''))
        self.s_when.delete(0, 'end')
        self.s_when.insert(0, time.strftime('%Y-%m-%d %H:%M', time.localtime(it.get('next') or time.time())))
        rep = float(it.get('repeat_minutes') or 0)
        if rep and rep % 60 == 0:
            self.s_rep.delete(0, 'end'); self.s_rep.insert(0, '%g' % (rep / 60)); self.s_unit.set('hours')
        else:
            self.s_rep.delete(0, 'end'); self.s_rep.insert(0, '%g' % rep); self.s_unit.set('minutes')

    def s_new(self):
        self.s_edit = None
        self.s_tree.selection_set(())
        self.s_text.delete(0, 'end')

    def s_save(self):
        C, _, _ = _C()
        try:
            when = time.mktime(time.strptime(self.s_when.get().strip(), '%Y-%m-%d %H:%M'))
        except ValueError:
            self.s_msg.config(text='Type the time like 2026-10-10 20:30', fg=C['red'])
            return
        try:
            rep = float(self.s_rep.get() or 0) * (60 if self.s_unit.get() == 'hours' else 1)
            if when < time.time() and rep > 0:
                while when < time.time():
                    when += rep * 60
            self.s_edit = self.ch.put_scheduled(self.s_text.get(), when, rep, self.s_edit)
        except Exception as e:                               # noqa: BLE001
            self.s_msg.config(text=str(e), fg=C['red'])
            return
        self.s_msg.config(text='Saved. The server sends it on time while it is on.', fg=C['green'])
        self.s_fill()

    def s_delete(self):
        sel = self.s_tree.selection()
        if sel:
            self.ch.delete_scheduled(sel[0])
            self.s_new()
            self.s_fill()

    # ---- chat history
    def _history_tab(self, player):
        C, RB, _ = _C()
        app, f = self.app, self.app.f
        fr = self._tab('Chat history')
        bar = tk.Frame(fr, bg=C['card'])
        bar.pack(fill='x', padx=14, pady=(12, 6))
        app.L(bar, 'Player', f.small, fg=C['soft'], bg=C['card']).pack(side='left')
        self.h_player = app.entry(bar, width=16)
        self.h_player.pack(side='left', padx=6, ipady=3)
        if player:
            self.h_player.insert(0, player)
        app.L(bar, 'Text', f.small, fg=C['soft'], bg=C['card']).pack(side='left', padx=(10, 0))
        self.h_text = app.entry(bar, width=22)
        self.h_text.pack(side='left', padx=6, ipady=3)
        RB(bar, 'Search', self.h_fill, C['accent'], f.small, height=f.s(30), width=f.s(80), radius=8, bg=C['card']).pack(side='left', padx=4)
        RB(bar, 'Export to a file', self.h_export, C['grey'], f.small, height=f.s(30), width=f.s(130), radius=8, bg=C['card']).pack(side='right')
        for e in (self.h_player, self.h_text):
            e.bind('<Return>', lambda ev: self.h_fill())
        tf = tk.Frame(fr, bg=C['card'])
        tf.pack(fill='both', expand=True, padx=14, pady=(0, 12))
        self.h_tree = ttk.Treeview(tf, columns=('time', 'player', 'chan', 'zone', 'text'), show='headings')
        for c, t, w in (('time', 'Time', 140), ('player', 'Player', 110), ('chan', 'Channel', 80), ('zone', 'Zone', 150), ('text', 'Message', 420)):
            self.h_tree.heading(c, text=t, anchor='w')
            self.h_tree.column(c, width=f.s(w), anchor='w', stretch=(c == 'text'))
        sb = ttk.Scrollbar(tf, orient='vertical', command=self.h_tree.yview, style='Vertical.TScrollbar')
        self.h_tree.configure(yscrollcommand=sb.set)
        self.h_tree.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        self.h_fill()

    def h_fill(self):
        t = self.h_tree
        t.delete(*t.get_children())
        zones = self.ch.zone_names()
        for ts, p, chn, z, tg, tx in self.ch.history(self.h_player.get().strip() or None, self.h_text.get().strip() or None, 2000):
            t.insert('', 'end', values=(time.strftime('%m-%d %H:%M:%S', time.localtime(ts)), p, chn, zones.get(z, '') if z else '',
                                        ('to %s: ' % tg if tg else '') + tx))
        kids = t.get_children()
        if kids:
            t.see(kids[-1])

    def h_export(self):
        _, _, TITLE = _C()
        p = self.h_player.get().strip() or None
        path = filedialog.asksaveasfilename(parent=self.d, title='Save the chat history', defaultextension='.txt',
                                            initialfile='chat history%s.txt' % (' ' + p if p else ''),
                                            filetypes=[('Text file', '*.txt')])
        if path:
            n = self.ch.export_history(path, p, self.h_text.get().strip() or None)
            messagebox.showinfo(TITLE, 'Saved %d lines to:\n%s' % (n, path), parent=self.d)

    # ---- filter log
    def _hits_tab(self):
        C, RB, _ = _C()
        app, f = self.app, self.app.f
        fr = self._tab('Filter log')
        bar = tk.Frame(fr, bg=C['card'])
        bar.pack(fill='x', padx=14, pady=(12, 6))
        app.L(bar, 'Search', f.small, fg=C['soft'], bg=C['card']).pack(side='left')
        self.k_text = app.entry(bar, width=24)
        self.k_text.pack(side='left', padx=6, ipady=3)
        self.k_text.bind('<Return>', lambda ev: self.k_fill())
        RB(bar, 'Search', self.k_fill, C['accent'], f.small, height=f.s(30), width=f.s(80), radius=8, bg=C['card']).pack(side='left', padx=4)
        tf = tk.Frame(fr, bg=C['card'])
        tf.pack(fill='both', expand=True, padx=14, pady=(0, 12))
        self.k_tree = ttk.Treeview(tf, columns=('time', 'player', 'rule', 'text', 'done'), show='headings')
        for c, t, w in (('time', 'Time', 140), ('player', 'Player', 110), ('rule', 'Rule', 170), ('text', 'They wrote', 300), ('done', 'What happened', 240)):
            self.k_tree.heading(c, text=t, anchor='w')
            self.k_tree.column(c, width=f.s(w), anchor='w', stretch=(c in ('text', 'done')))
        sb = ttk.Scrollbar(tf, orient='vertical', command=self.k_tree.yview, style='Vertical.TScrollbar')
        self.k_tree.configure(yscrollcommand=sb.set)
        self.k_tree.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        self.k_fill()

    def k_fill(self):
        t = self.k_tree
        t.delete(*t.get_children())
        for i, ts, p, chn, rule, tx, done in self.ch.hits(self.k_text.get().strip() or None, 0, 2000):
            t.insert('', 'end', values=(time.strftime('%m-%d %H:%M:%S', time.localtime(ts)), p, rule, tx, done))
        kids = t.get_children()
        if kids:
            t.see(kids[-1])
