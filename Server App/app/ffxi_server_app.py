#!/usr/bin/env python3
"""FFXI 2016 Server - the window that runs the server. Fan Project by Habex.

Python 3 + Tk (standard library only). Mac, Windows and Linux. Dark look only.
Left: navigation (Server, Profiles, Internet, Roles, Chat rules, Game disc).
Server page: status + Start / Stop, the address players type, who is online, the world chat.
The work is done by Server/server_control.py (start/stop, profiles), server_admin.py (players, chat, commands),
server_net.py (addresses, ports), server_roles.py (roles) and server_chat.py (chat rules).
"""
import importlib.util, os, queue, subprocess, sys, threading, time, traceback
import tkinter as tk
import tkinter.font as tkfont
from tkinter import filedialog, messagebox, ttk

APP_DIR = os.path.dirname(os.path.abspath(__file__))
RELEASE = os.environ.get('FFXI_RELEASE_DIR') or os.path.dirname(os.path.dirname(APP_DIR))
SERVER_DIR = os.path.join(RELEASE, 'Server')
DISC_DIR = os.path.join(RELEASE, 'Disc')
sys.path.insert(0, SERVER_DIR)
sys.path.insert(0, APP_DIR)
try:
    import server_control as sc
    import server_admin as sa
    import server_net as sn
    import server_roles as sr
    import server_chat as sch
except Exception:                                            # noqa: BLE001
    sc = sa = sn = sr = sch = None
    SC_ERROR = traceback.format_exc()

TITLE = 'FFXI 2016 Server (Fan Project by Habex)'
WINDOWS = os.name == 'nt'
MAC = sys.platform == 'darwin'

# ---------------------------------------------------------------- look (dark only, one accent colour)
C = dict(
    bg='#0e1116', nav='#0a0d11', card='#151a21', card2='#1b212a', line='#232a34', input='#1d242d', hover='#1c232c',
    text='#e8ecf1', soft='#9aa5b1', faint='#647080',
    accent='#4c8dff', accent_dk='#3a73d9',
    green='#34c47c', green_dk='#1f8a52', green_bg='#13281e',
    red='#ef5b52', red_dk='#a83a33', red_bg='#2c1717',
    amber='#e9ac45', amber_bg='#2e2513', grey='#2a323d', sel='#24406e', zebra='#181e26',
    blue='#4c8dff', purple='#4c8dff')
CHAT_COLORS = {'Say': '#e8ecf1', 'Shout': '#ff9f5a', 'Yell': '#ffcf5a', 'Tell': '#c792ea', 'Party': '#62c9ff', 'LS': '#8ddf8d',
               'Server': '#4c8dff', 'info': '#9aa5b1', 'error': '#ff7b72', 'admin': '#4c8dff', 'event': '#647080'}


def pick_font(cands):
    try:
        fams = set(tkfont.families())
    except tk.TclError:
        fams = set()
    for c in cands:
        if c in fams:
            return c
    return 'TkDefaultFont'


class Fonts:
    def __init__(self):
        ui = pick_font(['SF Pro Text', 'Helvetica Neue', 'Segoe UI', 'Inter', 'Noto Sans', 'Ubuntu', 'Cantarell', 'DejaVu Sans', 'Helvetica', 'Arial'])
        disp = pick_font(['SF Pro Display', 'Helvetica Neue', 'Segoe UI Semibold', 'Segoe UI', 'Inter', 'Noto Sans', 'Ubuntu', 'DejaVu Sans', 'Arial'])
        mono = pick_font(['SF Mono', 'Menlo', 'Cascadia Mono', 'Consolas', 'JetBrains Mono', 'DejaVu Sans Mono', 'Liberation Mono', 'Courier New'])
        k = 1.0 if MAC else 0.82                         # Windows/Linux draw the same point size bigger
        s = lambda n: max(8, int(round(n * k)))
        self.title = (disp, s(22), 'bold')
        self.h1 = (disp, s(20), 'bold')
        self.h2 = (ui, s(15), 'bold')
        self.h3 = (ui, s(13), 'bold')
        self.body = (ui, s(13))
        self.small = (ui, s(12))
        self.tiny = (ui, s(11))
        self.nav = (ui, s(14))
        self.nav_b = (ui, s(14), 'bold')
        self.btn = (ui, s(14), 'bold')
        self.bigbtn = (disp, s(17), 'bold')
        self.status = (disp, s(26), 'bold')
        self.mono = (mono, s(20), 'bold')
        self.mono_s = (mono, s(12))
        self.ui = ui
        self.s = s


def shade(c, k):
    r, g, b = int(c[1:3], 16), int(c[3:5], 16), int(c[5:7], 16)
    return '#%02x%02x%02x' % tuple(max(0, min(255, int(v * k))) for v in (r, g, b))


def rounded(cv, x1, y1, x2, y2, r, **kw):
    r = max(1, min(r, (x2 - x1) / 2, (y2 - y1) / 2))
    pts = [x1 + r, y1, x2 - r, y1, x2, y1, x2, y1 + r, x2, y2 - r, x2, y2, x2 - r, y2, x1 + r, y2, x1, y2, x1, y2 - r, x1, y1 + r, x1, y1]
    return cv.create_polygon(pts, smooth=True, **kw)


class RoundButton(tk.Canvas):
    """A rounded button with a hover state that looks the same on every system."""

    def __init__(self, master, text, command, color, font, height=44, width=None, fg='white', radius=12, bg=None):
        super().__init__(master, height=height, width=width or 10, bg=bg or master['bg'], highlightthickness=0, bd=0, cursor='hand2')
        self.text, self.command, self.color, self.font, self.fg, self.radius = text, command, color, font, fg, radius
        self.enabled, self.hover = True, False
        self.bind('<Configure>', lambda e: self.draw())
        self.bind('<Enter>', lambda e: self._hov(True))
        self.bind('<Leave>', lambda e: self._hov(False))
        self.bind('<ButtonRelease-1>', lambda e: self.enabled and self.command())

    def _hov(self, on):
        self.hover = on
        self.draw()

    def set_enabled(self, on):
        if on != self.enabled:
            self.enabled = on
            self.config(cursor='hand2' if on else 'arrow')
            self.draw()

    def set_text(self, text):
        self.text = text
        self.draw()

    def draw(self):
        self.delete('all')
        w, h = self.winfo_width(), self.winfo_height()
        if w < 4:
            return
        col = self.color if self.enabled else C['grey']
        if self.enabled and self.hover:
            col = shade(col, 1.18)
        rounded(self, 1, 1, w - 1, h - 1, self.radius, fill=col, outline='')
        self.create_text(w / 2, h / 2, text=self.text, fill=self.fg if self.enabled else '#77818d', font=self.font)


class Segmented(tk.Canvas):
    """Two-choice switch (Local / Port forwarding)."""

    def __init__(self, master, choices, command, font, height=36):
        super().__init__(master, height=height, width=10, bg=master['bg'], highlightthickness=0, bd=0, cursor='hand2')
        self.choices, self.command, self.font, self.value = choices, command, font, choices[0][0]
        self.bind('<Configure>', lambda e: self.draw())
        self.bind('<ButtonRelease-1>', self._click)

    def set(self, v):
        self.value = v
        self.draw()

    def _click(self, e):
        i = min(len(self.choices) - 1, int(e.x / max(1, self.winfo_width()) * len(self.choices)))
        v = self.choices[i][0]
        if v != self.value:
            self.command(v)

    def draw(self):
        self.delete('all')
        w, h = self.winfo_width(), self.winfo_height()
        if w < 10:
            return
        rounded(self, 1, 1, w - 1, h - 1, h / 2, fill=C['card2'], outline='')
        n = len(self.choices)
        for i, (v, label) in enumerate(self.choices):
            x1, x2 = 1 + i * (w - 2) / n, 1 + (i + 1) * (w - 2) / n
            if v == self.value:
                rounded(self, x1 + 3, 4, x2 - 3, h - 4, (h - 8) / 2, fill=C['accent'], outline='')
            self.create_text((x1 + x2) / 2, h / 2, text=label, font=self.font, fill='white' if v == self.value else C['soft'])


class Pill(tk.Canvas):
    def __init__(self, master, fonts):
        super().__init__(master, height=34, width=200, bg=master['bg'], highlightthickness=0, bd=0)
        self.f = fonts
        self.set('off', 'Off')

    def set(self, mode, text):
        col = {'on': (C['green_bg'], C['green']), 'off': (C['red_bg'], C['red']), 'busy': (C['amber_bg'], C['amber'])}[mode]
        self.delete('all')
        fnt = tkfont.Font(font=self.f.h3)
        w = fnt.measure(text) + 46
        self.config(width=w)
        rounded(self, 1, 1, w - 1, 33, 16, fill=col[0], outline='')
        self.create_oval(14, 12, 24, 22, fill=col[1], outline='')
        self.create_text(32, 17, text=text, anchor='w', fill=col[1], font=self.f.h3)


class Panel(tk.Frame):
    """A soft panel: no border, just a slightly lighter background and roomy padding."""

    def __init__(self, master, title=None, fonts=None, pad=20):
        super().__init__(master, bg=C['card'], highlightthickness=0, bd=0)
        if title:
            head = tk.Frame(self, bg=C['card'])
            head.pack(fill='x', padx=pad, pady=(pad - 4, 8))
            self.title = tk.Label(head, text=title, font=fonts.h2, bg=C['card'], fg=C['text'], anchor='w')
            self.title.pack(side='left')
            self.head = head
        self.body = tk.Frame(self, bg=C['card'])
        self.body.pack(fill='both', expand=True, padx=pad, pady=(0 if title else pad, pad))


