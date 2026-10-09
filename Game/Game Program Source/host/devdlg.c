/* In-game developer login: Account / Password / ServerIP / Port entered on screen before the game's network init.
   The program's own dialog class (vtable 0x5F30E0) is never opened in this build and is not wired into the window manager, so the host draws
   its own entry screen with the program's text routine (0x2C5A00) from a hook in the per-frame function (0x2D8C00), reads the keyboard through
   the program's own keyboard services (slots 104 update / 107 ascii), and finally writes
   "-net 3 -f -ip <ip> -port <port> -pass <pass> -print -accunt <account>" over the active command line (0x7BE260, 200 bytes). */
#include <stdio.h>
#include <string.h>
#include <tamtypes.h>
#include <kernel.h>
#include "host.h"
#ifdef DISC_BUILD
#include "dev_cfg_disc.h"       /* install disc / shipped builds: no account, password or address compiled in */
#else
#include "dev_cfg.h"          /* DEV_ACCT / DEV_PASS: private test credentials (mode 600, not part of any shipped file) */
#endif

#define GAME_CMDLINE   0x7BE260
#define GAME_FRAME_FN  0x2D89F0
#define GAME_ORIG_NT   0x376CB0       /* the call we hook in MainFlow (0x2D9AA4) */
#define GAME_ORIG_DRAW 0x2DDC90       /* the call we hook in the frame function (0x2D8BE0), before the 2D passes flush */
#ifndef DEV_IP
#define DEV_IP "0.0.0.0"
#endif

extern void host_drawtext(int x, int y, const char *s, u32 color);

volatile int g_restart_req = 0;      /* the game began shutting down (host.c) */
volatile int g_input_block = 0;        /* set while a host screen owns the keyboard/pad (the game gets no input) */
volatile u32 g_dlg_state = 0;         /* 0 not run, 1 running, 2 done */
static char f_ip[32] = DEV_IP, f_port[8] = "54001", f_acct[16] = "", f_pass[16] = "";
static char *fields[4] = { f_ip, f_port, f_acct, f_pass };
static const int flen[4] = { 31, 7, 15, 15 };
static const char *flabel[4] = { "Server IP:", "Port:", "Account:", "Password:" };
static int cur = 0, done = 0;

static void key_in(int ch)
{
    char *f = fields[cur]; int n = (int)strlen(f);
    if (ch == '\r' || ch == '\n') { if (cur == 3) done = 1; else cur++; return; }
    if (ch == '\t') { cur = (cur + 1) & 3; return; }
    if (ch == 8 || ch == 127) { if (n) f[n - 1] = 0; return; }
    if (ch >= 0x21 && ch < 0x7f && n < flen[cur]) { f[n] = (char)ch; f[n + 1] = 0; }
}

static void poll_keys(void)
{
    u32 *tab = (u32 *)SLOT_TABLE;
    int (*upd)(int) = (int (*)(int))tab[104];            /* sqKbdUpdate(0) */
    int (*asc)(int) = (int (*)(int))tab[107];            /* sqKbdGetAsciiCodeLastUpdated(0) */
    if (upd(0) > 0) { int c = asc(0); if (c > 0) key_in(c); }
}

static void draw_screen(void)
{
    char line[64]; int y = 120 * 16;
    host_drawtext(40 * 16, 70 * 16, "FFXI developer login   (Enter = next / start, Tab = next, Backspace = delete)", 0x80808080);
    for (int i = 0; i < 4; i++) {
        const char *shown = fields[i];
        char mask[20]; if (i == 3) { int n = (int)strlen(f_pass); for (int k = 0; k < n; k++) mask[k] = '#'; mask[n] = 0; shown = mask; }
        snprintf(line, sizeof line, "%c %-10s %s%s", i == cur ? '>' : ' ', flabel[i], shown, i == cur ? "_" : "");
        host_drawtext(40 * 16, y, line, i == cur ? 0x80808080 : 0x60606060);
        y += 28 * 16;
    }
}


#ifdef DEV_NATIVE
/* Developer login screen drawn over the running title screen with the program's own text routine (0x35BCF0, the one its unused developer window uses).
   English labels.  While it is up the game gets no keyboard/mouse/pad input (g_input_block); the host reads the keyboard itself.
   Keys: type to edit, Tab or Enter = next field, Shift+Tab not needed, Backspace = delete, Enter on the last field = connect.
   When confirmed: account -> the lobby context, password -> command line (the lobby digest reads it), server address -> DNS answer. */
#define DLG_OBJ_PTR   0x7B97E8
extern char g_dev_ip[32];
extern volatile u32 g_real[];
static int nat_state = 0, nat_frames = 0, nat_field = 0;
static char n_acct[16], n_pass[16], n_ip[32], n_port[8] = "54001";
static char *n_f[4] = { n_acct, n_pass, n_ip, n_port };
static const int n_len[4] = { 15, 15, 31, 5 };
static const char *n_label[4] = { "POL-ID (account) :", "Password         :", "Server IP        :", "Server Port      :" };
static void gtext(int x, int y, const char *s, u32 col)
{
    void (*f)(int, int, const char *, u32) = (void (*)(int, int, const char *, u32))0x549D20;
    f(x - 1, y, s, 0x80000000); f(x + 1, y, s, 0x80000000); f(x, y - 1, s, 0x80000000); f(x, y + 1, s, 0x80000000);     /* dark outline so it reads over the scenery */
    f(x, y, s, col);
}   /* the title screen's own string draw (pixel coordinates, 512x448); only valid inside its draw step */
static void nat_apply(void)
{
    char line[200];
    if (n_ip[0]) { strncpy(g_dev_ip, n_ip, sizeof g_dev_ip - 1); g_dev_ip[sizeof g_dev_ip - 1] = 0; }
    if (n_acct[0]) { strncpy((char *)0x60FED4, n_acct, 15); ((char *)0x60FED4)[15] = 0; strncpy((char *)0x62359C, n_acct, 15); ((char *)0x62359C)[15] = 0; }
    snprintf(line, sizeof line, "-net 3 -ip %s -port %s -pass %s -print -accunt %s", g_dev_ip, n_port[0] ? n_port : "54001", n_pass, n_acct);
    memset((void *)GAME_CMDLINE, 0, 200); strncpy((char *)GAME_CMDLINE, line, 199);
    printf("[host] devdlg: login set (account %s, server %s:%s)\n", n_acct, g_dev_ip, n_port[0] ? n_port : "54001");
}
static void nat_key(int c)
{
    char *f = n_f[nat_field]; int n = (int)strlen(f);
    if (c == '\r' || c == '\n') { if (nat_field < 3) nat_field++; else { nat_apply(); nat_state = 2; g_input_block = 0; } return; }
    if (c == '\t') { nat_field = (nat_field + 1) & 3; return; }
    if (c == 8 || c == 127) { if (n) f[n - 1] = 0; return; }
    if (c >= 0x20 && c < 0x7f && n < n_len[nat_field]) { f[n] = (char)c; f[n + 1] = 0; }
}
static void nat_draw(void)
{
    char line[80], mask[20];
    gtext(40, 20, "FFXI  Developer Login", 0x80808080);
    gtext(40, 42, "Type to edit.  Tab / Enter = next field.", 0x80808080);
    gtext(40, 60, "Enter on the last field = connect.", 0x80808080);
    for (int i = 0; i < 4; i++) {
        const char *shown = n_f[i];
        if (i == 1) { int n = (int)strlen(n_pass), k; for (k = 0; k < n; k++) mask[k] = '*'; mask[n] = 0; shown = mask; }
        snprintf(line, sizeof line, "%s %s%s", n_label[i], shown, i == nat_field ? "_" : "");
        gtext(40, 88 + i * 22, line, i == nat_field ? 0x8040c0c0 : 0x80808080);
    }
}
volatile int g_veto_terms = 0, g_terms_vetoed = 0, g_signin_pending = 0;   /* PS2 fix: OK pressed before the network was up: terms + lobby wait for it */      /* the developer page comes first: the terms-of-service window ("menu    ptc8lice") is held back until it is done */
#ifdef DEV_SHOW
#ifdef DISC_BUILD
#include "dev_profiles_disc.h"
#else
#include "dev_profiles.h"
#endif
/* The program's own (beta) developer account page, opened by name through the menu manager: the registry entry for it was patched in at start-up (registry_patch).
   Opened as soon as the interface exists, i.e. before the terms-of-service page.  The page's native input handles field selection / typing / "OK" (obj+0x14 = done);
   F1..F8 load a saved login (g_profiles) into the four edit boxes, and when the page reports done the values are applied (account, password, server address). */
