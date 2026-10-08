/* 2016 host probe: puts the 2016 program at 0x280000, points every kernel slot at a logger, calls its entry. */
#ifndef DEV_IP
#define DEV_IP "0.0.0.0"
#endif
#ifndef DEV_PASS
#define DEV_PASS "ff.11"
#endif
#ifndef DEV_ACCT
#define DEV_ACCT "YAAA7839"
#endif
#include <stdio.h>
#include <string.h>
#include <tamtypes.h>
#include <kernel.h>
#include <delaythread.h>
#include <sifrpc.h>
#include <debug.h>
#include "host.h"
#ifdef LOGOUT_FIX
volatile int g_in_world = 0;                         /* set by the menu hook (devdlg.c): 1 while playing, 0 on the title / character screens */
static u32 heap_fallback(u32 a0, u32 a1, u32 a2, u32 a3)    /* the allocator's other-heap attempt (call at 0x281678) */
{
    return g_in_world ? ((u32 (*)(u32, u32, u32, u32))0x2817A0)(a0, a1, a2, a3)       /* bottom-up: keeps the freed world memory in one piece */
                      : ((u32 (*)(u32, u32, u32, u32))0x281930)(a0, a1, a2, a3);      /* top-down: the game's own choice */
}
#else
volatile int g_in_world = 0;
#endif

#ifndef NO_SEACOM_BOX
/* target of the jump patched in at 0x3A7558 (/seacom handler, argument count < 2). Runs in the handler's frame (ra, s0-s2 are
   saved there). Search-menu object *(0x7BF810) present: open the Edit Comment box (0x520490(obj, 0)) and leave through 0x3A7614
   (v0 = s2 = command id, positive = no error line). No object: the original error path (0x3A7618 with v0 = -s2). */
__asm__(".set push\n.set noreorder\n.set noat\n"
        ".globl seacom_tramp\n"
        "seacom_tramp:\n"
        "  lui   $1, 0x7c\n"
        "  lw    $4, -2032($1)\n"
        "  beqz  $4, 1f\n"
        "  nop\n"
        "  jal   0x520490\n"
        "  move  $5, $0\n"
        "  j     0x3a7614\n"
        "  nop\n"
        "1:j     0x3a7618\n"
        "  subu  $2, $0, $18\n"
        ".set pop\n");
#endif

extern u8 slot_stubs[];
extern const LiftSet lift_k_set;
void net_install(u32 *tab); void lockbug_install(const LiftSet *s);
int iop_init(void); int iop_init_sony(void); int input_init(void); void input_hid_prepare(void); void input_hid_go(void); extern volatile u32 g_hid_ready;
u32 svc_scePadRead(), svc_scePadInfoAct(), svc_scePadInfoComb(), svc_scePadInfoMode(), svc_scePadSetActDirect(), svc_scePadSetActAlign(), svc_scePadGetState(), svc_scePadGetReqState(), svc_scePadSetMainMode(), svc_scePadInfoPressMode(), svc_scePadEnterPressMode(), svc_scePadExitPressMode();
u64 svc_imm_true(), svc_imm_false(), svc_imm_ctx(), svc_imm_getconv(), svc_vulgar_map(), svc_vulgar_test(), svc_tickcount(), svc_caltime();
u64 svc_alarm_set(), svc_alarm_iset(), svc_alarm_rel(), svc_alarm_irel(), svc_xf1047(), svc_xf1294(), svc_xf1295(), svc_xf1296(), svc_xf1297(), svc_xf1298(), svc_xf1299();
u32 svc_sifsetdma(), svc_sifdmastat(), svc_callrpc(), svc_bindrpc(), svc_checkstatrpc(), svc_loadmod(const char *path, int arg_len, void *args), svc_sceOpen(), svc_sceClose(), svc_sceRead(), svc_sceWrite(), svc_sceLseek(), svc_sceGetstat(), svc_sceMount(), svc_sceUmount();

#define LOGN 1024
typedef struct { u32 idx, ra, a0, a1, a2, a3, t0, t1; } LogEnt;
volatile LogEnt g_log[LOGN];          /* readable over PINE; address from nm */
volatile u32 g_logn = 0, g_calls = 0;
volatile u32 g_seen[NSLOTS];          /* per-slot call counts */
volatile u32 g_stage = 0;             /* 1 host up, 2 entering the 2016 program, 3 returned */
volatile u32 g_ret = 0;

#define RINGN 256
volatile u32 g_ring[RINGN][2]; volatile u32 g_ringp = 0;   /* last calls: slot, ra */

/* Universal call tracer: every slot, including the ones implemented for real or lifted, goes through the slot stub ->
   trap_common -> trap_c.  g_real[idx] holds the real implementation (0 = log-only slot).  Entry + return are recorded in
   g_tr (PINE readable; see pk.py tr).  Noisy slots are recorded only for their first TR_FIRST calls. */
volatile u32 g_real[NSLOTS];
#define TRN 512
typedef struct { u32 idx, ra, a0, a1, a2, a3, ret, seq; char s0[32]; char s1[64]; } TrEnt;
volatile TrEnt g_tr[TRN]; volatile u32 g_trn = 0;
#define TR_FIRST 6
static int tr_always(u32 idx) { return idx == 84 || idx == 93 || idx == 94 || idx == 421 || idx == 956 || idx == 957 || idx == 969 || idx == 1026 || (idx >= 900 && idx <= 960) || (idx >= 1290 && idx <= 1300); }
static void tr_str(volatile char *d, u32 p, int max)
{
    int i = 0;
    if (p >= 0x100000 && p < 0x2000000) for (; i < max - 1 && ((char *)p)[i] >= 0x20 && ((char *)p)[i] < 0x7f; i++) d[i] = ((char *)p)[i];
    d[i] = 0;
}
typedef u64 (*svc8)(u64, u64, u64, u64, u64, u64, u64, u64);
extern u64 call8s(u32 fn, u64 *regs, u64 *stk);

static int hid_slot(u32 i) { return (i >= 95 && i <= 124) || i == 705 || i == 706 || i == 707 || i == 1055 || i == 1056 || i == 1057 || i == 1101 || i == 1137 || i == 1138 || i == 1281 || i == 1514; }
volatile u32 g_uon = 0; volatile char g_uop[400][32];
volatile u32 g_opn = 0, g_opr[40], g_opf[40]; volatile char g_opp[40][48];
volatile u32 g_failf[120]; volatile u32 g_failn = 0, g_failr[120]; volatile char g_failp[120][48];
volatile u32 g_failtot = 0;                            /* every failed file open / stat (g_failp keeps each distinct path once) */
volatile u32 g_err_a0[16], g_err_ra[16], g_err_n;
volatile u32 g_ikq[16], g_ikw = 0, g_ikr = 0, g_ikcur = 0;
volatile u32 g_kbd_new = 0, g_kbd_w = 0; volatile u8 g_kbd_ring[32];