# ---------------------------------------------------------------- the window
class App:
    PAGES = [('server', 'Server'), ('profiles', 'Profiles'), ('internet', 'Internet'), ('roles', 'Roles'),
             ('chat', 'Chat rules'), ('disc', 'Game disc')]

    def __init__(self, root):
        self.root = root
        self.f = Fonts()
        self.q = queue.Queue()
        self.busy = False
        self.state = None
        self.last_ip = None
        self.prev_online = None
        self.setup_ok = True
        self.char_names = []
        self.members = {}
        self.hit_id = None
        self.addr = {'lan': '', 'net': ''}
        self.page = None
        self.pages = {}
        self.kick = threading.Event()
        root.title(TITLE)
        root.configure(bg=C['bg'])
        root.minsize(1080, 680)
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        w, h = min(1380, sw - 60), min(880, sh - 90)
        root.geometry('%dx%d+%d+%d' % (w, h, max(0, (sw - w) // 2), max(0, (sh - h) // 3)))
        self._style()
        self._icon()
        self.mode = sn.get_mode() if sn else 'local'
        self.checking = False
        self.last_check = 0
        self._build()
        root.protocol('WM_DELETE_WINDOW', self.on_close)
        if sc is None:
            messagebox.showerror(TITLE, 'The server files were not found.\n\nKeep the "Server App" folder next to the "Server" '
                                        'folder (both inside "FFXI 2016 Release").')
            return
        self.chat = sa.ChatReader()
        self._check_write_access()
        threading.Thread(target=self._collector, daemon=True).start()
        self.root.after(150, self.poll)
        self.root.after(300, self._take_focus)
        self.root.after(5000, self.watch_map)

    # -------------------------------------------------------------- style
    def _style(self):
        st = ttk.Style(self.root)
        try:
            st.theme_use('clam')
        except tk.TclError:
            pass
        f = self.f
        st.configure('Treeview', background=C['card'], fieldbackground=C['card'], foreground=C['text'], borderwidth=0,
                     rowheight=f.s(34), font=f.body)
        st.map('Treeview', background=[('selected', C['sel'])], foreground=[('selected', 'white')])
        st.configure('Treeview.Heading', background=C['card'], foreground=C['faint'], relief='flat', font=f.tiny, borderwidth=0,
                     padding=(6, 6))
        st.map('Treeview.Heading', background=[('active', C['card'])])
        st.layout('Treeview', [('Treeview.treearea', {'sticky': 'nswe'})])
        st.configure('Vertical.TScrollbar', background=C['card2'], troughcolor=C['card'], bordercolor=C['card'], arrowcolor=C['faint'],
                     lightcolor=C['card2'], darkcolor=C['card2'], gripcount=0, arrowsize=f.s(11))
        st.map('Vertical.TScrollbar', background=[('active', C['line'])])
        st.configure('ffxi.Horizontal.TProgressbar', troughcolor=C['card2'], background=C['accent'], bordercolor=C['card2'],
                     lightcolor=C['accent'], darkcolor=C['accent'], thickness=f.s(14))

    def _icon(self):
        """Window icon: the game art (app/icon.png; Windows also app/icon.ico for the title bar)."""
        try:
            png = os.path.join(APP_DIR, 'icon.png')
            if os.path.exists(png):
                img = tk.PhotoImage(file=png)
                f = max(1, img.width() // 256)
                if f > 1:
                    img = img.subsample(f, f)
            else:
                img = tk.PhotoImage(width=32, height=32)
                img.put(C['accent'], to=(4, 4, 28, 28))
            self.root.iconphoto(True, img)
            self._img = img
            ico = os.path.join(APP_DIR, 'icon.ico')
            if WINDOWS and os.path.exists(ico):
                self.root.iconbitmap(default=ico)
        except tk.TclError:
            pass

    def L(self, parent, text='', font=None, fg=None, bg=None, **kw):
        return tk.Label(parent, text=text, font=font or self.f.body, fg=fg or C['text'], bg=bg or parent['bg'], **kw)

    def entry(self, parent, show='', width=22):
        return tk.Entry(parent, font=self.f.body, width=width, show=show, bg=C['input'], fg=C['text'], insertbackground=C['text'],
                        relief='flat', bd=0, highlightthickness=1, highlightbackground=C['input'], highlightcolor=C['accent'],
                        disabledbackground=C['card2'])

    def _scroll(self, parent, widget):
        sb = ttk.Scrollbar(parent, orient='vertical', command=widget.yview, style='Vertical.TScrollbar')
        widget.configure(yscrollcommand=sb.set)
        return sb

    # -------------------------------------------------------------- layout
    def _build(self):
        f, r = self.f, self.root
        nav = tk.Frame(r, bg=C['nav'], width=f.s(210))
        nav.pack(side='left', fill='y')
        nav.pack_propagate(False)
        self.L(nav, 'FFXI 2016', f.title, bg=C['nav']).pack(anchor='w', padx=22, pady=(22, 0))
        self.L(nav, 'Server', f.title, bg=C['nav'], fg=C['soft']).pack(anchor='w', padx=22)
        self.L(nav, 'Fan Project by Habex', f.small, fg=C['accent'], bg=C['nav']).pack(anchor='w', padx=22, pady=(6, 26))
        self.nav_items = {}
        for key, label in self.PAGES:
            it = tk.Frame(nav, bg=C['nav'], cursor='hand2')
            it.pack(fill='x', padx=12, pady=1)
            bar = tk.Frame(it, bg=C['nav'], width=3)
            bar.pack(side='left', fill='y')
            lab = self.L(it, label, f.nav, fg=C['soft'], bg=C['nav'], anchor='w', padx=14, pady=f.s(9))
            lab.pack(side='left', fill='x', expand=True)
            for w in (it, lab):
                w.bind('<Button-1>', lambda e, k=key: self.show_page(k))
                w.bind('<Enter>', lambda e, k=key: self._nav_hover(k, True))
                w.bind('<Leave>', lambda e, k=key: self._nav_hover(k, False))
            self.nav_items[key] = (it, bar, lab)
        self.nav_pill = Pill(nav, f)
        self.nav_pill.pack(side='bottom', anchor='w', padx=22, pady=22)

        self.content = tk.Frame(r, bg=C['bg'])
        self.content.pack(side='left', fill='both', expand=True)
        self._build_server()
        self._build_profiles()
        self._build_internet()
        self._build_disc()
        self.show_page('server')

    def _nav_hover(self, key, on):
        it, bar, lab = self.nav_items[key]
        if key != self.page:
            for w in (it, lab):
                w.config(bg=C['hover'] if on else C['nav'])

    def show_page(self, key):
        if key == 'roles' and 'roles' not in self.pages:
            self.pages['roles'] = self._page_frame('Roles', 'Who may use which in-game "!" commands. Right-click a player to promote them.')
            import ffxi_app_extra as X
            self.roles_page = X.RolesWindow(self, parent=self.pages['roles'].body)
        if key == 'chat' and 'chat' not in self.pages:
            self.pages['chat'] = self._page_frame('Chat rules', 'Word filter, spam limit, scheduled messages and the chat history.')
            import ffxi_app_extra as X
            self.chat_page = X.ChatRulesWindow(self, parent=self.pages['chat'].body)
        for k, fr in self.pages.items():
            if k != key:
                fr.pack_forget()
        self.pages[key].pack(fill='both', expand=True)
        self.page = key
        for k, (it, bar, lab) in self.nav_items.items():
            on = k == key
            for w in (it, lab):
                w.config(bg=C['card'] if on else C['nav'])
            bar.config(bg=C['accent'] if on else C['nav'])
            lab.config(fg=C['text'] if on else C['soft'], font=self.f.nav_b if on else self.f.nav)

    def _page_frame(self, title, sub=None):
        fr = tk.Frame(self.content, bg=C['bg'])
        head = tk.Frame(fr, bg=C['bg'])
        head.pack(fill='x', padx=28, pady=(24, 14))
        self.L(head, title, self.f.h1).pack(anchor='w')
        if sub:
            self.L(head, sub, self.f.small, fg=C['soft']).pack(anchor='w', pady=(4, 0))
        fr.head = head
        fr.body = tk.Frame(fr, bg=C['bg'])
        fr.body.pack(fill='both', expand=True, padx=28, pady=(0, 24))
        return fr

    # ---- Server page
    def _build_server(self):
        f = self.f
        page = tk.Frame(self.content, bg=C['bg'])
        self.pages['server'] = page
        hero = Panel(page, None, f, pad=24)
        hero.pack(fill='x', padx=28, pady=(24, 14))
        hb = hero.body
        left = tk.Frame(hb, bg=C['card'])
        left.pack(side='left', fill='both', expand=True)
        srow = tk.Frame(left, bg=C['card'])
        srow.pack(anchor='w')
        self.status_dot = tk.Canvas(srow, width=f.s(18), height=f.s(18), bg=C['card'], highlightthickness=0)
        self.status_dot.pack(side='left', padx=(0, 10))
        self.status_text = self.L(srow, 'Server is off', f.status, bg=C['card'])
        self.status_text.pack(side='left')
        self.step = self.L(left, '', f.body, fg=C['soft'], bg=C['card'], anchor='w', justify='left')
        self.step.pack(fill='x', pady=(6, 0))
        self.parts = self.L(left, '', f.tiny, fg=C['faint'], bg=C['card'], anchor='w', justify='left')
        self.parts.pack(fill='x', pady=(6, 0))
        wrow = tk.Frame(left, bg=C['card'])
        wrow.pack(fill='x', pady=(12, 0))
        self.work_icon = self.L(wrow, '●', f.h3, fg=C['faint'], bg=C['card'])
        self.work_icon.pack(side='left', anchor='n')
        wcol = tk.Frame(wrow, bg=C['card'])
        wcol.pack(side='left', fill='x', expand=True, padx=(8, 0))
        self.work_title = self.L(wcol, 'Is it working?', f.h3, bg=C['card'], anchor='w')
        self.work_title.pack(fill='x')
        self.work_text = self.L(wcol, '', f.small, fg=C['soft'], bg=C['card'], anchor='w', justify='left')
        self.work_text.pack(fill='x')
        chk = self.L(wrow, 'check now', f.tiny, fg=C['accent'], bg=C['card'], cursor='hand2')
        chk.pack(side='right', anchor='n')
        chk.bind('<Button-1>', lambda e: self.check_now())
        right = tk.Frame(hb, bg=C['card'])
        right.pack(side='right', padx=(24, 0))
        self.mode_switch = Segmented(right, [('local', 'Local'), ('internet', 'Port forwarding')], self.set_mode, f.small, height=f.s(34))
        self.mode_switch.pack(fill='x', pady=(0, 12))
        self.mode_switch.set(self.mode)
        brow = tk.Frame(right, bg=C['card'])
        brow.pack()
        self.start_btn = RoundButton(brow, 'Start Server', self.do_start, C['green_dk'], f.bigbtn, height=f.s(58), width=f.s(190), radius=14)
        self.start_btn.pack(side='left', padx=(0, 10))
        self.stop_btn = RoundButton(brow, 'Stop', self.do_stop, C['grey'], f.bigbtn, height=f.s(58), width=f.s(110), radius=14)
        self.stop_btn.pack(side='left')

        addr = Panel(page, None, f, pad=22)
        addr.pack(fill='x', padx=28, pady=(0, 14))
        ab = addr.body
        self.L(ab, 'PLAYERS SIGN IN WITH', f.tiny, fg=C['faint'], bg=C['card']).grid(row=0, column=0, columnspan=4, sticky='w')
        self.L(ab, 'ServerIP', f.small, fg=C['soft'], bg=C['card']).grid(row=1, column=0, sticky='w', pady=(6, 0))
        self.ip_val = self.L(ab, '...', f.mono, bg=C['card'])
        self.ip_val.grid(row=1, column=1, sticky='w', padx=(12, 14), pady=(6, 0))
        self.copy_btn = RoundButton(ab, 'Copy', self.copy_ip, C['grey'], f.tiny, height=f.s(28), width=f.s(60), radius=8, bg=C['card'])
        self.copy_btn.grid(row=1, column=2, sticky='w', pady=(6, 0))
        self.change_btn = self.L(ab, 'change', f.tiny, fg=C['accent'], bg=C['card'], cursor='hand2')
        self.change_btn.grid(row=1, column=3, sticky='w', padx=10, pady=(6, 0))
        self.change_btn.bind('<Button-1>', lambda e: self.change_public())
        self.L(ab, 'ServerPort', f.small, fg=C['soft'], bg=C['card']).grid(row=1, column=4, sticky='w', padx=(40, 0), pady=(6, 0))
        self.L(ab, str(sc.SERVER_PORT_FOR_PLAYERS) if sc else '54001', f.mono, bg=C['card']).grid(row=1, column=5, sticky='w', padx=12, pady=(6, 0))
        self.ports_hint = self.L(ab, '', f.tiny, fg=C['soft'], bg=C['card'], cursor='hand2')
        self.ports_hint.grid(row=2, column=0, columnspan=6, sticky='w', pady=(8, 0))
        self.ports_hint.bind('<Button-1>', lambda e: self.show_page('internet'))
        self.setup_card = tk.Frame(ab, bg=C['amber_bg'])
        self.setup_list = self.L(self.setup_card, '', f.small, bg=C['amber_bg'], anchor='w', justify='left')
        self.setup_list.pack(side='left', fill='x', expand=True, padx=14, pady=10)
        RoundButton(self.setup_card, 'Check again', lambda: self.kick.set(), C['grey'], f.small, height=f.s(32), width=f.s(110),
                    radius=9, bg=C['amber_bg']).pack(side='right', padx=(4, 12))
        RoundButton(self.setup_card, 'Run Setup', self.do_setup, C['amber'], f.small, height=f.s(32), width=f.s(110), radius=9,
                    fg='#1a1300', bg=C['amber_bg']).pack(side='right')

        low = tk.Frame(page, bg=C['bg'])
        low.pack(fill='both', expand=True, padx=28, pady=(0, 24))
        low.grid_columnconfigure(0, weight=4, uniform='l')
        low.grid_columnconfigure(1, weight=5, uniform='l')
        low.grid_rowconfigure(0, weight=1)
        onl = Panel(low, 'Online now', f)
        onl.grid(row=0, column=0, sticky='nsew', padx=(0, 14))
        self.online_count = self.L(onl.head, '', f.small, fg=C['soft'], bg=C['card'])
        self.online_count.pack(side='right')
        of = tk.Frame(onl.body, bg=C['card'])
        of.pack(fill='both', expand=True)
        cols = (('name', 'Character', 120), ('zone', 'Zone', 160), ('job', 'Job', 80), ('role', 'Role', 90))
        self.online = ttk.Treeview(of, columns=[c[0] for c in cols], show='headings', selectmode='browse', height=4)
        for col, txt, w in cols:
            self.online.heading(col, text=txt.upper(), anchor='w')
            self.online.column(col, width=f.s(w), anchor='w', stretch=True)
        self.online.tag_configure('odd', background=C['zebra'])
        self.online.tag_configure('afk', foreground=C['amber'])
        osb = self._scroll(of, self.online)
        self.online.pack(side='left', fill='both', expand=True)
        osb.pack(side='right', fill='y')
        for ev in (('<Button-2>', '<Button-3>', '<Control-Button-1>') if MAC else ('<Button-3>',)):
            self.online.bind(ev, self.online_menu)

        chat = Panel(low, 'World chat', f)
        chat.grid(row=0, column=1, sticky='nsew')
        self.link_state = self.L(chat.head, '', f.small, fg=C['soft'], bg=C['card'])
        self.link_state.pack(side='right')
        self.L(chat.body, 'Enter sends to everyone online.  Type / for commands, @ for a player.', f.tiny, fg=C['faint'],
               bg=C['card'], anchor='w').pack(side='bottom', fill='x', pady=(6, 0))
        send = tk.Frame(chat.body, bg=C['card'])
        send.pack(side='bottom', fill='x', pady=(10, 0))
        self.chat_entry = self.entry(send, width=30)
        self.chat_entry.pack(side='left', fill='x', expand=True, ipady=f.s(8))
        self.chat_entry.bind('<Return>', self._enter)
        self.chat_entry.bind('<KP_Enter>', self._enter)
        self.chat_entry.bind('<Button-1>', lambda e: self.chat_entry.focus_force(), add='+')
        self.send_btn = RoundButton(send, 'Send', self.send_chat, C['accent'], f.h3, height=f.s(40), width=f.s(84), radius=10, bg=C['card'])
        self.send_btn.pack(side='left', padx=(8, 0))
        cf = tk.Frame(chat.body, bg=C['card2'])
        cf.pack(fill='both', expand=True)
        self.chat_box = tk.Text(cf, bg=C['card2'], fg=C['text'], font=f.mono_s, wrap='word', relief='flat', bd=0, padx=12, pady=10,
                                height=6, width=40, highlightthickness=0, state='disabled', cursor='arrow', spacing1=3, spacing3=3)
        csb = self._scroll(cf, self.chat_box)
        self.chat_box.pack(side='left', fill='both', expand=True)
        csb.pack(side='right', fill='y')
        for k, col in CHAT_COLORS.items():
            self.chat_box.tag_configure(k, foreground=col)
        self.chat_box.tag_configure('time', foreground=C['faint'])
        self.chat_box.tag_configure('who', foreground=C['text'], font=(f.mono_s[0], f.mono_s[1], 'bold'))
        self.chat_box.bind('<Button-1>', lambda e: self.chat_entry.focus_force())
        try:
            import ffxi_app_extra as X
            self.helper = X.CommandHelper(self, self.chat_entry, cf)
        except Exception:                                    # noqa: BLE001
            self.helper = None
        for w in (self.step, self.parts, self.work_text):
            w.master.bind('<Configure>', lambda e, w=w: self._wrap(w, e.width), add='+')

    # ---- Profiles page
    def _build_profiles(self):
        f = self.f
        page = self._page_frame('Profiles', 'One profile per player. POL-ID = profile name. Right-click a profile or character for more.')
        self.pages['profiles'] = page
        bar = tk.Frame(page.head, bg=C['bg'])
        bar.pack(fill='x', pady=(12, 0))
        self.profile_btn = RoundButton(bar, '+  Create Profile', self.do_profile, C['accent'], f.btn, height=f.s(42), width=f.s(190), radius=12)
        self.profile_btn.pack(side='left')
        self.prof_count = self.L(bar, '', f.small, fg=C['soft'])
        self.prof_count.pack(side='left', padx=16)
        panel = Panel(page.body, None, f, pad=14)
        panel.pack(fill='both', expand=True)
        tf = panel.body
        self.prof_tree = ttk.Treeview(tf, columns=('role', 'job', 'zone', 'info'), show='tree headings', selectmode='browse', height=4)
        self.prof_tree.heading('#0', text='PROFILE / CHARACTER', anchor='w')
        for col, txt, w in (('role', 'ROLE', 120), ('job', 'JOB', 90), ('zone', 'LAST ZONE', 200), ('info', '', 150)):
            self.prof_tree.heading(col, text=txt, anchor='w')
            self.prof_tree.column(col, width=f.s(w), anchor='w', stretch=True)
        self.prof_tree.column('#0', width=f.s(240), stretch=True)
        self.prof_tree.tag_configure('acct', font=f.h3, foreground=C['text'])
        self.prof_tree.tag_configure('banned', font=f.h3, foreground=C['red'])
        self.prof_tree.tag_configure('char', foreground=C['soft'])
        self.prof_tree.tag_configure('charon', foreground=C['green'])
        self.prof_tree.tag_configure('empty', foreground=C['faint'])
        sb = self._scroll(tf, self.prof_tree)
        self.prof_tree.pack(side='left', fill='both', expand=True)
        sb.pack(side='right', fill='y')
        for ev in (('<Button-2>', '<Button-3>', '<Control-Button-1>') if MAC else ('<Button-3>',)):
            self.prof_tree.bind(ev, self.profile_menu)
        self.prof_items = {}

    # ---- Internet page
    def _build_internet(self):
        f = self.f
        page = self._page_frame('Internet', 'For friends outside your house (Port forwarding mode).')
        self.pages['internet'] = page
        p = Panel(page.body, 'Forward these ports on your router to this computer', f)
        p.pack(fill='x')
        chips = tk.Frame(p.body, bg=C['card'])
        chips.pack(fill='x')
        for i, (pr, po, what) in enumerate(sn.FORWARD if sn else []):
            chips.grid_columnconfigure(i, weight=1, uniform='c')
            c = tk.Frame(chips, bg=C['card2'])
            c.grid(row=0, column=i, sticky='ew', padx=(0 if i == 0 else 5, 0 if i == 3 else 5))
            self.L(c, pr, f.tiny, fg=C['soft'], bg=C['card2']).pack(pady=(10, 0))
            self.L(c, str(po), f.mono, bg=C['card2']).pack()
            self.L(c, what, f.tiny, fg=C['faint'], bg=C['card2']).pack(pady=(0, 10))
        self.ports_text = self.L(p.body, '', f.small, fg=C['soft'], bg=C['card'], anchor='w')
        self.ports_text.pack(fill='x', pady=(12, 0))
        prow = tk.Frame(p.body, bg=C['card'])
        prow.pack(fill='x', pady=(14, 0))
        self.upnp_btn = RoundButton(prow, 'Open ports for me', self.do_open_ports, C['accent'], f.small, height=f.s(38), width=f.s(170), radius=10, bg=C['card'])
        self.upnp_btn.pack(side='left')
        self.test_btn = RoundButton(prow, 'Test my ports', self.do_test_ports, C['grey'], f.small, height=f.s(38), width=f.s(140), radius=10, bg=C['card'])
        self.test_btn.pack(side='left', padx=8)
        self.net_status = self.L(p.body, '', f.small, fg=C['soft'], bg=C['card'], anchor='w', justify='left')
        self.net_status.pack(fill='x', pady=(10, 0))
        h = Panel(page.body, 'How friends connect', f)
        h.pack(fill='x', pady=(14, 0))
        self.help_text = self.L(h.body, '', f.small, fg=C['soft'], bg=C['card'], anchor='w', justify='left')
        self.help_text.pack(fill='x')
        for w in (self.net_status, self.help_text, self.ports_text):
            w.master.bind('<Configure>', lambda e, w=w: self._wrap(w, e.width), add='+')

    # ---- Game disc page
    def _build_disc(self):
        f = self.f
        page = self._page_frame('Game disc', 'Everything PCSX2 needs: the 2016 disc and a PS2 hard drive. You only do this once.')
        self.pages['disc'] = page
        p = Panel(page.body, None, f, pad=24)
        p.pack(fill='x')
        self.L(p.body, '1.  Make the disc', f.h3, bg=C['card'], anchor='w').pack(fill='x')
        self.L(p.body, 'Pick your original disc file (in Disc > Original Disc). The patched disc is written to Disc > Patched ISO.',
               f.body, fg=C['soft'], bg=C['card'], anchor='w', justify='left').pack(fill='x', pady=(4, 0))
        self.patch_btn = RoundButton(p.body, 'Patch My Disc', self.do_patch, C['accent'], f.btn, height=f.s(46), width=f.s(200), radius=12, bg=C['card'])
        self.patch_btn.pack(anchor='w', pady=(12, 0))
        p2 = Panel(page.body, None, f, pad=24)
        p2.pack(fill='x', pady=(16, 0))
        self.L(p2.body, '2.  Make the hard drive', f.h3, bg=C['card'], anchor='w').pack(fill='x')
        self.L(p2.body, 'The game installs onto a PS2 hard drive, and it has to be formatted. Don\'t use the "Create" button in PCSX2 '
               '(it makes an unformatted one). Click this instead and save it somewhere easy, like Documents.\n\n'
               'Then point PCSX2 at it: Settings > Network & HDD > Hard Disk Drive > tick "Enabled" > "Browse" next to HDD File > pick the file you just made.',
               f.body, fg=C['soft'], bg=C['card'], anchor='w', justify='left').pack(fill='x', pady=(4, 0))
        self.hdd_btn = RoundButton(p2.body, 'Make Hard Drive', self.do_make_hdd, C['accent'], f.btn, height=f.s(46), width=f.s(200), radius=12, bg=C['card'])
        self.hdd_btn.pack(anchor='w', pady=(12, 0))
        for w in p.body.winfo_children() + p2.body.winfo_children():
            if isinstance(w, tk.Label):
                w.master.bind('<Configure>', lambda e, w=w: self._wrap(w, e.width), add='+')

    def do_make_hdd(self):
        tool = os.path.join(DISC_DIR, 'Hard Drive', 'make_hard_drive.py')
        try:
            spec = importlib.util.spec_from_file_location('ffxi_make_hdd', tool)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        except Exception:                                    # noqa: BLE001
            messagebox.showerror(TITLE, 'The hard drive maker is missing (Disc/Hard Drive/make_hard_drive.py). Copy the release folder again.')
            return
        start = os.path.expanduser('~/Documents')
        if not os.path.isdir(start):
            start = os.path.expanduser('~')
        out = filedialog.asksaveasfilename(parent=self.root, title='Save your PS2 hard drive', initialdir=start,
                                           initialfile='FFXI 2016 HDD.raw', defaultextension='.raw',
                                           filetypes=[('PS2 hard drive', '*.raw')])
        if not out:
            return
        if os.path.exists(out):
            messagebox.showerror(TITLE, 'There is already a file with that name, and it might have your game on it, so it was left alone.\n\n'
                                 'Pick a different name.')
            return
        try:
            mod.make(out)
        except Exception as e:                               # noqa: BLE001
            messagebox.showerror(TITLE, 'The hard drive could not be made: %s' % e)
            return
        messagebox.showinfo(TITLE, 'Your PS2 hard drive is ready:\n\n%s\n\n'
                            'Now in PCSX2: Settings > Network & HDD > Hard Disk Drive. Tick "Enabled", click "Browse" next to '
                            'HDD File and pick this file. Don\'t click "Create".' % out)

    # -------------------------------------------------------------- chat box
    def chat_add(self, kind, text, speaker=None, extra=''):
        b = self.chat_box
        b.configure(state='normal')
        b.insert('end', time.strftime('%H:%M  '), 'time')
        if speaker:
            b.insert('end', '[%s] ' % kind, kind if kind in CHAT_COLORS else 'Say')
            b.insert('end', speaker + (' (%s)' % extra if extra else '') + ': ', 'who')
            b.insert('end', text + '\n', kind if kind in CHAT_COLORS else 'Say')
        else:
            b.insert('end', text + '\n', kind)
        if int(b.index('end-1c').split('.')[0]) > 2000:
            b.delete('1.0', '500.0')
        b.configure(state='disabled')
        b.see('end')

    def _enter(self, ev=None):
        if self.helper and self.helper.wants_enter():
            self.helper.accept()
        else:
            if self.helper:
                self.helper.hide()
            self.send_chat()
        return 'break'

    def send_chat(self):
        line = self.chat_entry.get().strip()
        if not line:
            return
        self.chat_entry.delete(0, 'end')
        if line.lower() == '/clear':
            self.chat_box.configure(state='normal')
            self.chat_box.delete('1.0', 'end')
            self.chat_box.configure(state='disabled')
            return
        if not line.startswith('/'):
            if not (self.state and self.state.get('xi_map')):
                self.chat_add('error', 'The server is off, so the message was not sent.')
                return
            if not self.prev_online:
                self.chat_add('error', 'Nobody is online, so the message was not sent.')
                return
            self.chat_add('Server', 'Server: ' + line)
        else:
            self.chat_add('event', '> ' + line)
        self.admin(line)

    def admin(self, line):
        def work():
            ok, text = sa.command(line)
            if text:
                self.q.put(('chat', 'admin' if ok else 'error', text))
            self.kick.set()
        threading.Thread(target=work, daemon=True).start()

    # -------------------------------------------------------------- background status
    def _collector(self):
        n, errs = 0, set()

        def safe(key, fn, snap):
            try:
                snap[key] = fn()
                errs.discard(key)
            except Exception as e:                           # noqa: BLE001
                if key not in errs:
                    errs.add(key)
                    if "Can't connect" not in str(e) and '2002' not in str(e):   # the database is still starting or stopping: not worth a red line
                        self.q.put(('chat', 'error', 'Could not read %s: %s' % (key, e)))
        while True:
            snap = {}
            try:
                st = sc.status()
                snap.update(st=st, ip=sc.lan_address(), other=(not st['on'] and sc.other_server_running()))
                if n % 10 == 0 or self.kick.is_set() or not self.setup_ok:
                    snap['checks'] = sc.check_setup()
                if n % 10 == 0 or self.kick.is_set():
                    safe('ts', sn.tailscale_address, snap)
                    safe('public', sn.public_address, snap)
                if st['database']:
                    safe('online', sa.online_players, snap)
                    if n % 2 == 0 or self.kick.is_set():
                        safe('profiles', sa.profiles, snap)
                    if st['xi_map']:
                        safe('chat', self.chat.new_lines, snap)
                    snap['link'] = sa.bridge_ok()
                try:
                    snap['members'] = sr.load()['members']
                    if self.hit_id is None:
                        self.hit_id = sch.last_hit_id()
                    new_hits = sch.hits(since_id=self.hit_id)
                    if new_hits:
                        self.hit_id = new_hits[-1][0]
                        snap['hits'] = new_hits
                    done = sa.expire_mutes()
                    if done:
                        snap['unmuted'] = done
                except Exception:                            # noqa: BLE001
                    pass
                self.q.put(('snap', snap))
            except Exception as e:                           # noqa: BLE001
                self.q.put(('chat', 'error', 'Status check failed: %s' % e))
            n += 1
            self.kick.wait(3)
            self.kick.clear()

    def poll(self):
        try:
            while True:
                item = self.q.get_nowait()
                kind = item[0]
                if kind == 'snap':
                    self.apply(item[1])
                elif kind == 'step':
                    if self.busy:
                        self.step.config(text=item[1], fg=C['amber'])
                elif kind == 'chat':
                    self.chat_add(item[1], item[2])
                elif kind == 'done':
                    _, done, res, err = item
                    self.busy = False
                    if err:
                        self.step.config(text=err, fg=C['red'])
                        self.chat_add('error', err)
                        messagebox.showerror(TITLE, err)
                    if done:
                        done(res, err)
                    self.kick.set()
                elif kind == 'patch':
                    self._patch_update(*item[1:])
                elif kind == 'work':
                    if item[2] == getattr(self, 'check_seq', 0):
                        self._show_work(item[1])
                elif kind == 'net':
                    self.net_status.config(text=item[1], fg=item[2])
                    self.upnp_btn.set_enabled(True)
                    self.test_btn.set_enabled(True)
        except queue.Empty:
            pass
        self.root.after(150, self.poll)

    def _set_status(self, mode, text):
        col = {'on': C['green'], 'off': C['red'], 'busy': C['amber']}[mode]
        self.status_dot.delete('all')
        s = self.f.s(18)
        self.status_dot.create_oval(2, 2, s - 2, s - 2, fill=col, outline='')
        self.status_text.config(text=text, fg=C['text'])
        self.nav_pill.set(mode, {'on': 'Server on', 'off': 'Server off', 'busy': 'Working...'}[mode])
        self.stop_btn.color = C['red_dk'] if mode in ('on', 'busy') else C['grey']
        self.stop_btn.draw()

    def apply(self, s):
        st = s['st']
        self.state = st
        if 'checks' in s:
            bad = [t for ok, t in s['checks'] if not ok]
            self.setup_ok = not bad
            if bad:
                self.setup_list.config(text='One-time setup needed: ' + '; '.join(bad) + '.')
                if not self.setup_card.winfo_ismapped():
                    self.setup_card.grid(row=3, column=0, columnspan=6, sticky='ew', pady=(14, 0))
            elif self.setup_card.winfo_ismapped():
                self.setup_card.grid_forget()
        if not self.busy and (st['on'] != getattr(self, '_prev_on', None) or (st['on'] and time.time() - self.last_check > 30)):
            self._prev_on = st['on']
            self.root.after(500, self.check_now)
        nice = {'database': 'Database', 'xi_connect': 'Login', 'xi_search': 'Search', 'xi_world': 'World', 'xi_map': 'Map',
                'proxy': 'PS2 sign-in', 'social': 'Friends'}
        self.parts.config(text='    '.join(('● ' if st[p] else '○ ') + nice[p] for p in sc.ORDER))
        if not self.busy:
            if st['on']:
                self._set_status('on', 'Server is on')
                self.step.config(text='')
            elif s.get('other'):
                self._set_status('off', 'Server is off')
                self.step.config(text='Another server is already running on this computer. Close it first.', fg=C['red'])
            elif st['any']:
                self._set_status('busy', 'Partly on')
                self.step.config(text='Click Start Server to start the rest, or Stop.', fg=C['amber'])
            else:
                self._set_status('off', 'Server is off')
                self.step.config(text='' if self.setup_ok else 'Run Setup first.', fg=C['soft'])
            self.start_btn.set_enabled(self.setup_ok and not st['on'])
            self.stop_btn.set_enabled(st['any'])
            self.profile_btn.set_enabled(self.setup_ok)
        ip = s['ip']
        self.addr['lan'] = ip or ''
        if 'public' in s:
            self.addr['net'] = s['public'][0] or ''
        if 'ts' in s:
            self.addr['ts'] = s['ts']
        self._show_ip()
        if self.last_ip and ip and ip != self.last_ip:
            self.chat_add('error', 'This computer\'s home address changed from %s to %s.' % (self.last_ip, ip))
        if ip:
            self.last_ip = ip
        if 'members' in s:
            self.members = {k.lower(): v for k, v in s['members'].items()}
        if 'online' in s:
            self._fill_online(s['online'])
        elif not st['database']:
            self._fill_online([])
        if 'profiles' in s:
            self._fill_profiles(s['profiles'])
        elif not st['database'] and not self.prof_items:
            self._fill_profiles(None)
        for kind, spk, msg, extra in s.get('chat', []):
            self.chat_add(kind, msg, spk, extra)
        for _, ts, p, chn, rule, tx, done in s.get('hits', []):
            self.chat_add('error', '[Chat rules] %s (%s), %s: "%s" -> %s' % (p, chn, rule, tx[:80], done))
        for n in s.get('unmuted', []):
            self.chat_add('event', '%s can chat again (mute time over).' % n)
        if st['xi_map']:
            self.link_state.config(text='● live' if s.get('link') else '○ connecting...', fg=C['green'] if s.get('link') else C['amber'])
        else:
            self.link_state.config(text='off', fg=C['faint'])
        if WINDOWS:
            self._keep_awake(st['on'])

    def _fill_online(self, players):
        t = self.online
        sel = t.selection()
        t.delete(*t.get_children())
        for i, p in enumerate(players):
            tags = ['odd'] if i % 2 else []
            if p['state'] == 'AFK':
                tags.append('afk')
            t.insert('', 'end', iid='p:' + p['name'], values=(p['name'], p['zone'] + ('  (zoning)' if p['state'] == 'Zoning' else ''),
                                                             p['job'], self.members.get(p['name'].lower(), '')), tags=tags)
        if sel and t.exists(sel[0]):
            t.selection_set(sel[0])
        else:
            t.selection_set(())
        self.online_count.config(text='%d playing' % len(players) if players else 'nobody yet')
        cur = {p['name']: p for p in players}
        if self.prev_online is not None:
            for n, p in cur.items():
                if n not in self.prev_online:
                    self.chat_add('event', '%s signed in (%s)' % (n, p['zone']))
                elif self.prev_online[n]['zone'] != p['zone'] and p['state'] != 'Zoning':
                    self.chat_add('event', '%s arrived in %s' % (n, p['zone']))
            for n in self.prev_online:
                if n not in cur:
                    self.chat_add('event', '%s signed out' % n)
        self.prev_online = cur if self.state and self.state.get('database') else None

    def _fill_profiles(self, profiles):
        t = self.prof_tree
        open_ = {i for i in t.get_children() if t.item(i, 'open')}
        sel = t.selection()
        t.delete(*t.get_children())
        self.prof_items = {}
        if profiles is None:
            t.insert('', 'end', iid='none', text='Start the server to see the profiles', tags=('empty',))
            self.prof_count.config(text='')
            return
        self.char_names = [c['name'] for a in profiles for c in a['chars']]
        if not profiles:
            t.insert('', 'end', iid='none', text='No profiles yet. Click Create Profile', tags=('empty',))
        for a in profiles:
            iid = 'a:' + a['login']
            info = 'BANNED' if a['banned'] else ('%d character%s' % (len(a['chars']), '' if len(a['chars']) == 1 else 's'))
            t.insert('', 'end', iid=iid, text=('●  ' if a['online'] else '    ') + a['login'], values=('', '', '', info),
                     open=(iid in open_ or a['online'] or len(profiles) <= 8), tags=('banned' if a['banned'] else 'acct',))
            self.prof_items[iid] = a
            if not a['chars']:
                t.insert(iid, 'end', text='no characters yet', tags=('empty',))
            for c in a['chars']:
                t.insert(iid, 'end', iid='c:' + c['name'], text=('● ' if c['online'] else '') + c['name'],
                         values=(self.members.get(c['name'].lower(), ''), c['job'], c['zone'], 'online' if c['online'] else ''),
                         tags=('charon' if c['online'] else 'char',))
        if sel and t.exists(sel[0]):
            t.selection_set(sel[0])
        else:
            t.selection_set(())
        self.prof_count.config(text='%d profile%s' % (len(profiles), '' if len(profiles) == 1 else 's'))

    # -------------------------------------------------------------- jobs
    def run_job(self, label, fn, done=None):
        if self.busy:
            return
        self.busy = True
        for b in (self.start_btn, self.stop_btn, self.profile_btn):
            b.set_enabled(False)
        self._set_status('busy', label)
        self.step.config(text='', fg=C['amber'])

        def work():
            try:
                res = fn(lambda text: self.q.put(('step', text)))
                self.q.put(('done', done, res, None))
            except Exception as e:                           # noqa: BLE001
                plain = isinstance(e, sc.ServerError)
                if not plain:
                    try:
                        sc.log_line('app error: ' + traceback.format_exc())
                    except Exception:                        # noqa: BLE001
                        pass
                self.q.put(('done', done, None, str(e) if plain else 'Something went wrong: %s' % e))
        threading.Thread(target=work, daemon=True).start()

    def watch_map(self):
        """Every 5 seconds: if the map server crashed while the server is on, start it again."""
        s = self.state
        if s and not self.busy and s.get('database') and s.get('proxy') and s.get('xi_world') and not s.get('xi_map'):
            self.chat_add('error', 'The map server stopped. Starting it again...')
            self.run_job('Restarting the map...', lambda say: sc.restart_map_if_down(say))
        self.root.after(5000, self.watch_map)

    def do_start(self):
        self.run_job('Starting...', lambda say: sc.start(say), done=lambda r, e: (not e) and self.chat_add('admin', 'The server is on.'))

    def do_stop(self):
        if self.state and self.state.get('on'):
            if not messagebox.askyesno(TITLE, 'Stop the server?\n\nAnyone playing right now will be disconnected.'):
                return
        self.run_job('Stopping...', lambda say: sc.stop(say), done=lambda r, e: (not e) and self.chat_add('admin', 'The server is off.'))

    # ---- modes, addresses, ports
    def _take_focus(self):
        try:
            self.root.lift()
            self.root.attributes('-topmost', True)
            self.root.after(400, lambda: self.root.attributes('-topmost', False))
            self.root.focus_force()
            self.chat_entry.focus_set()
        except tk.TclError:
            pass

    def _wrap(self, w, width):
        want = max(120, width - 8)
        if abs(int(w.cget('wraplength') or 0) - want) > 12:
            w.config(wraplength=want)

    def set_mode(self, mode):
        if mode == self.mode:
            return
        self.mode = mode
        self.mode_switch.set(mode)
        try:
            sn.set_mode(mode)
        except Exception as e:                               # noqa: BLE001
            self.chat_add('error', str(e))
        self._show_ip()
        self.chat_add('admin', 'Mode: %s' % ('Local' if mode == 'local' else 'Port forwarding'))
        self.check_now()

    def _show_ip(self):
        internet = self.mode == 'internet'
        ip = self.addr['net'] if internet else self.addr['lan']
        empty = 'not found' if internet else 'not on a network'
        self.ip_val.config(text=ip or empty, fg=C['text'] if ip else C['red'], font=self.f.mono if ip else self.f.body)
        self.copy_btn.set_enabled(bool(ip))
        (self.change_btn.grid if internet else self.change_btn.grid_remove)()
        if internet and sn:
            self.ports_hint.config(text='Forward %s to %s   → Internet page' % (
                ', '.join('%s %d' % (pr, po) for pr, po, _ in sn.FORWARD), self.addr['lan'] or 'this computer'), fg=C['soft'])
            self.ports_hint.grid()
        else:
            self.ports_hint.grid_remove()
        if sn:
            self.ports_text.config(text='to this computer: %s' % (self.addr['lan'] or '?'))
            lan, net = self.addr['lan'] or '(home address)', self.addr['net'] or '(internet address)'
            ts = self.addr.get('ts')
            self.help_text.config(text=(
                'Local: friends in your house type ServerIP %s, ServerPort %d.\n\n'
                'Port forwarding: on your router, forward the 4 ports above to %s (or click "Open ports for me"), and give this '
                'computer a fixed home address in the router (DHCP reservation). Friends type ServerIP %s, ServerPort %d. '
                '"Test my ports" checks the router; the best test is a friend signing in.\n\n'
                'Tailscale (optional, no router changes): install Tailscale from tailscale.com here and on your friends\' '
                'computers, invite them to your Tailscale network; they type %s.') % (
                lan, sc.SERVER_PORT_FOR_PLAYERS, lan, net, sc.SERVER_PORT_FOR_PLAYERS, ts or 'this computer\'s Tailscale address'))

    def copy_ip(self):
        ip = self.addr['net'] if self.mode == 'internet' else self.addr['lan']
        if ip:
            self.root.clipboard_clear()
            self.root.clipboard_append(ip)
            self.copy_btn.set_text('Copied')
            self.root.after(1500, lambda: self.copy_btn.set_text('Copy'))

    def check_now(self):
        if not sn:
            return
        self.checking = True
        self.last_check = time.time()
        self.check_seq = getattr(self, 'check_seq', 0) + 1
        seq = self.check_seq
        self.work_title.config(text='Checking...', fg=C['amber'])
        self.work_icon.config(fg=C['amber'])
        mode = self.mode

        def work():
            try:
                res = sn.check_working(mode)
            except Exception as e:                           # noqa: BLE001
                res = ('unsure', 'Could not check', str(e))
            self.q.put(('work', res, seq))
        threading.Thread(target=work, daemon=True).start()

    def _show_work(self, res):
        self.checking = False
        state, head, text = res
        col = {'ok': C['green'], 'bad': C['red'], 'unsure': C['amber']}[state]
        self.work_icon.config(fg=col)
        self.work_title.config(text=head, fg=col)
        self.work_text.config(text=text, fg=C['soft'])

    def change_public(self):
        cur = sc.load_config().get('internet_ip_manual', '')
        v = self.ask('Internet address', 'Type your home\'s internet address (your router\'s status page shows it). '
                     'Leave it empty to find it automatically again.', initial=cur)
        if v is None and not cur:
            return

        def work():
            try:
                sn.set_manual_public_address(v or '')
                self.q.put(('chat', 'admin', 'Internet address: %s' % (sn.public_address()[0] or 'not found')))
            except Exception as e:                           # noqa: BLE001
                self.q.put(('chat', 'error', str(e)))
            self.kick.set()
        threading.Thread(target=work, daemon=True).start()

    def do_open_ports(self):
        if not messagebox.askyesno(TITLE, 'Ask your router to open the game ports to this computer?\n\n'
                                          + '\n'.join('%s %d  (%s)' % fw for fw in sn.FORWARD)
                                          + '\n\nThis works on most home routers (UPnP). The ports stay open until you remove them '
                                            'in the router settings.'):
            return
        self.net_status.config(text='Asking your router...', fg=C['amber'])
        self.upnp_btn.set_enabled(False)

        def work():
            try:
                res = sn.upnp_open_ports()
                ok = all(r[0] for r in res)
                text = ('Done. Your router opened all the ports.' if ok else 'Your router opened only some ports:') + \
                       '\n' + '\n'.join(('✓ ' if r[0] else '✗ ') + r[1] for r in res)
                self.q.put(('net', text, C['green'] if ok else C['amber']))
            except Exception as e:                           # noqa: BLE001
                self.q.put(('net', str(e), C['red']))
        threading.Thread(target=work, daemon=True).start()

    def do_test_ports(self):
        self.net_status.config(text='Testing...', fg=C['amber'])
        self.test_btn.set_enabled(False)

        def work():
            try:
                lines = sn.test_ports()
                bad = [l for l in lines if l[0] is False]
                text = '\n'.join({True: '✓ ', False: '✗ ', None: '• '}[ok] + s for ok, s in lines)
                self.q.put(('net', text, C['red'] if bad else C['green'] if all(l[0] for l in lines) else C['soft']))
            except Exception as e:                           # noqa: BLE001
                self.q.put(('net', 'The test did not work: %s' % e, C['red']))
        threading.Thread(target=work, daemon=True).start()

    def open_folder(self, path):
        try:
            os.makedirs(path, exist_ok=True)
            if WINDOWS:
                os.startfile(path)                           # noqa: S606
            elif MAC:
                subprocess.Popen(['open', path])
            else:
                subprocess.Popen(['xdg-open', path])
        except OSError as e:
            messagebox.showerror(TITLE, 'Could not open the folder: %s' % e)

    def _check_write_access(self):
        """macOS can block apps from the Downloads/Desktop/Documents folders until you allow it."""
        try:
            os.makedirs(sc.DATA, exist_ok=True)
            p = os.path.join(sc.DATA, '.write-test')
            with open(p, 'w') as fh:
                fh.write('ok')
            os.remove(p)
        except OSError:
            msg = ('This app is not allowed to save files in the release folder.\n\n'
                   + ('On a Mac: open System Settings > Privacy & Security > Files and Folders, find "FFXI Server" and turn on '
                      '"Downloads Folder" (or the folder you keep the release in). Then open the app again.\n\n'
                      'Or move the whole "FFXI 2016 Release" folder into your home folder.' if MAC else
                      'Move the whole "FFXI 2016 Release" folder somewhere you can save files, for example your Documents folder.'))
            self.chat_add('error', msg.replace('\n\n', ' '))
            messagebox.showwarning(TITLE, msg)

    def do_setup(self):
        setup = os.path.join(SERVER_DIR, 'setup')
        try:
            if WINDOWS:
                os.startfile(os.path.join(setup, 'Setup Windows.bat'))   # noqa: S606
            elif MAC:
                subprocess.Popen(['open', '-a', 'Terminal', os.path.join(setup, 'Setup Mac.command')])
            else:
                import shutil
                script = os.path.join(setup, 'Setup Linux.sh')
                for term in (['x-terminal-emulator', '-e'], ['gnome-terminal', '--'], ['konsole', '-e'], ['xfce4-terminal', '-x'], ['xterm', '-e']):
                    if shutil.which(term[0]):
                        subprocess.Popen(term + ['bash', script])
                        break
                else:
                    messagebox.showinfo(TITLE, 'Open a terminal and run:\n\nbash "%s"' % script)
                    return
            messagebox.showinfo(TITLE, 'Setup has opened in a new window. Follow it there.\n\nWhen it says it is finished, click "Check again".')
        except Exception as e:                               # noqa: BLE001
            messagebox.showerror(TITLE, 'Could not open Setup: %s\n\nIt is in the folder Server/setup.' % e)

    # -------------------------------------------------------------- dialogs
    def dialog(self, title):
        d = tk.Toplevel(self.root)
        d.title(title + ' (Fan Project by Habex)')
        d.configure(bg=C['bg'])
        d.transient(self.root)
        d.resizable(False, False)
        box = tk.Frame(d, bg=C['bg'])
        box.pack(fill='both', expand=True, padx=28, pady=24)
        return d, box

    def _center(self, d):
        d.update_idletasks()
        x = self.root.winfo_rootx() + (self.root.winfo_width() - d.winfo_width()) // 2
        y = self.root.winfo_rooty() + (self.root.winfo_height() - d.winfo_height()) // 3
        d.geometry('+%d+%d' % (max(0, x), max(0, y)))
        try:
            d.grab_set()
        except tk.TclError:
            pass

    def ask(self, title, prompt, initial='', hint=''):
        """A small themed question box. Returns the text or None."""
        d, box = self.dialog(title)
        self.L(box, title, self.f.h1).pack(anchor='w')
        self.L(box, prompt, self.f.body, fg=C['soft'], justify='left', wraplength=self.f.s(420)).pack(anchor='w', pady=(6, 12))
        e = self.entry(box, width=34)
        e.pack(fill='x', ipady=self.f.s(7))
        e.insert(0, initial)
        if hint:
            self.L(box, hint, self.f.tiny, fg=C['faint']).pack(anchor='w', pady=(4, 0))
        out = {'v': None}
        row = tk.Frame(box, bg=C['bg'])
        row.pack(fill='x', pady=(18, 0))

        def ok(*_):
            out['v'] = e.get().strip()
            d.destroy()
        RoundButton(row, 'OK', ok, C['accent'], self.f.h3, height=self.f.s(40), width=self.f.s(110)).pack(side='right')
        RoundButton(row, 'Cancel', d.destroy, C['grey'], self.f.h3, height=self.f.s(40), width=self.f.s(110)).pack(side='right', padx=8)
        d.bind('<Return>', ok)
        d.bind('<Escape>', lambda ev: d.destroy())
        self._center(d)
        e.focus_set()
        self.root.wait_window(d)
        return out['v'] or None

    # ---- Create Profile
    def do_profile(self):
        d, box = self.dialog('Create Profile')
        self.L(box, 'Create Profile', self.f.h1).pack(anchor='w')
        self.L(box, 'Letters and numbers only.', self.f.small, fg=C['soft']).pack(anchor='w', pady=(4, 14))
        form = tk.Frame(box, bg=C['bg'])
        form.pack(fill='x')
        ents = {}
        for i, (k, hint, show) in enumerate([('Username', '3 to 15 letters or numbers (this is the POL-ID)', ''),
                                             ('Password', '6 to 15 letters or numbers', '•'),
                                             ('Password again', '', '•')]):
            self.L(form, k, self.f.h3, anchor='w').grid(row=i * 2, column=0, sticky='w', pady=(8, 0), padx=(0, 14))
            e = self.entry(form, show=show, width=24)
            e.grid(row=i * 2, column=1, sticky='we', pady=(8, 0), ipady=self.f.s(6))
            if hint:
                self.L(form, hint, self.f.tiny, fg=C['faint'], anchor='w').grid(row=i * 2 + 1, column=1, sticky='w')
            ents[k] = e
        showvar = tk.IntVar(value=0)

        def toggle():
            for k in ('Password', 'Password again'):
                ents[k].config(show='' if showvar.get() else '•')
        tk.Checkbutton(form, text='Show password', variable=showvar, command=toggle, bg=C['bg'], fg=C['soft'], font=self.f.small,
                       activebackground=C['bg'], activeforeground=C['text'], selectcolor=C['input'], highlightthickness=0,
                       bd=0).grid(row=6, column=1, sticky='w', pady=(8, 0))
        msg = self.L(box, '', self.f.h3, fg=C['red'], anchor='w', justify='left', wraplength=self.f.s(420))
        msg.pack(fill='x', pady=(10, 0))
        row = tk.Frame(box, bg=C['bg'])
        row.pack(fill='x', pady=(12, 0))

        def submit(*_):
            name, pw = ents['Username'].get().strip(), ents['Password'].get()
            if pw != ents['Password again'].get():
                msg.config(text='The two passwords are not the same. Type them again.', fg=C['red'])
                return
            why = sc.check_profile(name, pw)
            if why:
                msg.config(text=why, fg=C['red'])
                return
            msg.config(text='Making the profile...', fg=C['soft'])
            make.set_enabled(False)

            def work():
                try:
                    sc.create_profile(name, pw, say=lambda t: None)
                    ip = sc.lan_address()
                    self.root.after(0, lambda: (d.destroy(), self.chat_add('admin', 'Profile "%s" made.' % name),
                                                self.show_profile_done(name, pw, ip), self.kick.set()))
                except Exception as e:                       # noqa: BLE001
                    text = str(e) if isinstance(e, sc.ServerError) else 'Something went wrong: %s' % e
                    self.root.after(0, lambda: (msg.config(text=text, fg=C['red']), make.set_enabled(True)))
            threading.Thread(target=work, daemon=True).start()
        make = RoundButton(row, 'Create Profile', submit, C['accent'], self.f.h3, height=self.f.s(42), width=self.f.s(170))
        make.pack(side='right')
        RoundButton(row, 'Cancel', d.destroy, C['grey'], self.f.h3, height=self.f.s(42), width=self.f.s(110)).pack(side='right', padx=8)
        d.bind('<Return>', submit)
        d.bind('<Escape>', lambda e: d.destroy())
        self._center(d)
        ents['Username'].focus_set()
        self._profile_dialog = (d, ents, msg, make)

    def show_profile_done(self, name, pw, ip):
        d, box = self.dialog('Profile made')
        self.L(box, 'Profile "%s" is ready' % name, self.f.h1, fg=C['green']).pack(anchor='w')
        self.L(box, 'On the game\'s sign-in page, type:', self.f.body, fg=C['soft']).pack(anchor='w', pady=(6, 14))
        card = tk.Frame(box, bg=C['card'])
        card.pack(fill='x')
        sip = (self.addr['net'] if self.mode == 'internet' else ip) or '(not found)'
        for i, (k, v) in enumerate([('POL-ID', name), ('Password', pw), ('ServerIP', sip), ('ServerPort', str(sc.SERVER_PORT_FOR_PLAYERS))]):
            self.L(card, k, self.f.h3, fg=C['soft'], anchor='w', width=10, bg=C['card']).grid(row=i, column=0, sticky='w', padx=(22, 8), pady=self.f.s(8))
            self.L(card, v, (self.f.mono[0], self.f.s(22), 'bold'), anchor='w', bg=C['card']).grid(row=i, column=1, sticky='w', padx=(0, 22), pady=self.f.s(8))
        self.L(box, 'The password is not shown again.', self.f.small, fg=C['faint']).pack(anchor='w', pady=(12, 0))
        RoundButton(box, 'OK', d.destroy, C['accent'], self.f.h3, height=self.f.s(42), width=self.f.s(120)).pack(anchor='e', pady=(14, 0))
        d.bind('<Return>', lambda e: d.destroy())
        self._center(d)
        self._done_dialog = d

    # ---- right-click menus
    def _menu(self):
        return tk.Menu(self.root, tearoff=0, bg=C['card2'], fg=C['text'], activebackground=C['sel'], activeforeground='white',
                       bd=0, font=self.f.body)

    def _popup(self, m, ev):
        try:
            m.tk_popup(ev.x_root, ev.y_root)
        finally:
            m.grab_release()

    def player_menu(self, name, online, ev):
        m = self._menu()
        if online:
            m.add_command(label='Send a private message...', command=lambda: self._ask_cmd('Message to %s' % name, 'The message (a tell from Server):', '/tell %s {}' % name))
            m.add_command(label='Heal', command=lambda: self.admin('/heal %s' % name))
            m.add_command(label='Free from a stuck cutscene', command=lambda: self.admin('/release %s' % name))
        m.add_command(label='Give an item...', command=lambda: self._ask_cmd('Give %s an item' % name, 'Item name and amount (e.g.  hi-potion 3):', '/give %s {}' % name))
        m.add_command(label='Move to a zone...', command=lambda: self._ask_cmd('Move %s' % name, 'Zone name (e.g.  Lower Jeuno):', '/tp %s {}' % name))
        m.add_command(label='Send to home point', command=lambda: self.admin('/home %s' % name))
        m.add_command(label='View chat history', command=lambda: self.open_chat_history(name))
        m.add_separator()
        roles = sorted(sr.load()['roles']) if sr else []
        pm = self._menu()
        for r in roles:
            pm.add_command(label=r, command=lambda r=r: self._promote(name, r))
        if not roles:
            pm.add_command(label='(no roles yet, see Roles)', state='disabled')
        m.add_cascade(label='Promote', menu=pm)
        cur = self.members.get(name.lower())
        if cur:
            m.add_command(label='Demote (remove %s)' % cur, command=lambda: self.admin('/demote %s' % name))
        m.add_separator()
        if name.lower() in [x.lower() for x in (sa.muted() if sa else [])]:
            m.add_command(label='Unmute', command=lambda: self.admin('/unmute %s' % name))
        else:
            m.add_command(label='Mute...', command=lambda: self._ask_cmd('Mute %s' % name, 'For how many minutes? (empty = until you unmute)', '/mute %s {}' % name, allow_empty=True))
        m.add_command(label='Send to jail', command=lambda: self.admin('/jail %s' % name))
        m.add_command(label='Free from jail', command=lambda: self.admin('/unjail %s' % name))
        if online:
            m.add_command(label='Kick', command=lambda: self.admin('/kick %s' % name))
        m.add_command(label='Ban...', command=lambda: self._ask_cmd('Ban %s' % name, 'Reason (optional):', '/ban %s {}' % name, allow_empty=True))
        self._popup(m, ev)

    def open_chat_history(self, name):
        self.show_page('chat')
        cp = self.chat_page
        cp.nb.select(3)
        cp.h_player.delete(0, 'end')
        cp.h_player.insert(0, name)
        cp.h_fill()

    def _promote(self, name, role):
        self.chat_add('event', '> /promote %s %s' % (name, role))
        self.admin('/promote %s %s' % (name, role))

    def _ask_cmd(self, title, prompt, template, allow_empty=False):
        v = self.ask(title, prompt)
        if v or allow_empty:
            line = template.format(v or '').strip()
            self.chat_add('event', '> ' + line)
            self.admin(line)

    def online_menu(self, ev):
        iid = self.online.identify_row(ev.y)
        if not iid or not iid.startswith('p:'):
            return
        self.online.selection_set(iid)
        self.player_menu(iid[2:], True, ev)

    def profile_menu(self, ev):
        iid = self.prof_tree.identify_row(ev.y)
        if not iid:
            return
        self.prof_tree.selection_set(iid)
        if iid.startswith('c:'):
            on = 'charon' in self.prof_tree.item(iid, 'tags')
            return self.player_menu(iid[2:], on, ev)
        a = self.prof_items.get(iid)
        if not a:
            return
        m = self._menu()
        m.add_command(label='Change password...', command=lambda: self.change_password(a['login']))
        m.add_separator()
        if a['banned']:
            m.add_command(label='Unban', command=lambda: self.admin('/unban %s' % a['login']))
        else:
            m.add_command(label='Ban...', command=lambda: messagebox.askyesno(TITLE, 'Ban the profile "%s"?\n\nThey cannot sign in '
                                                                                   'until you unban it.' % a['login']) and self.admin('/ban %s' % a['login']))
        self._popup(m, ev)

    def change_password(self, login):
        pw = self.ask('New password', 'A new password for "%s".' % login, hint='6 to 15 letters or numbers')
        if not pw:
            return

        def work():
            try:
                sc.change_password(login, pw)
                self.root.after(0, lambda: (self.chat_add('admin', 'Password changed for %s.' % login), self.show_profile_done(login, pw, sc.lan_address())))
            except Exception as e:                           # noqa: BLE001
                self.q.put(('chat', 'error', str(e)))
        threading.Thread(target=work, daemon=True).start()

    # ---- Patch My Disc
    def _patcher(self):
        mod_path = os.environ.get('FFXI_PATCHER') or os.path.join(DISC_DIR, 'Patch', 'patch_iso.py')
        if not os.path.exists(mod_path):
            return None, None, 'The disc patcher is missing (Disc/Patch/patch_iso.py). Copy the release folder again.'
        pdir = os.path.dirname(mod_path)
        names = os.listdir(pdir)
        patches = sorted(x for x in names if x.lower().endswith('.ffxipatch'))
        if not patches:                                      # a patch in parts: NAME.ffxipatch.001, .002 ... (the patcher reads them as one)
            patches = sorted(x[:-4] for x in names if x.lower().endswith('.ffxipatch.001'))
        if not patches:
            return None, None, ('The patch file is missing. Put "FFXI 2016 Patch.ffxipatch" (or both of its parts, .001 and .002) '
                                'in the Disc/Patch folder.')
        spec = importlib.util.spec_from_file_location('ffxi_patch_iso', mod_path)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod, os.path.join(pdir, patches[0]), None

    def do_patch(self):
        if getattr(self, '_patching', False):
            return
        try:
            mod, patchfile, err = self._patcher()
        except Exception as e:                               # noqa: BLE001
            mod, patchfile, err = None, None, 'The disc patcher could not be loaded: %s' % e
        if err:
            messagebox.showerror(TITLE, err)
            return
        start_dir = os.path.join(DISC_DIR, 'Original Disc')
        if not os.path.isdir(start_dir):
            start_dir = os.path.expanduser('~')
        orig = filedialog.askopenfilename(parent=self.root, title='Pick your original FFXI disc file (.iso)', initialdir=start_dir,
                                          filetypes=[('Disc image', '*.iso *.ISO'), ('All files', '*')])
        if not orig:
            return
        out_dir = os.path.join(DISC_DIR, 'Patched ISO')
        try:
            os.makedirs(out_dir, exist_ok=True)
            probe = os.path.join(out_dir, '.write-test')
            open(probe, 'w').close()
            os.remove(probe)
        except OSError:
            out_dir = os.path.dirname(orig)
        out = os.path.join(out_dir, 'FFXI 2016 (Patched).iso')
        if os.path.abspath(out) == os.path.abspath(orig):
            out = os.path.join(out_dir, 'FFXI 2016 (Patched) new.iso')
        if os.path.exists(out) and not messagebox.askyesno(TITLE, 'There is already a patched disc:\n\n%s\n\nMake it again (the old one is replaced)?' % out):
            return
        self._patch_window(orig)

        def work():
            try:                                             # the patcher writes "<out>.part" and renames it when it is checked
                mod.apply(orig, patchfile, out, progress=lambda frac, text='': self.q.put(('patch', frac, text, None, None)))
                self.q.put(('patch', 1.0, 'Done', out, None))
            except Exception as e:                           # noqa: BLE001
                try:
                    if os.path.exists(out + '.part'):
                        os.remove(out + '.part')
                except OSError:
                    pass
                self.q.put(('patch', None, '', None, str(e) if isinstance(e, ValueError) else 'Patching did not work: %s' % e))
        self._patching = True
        threading.Thread(target=work, daemon=True).start()

    def _patch_window(self, orig):
        d, box = self.dialog('Patch My Disc')
        d.protocol('WM_DELETE_WINDOW', lambda: None)
        title = self.L(box, 'Patching your disc...', self.f.h1)
        title.pack(anchor='w')
        self.L(box, 'Original: ' + os.path.basename(orig), self.f.small, fg=C['soft']).pack(anchor='w', pady=(4, 0))
        bar = ttk.Progressbar(box, length=self.f.s(520), mode='determinate', maximum=1000, style='ffxi.Horizontal.TProgressbar')
        bar.pack(fill='x', pady=(18, 8))
        text = self.L(box, 'Starting...', self.f.body, anchor='w', justify='left', wraplength=self.f.s(520))
        text.pack(fill='x')
        row = tk.Frame(box, bg=C['bg'])
        row.pack(fill='x', pady=(16, 0))
        self._pw = dict(win=d, bar=bar, text=text, row=row, title=title)
        self._center(d)

    def _patch_update(self, frac, text, out, err):
        w = getattr(self, '_pw', None)
        if not w:
            return
        if frac is not None:
            w['bar']['value'] = int(max(0.0, min(1.0, frac)) * 1000)
            if text and not out:
                w['text'].config(text='%s  (%d%%)' % (text, int(frac * 100)))
        if out or err:
            self._patching = False
            w['win'].protocol('WM_DELETE_WINDOW', w['win'].destroy)
            if out:
                w['title'].config(text='Done', fg=C['green'])
                w['text'].config(text='Done. Your patched disc is:\n\n' + out, font=self.f.h3)
                RoundButton(w['row'], 'Show the file', lambda: self.open_folder(os.path.dirname(out)), C['grey'], self.f.h3,
                            height=self.f.s(40), width=self.f.s(150)).pack(side='left')
            else:
                w['title'].config(text='The disc was not patched', fg=C['red'])
                w['text'].config(text=err, fg=C['red'], font=self.f.h3)
            RoundButton(w['row'], 'OK', w['win'].destroy, C['accent'], self.f.h3, height=self.f.s(40), width=self.f.s(110)).pack(side='right')

    # -------------------------------------------------------------- Windows: no sleep while the server is on
    def _keep_awake(self, on):
        try:
            import ctypes
            ctypes.windll.kernel32.SetThreadExecutionState(0x80000000 | (0x00000001 if on else 0))
        except Exception:                                    # noqa: BLE001
            pass

    def on_close(self):
        if getattr(self, '_patching', False):
            messagebox.showinfo(TITLE, 'Please wait until the disc is finished.')
            return
        if self.busy:
            messagebox.showinfo(TITLE, 'Please wait a moment. The server is starting or stopping.')
            return
        if self.state and self.state.get('any'):
            ans = messagebox.askyesnocancel(TITLE, 'The server is still on.\n\nTurn it off before closing?\n\n'
                                                   'Yes = turn it off, then close\nNo = leave it on and close this window')
            if ans is None:
                return
            if ans:
                self.run_job('Stopping...', lambda say: sc.stop(say), done=lambda r, e: self.root.destroy())
                return
        self.root.destroy()


def main():
    root = tk.Tk()
    if not MAC:
        try:
            root.tk.call('tk', 'scaling', max(1.0, root.winfo_fpixels('1i') / 72.0))
        except tk.TclError:
            pass
    App(root)
    if '--selftest' in sys.argv:
        root.after(2500, root.destroy)
    root.mainloop()


if __name__ == '__main__':
    main()