extern char g_dev_ip[32], g_dev_port[8];
extern volatile u32 g_real[];
static int sh_state = 0, sh_wait = 0, sh_prof = -1, sh_frame = 0;
static u32 sh_obj;
#define SH_CTRL(i) (*(u32 *)(sh_obj + 0x138 + 4 * (i)))
/* write an edit box's text directly (visible text +0x12, working copy +0x3A0, lengths +0x39C/+0x690): the box's own set-text routine clears the text when its input-method
   conversion call returns 0, which is what happens here while a box has the focus */
static void sh_direct(u32 c, const char *t)
{
    int n = (int)strlen(t); if (n > 31) n = 31;
    memcpy((char *)(c + 0x12), t, n); ((char *)(c + 0x12))[n] = 0;
    memcpy((char *)(c + 0x3A0), t, n); ((char *)(c + 0x3A0))[n] = 0;
    memcpy((char *)(c + 0x1D5), t, n); ((char *)(c + 0x1D5))[n] = 0;                       /* the converted copy the box draws from */
    *(volatile int *)(c + 0x39C) = n; *(volatile int *)(c + 0x690) = n;
}
static void sh_settext(int i, const char *t)
{
    u32 c = SH_CTRL(i); if (!c) return;
    u32 mgr = *(volatile u32 *)0x739A08;
    if (mgr && *(volatile u8 *)(mgr + 0x14) && *(volatile u32 *)(mgr + 0x10) == c && *(volatile u32 *)(mgr + 0x18)) ((void (*)(u32, const char *))0x56BF90)(*(volatile u32 *)(mgr + 0x18), t);
    else sh_direct(c, t);
}
/* the server address, port and POL-ID last typed on the sign-in page are kept in pfs1:/image/ffxi/SERVER.TXT (never the password) and filled in next time.
   The network thread (sv_poll) reads and writes the file with the game's own file calls. */