/* call recorder: every service call except the per-frame spam, as {cpu count, slot, caller, a0}; read it out of a savestate (g_cr / g_crn) */
typedef struct { u32 cyc; u16 idx, pad; u32 ra, a0; } CrEnt;
#ifndef CRN
#define CRN 1024                                       /* 1024 (was 4096) to make room for the packed-file layer */
#endif
volatile CrEnt g_cr[CRN]; volatile u32 g_crn = 0;
static int cr_skip(u32 i)
{
    switch (i) { case 100: case 101: case 102: case 103: case 109: case 113: case 483: case 518: case 519: case 520: case 521: case 522: case 557: case 558: case 559:
                 case 580: case 581: case 582: case 587: case 592: case 596: case 598: case 689: case 696: case 705: case 1055: case 1101: case 500: case 677: case 678: case 679: case 692: case 693: case 694: case 706: case 707: return 1; }
    if (i == 104 || (i >= 108 && i <= 124)) return 1;
    if (i == 98 || i == 737) return 1;
    return 0;
}
u64 trap_c(u32 idx, u64 *r)
{
#ifndef RELEASE
    volatile CrEnt *crc = 0;
    if (idx < NSLOTS && !cr_skip(idx)) { u32 cyc; __asm__ volatile("mfc0 %0, $9" : "=r"(cyc)); crc = &g_cr[g_crn++ & (CRN - 1)]; crc->cyc = cyc; crc->idx = (u16)idx; crc->pad = 0xdead; crc->ra = (u32)r[0]; crc->a0 = (u32)r[1]; }
#endif
    if (idx >= NSLOTS) { static int nbad = 0; if (nbad < 20) { nbad++; hlog(9, idx, (u32)r[0], (u32)r[1], (u32)r, 0, 0, "BAD SLOT idx/ra/a0/r:", 0, 0); } return 0; }
    { extern volatile int g_input_block; if (g_input_block && idx < NSLOTS && hid_slot(idx)) { g_calls++; return 0; } }
#ifdef INPUT_HID_INIT
    if (idx < NSLOTS && hid_slot(idx) && !g_hid_ready) { g_calls++; return 0; }   /* kbd/mouse not initialised yet: "no input" (sqMouseOpen: handle 0, which is what the real open returns) */
#endif
    g_calls++;
#ifndef RELEASE
    g_ring[g_ringp & (RINGN - 1)][0] = idx; g_ring[g_ringp & (RINGN - 1)][1] = (u32)r[0]; g_ringp++;
#endif
    u32 n = 0;
    if (idx < NSLOTS) n = ++g_seen[idx];
    if (idx < NSLOTS && n == 1 && !g_real[idx]) {      /* log the first call of each unimplemented slot in full */
        hlog(1, idx, (u32)r[0], (u32)r[1], (u32)r[2], (u32)r[3], (u32)r[4], (const char *)(u32)r[1], (const char *)(u32)r[2], (const char *)(u32)r[3]);
        if (g_logn < LOGN) {
            volatile LogEnt *e = &g_log[g_logn++];
            e->idx = idx; e->ra = (u32)r[0]; e->a0 = (u32)r[1]; e->a1 = (u32)r[2]; e->a2 = (u32)r[3];
            e->a3 = (u32)r[4]; e->t0 = (u32)r[5]; e->t1 = (u32)r[6];
        }
    }
    u64 ret = 0;
#ifndef RELEASE
    volatile TrEnt *e = 0;
    if (idx < NSLOTS && (n <= TR_FIRST || (tr_always(idx) && g_trn < TRN))) {   /* record entry first (calls may never return) */
        e = &g_tr[g_trn % TRN];
        e->idx = idx; e->ra = (u32)r[0]; e->a0 = (u32)r[1]; e->a1 = (u32)r[2]; e->a2 = (u32)r[3]; e->a3 = (u32)r[4];
        e->ret = 0xdead0000; e->seq = (g_trn & 0xffff) | ((u32)(((u32)r >= 0x100000) ? GetThreadId() : 0) << 16);
        if (idx == 956) e->a3 = (u32)r[5];            /* sceMount: record the 5th argument (arglen) instead of a3 */
        if (idx == 491) { e->a2 = ((u32 *)(u32)r[1])[1]; e->a3 = ((u32 *)(u32)r[1])[2]; }   /* CreateThread: record func, stack */
        if (idx >= 900 && idx <= 960) { tr_str(e->s0, (u32)r[1], 32); tr_str(e->s1, (u32)r[2], 64); } else { e->s0[0] = 0; e->s1[0] = 0; }
        if (idx == 940 && (u32)r[1] < 32) { volatile u32 *cx = (volatile u32 *)(0x249fc0 + 16 * (u32)r[1]); ((volatile u32 *)e->s1)[0] = cx[0]; ((volatile u32 *)e->s1)[1] = cx[1]; ((volatile u32 *)e->s1)[2] = cx[2]; ((volatile u32 *)e->s1)[3] = cx[3]; }   /* sceRead: the file context entry (donor 0x249fc0 + 16*fd) as seen at entry */
        g_trn++;
    }
    int oi = -1;
#endif
    if (idx == 938 || idx == 951) {                                                             /* bare file names (dictionaries, settings files) get a real path */
        extern const char *map_bare_path(const char *, char *);
        static char bp[4][100]; static u32 bpn = 0; char *b = bp[bpn++ & 3];
        const char *np = map_bare_path((const char *)(u32)r[1], b); if (np != (const char *)(u32)r[1]) r[1] = (u64)(u32)np;
    }
#ifndef RELEASE
    if ((idx == 938 || idx == 951) && (u32)r[1] >= 0x100000 && (u32)r[1] < 0x2000000) {        /* ring of every file open / stat: path + result (0xdead0000 while still in the call); read it with PINE */
        oi = (int)(g_opn++ % 40); const char *pp = (const char *)(u32)r[1]; int k;
        for (k = 0; k < 47 && pp[k] >= 0x20 && pp[k] < 0x7f; k++) g_opp[oi][k] = pp[k];
        g_opp[oi][k] = 0; g_opr[oi] = 0xdead0000; g_opf[oi] = (u32)r[2];
        { int tl = k > 30 ? k - 30 : 0, q, z;                                                    /* unique-path log: last 30 chars of every distinct path opened */
          for (q = 0; q < (int)g_uon && q < 400; q++) { for (z = 0; z < 30 && g_uop[q][z] == pp[tl + z]; z++) if (!pp[tl + z]) break; if (z == 30 || (!pp[tl + z] && g_uop[q][z] == 0)) break; }
          if (q == (int)g_uon && q < 400) { for (z = 0; pp[tl + z] && z < 30; z++) g_uop[q][z] = pp[tl + z]; g_uop[q][z] = 0; g_uon++; } }
    }
#endif
    /* PS2 fix: file gate. While the network modules start (IOP stack + Ethernet bring-up), the game's HDD requests are held here: in PCSX2 a
       game file request in flight during sqInitSocketAPI left both waiting forever (NETDIAG15/16.log: file thread + net thread stuck). */
    int fgated = 0;
    if (idx >= 938 && idx <= 955) {
        extern volatile int g_fio_gate, g_fio_busy, g_fio_held;
        int o = DIntr(), held = 0;
        while (g_fio_gate) { if (o) EIntr(); if (!held) { held = 1; g_fio_held++; } DelayThread(2000); o = DIntr(); }
        g_fio_busy++; fgated = 1;
        if (o) EIntr();
    }
#ifdef XCOMP
    if (idx >= 938 && idx <= 951) { extern int xc_pre(u32, u64 *, u64 *); if (xc_pre(idx, r, &ret)) goto xc_done; }   /* game files */
#endif
    if (idx < NSLOTS && g_real[idx]) {
        if (idx >= 548 && idx <= 570) ret = call8s(g_real[idx], &r[1], (u64 *)((u32)r + 0x60));   /* graphics SDK (sceGsSetDefClear..) reads its 9th+ arguments from the caller's stack */
        else ret = ((svc8)g_real[idx])(r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8]);
    }
