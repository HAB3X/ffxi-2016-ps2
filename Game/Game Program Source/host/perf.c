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
#ifdef PROF
static void perf_prof_start(void);
#endif
#ifdef ALARM_VBL
extern void al_irq_check(void);
#endif
static int vbl_handler(int c)
{
    (void)c; g_pf_vs++;
#ifdef ALARM_VBL
    al_irq_check();                                    /* overdue game alarms fire here (userfile.c) */
#endif
    return -1;                                         /* -1: let the other handlers run too */
}
static inline u32 cyc(void) { u32 c; __asm__ volatile("mfc0 %0, $9" : "=r"(c)); return c; }
void perf_init(void)
{
    if (AddIntcHandler(INTC_VBLANK_S, vbl_handler, 0) >= 0) { EnableIntc(INTC_VBLANK_S); g_pf_on = 1; }
#ifdef PROF
    perf_prof_start();
#endif
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
