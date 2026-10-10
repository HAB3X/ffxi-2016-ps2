/* dbg.c - NETDIAG builds only: live debug link to the developer PC (NETDIAG41).

   The lifted sq* socket library has no listening sockets, so the PS2 connects OUT to the PC (NETDIAG_PC_IP, port DBG_PORT), where
   tools/ps2link/ps2dbg.py listens.  It keeps reconnecting, so the console can be started before or after the game.  Text lines both ways:
     PS2 -> PC   H hello (build, Status register)        S status, every DBG_RATE ms (vblanks, frames, world, page, calls, ...)
                 L new host log lines                     R report lines (BEAT / STATS / EXC / hang: the text the proxy also gets)
                 E CPU exception caught (g_exc)           W hardware watchpoint hit
                 M memory dump line                       T thread / Q semaphore line          > command reply
     PC -> PS2   one command per line, numbers in C syntax (0x.. hex):
                 ping | rate MS | stream 0/1 | peek ADDR [LEN] | poke ADDR VALUE [1|2|4] | thr | sema | report | beat | log
                 watch ADDR [r|w|rw] [MASK] [COUNT] | iwatch ADDR [MASK] [COUNT] | unwatch | wtest
                 prof 0/1 | ap N ADDR | patch ADDR NEW [OLD] | unpatch ADDR [force] | unpatch all | patches | hist 0/1
                 samp 0/1 [RATE] | samp top [N] | samp clear   (sampling profiler, sprof.c)
                 gsw 0/1 | gsw top | gsw clear | gsw nov 0/1   (graphics wait meter, gsw.c)
                 crash   (crash report by hand - crash.c)
     more PS2 -> PC: A profiler (once a second)  F frame times (once a second)  X patch list line  P samples (once a second)
                     G graphics waits (once a second)  C crash report (C begin .. C end)
   The thread runs at priority 0 (with the report thread, above every game thread), so it keeps answering while the game is stuck,
   as long as the EE still takes interrupts and the IOP network stack answers.

   Watchpoints use the EE's own breakpoint registers (BPC/IAB/DAB): a hit enters the level-2 (debug) exception vector at 0x80000100,
   which dbg_l2 below takes over the first time a watchpoint is armed.  dbg_l2 saves a few registers, disarms the breakpoint and returns;
   this thread reports the hit and re-arms it (COUNT hits).  'wtest' checks the whole path on a variable of our own first.

   Placement: the code and constants go into their own sections (.dbgk*, see build.sh / host.ld), loaded after the lifted kernel: the
   host area below 0x1D6000 is full.  The buffers stay in the normal .bss (room made by shrinking the unused g_pcs ring, host.c). */
#ifdef NETDIAG
#include <tamtypes.h>
#include <kernel.h>
#include <delaythread.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#include "host.h"

#ifndef DBG_PORT
#define DBG_PORT 54100
#endif
#ifndef DBG_RATE
#define DBG_RATE 200
#endif
#ifndef BUILD_TAG
#define BUILD_TAG "NETDIAG"
#endif

extern int nd_sock(int op, int h, void *p, int n);          /* net.c: 0 open (n = port), 1 connect check, 2 send, 3 recv, 4 close */
extern volatile int g_net_state;
extern volatile u32 g_pf_vs, g_calls, g_opn, g_exc[20], g_exc_n, g_mon_insend;
extern volatile int g_in_world;
extern char g_netlog[16][64]; extern volatile int g_netlog_n;
extern int sh_frame_now(void), sh_state_now(void);
extern volatile u32 g_pcn __attribute__((weak));
typedef struct { volatile u32 idx, ra, a0, sp, cyc; } IfEnt;
extern volatile IfEnt g_if[32];

volatile int g_dbg_req = 0;                                 /* 1 full report, 2 beat: built by the report thread (net.c world_watch) */
volatile int g_dbg_up = 0;                                  /* link connected */
static volatile char (*mir_p)[72]; static volatile int mir_n = 0;

static u8 dbg_stack[6144] __attribute__((aligned(16)));
static char txb[1536] __attribute__((aligned(64)));
static char rxb[256] __attribute__((aligned(64)));
static char cmdl[160];
static int tx_n, cl_n, h = -1, rate = DBG_RATE, stream = 1;

/* ---- sending ---- */
static int flush(void)
{
    int o = 0, tries = 0;
    while (o < tx_n && h >= 0) {
        int r = nd_sock(2, h, txb + o, tx_n - o);
        if (r > 0) { o += r; tries = 0; continue; }
        if (r < 0 || ++tries > 200) { tx_n = 0; return -1; }      /* error, or 2 s without progress: drop the link */
        DelayThread(10 * 1000);
    }
    tx_n = 0;
    return 0;
}
static void out(const char *fmt, ...)
{
    va_list ap;
    if (tx_n > (int)sizeof txb - 200 && flush() < 0) return;
    va_start(ap, fmt); int n = vsnprintf(txb + tx_n, sizeof txb - tx_n - 1, fmt, ap); va_end(ap);
    if (n < 0) return;
    if (n > (int)sizeof txb - tx_n - 2) n = sizeof txb - tx_n - 2;
    tx_n += n; txb[tx_n++] = '\n';
}

