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
#include <stdlib.h>
#include <string.h>
#include <tamtypes.h>
#include <kernel.h>
#include <delaythread.h>
#include "host.h"

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
#define NET_TIMEOUT_S 120
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
int g_net_status_for_polcon = 0;            /* what sqPolconGetNetworkStatus reports */

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
static void L(const char *m, u32 a, u32 b, u32 c) { hlog(9, a, b, c, 0, 0, 0, m, 0, 0); hlog_kick(); }

static int net_load_modules(void)
{
    const char *t, *n; int usepfs = 0;
    L("net: bring-up thread started", 0, 0, 0);
    if (!sq_ready) { L("net: SQIOPMEM not ready", 0, 0, 0); return -1; }
#ifdef NET_SELFTEST
    if (0)                                              /* no pfs1: mount in the stand-alone test: probing would block */
#else
    if (!NET_FORCE_DISC && exists(NET_TCP_PFS) && exists(NET_NDI_PFS))
#endif
    { t = NET_TCP_PFS; n = NET_NDI_PFS; usepfs = 1; }
    else { t = NET_TCP_DISC; n = NET_NDI_DISC; }
    L(usepfs ? "net: using 2007 modules from pfs1" : "net: using 2003 modules from disc", 0, 0, 0);
    int r1 = sqmem_load(t, "", 1, 0);                  /* avetcp first: ndglue/smap/sqiopint import it */
    int r2 = sqmem_load(n, "", 1, 0);
    L("net: module loads rc tcp/ndi:", (u32)r1, (u32)r2, 0);
    return (r1 == 0 && r2 == 0) ? 0 : -2;               /* rc 0 only means the RPC was accepted, not that the module started */
}

static int net_configure(void)
{
    static SqAddr ip, mask, bc, gw, d1, d2; static char dom[256] __attribute__((aligned(16)));
    fn_v dhcp_init = E("sqDhcpInit"), dhcp_req = E("sqDhcpRequest");
    fn_chk dhcp_chk = E("sqDhcpRequestCheck");
    fn_cfg ifcfg = E("sqEthernetIfConfig"); fn_rt route = E("sqAddRoutingTable"); fn_dns dns = E("sqInitDnsResolver");
    memset(&gw, 0, sizeof gw); memset(&d1, 0, sizeof d1); memset(&d2, 0, sizeof d2); dom[0] = 0;
    DelayThread(5 * 1000 * 1000);                          /* smap link negotiation takes ~3 s after the modules start; ifconfig before that fails (-35) */
#if NET_USE_DHCP
    int r = dhcp_init(); L("net: sqDhcpInit rc", (u32)r, 0, 0);
    if (r < 0) return -10;
    for (int i = 0; i < 100; i++) {                     /* the adapter may still be negotiating its link right after the modules start */
        r = dhcp_req(); if (i < 3 || r >= 0) L("net: sqDhcpRequest rc", (u32)r, (u32)i, 0);
        if (r >= 0) break;
        DelayThread(200 * 1000);
    }
    if (r < 0) return -11;
    int st = 0;
    for (int i = 0; i < 600 && !st; i++) {              /* 60 s */
        st = dhcp_chk(&ip, &mask, &bc, &gw, &d1, &d2, dom);   /* 0 pending, <0 failed, >0 bitmask of fields received */
        if (st < 0) { L("net: DHCP failed rc", (u32)st, 0, 0); return -12; }
        if (!st) DelayThread(100 * 1000);
    }
    if (st <= 0) { L("net: DHCP timeout", 0, 0, 0); return -13; }
    L("net: DHCP ok ip/gw/dns1:", ip.addr, gw.addr, d1.addr);
    L("net: DHCP bitmask", (u32)st, 0, 0);
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

static void net_thread(void *arg)
{
    int rc = net_load_modules();
    /* sqInitSocketAPI itself spins until the Sony modules set SQIOPMEM parameter 0 (forever if they did not start);
       net_ensure() therefore gives up waiting after NET_TIMEOUT_S and leaves this thread parked */
    if (rc == 0) {
        int r = ((fn_i1)E("sqInitSocketAPI"))(3);                /* 3 = built-in Ethernet (type 1 = USB adapter also waits for link) */
        L("net: sqInitSocketAPI(3) rc", (u32)r, 0, 0);
        rc = r < 0 ? -4 : 0;
    }
    if (rc == 0) rc = net_configure();
    g_net_err = rc;
    g_net_status_for_polcon = (rc == 0) && NET_POLCON_STATUS;
    g_net_state = rc == 0 ? 2 : -1;
    L("net: bring-up done, state/err", (u32)g_net_state, (u32)rc, g_net_ip);
    for (;;) SleepThread();     /* park instead of exiting (deleting the thread coincided with a kernel-table crash) */
}

static u8 net_stack[65536] __attribute__((aligned(16)));
int net_ensure(void)                                    /* callable from any thread; blocks until bring-up finished; <0 = failed */
{
#ifdef NET_DISABLED
    return -1;
#endif
    if (g_net_state == 0) {
        g_net_state = 1;
        ee_thread_t t; t.func = (void *)net_thread; t.stack = net_stack; t.stack_size = sizeof net_stack; t.gp_reg = &_gp;
        t.initial_priority = 40; t.attr = 0; t.option = 0;
        int id = CreateThread(&t);
        if (id < 0 || StartThread(id, 0) < 0) { g_net_state = -1; g_net_err = -99; }
    }
    for (int ms = 0; g_net_state == 1; ms += 5) {
        if (ms > NET_TIMEOUT_S * 1000) { g_net_state = -2; g_net_err = -98; L("net: bring-up timed out (IOP modules did not come up?)", 0, 0, 0); break; }
        DelayThread(5000);
    }
    return g_net_state == 2 ? 0 : -1;
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
    { static int n = 0; if (slot == 240 && net_ensure() < 0) return (u32)-1; u32 r = ((u32 (*)(u32, u32, u32, u32, u32, u32, u32, u32))g_orig[slot])(a0, a1, a2, a3, t0, t1, t2, t3); \
      if (n < 5) { n++; hlog(9, a0, a1, a2, a3, r, 0, "UDP slot " #slot " a0..a3/ret:", 0, 0); } return r; }
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
    if ((int)r != last) { last = (int)r; hlog(9, a0, r, n, 0, 0, 0, "sqCreateSocketCheck h/ret/pollcount:", 0, 0); }
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

/* call after lift_place(): wraps the lifted socket slots and installs the POLCON answers */
void net_install(u32 *tab)
{
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
