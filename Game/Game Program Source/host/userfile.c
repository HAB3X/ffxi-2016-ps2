/* The 2016 program's per-user file services (kernel slots 1294-1299): settings files (FFXI0.DAT ...), macros, config under USER/<charid hex>/.
   The kernel implements them against the PlayOnline HDD storage; here they are files in the game partition (pfs1:/image/ffxi/USER/<id>/<name>).
   Argument meanings were read from the program's wrappers (0x43E310, 0x43F000, 0x43F220); every call is logged (xf_flush, from the frame hook). */
#include <stdio.h>
#include <string.h>
#include <tamtypes.h>
#include <kernel.h>
extern volatile u32 g_real[];
#define XO_RD 0x0001
#define XO_WR 0x0002
#define XO_CREAT 0x0200
#define XO_TRUNC 0x0400
typedef int (*io_open_t)(const char *, int, int); typedef int (*io_close_t)(int); typedef int (*io_rw_t)(int, void *, int);
#define IO_OPEN(p,f,m) ((io_open_t)g_real[938])(p,f,m)
#define IO_CLOSE(fd) ((io_close_t)g_real[939])(fd)
#define IO_READ(fd,b,n) ((io_rw_t)g_real[940])(fd,b,n)
#define IO_WRITE(fd,b,n) ((io_rw_t)g_real[941])(fd,b,n)
#include "host.h"

volatile u32 g_cur_charid = 0;                    /* set by GetCharacterInfo (net.c) */

#define XFN 32
typedef struct { u32 idx; u32 a[8]; u32 ret; char s[3][40]; } XfEnt;
static volatile XfEnt g_xf[XFN]; static volatile u32 g_xfn = 0, g_xfshown = 0;
static void cpstr(volatile char *d, u32 p) { int i = 0; if (p >= 0x100000 && p < 0x2000000) for (; i < 39 && ((char *)p)[i] >= 0x20 && ((char *)p)[i] < 0x7f; i++) d[i] = ((char *)p)[i]; d[i] = 0; }
static void xf_rec(u32 idx, const u64 *a, u32 ret)
{
    volatile XfEnt *e = &g_xf[g_xfn % XFN];
    e->idx = idx; for (int i = 0; i < 8; i++) e->a[i] = (u32)a[i]; e->ret = ret;
    for (int i = 0; i < 3; i++) cpstr(e->s[i], 0);
    cpstr(e->s[0], (u32)a[0]); cpstr(e->s[1], (u32)a[4]); cpstr(e->s[2], (u32)a[5]);
    g_xfn++;
}
void xf_flush(void)
{
    if (g_xfn - g_xfshown > XFN) g_xfshown = g_xfn - XFN;
    while (g_xfshown < g_xfn) {
        volatile XfEnt *e = &g_xf[g_xfshown++ % XFN];
        printf("[host] XF %d a=%08x %08x %08x %08x %08x %08x %08x ret=%08x s0='%s' s4='%s' s5='%s'\n", (int)e->idx, (unsigned)e->a[0], (unsigned)e->a[1], (unsigned)e->a[2], (unsigned)e->a[3], (unsigned)e->a[4], (unsigned)e->a[5], (unsigned)e->a[6], (unsigned)e->ret, (const char *)e->s[0], (const char *)e->s[1], (const char *)e->s[2]);
    }
}

static const char *hexd = "0123456789abcdef";
static int user_dir(char *out)                    /* pfs1:/image/ffxi/USER/<charid hex>, created on demand */
{
    static const char *base[] = { "pfs1://image/ffxi/USER", 0 };
    u32 id = g_cur_charid; char h[12]; int n = 0;
    if (!id) { h[n++] = '0'; } else { char t[12]; int m = 0; while (id) { t[m++] = hexd[id & 15]; id >>= 4; } while (m) h[n++] = t[--m]; }
    h[n] = 0;
    sprintf(out, "%s/%s", base[0], h);
    return 0;
}
static int clean_name(const char *in, char *out)   /* file name only (no path separators), 1..63 chars */
{
    int i = 0;
    if (!in || (u32)in < 0x100000 || (u32)in >= 0x2000000) return 0;
    for (; i < 63 && in[i] >= 0x20 && in[i] < 0x7f && in[i] != '/' && in[i] != '\\' && in[i] != ':'; i++) out[i] = in[i];
    out[i] = 0; return i;
}

