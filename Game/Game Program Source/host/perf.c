/* perf.c - frame-rate counters for the benchmark (read over PINE).
   g_pf_vs     : vertical blanks counted by an INTC VBLANK_START handler (59.94 per second NTSC) = emulated wall time
   g_pf_frames : game frames (the per-frame function 0x2D8BE0 calls dev_frame_hook once per frame)
   g_pf_ft[]   : ring of the last 1024 frame times in vblanks*16 + sub-vblank cycles (see below), g_pf_ftc = cycles per frame
   g_pf_hist[] : histogram of frame times in whole vblanks (index 1..15, 0 unused, 15 = 15 or more)
   g_pf_calls  : service calls (slot stub entries counted by trap_c; release builds count only file calls)
   Cost: a few loads/stores per frame and per vblank. */
#include <tamtypes.h>
#include <kernel.h>
volatile u32 g_pf_vs = 0, g_pf_frames = 0, g_pf_hist[16], g_pf_ftc[1024], g_pf_ftv[1024], g_pf_maxv = 0, g_pf_on = 0;
static u32 last_vs, last_cyc;
static int vbl_id = -1;
#ifdef PROF
static void perf_prof_start(void);
#endif
#ifdef ALARM_VBL
extern void al_irq_check(void);
#endif
#ifdef NETDIAG
/* NETDIAG40: freeze colours, written straight to the GS display registers from this interrupt (no DMA, no IOP, no thread needed).
     YELLOW = a CPU exception (bad address, bus error, break, trap): flashes 1 s when it happens, and stays if the game then stops.
              About 45 s after sign-in one deliberate exception in a throwaway thread gives one yellow flash: the catcher works.
              Solid yellow that never changes = an exception inside an interrupt handler or the kernel (the CPU is held there).
     RED    = the report thread has been stuck inside a network send for 15 s: the IOP / network stopped answering
     BLUE   = the report thread (priority 0) has not run for 15 s and is not in a send: the EE scheduler stopped
     GREEN  = report thread fine, but no game frame for 10 s
   A picture that stays frozen with no colour at all = the EE stopped taking interrupts for another reason. */
volatile u32 g_mon_tick = 0, g_mon_insend = 0, g_flash = 0;
static u32 fz_last = 0, fz_lastv = 0, fz_tick = 0, fz_tickv = 0;
/* exception catcher (exc_catch below saves registers into g_exc and returns into exc_park on its own stack) */
volatile u32 g_exc[20], g_exc_n = 0, g_exc_real = 0; volatile int g_exc_testid = -1;
u8 g_exc_stack[4096] __attribute__((section(".xcmem"), aligned(64)));
void exc_park(void)
{
    u32 sr = g_exc[3], pc = g_exc[1];
    { extern volatile u32 g_rb_stop;                                       /* NETDIAG59: during 'reboot' (crash.c): MAGENTA */
      if (g_rb_stop) for (;;) { *(volatile u64 *)0x120000E0 = 0xE000E0; *(volatile u64 *)0x12000000 = 0x4; } }
    if (!(sr & 1) || !(sr & 0x10000) || pc < 0x100000 || pc >= 0x2000000) {   /* interrupts were off / kernel code: cannot sleep here */
        g_exc_n++; g_exc_real++;
        for (;;) { *(volatile u64 *)0x120000E0 = 0x00E0E0; *(volatile u64 *)0x12000000 = 0x4; }
    }
    int id = GetThreadId(); g_exc[19] = (u32)id;
    if (id != g_exc_testid) g_exc_real++;
    g_flash = 60; g_exc_n++;
    for (;;) SleepThread();
}
/* exc_catch: entered by the kernel's exception vector (k0 free). Saves the useful registers into g_exc, then returns from the
   exception into exc_park on its own stack (and the host's gp), which parks the faulting thread and lets everything else run on. */
__asm__(
    ".set push\n.set noreorder\n.set noat\n.text\n"
    ".globl exc_catch\n"
    ".ent exc_catch\n"
    "exc_catch:\n"
    "la    $k0, g_exc\n"
    "sw    $ra, 16($k0)\n"
    "sw    $sp, 20($k0)\n"
    "sw    $gp, 24($k0)\n"
    "sw    $1,  28($k0)\n"
    "sw    $v0, 32($k0)\n"
    "sw    $v1, 36($k0)\n"
    "sw    $a0, 40($k0)\n"
    "sw    $a1, 44($k0)\n"
    "sw    $a2, 48($k0)\n"
    "sw    $a3, 52($k0)\n"
    "sw    $t9, 56($k0)\n"
    "sw    $s0, 60($k0)\n"
    "sw    $s1, 64($k0)\n"
    "sw    $s2, 68($k0)\n"
    "mfc0  $v0, $13\n"
    "sw    $v0, 0($k0)\n"
    "mfc0  $v0, $14\n"
    "sw    $v0, 4($k0)\n"
    "mfc0  $v0, $8\n"
    "sw    $v0, 8($k0)\n"
    "mfc0  $v0, $12\n"
    "sw    $v0, 12($k0)\n"
    "la    $sp, g_exc_stack + 4096 - 64\n"
    "la    $gp, _gp\n"
    "la    $k0, exc_park\n"
    "mtc0  $k0, $14\n"
    "sync.p\n"
    "eret\n"
    "nop\n"
    ".end exc_catch\n"
    ".set pop\n");