/* ---- memory access ---- */
static int rd_ok(u32 a, u32 n)
{
    u32 e = a + n;
    if (e < a) return 0;
    if (a >= 0x00100000 && e <= 0x02000000) return 1;                    /* main RAM (user view) */
    if (a >= 0x80000000 && e <= 0x82000000) return 2;                    /* main RAM incl. the kernel (kseg0, read in kernel mode) */
    if (a >= 0x70000000 && e <= 0x70004000) return 1;                    /* scratchpad */
    if (!(a & 3) && !(n & 3) && a >= 0x10000000 && e <= 0x10010000 && !(a < 0x10008000 && e > 0x10004000)) return 3;   /* EE registers (no FIFOs) */
    if (!(a & 3) && !(n & 3) && a >= 0x12001000 && e <= 0x12001100) return 3;                                           /* GS CSR / SIGLBLID */
    return 0;
}
static u32 kmode_on(void)
{
    u32 sr; __asm__ volatile("mfc0 %0, $12" : "=r"(sr));
    __asm__ volatile("mtc0 %0, $12\n sync.p" :: "r"(sr & ~0x18u));
    return sr;
}
static void kmode_off(u32 sr) { __asm__ volatile("mtc0 %0, $12\n sync.p" :: "r"(sr)); }
static void rd_copy(u32 *dst, u32 a, u32 n, int kind)             /* n: multiple of 4 */
{
    if (kind == 2) { DIntr(); u32 sr = kmode_on(); for (u32 i = 0; i < n; i += 4) { u32 w = 0; memcpy(&w, (void *)(a + i), 4); dst[i / 4] = w; } kmode_off(sr); EIntr(); }
    else if (kind == 3) { for (u32 i = 0; i < n; i += 4) dst[i / 4] = *(volatile u32 *)(a + i); }
    else memcpy(dst, (void *)a, n);
}
static void cmd_peek(u32 a, u32 n)
{
    if (n == 0) n = 16;
    if (n > 8192) n = 8192;
    n = (n + 3) & ~3u;
    int k = rd_ok(a, n);
    if (!k || ((k == 3) && (a & 3))) { out("> err peek %08x %u: not readable", (unsigned)a, (unsigned)n); return; }
    u32 w[4];
    for (u32 o = 0; o < n; o += 16) {
        u32 m = n - o < 16 ? n - o : 16;
        rd_copy(w, a + o, m, k);
        if (m == 16) out("M %08x %08x %08x %08x %08x", (unsigned)(a + o), (unsigned)w[0], (unsigned)w[1], (unsigned)w[2], (unsigned)w[3]);
        else { char b[64]; int bl = snprintf(b, sizeof b, "M %08x", (unsigned)(a + o)); for (u32 i = 0; i < m / 4; i++) bl += snprintf(b + bl, sizeof b - bl, " %08x", (unsigned)w[i]); out("%s", b); }
    }
    out("> ok peek");
}
static void cmd_poke(u32 a, u32 v, u32 sz)
{
    if (sz != 1 && sz != 2) sz = 4;
    if ((a & (sz - 1)) || a < 0x00100000 || a + sz > 0x02000000) { out("> err poke %08x: main RAM only, aligned", (unsigned)a); return; }
    u32 old = sz == 4 ? *(volatile u32 *)a : sz == 2 ? *(volatile u16 *)a : *(volatile u8 *)a;
    if (sz == 4) *(volatile u32 *)a = v; else if (sz == 2) *(volatile u16 *)a = (u16)v; else *(volatile u8 *)a = (u8)v;
    FlushCache(0); FlushCache(2);                                      /* in case it was code */
    out("> ok poke %08x %08x -> %08x", (unsigned)a, (unsigned)old, (unsigned)v);
}

/* ---- threads ---- */
static int tid_of_sp(u32 sp)
{
    for (int t = 1; t < 64; t++) {
        ee_thread_status_t st;
        if (ReferThreadStatus(t, &st) < 0 || st.status == 16) continue;
        u32 b = (u32)st.stack; if (sp >= b && sp < b + (u32)st.stack_size) return t;
    }
    return -1;
}
static void cmd_thr(void)
{
    for (int t = 1; t < 64; t++) {
        ee_thread_status_t st;
        if (ReferThreadStatus(t, &st) < 0) continue;
        out("T %d st %d prio %d wait %d/%d func %08x stack %08x size %x wakeups %d", t, st.status, st.current_priority, st.waitType, st.waitId,
            (unsigned)st.func, (unsigned)st.stack, (unsigned)st.stack_size, st.wakeupCount);
    }
    out("> ok thr");
}
static void cmd_sema(void)
{
    for (int s = 0; s < 128; s++) {
        ee_sema_t q;
        if (ReferSemaStatus(s, &q) < 0) continue;
        out("Q %d count %d max %d init %d waiting %d", s, q.count, q.max_count, q.init_count, q.wait_threads);
    }
    out("> ok sema");
}

/* ---- hardware watchpoints ---- */
#define BPC_IAE (1u << 31)
#define BPC_DRE (1u << 30)
#define BPC_DWE (1u << 29)
#define BPC_IUE (1u << 26)
#define BPC_IKE (1u << 24)
#define BPC_DUE (1u << 21)
#define BPC_DKE (1u << 19)
#define BPC_ITE (1u << 17)
#define BPC_DTE (1u << 16)
#define BPC_BED (1u << 15)
/* hit record, written by dbg_l2 through kseg0: [0] count [1] ErrorEPC [2] BPC [3] ra [4] sp [5] gp [6] v0 [7] v1 [8] a0 [9] a1 [10] a2
   [11] a3 [12] t0 [13] t1 [14] s0 [15] s1 [16] at [17] Cause [18] Status */
