/* update.c - in-game update client (Fan Project by Habex).
   After OK on the sign-in page (network up) the server typed there is asked for its update list over the lobby port:
       GET /update/manifest        FFXIUPD 1 / version N / H <size> <crc> <name> / D <size> <crc> <name> <path>   (Server/update_tool.py)
       GET /update/f/<name>        one file (Range: bytes=N- continues)
   Files in pfs1:/image/ffxi/: U_<name> the downloaded files, UPDVER.TXT the installed version, UPDOVR.TXT the data files
   (the game's opens of <path> are served from U_<name>, see ov_hook), UPDHOST.TXT the new game program (chain.c starts it at boot).
   Nothing on the original game files is changed: deleting the U_* and UPD*.TXT files undoes every update. */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <tamtypes.h>
#include <kernel.h>
#include <delaythread.h>
#include "host.h"

/* file calls go through the program's own slot table (the lifted Sony file service), as the game uses them */
#define SLOT(n) (((u32 *)SLOT_TABLE)[n])
static int io_open(const char *p, int fl, int m) { return ((int (*)(const char *, int, int))SLOT(938))(p, fl, m); }
static int io_close(int fd) { return ((int (*)(int))SLOT(939))(fd); }
static int io_read(int fd, void *b, int n) { return ((int (*)(int, void *, int))SLOT(940))(fd, b, n); }
static int io_write(int fd, const void *b, int n) { return ((int (*)(int, const void *, int))SLOT(941))(fd, b, n); }
static int io_lseek(int fd, int o, int w) { return ((int (*)(int, int, int))SLOT(942))(fd, o, w); }
static int io_stat(const char *p, void *st) { return ((int (*)(const char *, void *))SLOT(951))(p, st); }
int net_tcp(int op, int h, void *p, int n);
extern void host_soft_restart(void);
extern volatile int g_net_state;
extern volatile int g_chained;
extern void *_gp;

#define UD "pfs1:/image/ffxi/UPD"
#define WR (0x0002 | 0x0200 | 0x0400)

volatile int g_upd_state = 0;      /* 0 idle, 1 downloading, 2 finished (sign-in continues), 3 installed - restarting, 4 looking for an update, 5 asking the player, 6 player chose to return to login */
volatile int g_upd_answer = 0;     /* set by the sign-in page: 1 update now, 2 return to login */
volatile int g_upd_go = 0;         /* the sign-in page: OK pressed and the network is up */
volatile int g_upd_pct = 0;
char g_upd_msg[48];

#define MAXIT 24
typedef struct { char kind; u32 size, crc; char name[56]; char target[88]; } Item;
static Item it[MAXIT]; static int nit; static u32 mver;
static u8 mf[4096];
static u8 io[8192] __attribute__((aligned(64)));
static char pa[160];
static u8 stk[12288] __attribute__((aligned(16)));

static void msg(const char *m) { strncpy(g_upd_msg, m, sizeof g_upd_msg - 1); g_upd_msg[sizeof g_upd_msg - 1] = 0; }

static u32 crc32u(u32 c, const u8 *p, u32 n)
{
    c = ~c;
    while (n--) { c ^= *p++; for (int k = 0; k < 8; k++) c = (c >> 1) ^ (0xEDB88320u & (0u - (c & 1))); }
    return ~c;
}
static int rd_small(const char *path, char *buf, int max)       /* file -> buf (zero ended), length or -1 */
{
    int fd = (int)io_open(path, 1, 0), n;
    if (fd < 0) return -1;
    n = (int)io_read(fd, buf, max - 1); io_close(fd);
    if (n < 0) return -1;
    buf[n] = 0; return n;
}
static int put_small(const char *path, const char *buf, int n)
{
    int fd = (int)io_open(path, WR, 0666), w;
    if (fd < 0) return -1;
    w = (int)io_write(fd, buf, n); io_close(fd);
    return w == n ? 0 : -1;
}
static void empty_file(const char *path) { int fd = io_open(path, WR, 0666); if (fd >= 0) io_close(fd); }
static int file_size(const char *path)
{
    static u8 st[128] __attribute__((aligned(64)));
    if ((int)io_stat(path, st) < 0) return -1;
    return (int)*(u32 *)(st + 8);
}

