/* Network services for the 2016 host.

   Design: the socket services (slots 217-253, 478, 1080) are the 2007 PlayOnline kernel's own sq* socket library, lifted
   into the host by lift2.py (spec: k_spec_net.json).  That library talks over SIF RPC 0xF000.. to the Sony IOP stack the
   real game uses: avetcp (tcp005.erx) + ndglue/smap/avedhcp/sqiopint (ndi002.erx).  Nothing here re-implements TCP/UDP.

   What the host must add (the 2016 program never does it, POL did it before launching the game):
     1. load the two IOP modules through SQIOPMEM            (net_load_modules)
     2. sqInitSocketAPI(3)  = built-in Ethernet adapter      (net_bringup)
     3. configure the interface: DHCP or a static address, default route, DNS
     4. answer the few sqPolcon* network/message queries the game still makes without POLCON (svc_polcon_*)
   Bring-up is lazy: it runs on the first sqInetGetSafeUdpPort / sqCreateSocket / sqCreateDatagramSocket / sqGetHostByName
   call, on a helper thread with a big stack (game threads have tiny stacks), so the game's mount of pfs1: has happened. */
#include <stdio.h>
#include <stdarg.h>
#include <stdlib.h>
#include <string.h>
#include <tamtypes.h>
#include <kernel.h>
#include <delaythread.h>
#include "host.h"
#include <debug.h>

extern const LiftSet lift_k_set;
extern int sqmem_load(const char *path, const char *args, int cmd, u32 size);
extern int sq_ready;

/* ---- configuration (override before the first network call, or at build time with -D) ---- */
#ifndef NET_FORCE_DISC
#define NET_FORCE_DISC 0
#endif
#ifndef NET_POLCON_STATUS
#define NET_POLCON_STATUS 0     /* what sqPolconGetNetworkStatus reports once our bring-up worked (1 sends the game down the full PlayOnline login path, which needs the POL services) */
#endif
#ifndef NET_USE_DHCP
#define NET_USE_DHCP 1                      /* 1: DHCP (PCSX2 InterceptDHCP, or the LAN's server); 0: static address below */
#endif
#ifndef NET_IP
#define NET_IP   "192.168.1.222"
#endif
#ifndef NET_MASK
#define NET_MASK "255.255.255.0"
#endif
#ifndef NET_GW
#define NET_GW   "192.168.1.1"
#endif
#ifndef NET_DNS1
#define NET_DNS1 "192.168.1.1"
#endif
/* module sources, tried in order: 2007 viewer builds (ETHER class, MTU 1454) copied to the game partition, then the
   2003 builds that sit on the disc.  SQIOPMEM retries a failed open FOREVER, so a path is only used if it can be probed. */
#ifndef NET_TCP_PFS
#define NET_TCP_PFS "pfs1:/image/ffxi/prog/ps2/modules/tcp005.erx"
#define NET_NDI_PFS "pfs1:/image/ffxi/prog/ps2/modules/ndi002.erx"
#endif
#ifndef NET_TCP_DISC
#define NET_TCP_DISC "cdrom0:\\MODULES\\TCP000.ERX"     /* 2003 build; ETHER/PPP class unverified */
#define NET_NDI_DISC "cdrom0:\\MODULES\\NDI002.ERX"
#endif

#ifndef NET_TIMEOUT_S
#define NET_TIMEOUT_S 900                   /* NETDIAG: real PS2 + SATA needed several minutes (120 s gave up too early) */
#endif

typedef struct { s16 type; u16 port; u32 addr; u8 pad[24]; } SqAddr __attribute__((aligned(16)));   /* sqInternetAddress; kernel reads 20 bytes */

typedef int (*fn_v)(void);
typedef int (*fn_chk)(SqAddr *, SqAddr *, SqAddr *, SqAddr *, SqAddr *, SqAddr *, char *);
typedef int (*fn_cfg)(SqAddr *, SqAddr *, SqAddr *);
typedef int (*fn_rt)(SqAddr *, SqAddr *);
typedef int (*fn_dns)(const char *, SqAddr *, SqAddr *);
typedef int (*fn_i1)(int);
static void *E(const char *n) { return (void *)lift_entry_addr(&lift_k_set, n); }

volatile int g_net_state = 0;               /* 0 idle, 1 running, 2 up, -1 failed */
volatile int g_net_err = 0;
volatile u32 g_net_ip = 0;                  /* host order, valid when state == 2 */
int g_net_status_for_polcon = 0;
volatile u32 g_net_ready_word = 0xFFFFFFFF; volatile int g_net_ready_wait = 0;   /* NETDIAG: SQIOPMEM parameter 0 as last read, and quarter-seconds waited */
volatile int g_net_static = 0;               /* NETDIAG: 1 when the static fallback address is in use */            /* what sqPolconGetNetworkStatus reports */
volatile int g_net_early = 0;
extern volatile u32 g_sqd_calls;
extern volatile int g_dev_applied;
volatile int g_fio_gate = 0, g_fio_busy = 0, g_fio_held = 0;   /* PS2 fix: game file requests held while the network stack starts (host.c trap_c) */
volatile u32 g_net_t0 = 0, g_net_tup = 0;             /* PS2 fix: seconds since boot when bring-up started / finished */
volatile int g_bp_used_placeholder = 0;                /* PS2 fix: the boot-time address probe was answered before the network was up */

static int dev_parse_ip(const char *s, SqAddr *a)
{
    unsigned v = 0, o = 0; int n = 0;
    memset(a, 0, sizeof *a);
    for (;; s++) {
        if (*s >= '0' && *s <= '9') o = o * 10 + (*s - '0');
        else if (*s == '.' || !*s) { if (o > 255) return -1; v = (v << 8) | o; o = 0; n++; if (!*s) break; }
        else return -1;
    }
    if (n != 4) return -1;
    a->type = 1; a->addr = v;               /* the kernel byte-swaps +4 before it goes to the IOP: host order here */
    return 0;
}
/* file probe through the program's own slot table (938 sceOpen / 939 sceClose): works with the lifted Sony file service
   (SONY_IOP, where fileXio is not loaded) and with the fileXio-backed services of the plain build alike */
static int exists(const char *p)
{
    u32 *tab = (u32 *)SLOT_TABLE;
    int fd = ((int (*)(const char *, int, int))tab[938])(p, 1, 0);
    if (fd < 0) return 0;
    ((int (*)(int))tab[939])(fd);
    return 1;
}
char g_netlog[16][64]; volatile int g_netlog_n = 0;  /* NETDIAG: last bring-up steps, drawn on the sign-in page (devdlg.c sh_overlay) */
volatile u32 g_ticks = 0;                              /* host alarm ticks (host.c log_tick) - kernel alarms are unreliable on hardware, not used for time */
extern volatile u32 g_pf_vs;                          /* vertical blanks (perf.c INTC handler) - the one clock that is reliable on hardware */
unsigned net_secs(void) { return g_pf_vs / 60; }
void netlog(const char *m, u32 a, u32 b, u32 c)
{
    hlog(9, a, b, c, 0, 0, 0, m, 0, 0); hlog_kick();
    snprintf(g_netlog[g_netlog_n % 16], 64, "%4us %.36s %d %d", net_secs(), m, (int)a, (int)b); g_netlog_n++;
}
#define L netlog

/* PS2 fix: IOP free memory as a list of blocks (greedy: largest block, then the next largest ...), in KB */
volatile int g_iop_tot = -1, g_iop_big = -1, g_iop_at = 0;   /* the last measurement (KB) and when (s since boot) */
void iop_mem_map(const char *when)
{
#ifndef NETDIAG
    (void)when; return;
#endif
    extern void *SifAllocIopHeap(int size); extern int SifFreeIopHeap(void *addr);
    void *got[12]; int kb[12], n = 0, tot = 0;
    for (; n < 12; n++) {
        int lo = 0, hi = 2048;
        while (lo < hi) { int mid = (lo + hi + 1) / 2; void *p = SifAllocIopHeap(mid * 1024); if (p) { SifFreeIopHeap(p); lo = mid; } else hi = mid - 1; }
        if (lo < 1) break;
        got[n] = SifAllocIopHeap(lo * 1024); kb[n] = lo; tot += lo; if (!got[n]) break;
    }
    for (int i = 0; i < n; i++) if (got[i]) SifFreeIopHeap(got[i]);
    g_iop_tot = tot; g_iop_big = n > 0 ? kb[0] : 0; g_iop_at = (int)net_secs();
    char m[64]; snprintf(m, sizeof m, "IOP free %s: total KB / blocks", when);
    L(m, (u32)tot, (u32)n, 0);
    L("  IOP free blocks KB (largest 4)", (u32)(n > 0 ? kb[0] : 0), (u32)(n > 1 ? kb[1] : 0), 0);
    hlog(9, (u32)(n > 0 ? kb[0] : 0), (u32)(n > 1 ? kb[1] : 0), (u32)(n > 2 ? kb[2] : 0), (u32)(n > 3 ? kb[3] : 0), 0, 0, "  IOP free blocks KB 1-4:", 0, 0);
}
static int net_load_modules(void)
{
    const char *t, *n; int usepfs = 0;
    { extern volatile int g_net_early; L(g_net_early ? "net: bring-up started at pfs1 mount" : "net: bring-up thread started", 0, 0, 0); }
    if (!sq_ready) { L("net: SQIOPMEM not ready", 0, 0, 0); return -1; }
#ifdef NET_SELFTEST
    if (0)                                              /* no pfs1: mount in the stand-alone test: probing would block */
#elif !defined(NET_PROBE_MODULES)
    if (!NET_FORCE_DISC)                                /* PS2 fix: no probing - bring-up runs beside the game now, and the probe goes through the lifted
                                                           file layer whose lock spins on the alarm-based sqDelay when two threads meet; the install always has them */
#else
    if (!NET_FORCE_DISC && exists(NET_TCP_PFS) && exists(NET_NDI_PFS))
#endif
    { t = NET_TCP_PFS; n = NET_NDI_PFS; usepfs = 1; }
    else { t = NET_TCP_DISC; n = NET_NDI_DISC; }
    L(usepfs ? "net: using 2007 modules from pfs1" : "net: using 2003 modules from disc", 0, 0, 0);
    iop_mem_map("before net modules");
    int r1 = sqmem_load(t, "", 1, 0);                  /* avetcp first: ndglue/smap/sqiopint import it */
    L("net: tcp module loaded rc", (u32)r1, 0, 0);
    int r2 = sqmem_load(n, "", 1, 0);
    L("net: module loads rc tcp/ndi:", (u32)r1, (u32)r2, 0);
    iop_mem_map("after net modules");
    return (r1 == 0 && r2 == 0) ? 0 : -2;               /* rc 0 only means the RPC was accepted, not that the module started */
}

