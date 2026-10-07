/* social.c (b49_social): in-game social services for the 2016 host without PlayOnline.

   1. Command mailbox (test driver): a PC tool writes a command line into g_soc_cmd over PINE and bumps g_soc_cmd_seq; on the next frame the
      game thread runs it through the program's own command interpreter CommandCalc(line, 0) at 0x3A9ED0 (what FsShortcutManager::DoCommand does),
      exactly as if it had been typed on the chat line.

   2. Friend list without PlayOnline.  The 2016 program reads its friend list through the PlayOnline slots 165-169 (sqPlayOnlineStoreFriendList,
      ...Check, GetFriendInfo, GetBlackInfo): gcFriendRefSet / gcFriendUpdate call GetFriendInfo(i, sqPolFriend*) for i < 200 and use every record
      whose handle is valid; online friends (status 1-3, active character = FFXI) are then looked up on the FFXI search server (zone/job/level), the
      same way as /sea.  Here those slots answer from a table that a host thread fetches from the LAN friend service (work/b49_social/service/
      soc_service.py) over TCP on the server address typed on the developer page, port SOC_PORT, every SOC_PERIOD seconds and right after a command.
      Commands (typed on the chat line, caught before the game's interpreter):
        /befriend <name>   /addfriend <name>   send a friend request (the game's own /befriend would need PlayOnline mail)
        /faccept <name>    /fdecline <name>    accept / refuse a friend request (requests wait on the server until answered)
        /unfriend <name>                       remove a friend (or cancel a request)
        /fmsg <name> <text>                    leave a message for a friend (shown in their chat log at their next refresh, even if offline now)
        /friends                               print the friend list (online/offline, area, job) in the chat log
        /lan <command>                         run a server "!" command (e.g. /lan qmc = !qmc) without typing '!'
      /friend (the game's own command) and the main menu open the friend list window, which shows the same list. */
#include <stdio.h>
#include <string.h>
#include <tamtypes.h>
#include <kernel.h>
#include <delaythread.h>
#include "host.h"

#ifndef SOC_PORT
#define SOC_PORT 54460
#endif
#ifndef SOC_PERIOD
#define SOC_PERIOD 10
#endif
#define GAME_COMMANDCALC 0x3A9ED0u
#define GAME_CTX         0x624FE0u          /* *GAME_CTX = game context; friend system fields at +296.. (gcFriendInit) */
#define GAME_MSGWIN      0x689AE0u          /* *GAME_MSGWIN = CTkMsgWinData (chat log), as used by YkCmdBefriend */
#define GAME_ADDSYSSTR   0x35BC60u          /* CTkMsgWinData::AddSystemString(this, char *) */
#define GAME_CMDLINE     0x7BE260u          /* "-net 3 -ip .. -pass .. -accunt .." set by the developer page */

/* ---------------------------------------------------------------- 1. command mailbox */
volatile char g_soc_cmd[160];
volatile u32 g_soc_cmd_seq = 0, g_soc_cmd_done = 0, g_soc_cmd_n = 0;

/* ---------------------------------------------------------------- 2. friend list */
typedef struct { u32 accid, charid; u16 zone; u8 online, mjob, mlvl, sjob, slvl, pad; char name[16]; } SocFriend;   /* 32 bytes */
#define SOC_MAX 100                 /* friends shown in the game (the service keeps up to 200); host memory is tight below the lifted kernel */
static SocFriend g_sf_live[SOC_MAX], g_sf_stage[SOC_MAX];
volatile u32 g_sf_n = 0, g_sf_stage_n = 0, g_sf_stage_ready = 0;
volatile u32 g_soc_state = 0;                 /* 0 idle, 1 thread started; diagnostics below are PINE readable */
volatile s32 g_soc_last_err = 0; volatile u32 g_soc_syncs = 0, g_soc_fail = 0, g_soc_getinfo = 0;
/* outgoing command queue (game thread -> sync thread) and incoming chat-log lines (sync thread -> game thread) */
#define QN 8
static char g_q[QN][128]; volatile u32 g_qw = 0, g_qr = 0;
#define PN 16
static char g_p[PN][160]; volatile u32 g_pw = 0, g_pr = 0;
volatile u32 g_soc_wake = 0, g_soc_refresh = 0, g_soc_refreshes = 0, g_soc_retry = 0, g_soc_retry_t = 0;