#ifdef XCOMP
    if (idx == 938 || idx == 951) { extern void xc_post(u32, u64 *, u64); xc_post(idx, r, ret); }
    xc_done:
#endif
#ifdef NETDIAG
    if ((idx == 938 || idx == 951) && (int)ret < 0 && g_real[idx] && (u32)r[1] >= 0x100000 && (u32)r[1] < 0x2000000) {
        /* PS2 fix: a CD-only file (file ids listed in the disc's CDTABLE: only on the DVD, not installed on the HDD). The game asks for it as
           ROM/0/<id>.DAT (HDD table) or CDROM/<id/30>/<id%30>.DAT (net.c fs_path_cd); when that open fails, try the copy in the game folder
           (pfs1:/image/ffxi/CDROM/...), then the disc (cdrom0:\\CDROM\\...). */
        extern const u8 g_cd_ids[100];
        const char *p = (const char *)(u32)r[1], *q; int id = -1;
        if ((q = strstr(p, "/image/ffxi/ROM/0/"))) { int f = 0; const char *c = q + 18; while (*c >= '0' && *c <= '9') f = f * 10 + (*c++ - '0'); if (!strcmp(c, ".DAT") && f > 0 && f < 100 && g_cd_ids[f]) id = f; }
        else if ((q = strstr(p, "CDROM")) && (q[5] == '/' || q[5] == '\\') && (q[7] == '/' || q[7] == '\\')) { int d = q[6] - '0', f = 0; const char *c = q + 8; while (*c >= '0' && *c <= '9') f = f * 10 + (*c++ - '0'); if (d >= 0 && d < 4 && f < 30) id = d * 30 + f; }
        if (id > 0) {
            static char alt[4][64]; static u32 an = 0; u64 r1 = r[1];
#ifdef CD_DISC_FALLBACK
            for (int pass = 0; pass < 2 && (int)ret < 0; pass++) {
#else       /* NETDIAG32: no cdrom0: try - on a console with no disc in the drive that open may never return */
            for (int pass = 0; pass < 1 && (int)ret < 0; pass++) {
#endif
                char *a = alt[an++ & 3]; int n = 0; const char *t; int d = id / 30, f = id % 30;
                if (pass == 0) t = "pfs1://image/ffxi/CDROM/";                 /* the copy in the game folder */
                else t = "cdrom0:\\CDROM\\";
                while (*t) a[n++] = *t++;
                a[n++] = (char)('0' + d); a[n++] = pass ? '\\' : '/';
                if (f >= 10) a[n++] = (char)('0' + f / 10);
                a[n++] = (char)('0' + f % 10); a[n++] = '.'; a[n++] = 'D'; a[n++] = 'A'; a[n++] = 'T';
                if (pass) { a[n++] = ';'; a[n++] = '1'; }
                a[n] = 0;
                if (!strcmp(a, p)) continue;                                  /* the game already asked for exactly this */
                r[1] = (u64)(u32)a;
                ret = ((svc8)g_real[idx])(r[1], r[2], r[3], r[4], r[5], r[6], r[7], r[8]);
                { static int nl = 0; if (nl < 60) { nl++; hlog(2, idx, (u32)ret, 0, 0, 0, 0, a, 0, 0); } }
            }
            if ((int)ret < 0) r[1] = r1;
        }
    }
#endif
    if (fgated) { extern volatile int g_fio_busy; int o = DIntr(); g_fio_busy--; if (o) EIntr(); }
#ifndef RELEASE
    if (oi >= 0) g_opr[oi] = (u32)ret;
    if ((idx == 938 || idx == 951 || idx == 939) && (int)ret < 0 && g_failn < 120 && (u32)r[1] >= 0x100000 && (u32)r[1] < 0x2000000) {      /* failed file open / stat: remember the path (each distinct path once) */
        const char *pp = (const char *)(u32)r[1]; int k, dup = 0;
        g_failtot++;
        for (int j = 0; j < (int)g_failn && !dup; j++) { dup = 1; for (k = 0; k < 47; k++) { char c = (pp[k] >= 0x20 && pp[k] < 0x7f) ? pp[k] : 0; if (c != g_failp[j][k]) { dup = 0; break; } if (!c) break; } }
        if (dup) goto fail_done; for (k = 0; k < 47 && pp[k] >= 0x20 && pp[k] < 0x7f; k++) g_failp[g_failn][k] = pp[k]; g_failp[g_failn][k] = 0; g_failr[g_failn] = (u32)ret; g_failf[g_failn] = (u32)r[2]; g_failn++;
    }
    fail_done:;
#endif
    { extern volatile u32 g_ikq[16], g_ikw, g_ikr, g_ikcur;                            /* test driver: synthetic key presses {keycode<<8|ascii}, queued over PINE (drive.py) */
      if (idx == 104 && g_ikr != g_ikw) { g_ikcur = g_ikq[g_ikr++ & 15] | 0x10000; ret = 1; }
      else if (idx == 104) g_ikcur = 0;
      else if (idx == 106 && (g_ikcur & 0x10000)) ret = (g_ikcur >> 8) & 0xff;
      else if (idx == 107 && (g_ikcur & 0x10000)) ret = g_ikcur & 0xff; }
    if (idx == 104 && (int)ret > 0 && g_real[107]) {                                  /* a keyboard update with new keys: take the typed character for the developer page, whether or not the game reads it */
        int a = (g_ikcur & 0x10000) ? (int)(g_ikcur & 0xff) : (int)((svc8)g_real[107])(0, 0, 0, 0, 0, 0, 0, 0);
        { static int la = -1; static u32 lt = 0; u32 now; __asm__ volatile("mfc0 %0, $9" : "=r"(now));       /* a single key press is reported on several consecutive polls: drop the same character within 120 ms */
          if (a > 0 && a < 0x80 && !(a == la && (u32)(now - lt) < 35000000u)) g_kbd_ring[g_kbd_w++ & 31] = (u8)a;
          if (a > 0) { la = a; lt = now; } }
    }
#ifdef INPUT_HID_INIT
    if (idx == 956 && (int)ret >= 0) input_hid_go();
#endif
#ifdef NET_START_AT_MOUNT   /* NETDIAG15 started here: in PCSX2 the bring-up's SIF RPC traffic beside the game's boot loading deadlocked both (NETDIAG15.log) - off */
    if (idx == 956 && (int)ret >= 0 && (u32)r[1] >= 0x100000 && (u32)r[1] < 0x2000000 && !strncmp((const char *)(u32)r[1], "pfs1", 4)) {
        extern void net_start_async(void); extern volatile int g_net_early;
        g_net_early = 1; net_start_async();            /* PS2 fix: start now (the modules live on pfs1:), not at the first network call; no printing on this game thread */
    }
#endif
#ifndef RELEASE
    if (crc) crc->pad = (u16)ret;
    if (e) { e->ret = (u32)ret; if (idx == 940 && (u32)r[2] >= 0x100000 && (u32)r[2] < 0x1fff000) { volatile u32 *b = (volatile u32 *)((u32)r[2] | 0x20000000); u32 nz = 0; for (int i = 0; i < 512; i++) nz += b[i] != 0; e->a3 = nz; } }   /* sceRead: number of non-zero words among the first 512 of the destination after the call (uncached view) */
#endif
    return ret;                                         /* log-only slots: success / null */
}