volatile u32 g_wh[20] __attribute__((aligned(64)));
volatile u32 g_wtv[32] __attribute__((aligned(64)));     /* wtest: [0] is stored to, [16] (another cache line) is not */
static int bp_vec = 0, bp_kind = 0, bp_left = 0, bp_inv = 0; static u32 bp_addr, bp_mask, bp_seen = 0;
__asm__(
    ".set push\n.set noreorder\n.set noat\n"
    ".pushsection .text\n"
    ".globl dbg_l2\n.ent dbg_l2\n"
    "dbg_l2:\n"
    "lui   $k0, %hi(g_wh)\n"
    "addiu $k0, $k0, %lo(g_wh)\n"
    "lui   $k1, 0x8000\n"
    "or    $k0, $k0, $k1\n"                 /* kseg0: kuseg is unmapped while ERL = 1 */
    "sw    $ra, 12($k0)\n"
    "sw    $sp, 16($k0)\n"
    "sw    $gp, 20($k0)\n"
    "sw    $v0, 24($k0)\n"
    "sw    $v1, 28($k0)\n"
    "sw    $a0, 32($k0)\n"
    "sw    $a1, 36($k0)\n"
    "sw    $a2, 40($k0)\n"
    "sw    $a3, 44($k0)\n"
    "sw    $t0, 48($k0)\n"
    "sw    $t1, 52($k0)\n"
    "sw    $s0, 56($k0)\n"
    "sw    $s1, 60($k0)\n"
    "sw    $1,  64($k0)\n"
    "mfc0  $k1, $30\n"                      /* ErrorEPC */
    "sw    $k1, 4($k0)\n"
    "mfbpc $k1\n"
    "sw    $k1, 8($k0)\n"
    "mfc0  $k1, $13\n"
    "sw    $k1, 68($k0)\n"
    "mfc0  $k1, $12\n"
    "sw    $k1, 72($k0)\n"
    "ori   $k1, $0, 0x8000\n"               /* BED: no further breakpoint exceptions until the thread re-arms */
    "mtbpc $k1\n"
    "sync.p\n"
    "lw    $k1, 0($k0)\n"
    "addiu $k1, $k1, 1\n"
    "sw    $k1, 0($k0)\n"                   /* count last: the record is complete when the thread sees it change */
    "sync.l\n"
    "eret\n"
    "nop\n"
    ".end dbg_l2\n"
    ".globl dbg_wt_store\n.ent dbg_wt_store\n"
    "dbg_wt_store:\n"                       /* wtest: the store the test watchpoint must catch (a0 = value), at dbg_wt_store + 4 */
    "lui   $v0, %hi(g_wtv)\n"
    "sw    $a0, %lo(g_wtv)($v0)\n"
    "jr    $ra\n"
    "nop\n"
    ".end dbg_wt_store\n"
    ".popsection\n"
    ".set pop\n");
