/* File services: the 2016 program's sceOpen/sceRead/... go to the SDK's fileXio (same iomanX semantics). */
#include <stdio.h>
#include <string.h>
#include <tamtypes.h>
#include <kernel.h>
#include <fileXio_rpc.h>
#include <io_common.h>
#include "host.h"

static int nlog = 0;

/* The game opens, reads and closes a file for every request (a list item, a resource): open + seek + read + close, each a round trip to the IOP.
   A read-only handle that was just closed is therefore kept open for a moment: the next open of the same path takes it back and only has to
   rewind it. At most FC_N idle handles are kept (the IOP allows only a few open files); an open that fails, a write open of the same path and
   an unmount all give them back first. */
#define FC_N 2
#define FC_PATH 96
typedef struct { int fd; char path[FC_PATH]; } FcEnt;
static FcEnt g_fo[32];                              /* read-only handles the game has open now (path remembered for the close) */
static FcEnt g_fc[FC_N];                            /* idle ones, oldest first */
static int g_fcn;

static void fc_flush(const char *only)               /* close the idle handles (all, or only those of one path) */
{
    int out[FC_N], n = 0, i, k;
    int o = DIntr();
    for (i = 0, k = 0; i < g_fcn; i++) {
        if (only && strcmp(g_fc[i].path, only)) { g_fc[k++] = g_fc[i]; continue; }
        out[n++] = g_fc[i].fd;
    }
    g_fcn = k;
    if (o) EIntr();
    for (i = 0; i < n; i++) fileXioClose(out[i]);
}
static int fc_take(const char *p)                    /* an idle handle of this path, or -1 */
{
    int fd = -1, i;
    int o = DIntr();
    for (i = g_fcn - 1; i >= 0; i--) if (!strcmp(g_fc[i].path, p)) {
        fd = g_fc[i].fd;
        for (; i + 1 < g_fcn; i++) g_fc[i] = g_fc[i + 1];
        g_fcn--;
        break;
    }
    if (o) EIntr();
    return fd;
}
static void fo_track(int fd, const char *p)
{
    int i, o = DIntr();
    for (i = 0; i < 32; i++) if (g_fo[i].fd <= 0 || g_fo[i].fd == fd) { g_fo[i].fd = fd; strncpy(g_fo[i].path, p, FC_PATH - 1); g_fo[i].path[FC_PATH - 1] = 0; break; }
    if (o) EIntr();
}
static int fo_untrack(int fd, char *path)             /* 1 if fd was a tracked read-only handle (its path is copied to `path`) */
{
    int i, found = 0, o = DIntr();
    for (i = 0; i < 32; i++) if (g_fo[i].fd == fd && fd > 0) { strcpy(path, g_fo[i].path); g_fo[i].fd = 0; found = 1; break; }
    if (o) EIntr();
    return found;
}

u32 svc_sceOpen(const char *p, int fl, int mode)
{
    int r = -1, cacheable = (fl == 1 && strlen(p) < FC_PATH);
    if (cacheable) {
        int fd = fc_take(p);
        if (fd >= 0) {
            if (fileXioLseek(fd, 0, 0) == 0) { fo_track(fd, p); hlog(2, fl, fd, 0, 0, 0, 0, p, 0, 0); return (u32)fd; }
            fileXioClose(fd);
        }
    } else if (g_fcn) {
        char q[FC_PATH]; strncpy(q, p, FC_PATH - 1); q[FC_PATH - 1] = 0;      /* a write or other open of a file: no stale idle handle of it */
        fc_flush(q);
    }
    r = fileXioOpen(p, fl, mode);
    if (r < 0 && g_fcn) { fc_flush(0); r = fileXioOpen(p, fl, mode); }          /* the IOP's open-file limit: give the idle ones back */
    if (r >= 0 && cacheable) fo_track(r, p);
    hlog(2, fl, r, 0, 0, 0, 0, p, 0, 0);
    return (u32)r;
}
u32 svc_sceClose(int fd)
{
    char path[FC_PATH];
    if (fo_untrack(fd, path)) {
        int victim = -1, o = DIntr();
        if (g_fcn == FC_N) { victim = g_fc[0].fd; for (int i = 1; i < FC_N; i++) g_fc[i - 1] = g_fc[i]; g_fcn--; }
        g_fc[g_fcn].fd = fd; strcpy(g_fc[g_fcn].path, path); g_fcn++;
        if (o) EIntr();
        if (victim >= 0) fileXioClose(victim);
        return 0;
    }
    return (u32)fileXioClose(fd);
}
u32 svc_sceRead(int fd, void *b, u32 n)          { int r = fileXioRead(fd, b, n); hlog(3, fd, n, r, (u32)b, 0, 0, 0, 0, 0); return (u32)r; }
u32 svc_sceWrite(int fd, void *b, u32 n)         { return (u32)fileXioWrite(fd, b, n); }
u32 svc_sceLseek(int fd, int off, int wh)        { return (u32)fileXioLseek(fd, off, wh); }
u32 svc_sceGetstat(const char *p, void *st)      { int r = fileXioGetStat(p, st); hlog(4, r, 0, 0, 0, 0, 0, p, 0, 0); return (u32)r; }

