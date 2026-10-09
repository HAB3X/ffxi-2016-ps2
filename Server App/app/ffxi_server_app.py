#!/usr/bin/env python3
"""FFXI 2016 Server - the window that runs the server. Fan Project by Habex.

Python 3 + Tk (standard library only). Mac, Windows and Linux. Dark look only.
Left: navigation (Server, Profiles, Connect, World, Moderation, Chat rules, Maintenance, Game disc).
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
    import server_settings as ss
    import server_backup as sbk
    import server_notify as snt
    import server_debug as sd
    import server_ah as sah
    import server_modes as smo
    import server_pcsx2 as spc
except Exception:                                            # noqa: BLE001
    sc = sa = sn = sr = sch = ss = sbk = snt = sd = sah = smo = spc = None
    SC_ERROR = traceback.format_exc()

try:
    import ffxi_updater as up
except Exception:                                            # noqa: BLE001
    up = None

TITLE = 'FFXI 2016 Server (Fan Project by Habex)'
WINDOWS = os.name == 'nt'
MAC = sys.platform == 'darwin'

# ---------------------------------------------------------------- look (dark only, one accent colour)
C = dict(
    bg='#070b1c', nav='#060919', nav_bot='#0d0b26', nav_sel='#1b2762', nav_hov='#131c4a',
    card='#0e1633', card2='#152046', line='#222f63', input='#121c42', hover='#17224d',
    text='#eef2ff', soft='#a7b3d9', faint='#6f7ca8',
    accent='#6f8fff', accent_dk='#5373e6', gold='#f0cf7a',
    green='#3fd18d', green_dk='#23925f', green_bg='#0f2a29',
    red='#f0646b', red_dk='#a8404a', red_bg='#2c1530',
    amber='#efb85a', amber_bg='#2c2318', grey='#243060', sel='#2a3f86', zebra='#101a3d',
    blue='#6f8fff', purple='#6f8fff')
CHAT_COLORS = {'Say': '#eef2ff', 'Shout': '#ff9f5a', 'Yell': '#ffcf5a', 'Tell': '#c792ea', 'Party': '#62c9ff', 'LS': '#8ddf8d',
               'Server': '#6f8fff', 'info': '#a7b3d9', 'error': '#ff7b82', 'admin': '#6f8fff', 'event': '#6f7ca8'}


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


ART_DIR = os.path.join(APP_DIR, 'art')
_art_cache = {}


def art_image(name, size=None):
    """A picture from app/art. Pictures a player extracted from their own game disc (app/art/local) win over the ones that come with the app."""
    key = (name, size)
    if key in _art_cache:
        return _art_cache[key]
    base = '%s_%d.png' % (name, size) if size else '%s.png' % name
    img = None
    for d in (os.path.join(ART_DIR, 'local'), ART_DIR):
        p = os.path.join(d, base)
        if os.path.isfile(p):
            try:
                img = tk.PhotoImage(file=p)
                break
            except tk.TclError:
                img = None
    _art_cache[key] = img
    return img


def mask_corners(cv, w, h, r, color, tag='mask'):
    """Round the corners of a picture drawn on a canvas by covering each corner with the page colour."""
    import math
    for cx, cy, sx, sy in ((0, 0, 1, 1), (w, 0, -1, 1), (0, h, 1, -1), (w, h, -1, -1)):
        ox, oy = cx + sx * r, cy + sy * r
        pts = [cx, cy]
        for i in range(9):
            a = math.pi / 2 * i / 8
            pts += [ox - sx * r * math.sin(a), oy - sy * r * math.cos(a)]
        cv.create_polygon(pts, fill=color, outline='', tags=tag)


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


class TextLink(tk.Label):
    """A quiet clickable word: the minimal replacement for a small button."""

    def __init__(self, master, text, command, font, bg=None, fg=None):
        super().__init__(master, text=text, font=font, bg=bg or master['bg'], fg=fg or C['accent'], cursor='hand2')
        self.command, self.enabled, self.base_fg = command, True, fg or C['accent']
        self.bind('<Button-1>', lambda e: self.command() if self.enabled else None)

    def set_text(self, t):
        self.config(text=t)

    def set_enabled(self, on):
        self.enabled = bool(on)
        self.config(fg=self.base_fg if on else C['faint'], cursor='hand2' if on else '')


class RoundEntry(tk.Frame):
    """A text field with rounded corners, a fine border and a blue ring while you type. Behaves like a normal Entry (get, insert, delete, bind...)."""

    def __init__(self, master, font, width=22, show=''):
        super().__init__(master, bg=master['bg'], highlightthickness=0, bd=0)
        fnt = tkfont.Font(font=font)
        h = fnt.metrics('linespace') + 18
        self.cv = tk.Canvas(self, height=h, width=fnt.measure('0') * width + 30, bg=master['bg'], highlightthickness=0, bd=0)
        self.cv.pack(fill='x')
        self.entry = tk.Entry(self.cv, font=font, show=show, bg=C['input'], fg=C['text'], insertbackground=C['accent'], relief='flat', bd=0,
                              highlightthickness=0, disabledbackground=C['input'], disabledforeground=C['faint'], selectbackground=C['sel'],
                              selectforeground='white')
        self.win = self.cv.create_window(14, h // 2, window=self.entry, anchor='w', width=100)
        self.focused = False
        self.cv.bind('<Configure>', self._draw)
        self.entry.bind('<FocusIn>', lambda e: self._focus(True), add='+')
        self.entry.bind('<FocusOut>', lambda e: self._focus(False), add='+')
        self.cv.bind('<Button-1>', lambda e: self.entry.focus_set())

    def _focus(self, on):
        self.focused = on
        self._draw()

    def _draw(self, e=None):
        w, h = self.cv.winfo_width(), self.cv.winfo_height()
        if w < 8:
            return
        self.cv.delete('bg')
        rounded(self.cv, 1, 1, w - 1, h - 1, 10, fill=C['input'], outline=C['accent'] if self.focused else C['line'], width=2 if self.focused else 1, tags='bg')
        self.cv.tag_lower('bg')
        self.cv.itemconfigure(self.win, width=max(20, w - 30))

    def bind(self, sequence=None, func=None, add=None):
        return self.entry.bind(sequence, func, add)

    def focus_set(self):
        self.entry.focus_set()

    def configure(self, cnf=None, **kw):
        mine = {k: kw.pop(k) for k in ('state', 'show', 'textvariable') if k in kw}
        if mine:
            self.entry.configure(**mine)
        if kw or cnf:
            super().configure(cnf, **kw)

    config = configure

    def __getattr__(self, name):                               # get, insert, delete, icursor, selection_range ... go to the field itself
        if name in ('entry', 'cv'):
            raise AttributeError(name)
        return getattr(self.entry, name)


class Check(tk.Frame):
    """A checkbox: a rounded square that fills blue with a tick. Takes the same text, variable and command as a normal Checkbutton."""
    SIZE = 18

    def __init__(self, master, text='', variable=None, command=None, font=None, fg=None, bg=None, **ignored):
        bg = bg or master['bg']
        super().__init__(master, bg=bg, cursor='hand2', highlightthickness=0, bd=0)
        self.var = variable if variable is not None else tk.BooleanVar(value=False)
        self.command, self.hover, self.off = command, False, False
        self.box = tk.Canvas(self, width=self.SIZE + 2, height=self.SIZE + 2, bg=bg, highlightthickness=0, bd=0, cursor='hand2')
        self.box.pack(side='left')
        self.label = None
        if text:
            self.label = tk.Label(self, text=text, font=font, fg=fg or C['text'], bg=bg, anchor='w', cursor='hand2')
            self.label.pack(side='left', padx=(9, 0))
        for w in (self, self.box, self.label):
            if w is not None:
                w.bind('<Button-1>', self._toggle)
                w.bind('<Enter>', lambda e: self._hov(True))
                w.bind('<Leave>', lambda e: self._hov(False))
        self.var.trace_add('write', lambda *a: self._draw())
        self._draw()

    def _hov(self, on):
        self.hover = on
        self._draw()

    def _toggle(self, e=None):
        if self.off:
            return
        self.var.set(not bool(self.var.get()))
        if self.command:
            self.command()

    def configure(self, cnf=None, **kw):
        if 'state' in kw:
            self.off = kw.pop('state') == 'disabled'
            self._draw()
        if self.label is not None:
            look = {k: kw.pop(k) for k in ('text', 'font', 'fg') if k in kw}
            if look:
                self.label.configure(**look)
        for k in [k for k in kw if k not in ('bg', 'background', 'cursor')]:            # options only a real Checkbutton has: ignored
            kw.pop(k)
        if kw or cnf:
            super().configure(cnf, **kw)

    config = configure

    def _draw(self):
        c, s = self.box, self.SIZE
        c.delete('all')
        on = bool(self.var.get())
        if on:
            rounded(c, 1, 1, s + 1, s + 1, 6, fill=C['accent'] if not self.off else C['grey'], outline='')
            c.create_line(5, s // 2 + 1, s // 2 + 1, s - 3, s - 4, 6, fill='white', width=2, capstyle='round', joinstyle='round')
        else:
            rounded(c, 1, 1, s + 1, s + 1, 6, fill=C['input'], outline=C['accent'] if self.hover and not self.off else C['faint'], width=1)
        if self.label is not None:
            self.label.configure(fg=C['faint'] if self.off else (C['text']))


class Panel(tk.Frame):
    """A card: rounded corners, a fine border, roomy padding. `.body` is where the contents go; `.head` (titled cards) holds the title row.
    art=(name, offset) puts a soft picture inside the card, `offset` pixels from its right edge (behind the contents)."""
    RADIUS = 14
    INSET = 5

    def __init__(self, master, title=None, fonts=None, pad=20, icon=None, art=None):
        super().__init__(master, bg=master['bg'], highlightthickness=0, bd=0)
        self.edge = tk.Canvas(self, bg=master['bg'], highlightthickness=0, bd=0)       # the rounded border, behind everything
        self.edge.place(x=0, y=0, relwidth=1, relheight=1)
        self.edge.bind('<Configure>', self._draw_edge)
        self.inner = tk.Frame(self, bg=C['card'])
        self.inner.pack(fill='both', expand=True, padx=self.INSET, pady=self.INSET)
        if title:
            head = tk.Frame(self.inner, bg=C['card'])
            head.pack(fill='x', padx=pad, pady=(pad - 4, 8))
            pic = art_image(icon, 24) if icon else None
            if pic:
                lab = tk.Label(head, image=pic, bg=C['card'], bd=0)
                lab.image = pic
                lab.pack(side='left', padx=(0, 8))
            self.title = tk.Label(head, text=title, font=fonts.h2, bg=C['card'], fg=C['text'], anchor='w')
            self.title.pack(side='left')
            self.head = head
        self.body = tk.Frame(self.inner, bg=C['card'])
        self.body.pack(fill='both', expand=True, padx=pad, pady=(0 if title else pad, pad))
        if art and art_image(art[0]):
            pic = art_image(art[0])
            lab = tk.Label(self.body, image=pic, bg=C['card'], bd=0)                    # first child of the body: everything else sits on top of it
            lab.image = pic
            lab.place(relx=1.0, x=-art[1] + pad, rely=0.5, anchor='e')

    def _draw_edge(self, e):
        self.edge.delete('all')
        rounded(self.edge, 1, 1, e.width - 1, e.height - 1, self.RADIUS, fill=C['card'], outline=C['line'])


# ---------------------------------------------------------------- the window
class App:
    PAGES = [('server', 'Server'), ('profiles', 'Profiles'), ('connect', 'Connect'), ('settings', 'World'), ('roles', 'Moderation'),
             ('chat', 'Chat rules'), ('maint', 'Maintenance'), ('disc', 'Game disc')]

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
        self.root.after(8000, self._ddns_tick)
        self.root.after(10000, self._update_tick)
        self.root.after(20000, self._sched_loop)

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
        return RoundEntry(parent, self.f.body, width=width, show=show)

    def _scroll(self, parent, widget):
        sb = ttk.Scrollbar(parent, orient='vertical', command=widget.yview, style='Vertical.TScrollbar')
        widget.configure(yscrollcommand=sb.set)
        return sb

    # -------------------------------------------------------------- layout
    def _build(self):
        f, r = self.f, self.root
        nav = tk.Canvas(r, bg=C['nav_bot'], width=f.s(236), highlightthickness=0, bd=0)
        nav.pack(side='left', fill='y')
        self.nav = nav
        bgimg = art_image('nav_bg')
        if bgimg:
            nav.create_image(0, 0, image=bgimg, anchor='nw')
        logo = art_image('crystal', 32)
        if logo:
            nav.create_image(f.s(36), f.s(50), image=logo)
        nav.create_text(f.s(62), f.s(40), text='FFXI 2016', anchor='w', font=f.title, fill=C['text'])
        nav.create_text(f.s(62), f.s(66), text='Server', anchor='w', font=f.h2, fill=C['gold'])
        nav.create_text(f.s(26), f.s(100), text='Fan Project by Habex', anchor='w', font=f.small, fill=C['accent'])
        self.nav_y, self.nav_hot, self.nav_half = {}, None, f.s(21)
        icons = {'server': 'server', 'profiles': 'moogle', 'connect': 'chocobo', 'settings': 'world', 'roles': 'shield', 'chat': 'chat',
                 'maint': 'potion', 'disc': 'disc'}
        for i, (key, label) in enumerate(self.PAGES):
            y = f.s(152) + i * f.s(46)
            self.nav_y[key] = y
            rounded(nav, f.s(12), y - self.nav_half, f.s(224), y + self.nav_half, f.s(11), fill='', outline='', tags=('pill_' + key,))
            nav.create_rectangle(f.s(12), y - f.s(11), f.s(15), y + f.s(11), fill='', outline='', tags=('bar_' + key,))
            pic = art_image(icons.get(key, 'crystal'), 24)
            if pic:
                nav.create_image(f.s(38), y, image=pic)
            nav.create_text(f.s(62), y, text=label, anchor='w', font=f.nav, fill=C['soft'], tags=('txt_' + key,))
        nav.bind('<Motion>', self._nav_motion)
        nav.bind('<Leave>', lambda e: self._nav_set_hot(None))
        nav.bind('<Button-1>', self._nav_click)
        nav.config(cursor='arrow')
        self.nav_pill = Pill(nav, f)
        self.auto_link = TextLink(nav, '', self.toggle_auto_update, f.tiny, bg=C['nav_bot'], fg=C['soft'])
        self._nav_win_pill = nav.create_window(f.s(24), 0, window=self.nav_pill, anchor='sw')
        self._nav_win_auto = nav.create_window(f.s(24), 0, window=self.auto_link, anchor='sw')
        nav.bind('<Configure>', self._nav_layout)
        self._show_auto_link()

        self.content = tk.Frame(r, bg=C['bg'])
        self.content.pack(side='left', fill='both', expand=True)
        self.upd_bar = tk.Frame(self.content, bg=C['card2'])
        self._build_server()
        self._build_profiles()
        self._build_connect()
        self._build_disc()
        self.show_page('server')

    # ---- updates: look on GitHub for newer scripts, offer them or fetch them in the background
    def _auto_update_on(self):
        try:
            return bool(sc.load_config().get('auto_update', False))
        except Exception:                                    # noqa: BLE001
            return False

    def _show_auto_link(self):
        self.auto_link.set_text('Auto update: %s' % ('on' if self._auto_update_on() else 'off'))

    def toggle_auto_update(self):
        try:
            cfg = sc.load_config()
            cfg['auto_update'] = not bool(cfg.get('auto_update', False))
            sc.save_config(cfg)
        except Exception:                                    # noqa: BLE001
            return
        self._show_auto_link()
        if cfg['auto_update']:
            self._update_tick(now=True)
        else:
            self._hide_update_bar()

    def _hide_update_bar(self):
        self.upd_bar.pack_forget()

    def _update_bar(self, text, buttons=(), color=None):
        f = self.f
        for w in self.upd_bar.winfo_children():
            w.destroy()
        row = tk.Frame(self.upd_bar, bg=C['card2'])
        row.pack(fill='x', padx=28, pady=10)
        self.L(row, text, f.small, fg=color or C['text'], bg=C['card2']).pack(side='left')
        for label, cmd, col in reversed(buttons):
            RoundButton(row, label, cmd, col, f.small, height=f.s(32), width=f.s(max(90, 9 * len(label) + 24)), radius=9, bg=C['card2']).pack(side='right', padx=(8, 0))
        if not self.upd_bar.winfo_ismapped():
            kids = self.content.pack_slaves()
            if kids:
                self.upd_bar.pack(side='top', fill='x', before=kids[0])
            else:
                self.upd_bar.pack(side='top', fill='x')

    def _update_tick(self, now=False):
        if up is None or sc is None or getattr(self, '_upd_busy', False):
            if not now:
                self.root.after(6 * 3600 * 1000, self._update_tick)
            return
        self._upd_busy = True

        def work():
            try:
                info = up.check(RELEASE)
            except Exception:                                # noqa: BLE001
                info = None                                  # offline or GitHub is busy: try again later
            self.root.after(0, lambda: self._update_found(info))
        threading.Thread(target=work, daemon=True).start()
        if not now:
            self.root.after(6 * 3600 * 1000, self._update_tick)

    def _update_found(self, info):
        self._upd_busy = False
        if not info:
            return
        self.upd_info = info
        if self._auto_update_on():
            self.update_now()
            return
        n = len(info['files'])
        self._update_bar('A new version is available (%d file%s).' % (n, '' if n == 1 else 's'),
                         [('Update now', self.update_now, C['accent']),
                          ('Always update automatically', lambda: (self.toggle_auto_update() if not self._auto_update_on() else None), C['grey']),
                          ('Not now', self._hide_update_bar, C['grey'])])

    def update_now(self):
        info = getattr(self, 'upd_info', None)
        if not info or getattr(self, '_upd_busy', False):
            return
        self._upd_busy = True
        self._update_bar('Downloading the new version in the background...')

        def work():
            err = None
            try:
                up.apply(RELEASE, info)
            except Exception as e:                           # noqa: BLE001
                err = e
            self.root.after(0, lambda: self._update_done(err))
        threading.Thread(target=work, daemon=True).start()

    def _update_done(self, err):
        self._upd_busy = False
        if err:
            self._update_bar('The update did not work (%s). It will be tried again later.' % err, [('OK', self._hide_update_bar, C['grey'])], C['red'])
            return
        self.upd_info = None
        self._update_bar('Updated. Close this window and open the server again to use the new version.', [('OK', self._hide_update_bar, C['grey'])], C['green'])

    def _nav_layout(self, e):
        self.nav.coords(self._nav_win_pill, self.f.s(24), e.height - self.f.s(22))
        self.nav.coords(self._nav_win_auto, self.f.s(24), e.height - self.f.s(66))

    def _nav_key_at(self, y):
        for k, cy in self.nav_y.items():
            if abs(y - cy) <= self.nav_half:
                return k
        return None

    def _nav_motion(self, e):
        k = self._nav_key_at(e.y) if e.x < self.f.s(228) else None
        self._nav_set_hot(k)

    def _nav_set_hot(self, key):
        if key != self.nav_hot:
            self.nav_hot = key
            self.nav.config(cursor='hand2' if key else 'arrow')
            self._nav_paint()

    def _nav_click(self, e):
        k = self._nav_key_at(e.y) if e.x < self.f.s(228) else None
        if k:
            self.show_page(k)

    def _nav_paint(self):
        for k in self.nav_y:
            on, hot = k == self.page, k == self.nav_hot
            self.nav.itemconfigure('pill_' + k, fill=C['nav_sel'] if on else (C['nav_hov'] if hot else ''))
            self.nav.itemconfigure('bar_' + k, fill=C['accent'] if on else '')
            self.nav.itemconfigure('txt_' + k, fill=C['text'] if (on or hot) else C['soft'], font=self.f.nav_b if on else self.f.nav)

    def show_page(self, key):
        if key == 'roles' and 'roles' not in self.pages:
            self.pages['roles'] = self._page_frame('Moderation', 'Who may use which in-game "!" commands. Right-click a player to promote them.')
            import ffxi_app_extra as X
            self.roles_page = X.RolesWindow(self, parent=self.pages['roles'].body)
        if key == 'chat' and 'chat' not in self.pages:
            self.pages['chat'] = self._page_frame('Chat rules', 'Word filter, spam limit, scheduled messages and the chat history.')
            import ffxi_app_extra as X
            self.chat_page = X.ChatRulesWindow(self, parent=self.pages['chat'].body)
        if key == 'maint' and 'maint' not in self.pages:
            self._build_maintenance()
        if key == 'settings':
            if 'settings' not in self.pages:
                self._build_settings()
            else:
                self._load_settings()
        for k, fr in self.pages.items():
            if k != key:
                fr.pack_forget()
        self.pages[key].pack(fill='both', expand=True)
        self.page = key
        if key == 'settings' and getattr(self, 'set_name', None):
            self.root.after(50, lambda: (self.set_name.focus_set(), self.set_name.icursor('end')))
        self._nav_paint()

    PAGE_ICONS = {'Profiles': 'moogle', 'Connect': 'chocobo', 'World': 'world', 'Moderation': 'shield', 'Chat rules': 'chat', 'Maintenance': 'potion',
                  'Game disc': 'disc'}

    def _page_frame(self, title, sub=None):
        fr = tk.Frame(self.content, bg=C['bg'])
        head = tk.Frame(fr, bg=C['bg'])
        head.pack(fill='x', padx=28, pady=(24, 14))
        f = self.f
        banner = tk.Canvas(head, height=f.s(104), bg=C['bg'], highlightthickness=0, bd=0)
        banner.pack(fill='x')
        art = art_image('banner_bg')
        pic = art_image(self.PAGE_ICONS.get(title, 'crystal'), 64)

        def draw(e):
            w, h = e.width, e.height
            banner.delete('all')
            rounded(banner, 1, 1, w - 1, h - 1, 14, fill=C['card'], outline=C['line'])
            if art:
                banner.create_image(1, 1, image=art, anchor='nw')
                mask_corners(banner, w, h, 14, C['bg'])
                rounded(banner, 1, 1, w - 1, h - 1, 14, fill='', outline=C['line'])
            x = f.s(28)
            if pic:
                banner.create_image(x + 32, h // 2, image=pic)
                x += 84
            banner.create_text(x, h // 2 - (f.s(12) if sub else 0), text=title, anchor='w', font=f.h1, fill=C['text'])
            if sub:
                banner.create_text(x, h // 2 + f.s(16), text=sub, anchor='w', font=f.small, fill=C['soft'], width=max(100, w - x - f.s(30)))
        banner.bind('<Configure>', draw)
        fr.head = head
        fr.body = tk.Frame(fr, bg=C['bg'])
        fr.body.pack(fill='both', expand=True, padx=28, pady=(0, 24))
        return fr

    # ---- Server page
    def _build_server(self):
        f = self.f
        page = tk.Frame(self.content, bg=C['bg'])
        self.pages['server'] = page
        hero = Panel(page, None, f, pad=24, art=('hero_mid', f.s(210)))
        hero.pack(fill='x', padx=28, pady=(24, 14))
        hb = hero.body
        left = tk.Frame(hb, bg=C['card'])
        left.pack(side='left', fill='y')
        srow = tk.Frame(left, bg=C['card'])
        srow.pack(anchor='w')
        self.status_dot = tk.Canvas(srow, width=f.s(18), height=f.s(18), bg=C['card'], highlightthickness=0)
        self.status_dot.pack(side='left', padx=(0, 10))
        self.status_text = self.L(srow, 'Server is off', f.status, bg=C['card'])
        self.status_text.pack(side='left')
        self.step = self.L(left, '', f.body, fg=C['soft'], bg=C['card'], anchor='w', justify='left')
        self.step.pack(fill='x', pady=(6, 0))
        self.parts = self.L(left, '', f.tiny, fg=C['faint'], bg=C['card'], anchor='w', justify='left')   # kept for the status code, not shown
        wrow = tk.Frame(left, bg=C['card'])
        self.wrow = wrow                                   # shown only while something is running

        self.work_icon = self.L(wrow, '●', f.h3, fg=C['faint'], bg=C['card'])
        self.work_icon.pack(side='left', anchor='n')
        wcol = tk.Frame(wrow, bg=C['card'])
        wcol.pack(side='left', fill='x', expand=True, padx=(8, 0))
        self.work_title = self.L(wcol, 'Is it working?', f.h3, bg=C['card'], anchor='w')
        self.work_title.pack(fill='x')
        self.work_text = self.L(wcol, '', f.small, fg=C['soft'], bg=C['card'], anchor='w', justify='left')
        self.work_text.pack(fill='x')
        right = tk.Frame(hb, bg=C['card'])
        right.pack(side='right', padx=(24, 0))
        brow = tk.Frame(right, bg=C['card'])
        brow.pack()
        self.brow = brow
        self.start_btn = RoundButton(brow, 'Start', self.do_start, C['green_dk'], f.bigbtn, height=f.s(58), width=f.s(150), radius=14)
        self.stop_btn = RoundButton(brow, 'Stop', self.do_stop, C['grey'], f.bigbtn, height=f.s(58), width=f.s(150), radius=14)
        self.start_btn.pack(side='left')

        ab = tk.Frame(page, bg=C['bg'])
        ab.pack(fill='x', padx=32, pady=(0, 16))
        ab.grid_columnconfigure(4, weight=1)
        try:
            self.hide_ips = bool(sc.load_config().get('hide_ips', True))      # hidden on the first start, then remembered
        except Exception:                                                     # noqa: BLE001
            self.hide_ips = True
        self.L(ab, 'Local', f.small, fg=C['faint'], bg=C['bg'], width=8, anchor='w').grid(row=0, column=0, sticky='w')
        self.ip_val = self.L(ab, '...', f.mono, bg=C['bg'])
        self.ip_val.grid(row=0, column=1, sticky='w', padx=(4, 12))
        self.copy_btn = TextLink(ab, 'copy', lambda: self.copy_ip('lan'), f.tiny, bg=C['bg'])
        self.copy_btn.grid(row=0, column=2, sticky='w')
        self.L(ab, 'Internet', f.small, fg=C['faint'], bg=C['bg'], width=8, anchor='w').grid(row=1, column=0, sticky='w', pady=(4, 0))
        self.net_val = self.L(ab, '...', f.mono, bg=C['bg'])
        self.net_val.grid(row=1, column=1, sticky='w', padx=(4, 12), pady=(4, 0))
        self.copy_net = TextLink(ab, 'copy', lambda: self.copy_ip('net'), f.tiny, bg=C['bg'])
        self.copy_net.grid(row=1, column=2, sticky='w', pady=(4, 0))
        self.L(ab, 'Port', f.small, fg=C['faint'], bg=C['bg'], width=8, anchor='w').grid(row=2, column=0, sticky='w', pady=(4, 0))
        self.L(ab, str(sc.SERVER_PORT_FOR_PLAYERS) if sc else '54001', f.mono, bg=C['bg']).grid(row=2, column=1, sticky='w', padx=(4, 12), pady=(4, 0))
        self.hide_btn = TextLink(ab, 'show' if self.hide_ips else 'hide', self.toggle_hide, f.tiny, bg=C['bg'], fg=C['soft'])
        self.hide_btn.grid(row=0, column=4, sticky='e')
        how = TextLink(ab, 'how to connect', lambda: self.show_page('connect'), f.tiny, bg=C['bg'])
        how.grid(row=1, column=4, sticky='e', pady=(4, 0))
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
        onl = Panel(low, 'Online now', f, icon='moogle')
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
        self.player_actions = TextLink(onl.body, 'Actions for the selected player', self.open_player_actions, f.small, bg=C['card'])
        self.player_actions.pack(side='bottom', anchor='w', pady=(8, 0))
        self.online.bind('<<TreeviewSelect>>', lambda e: self.player_actions.set_enabled(bool(self.online.selection())))
        self.player_actions.set_enabled(False)

        chat = Panel(low, 'World chat', f, icon='chat')
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
        self.hdd_note = self.L(p2.body, '', f.body, fg=C['soft'], bg=C['card'], anchor='w', justify='left')
        self.hdd_note.pack(fill='x', pady=(8, 0))
        p3 = Panel(page.body, None, f, pad=24)
        p3.pack(fill='x', pady=(16, 0))
        self.L(p3.body, '3.  Try it in PCSX2', f.h3, bg=C['card'], anchor='w').pack(fill='x')
        self.L(p3.body, 'Starts PCSX2 with the patched disc. The hard drive must already be chosen once in PCSX2\'s settings (step 2). '
               'The first start installs the game, which takes a while.', f.body, fg=C['soft'], bg=C['card'], anchor='w',
               justify='left').pack(fill='x', pady=(4, 0))
        prow = tk.Frame(p3.body, bg=C['card'])
        prow.pack(fill='x', pady=(12, 0))
        self.pcsx2_btn = RoundButton(prow, 'Test in PCSX2', self.do_pcsx2, C['accent'], f.btn, height=f.s(46), width=f.s(200), radius=12, bg=C['card'])
        self.pcsx2_btn.pack(side='left')
        TextLink(prow, 'Choose PCSX2...', self.choose_pcsx2, f.small, bg=C['card']).pack(side='left', padx=20)
        self.pcsx2_note = self.L(p3.body, '', f.body, fg=C['soft'], bg=C['card'], anchor='w', justify='left')
        self.pcsx2_note.pack(fill='x', pady=(8, 0))
        rl = tk.Frame(p3.body, bg=C['card'])
        rl.pack(fill='x', pady=(10, 0))
        self.L(rl, 'Using a real PS2 instead?', f.small, fg=C['faint'], bg=C['card']).pack(side='left')
        TextLink(rl, 'Open the real PS2 guide', lambda: self._open_path(os.path.join(DISC_DIR, 'READ ME real PS2.txt')), f.small,
                 bg=C['card']).pack(side='left', padx=10)
        for w in p.body.winfo_children() + p2.body.winfo_children() + p3.body.winfo_children():
            if isinstance(w, tk.Label):
                w.master.bind('<Configure>', lambda e, w=w: self._wrap(w, e.width), add='+')

    def _pcsx2_say(self, text, color=None):
        self.pcsx2_note.config(text=text, fg=color or C['soft'])

    def do_pcsx2(self, picked=False):
        try:
            cmd = spc.launch()
        except spc.NeedProgram:
            if picked or not self.choose_pcsx2(start=True):
                self._pcsx2_say('PCSX2 was not found. Use "Choose PCSX2..." to pick it once.', C['amber'])
            return
        except Exception as e:                               # noqa: BLE001
            self._pcsx2_say(str(e), C['red'])
            return
        self._pcsx2_say('PCSX2 is starting with the patched disc. If it asks for a hard drive, finish step 2 first.', C['green'])

    def choose_pcsx2(self, start=False):
        if MAC:
            path = filedialog.askdirectory(parent=self.root, title='Pick the PCSX2 app', initialdir='/Applications', mustexist=True)
        elif WINDOWS:
            path = filedialog.askopenfilename(parent=self.root, title='Pick PCSX2', filetypes=[('Programs', '*.exe')])
        else:
            path = filedialog.askopenfilename(parent=self.root, title='Pick PCSX2')
        if not path:
            return False
        try:
            spc.remember(path)
        except Exception as e:                               # noqa: BLE001
            self._pcsx2_say(str(e), C['red'])
            return True
        self._pcsx2_say('Remembered. Press "Test in PCSX2".', C['green'])
        if start:
            self.do_pcsx2(picked=True)
        return True

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
        if getattr(self, '_hdd_busy', False):
            return
        self._hdd_busy = True
        self.hdd_note.configure(text='Making the hard drive. This can take a few minutes on some drives. Keep this window open.')

        def work():
            err = None
            try:
                mod.make(out)
            except Exception as e:                           # noqa: BLE001
                err = e
            self.root.after(0, lambda: done(err))

        def done(err):
            self._hdd_busy = False
            self.hdd_note.configure(text='')
            if err:
                messagebox.showerror(TITLE, 'The hard drive could not be made: %s' % err)
                return
            messagebox.showinfo(TITLE, 'Your PS2 hard drive is ready:\n\n%s\n\n'
                                'Now in PCSX2: Settings > Network & HDD > Hard Disk Drive. Tick "Enabled", click "Browse" next to '
                                'HDD File and pick this file. Don\'t click "Create".' % out)
        threading.Thread(target=work, daemon=True).start()

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

    def _sync_buttons(self, st):
        want = (not st['on'], bool(st['any']))                   # show Start when it is not fully on, Stop when anything runs
        if want == getattr(self, '_btn_want', None):
            return
        self._btn_want = want
        self.start_btn.pack_forget()
        self.stop_btn.pack_forget()
        if want[0]:
            self.start_btn.pack(side='left', padx=(0, 10) if want[1] else 0)
        if want[1]:
            self.stop_btn.pack(side='left')

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
        if st['on'] and not getattr(self, 'on_since', None):
            self.on_since = time.time()
        elif not st['on']:
            self.on_since = None
        if 'checks' in s:
            bad = [t for ok, t in s['checks'] if not ok]
            self.setup_ok = not bad
            if bad:
                self.setup_list.config(text='One-time setup needed: ' + '; '.join(bad) + '.')
                if not self.setup_card.winfo_ismapped():
                    self.setup_card.grid(row=5, column=0, columnspan=5, sticky='ew', pady=(14, 0))
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
            self._sync_buttons(st)
            self.profile_btn.set_enabled(self.setup_ok)
        ip = s['ip']
        self.addr['lan'] = ip or ''
        if 'public' in s:
            self.addr['net'] = s['public'][0] or ''
        if 'ts' in s:
            self.addr['ts'] = s['ts']
        self._show_ip()
        self._refresh_connect()
        if self.last_ip and ip and ip != self.last_ip:
            self.chat_add('error', 'This computer\'s home address changed from %s to %s.' % (self.mask(self.last_ip), self.mask(ip)))
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
            self.map_restarts = getattr(self, 'map_restarts', 0) + 1
            self._notify('The map server stopped and was started again.')
            self.run_job('Restarting the map...', lambda say: sc.restart_map_if_down(say))
        self.root.after(5000, self.watch_map)

    def do_start(self):
        self.run_job('Starting...', lambda say: sc.start(say), done=lambda r, e: (not e) and (self.chat_add('admin', 'The server is on.'), self._notify('The server is on.')))

    def do_stop(self):
        if self.state and self.state.get('on'):
            if not messagebox.askyesno(TITLE, 'Stop the server?\n\nAnyone playing right now will be disconnected.'):
                return
        self.run_job('Stopping...', lambda say: sc.stop(say), done=lambda r, e: (not e) and (self.chat_add('admin', 'The server is off.'), self._notify('The server is off.')))

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

    def _hide_in(self, text):
        if not self.hide_ips:
            return text
        for v in (self.addr.get('lan'), self.addr.get('net'), self.addr.get('ts')):
            if v:
                text = text.replace(v, '\u2022' * 10)
        return text

    def mask(self, v):
        return ('\u2022' * 10) if (self.hide_ips and v) else v

    def toggle_hide(self):
        self.hide_ips = not self.hide_ips
        self.hide_btn.set_text('show' if self.hide_ips else 'hide')
        try:
            cfg = sc.load_config()
            cfg['hide_ips'] = self.hide_ips
            sc.save_config(cfg)
        except Exception as e:                                                # noqa: BLE001
            self.chat_add('error', 'Could not remember the Hide IPs choice: %s' % e)
        self._show_ip()
        self._refresh_connect()
        if getattr(self, '_work_raw', None) is not None:
            self.work_text.config(text=self._hide_in(self._work_raw))

    def _show_ip(self):
        lan, net = self.addr['lan'], self.addr['net']
        self.ip_val.config(text=self.mask(lan) or 'not on a network', fg=C['text'] if lan else C['red'], font=self.f.mono if lan else self.f.body)
        self.net_val.config(text=self.mask(net) or 'not found', fg=C['text'] if net else C['faint'], font=self.f.mono if net else self.f.body)
        self.copy_btn.set_enabled(bool(lan))
        self.copy_net.set_enabled(bool(net))
        if sn:
            self.ports_text.config(text='Forward %s to %s on your router.' % (
                ', '.join('%s %d' % (pr, po) for pr, po, _ in sn.FORWARD), self.mask(lan) or 'this computer'))

    def copy_ip(self, which='lan'):
        ip = self.addr[which]
        btn = self.copy_net if which == 'net' else self.copy_btn
        if ip:
            self.root.clipboard_clear()
            self.root.clipboard_append(ip)
            btn.set_text('Copied')
            self.root.after(1500, lambda: btn.set_text('Copy'))

    def check_now(self):
        if not sn:
            return
        self.checking = True
        self.last_check = time.time()
        self.check_seq = getattr(self, 'check_seq', 0) + 1
        seq = self.check_seq
        self.work_title.config(text='Checking...', fg=C['amber'])
        self.work_icon.config(fg=C['amber'])
        def work():
            try:
                res = sn.check_working()
            except Exception as e:                           # noqa: BLE001
                res = ('unsure', 'Could not check', str(e))
            self.q.put(('work', res, seq))
        threading.Thread(target=work, daemon=True).start()

    def _show_work(self, res):
        self.checking = False
        state, head, text = res
        if self.state and not self.state.get('any'):                 # nothing is running: the status line already says so
            self.wrow.pack_forget()
        elif not self.wrow.winfo_ismapped():
            self.wrow.pack(fill='x', pady=(10, 0))
        col = {'ok': C['green'], 'bad': C['red'], 'unsure': C['amber']}[state]
        self.work_icon.config(fg=col)
        self.work_title.config(text=head, fg=col)
        self._work_raw = text
        self.work_text.config(text=self._hide_in(text), fg=C['soft'])

    def change_public(self):
        cur = sc.load_config().get('internet_ip_manual', '')
        v = self.ask('Internet address', 'Your home\'s internet address (the router\'s status page shows it) or a dynamic DNS name like myhome.ddns.net. Players type the same thing on the PS2 Server IP line. '
                     'Leave it empty to look it up again.', initial=cur)
        if v is None and not cur:
            return

        def work():
            try:
                sn.set_manual_public_address(v or '')
                self.q.put(('chat', 'admin', 'Internet address: %s' % (self.mask(sn.public_address()[0]) or 'not found')))
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
        Check(form, text='Show password', variable=showvar, command=toggle, bg=C['bg'], fg=C['soft'], font=self.f.small,
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

    # ---- How to connect page (all three ways work at the same time: the server gives each console the address it dialled)
    def _build_connect(self):
        f = self.f
        page = self._page_frame('Connect', 'What players type on the PS2 sign-in page.')
        self.pages['connect'] = page
        import ffxi_app_extra as X
        scroll = X.Scrolled(page.body, C['bg'])
        scroll.pack(fill='both', expand=True)
        body = scroll.inner
        port = str(sc.SERVER_PORT_FOR_PLAYERS) if sc else '54001'
        intro = self.L(body, 'POL-ID and Password come from a profile (Profiles page). Server Port is %s. Leave EtherIP, SubnetMask, BlodeCast and Gateway empty.' % port, f.small, fg=C['soft'], justify='left', anchor='w')
        intro.pack(fill='x', pady=(0, 12), padx=(0, 16))
        body.bind('<Configure>', lambda e: self._wrap(intro, e.width - 16), add='+')
        self.conn_ip = {}

        def section(key, title, lines, extra=None):
            p = Panel(body, title, f)
            p.pack(fill='x', pady=(0, 12), padx=(0, 16))
            row = tk.Frame(p.body, bg=C['card'])
            row.pack(fill='x')
            self.L(row, 'ServerIP', f.small, fg=C['soft'], bg=C['card']).pack(side='left')
            self.conn_ip[key] = self.L(row, '...', f.mono, fg=C['green'], bg=C['card'])
            self.conn_ip[key].pack(side='left', padx=(12, 0))
            if extra:
                extra(row)
            t = self.L(p.body, lines, f.small, fg=C['soft'], bg=C['card'], anchor='w', justify='left')
            t.pack(fill='x', pady=(8, 0))
            p.body.bind('<Configure>', lambda e, w=t: self._wrap(w, e.width - 8), add='+')
            return p

        section('lan', 'Local',
                'PS2 and this computer on the same router. No internet needed. If it will not connect, allow the server through this '
                'computer\'s firewall and turn off client isolation on the router.')
        section('direct', 'Direct cable',
                'PS2 cabled straight to this computer, no router. Set this computer\'s Ethernet to a manual address: IP 192.168.137.1, mask 255.255.255.0, no gateway.\n'
                'Windows: Settings > Network & internet > Ethernet > IP assignment > Edit > Manual.\n'
                'Mac: System Settings > Network > Ethernet > Details > TCP/IP > Configure IPv4: Manually.\n'
                'Linux: nmcli connection modify <name> ipv4.method manual ipv4.addresses 192.168.137.1/24\n'
                'The PS2 waits about 25 seconds for a router, then uses 192.168.137.2 by itself.')
        net_panel = section('net', 'Over the internet',
                'Players type a hostname so it keeps working when your home address changes. Set one up here (DuckDNS, No-IP, Dynu, any provider, '
                'or just type one). Your router has to forward the ports below to this computer. Behind a shared internet connection (CGNAT) forwarding '
                'cannot work: use a cloud server (Server/setup/CLOUD.txt).',
                extra=lambda row: RoundButton(row, 'Hostname', self.setup_ddns, C['grey'], f.small, height=f.s(32), width=f.s(120),
                                              radius=9, bg=C['card']).pack(side='left', padx=14))
        self._build_ports(net_panel.body)
        self.ddns_status = self.L(body, '', f.small, fg=C['faint'], anchor='w', justify='left')
        self.ddns_status.pack(fill='x', pady=(0, 12))
        self._refresh_connect()

    # ---- World page: name and welcome, rates, monsters, rules and scheduled events (small tabs, one panel at a time)
    WORLD_TABS = [('general', 'General'), ('rates', 'Rates'), ('monsters', 'Monsters'), ('rules', 'Rules'), ('events', 'Events'),
                  ('ah', 'Auction house'), ('modes', 'Modes')]
    WORLD_NOTES = {
        'rates': '1 is normal and 2 is double, from 0.1 to 10. A change applies within a few seconds, with no restart.',
        'monsters': 'Scales monsters as they spawn, so monsters that are already out keep their old values until they respawn.',
        'rules': 'Levels, and which expansions are open. Zones that are already loaded use the new rules after the next server start.',
    }

    def _build_settings(self):
        f = self.f
        page = self._page_frame('World', 'The name players see, rates, monsters and rules.')
        self.pages['settings'] = page
        self.world_bar = Segmented(page.body, self.WORLD_TABS, self._world_tab, f.small, height=f.s(38))
        self.world_bar.pack(fill='x', pady=(0, 14))
        self.world_panels = {k: Panel(page.body, None, f, pad=26) for k, _ in self.WORLD_TABS}
        self.world_entries, self.world_flags, self.world_msg = {}, {}, {}
        self.world_built = set()
        self.world_tab = None
        self._world_tab('general')

    def _world_tab(self, key):
        """Show one tab. Its contents are made the first time it is shown, once the panel is on screen (entry boxes made while a panel is
        hidden do not paint on macOS)."""
        for k, p in self.world_panels.items():
            p.pack_forget()
        panel = self.world_panels[key]
        panel.pack(fill='x')
        self.world_bar.set(key)
        self.world_tab = key
        if key not in self.world_built:
            self.world_built.add(key)
            if key == 'general':
                self._build_world_general(panel.body)
            elif key == 'events':
                self._build_world_events(panel.body)
            elif key == 'ah':
                self._build_world_ah(panel.body)
            elif key == 'modes':
                self._build_world_modes(panel.body)
            else:
                self._build_world_numbers(key, panel.body)
            self._load_settings()
        self.root.update_idletasks()

    def _save_row(self, parent, group):
        f = self.f
        row = tk.Frame(parent, bg=C['card'])
        row.pack(fill='x', pady=(24, 0))
        RoundButton(row, 'Save', lambda: self.save_world(group), C['accent'], f.h3, height=f.s(40), width=f.s(110), radius=10, bg=C['card']).pack(side='left')
        self.world_msg[group] = self.L(row, '', f.small, fg=C['soft'], bg=C['card'], anchor='w')
        self.world_msg[group].pack(side='left', padx=16)

    def _build_world_general(self, b):
        f = self.f
        self.L(b, 'Name', f.small, fg=C['faint'], bg=C['card'], anchor='w').pack(fill='x')
        self.set_name = self.entry(b, width=30)
        self.set_name.pack(fill='x', pady=(4, 0), ipady=f.s(7))
        self.L(b, 'Shown when players pick a world. Letters, numbers, spaces and dashes, 15 at most. Applies after the next server start.',
               f.tiny, fg=C['faint'], bg=C['card'], anchor='w').pack(fill='x', pady=(4, 0))
        self.L(b, 'Welcome message', f.small, fg=C['faint'], bg=C['card'], anchor='w').pack(fill='x', pady=(22, 0))
        self.set_welcome = self.entry(b, width=60)
        self.set_welcome.pack(fill='x', pady=(4, 0), ipady=f.s(7))
        self.L(b, 'Sent only to the player who just logged in. {player} becomes their name and {server} your world name. Leave it empty for none.',
               f.tiny, fg=C['faint'], bg=C['card'], anchor='w').pack(fill='x', pady=(4, 0))
        self._save_row(b, 'general')
        for e in (self.set_name, self.set_welcome):
            e.bind('<Return>', lambda ev: self.save_world('general'))

    def _build_world_numbers(self, group, b):
        f = self.f
        grid = tk.Frame(b, bg=C['card'])
        grid.pack(fill='x')
        numbers = [st for st in ss.GROUPS[group] if st.kind != 'flag'] if ss else []
        flags = [st for st in ss.GROUPS[group] if st.kind == 'flag'] if ss else []
        for i, st in enumerate(numbers):
            cell = tk.Frame(grid, bg=C['card'])
            cell.grid(row=i // 4, column=i % 4, sticky='w', padx=(0, 28), pady=(0, 14))
            self.L(cell, st.label, f.tiny, fg=C['soft'], bg=C['card'], anchor='w').pack(fill='x')
            e = self.entry(cell, width=9)
            e.pack(ipady=f.s(6), pady=(3, 0), anchor='w')
            e.bind('<Return>', lambda ev, g=group: self.save_world(g))
            self.world_entries[st.key] = e
        if flags:
            self.L(b, 'Open to players', f.small, fg=C['faint'], bg=C['card'], anchor='w').pack(fill='x', pady=(10, 4))
            fg = tk.Frame(b, bg=C['card'])
            fg.pack(fill='x')
            for i, st in enumerate(flags):
                var = tk.BooleanVar(value=True)
                self.world_flags[st.key] = var
                Check(fg, text=st.label, variable=var, bg=C['card'], fg=C['text'], font=f.small, anchor='w', activebackground=C['card'],
                               activeforeground=C['text'], selectcolor=C['input'], highlightthickness=0, bd=0).grid(
                    row=i // 3, column=i % 3, sticky='w', padx=(0, 26), pady=2)
        self.L(b, self.WORLD_NOTES[group], f.tiny, fg=C['faint'], bg=C['card'], anchor='w', justify='left').pack(fill='x', pady=(10, 0))
        self._save_row(b, group)

    def _build_world_events(self, b):
        f = self.f
        self.L(b, 'Events switch rates on and off by the clock, for example double experience on weekend evenings. '
                  'They run while this window is open.', f.tiny, fg=C['faint'], bg=C['card'], anchor='w', justify='left').pack(fill='x')
        self.events_list = tk.Frame(b, bg=C['card'])
        self.events_list.pack(fill='x', pady=(10, 0))
        row = tk.Frame(b, bg=C['card'])
        row.pack(fill='x', pady=(14, 0))
        RoundButton(row, 'Add an event', self.add_event, C['accent'], f.h3, height=f.s(40), width=f.s(150), radius=10, bg=C['card']).pack(side='left')
        self.world_msg['events'] = self.L(row, '', f.small, fg=C['soft'], bg=C['card'], anchor='w')
        self.world_msg['events'].pack(side='left', padx=16)

    # ---- Auction house tab: stock it with items so a small server is not empty
    def _check(self, parent, text, var, command=None):
        f = self.f
        return Check(parent, text=text, variable=var, command=command, bg=C['card'], fg=C['text'], font=f.small, anchor='w', activebackground=C['card'],
                     activeforeground=C['text'], selectcolor=C['input'], highlightthickness=0, bd=0)

    def _build_world_ah(self, b):
        f = self.f
        opt = sah.settings() if sah else {}
        self.L(b, 'A new server has an empty auction house. This puts ordinary items on sale, sold by a server character called "%s", so players '
                  'have something to buy. Players\' own listings are never touched.' % (sah.SELLER_NAME if sah else ''),
               f.tiny, fg=C['faint'], bg=C['card'], anchor='w', justify='left').pack(fill='x')
        self._wrap_later(b)
        self.L(b, 'What to sell', f.small, fg=C['faint'], bg=C['card'], anchor='w').pack(fill='x', pady=(14, 4))
        g = tk.Frame(b, bg=C['card'])
        g.pack(fill='x')
        self.ah_groups = {}
        for i, (key, label, _) in enumerate(sah.GROUPS if sah else []):
            var = tk.BooleanVar(value=key in opt.get('groups', []))
            self.ah_groups[key] = var
            self._check(g, label, var).grid(row=i // 2, column=i % 2, sticky='w', padx=(0, 40), pady=2)
        r = tk.Frame(b, bg=C['card'])
        r.pack(fill='x', pady=(16, 0))
        self.L(r, 'Listings of each item', f.small, fg=C['soft'], bg=C['card']).pack(side='left')
        self.ah_per = self.entry(r, width=4)
        self.ah_per.insert(0, str(opt.get('per_item', 2)))
        self.ah_per.pack(side='left', padx=(8, 26), ipady=f.s(4))
        self.L(r, 'Price', f.small, fg=C['soft'], bg=C['card']).pack(side='left')
        self.ah_pct = self.entry(r, width=5)
        self.ah_pct.insert(0, str(opt.get('percent', 100)))
        self.ah_pct.pack(side='left', padx=(8, 6), ipady=f.s(4))
        self.L(r, '% of the normal price', f.small, fg=C['soft'], bg=C['card']).pack(side='left', padx=(0, 26))
        self.ah_stacks = tk.BooleanVar(value=opt.get('stacks', True))
        self._check(r, 'Also sell full stacks', self.ah_stacks).pack(side='left')
        self.L(b, 'Normal price is about twice what a shop pays for the item. The lowest allowed is %d%%, so nobody can make gil by buying here and '
                  'selling to a shop.' % (sah.MIN_PERCENT if sah else 50), f.tiny, fg=C['faint'], bg=C['card'], anchor='w',
               justify='left').pack(fill='x', pady=(6, 0))
        self.L(b, 'Put items back on sale', f.small, fg=C['faint'], bg=C['card'], anchor='w').pack(fill='x', pady=(16, 4))
        self.ah_refill = Segmented(b, [(k, l) for k, l, _ in (sah.REFILLS if sah else [])], self._ah_refill_set, f.small, height=f.s(36))
        self.ah_refill.pack(fill='x')
        self.ah_refill.set(opt.get('refill', 'off'))
        self.ah_refill_key = opt.get('refill', 'off')
        self.L(b, 'Automatic refills run while this window is open and the server is on. Anything bought gets replaced, and prices follow the '
                  'setting above. Pressing the button again never doubles the listings.', f.tiny, fg=C['faint'], bg=C['card'], anchor='w',
               justify='left').pack(fill='x', pady=(6, 0))
        row = tk.Frame(b, bg=C['card'])
        row.pack(fill='x', pady=(20, 0))
        self.ah_btn = RoundButton(row, 'Stock the auction house', self.do_ah_stock, C['accent'], f.h3, height=f.s(40), width=f.s(230), radius=10, bg=C['card'])
        self.ah_btn.pack(side='left')
        TextLink(row, 'Remove the server\'s listings', self.do_ah_clear, f.small, bg=C['card']).pack(side='left', padx=22)
        TextLink(row, 'Save the options only', self.do_ah_save, f.small, bg=C['card']).pack(side='left')
        self.ah_msg = self.L(b, '', f.small, fg=C['soft'], bg=C['card'], anchor='w', justify='left')
        self.ah_msg.pack(fill='x', pady=(10, 0))
        self._wrap_later(b)

    def _wrap_later(self, parent):
        """Long grey notes in a card wrap to the card's width as it is resized."""
        def fit(e):
            for w in parent.winfo_children():
                if isinstance(w, tk.Label) and str(w.cget('justify')) == 'left':
                    self._wrap(w, e.width)
        parent.bind('<Configure>', fit, add='+')

    def _ah_refill_set(self, key):
        self.ah_refill_key = key
        self.ah_refill.set(key)

    def _ah_opts(self):
        return {'groups': [k for k, v in self.ah_groups.items() if v.get()], 'per_item': self.ah_per.get(), 'percent': self.ah_pct.get(),
                'stacks': self.ah_stacks.get(), 'refill': self.ah_refill_key}

    def _ah_say(self, text, color=None):
        self.ah_msg.config(text=text, fg=color or C['soft'])

    def _ah_job(self, label, fn):
        if getattr(self, '_ah_busy', False):
            return
        if not (self.state and self.state.get('database')):
            self._ah_say('Start the server first: the auction house lives in its database.', C['amber'])
            return
        self._ah_busy = True
        self.ah_btn.set_enabled(False)
        self._ah_say(label, C['amber'])

        def work():
            try:
                msg, col = fn(), C['green']
            except Exception as e:                           # noqa: BLE001
                msg, col = str(e), C['red']

            def done():
                self._ah_busy = False
                self.ah_btn.set_enabled(True)
                self._ah_say(msg, col)
            self.root.after(0, done)
        threading.Thread(target=work, daemon=True).start()

    def do_ah_save(self):
        try:
            sah.save_settings(self._ah_opts())
            self._ah_say('Saved.', C['green'])
        except Exception as e:                               # noqa: BLE001
            self._ah_say(str(e), C['red'])

    def do_ah_stock(self):
        try:
            opts = sah.save_settings(self._ah_opts())
        except Exception as e:                               # noqa: BLE001
            self._ah_say(str(e), C['red'])
            return

        def fn():
            r = sah.stock(opts)
            return 'Done: %d new listings added (%d for sale now, %d kinds of items).' % (r['added'], r['open'], r['items'])
        self._ah_job('Putting items on sale...', fn)

    def do_ah_clear(self):
        if not messagebox.askyesno(TITLE, 'Remove every listing the server put up?\n\nListings from players are not touched.'):
            return
        self._ah_job('Removing...', lambda: 'Removed %d listings.' % sah.clear())

    # ---- Modes tab: plain on/off switches
    def _build_world_modes(self, b):
        f = self.f
        self.L(b, 'Small changes to how the game plays, from LoxleyXI\'s open source modules (credited in Server/lsb/modules). All are off until '
                  'you switch them on. Each one applies the next time the server starts, so after changing one use Stop and then Start on '
                  'the Server page.', f.tiny, fg=C['faint'], bg=C['card'], anchor='w', justify='left').pack(fill='x')
        self._wrap_later(b)
        self.mode_vars = {}
        st = smo.states() if smo else {}
        for key, kind, label, text in (smo.MODES if smo else []):
            row = tk.Frame(b, bg=C['card'])
            row.pack(fill='x', pady=(16, 0))
            var = tk.BooleanVar(value=st.get(key, False))
            self.mode_vars[key] = var
            self._check(row, label, var, lambda k=key: self.toggle_mode(k)).pack(anchor='w')
            lab = self.L(row, text, f.tiny, fg=C['soft'], bg=C['card'], anchor='w', justify='left')
            lab.pack(fill='x', padx=(32, 0), pady=(2, 0))
            row.bind('<Configure>', lambda e, w=lab: self._wrap(w, e.width - 32), add='+')
        self.mode_msg = self.L(b, '', f.small, fg=C['soft'], bg=C['card'], anchor='w', justify='left')
        self.mode_msg.pack(fill='x', pady=(18, 0))

    def toggle_mode(self, key):
        want = self.mode_vars[key].get()
        self.mode_msg.config(text='Working...', fg=C['amber'])

        def work():
            try:
                msg, col, ok = smo.set_enabled(key, want), C['green'], True
            except Exception as e:                           # noqa: BLE001
                msg, col, ok = str(e), C['red'], False

            def done():
                if not ok:
                    self.mode_vars[key].set(not want)
                running = bool(self.state and self.state.get('any'))
                self.mode_msg.config(text=msg + (' The server is on now: restart it.' if ok and running else ''), fg=col)
            self.root.after(0, done)
        threading.Thread(target=work, daemon=True).start()

    def _load_settings(self):
        if not ss or not getattr(self, 'set_name', None):
            return
        cur = ss.get()
        for e, v in ((self.set_name, cur['name']), (self.set_welcome, cur['welcome'])):
            e.delete(0, 'end')
            e.insert(0, v)
        for g in ('rates', 'monsters', 'rules'):
            try:
                vals = ss.get_values(g)
            except Exception:                                # noqa: BLE001
                continue
            for k, v in vals.items():
                if k in self.world_entries:
                    self.world_entries[k].delete(0, 'end')
                    self.world_entries[k].insert(0, '%g' % v)
                elif k in self.world_flags:
                    self.world_flags[k].set(bool(v))
        self._show_events()

    def _world_say(self, group, text, color):
        self.world_msg[group].config(text=text, fg=color)

    def save_world(self, group):
        running = bool(self.state and self.state.get('any'))
        self._world_say(group, 'Saving...', C['amber'])
        if group == 'general':
            name, welcome = self.set_name.get(), self.set_welcome.get()
        else:
            values = {st.key: (self.world_flags[st.key].get() if st.kind == 'flag' else self.world_entries[st.key].get()) for st in ss.GROUPS[group]}

        def work():
            try:
                if group == 'general':
                    changed = ss.save(name=name, welcome=welcome)
                    msg = 'Saved.' + (' Restart the server for the new name to show.' if changed and running else '')
                else:
                    changed = ss.save_values(group, values)
                    msg = 'Saved.' + (' The server picks it up in a few seconds.' if changed and running and group != 'rules' else '')
                    if changed and running and group == 'rules':
                        msg = 'Saved. Restart the server for it to apply everywhere.'
                self.root.after(0, lambda: self._world_say(group, msg, C['green']))
            except Exception as e:                           # noqa: BLE001
                self.root.after(0, lambda e=e: self._world_say(group, str(e), C['red']))
        threading.Thread(target=work, daemon=True).start()

    def save_settings(self):
        self.save_world('general')

    # ---- scheduled events
    def _show_events(self):
        if not getattr(self, 'events_list', None):
            return
        f = self.f
        for w in self.events_list.winfo_children():
            w.destroy()
        events = ss.list_events() if ss else []
        active = ss._state().get('active') if ss else None
        if not events:
            self.L(self.events_list, 'No events yet.', f.small, fg=C['soft'], bg=C['card'], anchor='w').pack(fill='x')
        for ev in events:
            r = tk.Frame(self.events_list, bg=C['card2'])
            r.pack(fill='x', pady=3)
            var = tk.BooleanVar(value=bool(ev.get('on', True)))
            Check(r, variable=var, command=lambda e=ev, v=var: self._event_toggle(e, v), bg=C['card2'], activebackground=C['card2'],
                           selectcolor=C['input'], highlightthickness=0, bd=0).pack(side='left', padx=(10, 0), pady=8)
            txt = tk.Frame(r, bg=C['card2'])
            txt.pack(side='left', fill='x', expand=True, padx=8)
            self.L(txt, ev['name'] + ('   (on now)' if ev['id'] == active else ''), f.small, fg=C['green'] if ev['id'] == active else C['text'],
                   bg=C['card2'], anchor='w').pack(fill='x')
            self.L(txt, ss.event_text(ev), f.tiny, fg=C['soft'], bg=C['card2'], anchor='w').pack(fill='x')
            TextLink(r, 'Remove', lambda e=ev: self._event_remove(e), f.small, bg=C['card2']).pack(side='right', padx=14)

    def _event_toggle(self, ev, var):
        events = ss.list_events()
        for e in events:
            if e['id'] == ev['id']:
                e['on'] = bool(var.get())
        try:
            ss.save_events(events)
            self._sched_now()
        except Exception as e:                               # noqa: BLE001
            self._world_say('events', str(e), C['red'])

    def _event_remove(self, ev):
        ss.save_events([e for e in ss.list_events() if e['id'] != ev['id']])
        self._show_events()
        self._sched_now()

    def add_event(self):
        f = self.f
        d = tk.Toplevel(self.root)
        d.title('New event')
        d.configure(bg=C['bg'])
        d.transient(self.root)
        body = tk.Frame(d, bg=C['bg'])
        body.pack(fill='both', expand=True, padx=26, pady=22)
        self.L(body, 'Event name', f.small, fg=C['faint'], bg=C['bg'], anchor='w').pack(fill='x')
        name = self.entry(body, width=34)
        name.pack(fill='x', pady=(4, 14), ipady=f.s(6))
        self.L(body, 'Days', f.small, fg=C['faint'], bg=C['bg'], anchor='w').pack(fill='x')
        drow = tk.Frame(body, bg=C['bg'])
        drow.pack(fill='x', pady=(4, 14))
        dvars = []
        for i, dn in enumerate(ss.DAY_NAMES):
            v = tk.BooleanVar(value=i >= 5)
            dvars.append(v)
            Check(drow, text=dn, variable=v, bg=C['bg'], fg=C['text'], font=f.small, activebackground=C['bg'], activeforeground=C['text'],
                           selectcolor=C['input'], highlightthickness=0, bd=0).pack(side='left', padx=(0, 10))
        trow = tk.Frame(body, bg=C['bg'])
        trow.pack(fill='x', pady=(0, 14))
        times = []
        for label, default in (('From', '18:00'), ('Until', '23:00')):
            c = tk.Frame(trow, bg=C['bg'])
            c.pack(side='left', padx=(0, 22))
            self.L(c, label, f.small, fg=C['faint'], bg=C['bg'], anchor='w').pack(fill='x')
            e = self.entry(c, width=8)
            e.insert(0, default)
            e.pack(ipady=f.s(6), pady=(4, 0))
            times.append(e)
        self.L(body, 'Rates during the event (1 = normal)', f.small, fg=C['faint'], bg=C['bg'], anchor='w').pack(fill='x')
        rrow = tk.Frame(body, bg=C['bg'])
        rrow.pack(fill='x', pady=(4, 6))
        rates = {}
        for st in ss.GROUPS['rates'][:4]:
            c = tk.Frame(rrow, bg=C['bg'])
            c.pack(side='left', padx=(0, 18))
            self.L(c, st.label, f.tiny, fg=C['soft'], bg=C['bg'], anchor='w').pack(fill='x')
            e = self.entry(c, width=7)
            e.insert(0, '2' if st.key == 'EXP_RATE' else '1')
            e.pack(ipady=f.s(6), pady=(3, 0))
            rates[st.key] = e
        msg = self.L(body, '', f.small, fg=C['red'], bg=C['bg'], anchor='w', justify='left')
        msg.pack(fill='x', pady=(8, 0))

        def save():
            ev = {'name': name.get(), 'days': [i for i, v in enumerate(dvars) if v.get()], 'start': times[0].get().strip(), 'end': times[1].get().strip(),
                  'mult': {k: e.get() for k, e in rates.items()}}
            try:
                events = ss.list_events()
                events.append(ev)
                ss.save_events(events)
            except Exception as e:                           # noqa: BLE001
                msg.config(text=str(e))
                return
            d.destroy()
            self._show_events()
            self._sched_now()
        brow = tk.Frame(body, bg=C['bg'])
        brow.pack(fill='x', pady=(14, 0))
        RoundButton(brow, 'Add', save, C['accent'], f.h3, height=f.s(40), width=f.s(110), radius=10, bg=C['bg']).pack(side='left')
        TextLink(brow, 'Cancel', d.destroy, f.small, bg=C['bg']).pack(side='left', padx=18)
        d.update_idletasks()
        d.geometry('+%d+%d' % (self.root.winfo_rootx() + 140, self.root.winfo_rooty() + 90))
        name.focus_set()

    # ---- clock jobs: scheduled events and the daily backup (checked every half minute while the window is open)
    def _sched_now(self):
        self.root.after(200, self._sched_run)

    def _sched_loop(self):
        self._sched_run()
        self.root.after(30000, self._sched_loop)

    def _sched_run(self):
        if getattr(self, '_sched_busy', False) or not ss:
            return
        self._sched_busy = True

        def work():
            msg = err = bk = None
            try:
                msg = ss.tick_events()
            except Exception as e:                           # noqa: BLE001
                err = str(e)
            try:
                if sbk and self.state and self.state.get('database') and not self.busy and sbk.auto_due():
                    sbk.auto_backup()
                    bk = 'Automatic backup done.'
            except Exception as e:                           # noqa: BLE001
                err = err or str(e)
            try:
                if sah and self.state and self.state.get('database') and not self.busy and not getattr(self, '_ah_busy', False) and sah.refill_due():
                    r = sah.stock()
                    if r['added']:
                        bk = (bk + ' ' if bk else '') + 'Auction house restocked (%d listings).' % r['added']
            except Exception as e:                           # noqa: BLE001
                err = err or str(e)
            self.root.after(0, lambda: self._sched_done(msg, bk, err))
        threading.Thread(target=work, daemon=True).start()

    def _sched_done(self, msg, bk, err):
        self._sched_busy = False
        if msg:
            self.chat_add('admin', msg)
            self._notify(msg)
            self._show_events()
        if bk:
            self.chat_add('admin', bk)
            if getattr(self, 'backup_note', None):
                self._show_backup_note()
        if err:
            self.chat_add('error', 'Scheduled job: ' + err)

    def _notify(self, text):
        if not snt:
            return
        if snt.webhook():
            threading.Thread(target=lambda: snt.send(text), daemon=True).start()

    # ---- Maintenance page: backups, Discord messages and a quick health check
    def _build_maintenance(self):
        f = self.f
        page = self._page_frame('Maintenance', 'Backups, messages to a Discord channel, how the server is doing, and a readable log.')
        self.pages['maint'] = page
        self.maint_bar = Segmented(page.body, [('general', 'General'), ('debug', 'Debug')], self._maint_tab, f.small, height=f.s(38))
        self.maint_bar.pack(fill='x', pady=(0, 14))
        gen = tk.Frame(page.body, bg=C['bg'])
        self.maint_frames = {'general': gen, 'debug': tk.Frame(page.body, bg=C['bg'])}
        bp = Panel(gen, None, f, pad=26)
        bp.pack(fill='x')
        self.L(bp.body, 'Backups', f.small, fg=C['faint'], bg=C['card'], anchor='w').pack(fill='x')
        self.backup_note = self.L(bp.body, '', f.small, fg=C['soft'], bg=C['card'], anchor='w', justify='left')
        self.backup_note.pack(fill='x', pady=(6, 0))
        brow = tk.Frame(bp.body, bg=C['card'])
        brow.pack(fill='x', pady=(14, 0))
        self.backup_btn = RoundButton(brow, 'Back up now', self.do_backup, C['grey'], f.small, height=f.s(36), width=f.s(140), radius=10, bg=C['card'])
        self.backup_btn.pack(side='left')
        TextLink(brow, 'Restore from a backup...', self.do_restore, f.small, bg=C['card']).pack(side='left', padx=20)
        arow = tk.Frame(bp.body, bg=C['card'])
        arow.pack(fill='x', pady=(16, 0))
        on, keep = sbk.auto_settings() if sbk else (False, 7)
        self.auto_var = tk.BooleanVar(value=on)
        Check(arow, text='Back up every day while the server is on', variable=self.auto_var, command=self._save_auto, bg=C['card'], fg=C['text'],
                       font=f.small, activebackground=C['card'], activeforeground=C['text'], selectcolor=C['input'], highlightthickness=0, bd=0).pack(side='left')
        self.L(arow, 'Keep', f.small, fg=C['soft'], bg=C['card']).pack(side='left', padx=(22, 6))
        self.keep_entry = self.entry(arow, width=4)
        self.keep_entry.insert(0, str(keep))
        self.keep_entry.pack(side='left', ipady=f.s(4))
        self.keep_entry.bind('<FocusOut>', lambda e: self._save_auto())
        self.keep_entry.bind('<Return>', lambda e: self._save_auto())
        self.L(arow, 'automatic backups', f.small, fg=C['soft'], bg=C['card']).pack(side='left', padx=(6, 0))

        dp = Panel(gen, None, f, pad=26)
        dp.pack(fill='x', pady=(14, 0))
        self.L(dp.body, 'Discord', f.small, fg=C['faint'], bg=C['card'], anchor='w').pack(fill='x')
        self.L(dp.body, 'Posts a line to a channel when the server starts, stops, restarts after a problem, or a scheduled event begins or ends. '
                        'In Discord: channel settings > Integrations > Webhooks > Copy Webhook URL.', f.tiny, fg=C['faint'], bg=C['card'], anchor='w',
               justify='left').pack(fill='x', pady=(4, 8))
        self.hook_entry = self.entry(dp.body, show='•', width=50)
        self.hook_entry.pack(fill='x', ipady=f.s(7))
        if snt:
            self.hook_entry.insert(0, snt.webhook())
        drow = tk.Frame(dp.body, bg=C['card'])
        drow.pack(fill='x', pady=(12, 0))
        RoundButton(drow, 'Save', self.save_hook, C['grey'], f.small, height=f.s(36), width=f.s(110), radius=10, bg=C['card']).pack(side='left')
        TextLink(drow, 'Send a test message', self.test_hook, f.small, bg=C['card']).pack(side='left', padx=20)
        self.hook_msg = self.L(drow, '', f.small, fg=C['soft'], bg=C['card'], anchor='w')
        self.hook_msg.pack(side='left')

        hp = Panel(gen, None, f, pad=26)
        hp.pack(fill='x', pady=(14, 0))
        self.L(hp.body, 'Health', f.small, fg=C['faint'], bg=C['card'], anchor='w').pack(fill='x')
        self.health_text = self.L(hp.body, '', f.small, fg=C['text'], bg=C['card'], anchor='w', justify='left')
        self.health_text.pack(fill='x', pady=(6, 0))
        TextLink(hp.body, 'Open the logs folder', lambda: self._open_path(sc.LOGS), f.small, bg=C['card']).pack(anchor='w', pady=(10, 0))
        self._show_backup_note()
        self._show_health()
        self._build_debug(self.maint_frames['debug'])
        self._maint_tab('general')

    def _maint_tab(self, key):
        for k, fr in self.maint_frames.items():
            fr.pack_forget()
        self.maint_frames[key].pack(fill='both', expand=True)
        self.maint_bar.set(key)
        self.debug_on = key == 'debug'
        if self.debug_on:
            self._debug_refresh()

    # ---- Debug: the PS2 login part's log, readable
    def _build_debug(self, parent):
        f = self.f
        p = Panel(parent, None, f, pad=26)
        p.pack(fill='both', expand=True)
        self.L(p.body, 'Packet log', f.small, fg=C['faint'], bg=C['card'], anchor='w').pack(fill='x')
        self.L(p.body, 'What the PS2 login part has been doing, newest at the bottom. Use it when something does not work and you want to see what '
                       'the game and the server said to each other. It shows the last %d lines and refreshes by itself.' % (sd.LINES if sd else 300),
               f.tiny, fg=C['faint'], bg=C['card'], anchor='w', justify='left').pack(fill='x', pady=(4, 10))
        self.debug_filter = 'all'
        self.debug_bar = Segmented(p.body, sd.FILTERS if sd else [('all', 'All')], self._debug_set, f.small, height=f.s(36))
        self.debug_bar.pack(fill='x')
        self.debug_bar.set('all')
        box = tk.Frame(p.body, bg=C['input'], highlightthickness=1, highlightbackground=C['line'])
        box.pack(fill='both', expand=True, pady=(12, 0))
        self.debug_text = tk.Text(box, height=12, bg=C['input'], fg=C['text'], insertbackground=C['text'], relief='flat', bd=0, wrap='none',
                                  font=f.mono_s, padx=10, pady=8, highlightthickness=0, state='disabled')
        sb = self._scroll(box, self.debug_text)
        sb.pack(side='right', fill='y')
        self.debug_text.pack(side='left', fill='both', expand=True)
        row = tk.Frame(p.body, bg=C['card'])
        row.pack(fill='x', pady=(12, 0))
        RoundButton(row, 'Copy', self._debug_copy, C['grey'], f.small, height=f.s(36), width=f.s(110), radius=10, bg=C['card']).pack(side='left')
        self.debug_msg = self.L(row, '', f.small, fg=C['soft'], bg=C['card'], anchor='w')
        self.debug_msg.pack(side='left', padx=16)
        self._wrap_later(p.body)
        self._debug_last = None

    def _debug_set(self, key):
        self.debug_filter = key
        self.debug_bar.set(key)
        self._debug_last = None
        self._debug_refresh(once=True)

    def _debug_refresh(self, once=False):
        if not getattr(self, 'debug_text', None) or not sd or not getattr(self, 'debug_on', False):
            return
        mode = self.debug_filter

        def work():
            text = sd.view(mode)
            self.root.after(0, lambda: self._debug_show(text, mode))
        threading.Thread(target=work, daemon=True).start()
        if not once and not getattr(self, '_debug_timer', False):
            self._debug_timer = True
            self.root.after(2000, self._debug_tick)

    def _debug_tick(self):
        self._debug_timer = False
        if getattr(self, 'debug_on', False) and self.page == 'maint':
            self._debug_refresh()

    def _debug_show(self, text, mode):
        if not sd.exists():
            text = ''
            self.debug_msg.config(text='No log yet. It appears once the server has been started.', fg=C['soft'])
        elif not text:
            self.debug_msg.config(text='Nothing in the log matches this filter yet.', fg=C['soft'])
        else:
            self.debug_msg.config(text='', fg=C['soft'])
        if text == self._debug_last or mode != self.debug_filter:
            return
        self._debug_last = text
        t = self.debug_text
        at_end = t.yview()[1] >= 0.99
        t.config(state='normal')
        t.delete('1.0', 'end')
        t.insert('1.0', text)
        t.config(state='disabled')
        if at_end:
            t.see('end')

    def _debug_copy(self):
        text = self.debug_text.get('1.0', 'end').strip()
        self.root.clipboard_clear()
        self.root.clipboard_append(text)
        self.debug_msg.config(text='Copied %d lines.' % len(text.splitlines()) if text else 'Nothing to copy.', fg=C['green'] if text else C['soft'])

    def _save_auto(self):
        if not sbk:
            return
        try:
            keep = int(self.keep_entry.get())
        except ValueError:
            keep = 7
        keep = max(1, min(60, keep))
        self.keep_entry.delete(0, 'end')
        self.keep_entry.insert(0, str(keep))
        sbk.save_auto_settings(self.auto_var.get(), keep)
        if self.auto_var.get():
            self._sched_now()

    def save_hook(self):
        try:
            snt.save_webhook(self.hook_entry.get())
            self.hook_msg.config(text='Saved.', fg=C['green'])
        except Exception as e:                               # noqa: BLE001
            self.hook_msg.config(text=str(e), fg=C['red'])

    def test_hook(self):
        url = self.hook_entry.get().strip()
        try:
            snt.save_webhook(url)
        except Exception as e:                               # noqa: BLE001
            self.hook_msg.config(text=str(e), fg=C['red'])
            return
        self.hook_msg.config(text='Sending...', fg=C['amber'])

        def work():
            ok, why = snt.send('Test message from the FFXI 2016 Server app.', url)
            self.root.after(0, lambda: self.hook_msg.config(text='Sent. Check the channel.' if ok else why, fg=C['green'] if ok else C['red']))
        threading.Thread(target=work, daemon=True).start()

    def _show_health(self):
        if not getattr(self, 'health_text', None):
            return
        st = self.state
        if st and st.get('on') and getattr(self, 'on_since', None):
            mins = int((time.time() - self.on_since) // 60)
            up = 'The server has been on for %s.' % ('%d h %d min' % (mins // 60, mins % 60) if mins >= 60 else '%d min' % mins)
        elif st and st.get('any'):
            up = 'The server is partly on.'
        else:
            up = 'The server is off.'
        n = len(self.members) if getattr(self, 'members', None) else 0
        lines = [up, '%d player%s online.' % (n, '' if n == 1 else 's')]
        if getattr(self, 'map_restarts', 0):
            lines.append('The map server restarted by itself %d time%s since this window opened.' % (self.map_restarts, '' if self.map_restarts == 1 else 's'))
        self.health_text.config(text='  '.join(lines))
        self.root.after(10000, self._show_health)

    def _open_path(self, path):
        try:
            if WINDOWS:
                os.startfile(path)                           # noqa: S606
            else:
                subprocess.Popen(['open' if MAC else 'xdg-open', path])
        except Exception:                                    # noqa: BLE001
            messagebox.showinfo(TITLE, path)

    def _show_backup_note(self):
        last = sbk.listing() if sbk else []
        self.backup_note.config(text=('Last backup: %s.' % time.strftime('%d %b %Y, %H:%M', time.localtime(last[0][2]))) if last
                                else 'No backup yet. A backup saves every player and character.')

    def do_backup(self):
        self.backup_btn.set_enabled(False)
        self.backup_note.config(text='Backing up...', fg=C['amber'])

        def work():
            try:
                path = sbk.create()
                msg, col = 'Saved %s' % os.path.basename(path), C['green']
            except Exception as e:                           # noqa: BLE001
                msg, col = str(e), C['red']

            def done():
                self.backup_btn.set_enabled(True)
                self._show_backup_note()
                if col == C['red']:
                    self.backup_note.config(text=msg, fg=col)
                else:
                    self.backup_note.config(fg=C['soft'])
                    self.chat_add('admin', msg)
            self.root.after(0, done)
        threading.Thread(target=work, daemon=True).start()

    def do_restore(self):
        if self.state and self.state.get('xi_map'):
            messagebox.showinfo(TITLE, 'Stop the server first, then restore.')
            return
        os.makedirs(sbk.BACKUPS, exist_ok=True)
        path = filedialog.askopenfilename(title='Pick a backup', initialdir=sbk.BACKUPS, filetypes=[('Backups', '*.sql.gz'), ('All files', '*')])
        if not path:
            return
        if not messagebox.askyesno(TITLE, 'Replace every player and character with this backup?\n\n%s\n\nThe data you have now is saved as a backup first.' % os.path.basename(path)):
            return
        self.backup_note.config(text='Restoring...', fg=C['amber'])

        def work():
            try:
                safety = sbk.restore(path)
                msg, ok = 'Restored. The data from before is saved as %s.' % os.path.basename(safety), True
            except Exception as e:                           # noqa: BLE001
                msg, ok = str(e), False
            self.root.after(0, lambda: (self.backup_note.config(text=msg, fg=C['soft'] if ok else C['red']), ok and self.chat_add('admin', msg)))
        threading.Thread(target=work, daemon=True).start()

    def _build_ports(self, parent):
        f = self.f
        self.ports_text = self.L(parent, '', f.small, fg=C['soft'], bg=C['card'], anchor='w', justify='left')
        self.ports_text.pack(fill='x', pady=(12, 0))
        prow = tk.Frame(parent, bg=C['card'])
        prow.pack(fill='x', pady=(6, 0))
        self.upnp_btn = TextLink(prow, 'Open ports for me', self.do_open_ports, f.small, bg=C['card'])
        self.upnp_btn.pack(side='left')
        self.test_btn = TextLink(prow, 'Test my ports', self.do_test_ports, f.small, bg=C['card'])
        self.test_btn.pack(side='left', padx=20)
        self.net_status = self.L(parent, '', f.small, fg=C['soft'], bg=C['card'], anchor='w', justify='left')
        self.net_status.pack(fill='x', pady=(8, 0))
        self.help_text = self.L(parent, '', f.small)              # not shown; the code that fills the address text still sets it
        for w in (self.ports_text, self.net_status):
            parent.bind('<Configure>', lambda e, w=w: self._wrap(w, e.width - 8), add='+')

    def _refresh_connect(self):
        if not getattr(self, 'conn_ip', None):
            return
        self._show_ddns()
        lan = self.addr.get('lan') or ''
        net = self.addr.get('net') or ''
        for key, val, empty in (('lan', lan, 'this computer is not on a network'), ('direct', '192.168.137.1', ''),
                                ('net', net, 'not found: use "Set hostname"')):
            self.conn_ip[key].config(text=(self.mask(val) if key != 'direct' else val) or empty, fg=C['green'] if val else C['amber'])

    # ---- dynamic DNS: keeps a hostname pointing at this home while the app is open
    def setup_ddns(self):
        cur = sn.ddns_config() if sn else {}
        f = self.f
        d, box = self.dialog('Hostname updates')
        self.L(box, 'Hostname', f.h1).pack(anchor='w')
        self.L(box, 'Players type this instead of your home address. With a provider picked, this app tells it your new address whenever it changes '
                    '(every 5 minutes while the app is open).',
               f.small, fg=C['soft'], justify='left', wraplength=f.s(480)).pack(anchor='w', pady=(6, 12))
        kinds = [('manual', 'Manual'), ('duckdns', 'DuckDNS'), ('noip', 'No-IP'), ('dynu', 'Dynu'), ('other', 'Other')]
        manual_val = sc.load_config().get('internet_ip_manual', '') if sc else ''
        state = {'kind': cur.get('kind') or ('manual' if manual_val else 'duckdns')}
        form = tk.Frame(box, bg=C['bg'])
        rows = {}        # field -> (label, entry, extra widgets)
        spec = {'manual': ['host'], 'duckdns': ['name', 'token'], 'noip': ['host', 'user', 'password'], 'dynu': ['host', 'user', 'password'], 'other': ['host', 'url']}
        names = {'name': 'Name', 'token': 'Token', 'host': 'Hostname', 'user': 'Username', 'password': 'Password', 'url': 'Update link'}
        secret = ('token', 'password', 'url')
        for i, key in enumerate(('name', 'token', 'host', 'user', 'password', 'url')):
            lab = self.L(form, names[key], f.h3, anchor='w')
            ent = self.entry(form, show='\u2022' if key in secret else '', width=30)
            lab.grid(row=i, column=0, sticky='w', pady=(8, 0), padx=(0, 14))
            ent.grid(row=i, column=1, sticky='we', pady=(8, 0), ipady=f.s(6))
            val = cur.get(key, '') if cur.get('kind') == state['kind'] else (manual_val if key == 'host' and state['kind'] == 'manual' else '')
            if val:
                ent.insert(0, val)
            rows[key] = (lab, ent)
        suffix = self.L(form, '.duckdns.org', f.small, fg=C['soft'])
        hint = self.L(box, '', f.tiny, fg=C['faint'], justify='left', wraplength=f.s(480))
        hints = {'manual': 'Type the address or hostname players should use. Nothing is updated for you, so use this when your router keeps a name up to date, or you have a fixed internet address.',
                 'duckdns': 'Make a free account at duckdns.org, add a name there, and copy the token from the top of the page.',
                 'noip': 'Use the hostname you made at noip.com and your No-IP login.',
                 'dynu': 'Use the hostname you made at dynu.com and your Dynu login.',
                 'other': 'Most providers show an "update link" (sometimes called a dynamic update URL). Paste it here. Write {host} where the name goes if it asks for one.'}

        def show(kind):
            state['kind'] = kind
            seg.set(kind)
            for key, (lab, ent) in rows.items():
                if key in spec[kind]:
                    lab.grid()
                    ent.grid()
                else:
                    lab.grid_remove()
                    ent.grid_remove()
            if kind == 'duckdns':
                suffix.grid(row=0, column=2, sticky='w', padx=6)
            else:
                suffix.grid_remove()
            hint.config(text=hints[kind])
            msg.config(text='')
        seg = Segmented(box, kinds, show, f.small, height=f.s(34))
        seg.pack(fill='x', pady=(0, 6))
        form.pack(fill='x')
        hint.pack(anchor='w', pady=(10, 0))
        msg = self.L(box, '', f.small, fg=C['red'], justify='left', wraplength=f.s(480))
        msg.pack(anchor='w', pady=(8, 0))
        row = tk.Frame(box, bg=C['bg'])
        row.pack(fill='x', pady=(14, 0))

        def done(res):
            if isinstance(res, Exception):
                msg.config(text=str(res), fg=C['red'])
                save.set_enabled(True)
                return
            self.chat_add('admin', 'Hostname saved. Players type %s' % self.mask(res))
            self.kick.set()
            self._show_ddns()
            d.destroy()

        def do_save(*_):
            msg.config(text='Checking with your provider...', fg=C['amber'])
            save.set_enabled(False)
            kw = {k: rows[k][1].get() for k in spec[state['kind']]}
            kind = state['kind']

            def work():
                try:
                    r = sn.set_ddns(kind, **kw)
                except Exception as ex:                       # noqa: BLE001
                    r = ex
                self.root.after(0, lambda: done(r))
            threading.Thread(target=work, daemon=True).start()

        def do_off():
            sn.clear_ddns()
            self.chat_add('admin', 'Hostname updates turned off. The hostname itself was kept; change it with Set hostname.')
            self._show_ddns()
            d.destroy()
        save = RoundButton(row, 'Save', do_save, C['accent'], f.h3, height=f.s(40), width=f.s(110))
        save.pack(side='right')
        RoundButton(row, 'Cancel', d.destroy, C['grey'], f.h3, height=f.s(40), width=f.s(110)).pack(side='right', padx=8)
        if cur:
            RoundButton(row, 'Turn off', do_off, C['grey'], f.small, height=f.s(40), width=f.s(110)).pack(side='left')
        seg.set(state['kind'])
        show(state['kind'])
        d.bind('<Return>', do_save)
        d.bind('<Escape>', lambda ev: d.destroy())
        self._center(d)

    def _ddns_tick(self):
        """Every 5 minutes (and soon after start): tell the provider this home's current address, if hostname updates are set up."""
        self.root.after(300000, self._ddns_tick)
        if not sn or not sn.ddns_config():
            return

        def work():
            was = sn.ddns_last.get('ok')
            ok, text = sn.ddns_update()
            if not ok and was is not False:
                self.q.put(('chat', 'error', text))
            self.root.after(0, self._show_ddns)
        threading.Thread(target=work, daemon=True).start()

    def _show_ddns(self):
        if not getattr(self, 'ddns_status', None) or not sn:
            return
        c = sn.ddns_config()
        last = sn.ddns_last
        if not c:
            self.ddns_status.config(text='', fg=C['faint'])
        elif last.get('ok') is None:
            self.ddns_status.config(text='Waiting for the first update.', fg=C['soft'])
        else:
            when = time.strftime('%H:%M', time.localtime(last['time']))
            self.ddns_status.config(text='Last update %s: %s' % (when, self._hide_in(last['text']) if self.hide_ips else last['text']), fg=C['green'] if last['ok'] else C['red'])

    def show_profile_done(self, name, pw, ip):
        d, box = self.dialog('Profile made')
        self.L(box, 'Profile "%s" is ready' % name, self.f.h1, fg=C['green']).pack(anchor='w')
        self.L(box, 'On the game\'s sign-in page, type:', self.f.body, fg=C['soft']).pack(anchor='w', pady=(6, 14))
        card = tk.Frame(box, bg=C['card'])
        card.pack(fill='x')
        rows = [('POL-ID', name), ('Password', pw), ('ServerIP', self.mask(ip) or '(not on a network)')]
        if self.addr.get('net'):
            rows.append(('From outside', self.mask(self.addr['net'])))
        rows.append(('ServerPort', str(sc.SERVER_PORT_FOR_PLAYERS)))
        for i, (k, v) in enumerate(rows):
            self.L(card, k, self.f.h3, fg=C['soft'], anchor='w', width=13, bg=C['card']).grid(row=i, column=0, sticky='w', padx=(22, 8), pady=self.f.s(8))
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
            pm.add_command(label='(no roles yet, see Moderation)', state='disabled')
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

    def open_player_actions(self):
        sel = self.online.selection()
        if not sel or not sel[0].startswith('p:'):
            return
        w = self.player_actions

        class At:                                            # where the menu appears: just under the link
            x_root, y_root = w.winfo_rootx(), w.winfo_rooty() + w.winfo_height()
        self.player_menu(sel[0][2:], True, At)

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