static void say(const char *s)                /* game thread only */
{
    u32 mw = *(volatile u32 *)GAME_MSGWIN;
    static char b[160];
    if (!mw) return;
    strncpy(b, s, 159); b[159] = 0;
    ((void (*)(u32, char *))GAME_ADDSYSSTR)(mw, b);
}
static void post_line(const char *s)          /* sync thread: queue a chat-log line */
{
    if (g_pw - g_pr >= PN) return;
    strncpy(g_p[g_pw % PN], s, 159); g_p[g_pw % PN][159] = 0; g_pw++;
}

/* ---- tiny MD5 (RFC 1321) for the service login ---- */
static u32 md5_r(u32 x, int c) { return (x << c) | (x >> (32 - c)); }
static void md5(const u8 *msg, int len, u8 out[16])
{
    static const u32 K[64] = {
        0xd76aa478,0xe8c7b756,0x242070db,0xc1bdceee,0xf57c0faf,0x4787c62a,0xa8304613,0xfd469501,0x698098d8,0x8b44f7af,0xffff5bb1,0x895cd7be,0x6b901122,0xfd987193,0xa679438e,0x49b40821,
        0xf61e2562,0xc040b340,0x265e5a51,0xe9b6c7aa,0xd62f105d,0x02441453,0xd8a1e681,0xe7d3fbc8,0x21e1cde6,0xc33707d6,0xf4d50d87,0x455a14ed,0xa9e3e905,0xfcefa3f8,0x676f02d9,0x8d2a4c8a,
        0xfffa3942,0x8771f681,0x6d9d6122,0xfde5380c,0xa4beea44,0x4bdecfa9,0xf6bb4b60,0xbebfbc70,0x289b7ec6,0xeaa127fa,0xd4ef3085,0x04881d05,0xd9d4d039,0xe6db99e5,0x1fa27cf8,0xc4ac5665,
        0xf4292244,0x432aff97,0xab9423a7,0xfc93a039,0x655b59c3,0x8f0ccc92,0xffeff47d,0x85845dd1,0x6fa87e4f,0xfe2ce6e0,0xa3014314,0x4e0811a1,0xf7537e82,0xbd3af235,0x2ad7d2bb,0xeb86d391 };
    static const u8 R[64] = { 7,12,17,22,7,12,17,22,7,12,17,22,7,12,17,22, 5,9,14,20,5,9,14,20,5,9,14,20,5,9,14,20,
                              4,11,16,23,4,11,16,23,4,11,16,23,4,11,16,23, 6,10,15,21,6,10,15,21,6,10,15,21,6,10,15,21 };
    u32 h[4] = { 0x67452301, 0xefcdab89, 0x98badcfe, 0x10325476 };
    u8 buf[128]; int n = len < 64 ? len : 55, total, i, j;      /* passwords are short: one or two blocks */
    memset(buf, 0, sizeof buf); memcpy(buf, msg, n); buf[n] = 0x80;
    total = (n + 9 <= 64) ? 64 : 128;
    { u32 bits = (u32)n * 8; buf[total - 8] = bits; buf[total - 7] = bits >> 8; buf[total - 6] = bits >> 16; buf[total - 5] = bits >> 24; }
    for (j = 0; j < total; j += 64) {
        u32 w[16], a = h[0], b = h[1], c = h[2], d = h[3];
        for (i = 0; i < 16; i++) w[i] = buf[j + 4 * i] | (buf[j + 4 * i + 1] << 8) | (buf[j + 4 * i + 2] << 16) | ((u32)buf[j + 4 * i + 3] << 24);
        for (i = 0; i < 64; i++) {
            u32 f; int g;
            if (i < 16) { f = (b & c) | (~b & d); g = i; } else if (i < 32) { f = (d & b) | (~d & c); g = (5 * i + 1) & 15; }
            else if (i < 48) { f = b ^ c ^ d; g = (3 * i + 5) & 15; } else { f = c ^ (b | ~d); g = (7 * i) & 15; }
            u32 t = d; d = c; c = b; b = b + md5_r(a + f + K[i] + w[g], R[i]); a = t;
        }
        h[0] += a; h[1] += b; h[2] += c; h[3] += d;
    }
    for (i = 0; i < 4; i++) { out[4 * i] = h[i]; out[4 * i + 1] = h[i] >> 8; out[4 * i + 2] = h[i] >> 16; out[4 * i + 3] = h[i] >> 24; }
}
static int arg_of(const char *key, char *out, int max)       /* value after "key " in the game's command line */
{
    const char *cl = (const char *)GAME_CMDLINE; int kl = strlen(key), i, k;
    for (i = 0; i < 190 && cl[i]; i++)
        if (!memcmp(cl + i, key, kl) && cl[i + kl] == ' ') {
            for (k = 0; k < max - 1 && cl[i + kl + 1 + k] && cl[i + kl + 1 + k] != ' '; k++) out[k] = cl[i + kl + 1 + k];
            out[k] = 0; return k;
        }
    out[0] = 0; return 0;
}