void exc_install(void)
{
    extern void exc_catch(void);
    for (int i = 1; i < 4; i++) SetVTLBRefillHandler(i, exc_catch);
    for (int i = 1; i < 8; i++) SetVCommonHandler(i, exc_catch);
    for (int i = 9; i < 14; i++) SetVCommonHandler(i, exc_catch);
}
static void freeze_colour(void)
{
    extern int sh_frame_now(void);
    u32 v = g_pf_vs, f = (u32)sh_frame_now();
    if (f != fz_last) { fz_last = f; fz_lastv = v; }
    if (g_mon_tick != fz_tick) { fz_tick = g_mon_tick; fz_tickv = v; }
    u64 col = 0;
    if (g_flash) {                                                                 /* yellow: an exception just happened */
        if (--g_flash == 0) { *(volatile u64 *)0x120000E0 = 0; return; }           /* NETDIAG41: then black again (the game sets PMODE every */
        col = 0x00E0E0;                                                            /* frame but never BGCOLOR: it showed yellow behind the picture) */
    }
    else if (!fz_tick) return;                                                     /* report thread not watching yet */
    else if (v - fz_tickv > 900) col = g_mon_insend ? 0x0000E0 : 0xE00000;         /* red / blue */
    else if (v - fz_lastv > 600) col = g_exc_real ? 0x00E0E0 : 0x00C000;           /* yellow if an exception came first, else green */
    else return;
    *(volatile u64 *)0x120000E0 = col;                 /* BGCOLOR: R bits 0-7, G 8-15, B 16-23 */
    *(volatile u64 *)0x12000000 = 0x4;                 /* PMODE: both read circuits off -> the screen shows BGCOLOR */
}
#endif
static int vbl_handler(int c)
{
    (void)c; g_pf_vs++;
#ifdef ALARM_VBL
    al_irq_check();                                    /* overdue game alarms fire here (userfile.c) */
#endif
#ifdef NETDIAG
    freeze_colour();
#endif
    return -1;                                         /* -1: let the other handlers run too */
}
static inline u32 cyc(void) { u32 c; __asm__ volatile("mfc0 %0, $9" : "=r"(c)); return c; }
void perf_init(void)
{
    if ((vbl_id = AddIntcHandler(INTC_VBLANK_S, vbl_handler, 0)) >= 0) { EnableIntc(INTC_VBLANK_S); g_pf_on = 1; }
#ifdef PROF
    perf_prof_start();
#endif
}
void perf_stop(void)                                   /* crash.c reboot: the handler goes before PS2LINK starts */
{
    if (vbl_id >= 0) { RemoveIntcHandler(INTC_VBLANK_S, vbl_id); vbl_id = -1; }
    *(volatile u64 *)0x120000E0 = 0;                   /* no freeze colour left behind */
}
void perf_frame(void)
{
    u32 v = g_pf_vs, c = cyc(), dv = v - last_vs, i = g_pf_frames & 1023;
    if (g_pf_frames) {
        g_pf_ftv[i] = dv; g_pf_ftc[i] = c - last_cyc;
        g_pf_hist[dv < 15 ? dv : 15]++;
        if (dv > g_pf_maxv) g_pf_maxv = dv;
    }
    last_vs = v; last_cyc = c; g_pf_frames++;
}
#ifdef PROF
/* sampling profiler (PROF builds only): every 16 horizontal blanks (~1 ms) the interrupted program counter is recorded.
   g_pf_pc[] ring of 8192 samples, g_pf_pcn count; a profiler can bin them by function of the 2016 program. */
volatile u32 g_pf_pc[8192], g_pf_pcn = 0;
static void prof_tick(s32 id, u16 time, void *arg)
{
    u32 epc; (void)id; (void)time; (void)arg; __asm__ volatile("mfc0 %0, $14" : "=r"(epc));
    g_pf_pc[g_pf_pcn++ & 8191] = epc;
    iSetAlarm(16, prof_tick, 0);
}
static void perf_prof_start(void) { SetAlarm(16, prof_tick, 0); }
#endif
