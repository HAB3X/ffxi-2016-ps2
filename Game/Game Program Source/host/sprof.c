/* sprof.c - NETDIAG builds only: sampling profiler for the debug link (NETDIAG51).

   Where does the frame time go, without knowing in advance which function to time?  The EE's performance counter 0 counts the
   cycles the CPU spends in user mode (the game and the host run in user mode; the kernel, interrupt handlers and the idle wait do
   not count).  Every PERIOD such cycles the counter overflows and raises the performance-counter exception (level 2, vector
   0x80000080).  sp_vec below, copied onto that vector, writes the interrupted program counter (ErrorEPC) into a ring and returns.
   The debug thread (dbg.c) empties the ring every 50 ms, looks up the function each address belongs to, and once a second sends
     "P vbl n N lost L busy B% | f1 c1 f2 c2 ..."   samples in the last second, user-mode share of the CPU, the 10 busiest functions
   'samp top [N]' lists the busiest functions since 'samp 1' or 'samp clear' ("P top i func ADDR n COUNT PCT%").

   Function lookup: the game was compiled by gcc, so a function starts with "addiu sp, sp, -N" or right after the previous
   function's "jr ra" + delay slot (leaf functions have no stack frame).  Scanning back from the sample to the nearest of the two
   gives the start; an early "jr ra" in the middle of a function would split it, which gcc-built code rarely has.

   The vector handler only has k0/k1, which the kernel's own exception code may be using if a sample lands on its first
   instructions: they are parked in the cache tag registers (TagLo/TagHi, used only by cache-maintenance instructions) and put
   back.  Level-2 exceptions are blocked while ERL is set, so it cannot interrupt itself or the watchpoint handler (dbg_l2).
   PCSX2 counts but never raises this exception: 'samp 1' checks that samples arrive and switches off again if they do not.

   Placement: normal .text/.bss (the .dbgk / .xcmem area after the lifted kernel is full). */
#ifdef NETDIAG
#include <tamtypes.h>
#include <kernel.h>
#include <delaythread.h>
#include <string.h>
#include <stdio.h>
#include <stdlib.h>

typedef void (*out_fn)(const char *fmt, ...);
extern volatile u32 g_pf_vs;

#define SP_RING 1024                                       /* samples; the debug thread empties it every 50 ms */
#define SP_VEC  0x80000080u
#define FN_N    256                                        /* functions counted (open addressing) */
#define CYC_HZ  294912000u

/* [0] samples taken (handler), [1] counter reload value (0x80000000 - PERIOD), ring from [16] */
volatile u32 g_sp[16 + SP_RING] __attribute__((aligned(64)));

__asm__(
    ".set push\n.set noreorder\n.set noat\n"
    ".pushsection .text\n"
    ".globl sp_vec\n.ent sp_vec\n"
    "sp_vec:\n"
    "mtc0  $k0, $28\n"                      /* park k0 / k1 in TagLo / TagHi */
    "mtc0  $k1, $29\n"
    "sync.p\n"
    "lui   $k0, %hi(g_sp)\n"
    "addiu $k0, $k0, %lo(g_sp)\n"
    "lui   $k1, 0x8000\n"
    "or    $k0, $k0, $k1\n"                 /* kseg0: kuseg is unmapped while ERL = 1 */
    "lw    $k1, 4($k0)\n"
    "mtpc  $k1, 0\n"                        /* next sample after PERIOD more user-mode cycles (clears bit 31) */
    "sync.p\n"
    "lw    $k1, 0($k0)\n"
    "addiu $k1, $k1, 1\n"
    "sw    $k1, 0($k0)\n"
    "andi  $k1, $k1, 1023\n"                /* SP_RING - 1 */
    "sll   $k1, $k1, 2\n"
    "addu  $k0, $k0, $k1\n"
    "mfc0  $k1, $30\n"                      /* ErrorEPC: where the program was */
    "sw    $k1, 64($k0)\n"
    "mfc0  $k0, $28\n"
    "mfc0  $k1, $29\n"
    "sync.l\n"
    "eret\n"
    "nop\n"
    ".globl sp_vec_end\n"
    "sp_vec_end:\n"
    ".end sp_vec\n"
    ".popsection\n"
    ".set pop\n");