const char *soc_cmdline_pass(void) { static char pw[20]; arg_of("-pass", pw, sizeof pw); return pw; }
/* ---- the sync thread: one TCP exchange with the friend service ---- */
typedef struct { s16 type; u16 port; u32 addr; u8 pad[24]; } SqAddr __attribute__((aligned(16)));
extern char g_dev_ip[32];
static u32 parse_ip(const char *p) { u32 v = 0, a = 0; for (;; p++) { if (*p >= '0' && *p <= '9') a = a * 10 + (*p - '0'); else { v = (v << 8) | (a & 255); a = 0; if (!*p) break; } } return v; }
static char g_tx[1024] __attribute__((aligned(16))), g_rx[6144] __attribute__((aligned(16)));
static int parse_u(const char **pp) { const char *p = *pp; int v = 0; while (*p == ' ') p++; while (*p >= '0' && *p <= '9') v = v * 10 + (*p++ - '0'); *pp = p; return v; }
static int exchange(void)
{
    u32 *tab = (u32 *)SLOT_TABLE;
    typedef int (*f2)(u32, void *); typedef int (*f1)(int); typedef int (*f3)(int, void *, int);
    static SqAddr a; char acct[20], pass[20]; u8 dg[16]; int n = 0, i, h, r, got = 0;
    arg_of("-accunt", acct, sizeof acct); arg_of("-pass", pass, sizeof pass);
    if (!acct[0]) return -1;
    md5((const u8 *)pass, strlen(pass), dg);
    n = sprintf(g_tx, "HELLO %s ", acct);
    for (i = 0; i < 16; i++) n += sprintf(g_tx + n, "%02x", dg[i]);
    g_tx[n++] = '\n';
    while (g_qr != g_qw && n < (int)sizeof g_tx - 160) { n += sprintf(g_tx + n, "%s\n", g_q[g_qr % QN]); g_qr++; }
    n += sprintf(g_tx + n, "SYNC\n");
    memset(&a, 0, sizeof a); a.type = 1; a.port = SOC_PORT; a.addr = parse_ip(g_dev_ip);
    h = ((f2)tab[231])(0, &a);
    if (h < 0) return -2;
    for (r = 0, i = 0; i < 100 && r == 0; i++) { r = ((f1)tab[232])(h); if (!r) DelayThread(50 * 1000); }
    if (r <= 0) { ((f1)tab[236])(h); return -3; }
    if (((f3)tab[237])(h, g_tx, n) != n) { ((f1)tab[236])(h); return -4; }
    for (i = 0; i < 100; i++) {                                   /* up to ~5 s for the whole answer (ends with "END\n") */
        r = ((f3)tab[238])(h, g_rx + got, sizeof g_rx - 1 - got);
        if (r > 0) { got += r; g_rx[got] = 0; if (got >= 4 && !memcmp(g_rx + got - 4, "END\n", 4)) break; if (got >= (int)sizeof g_rx - 1) break; }
        else if (r < 0) break;
        else DelayThread(50 * 1000);
    }
    ((f1)tab[236])(h);
    if (got < 4) return -5;
    g_rx[got] = 0;
    /* parse */
    {
        char *p = g_rx; u32 k = 0;
        while (*p) {
            char *e = strchr(p, '\n'); if (!e) break; *e = 0;
            if (p[0] == 'N' && p[1] == ' ') post_line(p + 2);
            else if (p[0] == 'F' && p[1] == ' ' && k < SOC_MAX) {
                const char *q = p + 2; SocFriend *f = &g_sf_stage[k];
                f->accid = parse_u(&q); f->online = (u8)parse_u(&q); f->charid = parse_u(&q);
                while (*q == ' ') q++;
                for (i = 0; i < 15 && *q && *q != ' '; i++) f->name[i] = *q++ == '_' ? ' ' : q[-1];
                f->name[i] = 0;
                f->zone = (u16)parse_u(&q); f->mjob = (u8)parse_u(&q); f->mlvl = (u8)parse_u(&q); f->sjob = (u8)parse_u(&q); f->slvl = (u8)parse_u(&q);
                k++;
            }
            p = e + 1;
        }
        g_sf_stage_n = k; g_sf_stage_ready = 1;
    }
    return 0;
}
static u8 soc_stack[8192] __attribute__((aligned(16)));
static void soc_thread(void *arg)
{
    int warned = 0;
    for (;;) {
        int r = exchange();
        if (r < 0) { g_soc_fail++; g_soc_last_err = r; if (!warned) { post_line("Friend service not reachable (friend list unavailable)."); warned = 1; } }
        else { g_soc_syncs++; if (warned) { post_line("Friend service connected."); warned = 0; } }
        for (int t = 0; t < SOC_PERIOD * 10 && !g_soc_wake; t++) DelayThread(100 * 1000);
        g_soc_wake = 0;
    }
}
static void soc_start(void)
{
    extern void *_gp;
    ee_thread_t t; memset(&t, 0, sizeof t);
    t.func = (void *)soc_thread; t.stack = soc_stack; t.stack_size = sizeof soc_stack; t.initial_priority = 1; t.gp_reg = &_gp;      /* game threads run at 2 and never yield: anything lower never runs; this thread sleeps between steps */
    int id = CreateThread(&t); if (id >= 0) StartThread(id, 0);
    g_soc_state = 1;
}
static void queue_cmd(const char *s)
{
    if (g_qw - g_qr >= QN) { say("Friend service busy, try again."); return; }
    strncpy(g_q[g_qw % QN], s, 127); g_q[g_qw % QN][127] = 0; g_qw++; g_soc_wake = 1;
}

