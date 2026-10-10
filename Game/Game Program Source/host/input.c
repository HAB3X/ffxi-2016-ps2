/* Input bring-up for the 2016 host (pad, keyboard, mouse).
   The game only calls the *polling* half of the kernel's input libraries (scePadRead/GetState/..., sqKbdUpdate, sqMouseOpen/Update...);
   the one-time setup (padman load, scePadInit/PortOpen, the HID module RPC binds) was done by the PlayOnline kernel before the game
   started.  All of those library functions are lifted from the 2007 kernel (lift2.py entries), this file just performs the setup. */
#include <stdio.h>
#include <string.h>
#include <tamtypes.h>
#include <kernel.h>
#include <sifrpc.h>
#include <loadfile.h>
#include <libpad.h>
#include "host.h"

extern const LiftSet lift_k_set;
extern void *_gp;
volatile u32 g_input_step = 0;              /* progress marker, readable over PINE */
volatile int g_pad_rc[4];                   /* [0]=scePadInit, [1]=PortOpen(0,0), [2]=PortOpen(1,0) */
volatile int g_pad_state = -1;              /* last scePadGetState(0,0), updated by the watcher thread */
volatile u32 g_pad_btn = 0;                 /* last button word read (active low, as scePadRead returns it) */
volatile u32 g_kbd_ready = 0, g_mouse_ready = 0;

static u8 pad_buf[2][256] __attribute__((aligned(64)));   /* DMA buffers for scePadPortOpen */

static unsigned ent(const char *n) { return lift_entry_addr(&lift_k_set, n); }

static int load_rom(const char *p)
{
    int ret = 0, id = SifLoadStartModule(p, 0, NULL, &ret);
    printf("[host] input: %s -> id=%d ret=%d\n", p, id, ret);
    return id;
}

/* Kbd/mouse module init waits until the Square IOP side (HID000 via SQIOPMEM) reports module 18 / 19 ready, so it runs on its own thread. */
static u8 kth_stack[2][16384] __attribute__((aligned(16)));
static void kbd_thread(void *arg)
{
    g_input_step = 100;
    printf("[host] kbd thread start\n");
    unsigned a = ent("sqKbdModuleInit"); printf("[host] kbd init fn %08x\n", a);
    if (a) { ((void (*)(void))a)(); g_kbd_ready = 1; printf("[host] input: sqKbdModuleInit returned\n"); }
    ExitDeleteThread();
}
static void mouse_thread(void *arg)
{
    unsigned a = ent("sqMouseModuleInit"); printf("[host] mouse init fn %08x\n", a);
    if (a) { ((void (*)(void))a)(); g_mouse_ready = 1; printf("[host] input: sqMouseModuleInit returned\n"); }
    ExitDeleteThread();
}
static int spawn(void (*fn)(void *), void *stack, int size, int prio)
{
    ee_thread_t t; memset(&t, 0, sizeof t);
    t.func = (void *)fn; t.stack = stack; t.stack_size = size; t.initial_priority = prio;
    t.gp_reg = &_gp;
    int id = CreateThread(&t);
    if (id >= 0) StartThread(id, NULL);
    return id;
}

volatile u32 g_tri_edge = 0;
#ifdef INPUT_WATCH
static u8 wth_stack[16384] __attribute__((aligned(16)));
static void watch_thread(void *arg)
{
    struct padButtonStatus b __attribute__((aligned(64)));
    int last = -2; u32 lastb = 0xffffffff;
    for (;;) {
        int st = padGetState(0, 0); g_pad_state = st;
        if (st == PAD_STATE_STABLE || st == PAD_STATE_FINDCTP1) { if (padRead(0, 0, &b)) g_pad_btn = b.btns; }
        if (st != last || g_pad_btn != lastb) { printf("[host] pad(0,0) state=%d btn=%04x\n", st, g_pad_btn); last = st; lastb = g_pad_btn; }
        for (volatile int k = 0; k < 2000000; k++) { }
    }
}
#endif