/* ---- DMA: sceDmaChan = the channel's hardware register block (CHCR at +0, MADR +0x10, QWC +0x20, TADR +0x30) ---- */
static const u32 dma_base[10] = { 0x10008000, 0x10009000, 0x1000A000, 0x1000B000, 0x1000B400,
                                  0x1000C000, 0x1000C400, 0x1000C800, 0x1000D000, 0x1000D400 };
static u32 svc_sceDmaGetChan(u32 ch) { return ch < 10 ? dma_base[ch] : 0; }
static void dma_wait(volatile u32 *chcr) { u32 n = 0x1000000; while ((*chcr & 0x100) && --n) { } if (!n) *chcr &= ~0x100u; }
static u32 svc_sceDmaSend(volatile u32 *c, u32 tadr)       /* source-chain mode */
{
    dma_wait(c);
    if (c[0x30 / 4] != 0xffffffffu) c[0x30 / 4] = tadr;
    c[0x20 / 4] = 0;
    c[0] = (c[0] & ~0xdu) | 0x105;
    return (u32)c;
}
static u32 svc_sceDmaSendN(volatile u32 *c, u32 madr, u32 qwc)   /* normal mode, qwc quadwords */
{
    dma_wait(c);
    if (c[0x10 / 4] != 0xffffffffu) c[0x10 / 4] = madr;
    c[0x20 / 4] = qwc;
    c[0] = (c[0] & ~0xdu) | 0x101;
    return (u32)c;
}
static u32 svc_sceDmaSync(volatile u32 *c, u32 mode, u32 timeout)
{
    if (mode == 1) return (c[0] >> 8) & 1;
    u32 n = timeout ? timeout : 0x1000000;
    while ((c[0] & 0x100) && --n) { }
    return 0;
}
#ifndef POL_ARG
#define POL_ARG 0
#endif
volatile u32 g_pol_arg = POL_ARG;                    /* GetArgument (slot 421): XiPolArguments launch mode the POL kernel would have stored */
static u32 svc_getarg(void) { return g_pol_arg; }
/* sceGsSyncPath(0): wait for VIF1/GIF DMA to finish.
   6 Oct 2026: the old version gave up after 0x8000 loops and then CLEARED the channel's STR bit, i.e. it aborted
   texture/geometry transfers that were still running -> half-uploaded textures (floors flashing green/purple noise and
   checker blocks, different every frame). -DGSSYNC_WAIT makes it wait like libgraph (up to 0x1000000 loops) and report -1 without touching the channel.
   NOT the default: tests on 6 Oct showed it was not the cause of the floor noise (0 aborts counted while the noise
   showed) and the Create Character preview stayed black with it. Default = the original behaviour + counters. */
volatile u32 g_syncpath_timeouts = 0, g_syncpath_maxspin = 0;
static u32 svc_gssyncpath(u32 mode)
{
#ifdef GSSYNC_WAIT
    if (mode) return ((*(volatile u32 *)0x10009000 | *(volatile u32 *)0x1000A000) & 0x100) ? 1 : 0;
#else
    if (mode) return 0;
#endif
    static const u32 chs[2] = { 0x10009000, 0x1000A000 };
    u32 r = 0;
    for (int i = 0; i < 2; i++) {
        volatile u32 *c = (volatile u32 *)chs[i];
#ifndef GSSYNC_WAIT
        u32 n = 0x8000;
#else
        u32 n = 0x1000000;
#endif
        u32 n0 = n;
        while ((*c & 0x100) && --n) { }
        if (n0 - n > g_syncpath_maxspin) g_syncpath_maxspin = n0 - n;
        if (!n) {
            g_syncpath_timeouts++; r = (u32)-1;
#ifndef GSSYNC_WAIT
            *c &= ~0x100u; r = 0;
#endif
        }
    }
    return r;
}
static u32 svc_one(void) { return 1; }
static u32 svc_zero(void) { return 0; }