/* the chat-line commands: called from soc_cmd_entry (trap.S) before CommandCalc; 1 = handled here */
static int word(const char *s, const char *w) { int n = strlen(w); return !strncmp(s, w, n) && (s[n] == ' ' || s[n] == 0); }
int soc_cmd_filter(const char *line)
{
    char b[140]; const char *a; char *orig = (char *)line;
    if (!line || (u32)line < 0x100000 || (u32)line >= 0x2000000) return 0;
    while (*line == ' ') line++;
    if (line[0] != '/') return 0;
    if (word(line, "/lan")) {
        /* 6 Oct 2026: "/lan qmc Hello" runs the server command "!qmc Hello" (for keyboards / the on-screen keyboard where '!' is awkward).
           The line is rewritten in place (it only gets shorter) and handed on to the game's interpreter, which sends it as a say line;
           the server treats a say line starting with '!' as a command. */
        a = line + 4; while (*a == ' ') a++;
        if (!*a) { say("Usage: /lan <server command>   e.g. /lan qmc   (same as typing !qmc)"); return 1; }
        orig[0] = '!'; memmove(orig + 1, a, strlen(a) + 1);
        return 0;
    }
    if (word(line, "/befriend") || word(line, "/addfriend")) {
        a = strchr(line, ' '); while (a && *a == ' ') a++;
        if (!a || !*a) { say("Usage: /befriend <character name>"); return 1; }
        snprintf(b, sizeof b, "ADD %.20s", a); queue_cmd(b); return 1;
    }
    if (word(line, "/faccept") || word(line, "/fdecline")) {
        int acc = word(line, "/faccept");
        a = strchr(line, ' '); while (a && *a == ' ') a++;
        if (!a || !*a) { say(acc ? "Usage: /faccept <character name>" : "Usage: /fdecline <character name>"); return 1; }
        snprintf(b, sizeof b, "%s %.20s", acc ? "ACCEPT" : "DECLINE", a); queue_cmd(b); return 1;
    }
    if (word(line, "/unfriend")) {
        a = strchr(line, ' '); while (a && *a == ' ') a++;
        if (!a || !*a) { say("Usage: /unfriend <character name>"); return 1; }
        snprintf(b, sizeof b, "DEL %.20s", a); queue_cmd(b); return 1;
    }
    if (word(line, "/fmsg")) {
        a = strchr(line, ' '); while (a && *a == ' ') a++;
        if (!a || !*a || !strchr(a, ' ')) { say("Usage: /fmsg <name> <message>"); return 1; }
        snprintf(b, sizeof b, "MSG %.118s", a); queue_cmd(b); return 1;
    }
    if (word(line, "/friends")) { queue_cmd("LIST"); return 1; }
    return 0;
}