/* ---- HTTP over the lobby port ---- */
static int sock = -1; static int body_left;
static void sock_close(void) { if (sock >= 0) net_tcp(4, sock, 0, 0); sock = -1; }
static int sock_open(void)
{
    int i, r = 0;
    sock = net_tcp(0, -1, 0, 0);
    if (sock < 0) return -1;
    for (i = 0; i < 80 && r == 0; i++) { r = net_tcp(1, sock, 0, 0); if (!r) DelayThread(100 * 1000); }
    if (r <= 0) { sock_close(); return -1; }
    return 0;
}
static int send_all(const char *s, int n)
{
    int o = 0, idle = 0;
    while (o < n) {
        int r = net_tcp(2, sock, (void *)(s + o), n - o);
        if (r > 0) { o += r; idle = 0; continue; }
        if (r < 0 || ++idle > 300) return -1;
        DelayThread(10 * 1000);
    }
    return 0;
}
static int recv_some(void *b, int n)                              /* >0 bytes, 0 nothing for 8 s; -6 from the socket library means "no data yet" */
{
    int idle = 0;
    for (;;) {
        int r = net_tcp(3, sock, b, n);
        if (r > 0) return r;
        if (++idle > 800) return 0;
        DelayThread(10 * 1000);
    }
}
/* request `path` (from byte `start`); on success the headers are consumed, *first/*nfirst hold body bytes that came with them, returns the Content-Length (or -1) */
static int http_begin(const char *path, u32 start, u32 end, u8 **first, int *nfirst)
{
    int n = 0, i, code = 0, len = -1;
    char req[200];
    if (sock_open() < 0) return -1;
    if (end) snprintf(req, sizeof req, "GET %s HTTP/1.0\r\nRange: bytes=%u-%u\r\n\r\n", path, start, end);
    else snprintf(req, sizeof req, "GET %s HTTP/1.0\r\n\r\n", path);
    if (send_all(req, (int)strlen(req)) < 0) { sock_close(); return -1; }
    while (n < (int)sizeof io - 1) {
        int r = recv_some(io + n, (int)sizeof io - 1 - n);
        if (r <= 0) { sock_close(); return -1; }
        n += r; io[n] = 0;
        for (i = 3; i < n; i++) if (io[i] == '\n' && io[i - 1] == '\r' && io[i - 2] == '\n' && io[i - 3] == '\r') break;
        if (i < n) {
            char *h = (char *)io, *q;
            if (strncmp(h, "HTTP/", 5) == 0 && (q = strchr(h, ' '))) code = atoi(q + 1);
            if (code != 200 && code != 206) { sock_close(); return code == 404 ? -404 : -1; }
            for (q = h; q < (char *)io + i; q++) if ((q == h || q[-1] == '\n') && (q[0] | 0x20) == 'c' && !strncasecmp(q, "Content-Length:", 15)) len = atoi(q + 15);
            *first = io + i + 1; *nfirst = n - (i + 1);
            body_left = len;
            return len;
        }
    }
    sock_close(); return -1;
}

/* ---- local state ---- */
static u32 rd_num(const char *path)
{
    char b[24]; if (rd_small(path, b, sizeof b) < 0) return 0;
    return (u32)strtoul(b, 0, 10);
}
static void fpath(char *o, const char *name, const char *suffix) { snprintf(o, 160, "pfs1:/image/ffxi/U_%s%s", name, suffix); }

static int parse_manifest(int n)
{
    char *s = (char *)mf, *e, *l; nit = 0; mver = 0;
    mf[n] = 0;
    if (strncmp(s, "FFXIUPD 1", 9)) return -1;
    for (l = strchr(s, '\n'); l; l = e) {
        l++; e = strchr(l, '\n'); if (e) *e = 0;
        if (!strncmp(l, "version ", 8)) mver = (u32)strtoul(l + 8, 0, 10);
        else if ((l[0] == 'H' || l[0] == 'D') && l[1] == ' ' && nit < MAXIT) {
            Item *t = &it[nit]; char *q = l + 2, *w; memset(t, 0, sizeof *t); t->kind = l[0];
            t->size = (u32)strtoul(q, &q, 10); t->crc = (u32)strtoul(q, &q, 16);
            while (*q == ' ') q++;
            for (w = t->name; *q && *q != ' ' && *q != '\r' && w < t->name + sizeof t->name - 1; ) *w++ = *q++;
            while (*q == ' ') q++;
            if (t->kind == 'D') for (w = t->target; *q && *q != '\r' && w < t->target + sizeof t->target - 1; ) *w++ = *q++;
            for (w = t->name; *w; w++) if (!((*w >= '0' && *w <= '9') || (*w >= 'a' && *w <= 'z') || (*w >= 'A' && *w <= 'Z') || *w == '.' || *w == '_' || *w == '-')) return -1;
            if (!t->size || !t->name[0] || (t->kind == 'D' && (!t->target[0] || strstr(t->target, "..")))) return -1;
            nit++;
        }
        if (!e) break;
    }
    return mver ? 0 : -1;
}

