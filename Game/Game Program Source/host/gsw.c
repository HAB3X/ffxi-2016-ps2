/* gsw.c - graphics wait meter (NETDIAG52 test builds; debug link commands 'gsw ...', see dbg.c).
   The sampling profiler (sprof.c) showed about a quarter of the game's CPU time spent spinning in two places:
     sceGsSyncPath(0)  (slot 558, host.c svc_gssyncpath): wait until VIF1/GIF DMA, the VIF1, VU1 and the GIF are all idle
     sceGsSyncV        (slot 557, the lifted libgraph):   wait for the next vertical blank
   This times both per calling site in the game (CPU cycles) and, while SyncPath waits, samples the graphics units every loop
   to tell what the wait is really for:
     dma1 / dma2  VIF1 / GIF DMA channel running          vps   VIF1 busy (VIF1_STAT VPS)
     vew          VIF1 held until a VU1 microprogram ends  vgw   VIF1 held by the GIF (DIRECT / FLUSH)
     vfifo        data in the VIF1 FIFO                    vu1   VU1 running
     p1 / p2 / p3 GIF path active: 1 = VU1 XGKICK, 2 = VIF1 DIRECT, 3 = GIF DMA (textures, images)
     gfull        GIF FIFO full (the GS is not taking data as fast as it comes)
   'gsw nov 1' makes sceGsSyncV return at once (no vertical-blank wait; the picture may tear) to measure what that wait costs.
   NETDIAG53: while on, a sampler thread (priority 0) looks at the graphics units about 1000 times a second of wall time, so the
   G line also tells how busy they are over the whole frame, not only during the waits:
     vu1 = VU1 running   gif = a GIF path active   gfull = GIF FIFO full   idle = VU1, GIF and VIF1 DMA all idle
     cpu = VU1 idle while the game thread is not waiting for the graphics (the CPU is not feeding it)
   Lines: G (once a second while on: vbl, frames, SyncV calls / share of time, SyncPath calls / share, samples), G site, G bits.
   NETDIAG54: 'shot' - screen capture.  The picture the TV shows is read back out of the GS, a strip of rows each frame, inside
   the game's own sceGsSyncV call (its drawing is finished there and nothing else is using the graphics DMA): a GIF packet
   (BITBLTBUF/TRXPOS/TRXREG/TRXDIR=1) starts a GS -> memory transfer, the VIF1 FIFO is turned round (VIF1_STAT.FDR, GS BUSDIR)
   and VIF1 DMA (channel 1) brings the rows into a 16 KB buffer; then everything is turned back.  The debug thread sends the
   strip as base64 lines (I d OFFSET DATA) between 'I shot W H PSM FBP FBW' and 'I end'; ps2dbg.py writes shot-HHMMSS.png.
   The displayed buffer comes from the game's display settings (0x6021c0: PMODE, SMODE2, DISPFB, DISPLAY), or is given:
   shot FBP FBW PSM W H. */
#ifdef NETDIAG
#include <tamtypes.h>
#include <kernel.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <delaythread.h>

typedef void (*out_fn)(const char *, ...);
#define NS 48
#define CYC_MS 294912u
extern volatile u32 g_pf_vs, g_pf_frames, g_real[];

static u32 s_ra[NS], s_n[NS];                          /* call sites (ra | 1 for SyncV), calls */
static u64 s_c[NS], tot_c;                             /* cycles waited per site; cycles since 'gsw 1' */
static u32 b_n[12];                                    /* SyncPath loop samples per condition, [11] = all */
static u32 on, w_vn, w_vc, w_pn, w_pc, next_g, last_cyc, last_fr, other_n;
volatile u32 g_gw_nov = 0;
static u32 (*syncv_orig)(u32);
static volatile u32 in_wait;                           /* the game is in: 1 sceGsSyncPath, 2 sceGsSyncV */
static volatile u32 u_n, u_vu, u_gif, u_full, u_idle, u_cpu;   /* sampler counts this second */
static int smp_tid = -1;