/* ---- slots ---- */
static u16 world_no(void) { u32 c = *(volatile u32 *)GAME_CTX; return c ? *(volatile u16 *)(c + 304) : 0xFFFF; }
/* 167 sqPlayOnlineGetFriendInfo(idx < 200, sqPolFriend *out /0xB0/): 0, record copied (an empty slot = all zero, handle invalid); -0x1C07 out of range */
static int svc_get_friend(int idx, u8 *out)
{
    g_soc_getinfo++;
    if (idx < 0 || idx >= 200) return -7175;
    if (!out) return -7175;
    memset(out, 0, 0xB0);
    if (idx >= (int)g_sf_n) return 0;
    const SocFriend *f = &g_sf_live[idx];
    u16 w = world_no(); if (w == 0xFFFF) w = 0;
    u64 fl = 0;
    fl |= (u64)(idx & 0x1FF) << 2;                                 /* order */
    if (f->online) { fl |= 1ull << 11; fl |= 1ull << 13; fl |= 1ull << 16; fl |= 1ull << 33; }   /* login, status 1 (online), active character 0, contents class 1 = FFXI */
    fl |= (u64)(idx & 0xFF) << 20;                                 /* num (the kernel sets it too) */
    *(u64 *)(out + 0) = f->accid;
    *(u64 *)(out + 8) = fl;
    /* character primitive 0: valid, contents class 1 (FFXI), sub id = {char id bits 16-19 at 24, world at 16, char id low 16}, user id */
    *(u16 *)(out + 0x18) = 1; *(u16 *)(out + 0x1A) = 1;
    *(u32 *)(out + 0x1C) = ((f->charid >> 16) & 0xF) << 24 | ((u32)w & 0xFF) << 16 | (f->charid & 0xFFFF);
    *(u64 *)(out + 0x20) = f->charid;
    /* handle primitive: valid, id = account id, number 0; name = the character name */
    *(u64 *)(out + 0x98) = 1ull | ((u64)f->accid << 1);
    memcpy(out + 0xA0, f->name, 15); out[0xAF] = 0;
    return 0;
}
static int svc_get_black(int idx, u8 *out) { if (idx < 0 || idx >= 100 || !out) return -7175; memset(out, 0, 0xB0); return 0; }
static int svc_store_friend(void) { g_soc_wake = 1; return 0; }        /* 165: "fetch the list": the next exchange does it */
static int svc_store_friend_check(void) { return 1; }                  /* 166: done */
static int svc_add_friend(u32 a0, u32 a1) { (void)a0; (void)a1; return 0; }   /* 187 (PlayOnline mail flow only): accepted, list comes from the service */
volatile u32 g_mus_args[5];   /* SOC_MUSPROBE debug probe data */
void soc_install(u32 *tab)
{
#ifdef SOC_MUSPROBE
    { extern void musplay_entry(void); u32 *p = (u32 *)0x3CCF50; if (p[0] == 0x27BDFF70 && p[1] == 0xFFBF0070) { p[0] = 0x08000000 | (((u32)musplay_entry >> 2) & 0x3FFFFFF); p[1] = 0; } }
#endif
    tab[165] = (u32)svc_store_friend; tab[166] = (u32)svc_store_friend_check;
    tab[167] = (u32)svc_get_friend; tab[169] = (u32)svc_get_black; tab[187] = (u32)svc_add_friend;
#ifndef SOC_NO_CMDHOOK
    { extern void soc_cmd_entry(void); u32 *p = (u32 *)GAME_COMMANDCALC;
      if (p[0] == 0x27BDFB50 && p[1] == 0xFFBF0080) { p[0] = 0x08000000 | (((u32)soc_cmd_entry >> 2) & 0x3FFFFFF); p[1] = 0; printf("[host] social: command hook installed\n"); }
      else printf("[host] social: CommandCalc prologue unexpected %08x %08x\n", p[0], p[1]); }
#endif
}