#define SRV_FILE "pfs1:/image/ffxi/SERVER.TXT"
typedef int (*io_open_t)(const char *, int, int); typedef int (*io_close_t)(int); typedef int (*io_rw_t)(int, void *, int);
#define IO_SLOT(n) (((u32 *)SLOT_TABLE)[n])
static char sv_acct[16], sv_ip[32], sv_port[8]; static volatile int sv_have = 0, sv_applied = 0;
static char sv_buf[96]; static volatile int sv_len = 0;
static void sv_load(void)
{
    char buf[96]; int fd = ((io_open_t)IO_SLOT(938))(SRV_FILE, 1, 0), n, i, f = 0; char *dst[3] = { sv_ip, sv_port, sv_acct }; int cap[3] = { 31, 7, 15 }, len[3] = { 0, 0, 0 };
    if (fd < 0) return;
    n = ((io_rw_t)IO_SLOT(940))(fd, buf, sizeof buf - 1); ((io_close_t)IO_SLOT(939))(fd);
    for (i = 0; i < n && f < 3; i++) {
        if (buf[i] == '\n') { f++; continue; }
        if (buf[i] < 0x20 || buf[i] > 0x7e || len[f] >= cap[f]) continue;
        dst[f][len[f]++] = buf[i]; dst[f][len[f]] = 0;
    }
    sv_have = sv_ip[0] != 0;
}
void sv_poll(void)
{
    static int loaded = 0, quiet = 0;
    { extern volatile int g_restart_req, g_dev_applied; extern void host_soft_restart(void); if (g_restart_req && g_dev_applied && ++quiet > 6) host_soft_restart(); }   /* ~3 s after the game began shutting down; the frame hook is no longer called by then */
    if (!loaded) { loaded = 1; sv_load(); }
    if (sv_len > 0) {
        int fd = ((io_open_t)IO_SLOT(938))(SRV_FILE, 0x0002 | 0x0200 | 0x0400, 0666);
        if (fd >= 0) { ((io_rw_t)IO_SLOT(941))(fd, sv_buf, sv_len); ((io_close_t)IO_SLOT(939))(fd); }
        sv_len = 0;
    }
}
static void sv_save(const char *acct, const char *ip, const char *port)
{
    if (!sv_len) sv_len = snprintf(sv_buf, sizeof sv_buf, "%s\n%s\n%s\n", ip, port, acct);
}
static void sh_load(int n)
{
    if (n < 0 || n >= (int)(sizeof g_profiles / sizeof g_profiles[0])) return;
    sh_prof = n;
    sh_settext(0, g_profiles[n].acct); sh_settext(1, g_profiles[n].pass); sh_settext(2, g_profiles[n].ip); sh_settext(3, g_profiles[n].port);
}
static void sh_apply(void)
{
    char acct[16], pass[16], ip[32], port[8], line[200];
    if (SH_CTRL(0) && SH_CTRL(1) && SH_CTRL(2) && SH_CTRL(3)) {                     /* edit boxes still alive: read them */
        const char *(*get)(u32, int) = (const char *(*)(u32, int))0x4804C0;
        strncpy(acct, get(SH_CTRL(0), 0), 15); acct[15] = 0; strncpy(pass, get(SH_CTRL(1), 0), 15); pass[15] = 0;
        strncpy(ip, get(SH_CTRL(2), 0), 31); ip[31] = 0; strncpy(port, get(SH_CTRL(3), 0), 7); port[7] = 0;
        ((void (*)(u32))*(u32 *)(*(u32 *)(sh_obj + 4) + 0x10))(sh_obj);               /* then the page's own close */
    } else {                                                                         /* the page already closed itself and filled its strings */
        strncpy(acct, (const char *)(sh_obj + 0x16), 15); acct[15] = 0; strncpy(pass, (const char *)(sh_obj + 0x36), 15); pass[15] = 0;
        strncpy(ip, (const char *)(sh_obj + 0x56), 31); ip[31] = 0; strncpy(port, (const char *)(sh_obj + 0x76), 7); port[7] = 0;
    }
    if (ip[0]) { strncpy(g_dev_ip, ip, sizeof g_dev_ip - 1); g_dev_ip[sizeof g_dev_ip - 1] = 0; }
    if (port[0]) { strncpy(g_dev_port, port, sizeof g_dev_port - 1); g_dev_port[sizeof g_dev_port - 1] = 0; }
    if (acct[0]) { strncpy((char *)0x60FED4, acct, 15); ((char *)0x60FED4)[15] = 0; strncpy((char *)0x62359C, acct, 15); ((char *)0x62359C)[15] = 0; }
    snprintf(line, sizeof line, "-net 3 -ip %s -port %s -pass %s -print -accunt %s", g_dev_ip, g_dev_port, pass, acct);
    memset((void *)GAME_CMDLINE, 0, 200); strncpy((char *)GAME_CMDLINE, line, 199);
    printf("[host] devdlg: login set (account %s [%d chars], password %d chars, server %s:%s)\n", acct, (int)strlen(acct), (int)strlen(pass), g_dev_ip, g_dev_port);
    if (g_dev_ip[0] && strcmp(g_dev_ip, "0.0.0.0")) sv_save(acct, g_dev_ip, g_dev_port);
    { extern volatile int g_dev_applied; g_dev_applied = 1; }
}
/* text drawn on top of the page by text2_probe (once per frame): which saved login is loaded and the key help */
static const char *net_err_text(int e)
{
    switch (e) {
    case -1:  return "SQIOPMEM not ready";            case -2:  return "network module load failed";
    case -4:  return "sqInitSocketAPI failed";        case -10: return "DHCP init failed";
    case -11: return "DHCP request failed";           case -12: return "DHCP refused";
    case -13: return "DHCP no answer";                case -14: return "bad static address";
    case -15: return "interface config failed";       case -98: return "network modules never started";
    case -99: return "thread start failed";           default:  return "";
    }
}
static void net_overlay(void)                           /* NETDIAG: live network bring-up status */
{
    extern volatile int g_net_state, g_net_err, g_net_static; extern volatile u32 g_net_ip;
    extern char g_netlog[16][64]; extern volatile int g_netlog_n;
    void (*tx)(int, int, const char *, int, u32) = (void (*)(int, int, const char *, int, u32))0x35BCF0;
    extern unsigned net_secs(void); extern volatile u32 g_net_t0, g_net_tup;
    char line[96]; u32 ip = g_net_ip; unsigned now = net_secs();
    if (g_net_state == 2)
        snprintf(line, sizeof line, "Network UP  PS2 %u.%u.%u.%u%s  took %u s", (unsigned)(ip >> 24), (unsigned)(ip >> 16 & 255), (unsigned)(ip >> 8 & 255), (unsigned)(ip & 255),
                 g_net_static ? " (fixed, DHCP failed)" : " (DHCP)", (unsigned)(g_net_tup - g_net_t0));
    else if (g_net_state == 1) snprintf(line, sizeof line, "Network starting ... %u s   (wait for UP before OK)", now - (unsigned)g_net_t0);
    else if (g_net_state == 0) snprintf(line, sizeof line, "Network not started yet", now);
    else snprintf(line, sizeof line, "Network FAILED %d/%d %s", g_net_state, g_net_err, net_err_text(g_net_err));
    tx(24, 8, line, 0, g_net_state == 2 ? 0x80008000 : (g_net_state < 0 ? 0x80000080 : 0x80008080));
    if (g_signin_pending) tx(24, 400, "OK pressed - sign-in continues by itself when the network is UP", 0, 0x80008080);
    int n = g_netlog_n, first = n > 9 ? n - 9 : 0;
    for (int i = first, row = 0; i < n; i++, row++) tx(24, 24 + 14 * row, g_netlog[i % 16], 0, 0x80808080);
}
void sh_overlay(void)
{
    char line[80];
    { extern volatile int g_net_state; static int shown_up = 0;
      (void)shown_up; if (sh_state == 1 || g_signin_pending) net_overlay(); }   /* PS2 fix: only on the sign-in page (and while a sign-in waits), never on the lobby screens */
    if (sh_state != 1) return;
    snprintf(line, sizeof line, "Saved logins: F1-F%d   %s", (int)(sizeof g_profiles / sizeof g_profiles[0]), sh_prof >= 0 ? g_profiles[sh_prof].label : "(none loaded)");
    ((void (*)(int, int, const char *, int, u32))0x35BCF0)(24, 418, line, 0, 0x80808080);
}
int sh_frame_now(void) { return sh_frame; }
int sh_state_now(void) { return sh_state; }
extern volatile u32 g_kbd_w; extern volatile u8 g_kbd_ring[32];
static u32 sh_kr = 0;
/* the game's own text entry never receives characters here (no PS2 input-method service), so typed characters (copied from the keyboard reads in trap_c)
   are appended to the focused edit box with the box's own set-text routine */
static void sh_type(void)
{
#ifdef FEP_FIX
    sh_kr = g_kbd_w; return;          /* the game's own text input works (sqFepKatakanaToFullshape), so never copy keys in */
#endif
    /* while a box is being edited its text lives in the text-input object (mgr+0x18): the box draws from it every frame, so typed characters go there
       (0x56C020 reads its text, 0x56BF90 replaces it); the game handles Backspace itself */
    u32 mgr = *(volatile u32 *)0x739A08;
    int act = mgr && *(volatile u8 *)(mgr + 0x14); u32 ctrl = act ? *(volatile u32 *)(mgr + 0x10) : 0;
    u32 ime = mgr ? *(volatile u32 *)(mgr + 0x18) : 0;
    int idx = -1, i;
    for (i = 0; i < 4; i++) if (ctrl && ctrl == SH_CTRL(i)) idx = i;
    while (sh_kr != g_kbd_w) {
        int c = g_kbd_ring[sh_kr++ & 31];
        if (!ime || c < 0x20 || c >= 0x7f || (idx < 0 && sh_state == 1) || !act) continue;
        char t[80]; int n = ((int (*)(u32, char *))0x56C020)(ime, t); if (n < 0 || n > 40) n = 0; t[n] = 0;
        if (n >= (idx < 0 ? 40 : 15 + (idx == 2 ? 16 : 0))) continue;
        t[n] = (char)c; t[n + 1] = 0;
        ((void (*)(u32, const char *))0x56BF90)(ime, t);
    }
}
extern volatile u32 g_tri_edge;
/* triangle in the character-name box = "generate a random name": the game does it through the input-method layer, which is missing, so make a
   pronounceable name here (consonant/vowel syllables) and put it into the active text control */