extern void dbg_l2(void), dbg_wt_store(u32);
static void bp_vector(void)                                 /* point the level-2 exception vector at dbg_l2 */
{
    if (bp_vec) return;
    u32 t = (u32)dbg_l2 | 0x80000000u;
    u32 stub[4] = { 0x3C1A0000u | (t >> 16), 0x375A0000u | (t & 0xFFFF), 0x03400008u, 0 };   /* lui k0; ori k0; jr k0; nop */
    DIntr(); u32 sr = kmode_on();
    __asm__ volatile("ori $8, $0, 0x8000\n mtbpc $8\n sync.p" ::: "$8");
    memcpy((void *)0x80000100, stub, sizeof stub);
    kmode_off(sr); EIntr();
    FlushCache(0); FlushCache(2);
    bp_vec = 1;
}
static void bp_set(u32 bpc, u32 a, u32 m, int instr)
{
    __asm__ volatile("ori $8, $0, 0x8000\n mtbpc $8\n sync.p" ::: "$8");
    if (instr) __asm__ volatile("mtiab %0\n mtiabm %1\n sync.p" :: "r"(a), "r"(m));
    else __asm__ volatile("mtdab %0\n mtdabm %1\n sync.p" :: "r"(a), "r"(m));
    __asm__ volatile("mtbpc %0\n sync.p" :: "r"(bpc));
}
static void bp_off(void) { __asm__ volatile("ori $8, $0, 0x8000\n mtbpc $8\n sync.p" ::: "$8"); }
static u32 bp_mode(int instr)                               /* the privilege level the game runs at (Status KSU) */
{
    u32 sr; __asm__ volatile("mfc0 %0, $12" : "=r"(sr));
    int ksu = sr >> 3 & 3;
    if (instr) return ksu == 2 ? BPC_IUE : BPC_IKE;
    return ksu == 2 ? BPC_DUE : BPC_DKE;
}
static void bp_arm(void)
{
    if (bp_kind == 4) bp_set(BPC_IAE | BPC_ITE | bp_mode(1), bp_addr, bp_mask, 1);
    else bp_set(((bp_kind & 1) ? BPC_DRE : 0) | ((bp_kind & 2) ? BPC_DWE : 0) | BPC_DTE | bp_mode(0), bp_addr, bp_mask, 0);
}
static void cmd_watch(int kind, u32 a, u32 m, int count)
{
    bp_vector();
    bp_kind = kind; bp_addr = a; bp_mask = m; bp_left = count > 0 ? count : 1; bp_seen = g_wh[0];
    bp_arm();
    out("> ok %s %08x mask %08x count %d", kind == 4 ? "iwatch" : "watch", (unsigned)a, (unsigned)m, bp_left);
}
static void wh_report(void)
{
    volatile u32 *w = g_wh;
    u32 bpc = w[2], epc = w[1];
    const char *what = (bpc & 1) ? "exec" : (bpc & 4) ? "write" : (bpc & 2) ? "read" : "?";
    u32 v = 0; if (bp_kind != 4 && rd_ok(bp_addr & ~3u, 4) == 1) v = *(volatile u32 *)(bp_addr & ~3u);
    out("W %u %s addr %08x epc %08x thr %d now %08x bpc %08x cause %08x sr %08x", (unsigned)w[0], what, (unsigned)bp_addr, (unsigned)epc, tid_of_sp(w[4]),
        (unsigned)v, (unsigned)bpc, (unsigned)w[17], (unsigned)w[18]);
    out("W ra %08x sp %08x gp %08x at %08x v0 %08x v1 %08x", (unsigned)w[3], (unsigned)w[4], (unsigned)w[5], (unsigned)w[16], (unsigned)w[6], (unsigned)w[7]);
    out("W a0 %08x a1 %08x a2 %08x a3 %08x t0 %08x t1 %08x s0 %08x s1 %08x", (unsigned)w[8], (unsigned)w[9], (unsigned)w[10], (unsigned)w[11],
        (unsigned)w[12], (unsigned)w[13], (unsigned)w[14], (unsigned)w[15]);
    u32 pc = epc & 0x1FFFFFFCu;
    if (pc >= 0x100004 && pc < 0x1FFFFF0) { volatile u32 *p = (volatile u32 *)pc; out("W code %08x [%08x] %08x %08x", (unsigned)p[-1], (unsigned)p[0], (unsigned)p[1], (unsigned)p[2]); }
}
static int wt_try(u32 a, u32 m)                             /* arm a write watch on a, store to g_wtv[0]: hits, and was it that store */
{
    u32 n0 = g_wh[0];
    bp_kind = 2; bp_addr = a; bp_mask = m; bp_left = 0;
    bp_arm();
    dbg_wt_store(0x1234);
    bp_off();
    DelayThread(20 * 1000);
    u32 n1 = g_wh[0], epc = g_wh[1] & 0x1FFFFFFFu;
    bp_seen = n1;
    return n1 == n0 ? 0 : epc == ((u32)dbg_wt_store & 0x1FFFFFFFu) + 4 ? 1 : 2;   /* 0 no hit, 1 the store, 2 other code */
}
static void cmd_wtest(void)                                 /* which DABM convention works: 1 = compare this bit, or 1 = ignore it */
{
    static const char *rs[3] = { "no hit", "MATCH", "other code" };
    bp_vector();
    u32 m[2] = { 0xFFFFFFFCu, 0x00000003u };
    for (int i = 0; i < 2; i++) {
        int miss = wt_try((u32)&g_wtv[16], m[i]), hit = wt_try((u32)&g_wtv[0], m[i]);
        out("> wtest mask %08x: other address %s, watched address %s", (unsigned)m[i], rs[miss], rs[hit]);
        if (!miss && hit == 1) { bp_inv = i; out("> ok wtest: watchpoints work, mask mode %d (default mask %08x)", i, (unsigned)m[i]); return; }
    }
    out("> err wtest: watchpoints do not work here");
}

/* ---- where does the frame time go (NETDIAG43/44): 'prof 1' starts, 'prof 0' stops ----
   The game's memory allocator (0x281560) has five calls in it whose cost grows with the number of heap blocks.  'prof 1' points
   those jal's at wrappers below that call whatever the jal pointed at (the original, or a host replacement: hf_gc / hf_lf with
   HEAP_FAST, heap_fallback with LOGOUT_FIX) and add up the cycles spent (in units of 256 cycles) and the number of calls.
        0 gc  0x2815FC jal 0x282D40  main thread only: walks every block of the main heap looking for objects waiting to be deleted
        1 lf  0x281604 jal 0x282030  main thread only: largest free block of the requested heap (walks all its blocks)
        2 t1  0x281620 jal 0x281930  first-fit search in the requested heap
        3 t2  0x281678 jal 0x281930  search in the other heap (the requested one was full)
        4 pu  0x281728 jal 0x282E10  both heaps full: purge, then try again
   Reported once a second as "A vbl fr gc units calls lf .. t1 .. t2 .. pu .. hf scans skipped walks kept mallocskips lowered".
   'prof 0' puts the
   jal's back.  (NETDIAG43's PC sampler is gone: inside a kernel alarm callback EPC is not the interrupted program counter.) */