/* download item t in pieces of CHUNK bytes, one connection each: the PS2's network stack takes only about 40 KB on one connection
   (found in PCSX2; a longer transfer stops with the window never reopening).  done/total feed the percentage. */
#define CHUNK 16384
static int fetch(Item *t, u32 *done, u32 total)
{
    u32 got = 0, crc = 0; int fd, ok = 1;
    char url[100];
    fpath(pa, t->name, "");
    snprintf(url, sizeof url, "/update/f/%s", t->name);
    fd = io_open(pa, WR, 0666);
    if (fd < 0) return -1;
    while (got < t->size && ok) {
        u32 want = t->size - got < CHUNK ? t->size - got : CHUNK; int attempt, good = 0;
        for (attempt = 0; attempt < 4 && !good; attempt++) {
            u8 *first; int nfirst, len, r; u32 c = crc, g = got, left = want;
            len = http_begin(url, got, got + want - 1, &first, &nfirst);
            if (len == -404) { ok = 0; break; }
            if (len != (int)want) { if (len >= 0) sock_close(); DelayThread(300 * 1000); continue; }
            io_lseek(fd, (int)got, 0);
            r = nfirst;
            for (;;) {
                if (r > 0) {
                    if ((u32)r > left) r = (int)left;
                    if (io_write(fd, first, r) != r) { left = 1; break; }
                    c = crc32u(c, first, (u32)r); g += (u32)r; left -= (u32)r;
                    g_upd_pct = (int)((u64)(*done + (g - got)) * 100 / (total ? total : 1));
                }
                if (!left) break;
                first = io; r = recv_some(io, (int)sizeof io);
                if (r <= 0) break;
            }
            sock_close();
            if (!left) { crc = c; got = g; *done += want; good = 1; }
        }
        if (!good) ok = 0;
    }
    io_close(fd);
    if (!ok || got != t->size || crc != t->crc) { empty_file(pa); return -1; }       /* written straight to its name: a short or wrong file is emptied, so the size check redoes it */
    return 0;
}

static void apply_and_restart(int host_new)
{
    int i, n = 0; char *o = (char *)mf;
    for (i = 0; i < nit; i++) if (it[i].kind == 'D') n += snprintf(o + n, sizeof mf - n, "%u %08x %s %s\n", it[i].size, it[i].crc, it[i].name, it[i].target);
    put_small(UD "OVR.TXT", o, n);
    { extern void ov_reload(void); ov_reload(); }
    (void)host_new;
}

static void run(void)
{
    u32 ver, total = 0, done = 0, bad = 0; int i, n, len, host = -1, hnew = 0, need_n = 0, got_n = 0;
    u8 *first; int nfirst;
    g_upd_answer = 0; g_upd_pct = 0; g_upd_state = 4;
    msg("Looking for updates...");
    len = http_begin("/update/manifest", 0, 0, &first, &nfirst);
    if (len <= 0 || len >= (int)sizeof mf) { sock_close(); msg(""); return; }              /* no update on this server (or an older one) */
    n = 0; memcpy(mf, first, nfirst); n = nfirst;
    while (n < len) { int r = recv_some(mf + n, len - n); if (r <= 0) break; n += r; }
    sock_close();
    if (n != len || parse_manifest(n) < 0) { msg(""); return; }
    ver = rd_num(UD "VER.TXT");
    printf("[host] update: manifest %d bytes, version %u, installed %u\n", n, mver, ver);
    if (mver == ver) { msg(""); return; }
    { char b[64]; if (rd_small(UD "BAD.TXT", b, sizeof b) > 0) bad = (u32)strtoul(b, 0, 16); }
    for (i = 0; i < nit; i++) {
        if (it[i].kind == 'H') { if (bad && it[i].crc == bad) { it[i].kind = 'x'; continue; } host = i; }
        fpath(pa, it[i].name, "");
        if (file_size(pa) != (int)it[i].size) { total += it[i].size; need_n++; }
    }
    msg("A new update is available.");
    g_upd_state = 5;                                                /* the sign-in page asks: update now, or return to login */
    while (!g_upd_answer) DelayThread(50 * 1000);
    if (g_upd_answer != 1) { g_upd_state = 6; msg(""); return; }
    g_upd_state = 1;
    printf("[host] update: version %u (have %u), %d items, %u bytes to fetch, host item %d\n", mver, ver, nit, total, host);
    for (i = 0; i < nit; i++) {
        if (it[i].kind == 'x') continue;
        fpath(pa, it[i].name, "");
        if (file_size(pa) == (int)it[i].size) continue;
        printf("[host] update: fetching %s\n", it[i].name);
        snprintf(g_upd_msg, sizeof g_upd_msg, "Downloading update  (%d of %d)", ++got_n, need_n);
        if (fetch(&it[i], &done, total) < 0) { msg("Update failed - continuing without it"); DelayThread(2500 * 1000); return; }
    }
    msg("Installing update...");
    /* the game program */
    if (host >= 0) {
        char b[96]; int m = snprintf(b, sizeof b, "%u %08x %s\n0\n", it[host].size, it[host].crc, it[host].name);
        char old[96]; int had = rd_small(UD "HOST.TXT", old, sizeof old) > 0;
        hnew = !had || strncmp(old, b, m - 2) != 0;
        if (hnew && put_small(UD "HOST.TXT", b, m) < 0) { msg("Update failed - continuing without it"); DelayThread(2500 * 1000); return; }
    } else empty_file(UD "HOST.TXT");
    apply_and_restart(hnew);
    { char b[16]; int m = snprintf(b, sizeof b, "%u\n", mver); put_small(UD "VER.TXT", b, m); }
    if (hnew) {
        g_upd_pct = 100; msg("Update installed. Restarting the game...");
        g_upd_state = 3; DelayThread(3000 * 1000); host_soft_restart();
    }
    msg("Update installed.");
    DelayThread(1500 * 1000);
}