/* sceMount("pfs1:", "hdd0:PP.SCUS-97266.0001.FFXI,PASSWORD", flag, arg, arglen): the SDK mounts without the password part */
u32 svc_sceMount(const char *mp, const char *dev, int flag, void *arg, int arglen)
{
    char d[128]; int i;
    for (i = 0; dev[i] && dev[i] != ',' && i < 127; i++) d[i] = dev[i];
    d[i] = 0;
    int r = fileXioMount(mp, d, flag & 1);
    hlog(9, r, flag, 0, 0, 0, 0, "sceMount rc/flag:", 0, 0);
    if (r < 0) { r = fileXioMount(mp, dev, flag & 1); hlog(9, r, flag, 0, 0, 0, 0, "sceMount retry rc/flag:", 0, 0); }
    return (u32)r;
}
u32 svc_sceUmount(const char *mp) { fc_flush(0); int r = fileXioUmount(mp); hlog(9, r, 0, 0, 0, 0, 0, "sceUmount rc:", 0, 0); return (u32)r; }

#include <sifrpc.h>
#include <loadfile.h>
/* slot 93: the program asks for an IOP module by path ("pfs1:/image/ffxi/prog/ps2/modules/iopsound.irx"); the IOP reads it itself.
   Loaded on a helper thread because some modules (the sound driver) do not return from their start routine promptly. */
extern u8 irx_fakesound[], irx_fakesound_end[];
#ifdef SONY_IOP
int g_real_sound = 1;
#else
int g_real_sound = 0;
#endif            /* 1: load Square's IOPSOUND.IRX instead of the silent stand-in */
extern int sqmem_load(const char *path, const char *args, int cmd, u32 size);
u32 svc_loadmod(const char *path, const char *args, u32 size)
{
#ifdef SONY_IOP
    hlog(8, 0, 0, 0, 0, 0, 0, path, 0, 0);
    { extern void netlog(const char *, u32, u32, u32); const char *b = path; for (const char *q = path; *q; q++) if (*q == '/' || *q == '\\' || *q == ':') b = q + 1;
      char m[40]; snprintf(m, sizeof m, "mod> %.30s", b); netlog(m, size, 0, 0); }
    int rr = sqmem_load(path, args ? args : "", size ? 6 : 1, size);
    { extern void netlog(const char *, u32, u32, u32); netlog("mod< rc", (u32)rr, 0, 0); }
    return rr == 0 ? 0 : (u32)-3;
#endif
    int ret = 0, id;
#ifdef NOSOUND
    return 1;
#endif
    if (!g_real_sound && strstr(path, "iopsound")) {
        id = 1; hlog(8, 0, 0, 0, 0, 0, 0, path, 0, 0);
#ifdef RPCTEST
        {   static SifRpcClientData_t cd __attribute__((aligned(64))); static u8 sb[64] __attribute__((aligned(64))), rb[64] __attribute__((aligned(64)));
            int r = sceSifBindRpc(&cd, 0x1001, 0); printf("[host] test bind -> %d server=%08x\n", r, (u32)cd.server);
            r = sceSifCallRpc(&cd, 0, 0, sb, 64, rb, 64, NULL, NULL); printf("[host] test async call -> %d\n", r);
            int n = 0; while (sceSifCheckStatRpc(&cd) && n < 5000000) n++; printf("[host] test call done after %d polls\n", n);
        }
#endif
    } else {
        id = SifLoadStartModule(path, 0, NULL, &ret);
        printf("[host] load IOP module %s -> id=%d ret=%d\n", path, id, ret);
    }
    return id >= 0 ? 1 : (u32)id;
}