/* ---- screen capture ---- */
#define SH_BUF 16384
static u8 sh_buf[SH_BUF] __attribute__((aligned(64)));
static u64 sh_pk[10] __attribute__((aligned(64)));
static volatile u32 sh_on, sh_full, sh_y, sh_rows, sh_err;     /* sh_full: a strip is in sh_buf (rows sh_y .. sh_y + sh_rows) */
static u32 sh_fbp, sh_fbw, sh_psm, sh_w, sh_h, sh_bpp, sh_sent, sh_t0, sh_drain;
static u32 bpp_of(u32 psm) { return psm == 0 ? 4 : psm == 1 ? 3 : (psm == 2 || psm == 10) ? 2 : 0; }
static void sh_capture(void)
{
    if (!sh_on || sh_full || sh_y >= sh_h) return;
    u32 row = sh_w * sh_bpp, n = SH_BUF / row;
    while (n > 1 && (n * row) & 15) n--;
    if (sh_y + n > sh_h) n = sh_h - sh_y;
    if ((n * row) & 15) { sh_err = 1; return; }
    if ((*(volatile u32 *)0x10009000 | *(volatile u32 *)0x1000A000) & 0x100) return;          /* graphics DMA still busy: next frame */
    if ((*(volatile u32 *)0x10003C00 & 3) || (*(volatile u32 *)0x10003020 & 0x1F000C03)) return;   /* VIF1 / GIF busy, or PATH3 masked */
    sh_pk[0] = 4 | (1ull << 15) | (1ull << 60); sh_pk[1] = 0xE;                                  /* GIFtag: 4 x A+D, EOP */
    sh_pk[2] = (u64)(sh_fbp * 32) | ((u64)sh_fbw << 16) | ((u64)sh_psm << 24); sh_pk[3] = 0x50;   /* BITBLTBUF: source */
    sh_pk[4] = (u64)sh_y << 16; sh_pk[5] = 0x51;                                                  /* TRXPOS: x 0, y */
    sh_pk[6] = (u64)sh_w | ((u64)n << 32); sh_pk[7] = 0x52;                                       /* TRXREG */
    sh_pk[8] = 1; sh_pk[9] = 0x53;                                                                /* TRXDIR: local -> host */
    int o = DIntr();
    SyncDCache(sh_pk, (u8 *)sh_pk + sizeof sh_pk);
    InvalidDCache(sh_buf, sh_buf + SH_BUF - 1);
    *(volatile u32 *)0x1000A010 = (u32)sh_pk; *(volatile u32 *)0x1000A020 = 5; *(volatile u32 *)0x1000A000 = 0x101;
    u32 k = 0;
    while ((*(volatile u32 *)0x1000A000 & 0x100) && ++k < 1000000) { }
    while ((*(volatile u32 *)0x10003020 & 0x1F000000) && ++k < 1000000) { }                 /* the GIF FIFO has drained (the packet is in the GS) */
    if (k >= 1000000) { sh_err = 2; *(volatile u32 *)0x1000E010 = 4; if (o) EIntr(); return; }
    *(volatile u32 *)0x10003C00 = 0x800000;                                                      /* VIF1 FIFO: GS -> memory */
    *(volatile u64 *)0x12001040 = 1;                                                             /* GS BUSDIR: local -> host */
    *(volatile u32 *)0x10009010 = (u32)sh_buf; *(volatile u32 *)0x10009020 = n * row / 16; *(volatile u32 *)0x10009000 = 0x100;
    k = 0;
    while ((*(volatile u32 *)0x10009000 & 0x100) && ++k < 4000000) { }
    if (k >= 4000000) { *(volatile u32 *)0x10009000 = 0; sh_err = 3; }
    for (u32 quiet = 0, t = 0; quiet < 64 && t < 100000; t++) {        /* NETDIAG55: anything the GS sent beyond what was asked must not stay */
        if (*(volatile u32 *)0x10003C00 & 0x1F000000) {                  /* in the VIF1 FIFO, or VIF1 decodes it as VIF codes once turned back */
            __asm__ volatile("lq $8, 0(%0)" :: "r"(0x10005000) : "$8", "memory"); sh_drain++; quiet = 0;
        } else quiet++;
    }
    *(volatile u64 *)0x12001040 = 0;
    *(volatile u32 *)0x10003C00 = 0;
    *(volatile u32 *)0x1000E010 = 6;              /* NETDIAG55: clear the channel 1/2 'transfer ended' flags (D_STAT CIS1/CIS2) while interrupts
                                                     are still off - else the game's DMA-end handler takes our transfers for its own (NETDIAG54
                                                     froze PCSX2 after the first strip: VIF1 chain stalled, the game waiting in sceGsSyncPath) */
    InvalidDCache(sh_buf, sh_buf + SH_BUF - 1);
    if (o) EIntr();
    if (sh_err) return;
    sh_rows = n; sh_full = 1;
}
static u8 smp_stack[2048] __attribute__((aligned(16)));