static void confirm_host(void)                                    /* the updated game program reached the sign-in page: it works */
{
    char b[96]; int n = rd_small(UD "HOST.TXT", b, sizeof b), i;
    if (n < 4) return;
    for (i = 0; i < n && b[i] != '\n'; i++) { }
    if (i + 2 >= n || b[i + 1] == '0') return;
    b[i + 1] = '0'; put_small(UD "HOST.TXT", b, i + 3);
}

static void thread(void *a)
{
    (void)a;
    if (g_chained) confirm_host();
    for (;;) {
        while (!g_upd_go) DelayThread(100 * 1000);
        if (g_net_state == 2) run();
        if (g_upd_state != 6) g_upd_state = 2;                      /* 6: the player went back to the login page */
        while (g_upd_go) DelayThread(100 * 1000);                   /* the page takes the result, then clears g_upd_go (a second sign-in checks again) */
        g_upd_state = 0;
    }
}
void upd_start(void)                                              /* sign-in page up */
{
    static int started = 0; ee_thread_t t;
    if (started) return;
    started = 1;
    memset(&t, 0, sizeof t);
    t.func = (void *)thread; t.stack = stk; t.stack_size = sizeof stk; t.gp_reg = &_gp; t.initial_priority = 50;
    int id = CreateThread(&t); if (id >= 0) StartThread(id, 0);
}

/* ---- the game's opens of updated data files are served from UPDATE/f ---- */
#define NOV 24
static u32 ov_h[NOV]; static char ov_f[NOV][64]; static int ov_n, ov_state;
static u32 hash(const char *p) { u32 h = 2166136261u; while (*p) h = (h ^ (u8)*p++) * 16777619u; return h; }
void ov_reload(void) { ov_state = 0; }
static void ov_load(void)
{
    static char b[4096]; int n, i;                       /* static: the game's file thread has a tiny stack */
    ov_n = 0; ov_state = -1;                             /* also stops ov_hook from calling itself through the read below */
    n = rd_small(UD "OVR.TXT", b, sizeof b);
    if (n <= 0) return;
    for (i = 0; i < n && ov_n < NOV; ) {
        char *l = b + i, *e = strchr(l, '\n'), *q, *nm, *tg; if (!e) break; *e = 0; i = (int)(e - b) + 1;
        q = strchr(l, ' '); if (!q) continue; q = strchr(q + 1, ' '); if (!q) continue; nm = q + 1;
        tg = strchr(nm, ' '); if (!tg) continue; *tg++ = 0;
        if (strlen(nm) > 63) continue;
        ov_h[ov_n] = hash(tg); strcpy(ov_f[ov_n], nm); ov_n++;
    }
    if (ov_n) ov_state = 1;
}
/* idx 938 open / 951 getstat: path in r[1]; returns the replacement path or the same one */
const char *ov_hook(const char *p, char *buf)
{
    const char *q; int i;
    if (ov_state < 0 || (u32)p < 0x100000 || (u32)p >= 0x2000000) return p;
    if (p[0] != 'p' || p[1] != 'f' || p[2] != 's') return p;
    if (!ov_state) ov_load();
    if (ov_state <= 0) return p;
    q = strstr(p, "image/ffxi/"); if (!q) return p;
    { u32 h = hash(q + 11);
      for (i = 0; i < ov_n; i++) if (ov_h[i] == h) { strcpy(buf, "pfs1:/image/ffxi/U_"); strcat(buf, ov_f[i]); return buf; } }
    return p;
}