static u32 s_job = 0;

u64 svc_xf1294(u64 a0, u64 a1, u64 a2, u64 a3, u64 a4, u64 a5, u64 a6, u64 a7)       /* file name acceptable? */
{
    char nm[64]; u64 a[8] = { a0, a1, a2, a3, a4, a5, a6, a7 };
    u32 r = clean_name((const char *)(u32)a0, nm) ? 1 : 0;
    xf_rec(1294, a, r); return r;
}
u64 svc_xf1299(u64 a0, u64 a1, u64 a2, u64 a3, u64 a4, u64 a5, u64 a6, u64 a7)       /* size -> size of the scratch buffer the program has to supply */
{
    u64 a[8] = { a0, a1, a2, a3, a4, a5, a6, a7 };
    u32 r = (u32)a0 + 0x40; xf_rec(1299, a, r); return r;
}
u64 svc_xf1296(u64 a0, u64 a1, u64 a2, u64 a3, u64 a4, u64 a5, u64 a6, u64 a7)       /* start a job */
{
    u64 a[8] = { a0, a1, a2, a3, a4, a5, a6, a7 };
    u32 r = ++s_job; xf_rec(1296, a, r); return r;
}
u64 svc_xf1295(u64 a0, u64 a1, u64 a2, u64 a3, u64 a4, u64 a5, u64 a6, u64 a7)       /* job finished? (>0 = yes, ok) */
{
    u64 a[8] = { a0, a1, a2, a3, a4, a5, a6, a7 };
    xf_rec(1295, a, 1); return 1;
}
u64 svc_xf1298(u64 a0, u64 a1, u64 a2, u64 a3, u64 a4, u64 a5, u64 a6, u64 a7)       /* (data, size, scratch, scratch size, name, name) : write the file */
{
    u64 a[8] = { a0, a1, a2, a3, a4, a5, a6, a7 };
    char nm[64], dir[96], path[200]; int ok = -1;
    if (clean_name((const char *)(u32)a4, nm) && (u32)a0 >= 0x100000 && (u32)a0 < 0x2000000 && (u32)a1 <= 0x400000) {
        user_dir(dir); sprintf(path, "%s/%s", dir, nm);
        int fd = IO_OPEN(path, XO_WR | XO_CREAT | XO_TRUNC, 0666);
        if (fd >= 0) { int w = IO_WRITE(fd, (void *)(u32)a0, (int)(u32)a1); IO_CLOSE(fd); ok = (w == (int)(u32)a1) ? 0 : -1; }
    }
    xf_rec(1298, a, (u32)ok); return (u64)(s64)ok;
}
u64 svc_xf1297(u64 a0, u64 a1, u64 a2, u64 a3, u64 a4, u64 a5, u64 a6, u64 a7)       /* readSysFileNow(scratch, ?, out, size, name, name, 0xff): read; -1 = missing */
{
    u64 a[8] = { a0, a1, a2, a3, a4, a5, a6, a7 };
    char nm[64], dir[96], path[200]; int ok = -1;
    if (clean_name((const char *)(u32)a5, nm) && (u32)a2 >= 0x100000 && (u32)a2 < 0x2000000 && (u32)a3 <= 0x400000) {
        user_dir(dir); sprintf(path, "%s/%s", dir, nm);
        int fd = IO_OPEN(path, XO_RD, 0);
        if (fd >= 0) { int r = IO_READ(fd, (void *)(u32)a2, (int)(u32)a3); IO_CLOSE(fd); ok = r >= 0 ? 0 : -1; }
    }
    xf_rec(1297, a, (u32)ok); return (u64)(s64)ok;
}

/* slot 1047: the kernel decrypts + links the Dancer overlay that the program just read into memory (dancer.enc, loaded at 0x7C2210 by 0x4FD500).
   The decrypted overlay (dancer.bin, header word 2 = its load address 0x7C2210) is on the same folder; replace the buffer with it. */