extern u32 sp_vec[], sp_vec_end[];

static u32 vsave[32], vsaved = 0, on = 0, period = 0, rd = 0, lost = 0, lost_s = 0;
static u32 fk[FN_N], fs[FN_N], ft[FN_N], f_other_s = 0, f_other_t = 0, tot_s = 0, tot_t = 0;
static u32 next_p = 0, last_cyc = 0;

static u32 kmode_on(void)
{
    u32 sr; __asm__ volatile("mfc0 %0, $12" : "=r"(sr));
    __asm__ volatile("mtc0 %0, $12\n sync.p" :: "r"(sr & ~0x18u));
    return sr;
}
static void kmode_off(u32 sr) { __asm__ volatile("mtc0 %0, $12\n sync.p" :: "r"(sr)); }
static inline u32 cyc(void) { u32 c; __asm__ volatile("mfc0 %0, $9" : "=r"(c)); return c; }

static void counter_off(void) { __asm__ volatile("mtps $0, 0\n sync.p"); }
static void sp_stop(void)
{
    DIntr(); u32 sr = kmode_on();
    counter_off();
    if (vsaved) memcpy((void *)SP_VEC, vsave, sizeof vsave);
    kmode_off(sr); EIntr();
    FlushCache(0); FlushCache(2);
    on = 0;
}
static void sp_start(u32 per)
{
    u32 n = (u32)(sp_vec_end - sp_vec);
    period = per; g_sp[1] = 0x80000000u - per;
    DIntr(); u32 sr = kmode_on();
    counter_off();
    if (!vsaved) { memcpy(vsave, (void *)SP_VEC, sizeof vsave); vsaved = 1; }
    memcpy((void *)SP_VEC, sp_vec, n * 4);
    kmode_off(sr); EIntr();
    FlushCache(0); FlushCache(2);
    rd = g_sp[0]; lost = 0; next_p = g_pf_vs + 60; last_cyc = cyc();
    u32 r = g_sp[1], cfg = 0x80000000u | (16u << 15) | (1u << 5) | (1u << 4);  /* CTE, PCR1 event 16 (off), PCR0 cycles in user mode */
    __asm__ volatile("mtpc %0, 0\n mtpc $0, 1\n sync.p\n mtps %1, 0\n sync.p" :: "r"(r), "r"(cfg));
    on = 1;
}

/* ---- function lookup ---- */
static u32 fn_of(u32 pc)
{
    if (pc < 0x00100000 || pc >= 0x02000000 || (pc & 3)) return 0x80000000u;      /* kernel (should not happen: user mode only) */
    volatile u32 *p = (volatile u32 *)pc;
    for (int i = 0; i < 4096 && (u32)(p - 1) >= 0x00100000; i++) {
        u32 w = *p;
        if ((w >> 16) == 0x27BD && (w & 0x8000)) return (u32)p;                   /* addiu sp, sp, -N: a prologue */
        if ((w >> 16) == 0x67BD && (w & 0x8000)) return (u32)p;                   /* daddiu sp, sp, -N */
        if (w == 0x03E00008u && (u32)p + 4 < pc) {                                 /* jr ra of the function before */
            u32 s = (u32)p + 8;
            while (s < pc && *(volatile u32 *)s == 0) s += 4;                       /* alignment padding */
            return s;
        }
        p--;
    }
    return pc & ~0xFFFu;
}
static void count(u32 f)
{
    u32 h = (f >> 2) * 2654435761u >> 24;                  /* 8 bits */
    for (int i = 0; i < FN_N; i++) {
        u32 k = (h + i) & (FN_N - 1);
        if (fk[k] == f) { fs[k]++; ft[k]++; return; }
        if (!fk[k]) { fk[k] = f; fs[k] = 1; ft[k] = 1; return; }
    }
    f_other_s++; f_other_t++;
}
static void clear_all(void)
{
    memset(fk, 0, sizeof fk); memset(fs, 0, sizeof fs); memset(ft, 0, sizeof ft);
    f_other_s = f_other_t = tot_s = tot_t = 0; lost = lost_s = 0;
}