/* ---- real services: the EE kernel calls map 1:1 onto the SDK (same arguments, same results) ---- */
#include <semaphore.h>
#include <timer.h>
static int hot_slot(int k)
{
    switch (k) { case 483: case 500: case 518: case 519: case 520: case 521: case 522: case 558: case 559: case 580: case 581: case 582: case 587: return 1; }
    return 0;
}
static void install_real(u32 *tab)
{
#define REAL(idx, fn) tab[idx] = (u32)(fn)
    REAL(483, FlushCache);            /* FlushCache(mode)            */
    REAL(485, SyncDCache);            /* SyncDCache(start,end)       */
    REAL(487, InvalidDCache);         /* InvalidDCache(start,end)    */
    REAL(491, CreateThread);          /* CreateThread(ee_thread_t*)  */
    REAL(492, DeleteThread);
    REAL(493, StartThread);           /* StartThread(id,arg)         */
    REAL(496, TerminateThread);
    REAL(498, ChangeThreadPriority);
    REAL(500, RotateThreadReadyQueue);
    REAL(504, GetThreadId);
    REAL(505, ReferThreadStatus);     /* ReferThreadStatus(id, status*) */
    REAL(516, CreateSema);            /* CreateSema(ee_sema_t*)      */
    REAL(517, DeleteSema);
    REAL(518, SignalSema);
    REAL(519, iSignalSema);
    REAL(520, WaitSema);              /* first call a0=sema id, 1 argument: a WaitSema, not DIntr */
    REAL(523, ReferSemaStatus);
    REAL(533, svc_alarm_set);         /* SetAlarm(clock,handler,arg); a delay of 0 becomes 1 (see userfile.c) */
    REAL(535, svc_alarm_rel);
    /* the rest of the EE syscall block, in BIOS order (slot order = syscall order; confirmed against the donor wrappers) */
    REAL(494, ExitThread);            REAL(495, ExitDeleteThread);
    REAL(497, iTerminateThread);      REAL(499, iChangeThreadPriority);
    REAL(501, iRotateThreadReadyQueue); REAL(502, ReleaseWaitThread);   REAL(503, iReleaseWaitThread);
    REAL(506, iReferThreadStatus);
    REAL(507, SleepThread);           REAL(508, WakeupThread);          REAL(509, iWakeupThread);
    REAL(510, CancelWakeupThread);    REAL(511, iCancelWakeupThread);
    REAL(512, SuspendThread);         REAL(513, iSuspendThread);
    REAL(514, ResumeThread);          REAL(515, iResumeThread);
    REAL(521, PollSema);              REAL(522, iPollSema);
    REAL(534, svc_alarm_iset);        REAL(536, svc_alarm_irel);
    REAL(1108, GetMemorySize);
    REAL(580, svc_sceDmaGetChan); REAL(581, svc_sceDmaSend); REAL(582, svc_sceDmaSendN); REAL(587, svc_sceDmaSync);
#ifndef SONY_IOP
    REAL(938, svc_sceOpen); REAL(939, svc_sceClose); REAL(940, svc_sceRead); REAL(941, svc_sceWrite); REAL(942, svc_sceLseek);
    REAL(951, svc_sceGetstat); REAL(956, svc_sceMount); REAL(957, svc_sceUmount);
#endif
    REAL(1047, svc_xf1047); REAL(1294, svc_xf1294); REAL(1295, svc_xf1295); REAL(1296, svc_xf1296); REAL(1297, svc_xf1297); REAL(1298, svc_xf1298); REAL(1299, svc_xf1299);
    /* input method (sqImm*): the real lifted kernel code must run - its lock is created in sqImmInit3; stubbing 709-744/1271 silently drops all typed characters */
    REAL(696, svc_tickcount); REAL(689, svc_caltime);   /* system time (userfile.c) */
    REAL(1109, svc_vulgar_map); REAL(1110, svc_vulgar_test);   /* character-name filter (userfile.c) */
    REAL(93, svc_loadmod);           /* kernel 'load IOP module from path' (a0=path): iopsound.irx from the HDD */
    REAL(677, svc_bindrpc); REAL(678, svc_callrpc); REAL(679, svc_checkstatrpc);
    REAL(672, svc_sifsetdma); REAL(674, svc_sifdmastat);
    REAL(421, svc_getarg);
    REAL(592, svc_scePadRead); REAL(593, svc_scePadInfoAct); REAL(594, svc_scePadInfoComb); REAL(595, svc_scePadInfoMode);
    REAL(596, svc_scePadSetActDirect); REAL(597, svc_scePadSetActAlign); REAL(598, svc_scePadGetState); REAL(599, svc_scePadGetReqState);
    REAL(600, svc_scePadSetMainMode); REAL(601, svc_scePadInfoPressMode); REAL(602, svc_scePadEnterPressMode); REAL(603, svc_scePadExitPressMode);
    REAL(84, svc_one);               /* sceCdMmode: media mode set ok */
#ifdef FEP_FIX
    { extern void fep_install(u32 *); fep_install(tab); }   /* 6 Oct 2026: text-box character insert (sqFepKatakanaToFullshape, ime.c) - fixes the on-screen keyboard and the typing beep */
#endif
}

/* Silent sound stand-in: the game queues sound commands in shared memory (producer index at 0x5BFFE8) and waits until the
   sound driver's consumer index (0x5BFFEC) catches up. With no driver, the consumer is simply mirrored from the producer. */
static void sound_consumer(s32 id, u16 time, void *arg)
{
    volatile u32 *q = (volatile u32 *)0x5bffe8;
    q[1] = q[0];
    hlog_poke();
    iSetAlarm(16, sound_consumer, 0);                 /* about 1 ms */
}

/* thread table snapshot (PINE readable, pk.py thr): status, wait type/id and entry of every EE thread, refreshed every ~64 ticks */
typedef struct { u32 status, func, stack, prio, waitType, waitId, wakeups, valid; } ThrEnt;
volatile ThrEnt g_thr[32];
typedef struct { u32 count, max, init, waiters, valid; } SemEnt;
volatile SemEnt g_sem[64];
static void log_tick(s32 id, u16 time, void *arg)
{
    static u32 n = 0;
    { extern volatile u32 g_ticks; g_ticks++; }       /* NETDIAG: elapsed-time base for the network log */
    hlog_poke();
    if ((++n & 63) == 0)
        for (int t = 0; t < 32; t++) {
            ee_thread_status_t st;
            int r = iReferThreadStatus(t, &st);
            g_thr[t].valid = r >= 0 ? 1 : 0;
            if (r >= 0) { g_thr[t].status = st.status; g_thr[t].func = (u32)st.func; g_thr[t].stack = (u32)st.stack; g_thr[t].prio = st.current_priority;
                          g_thr[t].waitType = st.waitType; g_thr[t].waitId = st.waitId; g_thr[t].wakeups = st.wakeupCount; }
        }
    if ((n & 63) == 0)
        for (int t = 0; t < 64; t++) { ee_sema_t sm; int r = iReferSemaStatus(t, &sm); g_sem[t].valid = r >= 0; if (r >= 0) { g_sem[t].count = sm.count; g_sem[t].max = sm.max_count; g_sem[t].init = sm.init_count; g_sem[t].waiters = sm.wait_threads; } }
    iSetAlarm(32, log_tick, 0);
}