static int net_configure(void)
{
    static SqAddr ip, mask, bc, gw, d1, d2; static char dom[256] __attribute__((aligned(16)));
    fn_v dhcp_init = E("sqDhcpInit"), dhcp_req = E("sqDhcpRequest");
    fn_chk dhcp_chk = E("sqDhcpRequestCheck");
    fn_cfg ifcfg = E("sqEthernetIfConfig"); fn_rt route = E("sqAddRoutingTable"); fn_dns dns = E("sqInitDnsResolver");
    memset(&gw, 0, sizeof gw); memset(&d1, 0, sizeof d1); memset(&d2, 0, sizeof d2); dom[0] = 0;
#ifndef NO_FILE_GATE
    DelayThread(2 * 1000 * 1000);                          /* + the 3 s already waited under the file gate: smap link negotiation takes ~3 s; ifconfig before that fails (-35) */
#else
    DelayThread(5 * 1000 * 1000);                          /* smap link negotiation takes ~3 s after the modules start; ifconfig before that fails (-35) */
#endif
#if NET_USE_DHCP
    int r = dhcp_init(); L("net: sqDhcpInit rc", (u32)r, 0, 0);
    if (r < 0) { r = -10; goto fallback; }
    for (int i = 0; i < 100; i++) {                     /* the adapter may still be negotiating its link right after the modules start */
        r = dhcp_req(); if (i < 3 || r >= 0) L("net: sqDhcpRequest rc", (u32)r, (u32)i, 0);
        if (r >= 0) break;
        DelayThread(200 * 1000);
    }
    if (r < 0) { r = -11; goto fallback; }
    int st = 0;
    for (int i = 0; i < 600 && !st; i++) {              /* 60 s */
        st = dhcp_chk(&ip, &mask, &bc, &gw, &d1, &d2, dom);   /* 0 pending, <0 failed, >0 bitmask of fields received */
        if (st < 0) { L("net: DHCP failed rc", (u32)st, 0, 0); r = -12; goto fallback; }
        if (!st) DelayThread(100 * 1000);
    }
    if (st <= 0) { L("net: DHCP timeout", 0, 0, 0); r = -13; goto fallback; }
    L("net: DHCP ok ip/gw/dns1:", ip.addr, gw.addr, d1.addr);
    L("net: DHCP bitmask", (u32)st, 0, 0);
    if (0) {
fallback:                                               /* NETDIAG: DHCP did not work - use the fixed LAN address instead */
        L("net: DHCP gave up, static fallback", (u32)r, 0, 0);
        g_net_static = 1;
        memset(&gw, 0, sizeof gw); memset(&d1, 0, sizeof d1); memset(&d2, 0, sizeof d2); dom[0] = 0;
        if (dev_parse_ip(NET_IP, &ip) || dev_parse_ip(NET_MASK, &mask) || dev_parse_ip(NET_GW, &gw) || dev_parse_ip(NET_DNS1, &d1)) return -14;
        bc = ip; bc.addr = (ip.addr & mask.addr) | ~mask.addr;
        d2 = d1;
    }
#else
    if (dev_parse_ip(NET_IP, &ip) || dev_parse_ip(NET_MASK, &mask) || dev_parse_ip(NET_GW, &gw) || dev_parse_ip(NET_DNS1, &d1)) return -14;
    bc = ip; bc.addr = (ip.addr & mask.addr) | ~mask.addr;
    d2 = d1;
#endif
    int r2 = ifcfg(&ip, &mask, &bc); L("net: sqEthernetIfConfig rc", (u32)r2, 0, 0);
    if (r2 < 0) return -15;
    if (gw.addr) { r2 = route(0, &gw); L("net: sqAddRoutingTable(default) rc", (u32)r2, 0, 0); }
    if (d1.addr) { r2 = dns(dom, &d1, d2.addr ? &d2 : 0); L("net: sqInitDnsResolver rc", (u32)r2, 0, 0); }
    g_net_ip = ip.addr;
    return 0;
}

/* NETDIAG builds only: the developer PC running the server proxy, which logs the probe and the reports below. */
#ifndef NETDIAG_PC_IP
#define NETDIAG_PC_IP "192.168.1.5"
#endif
#ifndef NETDIAG_PC_PORT
#define NETDIAG_PC_PORT 54001
#endif
static u32 g_orig[1537];
/* PS2 fix: can the PS2 open a TCP connection to the PC (proxy, lobby port)?  The proxy log shows it as a lobby connection that closes at once. */
static void net_probe(void)
{
    typedef int (*f2)(u32, void *); typedef int (*f1)(int);
    static SqAddr a;
    if (dev_parse_ip(NETDIAG_PC_IP, &a) || !g_orig[231] || !g_orig[232] || !g_orig[236]) { L("probe: not possible", 0, 0, 0); return; }
    a.port = NETDIAG_PC_PORT;
    int h = ((f2)g_orig[231])(0, &a);
    L("probe: TCP to the developer PC, handle", (u32)h, 0, 0);
    if (h < 0) return;
    int r = 0, i;
    for (i = 0; i < 100 && r == 0; i++) { r = ((f1)g_orig[232])(h); if (!r) DelayThread(100 * 1000); }
    L("probe: connect (1 = OK) / polls x0.1s", (u32)r, (u32)i, 0);
    int c = ((f1)g_orig[236])(h);
    L("probe: closed rc", (u32)c, 0, 0);
}
/* PS2 fix: hang report.  Once the network is up the game should reach the sign-in page within seconds (PCSX2: 1 s).
   30 s after bring-up: if the sign-in page is not up, this thread takes over the screen with what the game was doing (where the CPU
   was at the last 128 vblanks, the last service calls, every thread's state and the return addresses on its stack) and also sends
   the same report to the PC as small lobby packets (the server proxy logs each one as  charid=<line*256+part> name="<15 chars>").
   If the sign-in page did come up, a short report is still sent once (checks the sending path). */
#ifndef BUILD_TAG
#define BUILD_TAG "NETDIAG"
#endif
#ifndef STATS_AFTER_S
#define STATS_AFTER_S 600
#endif
typedef struct { u32 cyc; u16 idx, pad; u32 ra, a0; } NdCr;
static u8 hm_stack[8192] __attribute__((aligned(16)));
#define HM_MAX 72
static char hm_rep[HM_MAX][72]; static u8 hm_scr[HM_MAX]; static int hm_n;
volatile int g_hm_sent = 0, g_hm_rc = 0; static int g_hm_force = 0;
static int hm_important = 0;                           /* NETDIAG41: EXC and hang reports also go the slow proxy way when the debug link is up */
static void hm_line(int scr, const char *fmt, ...)
{
    va_list ap; if (hm_n >= HM_MAX) return;
    va_start(ap, fmt); vsnprintf(hm_rep[hm_n], 72, fmt, ap); va_end(ap); hm_scr[hm_n++] = (u8)scr;
}
static u8 g_fps[128]; static volatile u32 g_fps_n = 0;  /* frames drawn in each of the last 128 seconds (world_watch) */
static void hm_fps(void)                               /* frames per second, the last 30 s (newest last) */
{
    char b[72]; int bl = 0; u32 n = g_fps_n, f = n > 30 ? n - 30 : 0, i = f;
    for (int line = 0; line < 2 && i < n; line++) {
        bl = snprintf(b, sizeof b, "fps%s", line ? "+" : "");
        for (int j = 0; j < 15 && i < n; j++, i++) bl += snprintf(b + bl, sizeof b - bl, " %u", (unsigned)g_fps[i & 127]);
        hm_line(1, "%s", b);
    }
}
static void hm_fails(int k)                            /* failed file opens / stats: totals, then the last k distinct paths */
{
    extern volatile u32 g_failtot, g_failn, g_failr[120]; extern volatile char g_failp[120][48]; extern volatile u32 g_resmiss;
    hm_line(1, "failed opens %u (distinct %u)  resources missing %u", (unsigned)g_failtot, (unsigned)g_failn, (unsigned)g_resmiss);
    u32 n = g_failn;
    for (u32 j = n > (u32)k ? n - k : 0; j < n; j++) { const char *pp = (const char *)g_failp[j]; int l = (int)strlen(pp); hm_line(1, "fail %d %s", (int)g_failr[j], l > 40 ? pp + l - 40 : pp); }
}
typedef struct { volatile u32 idx, ra, a0, sp, cyc; } IfEnt;
static int hm_tid_of_sp(u32 sp)                         /* which thread's stack holds this stack pointer (-1: none, e.g. an interrupt) */
{
    for (int t = 1; t < 64; t++) {
        ee_thread_status_t st;
        if (ReferThreadStatus(t, &st) < 0 || st.status == 16) continue;
        u32 b = (u32)st.stack; if (sp >= b && sp < b + (u32)st.stack_size) return t;
    }
    return -1;
}
static void hm_inflight(void)                          /* NETDIAG33: every service call still in progress, and the thread inside it */
{
    extern volatile IfEnt g_if[32];
    u32 now; __asm__ volatile("mfc0 %0, $9" : "=r"(now));
    int m = 0;
    for (int k = 0; k < 32 && m < 12; k++) {
        u32 id = g_if[k].idx; if (!id) continue;
        const char *nm = slot_name(id & 0xffff); m++;
        hm_line(1, "in t%d c%u %-14.14s ra %08x a0 %08x %ums", hm_tid_of_sp(g_if[k].sp), (unsigned)(id & 0xffff), nm ? nm : "?",
                (unsigned)g_if[k].ra, (unsigned)g_if[k].a0, (unsigned)((now - g_if[k].cyc) / 294912u));
    }
    if (!m) hm_line(1, "in: no call in progress");
}
static void hm_hw(void)                                /* NETDIAG33: interrupt, DMA and GS state */
{
#define HW(a) (*(volatile u32 *)(a))
    hm_line(1, "intc %04x/%04x dstat %08x dctrl %08x", (unsigned)(HW(0x1000F000) & 0xffff), (unsigned)(HW(0x1000F010) & 0xffff), (unsigned)HW(0x1000E010), (unsigned)HW(0x1000E000));
    hm_line(1, "chcr v0 %x v1 %x gif %x s0 %x s1 %x s2 %x", (unsigned)(HW(0x10008000) & 0xffff), (unsigned)(HW(0x10009000) & 0xffff), (unsigned)(HW(0x1000A000) & 0xffff),
            (unsigned)(HW(0x1000C000) & 0xffff), (unsigned)(HW(0x1000C400) & 0xffff), (unsigned)(HW(0x1000C800) & 0xffff));
    hm_line(1, "gs csr %08x gif %08x vif1 %08x", (unsigned)HW(0x12001000), (unsigned)HW(0x10003020), (unsigned)HW(0x10003C00));
    { extern volatile u32 g_syncpath_timeouts, g_syncpath_maxspin, g_syncpath_calls, g_syncpath_busy, g_syncpath_busybits, g_dma_timeouts;
      hm_line(1, "gssync %u timeouts %u max %u busy %u/%x dmato %u", (unsigned)g_syncpath_calls, (unsigned)g_syncpath_timeouts, (unsigned)g_syncpath_maxspin,
              (unsigned)g_syncpath_busy, (unsigned)g_syncpath_busybits, (unsigned)g_dma_timeouts); }
#undef HW
}
static void hm_threads_ready(char *b, int n)           /* READY threads as "tid:prio" */
{
    int bl = 0; b[0] = 0;
    for (int t = 1; t < 64; t++) { ee_thread_status_t st; if (ReferThreadStatus(t, &st) < 0 || st.status != 2) continue; bl += snprintf(b + bl, n - bl, " %d:%d", t, st.current_priority); if (bl > n - 8) break; }
}
#ifdef NETDIAG_RECOVER   /* NETDIAG37: off (none of the recovery steps ever unfroze the console) */
static int hm_recover(void)                            /* NETDIAG33: try to get a frozen game going again; returns the step that worked (0 = none) */
{
    extern int sh_frame_now(void);
    int me = GetThreadId(), f0;
    for (int step = 1; step <= 4; step++) {
        f0 = sh_frame_now();
        for (int t = 1; t < 64; t++) {
            ee_thread_status_t st;
            if (t == me || ReferThreadStatus(t, &st) < 0 || st.status != 2) continue;
            if (step == 1) RotateThreadReadyQueue(st.current_priority);          /* 1: the ready queue of each waiting priority */
            else if (step == 2) ChangeThreadPriority(t, st.current_priority);    /* 2: put each READY thread back in its queue */
            else if (step == 3) { SuspendThread(t); ResumeThread(t); }          /* 3: suspend + resume each READY thread */
            else if (st.current_priority > 1) ChangeThreadPriority(t, 1);         /* 4: move each READY thread to priority 1 (the level that still runs) */
        }
        DelayThread(2 * 1000 * 1000);
        int d = sh_frame_now() - f0;
        L("recover: step / frames after it", (u32)step, (u32)d, 0);
        if (d > 10) return step;
    }
    return 0;
}
#endif
static void hm_build(int hang, u32 fr_up, u32 vs_up)
{
    extern int sh_frame_now(void), sh_state_now(void); extern volatile u32 g_calls, g_crn; extern volatile NdCr g_cr[1024];
    extern volatile u32 g_pf_vs;
    extern volatile u32 g_opn, g_opr[40]; extern volatile char g_opp[40][48];
    u32 now; __asm__ volatile("mfc0 %0, $9" : "=r"(now));
    hm_n = 0; hm_important = hang;
    /* NETDIAG32: the most useful lines first (the NETDIAG29-31 reports filled up with thread stacks before the file lines were reached) */
    hm_line(1, "%s %s %us since boot, calls %u, page %d, sent %d/%d", BUILD_TAG, hang ? "HANG REPORT" : "OK", net_secs(), (unsigned)g_calls, sh_state_now(), g_hm_sent, g_hm_rc);
    hm_line(1, "since network up: frames %u vblanks %u   IP %u.%u.%u.%u", (unsigned)(sh_frame_now() - fr_up), (unsigned)(g_pf_vs - vs_up),
            (unsigned)(g_net_ip >> 24), (unsigned)(g_net_ip >> 16 & 255), (unsigned)(g_net_ip >> 8 & 255), (unsigned)(g_net_ip & 255));
    { int k = g_netlog_n, f = k > 6 ? k - 6 : 0; for (int i = f; i < k; i++) hm_line(1, "log%s", g_netlog[i % 16]); }   /* the host's own log: hang, missing resources */
    hm_line(1, "IOP free %d KB, largest block %d KB (at %ds)", g_iop_tot, g_iop_big, g_iop_at);
    hm_inflight();
    { char rb[64]; hm_threads_ready(rb, sizeof rb); hm_line(1, "ready%s", rb); }
    hm_hw();
    { extern volatile u32 g_alvbl_fired, g_alwd_fired; hm_line(1, "alarms rescued vblank %u watchdog %u", (unsigned)g_alvbl_fired, (unsigned)g_alwd_fired); }
    { u32 n = g_opn; for (u32 k = n > 8 ? n - 8 : 0; k < n; k++) { const char *pp = (const char *)g_opp[k % 40]; int l = (int)strlen(pp); hm_line(1, "open %d %s", (int)g_opr[k % 40], l > 40 ? pp + l - 40 : pp); } }
    hm_fails(3);
    hm_fps();
    u32 n = g_crn;
    for (int i = 0; i < 4 && (u32)i < n; i++) {
        volatile NdCr *c = &g_cr[(n - 1 - i) & 1023];
        const char *nm = slot_name(c->idx);
        hm_line(1, "c%4u %-18.18s ra %08x a0 %08x %ums", c->idx, nm ? nm : "?", (unsigned)c->ra, (unsigned)c->a0, (unsigned)((now - c->cyc) / 294912u));
    }
    for (int t = 1; t < 64; t++) {                      /* threads: one line each (status, wait, priority, entry, outermost callers); idle ones left out */
        ee_thread_status_t st;
        if (ReferThreadStatus(t, &st) < 0 || st.status == 16) continue;
        static u32 r[32]; int nr = 0;
        u32 base = (u32)st.stack, sz = (u32)st.stack_size;
        if (base >= 0x100000 && base + sz <= 0x2000000 && sz < 0x200000)
            for (u32 o = sz & ~3u; o >= 4 && nr < 32; o -= 4) {
                u32 v = *(volatile u32 *)(base + o - 4);
                if (v >= 0x100008 && v < 0x5fc580 && !(v & 3)) { u32 w = *(volatile u32 *)(v - 8); if ((w >> 26) == 3 || ((w >> 26) == 0 && (w & 0x3f) == 9)) r[nr++] = v; }
            }
        if (!nr) continue;
        hm_line(1, "t%-2d s%-2d w%-5x p%-3d f%08x n%-2d %08x %08x %08x %08x", t, st.status, st.waitType | (st.waitId << 8), st.current_priority, (unsigned)st.func, nr,
                nr > 0 ? (unsigned)r[nr - 1] : 0, nr > 1 ? (unsigned)r[nr - 2] : 0, nr > 2 ? (unsigned)r[nr - 3] : 0, nr > 3 ? (unsigned)r[nr - 4] : 0);
    }
}
#ifndef BEAT_S
#define BEAT_S 45
#endif
/* NETDIAG36: a short report every BEAT_S seconds from sign-in on, whether or not frames stop.  NETDIAG30/34/35 (and two earlier runs) stopped
   right at the zone-in (2 zone frames each way, then nothing) without any hang report: the loading screen keeps counting frames, so the
   frame watchdog never fires.  These reports show what every thread is doing during the zone load. */