/* 3. (removed) music change: the 2016 client re-applies its music slot table by itself (NormalMusicPlay); the "music does not change"
   reports were (a) a change of the day slot at night and (b) tracks >= 900, which this engine streams from DAT file 49875+track
   (only 900 exists; 901+ hung the music task) - fixed by renumbering the beta tracks to 7NN on the drive. */
/* ---------------------------------------------------------------- 4. Friend List window built before the search data arrived
   YkWndFriendMain::MakeList (0x531F70) fills the rows once, when the window opens; a row whose friend had no search-server data yet
   (entry +252 bit 0) shows the world name ("<unknown>") instead of the character name / area.  While the window is open
   (*(0x7BFB10) = window, +96 = row data, +84 = rows, 136 bytes per row, byte 0 = row kind, 6 = "no character data"), rebuild the
   list the way the game itself does after a category toggle (OnKeyOK: MakeList(win, *(s8 *)(win+88))) once the data is there. */
volatile u32 g_soc_relist_n = 0;
static void soc_friendwin(u32 ctx)
{
    static int tick = 0, tries = 0; u32 win = *(volatile u32 *)0x7BFB10, rows, n, i, stale = 0, have = 0;
    if (++tick < 30) return;
    tick = 0;
    if (!win || !(rows = *(volatile u32 *)(win + 96))) { tries = 0; return; }            /* window closed */
    n = *(volatile u32 *)(win + 84); if (n > 300) return;
    for (i = 0; i < n; i++) if (*(volatile u8 *)(rows + 136 * i) == 6) stale++;
    for (i = 0; i < g_sf_n && i < 200; i++) if (g_sf_live[i].online && (*(volatile u32 *)(ctx + 2704 + i * 256 + 252) & 1)) have++;
    if (stale && have && tries < 5) { tries++; g_soc_relist_n++; ((void (*)(u32, int))0x531F70)(win, *(volatile s8 *)(win + 88)); }
}

/* per frame, game thread */
void soc_frame(void)
{
    u32 ctx = *(volatile u32 *)GAME_CTX;
    if (g_soc_cmd_seq != g_soc_cmd_done) {
        char line[160]; int i;
        for (i = 0; i < 159 && g_soc_cmd[i]; i++) line[i] = g_soc_cmd[i];
        line[i] = 0;
        g_soc_cmd_done = g_soc_cmd_seq;
        if (ctx) { ((void (*)(char *, int))GAME_COMMANDCALC)(line, 0); g_soc_cmd_n++; }
    }
    if (!ctx) return;
    if (!g_soc_state && world_no() != 0xFFFF && *(volatile u32 *)GAME_MSGWIN) soc_start();     /* in the world: start the friend service thread */
    if (g_sf_stage_ready) {
        u32 n = g_sf_stage_n;
        if (n != g_sf_n || memcmp(g_sf_live, g_sf_stage, sizeof(SocFriend) * n)) { g_soc_refresh = 1; g_soc_retry = 15; g_soc_retry_t = 0; }   /* list or online state changed */
        memcpy(g_sf_live, g_sf_stage, sizeof(SocFriend) * n); g_sf_n = n; g_sf_stage_ready = 0;
    } else if (!g_soc_refresh && g_soc_retry > 0 && ++g_soc_retry_t >= 120) {
        /* the game ignores an update while its previous search query is still running: until every online friend has search data
           (entry +252 bit 0), ask again every ~2 s, at most 15 times per change */
        u32 i, missing = 0; g_soc_retry_t = 0;
        for (i = 0; i < g_sf_n && i < 200; i++) if (g_sf_live[i].online && !(*(volatile u32 *)(ctx + 2704 + i * 256 + 252) & 1)) missing++;
        if (missing) { g_soc_refresh = 1; g_soc_retry--; } else g_soc_retry = 0;
    }
    if (g_soc_refresh && world_no() != 0xFFFF && !g_sf_stage_ready) {
        /* ask the game to refresh its friend cache now (gcFriendUpdate(0) at 0x423560: re-reads GetFriendInfo and queries the search server
           for the online friends' area/job/level) instead of waiting for its own timer, so the Friend List window is current */
        g_soc_refresh = 0; g_soc_refreshes++;
        ((int (*)(int))0x423560)(0);
    }
    if (g_pr != g_pw && *(volatile u32 *)GAME_MSGWIN) { say(g_p[g_pr % PN]); g_pr++; }   /* one line per frame */
    soc_friendwin(ctx);
}