/* ---- SIF RPC: the sound servers (0x1000 / 0x1001) are answered here on the EE (silent stand-in, no IOP module) ---- */
#define FAKE_SERVER ((void *)0x7fff0001)
static int nrpc = 0;
typedef struct { u32 fno, ssz, rsz, mode, server, ret; } RpcEnt;      /* every SIF RPC call made by the lifted kernel code (PINE: pk.py rpc) */
volatile RpcEnt g_rpcring[128]; volatile u32 g_rpcn = 0;
static int is_fake_id(int id) { return id == 0x1000 || id == 0x1001; }
u32 svc_bindrpc(SifRpcClientData_t *c, int id, int mode)
{
    static int nb = 0;
    if (is_fake_id(id) && !g_real_sound) {
        c->server = FAKE_SERVER; c->command = 0;
        if (nb < 40) { nb++; hlog(5, id, 0, 0x7fff0001, 0, 0, 0, " (silent stand-in)", 0, 0); }
        return 0;
    }
    int r = sceSifBindRpc(c, id, mode);
    if (nb < 40) { nb++; hlog(5, id, r, (u32)c->server, 0, 0, 0, "", 0, 0); }
    return (u32)r;
}
u32 svc_callrpc(SifRpcClientData_t *c, int fno, int mode, void *snd, int ssz, void *rcv, int rsz, void (*endf)(void *), void *efdata)
{
    if (c->server == FAKE_SERVER) {
        if (nrpc < 40) { nrpc++; hlog(6, 0x7fff0001, fno, mode, (u32)snd, ssz, (u32)rcv, " (stand-in)", 0, 0); }
        if (rcv && rsz > 0) memset(rcv, 0, rsz);
        if (endf) endf(efdata);
        return 0;
    }
    if (mode & 1) { static int na = 0; if (na < 40) { na++; hlog(9, (u32)c, (u32)fno, (u32)snd, (u32)rcv, (u32)endf, (u32)c->server, "ASYNC CallRpc client/fno/snd/rcv/endf:", 0, 0); } }
    if (nrpc < 60) { nrpc++; hlog(6, (u32)c->server, fno, mode, (u32)snd, ssz, (u32)rcv, "", 0, 0); }
    volatile RpcEnt *e = &g_rpcring[g_rpcn % 128]; e->fno = fno; e->ssz = ssz; e->rsz = rsz; e->mode = mode; e->server = (u32)c->server; e->ret = 0xdead0000; g_rpcn++;
    u32 r = (u32)sceSifCallRpc(c, fno, mode, snd, ssz, rcv, rsz, endf, efdata);
    e->ret = r;
    return r;
}
u32 svc_checkstatrpc(SifRpcClientData_t *c)
{
    if (c->server == FAKE_SERVER) return 0;
    return (u32)sceSifCheckStatRpc(c);
}

/* SIF DMA to the IOP. The sound stand-in has no IOP side, so the program's uploads to it are swallowed (and reported done):
   letting them through would write to IOP addresses the stand-in's replies never provided (dest 0 = the IOP's own vectors). */
static u32 fake_dma_id = 0x7000;
u32 svc_sifsetdma(SifDmaTransfer_t *t, int n)
{
#ifdef SONY_IOP
    return (u32)sceSifSetDma(t, n);
#endif
    static int nd = 0;
    if (nd < 60) { nd++; for (int i = 0; i < n && i < 4; i++) hlog(7, (u32)t[i].src, (u32)t[i].dest, t[i].size, t[i].attr, 0, 0, 0, 0, 0); }
    return ++fake_dma_id;
}
u32 svc_sifdmastat(u32 id) {
#ifdef SONY_IOP
    return (u32)sceSifDmaStat(id);
#endif
    return (id > 0x7000 && id <= fake_dma_id) ? (u32)-1 : (u32)sceSifDmaStat(id); }