static void hm_beat(int nb)
{
    extern int sh_frame_now(void), sh_state_now(void); extern volatile u32 g_calls, g_opn, g_opr[40], g_pf_vs;
    extern volatile char g_opp[40][48]; extern volatile int g_in_world;
    extern volatile u32 g_syncpath_timeouts, g_syncpath_maxspin, g_syncpath_calls, g_alvbl_fired, g_alwd_fired;
    hm_n = 0;
    hm_line(1, "%s BEAT %d %us fr %d vbl %u world %d page %d calls %u opens %u", BUILD_TAG, nb, net_secs(), sh_frame_now(), (unsigned)g_pf_vs,
            g_in_world, sh_state_now(), (unsigned)g_calls, (unsigned)g_opn);
    { int k = g_netlog_n, f = k > 4 ? k - 4 : 0; for (int i = f; i < k; i++) hm_line(1, "log%s", g_netlog[i % 16]); }
    hm_inflight();
    { char rb[64]; hm_threads_ready(rb, sizeof rb); hm_line(1, "ready%s", rb); }
    hm_hw();
    hm_line(1, "alarms rescued vblank %u watchdog %u", (unsigned)g_alvbl_fired, (unsigned)g_alwd_fired);
    { u32 n = g_opn; for (u32 k = n > 5 ? n - 5 : 0; k < n; k++) { const char *pp = (const char *)g_opp[k % 40]; int l = (int)strlen(pp); hm_line(1, "open %d %s", (int)g_opr[k % 40], l > 40 ? pp + l - 40 : pp); } }
}
static void hm_stats(void)                             /* NETDIAG32: a short summary 10 minutes into the world, sent even when nothing went wrong */
{
    extern volatile u32 g_calls;
    hm_n = 0;
    hm_line(1, "%s STATS %us since boot, calls %u", BUILD_TAG, net_secs(), (unsigned)g_calls);
    { extern volatile u32 g_syncpath_timeouts, g_syncpath_maxspin, g_syncpath_calls, g_syncpath_busy, g_syncpath_busybits, g_dma_timeouts;
      hm_line(1, "gssync %u timeouts %u max %u busy %u/%x dmato %u", (unsigned)g_syncpath_calls, (unsigned)g_syncpath_timeouts, (unsigned)g_syncpath_maxspin,
              (unsigned)g_syncpath_busy, (unsigned)g_syncpath_busybits, (unsigned)g_dma_timeouts); }
    hm_line(1, "IOP free %d KB, largest block %d KB (at %ds)", g_iop_tot, g_iop_big, g_iop_at);
    hm_fails(4);
    unsigned mn = 999, sum = 0, n = 0; for (u32 i = g_fps_n > 120 ? g_fps_n - 120 : 0; i < g_fps_n; i++) { unsigned v = g_fps[i & 127]; sum += v; n++; if (v < mn) mn = v; }
    hm_line(1, "fps last %us: avg %u min %u", n, n ? sum / n : 0, n ? mn : 0);
    { extern volatile u32 g_alvbl_fired, g_alwd_fired; hm_line(1, "alarms rescued vblank %u watchdog %u", (unsigned)g_alvbl_fired, (unsigned)g_alwd_fired); }
    hm_fps();
}
static void hm_draw(void)
{
    scr_clear(); scr_setXY(0, 1);
    for (int i = 0; i < hm_n; i++) if (hm_scr[i]) scr_printf("%s\n", hm_rep[i]);
}
static int hm_send_raw(void);
static int hm_send(void)
{
    extern volatile u32 g_mon_insend; extern int dbg_mirror(char (*)[72], int);
    int imp = hm_important; hm_important = 0;
    if (dbg_mirror(hm_rep, hm_n) && !imp) return hm_n;   /* NETDIAG41: the debug link took it; the slow proxy path only for exceptions and hangs */
    g_mon_insend = 1; int r = hm_send_raw(); g_mon_insend = 0; return r;
}
#ifdef NETDIAG
/* NETDIAG41: debug link sockets (dbg.c): 0 open to the PC on port n, 1 connect check (>0 connected), 2 send, 3 recv, 4 close */
int nd_sock(int op, int h, void *p, int n)
{
    typedef int (*f2)(u32, void *); typedef int (*f1)(int); typedef int (*f3)(int, void *, int);
    static SqAddr a;
    if (!g_orig[231] || !g_orig[232] || !g_orig[236] || !g_orig[237] || !g_orig[238]) return -1;
    switch (op) {
    case 0: if (g_net_state != 2 || dev_parse_ip(NETDIAG_PC_IP, &a)) return -1; a.port = (u16)n; return ((f2)g_orig[231])(0, &a);
    case 1: return ((f1)g_orig[232])(h);
    case 2: return ((f3)g_orig[237])(h, p, n);
    case 3: return ((f3)g_orig[238])(h, p, n);
    case 4: return ((f1)g_orig[236])(h);
    }
    return -1;
}
#endif
static int hm_send_raw(void)
{
    typedef int (*f2)(u32, void *); typedef int (*f1)(int); typedef int (*f3)(int, void *, int);
    static SqAddr a; static u8 pk[64] __attribute__((aligned(64)));
    if (dev_parse_ip(NETDIAG_PC_IP, &a) || !g_orig[231] || !g_orig[232] || !g_orig[236] || !g_orig[237]) return -1;
    a.port = NETDIAG_PC_PORT;
    for (int l = 0; l < hm_n; l++) {
        if (g_dev_applied && !g_hm_force) return -400000 - l * 100;      /* never beside the real sign-in (the player pressed OK); PS2 fix: hang reports do go */
        int len = strlen(hm_rep[l]);
        for (int o = 0; o == 0 || o < len; o += 15) {
            memset(pk, 0, sizeof pk);
            *(u32 *)pk = 0x34; memcpy(pk + 4, "IXFF", 4); *(u32 *)(pk + 8) = 7; *(u32 *)(pk + 0x1C) = (u32)(l << 8 | o / 15);
            memcpy(pk + 0x24, hm_rep[l] + o, len - o < 15 ? len - o : 15);
            int h = ((f2)g_orig[231])(0, &a);
            if (h < 0) return -100000 - l * 100;
            int r = 0, i;
            for (i = 0; i < 30 && r == 0; i++) { r = ((f1)g_orig[232])(h); if (!r) DelayThread(100 * 1000); }
            if (r <= 0) { ((f1)g_orig[236])(h); return -200000 - l * 100; }
            int s = ((f3)g_orig[237])(h, pk, 0x34);
            { extern volatile u32 g_mon_tick; g_mon_tick++; }   /* NETDIAG37: a send that is moving counts as alive */
            DelayThread(200 * 1000);                     /* the proxy answers and closes first, so this side never sits in TIME_WAIT */
            ((f1)g_orig[236])(h);
            if (s < 0) return -300000 - l * 100;
            g_hm_sent++;
        }
    }
    return hm_n;
}
extern volatile int g_ei_fixed, g_prio_fixed;
static void hm_timeline(void)                           /* PS2 fix: how long the bring-up took on this console, step by step (the proxy log keeps it) */
{
    extern int sh_state_now(void);
    hm_n = 0;
    hm_line(1, "%s OK %us since boot, page %d, ei fix %d prio fix %d", BUILD_TAG, net_secs(), sh_state_now(), g_ei_fixed, g_prio_fixed);
    hm_line(1, "bring-up %us..%us took %us ph %d ip %u.%u.%u.%u", (unsigned)g_net_t0, (unsigned)g_net_tup, (unsigned)(g_net_tup - g_net_t0), g_bp_used_placeholder,
            (unsigned)(g_net_ip >> 24), (unsigned)(g_net_ip >> 16 & 255), (unsigned)(g_net_ip >> 8 & 255), (unsigned)(g_net_ip & 255));
    int k = g_netlog_n, f = k > 16 ? k - 16 : 0;
    for (int i = f; i < k; i++) hm_line(1, "%s", g_netlog[i % 16]);
}
/* NETDIAG40: CPU exceptions (bad address, bus error, break, trap ...). The stock kernel's handler for these just stops the EE with
   interrupts off: the picture freezes with no colour and nothing reaches the PC, which is what the NETDIAG39 zone-in freeze looked like.
   exc.S/exc_park (perf.c) now catch them, park the thread that faulted, flash the screen YELLOW, and this report goes to the PC. */