static void sh_randname(void)
{
    static u32 seen = 0, seed = 12345; static const char *C = "bdfghjklmnprstvz", *V = "aeiou";
    u32 mgr = *(volatile u32 *)0x739A08; if (g_tri_edge == seen) return; seen = g_tri_edge;
    if (!mgr || !*(volatile u8 *)(mgr + 0x14) || !*(volatile u32 *)(mgr + 0x18)) return;
    u32 ime = *(volatile u32 *)(mgr + 0x18); char t[16]; int n = 0, syl = 2 + (int)(sh_frame % 2), i;
    seed = seed * 1664525u + 1013904223u + (u32)sh_frame;
    for (i = 0; i < syl; i++) { seed = seed * 1664525u + 1013904223u; t[n++] = C[(seed >> 16) & 15]; seed = seed * 1664525u + 1013904223u; t[n++] = V[(seed >> 16) % 5]; }
    if ((seed >> 20) & 1) { seed = seed * 1664525u + 1013904223u; t[n++] = C[(seed >> 16) & 15]; }
    t[0] = (char)(t[0] - 32); t[n] = 0;
    ((void (*)(u32, const char *))0x56BF90)(ime, t);
}
static void registry_restore(void);
volatile u32 g_tca[8], g_tcs[8], g_tcn, g_tcpos = 0x300000;
static void tc_probe(void)      /* debug: find text-edit control objects (vtable 0x56f120 at obj+0x8ce0) and mirror their state field obj+0xa9c4 */
{
    u32 i, e = g_tcpos + 0x40000;
    for (; g_tcpos < e; g_tcpos += 4) { if (*(volatile u32 *)g_tcpos == 0x0056f120u && g_tcn < 8) { u32 o = g_tcpos - 0x8ce0, k; for (k = 0; k < g_tcn; k++) if (g_tca[k] == o) break; if (k == g_tcn) g_tca[g_tcn++] = o; } }
    if (g_tcpos >= 0x2000000) g_tcpos = 0x300000;
    for (i = 0; i < g_tcn; i++) if (g_tca[i] + 0xa9c4 < 0x2000000) g_tcs[i] = *(volatile u32 *)(g_tca[i] + 0xa9c4);   /* never read past 32 MB (TLB miss: an exception on a real PS2) */
}
static void terms_release(void)                          /* the developer page is done (and the network up): let the terms page open, then the lobby */
{
    g_signin_pending = 0; g_veto_terms = 0;
    if (g_terms_vetoed) {                                            /* now let the terms page open, as the game tried to a moment ago */
        static const char nm3[17] = "menu    ptc8lice";
        ((void (*)(u32, const char *, int, int))0x365150)(0x6AF320, nm3, 1, 0); ((void (*)(u32, int))0x365A80)(0x6AF320, 0);
        g_terms_vetoed = 0;
    }
}
static void nat_frame(void)
{
#if !defined(RELEASE) && defined(TC_PROBE)   /* 6 Oct 2026: debug RAM scan cost ~13% fps (W. Adoulin 21.5 -> 24.4); off unless -DTC_PROBE */
    tc_probe();                 /* debug only (it scanned 256 KB of memory every frame; not in release builds) */
#endif
    { extern void menu_ring_flush(void); menu_ring_flush(); }
    { extern void soc_frame(void); soc_frame(); }               /* command mailbox + friend-list service pump (social.c) */
    { extern void xf_flush(void); xf_flush(); }
    { extern void hlog_kick(void); hlog_kick(); }
    sh_frame++;
    { extern volatile int g_restart_req; extern void host_soft_restart(void); static int wait = 0;
      if (g_restart_req && sh_state == 2 && ++wait > 90) host_soft_restart(); }                 /* ~3 s after the game began shutting down */
    if (sh_state >= 1) {                                   /* PS2 fix: network bring-up starts 2 s after the sign-in page opened (game idle by then), every frame checked */
        static int nf = 0;
        if (++nf == 120) { extern void net_start_async(void); extern void netlog(const char *, u32, u32, u32); netlog("net: sign-in page up - bring-up starts", 0, 0, 0); net_start_async(); }
    }
    if (sh_state != 1) { sh_type(); /* sh_randname(): the game's own random-name button works now */ }                                          /* every other text box (character name, chat, ...): the game gets no characters from the missing input-method layer */
    if (sh_state == 0) {
        sh_obj = *(volatile u32 *)DLG_OBJ_PTR;
        if (sh_obj && ++sh_wait > 20) {
            static const char nm2[17] = "menu    dbaccoun";
            u32 ctx = *(volatile u32 *)0x624FE0;
            *(volatile u32 *)0x624FE0 = 0;                                  /* the page's no-context branch creates all four edit boxes */
            ((void (*)(u32, const char *, int, int))0x365150)(0x6AF320, nm2, 1, 0);
            ((void (*)(u32, int))0x365A80)(0x6AF320, 0);
            *(volatile u32 *)0x624FE0 = ctx;
            printf("[host] devdlg: developer page opened (controls %08x %08x %08x %08x)\n", (unsigned)SH_CTRL(0), (unsigned)SH_CTRL(1), (unsigned)SH_CTRL(2), (unsigned)SH_CTRL(3));
            sh_load(0); sh_state = 1;
        }
    } else if (sh_state == 2) {
        { static int rc = 0; if (++rc == 180) registry_restore(); }   /* a few seconds after the page closed */
        if (g_signin_pending) { extern volatile int g_net_state; if (g_net_state == 2 || g_net_state < 0) { printf("[host] devdlg: network state %d - sign-in continues\n", (int)g_net_state); terms_release(); } }
    } else if (sh_state == 1) {
        static int lastk = 0;
        sh_type();
        if (sv_have && !sv_applied && sh_frame > 30) {                          /* the saved server, unless something was typed already */
            sv_applied = 1;
            if (SH_CTRL(2) && !((const char *(*)(u32, int))0x4804C0)(SH_CTRL(2), 0)[0]) { sh_settext(2, sv_ip); if (sv_port[0]) sh_settext(3, sv_port); if (sv_acct[0]) sh_settext(0, sv_acct); }
        }
        int k = ((int (*)(int))g_real[106])(0);                              /* sqKbdGetKeyCodeLastUpdated(0) */
        if (k != lastk) { if (k) printf("[host] devdlg: key code %d\n", k); lastk = k; if (k >= 0x3a && k <= 0x41) sh_load(k - 0x3a); }
        if (*(volatile u8 *)(sh_obj + 0x14)) {
            extern volatile int g_net_state;
            sh_apply(); sh_state = 2;
            if (g_net_state == 2) terms_release();
            else { g_signin_pending = 1; printf("[host] devdlg: OK before the network is up (state %d) - sign-in held until it is\n", (int)g_net_state); }
        }
    }
}
u32 dev_title_text_hook(int x, int y, const char *str, u32 col) { return ((u32 (*)(int, int, const char *, u32))0x549D20)(x, y, str, col); }
#else
static void nat_frame(void)
{
    if (nat_state == 0) {
        if (*(volatile u32 *)DLG_OBJ_PTR && ++nat_frames > 300) {            /* the program's interface objects exist: the title screen is up */
            strncpy(n_ip, g_dev_ip, sizeof n_ip - 1);
#ifdef DEV_ACCT
            strncpy(n_acct, DEV_ACCT, 15); strncpy(n_pass, DEV_PASS, 15);
#endif
            g_input_block = 1; nat_state = 1;
            printf("[host] devdlg: developer login screen up\n");
        }
    }
    if (nat_state == 1) {
        static int last = 0;
        ((int (*)(int))g_real[104])(0);                                      /* sqKbdUpdate(0) */
        int c = ((int (*)(int))g_real[107])(0);                              /* sqKbdGetAsciiCodeLastUpdated(0) */
        if (c != last && c) nat_key(c);
        last = c;
    }
}
/* called in place of the title screen's version-string draw (0x4ACC18) */
u32 dev_title_text_hook(int x, int y, const char *str, u32 col)
{
    ((u32 (*)(int, int, const char *, u32))0x549D20)(x, y, str, col);
    if (nat_state == 1) nat_draw();
    return 0;
}
#endif   /* DEV_SHOW */
#endif   /* DEV_NATIVE */