static inline u32 cyc(void) { u32 c; __asm__ volatile("mfc0 %0, $9" : "=r"(c)); return c; }

static void site(u32 ra, u32 c)
{
    u32 k = (ra >> 2) % NS;
    for (int i = 0; i < NS; i++, k = (k + 1) % NS)
        if (s_ra[k] == ra || !s_ra[k]) { s_ra[k] = ra; s_n[k]++; s_c[k] += c; return; }
    other_n++;
}

/* sceGsSyncPath(0) wait loop (called by host.c svc_gssyncpath with the game's return address); returns the loop count, 0x1000000 = timed out */
u32 gsw_path(u32 ra)
{
    u32 c0 = cyc(), n = 0;
    in_wait = 1;
    for (;;) {
        u32 d1 = *(volatile u32 *)0x10009000 & 0x100, d2 = *(volatile u32 *)0x1000A000 & 0x100;
        u32 vs = *(volatile u32 *)0x10003C00, gs = *(volatile u32 *)0x10003020, vu;
        __asm__ volatile("cfc2 %0, $vi29" : "=r"(vu)); vu &= 0x100;
        if (!d1 && !d2 && !(vs & 0x1F000003) && !vu && !(gs & 0xC00)) break;
        if (++n >= 0x1000000) break;
        if (on) {
            b_n[11]++;
            if (d1) b_n[0]++;
            if (d2) b_n[1]++;
            if (vs & 3) b_n[2]++;
            if (vs & 4) b_n[3]++;
            if (vs & 8) b_n[4]++;
            if (vs & 0x1F000000) b_n[5]++;
            if (vu) b_n[6]++;
            u32 ap = gs >> 10 & 3; if (ap) b_n[6 + ap]++;
            if ((gs >> 24 & 0x1F) >= 16) b_n[10]++;
        }
    }
    in_wait = 0;
    if (on) { u32 c = cyc() - c0; w_pn++; w_pc += c; site(ra & ~1u, c); }
    return n;
}

static u32 gsw_syncv(u32 mode)
{
    u32 ra = (u32)__builtin_return_address(0), c0 = cyc(), r;
    if (sh_on) sh_capture();
    if (g_gw_nov) r = (u32)(*(volatile u64 *)0x12001000 >> 13) & 1;       /* GS CSR FIELD, as the real one answers in interlaced mode */
    else { in_wait = 2; r = syncv_orig(mode); in_wait = 0; }
    if (on) { u32 c = cyc() - c0; w_vn++; w_vc += c; site(ra | 1, c); }
    return r;
}

static void smp_thread(void *arg)
{
    (void)arg;
    for (;;) {
        if (!on) { DelayThread(100 * 1000); continue; }
        DelayThread(1000);
        u32 vu, gs = *(volatile u32 *)0x10003020, d1 = *(volatile u32 *)0x10009000 & 0x100, w = in_wait;
        __asm__ volatile("cfc2 %0, $vi29" : "=r"(vu)); vu &= 0x100;
        u_n++;
        if (vu) u_vu++;
        if (gs & 0xC00) u_gif++;
        if ((gs >> 24 & 0x1F) >= 16) u_full++;
        if (!vu && !(gs & 0xC00) && !d1) u_idle++;
        if (!vu && !w) u_cpu++;
    }
}

void gsw_install(u32 *tab)
{
    syncv_orig = (u32 (*)(u32))(g_real[557] ? g_real[557] : tab[557]);
    tab[557] = (u32)gsw_syncv;
}

static void clear_all(void)
{
    u_n = u_vu = u_gif = u_full = u_idle = u_cpu = 0;
    memset(s_ra, 0, sizeof s_ra); memset(s_n, 0, sizeof s_n); memset(s_c, 0, sizeof s_c); memset(b_n, 0, sizeof b_n);
    tot_c = 0; other_n = 0; w_vn = w_vc = w_pn = w_pc = 0; last_cyc = cyc(); last_fr = g_pf_frames; next_g = g_pf_vs + 60;
}

static u32 pm(u64 a, u64 b) { return b ? (u32)(a * 1000 / b) : 0; }