#ifdef INPUT_DIAG
static u8 dth_stack[16384] __attribute__((aligned(16)));
static void diag_thread(void *arg)
{
    unsigned q = ent("sqmemQuery"), p = ent("sqmemPoll");
    for (int id = 0; id < 40; id++) {
        int r = ((int (*)(int))q)(id); unsigned out[4] = {0xdead, 0, 0, 0}; int pr = 0;
        for (int t = 0; t < 50 && !pr; t++) { pr = ((int (*)(unsigned *))p)(out); for (volatile int k = 0; k < 200000; k++) { } }
        printf("[host] diag sqmem module %d: query=%d poll=%d out=%08x\n", id, r, pr, out[0]);
    }
    ExitDeleteThread();
}
#endif

/* keyboard/mouse: the kernel's own init (lifted) waits for IOP parameters 0x12/0x13, which HID000/squsb sets a few seconds after
   the USB bus is enumerated, then binds the RPC servers 0x1f10/0x1f00.  Must run after the lifted sqmem client lock is initialised. */
static volatile int g_wait_tid = 0;
static void wake_cb(s32 id, u16 t, void *arg) { (void)id; (void)t; (void)arg; iWakeupThread(g_wait_tid); }
extern void host_sqdelay(u32 ticks);
volatile u32 g_hid_ready = 0;                 /* kbd+mouse init finished, lifted kbd/mouse slots usable */
volatile u32 g_hid_started = 0;
static int hid_tid = -1;
static u8 hid_stack[32768] __attribute__((aligned(16)));
/* The kernel's keyboard/mouse init breaks sceMount when run before it, so it runs on its own thread right after the mount returned
   (trap_c wakes it); until then the kbd/mouse slots answer "nothing" (see trap_c) and sqMouseOpen is performed here. */
static void hid_thread(void *arg)
{
    SleepThread();
    unsigned ak = ent("sqKbdModuleInit"), am = ent("sqMouseModuleInit"), mo = ent("sqMouseOpen");
    hlog(9, ak, am, mo, 0, 0, 0, "hid: init start kbd/mouse/open", 0, 0); hlog_kick();
    if (ak) ((void (*)(void))ak)();
    hlog(9, 0, 0, 0, 0, 0, 0, "hid: kbd init returned", 0, 0); hlog_kick();
    {   /* the layout table the PlayOnline kernel used to hand over (sqPolSetKeyboardId = slot 707): copies it, de-scrambles, sqKbdOpen */
        extern const unsigned char kbd_layout_table[];
        unsigned sk = ent("sqPolSetKeyboardId");
        if (sk) { ((void (*)(const void *, int))sk)(kbd_layout_table, 0); hlog(9, sk, 0, 0, 0, 0, 0, "hid: sqPolSetKeyboardId done", 0, 0); hlog_kick(); }
    }
    if (am) ((void (*)(void))am)();
    hlog(9, 0, 0, 0, 0, 0, 0, "hid: mouse init returned", 0, 0); hlog_kick();
    if (mo) { int h = ((int (*)(int, int, int, int, int, int))mo)(0, 0x200, 0, 0x1c0, 1, 0x32); hlog(9, (u32)h, 0, 0, 0, 0, 0, "hid: sqMouseOpen handle", 0, 0); hlog_kick(); }
    g_hid_ready = 1;
    hlog(9, 0, 0, 0, 0, 0, 0, "hid: ready", 0, 0); hlog_kick();
    ExitDeleteThread();
}
void input_hid_prepare(void)
{
    ee_thread_t t; memset(&t, 0, sizeof t);
    t.func = (void *)hid_thread; t.stack = hid_stack; t.stack_size = sizeof hid_stack; t.initial_priority = 30; t.gp_reg = &_gp;
    hid_tid = CreateThread(&t); if (hid_tid >= 0) StartThread(hid_tid, NULL);
}
void input_hid_go(void)                        /* called from trap_c (game thread) once sceMount returned */
{
    if (g_hid_started || hid_tid < 0) return;
#ifdef HID_NEVER
    return;
#endif
    g_hid_started = 1; WakeupThread(hid_tid);
}