#ifdef DEV_MENU
/* Stand-alone developer login menu (its own full screen, nothing from the game is drawn behind it): the SDK debug console on a dark-blue screen, shown before the
   game's network start-up, keyboard through the program's own USB services once they are up.  Fields as in the beta: POL-ID, Password, ServerIP, ServerPort. */
#include <debug.h>
extern volatile u32 g_hid_ready;
extern volatile u32 g_real[];
extern char g_dev_ip[32];
static void menu_putf(int col, int row, u32 color, const char *s) { scr_setfontcolor(color); scr_setXY(col, row); scr_printf("%s", s); }
static void menu_draw(const char *status)
{
    char line[96], mask[20];
    scr_setXY(0, 0); scr_clear();
    menu_putf(4, 2, 0x00FFFFFF, "FINAL FANTASY XI   -   Developer Login");
    menu_putf(4, 3, 0x00C0A080, "----------------------------------------------------------------");
    static const char *lab[4] = { "POL-ID     :", "Password   :", "ServerIP   :", "ServerPort :" };
    char *val[4] = { f_acct, f_pass, f_ip, f_port };
    for (int i = 0; i < 4; i++) {
        const char *shown = val[i];
        if (i == 1) { int n = (int)strlen(f_pass), k; for (k = 0; k < n; k++) mask[k] = '*'; mask[n] = 0; shown = mask; }
        snprintf(line, sizeof line, "%s %s%s", lab[i], shown, i == cur ? "_" : " ");
        menu_putf(4, 6 + i * 2, i == cur ? 0x0000FFFF : 0x00FFFFFF, line);
        if (i == cur) menu_putf(2, 6 + i * 2, 0x0000FFFF, ">");
    }
    menu_putf(4, 15, cur == 4 ? 0x0000FFFF : 0x00FFFFFF, cur == 4 ? "> [ Start ]" : "  [ Start ]");
    menu_putf(4, 19, 0x00C0A080, "Type to edit.   Tab / Enter = next field.   Enter on [ Start ] = connect.");
    menu_putf(4, 20, 0x00C0A080, "Backspace = delete.   The server address is where every PlayOnline name points.");
    if (status) menu_putf(4, 23, 0x0000A0FF, status);
}
static void run_menu(void)
{
    u32 tab_ok = 0; int waited = 0;
    init_scr(); scr_setbgcolor(0x00502010); scr_setCursor(0);
    while (!g_hid_ready && waited < 600) { menu_draw("Starting the keyboard ..."); { volatile int d; for (d = 0; d < 400000; d++) ; } waited++; }
    (void)tab_ok;
    int last = 0, draws = 0;
    for (;;) {
        ((int (*)(int))g_real[104])(0);                                  /* sqKbdUpdate(0) */
        int c = ((int (*)(int))g_real[107])(0);                          /* sqKbdGetAsciiCodeLastUpdated(0) */
        if (c && c != last) {
            if (c == '\r' || c == '\n') { if (cur == 4) break; cur++; if (cur > 4) cur = 4; }
            else if (c == '\t') cur = (cur + 1) % 5;
            else if (cur < 4) {
                char *f = cur == 0 ? f_acct : cur == 1 ? f_pass : cur == 2 ? f_ip : f_port; int n = (int)strlen(f);
                int lim = cur == 0 ? 15 : cur == 1 ? 15 : cur == 2 ? 31 : 5;
                if (c == 8 || c == 127) { if (n) f[n - 1] = 0; }
                else if (c >= 0x20 && c < 0x7f && n < lim) { f[n] = (char)c; f[n + 1] = 0; }
            }
        }
        last = c;
        if ((draws++ & 3) == 0) menu_draw(0);
        { volatile int d; for (d = 0; d < 20000; d++) ; }
    }
    strncpy(g_dev_ip, f_ip, sizeof g_dev_ip - 1); g_dev_ip[sizeof g_dev_ip - 1] = 0;
    scr_setXY(0, 0); scr_clear(); menu_putf(4, 10, 0x00FFFFFF, "Starting ...");
}
#endif


#ifdef DEV_SCREEN
/* Developer login screen in place of the "Connecting to lobby server." page (a plain striped screen with the logo): the lobby connection is held (net.c,
   g_dev_hold) until Enter on [Start]; the form is drawn by the program's own text routine when that status text would be drawn, the keyboard is read
   through the program's USB services, and the game gets no input meanwhile.  English, fields as in the beta: POL-ID / Password / ServerIP / ServerPort. */