extern volatile u32 g_exc[20], g_exc_n;
static void hm_exc(void)
{
    extern int sh_frame_now(void); extern volatile u32 g_pf_vs;
    volatile u32 *e = g_exc;
    hm_n = 0; hm_important = 1;
    hm_line(1, "%s EXC %u code %u cause %08x epc %08x bad %08x thr %d", BUILD_TAG, (unsigned)g_exc_n, (unsigned)(e[0] >> 2 & 31), (unsigned)e[0], (unsigned)e[1], (unsigned)e[2], (int)e[19]);
    hm_line(1, "ra %08x sp %08x gp %08x at %08x sr %08x", (unsigned)e[4], (unsigned)e[5], (unsigned)e[6], (unsigned)e[7], (unsigned)e[3]);
    hm_line(1, "v0 %08x v1 %08x a0 %08x a1 %08x", (unsigned)e[8], (unsigned)e[9], (unsigned)e[10], (unsigned)e[11]);
    hm_line(1, "a2 %08x a3 %08x t9 %08x s0 %08x", (unsigned)e[12], (unsigned)e[13], (unsigned)e[14], (unsigned)e[15]);
    hm_line(1, "s1 %08x s2 %08x fr %d vbl %u", (unsigned)e[16], (unsigned)e[17], sh_frame_now(), (unsigned)g_pf_vs);
    {   /* the instructions at EPC (if it is a readable address) */
        u32 pc = e[1] & ~3u;
        if (pc >= 0x100000 && pc < 0x1FFFFF0) { volatile u32 *p = (volatile u32 *)pc; hm_line(1, "code %08x %08x %08x %08x", (unsigned)p[-1], (unsigned)p[0], (unsigned)p[1], (unsigned)p[2]); }
    }
    { int k = g_netlog_n, f = k > 3 ? k - 3 : 0; for (int i = f; i < k; i++) hm_line(1, "log%s", g_netlog[i % 16]); }
}
static u8 exct_stack[2048] __attribute__((section(".xcmem"), aligned(64)));   /* .xcmem: outside the full host area */
static void exc_test_thread(void *arg) { (void)arg; __asm__ volatile("lw $2, 1($0)" ::: "$2", "memory"); for (;;) SleepThread(); }   /* misaligned load = address error (code 4) on purpose; nothing is read or written */
static void exc_test(void)
{
    extern volatile int g_exc_testid;
    ee_thread_t t; memset(&t, 0, sizeof t);
    t.func = (void *)exc_test_thread; t.stack = exct_stack; t.stack_size = sizeof exct_stack; t.initial_priority = 1; t.gp_reg = &_gp;
    int id = CreateThread(&t); if (id >= 0) { g_exc_testid = id; StartThread(id, NULL); }
}
static void world_watch(void)                          /* PS2 fix: after sign-in, report to the PC if the game stops drawing frames (5 s) */
{
    extern int sh_frame_now(void); extern volatile u32 g_pf_vs; extern volatile int g_in_world;
    int last = sh_frame_now(), still = 0, sent = 0, prev = last, inw = 0, stats = 0;
    extern volatile u32 g_mon_tick; extern void exc_install(void);
    exc_install();                                     /* NETDIAG40: again here, in case anything replaced the handlers since start-up */
    for (;;) {
        DelayThread(1000 * 1000);
        g_mon_tick++;
        {   static u32 exc_seen = 0;
            if (g_exc_n != exc_seen) { exc_seen = g_exc_n; hm_exc(); g_hm_force = 1; g_hm_rc = hm_send(); g_hm_force = 0; }
        }
        {   /* NETDIAG41: a report asked for over the debug link */
            extern volatile int g_dbg_req; extern int dbg_mirror(char (*)[72], int);
            int q = g_dbg_req;
            if (q) { g_dbg_req = 0; if (q == 1) hm_build(0, 0, 0); else hm_beat(0); hm_important = 0; dbg_mirror(hm_rep, hm_n); }
        }
        int f = sh_frame_now();
        { int d = f - prev; g_fps[g_fps_n & 127] = (u8)(d < 0 ? 0 : d > 255 ? 255 : d); g_fps_n++; prev = f; }
        /* NETDIAG32: no IOP memory probe every 15 s any more - it holds all free IOP memory for a moment, and a file open or network
           buffer at that moment fails (suspected in the NETDIAG30/31 console freezes); measured only at a hang now */
        if (g_in_world && !stats && ++inw == STATS_AFTER_S) {   /* 10 minutes in the world: a short summary */
            stats = 1; hm_stats(); g_hm_force = 1; g_hm_rc = hm_send(); g_hm_force = 0;
            L("report: stats sent rc/packets", (u32)g_hm_rc, g_hm_sent, 0);
        }
        {   /* NETDIAG36: heartbeat reports from sign-in on (every BEAT_S s until 3 min in the world, then every 3 min) */
            static int bt = 0, nb = 0, wt = 0;
            if (g_in_world) wt++; else wt = 0;
            if (g_dev_applied && ++bt >= (wt > 180 ? 180 : BEAT_S)) {
                bt = 0; if (nb == 0) exc_test();   /* NETDIAG40: one deliberate exception in a throwaway thread: yellow flash + EXC report = the catcher works */
                hm_beat(++nb); g_hm_force = 1; g_hm_rc = hm_send(); g_hm_force = 0;
                prev = sh_frame_now();                 /* the send takes a while: don't count it as a slow second */
            }
        }
        if (f != last) { last = f; still = 0; continue; }
        if (++still == 5 && sent < 3) {
            sent++;
            L("hang: no frame for 5 s - report to PC", (u32)f, g_pf_vs, 0);
            if (sent == 1) iop_mem_map("at the hang");
            { extern volatile u32 g_opn, g_opr[40]; extern volatile char g_opp[40][48];
              u32 n = g_opn; for (u32 k = n > 12 ? n - 12 : 0; k < n; k++) hlog(2, k, g_opr[k % 40], 0, 0, 0, 0, (const char *)g_opp[k % 40], 0, 0); }
            hm_build(1, (u32)f, g_pf_vs);
            g_hm_force = 1; g_hm_rc = hm_send(); g_hm_force = 0;
            L("report: hang report sent rc/packets", (u32)g_hm_rc, g_hm_sent, 0);
            if (sent == 1) {                           /* NETDIAG33: then try to unfreeze it, and say which step worked */
                int st = 0, fr = sh_frame_now();   /* NETDIAG37: no recovery attempts (none ever worked) */
                hm_n = 0; hm_line(1, "%s RECOVER step %d (0 = none) frames now %d", BUILD_TAG, st, fr);
                { int k = g_netlog_n, f = k > 3 ? k - 3 : 0; for (int i = f; i < k; i++) hm_line(1, "log%s", g_netlog[i % 16]); }
                g_hm_force = 1; g_hm_rc = hm_send(); g_hm_force = 0;
                if (st) { last = sh_frame_now(); still = 0; sent = 0; continue; }   /* running again: watch for the next freeze */
            }
            still = -55;                               /* again after another minute if still stuck */
        }
    }
}
static void hang_monitor(void *arg)
{
    extern int sh_frame_now(void), sh_state_now(void); extern volatile u32 g_pf_vs;
    u32 fr_up = sh_frame_now(), vs_up = g_pf_vs;
    int hang = 1;
    for (int s = 0; s < 30; s++) { if (sh_state_now() != 0) { hang = 0; break; } DelayThread(1000 * 1000); }
    if (hang) L("hang: no sign-in page 30 s after network up", 0, 0, 0);
    DelayThread(2 * 1000 * 1000);
    if (g_dev_applied) L("report: skipped (sign-in already started)", 0, 0, 0);
    else {
        hm_timeline();                                 /* the bring-up timeline (no screen take-over: init_scr is never seen on the console) */
        g_hm_rc = hm_send(); L("report: sent to PC rc/packets", (u32)g_hm_rc, g_hm_sent, 0);
        if (hang) { hm_build(1, fr_up, vs_up); g_hm_rc = hm_send(); L("report: hang report sent rc", (u32)g_hm_rc, g_hm_sent, 0); }
    }
    world_watch();
}
static void hang_monitor_start(void)
{
    ee_thread_t t; memset(&t, 0, sizeof t);
    t.func = (void *)hang_monitor; t.stack = hm_stack; t.stack_size = sizeof hm_stack; t.initial_priority = 0;   /* NETDIAG37: 0, above every game thread */ t.gp_reg = &_gp;
    int id = CreateThread(&t); if (id >= 0) StartThread(id, NULL);
}
static void fio_gate_on(void)
{
    g_fio_gate = 1;
    int ms = 0; while (g_fio_busy > 0 && ms < 20000) { DelayThread(5000); ms += 5; }   /* let the requests already in flight finish */
    L("net: game file requests paused (in flight / waited ms)", (u32)g_fio_busy, (u32)ms, 0);
}
static void fio_gate_off(void) { g_fio_gate = 0; L("net: game file requests resumed (calls held)", (u32)g_fio_held, 0, 0); }
static void boot_ip_fixup(void);
static void net_thread(void *arg)
{
    g_net_t0 = net_secs();
#ifdef NET_SIM_DELAY_S
    L("net: PCSX2 test - simulated slow start, s", NET_SIM_DELAY_S, 0, 0);
    DelayThread(NET_SIM_DELAY_S * 1000 * 1000);
#endif
    { extern volatile int g_lkalarm_patched; extern volatile u32 g_sqd_calls; L("net: sqDelay fix (2 = on) / sleeps so far", (u32)g_lkalarm_patched, g_sqd_calls, 0); }
#ifndef NO_FILE_GATE
    fio_gate_on();
#endif
    int rc = net_load_modules();
    /* sqInitSocketAPI itself spins until the Sony modules set SQIOPMEM parameter 0 (forever if they did not start);
       net_ensure() therefore gives up waiting after NET_TIMEOUT_S and leaves this thread parked */
    if (rc == 0) {
        {   /* NET fix: wait for the IOP stack's "ready" flag (SQIOPMEM parameter 0) here, with DelayThread, so the kernel's sqmemReady loop
               finds it set on its first check and never uses its alarm-based sleep (kernel alarms barely fire on a real PS2 once the game runs) */
            extern int host_sqmem_query(int n); extern volatile u32 g_q_word;
            int waited = 0, lastv = -12345;
            for (;;) {
                int qr = host_sqmem_query(0); u32 v = g_q_word;
                g_net_ready_word = v; g_net_ready_wait = waited;
                if ((int)v != lastv) { L("net: IOP ready flag / query rc", v, (u32)qr, 0); lastv = (int)v; }
                if (qr >= 0 && (int)v > 0) break;
                if (waited >= 300) { L("net: IOP ready flag never set (s)", (u32)waited, 0, 0); break; }
                DelayThread(250 * 1000); waited++;           /* 4 checks per second */
            }
        }
        L("net: sqInitSocketAPI(3) waiting", 0, 0, 0);
        int r = ((fn_i1)E("sqInitSocketAPI"))(3);                /* 3 = built-in Ethernet (type 1 = USB adapter also waits for link) */
        { extern volatile u32 g_alvbl_fired, g_alwd_fired; extern volatile int g_lkalarm_patched;
          (void)g_lkalarm_patched; L("net: socket API rc / alarms rescued / sqDelays", (u32)r, g_alvbl_fired + g_alwd_fired, g_sqd_calls); }
        rc = r < 0 ? -4 : 0;
        iop_mem_map("after sqInitSocketAPI");
#ifndef NO_FILE_GATE
        if (rc == 0) DelayThread(3 * 1000 * 1000);          /* Ethernet link negotiation (~3 s after the modules start) also with the HDD quiet */
#endif
    }
#ifndef NO_FILE_GATE
    fio_gate_off();
#endif
    if (rc == 0) rc = net_configure();
#ifdef NETDIAG
    if (rc == 0) net_probe();                         /* diagnostic: TCP probe to the developer PC */
#endif
    g_net_err = rc;
    g_net_status_for_polcon = (rc == 0) && NET_POLCON_STATUS;
    if (rc == 0) boot_ip_fixup();
    iop_mem_map("after bring-up");
    g_net_tup = net_secs();
    g_net_state = rc == 0 ? 2 : -1;
    L("net: bring-up done, state/err/took s", (u32)g_net_state, (u32)rc, g_net_tup - g_net_t0);
#ifdef NETDIAG
    if (g_net_state == 2) { hang_monitor_start(); { extern void dbg_start(void); dbg_start(); } }   /* bring-up timeline + hang reports to the developer PC; NETDIAG41: + live debug link (dbg.c) */
#endif
    for (;;) SleepThread();     /* park instead of exiting (deleting the thread coincided with a kernel-table crash) */
}