u64 svc_xf1047(u64 a0, u64 a1, u64 a2, u64 a3, u64 a4, u64 a5, u64 a6, u64 a7)
{
    u64 a[8] = { a0, a1, a2, a3, a4, a5, a6, a7 };
    int ok = -1;
    if ((u32)a0 >= 0x100000 && (u32)a0 < 0x1fff000) {
        int fd = IO_OPEN("pfs1://image/ffxi/prog/ps2/dancer.bin", XO_RD, 0);
        if (fd >= 0) { int r = IO_READ(fd, (void *)(u32)a0, (int)(u32)a1); IO_CLOSE(fd); ok = r; FlushCache(0); FlushCache(2); }
    }
    xf_rec(1047, a, (u32)ok); return (u64)(s64)ok;
}

/* ---- alarms for the game: SetAlarm with a watchdog ----
   The game's timed-sleep helper (0x442D00) is Sleep(ms) = SetAlarm(ms*15734/1000 & 0xffff) + WaitSema.  On this system an alarm is sometimes missed by the EE timer (target
   already passed when it is armed: delay 0, or a few hsyncs) and then only fires after the 16-bit timer wraps (4.2 s, 8.4 s ...), or never; the file thread sleeps holding the
   file lock and the whole game stalls.  Here every game alarm is also tracked in a table: tiny delays are completed at once (the sleep is a yield), and a low-priority
   watchdog thread (it only runs when everything else is blocked) fires any alarm that is overdue.  Released/fired alarms are ignored, ids are never reused. */
#include <timer.h>
#define NAL 40
typedef struct { volatile s32 vid, rid; void *cb; void *arg; volatile u32 deadline; u16 clk; volatile u8 state; } AlEnt;   /* state 0 free, 1 pending, 2 claimed */
static AlEnt g_al[NAL]; static volatile u32 g_alnext = 0;
#define HS_CYC 18743u                                  /* EE cycles per hsync (294.912 MHz / 15734 Hz) */
static inline u32 cpu_count(void) { u32 c; __asm__ volatile("mfc0 %0, $9" : "=r"(c)); return c; }
static void al_fire(AlEnt *e)                          /* e is claimed (state 2) */
{
    void (*cb)(s32, u16, void *) = (void (*)(s32, u16, void *))e->cb; s32 vid = e->vid; void *a = e->arg; u16 clk = e->clk;
    e->vid = 0; e->state = 0;
    if (cb) cb(vid, clk, a);
}
static void al_tramp(s32 id, u16 t, void *arg)
{
    AlEnt *e = (AlEnt *)arg;
    if (e->state != 1) return;                         /* released, or already fired by the watchdog */
    e->state = 2; al_fire(e);
}
static int is_io_thread(void)                        /* the game's file thread (static stack at 0x7B6A30) */
{
    ee_thread_status_t st;
    return ReferThreadStatus(GetThreadId(), &st) >= 0 && (u32)st.stack == 0x7b6a30;
}
static s32 al_set(u16 clk, void *cb, void *arg, int irq)
{
    int i, oldi = 0;
    /* (a 1 ms file-thread poll was tried here; it left the overlay's unload loop waiting for a request that never cleared) */
    if (!irq) oldi = DIntr();
    for (i = 0; i < NAL; i++) if (!g_al[i].state) break;
    s32 vid = 0x1000 + (s32)(++g_alnext & 0x3fffff);
    if (i < NAL) { AlEnt *e = &g_al[i]; e->vid = vid; e->cb = cb; e->arg = arg; e->clk = clk; e->rid = -1; e->deadline = cpu_count() + (u32)clk * HS_CYC; e->state = 1; }
    if (!irq && oldi) EIntr();
    if (i >= NAL) return irq ? iSetAlarm(clk ? clk : 1, cb, arg) : SetAlarm(clk ? clk : 1, cb, arg);     /* table full: plain alarm */
    AlEnt *e = &g_al[i];
    if (clk <= 1) {                                    /* a yield: done now, no timer race */
        int o = irq ? 0 : DIntr();
        if (e->state == 1) { e->state = 2; al_fire(e); }
        if (!irq && o) EIntr();
        return vid;
    }
    s32 rid = irq ? iSetAlarm(clk, al_tramp, (void *)e) : SetAlarm(clk, al_tramp, (void *)e);
    if (rid < 0) { e->state = 0; e->vid = 0; return rid; }
    e->rid = rid;
    return vid;
}
static s32 al_rel(s32 vid, int irq)
{
    int i, oldi = 0; s32 rid = -1;
    if (!irq) oldi = DIntr();
    for (i = 0; i < NAL; i++) if (g_al[i].vid == vid && vid && g_al[i].state == 1) { rid = g_al[i].rid; g_al[i].state = 0; g_al[i].vid = 0; break; }
    if (!irq && oldi) EIntr();
    if (rid < 0) return -1;                            /* unknown / already fired */
    return irq ? iReleaseAlarm(rid) : ReleaseAlarm(rid);
}
u64 svc_alarm_set(u64 clk, u64 cb, u64 arg)   { return (u64)(s64)al_set((u16)clk, (void *)(u32)cb, (void *)(u32)arg, 0); }
u64 svc_alarm_iset(u64 clk, u64 cb, u64 arg)  { return (u64)(s64)al_set((u16)clk, (void *)(u32)cb, (void *)(u32)arg, 1); }
u64 svc_alarm_rel(u64 vid)                    { return (u64)(s64)al_rel((s32)vid, 0); }
u64 svc_alarm_irel(u64 vid)                   { return (u64)(s64)al_rel((s32)vid, 1); }