volatile int g_dev_hold = 0;
extern char g_dev_ip[32], g_dev_port[8];
extern volatile u32 g_real[];
extern void host_drawtext(int x, int y, const char *s, u32 color);
static char s_acct[16], s_pass[16], s_ip[32], s_port[8];
static int s_cur = 0, s_state = 0, s_in_form = 0;
static void scr_key(int c)
{
    char *f[4] = { s_acct, s_pass, s_ip, s_port }; static const int lim[4] = { 15, 15, 31, 5 };
    if (c == '\r' || c == '\n') {
        if (s_cur >= 3) {
            strncpy(g_dev_ip, s_ip, sizeof g_dev_ip - 1); strncpy(g_dev_port, s_port[0] ? s_port : "54001", sizeof g_dev_port - 1);
            if (s_acct[0]) { strncpy((char *)0x60FED4, s_acct, 15); ((char *)0x60FED4)[15] = 0; strncpy((char *)0x62359C, s_acct, 15); ((char *)0x62359C)[15] = 0; }
            { char line[200]; snprintf(line, sizeof line, "-net 3 -ip %s -port %s -pass %s -print -accunt %s", g_dev_ip, g_dev_port, s_pass, s_acct);
              memset((void *)GAME_CMDLINE, 0, 200); strncpy((char *)GAME_CMDLINE, line, 199); }
            printf("[host] devdlg: login set (account %s, server %s:%s)\n", s_acct, g_dev_ip, g_dev_port);
            s_state = 2; g_input_block = 0; g_dev_hold = 0; return;
        }
        s_cur++; return;
    }
    if (c == '\t') { s_cur = (s_cur + 1) % 4; return; }
    if (s_cur < 4) {
        char *p = f[s_cur]; int n = (int)strlen(p);
        if (c == 8 || c == 127) { if (n) p[n - 1] = 0; }
        else if (c >= 0x20 && c < 0x7f && n < lim[s_cur]) { p[n] = (char)c; p[n + 1] = 0; }
    }
}
static void scr_text(int x, int y, const char *s, u32 col) { ((void (*)(int, int, const char *, int, u32))0x35BCF0)(x, y, s, 0, col); }   /* the program's own wrapper: color in t0 */
static void scr_form(void)
{
    char line[64], mask[20]; int i;
    scr_text(30, 86, "Developer Login", 0x80808080);
    static const char *lab[4] = { "POL-ID     :", "Password   :", "ServerIP   :", "ServerPort :" };
    char *val[4] = { s_acct, s_pass, s_ip, s_port };
    for (i = 0; i < 4; i++) {
        const char *shown = val[i];
        if (i == 1) { int n = (int)strlen(s_pass), k; for (k = 0; k < n; k++) mask[k] = '*'; mask[n] = 0; shown = mask; }
        snprintf(line, sizeof line, "%c %s %s%s", i == s_cur ? '>' : ' ', lab[i], shown, i == s_cur ? "_" : "");
        scr_text(24, 118 + i * 17, line, i == s_cur ? 0x80808080 : 0x80686868);
    }
    scr_text(24, 118 + 4 * 17 + 2, "Tab / Enter = next field.  Enter on ServerPort = connect.", 0x80585858);
}
/* called from text2_probe for every string the game draws; returns 1 when the call was replaced by the form */
static int scr_probe(int x, int y, const char *str)
{
    if (s_in_form || s_state == 2) return 0;
    if (x != 27 || y < 138 || y > 218 || strncmp(str, "FINAL FANTASY", 13) == 1000) return 0;       /* the user-agreement paragraph (six lines at x=27) */
    if (y != 138) return 1;                                                  /* the other five lines: nothing */
    if (s_state == 0) {
        strncpy(s_ip, g_dev_ip, sizeof s_ip - 1); strncpy(s_port, g_dev_port, sizeof s_port - 1);
#ifdef DEV_ACCT
        strncpy(s_acct, DEV_ACCT, 15); strncpy(s_pass, DEV_PASS, 15);
#endif
        s_state = 1; g_input_block = 1; printf("[host] devdlg: developer login screen up\n");
    }
    static int last = 0;
    ((int (*)(int))g_real[104])(0);                                          /* sqKbdUpdate(0) */
    int c = ((int (*)(int))g_real[107])(0);                                  /* sqKbdGetAsciiCodeLastUpdated(0) */
    if (c && c != last) scr_key(c);
    last = c;
    s_in_form = 1; scr_form(); s_in_form = 0;
    return 1;
}
#endif

/* ---- string-draw hook (see trap.S text_hook_entry) ---- */
extern void text_hook_entry(void);
volatile int g_textlog = 0;
/* 6 Oct 2026: the newest text drawn on the bottom help line (y >= 380), readable over PINE, so the one-click launcher can see
   which main-menu entry is selected ("Create a new character." etc.) instead of counting button presses. */