static u8 net_stack[32768] __attribute__((aligned(16)));
void net_start_async(void)                              /* NETDIAG: start the bring-up without waiting for it (sign-in page) */
{
    if (g_net_state == 0) {
        g_net_state = 1;
        ee_thread_t t; t.func = (void *)net_thread; t.stack = net_stack; t.stack_size = sizeof net_stack; t.gp_reg = &_gp;
        t.initial_priority = 40; t.attr = 0; t.option = 0;
        int id = CreateThread(&t);
        if (id < 0 || StartThread(id, 0) < 0) { g_net_state = -1; g_net_err = -99; }
    }
}
int net_wait(unsigned max_ms)                          /* PS2 fix: wait for the bring-up at most max_ms; <0 = not up (yet).  A timeout is NOT remembered:
                                                           the next call waits again and succeeds once the bring-up has finished. */
{
#ifdef NET_DISABLED
    return -1;
#endif
    net_start_async();
    { static int who_set = 0; if (!who_set) { who_set = 1; L("net: first wait from caller ra", (u32)__builtin_return_address(0), 0, 0); } }
    for (unsigned ms = 0; g_net_state == 1 && ms < max_ms; ms += 5) DelayThread(5000);
    if (g_net_state != 2) { static int told = 0; if (told < 3) { told++; L("net: caller told: not up yet, state/err", (u32)g_net_state, (u32)g_net_err, 0); } }
    return g_net_state == 2 ? 0 : -1;
}
int net_ensure(void) { return net_wait(NET_TIMEOUT_S * 1000u); }   /* callable from any thread */

/* PS2 fix: the game's boot-time local-address probe (0x352660: open a datagram socket, ask its name, close it) runs ~7 s after boot and its
   answer is kept for the whole session: with no address the start-up (0x2cf270) finds no host-table entry, tears the network manager down and
   the lobby context is never created, so a later sign-in fails (FFXI-3101) without sending anything.  The three calls of that probe are routed
   here (call sites patched in net_install): they wait a few seconds for the real address and otherwise answer with a placeholder, which
   boot_ip_fixup() replaces once the network is up.  The game no longer needs the network to reach the sign-in page. */
#ifndef BOOT_PROBE_WAIT_S
#define BOOT_PROBE_WAIT_S 4
#endif
#ifndef BOOT_PLACEHOLDER_IP
#define BOOT_PLACEHOLDER_IP 0xA9FE0101u                 /* 169.254.1.1 (host order): only used until the real address is known */
#endif
#define BP_HANDLE 0x7ffe
static u32 bp_ip;
static u32 bp_open(u32 a0, u32 a1)
{
    (void)a0; (void)a1;
    if (g_net_state == 1) net_wait(BOOT_PROBE_WAIT_S * 1000u);   /* PS2 fix: never START the bring-up here (game still loading); it starts on the sign-in page */
    bp_ip = g_net_state == 2 ? g_net_ip : BOOT_PLACEHOLDER_IP;
    g_bp_used_placeholder = g_net_state != 2;
    L(g_bp_used_placeholder ? "boot probe: network not up, placeholder ip" : "boot probe: network up, ip", bp_ip, (u32)g_net_state, 0);
    return BP_HANDLE;
}
static u32 bp_getname(u32 h, u16 *out)
{
    if (h != BP_HANDLE || (u32)out < 0x100000 || (u32)out >= 0x2000000) return (u32)-1;
    out[0] = 1; out[1] = 0; *(u32 *)(out + 2) = bp_ip;      /* {type 1, port 0, address host order} at +0/+2/+4, as the library fills it */
    return 0;
}
static u32 bp_close(u32 h) { (void)h; return 0; }
static u32 bswap32(u32 v) { return (v >> 24) | ((v >> 8) & 0xff00) | ((v << 8) & 0xff0000) | (v << 24); }
static void bp_fix_word(volatile u32 *w, const char *what)
{
    if ((u32)w < 0x100000 || (u32)w >= 0x2000000) return;
    u32 p = BOOT_PLACEHOLDER_IP, v = *w;
    if (v == p) { *w = g_net_ip; L(what, v, g_net_ip, 0); }
    else if (v == bswap32(p)) { *w = bswap32(g_net_ip); L(what, v, bswap32(g_net_ip), 0); }
}
static void boot_ip_fixup(void)                         /* the network is up: put the real address where the placeholder went */
{
    if (!g_bp_used_placeholder || g_net_ip == BOOT_PLACEHOLDER_IP) return;
    u32 nm = *(volatile u32 *)0x6036b0, lc = *(volatile u32 *)0x624FE0;   /* network manager (local address at +20), lobby context (+0/+8) */
    if (nm) bp_fix_word((volatile u32 *)(nm + 20), "net: fixed local ip (manager) old/new");
    if (lc) { bp_fix_word((volatile u32 *)(lc + 0), "net: fixed ip (lobby+0) old/new"); bp_fix_word((volatile u32 *)(lc + 8), "net: fixed ip (lobby+8) old/new"); }
}
/* PS2 fix: PCSX2 (NETDIAG29G) crashed 1.5 s after the lobby's world list: 0x4ABDE0 loads a resource by name (0x449A10) and uses the
   result without a NULL check (TLB miss at 0x4ABDF8, then the EE kernel died).  Log every name that comes back empty. */
volatile u32 g_resmiss = 0;
static char g_resname[16][32]; static volatile u32 g_resn = 0;
static void res_copy(char *d, u32 name) { int i = 0; if (name >= 0x100000 && name < 0x2000000) for (; i < 31 && ((char *)name)[i] >= 0x20 && ((char *)name)[i] < 0x7f; i++) d[i] = ((char *)name)[i]; d[i] = 0; }
static u32 res_load_logged(u32 name, u32 flag)
{
    res_copy(g_resname[g_resn++ & 15], name);
    u32 r = ((u32 (*)(u32, u32))0x449A10)(name, flag);
    if (!r) {                                          /* PS2 fix: the game would crash on this NULL: report it and park this thread so the log gets out */
        g_resmiss++;
        for (u32 k = g_resn > 16 ? g_resn - 16 : 0; k < g_resn; k++) hlog(9, k, 0, 0, 0, 0, 0, "resource requested:", g_resname[k & 15], 0);
        hlog(9, name, flag, (u32)__builtin_return_address(0), g_resmiss, 0, 0, "RESOURCE MISSING name/flag/ra/n:", g_resname[(g_resn - 1) & 15], 0);
        { char m[40]; snprintf(m, sizeof m, "RES MISS %.27s", g_resname[(g_resn - 1) & 15]); L(m, name, flag, 0); }
        iop_mem_map("at the missing resource");
        { extern volatile u32 g_opn, g_opr[40]; extern volatile char g_opp[40][48];      /* the last file opens / stats (host.c ring) */
          u32 n = g_opn; for (u32 k = n > 12 ? n - 12 : 0; k < n; k++) hlog(2, k, g_opr[k % 40], 0, 0, 0, 0, (const char *)g_opp[k % 40], 0, 0); }   /* printed as open(path, n) -> rc */
        for (;;) { hlog_kick(); DelayThread(500 * 1000); }
    }
    return r;
}
/* PS2 fix: the disc's CD-only files.  The 2016 game keeps 70 small files (CDROM/0..2/*.DAT, file ids 1-85, listed in the disc's CDTABLE.DAT)
   on the DVD only; the HDD file table (VTABLE) does not list them.  Booted from the disc they come from cdrom0:; started from USB with no disc,
   the lobby's next screen asks for file id 23 (CDROM/0/23.DAT), gets nothing and crashes (NETDIAG17-19).  The game's id -> path lookup
   (0x441760, mode 1 = HDD) now answers the CD ids with "/CDROM/<id/30>/<id%30>.DAT" under the game folder (pfs1:/image/ffxi/CDROM/...);
   when that file is not on the HDD, the open falls back to the disc (trap_c, host.c). */
const u8 g_cd_ids[100] = { 0,1,1,1,1,1,1,1,1,0, 0,1,1,1,1,1,1,1,1,0, 0,1,1,1,1,1,1,1,0,0,
    1,1,1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,1,1, 1,1,1,1,1,1,1,1,1,1, 1,0,0,0,0,0,0,0,0,0, 1,1,1,1,1,1,0,0,0,0, 0,0,0,0,0,0,0,0,0,0 };
volatile u32 g_cdmap_n = 0, g_cdmap_last = 0;
static int fs_path_cd(u32 fs, int id, char *out)
{
    int r = ((int (*)(u32, int, char *))0x441760)(fs, id, out);
    { static int nl = 0; if ((r < 0 || id == 23) && nl < 20) { nl++; hlog(9, (u32)id, *(volatile u32 *)(fs + 16), *(volatile u32 *)(fs + 20), (u32)r, 0, 0, "file id not in the HDD tables: id/mode/dev/rc", 0, 0); } }
    if (r < 0 && out && id > 0 && id < 100 && g_cd_ids[id]) {             /* PS2 fix: any table mode (PS2 fix: the lobby's fs is not mode 1) */
        const char *pre = "/CDROM/"; int n = 0, d = id / 30, f = id % 30;
        while (*pre) out[n++] = *pre++;
        out[n++] = (char)('0' + d); out[n++] = '/';
        if (f >= 10) out[n++] = (char)('0' + f / 10);
        out[n++] = (char)('0' + f % 10);
        out[n++] = '.'; out[n++] = 'D'; out[n++] = 'A'; out[n++] = 'T'; out[n] = 0;
        g_cdmap_n++; g_cdmap_last = (u32)id;
        return 1;
    }
    return r;
}
static void cd_install(void)
{
    static const u32 at[8] = { 0x43d948, 0x43daf4, 0x43dda8, 0x43e694, 0x43f738, 0x43f858, 0x43f94c, 0x43fe3c };
    int n = 0;
    for (int i = 0; i < 8; i++) { u32 *w = (u32 *)at[i]; if (*w == 0x0C1105D8) { *w = 0x0C000000 | (((u32)fs_path_cd >> 2) & 0x3FFFFFF); n++; } }
    FlushCache(0); FlushCache(2);
    printf("[host] CD-only files: %d of 8 file-id lookups routed to the host\n", n);
}
/* PS2 fix: the steps of the game's resource loader 0x449A10 (size 0x445E70, alloc 0x282170, read 0x445C70, parse 0x2DABD0), logged for file id 23 */
typedef u32 (*f8)(u32, u32, u32, u32, u32, u32, u32, u32);
static volatile u32 rl_id = 0;
#define RLW(name, addr, what) static u32 name(u32 a0, u32 a1, u32 a2, u32 a3, u32 t0, u32 t1, u32 t2, u32 t3) \
    { u32 r = ((f8)(addr))(a0, a1, a2, a3, t0, t1, t2, t3); if (rl_id == 23) hlog(9, a0, a1, a2, r, 0, 0, what, 0, 0); return r; }
static u32 rl_size(u32 a0, u32 a1, u32 a2, u32 a3, u32 t0, u32 t1, u32 t2, u32 t3)
{ rl_id = a1; u32 r = ((f8)0x445E70)(a0, a1, a2, a3, t0, t1, t2, t3); if (a1 == 23) hlog(9, a0, a1, 0, r, 0, 0, "loader id 23: size  fs/id/-/rc", 0, 0); return r; }
RLW(rl_alloc, 0x282170, "loader id 23: alloc size/-/-/ptr")
RLW(rl_read,  0x445C70, "loader id 23: read  fs/id/buf/rc")
RLW(rl_parse, 0x2DABD0, "loader id 23: parse buf/id/flag/obj")
static void rl_install(void)
{
    static const struct { u32 at, orig; void *fn; } c[] = { { 0x449A44, 0x0C11179C, rl_size }, { 0x449A5C, 0x0C0A085C, rl_alloc }, { 0x449A7C, 0x0C11171C, rl_read }, { 0x449AA4, 0x0C0B6AF4, rl_parse } };
    for (unsigned i = 0; i < 4; i++) { u32 *w = (u32 *)c[i].at; if (*w == c[i].orig) *w = 0x0C000000 | (((u32)c[i].fn >> 2) & 0x3FFFFFF); }
}
static void bp_install(void)
{
#ifdef NETDIAG
    { u32 *w = (u32 *)0x4ABDF0; if (*w == 0x0C112684) *w = 0x0C000000 | (((u32)res_load_logged >> 2) & 0x3FFFFFF); else printf("[host] res logger: unexpected word %08x\n", *w); }
#endif
    static const struct { u32 at, orig; void *fn; } c[] = {
        { 0x3526b8, 0x0c15bfea, bp_open },               /* jal stub 240 sqCreateDatagramSocket */
        { 0x3526cc, 0x0c15bfd2, bp_getname },            /* jal stub 225 sqGetSockName */
        { 0x3526f4, 0x0c15bff0, bp_close },              /* jal stub 243 sqCloseDatagramSocket */
    };
    int n = 0;
    for (unsigned i = 0; i < 3; i++) { u32 *w = (u32 *)c[i].at; if (*w == c[i].orig) { *w = 0x0C000000 | (((u32)c[i].fn >> 2) & 0x3FFFFFF); n++; } }
    FlushCache(0); FlushCache(2);
    printf("[host] boot address probe: %d of 3 call sites routed to the host\n", n);
}