/* watchdog: lowest priority, so it only runs when every other thread is blocked or sleeping */
volatile u32 g_alwd_fired = 0;
static u8 alwd_stack[4096] __attribute__((aligned(16)));
static void alwd(void *arg)
{
    for (;;) {
        for (volatile int w = 0; w < 20000; w++) { }
        u32 now = cpu_count();
        for (int i = 0; i < NAL; i++) {
            AlEnt *e = &g_al[i];
            if (e->state != 1) continue;
            if ((s32)(now - e->deadline) < (s32)(10 * 294912u)) continue;      /* overdue by 10 ms */
            int o = DIntr();
            if (e->state == 1) {
                e->state = 2; s32 rid = e->rid;
                if (o) EIntr();
                if (rid >= 0) iReleaseAlarm(rid);
                g_alwd_fired++;
                int o2 = DIntr(); al_fire(e); if (o2) EIntr();
            } else if (o) EIntr();
        }
    }
}
#ifdef ALARM_VBL
/* the same overdue check, run from the host's vertical-blank interrupt (perf.c) so a missed timer alarm fires at most
   ~17 ms + 2 ms late even while some thread is busy (the watchdog thread above only runs when every thread is blocked; a busy
   main thread let a missed 100 ms alarm wait for the 16-bit timer wrap: an 8.4 s freeze measured in Create Character). */
volatile u32 g_alvbl_fired = 0;
void al_irq_check(void)
{
    u32 now = cpu_count();
    for (int i = 0; i < NAL; i++) {
        AlEnt *e = &g_al[i];
        if (e->state != 1 || (s32)(now - e->deadline) < (s32)(2 * 294912u)) continue;
        e->state = 2; s32 rid = e->rid;
        if (rid >= 0) iReleaseAlarm(rid);
        g_alvbl_fired++; al_fire(e);
    }
}
#endif
void alwd_start(void)
{
    ee_thread_t t; memset(&t, 0, sizeof t);
    t.func = (void *)alwd; t.stack = alwd_stack; t.stack_size = sizeof alwd_stack; t.initial_priority = 100; t.gp_reg = &_gp;
    int id = CreateThread(&t); if (id >= 0) StartThread(id, NULL);
}

/* The game opens some files by bare name (no device): the IME dictionaries ("entryz.dic") and the settings files ("FFXI0.DAT").  The original kernel resolved them against
   its current directory; here they are mapped to the real folders on the game partition. */