volatile char g_bottom[48]; volatile u32 g_bottom_n = 0;
static void note_bottom(int y, const char *str)
{
    int i;
    if (y < 380 || (u32)str < 0x100000 || (u32)str >= 0x2000000 || !str[0]) return;
    for (i = 0; i < 47 && str[i] >= 0x20 && str[i] < 0x7f; i++) g_bottom[i] = str[i];
    g_bottom[i] = 0; g_bottom_n++;
}
/* 6 Oct 2026: never write the developer page's password row (x ~335, y ~127) into the emulator log */
static int is_secret_row(int x, int y) { return x >= 320 && x <= 350 && y >= 118 && y <= 138; }
int text_probe(int x, int y, const char *str, u32 col, u32 flag)
{
    (void)flag;
    note_bottom(y, str);
    if (is_secret_row(x, y)) return 0;
    if ((u32)str >= 0x100000 && (u32)str < 0x2000000) {   /* 6 Oct 2026: 決定 (Shift-JIS 8C 88 92 E8) may come through this text path too: draw "OK" */
        u8 *u = (u8 *)str; static int logged1 = 0;
        if (u[0] >= 0x80 && !logged1) { logged1 = 1; printf("[host] text1 high-byte label %02x %02x %02x %02x at x=%d y=%d\n", u[0], u[1], u[2], u[3], x, y); }
        if (u[0] == 0x8C && u[1] == 0x88 && ((u[2] == 0x92 && u[3] == 0xE8) || (u[2] == 0x81 && u[3] == 0x40 && u[4] == 0x92 && u[5] == 0xE8))) { u[0] = 'O'; u[1] = 'K'; u[2] = 0; u[3] = 0; }   /* 決定 or 決　定 */
    }
    if (g_textlog > 0 && (u32)str >= 0x100000 && (u32)str < 0x2000000) {
        char b[48]; int i; for (i = 0; i < 40 && str[i] >= 0x20 && str[i] < 0x7f; i++) b[i] = str[i]; b[i] = 0;
        static char seen[64][16]; static int ns = 0; int k, dup = 0;
        for (k = 0; k < ns; k++) if (!strncmp(seen[k], b, 15)) { dup = 1; break; }
        if (!dup && ns < 64) { strncpy(seen[ns], b, 15); seen[ns][15] = 0; ns++; g_textlog--; printf("[host] text x=%d y=%d col=%08x '%s'\n", x, y, (unsigned)col, b); }
    }
    return 0;
}
extern void text2_hook_entry(void);
extern void menu_hook_entry(void);
static char g_mring[32][17]; static volatile int g_mhead = 0, g_mshown = 0;
volatile char g_mlast[17]; volatile u32 g_mlast_n = 0;   /* 7 Oct 2026: newest menu opened (the ring above keeps only the first 32) */
int menu_probe(u32 mgr, const char *name, int flag, int a3)
{
    (void)mgr; (void)a3; (void)flag;
    if (g_veto_terms && (u32)name >= 0x100000 && (u32)name < 0x2000000 && !memcmp(name, "menu    ptc8lice", 16)) { g_terms_vetoed = 1; return 1; }
    if ((u32)name >= 0x100000 && (u32)name < 0x2000000) { int i; for (i = 0; i < 16; i++) g_mlast[i] = (name[i] >= 0x20 && name[i] < 0x7f) ? name[i] : '.'; g_mlast[16] = 0; g_mlast_n++;
        { extern volatile int g_in_world;                 /* title / character screens vs. playing (LOGOUT_FIX in host.c uses it) */
          if (!memcmp(name + 8, "loby2", 5) || !memcmp(name + 8, "chf", 3) || !memcmp(name + 8, "chmk", 4) || !memcmp(name + 8, "race", 4)) g_in_world = 0;
          else if (!memcmp(name + 8, "hnback", 6)) g_in_world = 1; } }
    if ((u32)name >= 0x100000 && (u32)name < 0x2000000 && g_mhead < 32) {          /* no printing here: this runs on the game's small thread stacks */
        char *d = g_mring[g_mhead]; int i; for (i = 0; i < 16; i++) d[i] = (name[i] >= 0x20 && name[i] < 0x7f) ? name[i] : '.'; d[16] = 0; g_mhead++;
    }
    return 0;
}
extern volatile u32 g_failn, g_failr[120]; extern volatile char g_failp[120][48];
void menu_ring_flush(void) { static u32 fs = 0; while (fs < g_failn) { printf("[host] FILE FAIL %08x '%s'\n", (unsigned)g_failr[fs], (const char *)g_failp[fs]); fs++; } while (g_mshown < g_mhead) { printf("[host] menu open '%s'\n", g_mring[g_mshown]); g_mshown++; } }
volatile int g_textlog2 = 0;
int text2_probe(int x, int y, const char *str, u32 a3, u32 col)
{
    (void)a3;
#ifdef DEV_SHOW
    { extern void sh_overlay(void); static int lastf = -1; extern int sh_frame_now(void); int f = sh_frame_now(); if (f != lastf) { lastf = f; sh_overlay(); } }
#endif
#ifdef DEV_SCREEN
    if ((u32)str >= 0x100000 && (u32)str < 0x2000000 && scr_probe(x, y, str)) return 1;
#endif
    note_bottom(y, str);
    if (is_secret_row(x, y)) {                                                        /* Password box: stars instead of the characters, the cursor '|' stays */
        static char st[4][40]; static int si = 0;
        if ((u32)str >= 0x100000 && (u32)str < 0x2000000 && str[0]) {
            char *d = st[si++ & 3]; int n = 0; while (n < 36 && str[n] >= 0x20 && str[n] < 0x7f) n++;
            if (n >= 1 && str[n] == 0) { int k; int cur = str[n - 1] == '|'; for (k = 0; k < n - cur; k++) d[k] = '*'; if (cur) d[k++] = '|'; d[k] = 0; return (int)d; }
        }
        return 0;
    }
    if (x >= 330 && x <= 340 && y >= 90 && y <= 330 && (u32)str >= 0x100000 && (u32)str < 0x2000000) {      /* sign-in page boxes: only the last 17 characters fit */
        static char clip[4][24]; static int ci = 0; int n = 0; while (n < 64 && str[n] >= 0x20 && str[n] < 0x7f) n++;
        if (n > 17 && str[n] == 0) { char *d = clip[ci++ & 3]; memcpy(d, str + n - 17, 17); d[17] = 0; return (int)d; }
    }
    if ((u32)str >= 0x100000 && (u32)str < 0x2000000 && (u8)str[0] >= 0x80) {
        /* 6 Oct 2026: the developer page's OK button (and any other button) reads 決定 (Shift-JIS 8C 88 92 E8): draw "OK" instead.
           The label is rewritten in place (same or shorter length). First sighting at the dev page's button row is logged in hex. */
        u8 *u = (u8 *)str;
        static int logged = 0;
        if (!logged) { logged = 1; printf("[host] button label bytes %02x %02x %02x %02x %02x at x=%d y=%d\n", u[0], u[1], u[2], u[3], u[4], x, y); }
        if (u[0] == 0x8C && u[1] == 0x88 && ((u[2] == 0x92 && u[3] == 0xE8) || (u[2] == 0x81 && u[3] == 0x40 && u[4] == 0x92 && u[5] == 0xE8))) { u[0] = 'O'; u[1] = 'K'; u[2] = 0; u[3] = 0; }   /* 決定 or 決　定 */
    }
    if (g_textlog2 > 0 && (u32)str >= 0x100000 && (u32)str < 0x2000000) {
        char b[48]; int i; for (i = 0; i < 40 && str[i] >= 0x20 && str[i] < 0x7f; i++) b[i] = str[i]; b[i] = 0;
        static char seen[96][16]; static int ns = 0; int k, dup = 0;
        for (k = 0; k < ns; k++) if (!strncmp(seen[k], b, 15)) { dup = 1; break; }
        if (!dup && ns < 96) { strncpy(seen[ns], b, 15); seen[ns][15] = 0; ns++; g_textlog2--; printf("[host] text2 x=%d y=%d col=%08x '%s'\n", x, y, (unsigned)col, b); }
    }
    return 0;
}
#ifdef DEV_SHOW
/* the release build's menu registry (0x5AF130, 44-byte entries: name[16], pad, slot pointer at +0x20, flags +0x24/+0x28) has no entry for the beta account page; the unused
   'tkdebug dbnamese' entry (306) is turned into 'menu    dbaccoun' pointing at the already-constructed account object slot (0x7B97E8) */