/* ---- slot wrappers: first use of the network triggers the bring-up, then forward to the lifted kernel function ---- */
static u32 g_orig[1537];
#define WRAP(name, slot) \
    static u32 name(u32 a0, u32 a1, u32 a2, u32 a3, u32 t0, u32 t1, u32 t2, u32 t3) \
    { if (net_ensure() < 0) return (u32)-1; return ((u32 (*)(u32, u32, u32, u32, u32, u32, u32, u32))g_orig[slot])(a0, a1, a2, a3, t0, t1, t2, t3); }
WRAP(w_safeport, 1080)      /* sqInetGetSafeUdpPort(0): first call of the UDP setup */
WRAP(w_gethost, 221)        /* sqGetHostByName */
extern volatile int g_dev_hold;                         /* 1 while the developer screen is up: the lobby connection is not started yet */
extern char g_dev_ip[32], g_dev_port[8];
static u32 g_cs_args[8], g_cs_sa[4]; static int g_cs_def = 0;
volatile int g_dev_applied = 0;                         /* the developer page has set a server: the first (lobby) connection goes there */
static int g_cs_patched = 0;
static u32 hold_ip_u32(const char *p) { u32 v = 0, a = 0; for (;; p++) { if (*p >= '0' && *p <= '9') a = a * 10 + (*p - '0'); else { v = (v << 8) | (a & 255); a = 0; if (!*p) break; } } return v; }
static u32 w_csock(u32 a0, u32 a1, u32 a2, u32 a3, u32 t0, u32 t1, u32 t2, u32 t3)
{
    if (net_ensure() < 0) return (u32)-1;
    if (a1 >= 0x100000 && a1 < 0x1fff000) hlog(9, a0, *(u32 *)a1, *(u32 *)(a1 + 4), *(u32 *)(a1 + 8), 0, 0, "sqCreateSocket a0 / sockaddr words:", 0, 0);
    if (a1 >= 0x100000 && a1 < 0x1fff000) L("game: socket ip / port", *(u32 *)(a1 + 4), *(u32 *)a1 >> 16, 0);
    if (g_dev_applied && !g_cs_patched && a1 >= 0x100000 && a1 < 0x1fff000) {       /* lobby socket: use the typed address and port */
        u32 *sa = (u32 *)a1; sa[1] = hold_ip_u32(g_dev_ip); sa[0] = (sa[0] & 0xffff) | ((u32)atoi(g_dev_port) << 16); g_cs_patched = 1;      /* sockaddr: word0 = port<<16 | type, word1 = ip */
        hlog(9, sa[0], sa[1], 0, 0, 0, 0, "lobby socket redirected (port word / ip):", 0, 0);
    }
#ifdef DEV_HOLD
    if (g_dev_hold && !g_cs_def && a1 >= 0x100000 && a1 < 0x1fff000) {      /* first (lobby) connection: wait for the developer screen */
        g_cs_args[0] = a0; g_cs_args[1] = a1; g_cs_args[2] = a2; g_cs_args[3] = a3; g_cs_args[4] = t0; g_cs_args[5] = t1; g_cs_args[6] = t2; g_cs_args[7] = t3;
        for (int i = 0; i < 4; i++) g_cs_sa[i] = ((u32 *)a1)[i];
        g_cs_def = 1; return a0;
    }
#endif
    return ((u32 (*)(u32, u32, u32, u32, u32, u32, u32, u32))g_orig[231])(a0, a1, a2, a3, t0, t1, t2, t3);
}