volatile u32 g_ap[6][2] __attribute__((section(".xcmem"), aligned(64)));
static volatile u32 ap_tgt[6] __attribute__((section(".xcmem"), aligned(16)));          /* where each jal pointed */
static volatile u32 ap_save[6] __attribute__((section(".xcmem"), aligned(16)));         /* the jal word it replaced */
static volatile u32 ap_on __attribute__((section(".xcmem")));
extern volatile u32 g_hf[6] __attribute__((weak));
#define AP_WRAP(n) \
    ".globl ap_w" #n "\n.ent ap_w" #n "\nap_w" #n ":\n" \
    "addiu $sp, $sp, -16\n sd $31, 0($sp)\n mfc0 $12, $9\n sw $12, 8($sp)\n" \
    "lui $25, %hi(ap_tgt + 4 * " #n ")\n lw $25, %lo(ap_tgt + 4 * " #n ")($25)\n jalr $25\n nop\n" \
    "mfc0 $12, $9\n lw $13, 8($sp)\n subu $12, $12, $13\n srl $12, $12, 8\n" \
    "la $13, g_ap + 8 * " #n "\n lw $14, 0($13)\n addu $14, $14, $12\n sw $14, 0($13)\n lw $14, 4($13)\n addiu $14, $14, 1\n sw $14, 4($13)\n" \
    "ld $31, 0($sp)\n jr $31\n addiu $sp, $sp, 16\n.end ap_w" #n "\n"
/* only $12-$14 and $25 are used: $8-$11 may carry arguments (EABI), v0/v1 carry the result */
__asm__(".set push\n.set noreorder\n.set noat\n.text\n" AP_WRAP(0) AP_WRAP(1) AP_WRAP(2) AP_WRAP(3) AP_WRAP(4) ".set pop\n");
extern void ap_w0(void), ap_w1(void), ap_w2(void), ap_w3(void), ap_w4(void);
static const u32 ap_at[5] = { 0x2815FC, 0x281604, 0x281620, 0x281678, 0x281728 };
static volatile u32 ap_site[5] __attribute__((section(".xcmem"), aligned(16)));         /* the jal each wrapper currently stands in for */
static u32 jal_to(void (*f)(void)) { return 0x0C000000u | (((u32)f >> 2) & 0x3FFFFFFu); }
static void (*const ap_w[5])(void) = { ap_w0, ap_w1, ap_w2, ap_w3, ap_w4 };
static void ap_put(int i)                                   /* slot i back to the original jal */
{
    volatile u32 *p = (volatile u32 *)ap_site[i];
    if (p && *p == jal_to(ap_w[i])) *p = ap_save[i];
    ap_site[i] = 0;
}
static int ap_take(int i, u32 a)                            /* slot i times the jal at a (any game code); 0 if a is not a jal */
{
    volatile u32 *p = (volatile u32 *)a; u32 j = *p;
    if ((a & 3) || a < 0x100000 || a >= 0x2000000 || (j >> 26) != 3) return 0;
    ap_save[i] = j; ap_tgt[i] = (a & 0xF0000000u) | ((j & 0x3FFFFFFu) << 2); g_ap[i][0] = g_ap[i][1] = 0;
    ap_site[i] = a; *p = jal_to(ap_w[i]);
    return 1;
}
static void cmd_prof(int on)
{
    int n = 0;
    if (on && !ap_on) {
        memset((void *)g_ap, 0, sizeof g_ap);
        for (int i = 0; i < 5; i++) n += ap_take(i, ap_at[i]);
        FlushCache(0); FlushCache(2); ap_on = 1;
    } else if (!on && ap_on) {
        ap_on = 0;
        for (int i = 0; i < 5; i++) if (ap_site[i]) { ap_put(i); n++; }
        FlushCache(0); FlushCache(2);
    }
    out("> ok prof %d (%d calls switched)", ap_on ? 1 : 0, n);
}
/* 'ap N ADDR' (NETDIAG47): wrapper N (0-4, the gc..pu columns of the A line) times the jal at ADDR instead; 'ap N 0' frees it.
   The previous site of that wrapper is put back first, so a wrapper never stands in for two different functions. */
static void cmd_ap(int i, u32 a)
{
    if (i < 0 || i > 4) { out("> err ap: slot 0-4"); return; }
    ap_put(i); FlushCache(0); FlushCache(2);
    int ok = a ? ap_take(i, a) : 1;
    FlushCache(0); FlushCache(2); ap_on = 1;
    if (ok) out("> ok ap %d %08x -> %08x", i, (unsigned)a, a ? (unsigned)ap_tgt[i] : 0u); else out("> err ap %d %08x: not a jal", i, (unsigned)a);
}
static void prof_send(void)
{
    static u32 next_a;
    if (!ap_on || (int)(g_pf_vs - next_a) < 0) return;
    next_a = g_pf_vs + 60;
    out("A %u fr %d gc %u %u lf %u %u t1 %u %u t2 %u %u pu %u %u hf %u %u %u %u %u %u", (unsigned)g_pf_vs, sh_frame_now(),
        (unsigned)g_ap[0][0], (unsigned)g_ap[0][1], (unsigned)g_ap[1][0], (unsigned)g_ap[1][1], (unsigned)g_ap[2][0], (unsigned)g_ap[2][1],
        (unsigned)g_ap[3][0], (unsigned)g_ap[3][1], (unsigned)g_ap[4][0], (unsigned)g_ap[4][1],
        &g_hf ? (unsigned)g_hf[0] : 0u, &g_hf ? (unsigned)g_hf[1] : 0u, &g_hf ? (unsigned)g_hf[2] : 0u, &g_hf ? (unsigned)g_hf[3] : 0u,
        &g_hf ? (unsigned)g_hf[4] : 0u, &g_hf ? (unsigned)g_hf[5] : 0u);
}

/* ---- command parsing ---- */
static u32 num(char **s) { while (**s == ' ') (*s)++; char *e; u32 v = (u32)strtoul(*s, &e, 0); *s = e; return v; }
static int word(char **s, const char *w) { while (**s == ' ') (*s)++; int n = strlen(w); if (strncmp(*s, w, n) || ((*s)[n] && (*s)[n] != ' ')) return 0; *s += n; return 1; }