static u8 s_reg_orig[44]; static int s_reg_saved = 0;
static void registry_restore(void)      /* the game's own character-name page lives in this entry: give it back once the developer page is done */
{
    if (!s_reg_saved) return;
    memcpy((void *)(0x5AF130 + 306 * 44), s_reg_orig, 44); s_reg_saved = 0;
    FlushCache(0); FlushCache(2);
    printf("[host] devdlg: registry entry 306 (character name page) restored\n");
}
static void registry_patch(void)
{
    g_veto_terms = 1;
    u8 *e = (u8 *)(0x5AF130 + 306 * 44);
    if (memcmp(e, "tkdebug dbnamese", 16)) { printf("[host] devdlg: registry entry 306 is not dbnamese\n"); return; }
    memcpy(s_reg_orig, e, 44); s_reg_saved = 1;
    memcpy(e, "menu    dbaccoun", 16); *(u32 *)(e + 32) = 0x7B97E8; *(u32 *)(e + 36) = 0x1002e; *(u32 *)(e + 40) = 0x208;
    printf("[host] devdlg: registered menu    dbaccoun\n");
}
#endif
/* ---- 6 Oct 2026: emote diagnostics (handler 0x30D5F0 / motion start 0x30DBB0), read over PINE ---- */
extern void emote_hook_entry(void); extern void motion_hook_entry(void);
volatile u32 g_emo_n = 0, g_emo_pkt[8], g_emo_act[8], g_mot_n = 0, g_mot_args[4];
void emote_probe(u32 a0, u32 a1, u32 pkt)
{
    int i; u32 idx, act;
    (void)a0; (void)a1;
    if (pkt < 0x100000 || pkt >= 0x2000000) return;
    for (i = 0; i < 8; i++) g_emo_pkt[i] = ((volatile u32 *)pkt)[i];
    idx = *(volatile u16 *)(pkt + 12);
    act = idx < 2304 ? *(volatile u32 *)(0x663600 + 4 * idx) : 0;
    g_emo_act[0] = act;
    if (act >= 0x100000 && act < 0x2000000) {
        g_emo_act[1] = *(volatile u8 *)(act + 0x1C4); g_emo_act[2] = *(volatile u8 *)(act + 0x134);
        g_emo_act[3] = *(volatile u32 *)(act + 0x178); g_emo_act[4] = *(volatile u8 *)(act + 0xFA);
        g_emo_act[5] = *(volatile u8 *)(act + 0x12C) | (*(volatile u8 *)(act + 0x12D) << 8) | (*(volatile u8 *)(act + 0x137) << 16);
        g_emo_act[6] = *(volatile u32 *)(act + 0x84);
    }
    g_emo_n++;
}
void motion_probe(u32 a0, u32 a1, u32 a2, u32 a3) { g_mot_args[0] = a0; g_mot_args[1] = a1; g_mot_args[2] = a2; g_mot_args[3] = a3; g_mot_n++; }
#ifdef EMOTE_PROBE
static void emote_hooks_install(void)
{
    u32 *e = (u32 *)0x30D5F0, *m = (u32 *)0x30DBB0;
    if (e[0] == 0x27bdff90 && e[1] == 0xffbf0050) { e[0] = 0x08000000 | (((u32)emote_hook_entry >> 2) & 0x3ffffff); e[1] = 0; printf("[host] emote hook installed\n"); }
    if (m[0] == 0x27bdff90 && m[1] == 0xffbf0050) { m[0] = 0x08000000 | (((u32)motion_hook_entry >> 2) & 0x3ffffff); m[1] = 0; printf("[host] motion hook installed\n"); }
}
#endif

void text_hook_install(void)
{
#ifdef EMOTE_PROBE
    emote_hooks_install();
#endif
#ifdef DEV_SHOW
    registry_patch();
#endif
#ifdef DEV_SCREEN
    g_dev_hold = 1;
#endif
    { u32 *m = (u32 *)0x365150;
      if (m[0] == 0x27bdff70 && m[1] == 0xffbf0050) { m[0] = 0x08000000 | (((u32)menu_hook_entry >> 2) & 0x3ffffff); m[1] = 0; printf("[host] menu hook installed\n"); }
      else printf("[host] menu hook: unexpected prologue %08x %08x\n", m[0], m[1]); }
    { u32 *q = (u32 *)0x2C5A00;
      if (q[0] == 0x27bdff60 && q[1] == 0xffbf0070) { q[0] = 0x08000000 | (((u32)text2_hook_entry >> 2) & 0x3ffffff); q[1] = 0; g_textlog2 = 300; printf("[host] text2 hook installed\n"); }
      else printf("[host] text2 hook: unexpected prologue %08x %08x\n", q[0], q[1]); }
    u32 *p = (u32 *)0x549D40;
    if (p[0] == 0x27bdff60 && p[1] == 0xffbf0090) { p[0] = 0x08000000 | (((u32)text_hook_entry >> 2) & 0x3ffffff); p[1] = 0; printf("[host] text hook installed\n"); }
    else printf("[host] text hook: unexpected prologue %08x %08x\n", p[0], p[1]);
}

u32 dev_frame_hook(u32 a0)
{
    static int armed = 0, fr = 0;
    if (!armed) { armed = 1; g_textlog = 200; }
    u32 r = ((u32 (*)(u32))GAME_ORIG_DRAW)(a0);
    { extern void perf_frame(void); perf_frame(); }      /* frame counter (perf.c) */
#ifdef HEAP_FAST
    { extern void hf_frame(void); hf_frame(); }          /* a delete scan the allocator skipped (host.c) */
#endif
#ifdef DEV_NATIVE
    nat_frame();
#endif
    if (g_dlg_state == 1) { poll_keys(); draw_screen(); }
    return r;
}

u32 dev_dialog_hook(u32 a0, u32 a1, u32 a2, u32 a3)
{
    if (!g_dlg_state) {
#ifdef DEV_AUTOLOGIN
        strncpy(f_acct, DEV_ACCT, sizeof f_acct - 1); strncpy(f_pass, DEV_PASS, sizeof f_pass - 1); done = 1;     /* no screen: fixed test login */
        g_dlg_state = 1;
#elif defined(DEV_MENU)
        g_dlg_state = 1;
#ifdef DEV_ACCT
        strncpy(f_acct, DEV_ACCT, sizeof f_acct - 1); strncpy(f_pass, DEV_PASS, sizeof f_pass - 1);
#endif
        run_menu();
#else
        g_dlg_state = 1;
        void (*frame)(void) = (void (*)(void))GAME_FRAME_FN;
        while (!done) frame();
#endif
        char line[200];
        snprintf(line, sizeof line, "-net 3 -ip %s -port %s -pass %s -print -accunt %s", f_ip, f_port[0] ? f_port : "54001", f_pass, f_acct);
        memset((void *)GAME_CMDLINE, 0, 200); strncpy((char *)GAME_CMDLINE, line, 199);
        printf("[host] devdlg: command line set: -net 3 -ip %s -port %s -accunt %s\n", f_ip, f_port, f_acct);
        g_dlg_state = 2;
    }
    return ((u32 (*)(u32, u32, u32, u32))GAME_ORIG_NT)(a0, a1, a2, a3);
}
