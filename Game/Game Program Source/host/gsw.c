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
   Lines: G (once a second while on: vbl, frames, SyncV calls / share of time, SyncPath calls / share), G site, G bits. */
#ifdef NETDIAG
#include <tamtypes.h>
#include <kernel.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>

typedef void (*out_fn)(const char *, ...);
#define NS 16
#define CYC_MS 294912u
extern volatile u32 g_pf_vs, g_pf_frames, g_real[];

static u32 s_ra[NS], s_n[NS];                          /* call sites (ra | 1 for SyncV), calls */
static u64 s_c[NS], tot_c;                             /* cycles waited per site; cycles since 'gsw 1' */
static u32 b_n[12];                                    /* SyncPath loop samples per condition, [11] = all */
static u32 on, w_vn, w_vc, w_pn, w_pc, next_g, last_cyc, last_fr, other_n;
volatile u32 g_gw_nov = 0;
static u32 (*syncv_orig)(u32);

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
    if (on) { u32 c = cyc() - c0; w_pn++; w_pc += c; site(ra & ~1u, c); }
    return n;
}

static u32 gsw_syncv(u32 mode)
{
    u32 ra = (u32)__builtin_return_address(0), c0 = cyc(), r;
    if (g_gw_nov) r = (u32)(*(volatile u64 *)0x12001000 >> 13) & 1;       /* GS CSR FIELD, as the real one answers in interlaced mode */
    else r = syncv_orig(mode);
    if (on) { u32 c = cyc() - c0; w_vn++; w_vc += c; site(ra | 1, c); }
    return r;
}

void gsw_install(u32 *tab)
{
    syncv_orig = (u32 (*)(u32))(g_real[557] ? g_real[557] : tab[557]);
    tab[557] = (u32)gsw_syncv;
}

static void clear_all(void)
{
    memset(s_ra, 0, sizeof s_ra); memset(s_n, 0, sizeof s_n); memset(s_c, 0, sizeof s_c); memset(b_n, 0, sizeof b_n);
    tot_c = 0; other_n = 0; w_vn = w_vc = w_pn = w_pc = 0; last_cyc = cyc(); last_fr = g_pf_frames; next_g = g_pf_vs + 60;
}

static u32 pm(u64 a, u64 b) { return b ? (u32)(a * 1000 / b) : 0; }

void gsw_tick(out_fn o, int show)
{
    if (!on || (int)(g_pf_vs - next_g) < 0) return;
    next_g = g_pf_vs + 60;
    u32 c = cyc(), dc = c - last_cyc, fr = g_pf_frames, vn = w_vn, vc = w_vc, pn = w_pn, pc = w_pc;
    w_vn = w_vc = w_pn = w_pc = 0;
    last_cyc = c; tot_c += dc;
    u32 a = pm(vc, dc), b = pm(pc, dc);
    if (show) o("G %u fr %u | syncv %u %u.%u%% | path %u %u.%u%% | nov %u", (unsigned)g_pf_vs, (unsigned)(fr - last_fr), (unsigned)vn, (unsigned)(a / 10), (unsigned)(a % 10),
                (unsigned)pn, (unsigned)(b / 10), (unsigned)(b % 10), (unsigned)g_gw_nov);
    last_fr = fr;
}

void gsw_cmd(char *s, out_fn o)
{
    while (*s == ' ') s++;
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
    if (atoi(s)) { clear_all(); on = 1; o("> ok gsw 1 (G line once a second; 'gsw top' for the call sites)"); }
    else { on = 0; o("> ok gsw 0"); }
}
#else
typedef int gsw_unused;
#endif