int input_init(void)
{
    g_input_step = 1;
    /* 1. PS2 pad stack lives in the BIOS ROM (the disc's IOPRP.IMG does not carry it): SIO2MAN + PADMAN, then the SDK's libpad.
          (the lifted 2007 libpad was tried first: its PortOpen hangs with padman reporting "DMA Busy") */
    int a = load_rom("rom0:SIO2MAN"), b = load_rom("rom0:PADMAN");
    g_input_step = 2;
    if (a >= 0 && b >= 0) {
        g_pad_rc[0] = padInit(0);
        g_pad_rc[1] = padPortOpen(0, 0, pad_buf[0]);
        g_pad_rc[2] = padPortOpen(1, 0, pad_buf[1]);
        printf("[host] input: padInit=%d padPortOpen(0,0)=%d padPortOpen(1,0)=%d\n", g_pad_rc[0], g_pad_rc[1], g_pad_rc[2]);
    }
    g_input_step = 3;
    /* 2. keyboard / mouse: RPC binds to HID000.ERX's servers (0x1f10 keyboard, 0x1f00 mouse) inside the lifted kernel code */
#ifdef INPUT_DIAG
    spawn(diag_thread, dth_stack, sizeof dth_stack, 15);
#endif
#ifdef INPUT_WATCH
    spawn(watch_thread, wth_stack, sizeof wth_stack, 60);
#endif
    g_input_step = 4;
    return 0;
}

/* ---- scePad* services (slots 592-605) mapped onto the SDK's libpad (same arguments; Sony's scePadRead returns the byte count) ---- */
u32 svc_scePadRead(int port, int slot, void *d)
{
    struct padButtonStatus *b = (struct padButtonStatus *)d;
    if (!padRead(port, slot, b)) return 0;
    if (b->mode == 0x41) {
        /* 6 Oct 2026: the pad was never switched to analog (input_init did not call padSetMainMode), so the real sticks never
           reached the game. Ask libpad once per port (asynchronous request, no waiting) as soon as the pad is stable. */
        static int asked[2]; static int frames[2];
        if (port >= 0 && port < 2 && asked[port] < 4 && ++frames[port] > 30) {
            int st = padGetState(port, slot);
            if (st == PAD_STATE_STABLE || st == PAD_STATE_FINDCTP1) { padSetMainMode(port, slot, PAD_MMODE_DUALSHOCK, PAD_MMODE_LOCK); asked[port]++; frames[port] = 0;
                printf("[host] input: padSetMainMode(%d) analog request %d\n", port, asked[port]); }
        }
        b->rjoy_h = b->rjoy_v = b->ljoy_h = b->ljoy_v = 0x80; b->mode = 0x73;   /* until then: digital pad presented as a centred DualShock */
    }
    { extern volatile u32 g_tri_edge; static u16 prev = 0xffff; if (!(b->btns & 0x1000) && (prev & 0x1000)) g_tri_edge++; prev = b->btns; }   /* triangle press: random-name request for the name box (devdlg.c) */
    { extern volatile int g_input_block; if (g_input_block) b->btns = 0xffff; }   /* the developer login screen owns the input */
    return 32;
}
u32 svc_scePadInfoAct(int p, int s, int act, int cmd)       { return padInfoAct(p, s, act, cmd); }
u32 svc_scePadInfoComb(int p, int s, int l, int o)          { return 0; }   /* not in the SDK libpad; the game does not call it */
u32 svc_scePadInfoMode(int p, int s, int t, int o)
{
    int r = padInfoMode(p, s, t, o);
#ifndef PAD_NO_FAKE_DUALSHOCK
    if (t == PAD_MODECURID || t == PAD_MODECUREXID) return 7;      /* tell the game it is a DualShock; makes it read the pad, which currently stalls the file layer */
#endif
    return r;
}
u32 svc_scePadSetActDirect(int p, int s, const char *a)     { return padSetActDirect(p, s, a); }
u32 svc_scePadSetActAlign(int p, int s, const char *a)      { return padSetActAlign(p, s, a); }
u32 svc_scePadGetState(int p, int s)                        { return padGetState(p, s); }
u32 svc_scePadGetReqState(int p, int s)                     { return padGetReqState(p, s); }
u32 svc_scePadSetMainMode(int p, int s, int m, int l)       { (void)p; (void)s; (void)m; (void)l; return 1; }   /* analog mode is set once in input_init (the live SDK call hangs the game later) */
u32 svc_scePadInfoPressMode(int p, int s)                   { return padInfoPressMode(p, s); }
u32 svc_scePadEnterPressMode(int p, int s)                  { (void)p; (void)s; return 1; }
u32 svc_scePadExitPressMode(int p, int s)                   { (void)p; (void)s; return 1; }
