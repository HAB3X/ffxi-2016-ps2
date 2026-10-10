/* crash.c - NETDIAG56: crash report for the debug link (dbg.c).
   When the game stops (a CPU exception in a game thread, or no game frame for 12 s after it had been drawing), the debug thread
   sends one report between 'C begin REASON' and 'C end': thread list (with where each one is), semaphores, the last host log
   lines and the graphics / DMA / interrupt registers.  ps2dbg.py saves it as crash-HHMMSS.txt.  Again only after the game has
   drawn frames again.  'crash' sends one by hand.
   (NETDIAG56-61 also had 'reboot', back to PS2LINK over the link; dropped in NETDIAG62 - more trouble than it was worth.) */
#ifdef NETDIAG
#include <tamtypes.h>
#include <kernel.h>

typedef void (*out_fn)(const char *, ...);
extern volatile u32 g_pf_vs, g_pf_frames, g_exc_real;
extern void dbg_run(const char *c);

static u32 last_fr, last_frv, last_exc, armed;

static void report(out_fn o, const char *why)
{
    o("C begin %s vbl %u frames %u", why, (unsigned)g_pf_vs, (unsigned)g_pf_frames);
    static const char *const cmds[] = { "thr", "sema", "log",
        "peek 0x10003020 4", "peek 0x10003c00 4", "peek 0x10009000 48", "peek 0x1000a000 48", "peek 0x1000e000 32",
        "peek 0x1000f000 16", "peek 0x12001000 8" };
    for (unsigned i = 0; i < sizeof cmds / sizeof cmds[0]; i++) dbg_run(cmds[i]);
    o("C end");
}

void crash_tick(out_fn o)
{
    u32 v = g_pf_vs, fr = g_pf_frames;
    if (fr != last_fr) { if (last_fr) armed = 1; last_fr = fr; last_frv = v; }
    if (g_exc_real != last_exc) { last_exc = g_exc_real; report(o, "exception"); return; }
    if (armed && v - last_frv > 60 * 12) { armed = 0; report(o, "no game frame for 12 s"); }
}
void crash_cmd(out_fn o) { report(o, "asked for"); }

#else
typedef int crash_unused;
#endif