void gsw_tick(out_fn o, int show)
{
    if (!on || (int)(g_pf_vs - next_g) < 0) return;
    next_g = g_pf_vs + 60;
    u32 c = cyc(), dc = c - last_cyc, fr = g_pf_frames, vn = w_vn, vc = w_vc, pn = w_pn, pc = w_pc;
    u32 n = u_n, x1 = pm(u_vu, n), x2 = pm(u_gif, n), x3 = pm(u_full, n), x4 = pm(u_idle, n), x5 = pm(u_cpu, n);
    u_n = u_vu = u_gif = u_full = u_idle = u_cpu = 0;
    w_vn = w_vc = w_pn = w_pc = 0;
    last_cyc = c; tot_c += dc;
    u32 a = pm(vc, dc), b = pm(pc, dc);
    if (show) o("G %u fr %u | syncv %u %u.%u%% | path %u %u.%u%% | nov %u | smp %u vu1 %u%% gif %u%% gfull %u%% idle %u%% cpu %u%%", (unsigned)g_pf_vs,
                (unsigned)(fr - last_fr), (unsigned)vn, (unsigned)(a / 10), (unsigned)(a % 10), (unsigned)pn, (unsigned)(b / 10), (unsigned)(b % 10), (unsigned)g_gw_nov,
                (unsigned)n, (unsigned)((x1 + 5) / 10), (unsigned)((x2 + 5) / 10), (unsigned)((x3 + 5) / 10), (unsigned)((x4 + 5) / 10), (unsigned)((x5 + 5) / 10));
    last_fr = fr;
}

static const char b64[] = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";
static char sh_ln[1088] __attribute__((aligned(64)));
void shot_tick(out_fn o, int (*send)(const char *, int))
{
    if (!sh_on) return;
    if (sh_err) { o("> err shot: GS read failed (%u) at row %u, %u qwords drained", (unsigned)sh_err, (unsigned)sh_y, (unsigned)sh_drain); sh_on = 0; sh_err = 0; return; }
    if (!sh_full) { if (g_pf_vs - sh_t0 > 60 * 30) { o("> err shot: no frame drawn for 30 s (row %u)", (unsigned)sh_y); sh_on = 0; } return; }
    u32 len = sh_rows * sh_w * sh_bpp;
    for (u32 p = 0; p < len; p += 768) {
        u32 m = len - p < 768 ? len - p : 768;
        int l = snprintf(sh_ln, 32, "I d %u ", (unsigned)(sh_sent + p));
        const u8 *q = sh_buf + p;
        for (u32 i = 0; i < m; i += 3) {
            u32 v = (u32)q[i] << 16 | (i + 1 < m ? (u32)q[i + 1] << 8 : 0) | (i + 2 < m ? q[i + 2] : 0);
            sh_ln[l++] = b64[v >> 18 & 63]; sh_ln[l++] = b64[v >> 12 & 63];
            sh_ln[l++] = i + 1 < m ? b64[v >> 6 & 63] : '='; sh_ln[l++] = i + 2 < m ? b64[v & 63] : '=';
        }
        sh_ln[l++] = '\n';
        if (send(sh_ln, l) < 0) { sh_on = 0; return; }
    }
    sh_sent += len; sh_y += sh_rows; sh_full = 0;
    if (sh_y >= sh_h) { o("I end %u", (unsigned)sh_sent); o("> ok shot %ux%u in %u ms, %u extra qwords drained", (unsigned)sh_w, (unsigned)sh_h, (unsigned)((g_pf_vs - sh_t0) * 1000 / 60), (unsigned)sh_drain); sh_on = 0; }
}