#ifdef THRDBG
/* sampling profiler: every 2 ms record the interrupted program counter (read the ring from a savestate: g_pcs / g_pcn) */
volatile u32 g_pcs[8192]; volatile u32 g_pcn = 0;
static void prof_tick(s32 id, u16 time, void *arg)
{
    u32 epc; __asm__ volatile("mfc0 %0, $14" : "=r"(epc));
    g_pcs[g_pcn++ & 8191] = epc;
    iSetAlarm(32, prof_tick, 0);
}
#endif
int main(int argc, char **argv)
{
    hlog_start();
    { extern int g_boot_disc; g_boot_disc = !(argc > 0 && argv && argv[0] && strncmp(argv[0], "cdrom", 5));    /* where were we started from? */
      printf("[host] started as '%s' (%s)\n", argc > 0 && argv && argv[0] ? argv[0] : "?", g_boot_disc ? "disc" : "not the disc: embedded IOP modules"); }
    /* no logger alarm: hlog_kick() is called from the frame hook and from the thread dump */
    { extern void alwd_start(void); alwd_start(); }          /* alarm watchdog (userfile.c) */
    g_stage = 1;
    printf("[host] 2016 host: pex at %08x, slot table %08x, %d slots\n", PEX_BASE, SLOT_TABLE, NSLOTS);
    u32 *tab = (u32 *)SLOT_TABLE;
    for (int k = 0; k < NSLOTS; k++) tab[k] = (u32)(slot_stubs + 8 * k);
    install_real(tab);
    lift_place(&lift_k_set, tab);
    lockbug_install(&lift_k_set); net_install(tab);
    { extern void soc_install(u32 *); soc_install(tab); }   /* friend-list slots + chat command hook (social.c) */                                  /* wrap lifted socket slots (lazy IOP net bring-up) + POLCON answers */
    tab[558] = (u32)svc_gssyncpath;                    /* bounded wait instead of the kernel's 16M-iteration spin */
#ifdef OPT_RET0
    tab[907] = tab[908] = (u32)svc_zero;
#else
    tab[907] = tab[908] = (u32)svc_one;
#endif
                    /* option load: report "loaded" (the kernel version waits for POL option storage) */
#ifdef RELEASE
    /* release build: implemented slots are called DIRECTLY (no stub, no trap_c); only the slots that need the host's own
       handling still go through trap_c: file open/stat/read/seek/close (bare-path mapping, packed files), keyboard (developer page),
       keyboard/mouse before the input stack is up, and mount (starts the input stack). */
    for (int k = 0; k < NSLOTS; k++)
        if (tab[k] != (u32)(slot_stubs + 8 * k)) {
            g_real[k] = tab[k];
            if (k == 938 || k == 939 || k == 940 || k == 942 || k == 951 || k == 104 || k == 106 || k == 107 || k == 956 || hid_slot(k))
                tab[k] = (u32)(slot_stubs + 8 * k);
        }
#elif !defined(NO_TRACE)
    for (int k = 0; k < NSLOTS; k++)                  /* route every implemented slot through the tracer (trap_c calls g_real[k]) */
        if (tab[k] != (u32)(slot_stubs + 8 * k)) {
            g_real[k] = tab[k];
            if (hot_slot(k)) continue;                /* per-frame spam (graphics DMA, cache flush, semaphores...): called directly, no tracing (it made big models crawl) */
            tab[k] = (u32)(slot_stubs + 8 * k);
        }
#endif
    FlushCache(0); FlushCache(2);
#ifdef SONY_IOP
    iop_init_sony();                                   /* IOP reset with IOPRP.IMG, SQIOPMEM, SCE000-002, HID000 (see iop_sony.c) */
    input_init();                                      /* padman + libpad (BIOS modules) */
    {   /* the engine's next two steps after the reboot: reset the Sony load-file and file-service libraries */
        unsigned a1 = lift_entry_addr(&lift_k_set, "sceSifLoadFileReset"), a2 = lift_entry_addr(&lift_k_set, "sceFsReset");
        unsigned a3 = lift_entry_addr(&lift_k_set, "sqmemClientInit");
        if (a1) ((void (*)(void))a1)();
        if (a3) ((int (*)(void))a3)();
        int r = a2 ? ((int (*)(void))a2)() : -99;
        hlog(9, (u32)r, a1, a2, 0, 0, 0, "kernel sceFsReset rc / entries:", 0, 0);
        /* the kernel's file layer (sqFileInit = slot 919, donor 0x153338): sets up the request lock 0x193e40 (sceOpen/sceMount/...
           all take it first; with it uninitialised the lifted code hits a 'break' in the lock function), the 4 file contexts,
           and the init flag 0x193e38.  Nothing in the 2016 program calls it, so the host must. */
        unsigned a4 = lift_entry_addr(&lift_k_set, "sqFileInit");
        int r4 = a4 ? ((int (*)(void))a4)() : -99;
        hlog(9, (u32)r4, a4, 0, 0, 0, 0, "kernel sqFileInit rc / entry:", 0, 0);
#ifdef INPUT_HID_INIT
        input_hid_prepare();
#ifdef NET_INGAME_TEST
        { extern void nettest_start(void); nettest_start(); }
#endif
#endif
    }
#else
    iop_init();
#endif
#if defined(SONY_IOP) && !defined(NO_NETBOOT)
    { extern int net_ensure(void); int nr = net_ensure(); printf("[host] network bring-up before the game: %d\n", nr); }   /* done once, before any game thread exists */
#endif
    { extern void iop_mem_map(const char *); iop_mem_map("at host start"); }
    memset((void *)PEX_END, 0, PEX_TOP - PEX_END);
    FlushCache(0); FlushCache(2);
#ifndef SONY_IOP
    SetAlarm(16, sound_consumer, 0);
#else
    SetAlarm(32, log_tick, 0);
#endif
    static char *av[2] = { "hdd0:PP.SCUS-97266.0001.FFXI", 0 };
#ifdef NULLPAGE
    {   /* debug aid: map virtual 0..0x1FFF to a page of "jr ra; nop" so null dereferences/calls do not kill the game */
        static u32 zpage[2048] __attribute__((aligned(4096)));
        for (int i = 0; i < 2048; i += 2) { zpage[i] = 0x03E00008; zpage[i + 1] = 0; }
        FlushCache(0);
        u32 pa = (u32)zpage & 0x1FFFFFFF;
        int r = PutTLBEntry(0, 0, ((pa >> 12) << 6) | 0x1F, (((pa + 0x1000) >> 12) << 6) | 0x1F);   /* C=3 D V G */
        printf("[host] null page mapped rc=%d\n", r);
    }
#endif
#ifndef NO_ACCT_PATCH
    {   /* lobby login packet (0x353340): with a PlayOnline token present the program zeroes the first byte of the account name (sb zero,0x1c(s1) at
           0x3533DC); the LAN proxy needs the account in clear, so drop that store */
        u32 *p = (u32 *)0x3533DC; if (*p == 0xA220001C) { *p = 0; FlushCache(0); FlushCache(2); } else printf("[host] account patch: unexpected word %08x\n", *p);
    }
#endif
#ifndef NO_TOKEN_PATCH
    {   /* the lobby login (0x37274C..) stores the PlayOnline session token as the "password" and sets ctx+0xa20 = 1 (call at 0x372790 to 0x55DA60); with
           that flag the program hashes the token instead of the -pass password.  Without PlayOnline there is no token: skip the call so the digest
           is MD5(key, -pass) like the 2012 build, which the LAN proxy verifies against players.txt */
        u32 *p = (u32 *)0x372790; if (*p == 0x0C157698) { *p = 0; FlushCache(0); FlushCache(2); } else printf("[host] token patch: unexpected word %08x\n", *p);
    }
#endif
#ifdef B55_GEAR5
    {   /* PC content: weapon looks 896-967 (main/sub gear group 5). The 2016 gear table (0x5ABF10 -> per race 9 slots x 5
           groups of {base file id, count}) has group 5 = {0, 32} for main/sub: base 0 = file ids 0-31 (wrong files). Give each race's
           main/sub group 5 a block of 72 new file ids and count 72. Only data words change; each is checked first. */
        static const u32 g5[][2] = {
        { 0x5AA920, 88286 },   /* race 1 main group 5 */
        { 0x5AA948, 88358 },   /* race 1 sub group 5 */
        { 0x5AAA90, 88430 },   /* race 2 main group 5 */
        { 0x5AAAB8, 88798 },   /* race 2 sub group 5 */
        { 0x5AAC00, 88870 },   /* race 3 main group 5 */
        { 0x5AAC28, 88942 },   /* race 3 sub group 5 */
        { 0x5AAD70, 89310 },   /* race 4 main group 5 */
        { 0x5AAD98, 89382 },   /* race 4 sub group 5 */
        { 0x5AAEE0, 89454 },   /* race 5 main group 5 */
        { 0x5AAF08, 89822 },   /* race 5 sub group 5 */
        { 0x5AB050, 89454 },   /* race 6 main group 5 */
        { 0x5AB078, 89822 },   /* race 6 sub group 5 */
        { 0x5AB1C0, 89894 },   /* race 7 main group 5 */
        { 0x5AB1E8, 89966 },   /* race 7 sub group 5 */
        { 0x5AB330, 90334 },   /* race 8 main group 5 */
        { 0x5AB358, 90406 },   /* race 8 sub group 5 */
        };
        int ok = 0;
        for (unsigned i = 0; i < sizeof g5 / sizeof g5[0]; i++) {
            u32 *p = (u32 *)g5[i][0];
            if ((p[0] == 0 && p[1] == 32) || (p[0] == g5[i][1] && p[1] == 72)) { p[0] = g5[i][1]; p[1] = 72; ok++; }
            else printf("[host] gear5: unexpected words at %08x: %08x %08x\n", (unsigned)g5[i][0], (unsigned)p[0], (unsigned)p[1]);
        }
        FlushCache(0);
        printf("[host] gear5: %d of %d weapon group-5 entries set\n", ok, (int)(sizeof g5 / sizeof g5[0]));
    }
#endif
#ifdef FASTFILEWAIT
    {   /* Step 2, loading hitches: the program's file-request waits time out after 1000 ms before a failed request is tried
           again (e.g. no buffer free yet while Create Character swaps race models: 1-3 s dark screens). The same waits with a
           FASTFILEWAIT ms timeout: the identical requests in the identical order, retried sooner. Only the file thread's own idle
           waits of its request loop (0x443D2C after a failed attempt, 0x443D58 when idle); a timeout there just loops. The callers'
           completion waits (0x4436E8, 0x4437D8, 0x4439E4) are NOT changed: their timeout is treated as a failure. */
        static const u32 at[2] = { 0x443D2C, 0x443D58 }; int n = 0;
        for (int i = 0; i < 2; i++) { u32 *w = (u32 *)at[i]; if (*w == 0x240503E8) { *w = 0x24050000 | (FASTFILEWAIT & 0xFFFF); n++; } }
        FlushCache(0); FlushCache(2);
        printf("[host] file-thread retry waits: %d of 2 set to %d ms\n", n, FASTFILEWAIT);
    }
#endif
#ifndef NO_SEACOM_BOX
    {   /* "/seacom" (alias "/sc") typed with no arguments. The program's handler 0x3A7530 needs "/seacom <line 1-3> "text"" and
           otherwise prints "A command error occurred." (0x3A7558: b 0x3A7618 / negu v0,s2). Players expect the command to open the
           search-comment box, so the no-argument case now opens Main menu > Search > Edit Comment (0x520490(search object, 0), as the
           Search menu does at 0x52004C) and returns success. With arguments the command is unchanged; /seacomup is unchanged. */
        extern void seacom_tramp(void);
        u32 *p = (u32 *)0x3A7558;
        if (p[0] == 0x1000002F && p[1] == 0x00121023) { p[0] = 0x08000000 | (((u32)seacom_tramp >> 2) & 0x3FFFFFF); p[1] = 0; FlushCache(0); FlushCache(2); }
        else printf("[host] seacom patch: unexpected words at 0x3a7558: %08x %08x\n", p[0], p[1]);
    }
#endif
#ifdef CIRCLE_TARGET   /* 7 Oct: experiment, not enough on its own (circle still not targetable) - off */
    {   /* 7 Oct 2026: the NPC update handler (0x307670) marks every object with model 50-59 untargetable (actor+0x134 bit 3), which
           includes the Burning Circle (model 52) - so no orb could be traded and no battlefield entered. Keep the bit clear for them
           (0x307698 daddiu v1,zero,8 -> daddiu v1,zero,0). */
        u32 *p = (u32 *)0x307698;
        if (*p == 0x64030008) { *p = 0x64030000; FlushCache(0); FlushCache(2); }
        else printf("[host] circle patch: unexpected word at 0x307698: %08x\n", *p);
    }
#endif
#ifndef NO_GS_MODE2
    {   /* screen-mode setup (0x2BF1D0): mode 0 renders the 3D scene into a 448x384 target inside the 512x448 display; force mode 2 (3D target = 512x448) */
        u32 *p = (u32 *)0x2BF1E8; if (*p == 0x70A09E28) { *p = 0x24130002; FlushCache(0); FlushCache(2); } else printf("[host] gsmode patch: unexpected word %08x\n", *p);
    }
#endif
#ifdef DEV_DIALOG
    {   /* hook MainFlow (jal 0x376CB0 at 0x2D9AA4 -> jal dev_dialog_hook); the hook opens the in-game ServerIP dialog */
        extern u32 dev_dialog_hook(u32, u32, u32, u32);
        extern u32 dev_frame_hook(u32);
#ifdef DEV_NATIVE
        { extern u32 dev_title_text_hook(int, int, const char *, u32); u32 *pt = (u32 *)0x4ACC18; if (*pt == 0x0C152748) *pt = 0x0C000000 | (((u32)dev_title_text_hook >> 2) & 0x3FFFFFF); else printf("[host] devdlg: unexpected word at 0x4ACC18: %08x\n", *pt); }
#endif
        /* text input: outside the JP region the control relies on the console input-method library (not implemented here); take the JP path
           (game's own key queue, flag 0x6af428) in every region so typing works with the NA/English text */
        { u32 *pi = (u32 *)0x36AB88; if (*pi == 0x10400008) { *pi = 0x10000008; } else printf("[host] imm-path patch: unexpected word at 0x36ab88: %08x\n", *pi); }
        { extern void err_hook_entry(void); u32 *pe = (u32 *)0x3CEF40; if (pe[0] == 0x27BDF9D0 && pe[1] == 0xFFBF0020) { pe[0] = 0x08000000 | (((u32)err_hook_entry >> 2) & 0x3FFFFFF); pe[1] = 0; } else printf("[host] err hook: unexpected words at 0x3cef40: %08x %08x\n", pe[0], pe[1]); }
        { extern void text_hook_install(void); text_hook_install(); }
        u32 *pf = (u32 *)0x2D8BE0; if (*pf == 0x0C0B7724) *pf = 0x0C000000 | (((u32)dev_frame_hook >> 2) & 0x3FFFFFF);
        u32 *p = (u32 *)0x2D9AA4;
        if (*p == 0x0C0DDB2C) *p = 0x0C000000 | (((u32)dev_dialog_hook >> 2) & 0x3FFFFFF); else printf("[host] devdlg: unexpected word at 0x2D9AA4: %08x\n", *p);
        FlushCache(0); FlushCache(2);
    }
#endif
#ifndef NO_DEVMENU
    {   /* the program's built-in developer command lines carry Square's test server 172.22.100.112: rewrite the IP in place (new text must not be longer) */
        static const char l1[] = "-net 3 -ip " DEV_IP " -port 54001 -pass " DEV_PASS " -print -accunt " DEV_ACCT;
        static const char l2[] = "-net 3 -f -ip " DEV_IP " -port 54001";
        char *p1 = (char *)0x5d2d70, *p2 = (char *)0x5d2ef0;
        memset(p1, 0, 74); memcpy(p1, l1, sizeof l1);
        memset(p2, 0, 40); memcpy(p2, l2, sizeof l2);
    }
#endif
#ifndef NO_DEVMENU
    *(volatile u8 *)0x5A7A30 = 1;      /* debug flag read by the 2016 start-up (0x2802E4): enables the "-net 3" direct-login mode = developer ServerIP screen */
#endif
#ifdef EXC_HOLD
    {   /* debug: park on a TLB exception instead of letting the kernel kill the run, so a savestate can show EPC and registers */
        extern void exc_hold(void);
        SetVTLBRefillHandler(2, exc_hold); SetVTLBRefillHandler(3, exc_hold);
        SetVCommonHandler(2, exc_hold); SetVCommonHandler(3, exc_hold); SetVCommonHandler(4, exc_hold); SetVCommonHandler(5, exc_hold);
    }
#endif
#ifdef LOGOUT_FIX
    {   /* 7 Oct 2026: /logout -> black or frozen title. The title screen draws a random zone as its background and needs ONE
           free block of 6.7-8.2 MB in the program's second heap (0x7C2200-0x19C2200, 18 MB). At the start of a logout the main heap
           (0x19C2200-) is full, so the allocator's fallback (0x281560) puts the overflowing block (a ~94 KB table) into the second
           heap with the TOP-DOWN search (0x281930): it lands at the top end of the lowest free block, i.e. in the middle of the memory
           the world frees a moment later. Then the largest free block is only 6-7.3 MB, the background (e.g. ROM/0/53, 7.9 MB) can
           never be loaded, nothing of the title is drawn (the menu works blind). Fix: the fallback's other-heap attempt (0x281678)
           uses the BOTTOM-UP search (0x2817A0, same arguments, carves at the low end), so the block sits below the world's memory
           and the freed space stays in one piece. */
        /* 7 Oct 2026: only while playing. On the title and character screens the original top-down search stays: Create
           Character's 3D preview (the Dancer overlay) must load at the very bottom of that heap (0x7C2210) and needs a 10 MB
           block there; bottom-up placement put other blocks in its way and the preview stayed black. */
        u32 *p = (u32 *)0x281678;
        if (*p == 0x0C0A064C) { *p = 0x0C000000 | (((u32)heap_fallback >> 2) & 0x3FFFFFF); FlushCache(0); FlushCache(2); printf("[host] logout fix: heap fallback bottom-up while playing\n"); }
        else printf("[host] logout fix: unexpected word at 0x281678: %08x\n", *p);
    }
#endif
    {   /* 7 Oct 2026: Create Character's 3D preview (the Dancer overlay) was black on drives installed from our disc. The program loads
           "../prog/ps2/dancer.enc" (0x5E6610, read by 0x4FD500) and only then asks slot 1047 to unlock it, and slot 1047 already
           swaps in dancer.bin. The disc leaves out every .enc file, so the read failed and the preview never started. The program
           now reads dancer.bin itself (same length name); slot 1047 still does its swap, so drives that do have dancer.enc behave the same. */
        char *nm = (char *)0x5E6610;
        if (!memcmp(nm, "../prog/ps2/dancer.enc", 23)) { memcpy(nm + 19, "bin", 3); FlushCache(0); printf("[host] dancer: reads dancer.bin\n"); }
        else printf("[host] dancer: unexpected name at 0x5e6610\n");
    }
#ifdef THRDBG
    { extern void thrdbg_start(void); thrdbg_start(); }
#endif
    g_stage = 2;
    { extern void perf_init(void); perf_init(); }        /* frame-rate counters (perf.c) */
    printf("[host] entering the 2016 program at %08x\n", PEX_BASE);
    int (*entry)(int, char **) = (int (*)(int, char **))PEX_BASE;
    g_ret = (u32)entry(1, av);
    g_stage = 3;
    printf("[host] the 2016 program returned %d\n", (int)g_ret);
#ifdef SONY_IOP
    { unsigned ga = lift_entry_addr(&lift_k_set, "sqPolGetReturnValue");      /* what the program told POL via sqPolSetReturnValue (969) */
      if (ga) printf("[host] sqPolGetReturnValue = %d\n", ((int (*)(void))ga)()); }
#endif
    for (;;) SleepThread();
    return 0;
}