/* ---- checked code patches (NETDIAG50) ----
   'patch ADDR NEW [OLD]' writes one word of main RAM and remembers what was there first; with OLD it refuses unless the word is OLD
   now (a wrong address or a different build changes nothing).  'unpatch ADDR' puts the first value back if the word still holds
   what 'patch' wrote ('unpatch ADDR force': whatever it holds), 'unpatch all' does that for every patch, newest first, and frees the
   profiler slots too, so the game code is back as loaded.  'patches' lists them ("X n addr orig new now", "changed" when the word
   no longer holds what was written).  A stub written into free memory needs no record: unpatching the jump into it is enough.
   Writes to a profiler call site in use, or to the target of a slot in use, are refused (poke too): that is what crashed the game
   earlier (a slot retargeted while frame code still called it).  'ap' is the way to move a slot. */
#define PT_N 64
static volatile u32 pt_a[PT_N], pt_old[PT_N], pt_new[PT_N];          /* normal .bss: .xcmem is full (it ends where the game starts) */
static volatile int pt_n;
static int ap_owned(u32 a, u32 n)                           /* 1 if [a, a+n) touches a live call site or the target word of a live slot */
{
    for (int i = 0; i < 5; i++) {
        if (!ap_site[i]) continue;
        u32 s = ap_site[i], t = (u32)&ap_tgt[i];
        if ((a < s + 4 && a + n > s) || (a < t + 4 && a + n > t)) return 1;
    }
    return 0;
}
static int pt_find(u32 a) { for (int i = 0; i < pt_n; i++) if (pt_a[i] == a) return i; return -1; }
static void pt_drop(int i) { for (int k = i; k < pt_n - 1; k++) { pt_a[k] = pt_a[k + 1]; pt_old[k] = pt_old[k + 1]; pt_new[k] = pt_new[k + 1]; } pt_n--; }
static int more(char *s) { while (*s == ' ') s++; return *s != 0; }
static void cmd_patch(u32 a, u32 v, int check, u32 want)
{
    if ((a & 3) || a < 0x00100000 || a >= 0x02000000) { out("> err patch %08x: main RAM only, word aligned", (unsigned)a); return; }
    if (ap_owned(a, 4)) { out("> err patch %08x: in use by a profiler slot (use 'ap N 0' first)", (unsigned)a); return; }
    volatile u32 *p = (volatile u32 *)a; u32 cur = *p;
    if (check && cur != want) { out("> err patch %08x: holds %08x, expected %08x - nothing written", (unsigned)a, (unsigned)cur, (unsigned)want); return; }
    int i = pt_find(a);
    if (i < 0) {
        if (pt_n >= PT_N) { out("> err patch: table full (%d), unpatch something first", PT_N); return; }
        i = pt_n; pt_a[i] = a; pt_old[i] = cur; pt_n = i + 1;
    }
    pt_new[i] = v; *p = v;
    FlushCache(0); FlushCache(2);
    out("> ok patch %08x %08x -> %08x (#%d, first value %08x)", (unsigned)a, (unsigned)cur, (unsigned)v, i, (unsigned)pt_old[i]);
}
static int pt_undo(int i, int force)                         /* 1 restored, 0 left alone (changed since) */
{
    volatile u32 *p = (volatile u32 *)pt_a[i]; u32 cur = *p;
    if (cur != pt_new[i] && !force) { out("> err unpatch %08x: holds %08x, not the patched %08x - left alone ('unpatch %08x force')", (unsigned)pt_a[i],
                                          (unsigned)cur, (unsigned)pt_new[i], (unsigned)pt_a[i]); return 0; }
    *p = pt_old[i];
    out("> ok unpatch %08x %08x -> %08x", (unsigned)pt_a[i], (unsigned)cur, (unsigned)pt_old[i]);
    pt_drop(i); return 1;
}
static void cmd_unpatch(char *s)
{
    if (word(&s, "all")) {
        int n = 0, ap = 0, left = 0;
        ap_on = 0; for (int i = 0; i < 5; i++) if (ap_site[i]) { ap_put(i); ap++; }
        for (int i = pt_n - 1; i >= 0; i--) { if (pt_undo(i, 0)) n++; else left++; }
        FlushCache(0); FlushCache(2);
        out("> ok unpatch all: %d restored, %d profiler slots freed, %d left (changed since)", n, ap, left);
        return;
    }
    u32 a = num(&s); int force = word(&s, "force");
    int i = pt_find(a);
    if (i < 0) { out("> err unpatch %08x: not patched", (unsigned)a); return; }
    pt_undo(i, force); FlushCache(0); FlushCache(2);
}
static void cmd_patches(void)
{
    for (int i = 0; i < pt_n; i++) {
        u32 now = *(volatile u32 *)pt_a[i];
        out("X %d %08x orig %08x new %08x now %08x%s", i, (unsigned)pt_a[i], (unsigned)pt_old[i], (unsigned)pt_new[i], (unsigned)now, now == pt_new[i] ? "" : " changed");
    }
    for (int i = 0; i < 5; i++) if (ap_site[i]) out("X ap%d %08x orig %08x -> target %08x", i, (unsigned)ap_site[i], (unsigned)ap_save[i], (unsigned)ap_tgt[i]);
    out("> ok patches %d", pt_n);
}