static void shot_cmd(char *s, out_fn o)
{
    if (sh_on) { o("> err shot: one is still being sent"); return; }
    volatile u64 *ds = (volatile u64 *)0x6021c0;                       /* the game's display settings: PMODE, SMODE2, DISPFB, DISPLAY */
    u64 fb = ds[2], dp = ds[3];
    sh_fbp = (u32)(fb & 0x1FF); sh_fbw = (u32)(fb >> 9 & 0x3F); sh_psm = (u32)(fb >> 15 & 0x1F);
    sh_w = (u32)((dp >> 32 & 0xFFF) + 1) / (u32)((dp >> 23 & 0xF) + 1); sh_h = (u32)((dp >> 44 & 0x7FF) + 1) / (u32)((dp >> 27 & 3) + 1);
    while (*s == ' ') s++;
    if (*s) {                                                           /* shot FBP FBW PSM W H */
        char *e; u32 v[5]; int k = 0;
        for (; k < 5 && *s; k++) { v[k] = strtoul(s, &e, 0); if (e == s) break; s = e; while (*s == ' ') s++; }
        if (k != 5) { o("> err shot: use 'shot' or 'shot FBP FBW PSM W H'"); return; }
        sh_fbp = v[0]; sh_fbw = v[1]; sh_psm = v[2]; sh_w = v[3]; sh_h = v[4];
    }
    if (sh_psm == 1) sh_psm = 0;                                       /* PSMCT24 is read as PSMCT32 (same layout, 4 bytes a pixel: no 24-bit packing question) */
    sh_bpp = bpp_of(sh_psm);
    if (!sh_bpp || !sh_w || !sh_h || sh_w > 1024 || sh_h > 1024 || sh_w > sh_fbw * 64 || sh_w * sh_bpp > SH_BUF) {
        o("> err shot: unusable picture fbp %u fbw %u psm %u %ux%u (DISPFB %08x%08x DISPLAY %08x%08x)", (unsigned)sh_fbp, (unsigned)sh_fbw, (unsigned)sh_psm,
          (unsigned)sh_w, (unsigned)sh_h, (unsigned)(fb >> 32), (unsigned)fb, (unsigned)(dp >> 32), (unsigned)dp);
        return;
    }
    o("I shot %u %u %u %u %u", (unsigned)sh_w, (unsigned)sh_h, (unsigned)sh_psm, (unsigned)sh_fbp, (unsigned)sh_fbw);
    sh_y = 0; sh_sent = 0; sh_full = 0; sh_err = 0; sh_drain = 0; sh_t0 = g_pf_vs; sh_on = 1;
}

void gsw_cmd(char *s, out_fn o)
{
    while (*s == ' ') s++;
    if (!strncmp(s, "shot", 4)) { shot_cmd(s + 4, o); return; }
    if (!strncmp(s, "top", 3)) {
        u64 prev = ~0ull; u32 prev_ra = 0;
        for (int r = 0; r < NS; r++) {                                       /* descending by cycles waited */
            int best = -1;
            for (int k = 0; k < NS; k++) {
                if (!s_ra[k]) continue;
                if (s_c[k] > prev || (s_c[k] == prev && s_ra[k] <= prev_ra)) continue;
                if (best < 0 || s_c[k] > s_c[best] || (s_c[k] == s_c[best] && s_ra[k] < s_ra[best])) best = k;
            }
            if (best < 0) break;
            prev = s_c[best]; prev_ra = s_ra[best];
            u32 p = pm(s_c[best], tot_c), avg = s_n[best] ? (u32)(s_c[best] / s_n[best] / (CYC_MS / 1000)) : 0;
            o("G site %s ra %08x n %u avg %u us %u.%u%%", (s_ra[best] & 1) ? "syncv" : "path", (unsigned)(s_ra[best] & ~1u), (unsigned)s_n[best],
              (unsigned)avg, (unsigned)(p / 10), (unsigned)(p % 10));
        }
        static const char *nm[11] = { "dma1", "dma2", "vps", "vew", "vgw", "vfifo", "vu1", "p1", "p2", "p3", "gfull" };
        char ln[200]; int l = snprintf(ln, sizeof ln, "G bits n %u", (unsigned)b_n[11]);
        for (int i = 0; i < 11 && l < (int)sizeof ln - 20; i++) { u32 p = pm(b_n[i], b_n[11]); l += snprintf(ln + l, sizeof ln - l, " %s %u%%", nm[i], (unsigned)((p + 5) / 10)); }
        o("%s", ln);
        o("> ok gsw top: %u ms measured, %u calls past the table", (unsigned)(tot_c / CYC_MS), (unsigned)other_n);
        return;
    }
    if (!strncmp(s, "nov", 3)) { g_gw_nov = atoi(s + 3) != 0; o("> ok gsw nov %u (%s)", (unsigned)g_gw_nov, g_gw_nov ? "no vblank wait - the picture may tear" : "normal vblank wait"); return; }
    if (!strncmp(s, "clear", 5)) { clear_all(); o("> ok gsw clear"); return; }
    if (atoi(s)) {
        if (smp_tid < 0) {
            extern void *_gp; ee_thread_t t; memset(&t, 0, sizeof t);
            t.func = (void *)smp_thread; t.stack = smp_stack; t.stack_size = sizeof smp_stack; t.initial_priority = 0; t.gp_reg = &_gp;
            smp_tid = CreateThread(&t); if (smp_tid >= 0) StartThread(smp_tid, NULL);
        }
        clear_all(); on = 1; o("> ok gsw 1 (G line once a second; 'gsw top' for the call sites)"); }
    else { on = 0; o("> ok gsw 0"); }
}
#else
typedef int gsw_unused;
#endif