/* UDP call tracer: first few calls of each datagram slot (args and result) */
#define UDPLOG(name, slot) \
    static u32 name(u32 a0, u32 a1, u32 a2, u32 a3, u32 t0, u32 t1, u32 t2, u32 t3) \
    { static int n = 0; if (slot == 240 && net_ensure() < 0) return (u32)-1; if (slot == 240 && n < 2) L("game: UDP slot 240 call a0", a0, 0, 0); u32 r = ((u32 (*)(u32, u32, u32, u32, u32, u32, u32, u32))g_orig[slot])(a0, a1, a2, a3, t0, t1, t2, t3); \
      if (n < 5) { n++; hlog(9, a0, a1, a2, a3, r, 0, "UDP slot " #slot " a0..a3/ret:", 0, 0); if (n < 3) L("game: UDP slot " #slot " a0/ret", a0, r, 0); } return r; }
UDPLOG(u240, 240) UDPLOG(u244, 244) UDPLOG(u245, 245) UDPLOG(u246, 246) UDPLOG(u247, 247) UDPLOG(u252, 252) UDPLOG(u253, 253) UDPLOG(u241, 241) UDPLOG(u242, 242) UDPLOG(u243, 243) UDPLOG(u248, 248) UDPLOG(u249, 249) UDPLOG(u250, 250) UDPLOG(u251, 251) UDPLOG(u225, 225)
#define NETLOG(name, slot) \
    static u32 name(u32 a0, u32 a1, u32 a2, u32 a3, u32 t0, u32 t1, u32 t2, u32 t3) \
    { static int n = 0; static u32 last = 0x12345; u32 r = ((u32 (*)(u32, u32, u32, u32, u32, u32, u32, u32))g_orig[slot])(a0, a1, a2, a3, t0, t1, t2, t3); \
      if (n < 30 && r != last) { n++; last = r; hlog(9, a0, a1, a2, r, 0, 0, "NET slot " #slot " a0/a1/a2/ret:", 0, 0); } return r; }
NETLOG(n236, 236) NETLOG(n238, 238)
/* 237 sqSocketSend(h, buf, len): log the first sends (lobby login packet layout) */
static u32 w_send(u32 a0, u32 a1, u32 a2, u32 a3, u32 t0, u32 t1, u32 t2, u32 t3)
{
    static int n = 0;
    if (n < 3 && a1 >= 0x100000 && a1 < 0x1fff000 && a2 >= 0x2c) { n++; u32 *w = (u32 *)a1; hlog(9, a2, w[0], w[1], w[2], w[7], w[8], "SEND len/w0/w1/w2/w7(0x1c)/w8:", 0, 0); hlog(9, w[9], w[10], w[11], w[29], w[30], w[31], "SEND w9..w11 w29..w31:", 0, 0); }
    return ((u32 (*)(u32, u32, u32, u32, u32, u32, u32, u32))g_orig[237])(a0, a1, a2, a3, t0, t1, t2, t3);
}
/* 232 sqCreateSocketCheck: log every change of its answer (0 pending, >0 connected, <0 error) */
static u32 w_cchk(u32 a0, u32 a1, u32 a2, u32 a3, u32 t0, u32 t1, u32 t2, u32 t3)
{
    static int last = 0x7fff0000, n = 0;
#ifdef DEV_HOLD
    if (g_cs_def == 1) {
        if (g_dev_hold) return 0;                                           /* still waiting for the developer screen: "connecting" */
        g_cs_sa[1] = hold_ip_u32(g_dev_ip); g_cs_sa[0] = (g_cs_sa[0] & 0xffff) | ((u32)atoi(g_dev_port) << 16);   /* the address / port typed there */
        g_cs_def = 2;
        ((u32 (*)(u32, u32, u32, u32, u32, u32, u32, u32))g_orig[231])(g_cs_args[0], (u32)g_cs_sa, g_cs_args[2], g_cs_args[3], g_cs_args[4], g_cs_args[5], g_cs_args[6], g_cs_args[7]);
    }
#endif
    u32 r = ((u32 (*)(u32, u32, u32, u32, u32, u32, u32, u32))g_orig[232])(a0, a1, a2, a3, t0, t1, t2, t3);
    n++;
    if ((int)r != last) { last = (int)r; hlog(9, a0, r, n, 0, 0, 0, "sqCreateSocketCheck h/ret/pollcount:", 0, 0); L("game: connect state / polls", r, (u32)n, 0); }
    return r;
}

/* ---- POLCON: the 2016 program asks POL (not present) a few things; answers equal the 2007 kernel's own with POLCON down,
   except the network status, which reports whether our bring-up succeeded ---- */
static u32 svc_polcon_check_msg(void)  { return 1; }    /* 818 sqPolconCheckMessageService: kernel returns 1 when POLCON is not initialised; game accepts 0 or 1 */
static u32 svc_polcon_msg_stat(void)   { return 1; }    /* 836 sqPolconGetMessageServiceStat: same (1 when uninitialised) */
static u32 svc_polcon_net_status(void) { return (u32)g_net_status_for_polcon; }   /* 838 sqPolconGetNetworkStatus: game stores -1 (error flag) when 0 */
/* PlayOnline background operations: there is no PlayOnline, so every asynchronous "Check" / "AllStoreComRepeatEnd" answers "finished" (>0) */
static u32 svc_pol_done(void) { return 1; }
/* 1003 sqPlayOnlineGetPolproRandomValue(out16): the 16-byte per-session secret PlayOnline hands to the lobby login; the program copies it into the
   lobby context's password buffer (0x55DB80) and hashes it with the lobby key.  The LAN proxy checks MD5(password zero-padded to 16 || key), so
   the host returns the -pass value from the active command line, zero padded (what the 2012 build's makeMD5len(..., 16) patch did). */
static u32 svc_polpro_random(u8 *out)
{
    if (!out) return 0;
    const char *cl = (const char *)0x7BE260; const char *p = 0;
    for (int i = 0; i < 190 && cl[i]; i++) if (cl[i] == '-' && cl[i + 1] == 'p' && cl[i + 2] == 'a' && cl[i + 3] == 's' && cl[i + 4] == 's' && cl[i + 5] == ' ') { p = cl + i + 6; break; }
    for (int i = 0; i < 16; i++) out[i] = 0;
    if (p) for (int i = 0; i < 15 && p[i] && p[i] != ' '; i++) out[i] = (u8)p[i];
    return 1;
}
/* 177 sqPlayOnlineGetCharacterInfo(idx, out): PlayOnline's own list of the account's characters.  The game picks the one it is about to enter by
   comparing {content id, a 32-bit key built from the entry's fields} against this list (0x375AD0) and shows POL-0001 when nothing matches.  Our
   list is the lobby's character table the game already holds (ctx = *0x624FE0, 140-byte entries at ctx+0x13824): entry i answers index i. */
static int svc_pol_charinfo(int idx, u8 *out)
{
    u32 ctx = *(volatile u32 *)0x624FE0;
    if (!out || !ctx || idx < 0 || idx >= 16) return -1;
    const u8 *e = (const u8 *)(ctx + 0x13824 + (u32)idx * 140);
    u32 id = *(const u32 *)e; if (!id) return -1;
    u32 a2 = *(const u16 *)(e + 4) | ((u32)e[0xB] << 16), a1 = *(const u16 *)(e + 6);
    for (int i = 0; i < 0x20; i++) out[i] = 0;
    out[0] = 1; *(u16 *)(out + 2) = 1; out[0x11] = 0x80; out[0x12] = 1;   /* out[0x11] bit7: the character is cleared to enter the world (0x373234 waits for it, then times out as FFXI-3113); out[0x12]&0x3f: world id passed on to slot 195 */
    *(u32 *)(out + 4) = (a2 & 0xff0000) << 8 | (a1 & 0xffff) << 16 | (a2 & 0xffff);
    *(u32 *)(out + 8) = id; *(u32 *)(out + 12) = 0;
    { extern volatile u32 g_cur_charid; g_cur_charid = id; }
    { static int n; if (n++ < 6) hlog(9, (u32)idx, id, *(u32 *)(out + 4), ctx, 0, 0, "GetCharacterInfo idx/id/key/ctx:", 0, 0); }
    return 0;
}
/* 173 sqPlayOnlineGetHandleNameInfo(idx, out): PlayOnline's handle-name (nickname) list.  When a character is picked the game looks for a valid handle record
   with a free character slot (0x375A00: out[0] bit0 = valid, out[0x20..0x27] bit0 = slot in use) to attach it to; with no PlayOnline it found none and raised
   POL-0001.  One record (index 0) with all eight slots free. */
static int svc_pol_handleinfo(int idx, u8 *out)
{
    if (!out || idx != 0) return -1;
    out[0] = 1;                                   /* only the bytes the game reads: the buffer is the 0x28-byte record */
    for (int i = 0x20; i < 0x28; i++) out[i] = 0;
    return 0;
}
static u32 svc_polcon_nop(void)        { return 0; }    /* 1140 SetNonOperationTimeEnable, 1141 SetDisconnectionTimeForNonOperation, 1149 SetNonOperationFunc, 1150 CloseNowForNonOperation */

/* UDP "local address probe" (the game opens a datagram socket just to ask its own address, then closes it): the lifted UDP path is untested
   and crashes, so answer these three directly */
static u32 svc_udp_open_stub(void)  { net_ensure(); return 1; }                /* 240 sqCreateDatagramSocket -> fake handle */
static u32 svc_udp_getname_stub(int h, u16 *out)                               /* 225 sqGetSockName: {type=1, port, addr} in host order */
{
    (void)h; if (out) { out[0] = 1; out[1] = 0x9000; *(u32 *)(out + 2) = g_net_ip; }
    return 0;
}
/* DNS: the game resolves PlayOnline host names (ffxi00.pol.com ...); every name resolves to our server.  221 = sqGetHostByName(name) -> handle,
   222 = sqGetHostByNameCheck(handle, out): >0 done; the 4 address bytes (network order) go to out+4 */
#ifndef DEV_IP
#define DEV_IP "0.0.0.0"
#endif
char g_dev_port[8] = "54001";
char g_dev_ip[32] = DEV_IP;      /* the server address every PlayOnline host name resolves to; the developer window can change it */
static u32 svc_dns_open(const char *name) { (void)name; net_ensure(); return 1; }
static u32 svc_dns_check(int h, u8 *out)
{
    (void)h; if (!out) return -1;
    const char *ip = g_dev_ip; u8 b[4] = {0, 0, 0, 0}; int k = 0; unsigned v = 0;
    for (const char *p = ip;; p++) { if (*p >= '0' && *p <= '9') v = v * 10 + (*p - '0'); else { if (k < 4) b[k++] = (u8)v; v = 0; if (!*p) break; } }
    for (int i = 0; i < 0x20; i++) out[i] = 0;
    out[4] = b[3]; out[5] = b[2]; out[6] = b[1]; out[7] = b[0];   /* the game byte-swaps this once more on the way to the socket: observed 111.1.168.192 with the natural order */
    return 1;
}
static u32 svc_udp_close_stub(void) { return 0; }                              /* 243 sqCloseDatagramSocket */

/* POL slot call tracer (debug): logs the first few calls of each wrapped lifted slot with a0/a1/result */
#ifdef POL_TRACE
volatile u32 g_poltr[1537][5];   /* per slot: count, last a0, last a1, last ret, first-nonzero-ret-or-neg flag */
static inline void pol_tlog(int n, u32 a0, u32 a1, u32 r) { volatile u32 *e = g_poltr[n]; e[0]++; e[1] = a0; e[2] = a1; e[3] = r; if ((int)r < 0) e[4] = r; }
static u32 pt126(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[126])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(126,a0,a1,r);return r;}
static u32 pt167(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[167])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(167,a0,a1,r);return r;}
static u32 pt168(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[168])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(168,a0,a1,r);return r;}
static u32 pt169(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[169])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(169,a0,a1,r);return r;}
static u32 pt170(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[170])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(170,a0,a1,r);return r;}
static u32 pt171(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[171])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(171,a0,a1,r);return r;}
static u32 pt172(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[172])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(172,a0,a1,r);return r;}
static u32 pt173(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[173])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(173,a0,a1,r);return r;}
static u32 pt174(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[174])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(174,a0,a1,r);return r;}
static u32 pt175(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[175])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(175,a0,a1,r);return r;}
static u32 pt178(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[178])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(178,a0,a1,r);return r;}
static u32 pt179(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[179])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(179,a0,a1,r);return r;}
static u32 pt181(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[181])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(181,a0,a1,r);return r;}
static u32 pt183(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[183])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(183,a0,a1,r);return r;}
static u32 pt184(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[184])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(184,a0,a1,r);return r;}
static u32 pt185(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[185])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(185,a0,a1,r);return r;}
static u32 pt186(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[186])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(186,a0,a1,r);return r;}
static u32 pt187(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[187])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(187,a0,a1,r);return r;}
static u32 pt188(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[188])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(188,a0,a1,r);return r;}
static u32 pt189(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[189])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(189,a0,a1,r);return r;}
static u32 pt190(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[190])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(190,a0,a1,r);return r;}
static u32 pt191(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[191])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(191,a0,a1,r);return r;}
static u32 pt192(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[192])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(192,a0,a1,r);return r;}
static u32 pt193(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[193])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(193,a0,a1,r);return r;}
static u32 pt194(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[194])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(194,a0,a1,r);return r;}
static u32 pt195(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[195])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(195,a0,a1,r);return r;}
static u32 pt197(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[197])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(197,a0,a1,r);return r;}
static u32 pt198(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[198])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(198,a0,a1,r);return r;}
static u32 pt199(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[199])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(199,a0,a1,r);return r;}
static u32 pt200(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[200])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(200,a0,a1,r);return r;}
static u32 pt201(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[201])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(201,a0,a1,r);return r;}
static u32 pt202(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[202])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(202,a0,a1,r);return r;}
static u32 pt203(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[203])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(203,a0,a1,r);return r;}
static u32 pt204(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[204])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(204,a0,a1,r);return r;}
static u32 pt205(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[205])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(205,a0,a1,r);return r;}
static u32 pt206(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[206])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(206,a0,a1,r);return r;}
static u32 pt207(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[207])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(207,a0,a1,r);return r;}
static u32 pt208(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[208])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(208,a0,a1,r);return r;}
static u32 pt210(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[210])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(210,a0,a1,r);return r;}
static u32 pt211(u32 a0,u32 a1,u32 a2,u32 a3,u32 t0,u32 t1,u32 t2,u32 t3){u32 r=((u32(*)(u32,u32,u32,u32,u32,u32,u32,u32))g_orig[211])(a0,a1,a2,a3,t0,t1,t2,t3);pol_tlog(211,a0,a1,r);return r;}
static void pol_trace_install(u32 *tab){
  if (tab[126] && (tab[126] != g_orig[126])) { g_orig[126] = tab[126]; tab[126] = (u32)pt126; }
  if (tab[167] && (tab[167] != g_orig[167])) { g_orig[167] = tab[167]; tab[167] = (u32)pt167; }
  if (tab[168] && (tab[168] != g_orig[168])) { g_orig[168] = tab[168]; tab[168] = (u32)pt168; }
  if (tab[169] && (tab[169] != g_orig[169])) { g_orig[169] = tab[169]; tab[169] = (u32)pt169; }
  if (tab[170] && (tab[170] != g_orig[170])) { g_orig[170] = tab[170]; tab[170] = (u32)pt170; }
  if (tab[171] && (tab[171] != g_orig[171])) { g_orig[171] = tab[171]; tab[171] = (u32)pt171; }
  if (tab[172] && (tab[172] != g_orig[172])) { g_orig[172] = tab[172]; tab[172] = (u32)pt172; }
  if (tab[173] && (tab[173] != g_orig[173])) { g_orig[173] = tab[173]; tab[173] = (u32)pt173; }
  if (tab[174] && (tab[174] != g_orig[174])) { g_orig[174] = tab[174]; tab[174] = (u32)pt174; }
  if (tab[175] && (tab[175] != g_orig[175])) { g_orig[175] = tab[175]; tab[175] = (u32)pt175; }
  if (tab[178] && (tab[178] != g_orig[178])) { g_orig[178] = tab[178]; tab[178] = (u32)pt178; }
  if (tab[179] && (tab[179] != g_orig[179])) { g_orig[179] = tab[179]; tab[179] = (u32)pt179; }
  if (tab[181] && (tab[181] != g_orig[181])) { g_orig[181] = tab[181]; tab[181] = (u32)pt181; }
  if (tab[183] && (tab[183] != g_orig[183])) { g_orig[183] = tab[183]; tab[183] = (u32)pt183; }
  if (tab[184] && (tab[184] != g_orig[184])) { g_orig[184] = tab[184]; tab[184] = (u32)pt184; }
  if (tab[185] && (tab[185] != g_orig[185])) { g_orig[185] = tab[185]; tab[185] = (u32)pt185; }
  if (tab[186] && (tab[186] != g_orig[186])) { g_orig[186] = tab[186]; tab[186] = (u32)pt186; }
  if (tab[187] && (tab[187] != g_orig[187])) { g_orig[187] = tab[187]; tab[187] = (u32)pt187; }
  if (tab[188] && (tab[188] != g_orig[188])) { g_orig[188] = tab[188]; tab[188] = (u32)pt188; }
  if (tab[189] && (tab[189] != g_orig[189])) { g_orig[189] = tab[189]; tab[189] = (u32)pt189; }
  if (tab[190] && (tab[190] != g_orig[190])) { g_orig[190] = tab[190]; tab[190] = (u32)pt190; }
  if (tab[191] && (tab[191] != g_orig[191])) { g_orig[191] = tab[191]; tab[191] = (u32)pt191; }
  if (tab[192] && (tab[192] != g_orig[192])) { g_orig[192] = tab[192]; tab[192] = (u32)pt192; }
  if (tab[193] && (tab[193] != g_orig[193])) { g_orig[193] = tab[193]; tab[193] = (u32)pt193; }
  if (tab[194] && (tab[194] != g_orig[194])) { g_orig[194] = tab[194]; tab[194] = (u32)pt194; }
  if (tab[195] && (tab[195] != g_orig[195])) { g_orig[195] = tab[195]; tab[195] = (u32)pt195; }
  if (tab[197] && (tab[197] != g_orig[197])) { g_orig[197] = tab[197]; tab[197] = (u32)pt197; }
  if (tab[198] && (tab[198] != g_orig[198])) { g_orig[198] = tab[198]; tab[198] = (u32)pt198; }
  if (tab[199] && (tab[199] != g_orig[199])) { g_orig[199] = tab[199]; tab[199] = (u32)pt199; }
  if (tab[200] && (tab[200] != g_orig[200])) { g_orig[200] = tab[200]; tab[200] = (u32)pt200; }
  if (tab[201] && (tab[201] != g_orig[201])) { g_orig[201] = tab[201]; tab[201] = (u32)pt201; }
  if (tab[202] && (tab[202] != g_orig[202])) { g_orig[202] = tab[202]; tab[202] = (u32)pt202; }
  if (tab[203] && (tab[203] != g_orig[203])) { g_orig[203] = tab[203]; tab[203] = (u32)pt203; }
  if (tab[204] && (tab[204] != g_orig[204])) { g_orig[204] = tab[204]; tab[204] = (u32)pt204; }
  if (tab[205] && (tab[205] != g_orig[205])) { g_orig[205] = tab[205]; tab[205] = (u32)pt205; }
  if (tab[206] && (tab[206] != g_orig[206])) { g_orig[206] = tab[206]; tab[206] = (u32)pt206; }
  if (tab[207] && (tab[207] != g_orig[207])) { g_orig[207] = tab[207]; tab[207] = (u32)pt207; }
  if (tab[208] && (tab[208] != g_orig[208])) { g_orig[208] = tab[208]; tab[208] = (u32)pt208; }
  if (tab[210] && (tab[210] != g_orig[210])) { g_orig[210] = tab[210]; tab[210] = (u32)pt210; }
  if (tab[211] && (tab[211] != g_orig[211])) { g_orig[211] = tab[211]; tab[211] = (u32)pt211; }
}
#endif

/* NET fix: the lifted kernel's sleep sqDelay(hsyncs) (0x1FAA10) arms a raw kernel alarm. On a real PS2 such an alarm is sometimes missed
   and then fires only at the 4.2 s timer wrap or never (userfile.c), which stalls the network start-up (sqInitSocketAPI's readiness loop)
   and the file-lock spin at 0x1FAAA0 (sqDelay(1)). Replaced by the same sleep on the host's protected alarm (svc_alarm_set: watchdog +
   vblank rescue). The callback here is the host's own: the lifted one ends with "ei", which must not run inside the vblank handler
   (NETDIAG9 routed the lifted callback through that path and the console went black at boot). */