/* ---- frame times (NETDIAG50): one F line a second from perf.c's per-frame ring ----
   "F vbl frames n v1 a v2 b v3 c v4 d v5 e v6 f max M.MMms": frames finished in the last second, how many took 1, 2, 3, 4, 5 and
   6 or more vertical blanks (1 = 60 fps, 3 = 20 fps), and the longest one in ms (cycle counter).  Averages hide the hitches; this
   shows them.  'hist 0' / 'hist 1' turns the line off / on. */
extern volatile u32 g_pf_frames, g_pf_ftv[1024], g_pf_ftc[1024];
static int hist_on = 1;
static void hist_send(void)
{
    static u32 next_f, last_fr;
    if ((int)(g_pf_vs - next_f) < 0) return;
    next_f = g_pf_vs + 60;
    u32 fr = g_pf_frames, n = fr - last_fr, h[6] = { 0 }, mx = 0;
    if (n > 1000) n = 1000;                                  /* first call, or a long stall: the ring holds the last 1024 */
    for (u32 k = fr - n; k != fr; k++) {
        if (!k) continue;                                    /* frame 0 has no time */
        u32 dv = g_pf_ftv[k & 1023], c = g_pf_ftc[k & 1023];
        h[dv < 1 ? 0 : dv > 6 ? 5 : dv - 1]++;
        if (c > mx) mx = c;
    }
    last_fr = fr;
    if (!hist_on || !stream) return;
    u32 us = mx / 295;                                       /* 294.912 MHz */
    out("F %u frames %u v1 %u v2 %u v3 %u v4 %u v5 %u v6 %u max %u.%02ums", (unsigned)g_pf_vs, (unsigned)n, (unsigned)h[0], (unsigned)h[1], (unsigned)h[2],
        (unsigned)h[3], (unsigned)h[4], (unsigned)h[5], (unsigned)(us / 1000), (unsigned)(us % 1000 / 10));
}

/* ---- commands ---- */
extern void sp_cmd(char *s, void (*o)(const char *, ...)), sp_tick(void (*o)(const char *, ...), int show);   /* sprof.c */
extern void gsw_cmd(char *s, void (*o)(const char *, ...)), gsw_tick(void (*o)(const char *, ...), int show);   /* gsw.c */
extern void crash_tick(void (*o)(const char *, ...)), crash_cmd(void (*o)(const char *, ...));   /* crash.c */
static void cmd(char *s)
{
    if (word(&s, "ping")) out("> pong vbl %u", (unsigned)g_pf_vs);
    else if (word(&s, "rate")) { u32 v = num(&s); rate = v < 50 ? 50 : v > 5000 ? 5000 : (int)v; out("> ok rate %d", rate); }
    else if (word(&s, "stream")) { stream = num(&s) != 0; out("> ok stream %d", stream); }
    else if (word(&s, "peek")) { u32 a = num(&s), n = num(&s); cmd_peek(a, n); }
    else if (word(&s, "poke")) { u32 a = num(&s), v = num(&s), z = num(&s);
        if (ap_owned(a, z == 1 || z == 2 ? z : 4)) out("> err poke %08x: in use by a profiler slot (use 'ap N 0' first)", (unsigned)a); else cmd_poke(a, v, z); }
    else if (word(&s, "patches")) cmd_patches();
    else if (word(&s, "patch")) { u32 a = num(&s), v = num(&s); int c = more(s); u32 w = c ? num(&s) : 0; cmd_patch(a, v, c, w); }
    else if (word(&s, "unpatch")) cmd_unpatch(s);
    else if (word(&s, "samp")) sp_cmd(s, out);
    else if (word(&s, "gsw")) gsw_cmd(s, out);
    else if (word(&s, "crash")) crash_cmd(out);
    else if (word(&s, "hist")) { hist_on = num(&s) != 0; out("> ok hist %d", hist_on); }
    else if (word(&s, "thr")) cmd_thr();
    else if (word(&s, "sema")) cmd_sema();
    else if (word(&s, "report")) { g_dbg_req = 1; out("> ok report (from the report thread within ~1 s)"); }
    else if (word(&s, "beat")) { g_dbg_req = 2; out("> ok beat"); }
    else if (word(&s, "log")) { int k = g_netlog_n, f = k > 16 ? k - 16 : 0; for (int i = f; i < k; i++) out("L %s", g_netlog[i % 16]); out("> ok log"); }
    else if (word(&s, "iwatch")) { u32 a = num(&s), m = num(&s), c = num(&s); cmd_watch(4, a, m ? m : bp_inv ? 3u : 0xFFFFFFFCu, (int)c); }
    else if (word(&s, "watch")) {
        int k = 2; while (*s == ' ') s++;
        u32 a = num(&s); while (*s == ' ') s++;
        if (!strncmp(s, "rw", 2)) { k = 3; s += 2; } else if (*s == 'r') { k = 1; s++; } else if (*s == 'w') { k = 2; s++; }
        u32 m = num(&s), c = num(&s);
        cmd_watch(k, a, m ? m : bp_inv ? 3u : 0xFFFFFFFCu, (int)c);
    }
    else if (word(&s, "unwatch")) { bp_off(); bp_left = 0; out("> ok unwatch"); }
    else if (word(&s, "wtest")) cmd_wtest();
    else if (word(&s, "prof")) cmd_prof(num(&s) != 0);
    else if (word(&s, "ap")) { int i = (int)num(&s); u32 a = num(&s); cmd_ap(i, a); }
    else out("> err unknown command: %s", s);
}