/* called by the debug thread every loop (50 ms): empty the ring, once a second send the P line */
void sp_tick(out_fn o, int show)
{
    if (!on) return;
    u32 n = g_sp[0];
    if (n - rd > SP_RING - 64) { u32 skip = n - rd - (SP_RING - 64); lost += skip; lost_s += skip; rd += skip; }
    while (rd != n) { rd++; count(fn_of(g_sp[16 + (rd & (SP_RING - 1))] & ~3u)); tot_s++; tot_t++; }
    if ((int)(g_pf_vs - next_p) < 0) return;
    next_p = g_pf_vs + 60;
    u32 c = cyc(), dc = c - last_cyc; last_cyc = c;
    u32 busy = dc ? (u32)((u64)tot_s * period * 100 / dc) : 0;
    if (show) {
        char b[200]; int bl = 0;
        u32 used[10]; int nu = 0;
        for (int r = 0; r < 10; r++) {                      /* the 10 busiest of the last second */
            int best = -1;
            for (int k = 0; k < FN_N; k++) {
                if (!fs[k]) continue;
                int u = 0; for (int j = 0; j < nu; j++) if (used[j] == (u32)k) u = 1;
                if (!u && (best < 0 || fs[k] > fs[best])) best = k;
            }
            if (best < 0) break;
            used[nu++] = (u32)best;
            bl += snprintf(b + bl, sizeof b - bl, " %06x %u", (unsigned)fk[best], (unsigned)fs[best]);
        }
        o("P %u n %u lost %u busy %u%% other %u |%s", (unsigned)g_pf_vs, (unsigned)tot_s, (unsigned)lost_s, (unsigned)busy, (unsigned)f_other_s, b);
    }
    memset(fs, 0, sizeof fs); f_other_s = 0; tot_s = 0; lost_s = 0;
}

/* 'samp 1 [RATE]' start (RATE samples per second of user-mode time, default 1000), 'samp 0' stop, 'samp top [N]', 'samp clear' */
void sp_cmd(char *s, out_fn o)
{
    while (*s == ' ') s++;
    if (!strncmp(s, "top", 3)) {
        int nmax = atoi(s + 3); if (nmax <= 0) nmax = 20; if (nmax > 40) nmax = 40;
        u32 prev_c = 0xFFFFFFFFu, prev_f = 0; int shown = 0;
        for (int r = 0; r < nmax; r++) {                    /* descending by count, ties by address */
            int best = -1;
            for (int k = 0; k < FN_N; k++) {
                if (!fk[k] || !ft[k]) continue;
                if (ft[k] > prev_c || (ft[k] == prev_c && fk[k] <= prev_f)) continue;
                if (best < 0 || ft[k] > ft[best] || (ft[k] == ft[best] && fk[k] < fk[best])) best = k;
            }
            if (best < 0) break;
            prev_c = ft[best]; prev_f = fk[best]; shown++;
            u32 pm = tot_t ? (u32)((u64)ft[best] * 1000 / tot_t) : 0;
            o("P top %d func %08x n %u %u.%u%%", r + 1, (unsigned)fk[best], (unsigned)ft[best], (unsigned)(pm / 10), (unsigned)(pm % 10));
        }
        o("> ok samp top: %u samples, %u lost, %u in functions past the table", (unsigned)tot_t, (unsigned)lost, (unsigned)f_other_t);
        return;
    }
    if (!strncmp(s, "clear", 5)) { clear_all(); o("> ok samp clear"); return; }
    int want = atoi(s);
    if (!want) { if (on) sp_stop(); o("> ok samp 0 (%u samples, %u lost)", (unsigned)tot_t, (unsigned)lost); return; }
    while (*s && *s != ' ') s++;
    int rate = atoi(s); if (rate <= 0) rate = 1000; if (rate < 50) rate = 50; if (rate > 5000) rate = 5000;
    if (on) sp_stop();
    clear_all();
    u32 n0 = g_sp[0];
    sp_start(CYC_HZ / (u32)rate);
    DelayThread(200 * 1000);
    if (g_sp[0] == n0) { sp_stop(); o("> err samp: no samples in 0.2 s - this CPU does not raise the counter exception (PCSX2 does not), off again"); return; }
    o("> ok samp 1: %d samples a second of user-mode time, %u in the first 0.2 s", rate, (unsigned)(g_sp[0] - n0));
}
#else
typedef int sprof_unused;
#endif
