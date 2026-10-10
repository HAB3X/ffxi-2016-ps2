/* crash.c - NETDIAG56: crash recovery for the debug link (dbg.c).
   1. Automatic report: when the game stops (a CPU exception in a game thread, or no game frame for 12 s after it had been
      drawing), the debug thread sends one report between 'C begin REASON' and 'C end': thread list (with where each one is),
      semaphores, the last host log lines and the graphics / DMA / interrupt registers.  ps2dbg.py saves it as crash-HHMMSS.txt.
      Again only after the game has drawn frames again.  'crash' sends one by hand.
   2. 'reboot': back to PS2LINK without touching the console.  The PS2 asks the PC (ps2dbg.py) for PS2LINK.ELF's program
      segment, which arrives over the debug link straight into the place it runs from (0x94000, below the host - nothing of
      ours is there).  Then, like ps2link's own 'execee': every other thread is suspended, our interrupt / alarm code stops,
      the IOP is reset, and ExecPS2 starts PS2LINK, which reads its network settings from its defaults (192.168.1.11).
      Not possible when the EE no longer takes interrupts (frozen picture with no colour): then only the power button helps. */
#ifdef NETDIAG
#include <tamtypes.h>
#include <kernel.h>
#include <sifrpc.h>
#include <loadfile.h>
#include <iopcontrol.h>
#include <string.h>
#include <stdlib.h>
#include <delaythread.h>

typedef void (*out_fn)(const char *, ...);
extern volatile u32 g_pf_vs, g_pf_frames, g_exc_real;
extern void dbg_run(const char *c);
extern int dbg_handle(void), dbg_flush_now(void);
extern int nd_sock(int op, int h, void *p, int n);
extern void perf_stop(void), _ps2sdk_deinit_timer(void);
extern void sp_cmd(char *s, out_fn o);
volatile u32 g_rb_stop = 0, g_rb_step = 0;   /* g_rb_step: how far the reboot got - perf.c shows it as the colour of an exception */                                 /* set just before ExecPS2: our interrupt and alarm code does nothing */

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

/* ---- reboot to PS2LINK ---- */
static int rx(int h, u8 *p, int n, u32 until)              /* n bytes, or -1 when the link fails / time runs out */
{
    int got = 0;
    while (got < n) {
        int r = nd_sock(3, h, p + got, n - got > 4096 ? 4096 : n - got);
        if (r > 0) { got += r; continue; }
        if (r < 0 || (int)(g_pf_vs - until) > 0) return -1;
        DelayThread(2 * 1000);
    }
    return got;
}

void rb_cmd(out_fn o)
{
    int h = dbg_handle();
    o("R getelf"); if (dbg_flush_now() < 0) return;           /* ps2dbg.py answers "ELF vaddr filesz memsz entry\n", then each 'R getchunk' */
    u32 until = g_pf_vs + 60 * 20;
    char ln[96]; int n = 0; u8 c;
    for (;;) {                                                /* the header line (keepalive newlines before it are skipped) */
        if (rx(h, &c, 1, until) < 0) { o("> err reboot: no answer from ps2dbg.py (is it the NETDIAG56 one?)"); return; }
        if (c == '\n') { if (n) break; continue; }
        if (n < (int)sizeof ln - 1) ln[n++] = (char)c;
    }
    ln[n] = 0;
    u32 v4[4] = { 0 }; int k = 0;
    if (!strncmp(ln, "ELF ", 4)) { char *q = ln + 4, *e; for (; k < 4; k++) { v4[k] = strtoul(q, &e, 16); if (e == q) break; q = e; } }
    u32 va = v4[0], fs = v4[1], ms = v4[2], ep = v4[3];
    if (k != 4 || !fs) {
        o("> err reboot: ps2dbg.py answered '%s'", ln); return;
    }
    if (va < 0x00090000 || va + ms > 0x00100000 || fs > ms || ep < va || ep >= va + fs) {
        o("> err reboot: PS2LINK.ELF does not fit below the host (%08x + %x)", (unsigned)va, (unsigned)ms); return;
    }
    /* 0x94000.. is free while the game runs (nothing is loaded or allocated below the host at 0x100000), and the socket
       library may need its other threads to receive, so the game keeps running until the segment is in */
    for (u32 off = 0; off < fs; off += 8192) {               /* 8 KB at a time, each one asked for: no long burst (PCSX2's DEV9 TCP lost */
        u32 m = fs - off < 8192 ? fs - off : 8192;           /* step on a 230 KB burst and reset the link) */
        o("R getchunk %x %x", (unsigned)off, (unsigned)m);
        if (dbg_flush_now() < 0 || rx(h, (u8 *)va + off, (int)m, g_pf_vs + 60 * 10) < 0) {
            o("> err reboot: PS2LINK.ELF did not arrive (stopped at %x of %x; the game carries on)", (unsigned)off, (unsigned)fs); return;
        }
    }
    int me = GetThreadId();
    for (int t = 1; t < 256; t++) if (t != me) SuspendThread(t);  /* from here on the game is given up */
    memset((u8 *)va + fs, 0, ms - fs);
    o("> ok reboot: PS2LINK (%u bytes) is in place, starting it", (unsigned)fs);
    /* NETDIAG59: NETDIAG58 went solid yellow on the PS2 (a CPU exception with interrupts off) somewhere between here and
       PS2LINK.  Each step now reports on the link (R step N) while it still can, and the screen colour tells the rest:
       magenta = an exception after the reboot began (perf.c), anything else = PS2LINK's own screen. */
    o("R step 1 threads stopped"); dbg_flush_now();
    sp_cmd("0", o);                                           /* sampling profiler vector off, if it was on */
    o("R step 2 closing the link; next our handlers and alarms stop, the interrupts go off, the IOP is reset and PS2LINK starts");
    dbg_flush_now();
    DelayThread(200 * 1000);
    nd_sock(4, h, 0, 0);                                      /* the network needs the SIF interrupts, timer 2 (DelayThread) and the game's alarms */
    g_rb_step = 3; g_rb_stop = 1;                             /* (NETDIAG59 set g_rb_stop before closing: the socket library waits on */
    perf_stop();                                              /*  an alarm, which then never came - the link hung after step 2) */
    g_rb_step = 4;
    { int o2 = DIntr();                                       /* every interrupt / DMA-end source off except timer 3 (the kernel's alarms): */
      for (int c = 0; c < 15; c++) if (c != 12) DisableIntc(c);   /* the game's handlers stay registered in the kernel but are never called */
      for (int c = 0; c < 10; c++) DisableDmac(c);
      if (o2) EIntr(); }
    g_rb_step = 5; _ps2sdk_deinit_timer();
    g_rb_step = 6; SifInitRpc(0); SifExitRpc();
    g_rb_step = 7; SifIopReset(NULL, 0);
    g_rb_step = 8; while (!SifIopSync()) { }
    g_rb_step = 9; SifInitRpc(0); SifExitRpc(); SifLoadFileExit();
    g_rb_step = 10; FlushCache(0); FlushCache(2);             /* (NETDIAG58: no DIntr here - ps2link's own execee leaves interrupts on) */
    static char a0[] = "mass:/PS2LINK/PS2LINK.ELF";
    static char *argv[1] = { a0 };
    g_rb_step = 11;                                           /* an exception from here on is in ExecPS2 or PS2LINK itself (before it sets up its own) */
    ExecPS2((void *)ep, 0, 1, argv);
}
#else
typedef int crash_unused;
#endif