void dbg_run(const char *c) { char b[64]; strncpy(b, c, sizeof b - 1); b[sizeof b - 1] = 0; cmd(b); }   /* crash.c */

/* the report thread hands its finished report lines over here before sending them to the proxy (1 = taken) */
int dbg_mirror(char (*lines)[72], int n)
{
    if (!g_dbg_up || n <= 0) return 0;
    mir_p = (volatile char (*)[72])lines; mir_n = n;
    for (int i = 0; i < 300 && mir_n; i++) DelayThread(10 * 1000);
    if (mir_n) { mir_n = 0; return 0; }
    return 1;
}

static void dbg_thread(void *arg)
{
    (void)arg;
    u32 exc_seen = g_exc_n, log_seen = g_netlog_n, fails = 0;
    while (g_net_state != 2) DelayThread(500 * 1000);
    for (;;) {
        /* connect */
        h = nd_sock(0, -1, 0, DBG_PORT);
        int r = 0;
        if (h >= 0) for (int i = 0; i < 50 && r == 0; i++) { r = nd_sock(1, h, 0, 0); if (!r) DelayThread(100 * 1000); }
        if (h < 0 || r <= 0) {
            if (h >= 0) nd_sock(4, h, 0, 0);
            h = -1; fails++;
            DelayThread((fails > 60 ? 30 : 5) * 1000 * 1000);
            continue;
        }
        fails = 0; tx_n = 0; cl_n = 0; g_dbg_up = 1;
        u32 sr; __asm__ volatile("mfc0 %0, $12" : "=r"(sr));
        out("H %s debug link up, vbl %u, sr %08x, wh %08x, wtest %08x", BUILD_TAG, (unsigned)g_pf_vs, (unsigned)sr, (unsigned)(u32)g_wh, (unsigned)(u32)g_wtv);
        log_seen = g_netlog_n > 16 ? g_netlog_n - 16 : 0;
        u32 last_rx = g_pf_vs, next_s = 0;
        while (h >= 0) {
            /* incoming commands */
            int got = nd_sock(3, h, rxb, sizeof rxb);
            if (got > 0) {
                last_rx = g_pf_vs;
                for (int i = 0; i < got; i++) {
                    char c = rxb[i];
                    if (c == '\n' || c == '\r') { if (cl_n) { cmdl[cl_n] = 0; cl_n = 0; cmd(cmdl); } }
                    else if (cl_n < (int)sizeof cmdl - 1) cmdl[cl_n++] = c;
                }
            }
            /* events */
            if (g_exc_n != exc_seen) {
                exc_seen = g_exc_n; volatile u32 *e = g_exc;
                out("E %u code %u cause %08x epc %08x bad %08x thr %d sr %08x ra %08x sp %08x", (unsigned)g_exc_n, (unsigned)(e[0] >> 2 & 31), (unsigned)e[0],
                    (unsigned)e[1], (unsigned)e[2], (int)e[19], (unsigned)e[3], (unsigned)e[4], (unsigned)e[5]);
            }
            if (g_wh[0] != bp_seen) { bp_seen = g_wh[0]; wh_report(); if (--bp_left > 0) bp_arm(); else out("> watch done"); }
            while ((int)log_seen < g_netlog_n) { out("L %s", g_netlog[log_seen % 16]); log_seen++; }
            if (mir_n) { for (int i = 0; i < mir_n; i++) out("R %s", (const char *)mir_p[i]); mir_n = 0; }
            /* status */
            if (stream && (int)(g_pf_vs - next_s) >= 0) {
                next_s = g_pf_vs + (u32)(rate * 60 / 1000);
                char inb[48]; int il = 0; inb[0] = 0;
                for (int k = 0; k < 32 && il < 36; k++) { u32 id = g_if[k].idx; if (id) il += snprintf(inb + il, sizeof inb - il, " %u", (unsigned)(id & 0xffff)); }
                out("S %u fr %d w %d pg %d calls %u opens %u exc %u prof %u send %u in%s", (unsigned)g_pf_vs, sh_frame_now(), g_in_world, sh_state_now(),
                    (unsigned)g_calls, (unsigned)g_opn, (unsigned)g_exc_n, &g_pcn ? (unsigned)g_pcn : 0u, (unsigned)g_mon_insend, inb);
            }
            prof_send();
            hist_send();
            sp_tick(out, stream);
            gsw_tick(out, stream);
            crash_tick(out);
            if (tx_n && flush() < 0) break;
            if (g_pf_vs - last_rx > 60 * 10) { break; }       /* the console pings every second: 10 s of silence = gone */
            DelayThread(50 * 1000);
        }
        g_dbg_up = 0; mir_n = 0;
        nd_sock(4, h, 0, 0); h = -1;
        DelayThread(2 * 1000 * 1000);
    }
}
void dbg_start(void)
{
    ap_on = 0; for (int i = 0; i < 5; i++) ap_site[i] = 0;   /* .xcmem is not cleared at load */
    pt_n = 0;
    ee_thread_t t; memset(&t, 0, sizeof t);
    t.func = (void *)dbg_thread; t.stack = dbg_stack; t.stack_size = sizeof dbg_stack; t.initial_priority = 0; t.gp_reg = &_gp;
    int id = CreateThread(&t); if (id >= 0) StartThread(id, NULL);
}
#endif