volatile int g_lkalarm_patched = 0; volatile u32 g_sqd_calls = 0;
static void sqd_cb(s32 id, u16 t, void *arg) { (void)id; (void)t; iSignalSema((int)(u32)arg); }
int host_sqdelay_safe(u32 ticks)
{
    extern u64 svc_alarm_set(u64 clk, u64 cb, u64 arg);
    ticks &= 0xffff; if (ticks < 2) ticks = 2;               /* as the original: 0 or 1 becomes 2 */
    g_sqd_calls++;
    ee_sema_t sp; memset(&sp, 0, sizeof sp); sp.init_count = 0; sp.max_count = 1;
    int sid = CreateSema(&sp);
    if (sid < 0) return sid;
    s32 r = (s32)svc_alarm_set((u64)ticks, (u64)(u32)sqd_cb, (u64)(u32)sid);
    if (r >= 0) WaitSema(sid);
    DeleteSema(sid);
    return 0;
}
static void patch_lk_alarm(void)
{
    volatile u32 *p = (volatile u32 *)0x1FAA10;
    if (p[0] == 0x27bdffd0 && p[1] == 0xffb10010) {           /* expected prologue: addiu sp,-0x30 ; sd s1,0x10(sp) */
        p[0] = 0x08000000 | (((u32)host_sqdelay_safe >> 2) & 0x3ffffff); p[1] = 0;   /* j host_sqdelay_safe ; nop */
        FlushCache(0); FlushCache(2); g_lkalarm_patched = 1;
    } else g_lkalarm_patched = -1;
}
/* PS2 fix: the lifted sqDelay(hsyncs) (0x1FAA10) = CreateSema + raw kernel SetAlarm + WaitSema. When the alarm is missed (the timer target
   has already passed when it is armed, more likely while the game keeps the CPU busy) the thread waits until the 16-bit timer wraps, or forever.
   Seen in PCSX2 (NETDIAG29P): with the game running beside the bring-up, sqInitSocketAPI(3) never returned (net thread waiting on that semaphore).
   Replaced by a plain DelayThread of the same length: no callback, no semaphore; DelayThread is what the host's own waits use and is reliable on
   the console.  It is the only raw-alarm user in the lifted kernel (0x1FA9E0 has one caller). */
static int host_sqdelay_dt(u32 ticks)
{
    ticks &= 0xffff; if (ticks < 2) ticks = 2;                /* as the original: 0 or 1 becomes 2 */
    g_sqd_calls++;
    DelayThread(ticks * 64);                                  /* one hsync = 63.6 us */
    return 0;
}
/* PS2 fix (NETDIAG34): interrupt-context code from the 2007 kernel and the game ends with "sync; ei" (the SDK's ExitHandler), but here it runs
   in the middle of other handlers: the game's alarm callbacks (0x442CB0, 0x4E73F0) inside the host's alarm table / vblank rescue, the sceFs
   SIF command wrapper (0x1EC5F0) inside the SDK's SIF interrupt handler, the old sqDelay callback (0x1FA9B0).  The early "ei" lets the next
   interrupt in while the outer handler is still running.  The real PS2 then stops running threads that are READY (NETDIAG31-33 hang reports:
   CPU idle, game threads READY, frames 0).  The ei becomes a nop; interrupts come back on when the kernel returns from the interrupt.
   Also: the game's request worker (0x443B40 loop) lowers its own priority 1 -> 2 between requests (0x443D48); every console freeze had that
   call still in progress.  The worker now stays at priority 1.
   NETDIAG34 on the console froze at the zone-in with both changes (no report at all: interrupts or the report thread never came back),
   so both are OFF by default now (-DEI_FIX / -DPRIO_FIX to try them again).  The freeze was the GS wait above (host.c svc_gssyncpath). */
volatile int g_ei_fixed = 0, g_prio_fixed = 0;
static void __attribute__((unused)) patch_handler_ei(void)
{
#ifdef EI_FIX
    static const u32 at[4] = { 0x1EC60C, 0x1FA9C4, 0x442CD4, 0x4E7404 };
    for (int i = 0; i < 4; i++) { volatile u32 *w = (volatile u32 *)at[i]; if (*w == 0x42000038u) { *w = 0; g_ei_fixed++; } }
#endif
#ifdef PRIO_FIX
    { volatile u32 *w = (volatile u32 *)0x443D48; if (*w == 0x0C15C16Eu && *(volatile u32 *)0x443D4C == 0x24050002u) { *w = 0; g_prio_fixed = 1; } }
#endif
    FlushCache(0); FlushCache(2);
}
static void patch_lk_delay(void)
{
    volatile u32 *p = (volatile u32 *)0x1FAA10;
    if (p[0] == 0x27bdffd0 && p[1] == 0xffb10010) {
        p[0] = 0x08000000 | (((u32)host_sqdelay_dt >> 2) & 0x3ffffff); p[1] = 0;   /* j host_sqdelay_dt ; nop */
        FlushCache(0); FlushCache(2); g_lkalarm_patched = 2;
    } else g_lkalarm_patched = -1;
}
/* call after lift_place(): wraps the lifted socket slots and installs the POLCON answers */
void net_install(u32 *tab)
{
    (void)patch_lk_alarm; (void)hm_draw;                                   /* PS2 fix: not applied (NETDIAG9/10 went black on the console) */
    (void)exists;
    bp_install();
#if defined(EI_FIX) || defined(PRIO_FIX)
    patch_handler_ei(); printf("[host] handler ei -> nop: %d of 4, worker priority fix: %d\n", g_ei_fixed, g_prio_fixed);
#endif
#ifdef NETDIAG
    cd_install(); rl_install();                       /* diagnostic: CD-only file fallback, resource-loader tracing */
#endif
#ifndef NO_SQDELAY_FIX
    patch_lk_delay(); printf("[host] sqDelay -> DelayThread: %d (2 = patched)\n", g_lkalarm_patched);
#endif
    static const struct { int slot; void *fn; } w[] = { {1080, w_safeport}, {221, w_gethost}, {231, w_csock}, {232, w_cchk}, {237, w_send}, {236, n236}, {238, n238} };
    for (unsigned i = 0; i < sizeof w / sizeof w[0]; i++) {
        g_orig[w[i].slot] = tab[w[i].slot];
        if (g_orig[w[i].slot]) tab[w[i].slot] = (u32)w[i].fn;
    }
    tab[221] = (u32)svc_dns_open; tab[222] = (u32)svc_dns_check;
    { static const int done_slots[] = { 176, 180, 182, 196, 209, 274, 276, 279, 281 }; for (unsigned k = 0; k < sizeof done_slots / sizeof done_slots[0]; k++) tab[done_slots[k]] = (u32)svc_pol_done; }
    tab[1003] = (u32)svc_polpro_random; tab[177] = (u32)svc_pol_charinfo; tab[173] = (u32)svc_pol_handleinfo;
#ifdef NET_REAL_UDP
    { static const struct { int slot; void *fn; } u[] = { {240,u240},{244,u244},{245,u245},{246,u246},{247,u247},{252,u252},{253,u253},{241,u241},{242,u242},{243,u243},{248,u248},{249,u249},{250,u250},{251,u251},{225,u225} };
      for (unsigned i = 0; i < sizeof u / sizeof u[0]; i++) if (tab[u[i].slot]) { g_orig[u[i].slot] = tab[u[i].slot]; tab[u[i].slot] = (u32)u[i].fn; } }
#else
    tab[240] = (u32)svc_udp_open_stub; tab[225] = (u32)svc_udp_getname_stub; tab[243] = (u32)svc_udp_close_stub;
#endif
    tab[818] = (u32)svc_polcon_check_msg; tab[836] = (u32)svc_polcon_msg_stat; tab[838] = (u32)svc_polcon_net_status;
    tab[1140] = tab[1141] = tab[1149] = tab[1150] = (u32)svc_polcon_nop;
#ifdef POL_TRACE
    pol_trace_install(tab);
#endif
}

#ifdef NET_SELFTEST
/* Stand-alone test, no game: build with -DNET_SELFTEST (net_test.h supplies NET_TEST_IP / NET_TEST_PORT).  Brings the stack up, opens one TCP
   connection through the real slot table (231/232/237/238/236), sends "HELLO-FFXI\n" and logs what comes back (an echo server is enough). */
#include "net_test.h"      /* defines NET_TEST_IP "a.b.c.d" and NET_TEST_PORT; written by run_net.sh */


void net_selftest(void)
{
    u32 *tab = (u32 *)SLOT_TABLE; SqAddr a; static char buf[64] __attribute__((aligned(16)));
    typedef int (*f2)(u32, void *); typedef int (*f1)(int); typedef int (*f3)(int, void *, int);
    if (dev_parse_ip(NET_TEST_IP, &a)) { L("selftest: bad NET_TEST_IP", 0, 0, 0); return; }
    a.port = NET_TEST_PORT;   /* host order: the kernel byte-swaps both fields on the way to the IOP (the game passes ntohs/ntohl values too) */
    int h = ((f2)tab[231])(0, &a);                       /* wrapper: runs the bring-up first */
    L("selftest: net state / sqCreateSocket handle", (u32)g_net_state, (u32)h, g_net_err);
    if (h < 0) return;
    int r = 0;
    for (int i = 0; i < 300 && r == 0; i++) { r = ((f1)tab[232])(h); if (!r) DelayThread(100 * 1000); }
    L("selftest: sqCreateSocketCheck (>0 connected)", (u32)r, 0, 0);
    if (r <= 0) return;
    memcpy(buf, "HELLO-FFXI\n", 11);
    int sent = ((f3)tab[237])(h, buf, 11); L("selftest: sqSocketSend rc", (u32)sent, 0, 0);
    int got = 0; memset(buf, 0, sizeof buf);
    for (int i = 0; i < 100 && got <= 0; i++) { got = ((f3)tab[238])(h, buf, 32); if (got <= 0) DelayThread(100 * 1000); }
    L("selftest: sqSocketRecv rc", (u32)got, 0, 0);
    if (got > 0) { hlog(9, *(u32 *)buf, *(u32 *)(buf + 4), *(u32 *)(buf + 8), 0, 0, 0, "selftest: first 12 bytes echoed", buf, 0); }
    ((f1)tab[236])(h);
    L("selftest: done", 0, 0, 0);
}
#endif

#ifdef NET_INGAME_TEST
#include "net_test.h"
static u8 nt_stack[16384] __attribute__((aligned(16)));
static void nettest_thread(void *arg)
{
    extern volatile u32 g_hid_ready;
    while (!g_hid_ready) { for (volatile int w = 0; w < 3000000; w++) { } }
    net_ensure();
    u32 *tab = (u32 *)SLOT_TABLE; SqAddr a; static char buf[64] __attribute__((aligned(16)));
    typedef int (*f2)(u32, void *); typedef int (*f1)(int); typedef int (*f3)(int, void *, int);
    if (dev_parse_ip(NET_TEST_IP, &a)) return;
    a.port = NET_TEST_PORT;
    int h = ((f2)tab[231])(0, &a);
    hlog(9, (u32)h, a.addr, a.port, 0, 0, 0, "NETTEST sqCreateSocket handle/addr/port:", 0, 0);
    if (h < 0) return;
    int r = 0, i;
    for (i = 0; i < 400 && r == 0; i++) { r = ((f1)tab[232])(h); if (!r) DelayThread(50 * 1000); }
    hlog(9, (u32)r, (u32)i, 0, 0, 0, 0, "NETTEST connect-check result/polls:", 0, 0);
    if (r <= 0) return;
    memcpy(buf, "HELLO-INGAME\n", 13);
    int sent = ((f3)tab[237])(h, buf, 13);
    int got = 0; memset(buf, 0, sizeof buf);
    for (i = 0; i < 100 && got <= 0; i++) { got = ((f3)tab[238])(h, buf, 32); if (got <= 0) DelayThread(100 * 1000); }
    hlog(9, (u32)sent, (u32)got, *(u32 *)buf, 0, 0, 0, "NETTEST sent/recv/first word:", 0, 0);
    ((f1)tab[236])(h);
}
void nettest_start(void)
{
    ee_thread_t t; memset(&t, 0, sizeof t);
    t.func = (void *)nettest_thread; t.stack = nt_stack; t.stack_size = sizeof nt_stack; t.initial_priority = 50; t.gp_reg = &_gp;
    int id = CreateThread(&t); if (id >= 0) StartThread(id, NULL);
}
#endif