const char *map_bare_path(const char *p, char *buf)
{
    int n = 0, i;
    if (!p || (u32)p < 0x100000 || (u32)p >= 0x2000000) return p;
    for (i = 0; p[i] && i < 60; i++) if (p[i] == ':' || p[i] == '/') return p;          /* already a full path */
    n = i; if (!n || p[n]) return p;                                                   /* not a short bare name */
    /* the file name proper is the trailing run of [A-Za-z0-9_.-]; anything before it is a device/prefix code the original kernel interpreted (\x04 for the dictionaries) */
    int st = n;
    while (st > 0) { char c = p[st - 1]; if ((c >= '0' && c <= '9') || (c >= 'A' && c <= 'Z') || (c >= 'a' && c <= 'z') || c == '_' || c == '.' || c == '-') st--; else break; }
    const char *q = p + st; int m = n - st;
    if (m > 4 && q[m - 4] == '.' && (q[m - 3] | 0x20) == 'd' && (q[m - 2] | 0x20) == 'i' && (q[m - 1] | 0x20) == 'c') {
        sprintf(buf, "pfs1://image/ffxi/pol/install/ps2/data/dic/%s", q); return buf;
    }
    if (m >= 9 && q[0] == 'F' && q[1] == 'F' && q[2] == 'X' && q[3] == 'I' && q[m - 4] == '.') {
        char dir[96]; user_dir(dir); sprintf(buf, "%s/%s", dir, q); return buf;
    }
    return p;
}

/* ---- input method (sqImm*) in direct-input mode: the game's text boxes ask the IME layer for a context and the composition state before they accept a typed
   character.  English keyboards do not use the IME: context valid, IME closed, nothing being composed, setters succeed. ---- */
u64 svc_imm_true(void)  { return 1; }
u64 svc_imm_false(void) { return 0; }
u64 svc_imm_ctx(void)   { return 1; }                                  /* sqImmGetContext: a (fake) input context handle */
u64 svc_imm_getconv(u64 ctx, u64 pconv, u64 psent)                      /* sqImmGetConversionStatus(ctx, &conversion, &sentence) */
{
    if ((u32)pconv >= 0x100000 && (u32)pconv < 0x2000000) *(volatile u32 *)(u32)pconv = 0;
    if ((u32)psent >= 0x100000 && (u32)psent < 0x2000000) *(volatile u32 *)(u32)psent = 0;
    return 1;
}

/* 1109 sqPlayOnlineVulgarMapCharaEntryDictionary(buf, size): "maps" the name-filter dictionary (entryz.dic) and returns a non-zero handle (the game treats 0 as "dictionary
   not loaded" and then refuses every character name with error 322); 1110 sqPlayOnlineVulgarCharaEntryTest(handle, name, len): 1 = the name contains a prohibited word,
   0 = fine.  The server does its own name checks, so no word is ever reported here. */
u64 svc_vulgar_map(u64 buf, u64 size) { return buf ? buf : 1; }
u64 svc_vulgar_test(u64 h, u64 name, u64 len) { return 0; }

/* system time services (not part of the lifted kernel, so they used to return 0 and every game clock - the Vana'diel clock, the zone-in timers - stood still):
   696 sqGetTickCount() = milliseconds since start; 689 sqGetCalendarTime(&secs) = seconds since 1970 (fixed start date + run time), returns 0. */
static u64 tm_total; static u32 tm_last; static int tm_init;
static u64 tm_cycles(void)
{
    u32 c; __asm__ volatile("mfc0 %0, $9" : "=r"(c));
    if (!tm_init) { tm_init = 1; tm_last = c; }
    tm_total += (u32)(c - tm_last); tm_last = c; return tm_total;
}
u64 svc_tickcount(void) { return (u32)(tm_cycles() / 294912u); }
u64 svc_caltime(u64 out)
{
    u32 secs = 1791072000u + (u32)(tm_cycles() / 294912000u);                 /* 2026-10-04 00:00:00 UTC + run time */
    if ((u32)out >= 0x100000 && (u32)out < 0x2000000) *(volatile u32 *)(u32)out = secs;
    return 0;
}
