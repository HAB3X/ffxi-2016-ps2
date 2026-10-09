/* IOP bring-up copied from the 2012 engine's XiHardInitialize:
   reset the IOP with the disc's IOPRP.IMG, load SQIOPMEM, bind its loader RPC (server 0x800), then load the Square/Sony
   modules through it: SCE000, SCE001, SCE002 (with the per-module argument lines), HID000. SQIOPMEM decrypts the .ERX files
   itself on the IOP; nothing is decrypted here. */
#include <stdio.h>
#include <string.h>
#include <tamtypes.h>
#include <kernel.h>
#include <sifrpc.h>
#include <loadfile.h>
#include <iopcontrol.h>
#include <libcdvd.h>
#include <iopheap.h>
#include <sbv_patches.h>
#include <iopcontrol_special.h>
#include "host.h"

static SifRpcClientData_t sq_client __attribute__((aligned(64)));
static u8 sq_buf[0xd0 + 64] __attribute__((aligned(64)));
int sq_ready = 0;
volatile u32 g_iop_step = 0;

/* SQIOPMEM loader command: +4 path (63), +0x44 arguments (127), cmd = RPC function number:
   1 = load+start; 6 = load+start and reserve `size` bytes of IOP memory (+0xc4) */
int sqmem_load(const char *path, const char *args, int cmd, u32 size)
{
    if (!sq_ready) return -1;
    u8 *b = (u8 *)((u32)sq_buf & ~63u);
    memset(b, 0, 0xd0);
    strncpy((char *)b + 4, path, 63);
    if (args) strncpy((char *)b + 0x44, args, 127);
    if (cmd == 6 || cmd == 5) *(u32 *)(b + 0xc4) = size;
    int r = SifCallRpc(&sq_client, cmd, 0, b, 0xd0, b, 0xd0, NULL, NULL);
    hlog(9, (u32)r, *(u32 *)b, *(u32 *)(b + 4), cmd, 0, 0, "sqmem_load rpc/reply0:", path, 0);
    return r;
}

/* ---- start without the install DVD (FreeMcBoot / uLaunchELF from mass: or hdd0:, PCSX2 -elf from host:) ----
   The same Square Enix / Sony IOP modules as the disc's MODULES folder are carried inside this ELF (section .embmods, emb.S):
   the IOP is rebooted with the embedded IOPRP.IMG, embfs.irx provides the device "emb:", and SQIOPMEM loads emb:SCE000.ERX ...
   exactly as it loads cdrom0:\MODULES\SCE000.ERX from the disc. */
int g_boot_disc = 1;                                  /* set by main() from argv[0] */
extern u8 emb_ioprp[], emb_sqiopmem[], emb_embfs[], emb_sce000[], emb_sce001[], emb_sce002[], emb_hid000[];
extern u32 emb_ioprp_size, emb_sqiopmem_size, emb_embfs_size, emb_sce000_size, emb_sce001_size, emb_sce002_size, emb_hid000_size;
static SifRpcClientData_t emb_client __attribute__((aligned(64)));
static u32 emb_buf[16] __attribute__((aligned(64)));
static int emb_put(const char *name, const u8 *data, u32 size)
{
    memset(emb_buf, 0, sizeof emb_buf); strncpy((char *)emb_buf, name, 23); emb_buf[6] = size;
    if (SifCallRpc(&emb_client, 1, 0, emb_buf, 64, emb_buf, 64, NULL, NULL) < 0 || !emb_buf[0]) return -1;
    u32 dst = emb_buf[0], done = 0;
    FlushCache(0);
    while (done < size) {                                   /* SIF DMA in pieces of <= 64 KB (16-byte multiple) */
        SifDmaTransfer_t t; u32 n = size - done > 0x10000 ? 0x10000 : ((size - done + 15) & ~15u);
        t.src = (void *)(data + done); t.dest = (void *)(dst + done); t.size = n; t.attr = 0;
        u32 id; while ((id = SifSetDma(&t, 1)) == 0) { }
        while (SifDmaStat(id) >= 0) { }
        done += n;
    }
    return 0;
}
static int iop_init_emb(void)
{
    int r, id;
    g_iop_step = 101;
    SifInitRpc(0);
    printf("[host] not started from the disc: IOP modules from this ELF (emb:)\n");
    while (!SifIopRebootBuffer(emb_ioprp, (int)emb_ioprp_size)) { g_iop_step = 102; }
    while (!SifIopSync()) { g_iop_step = 103; }
    SifInitRpc(0); SifLoadFileInit(); SifInitIopHeap();
    sbv_patch_enable_lmb(); sbv_patch_disable_prefix_check();
    g_iop_step = 104;
    id = SifExecModuleBuffer(emb_embfs, emb_embfs_size, 0, NULL, &r);
    printf("[host] embfs id=%d ret=%d\n", id, r);
    while (SifBindRpc(&emb_client, 0x0E3B0F51, 0) < 0 || !emb_client.server) { g_iop_step = 105; }
    int e = 0;
    e |= emb_put("SCE000.ERX", emb_sce000, emb_sce000_size); e |= emb_put("SCE001.ERX", emb_sce001, emb_sce001_size);
    e |= emb_put("SCE002.ERX", emb_sce002, emb_sce002_size); e |= emb_put("HID000.ERX", emb_hid000, emb_hid000_size);
    printf("[host] embedded modules uploaded rc=%d\n", e);
    g_iop_step = 106;
    id = SifExecModuleBuffer(emb_sqiopmem, emb_sqiopmem_size, 0, NULL, &r);
    printf("[host] SQIOPMEM (embedded) id=%d ret=%d\n", id, r);
    r = SifBindRpc(&sq_client, 0x800, 0);
    printf("[host] bind SQIOPMEM RPC 0x800 -> %d server=%08x\n", r, (u32)sq_client.server);
    if (r < 0 || !sq_client.server) return -3;
    sq_ready = 1;
    int rc = 0;
    rc |= sqmem_load("emb:SCE000.ERX", "", 1, 0);
    rc |= sqmem_load("emb:SCE001.ERX", "", 1, 0);
    rc |= sqmem_load("emb:SCE002.ERX", "\n\n-o\t2\t-n\t100\n-m\t3\t-o\t3\t-n\t20\n", 1, 0);
    rc |= sqmem_load("emb:HID000.ERX", "", 1, 0);
    printf("[host] Square/Sony IOP modules requested from emb:, rc=%d\n", rc);
    g_iop_step = 107;
    return rc;
}

int iop_init_sony(void)
{
    if (!g_boot_disc) return iop_init_emb();
    g_iop_step = 1;
    SifInitRpc(0);
    g_iop_step = 2;
    sceCdInit(SCECdINIT);                 /* the engine initialises CDVD before the reboot (its 2nd call) */
    sceCdDiskReady(0);
    while (!SifIopReset("rom0:UDNL cdrom0:\\MODULES\\IOPRP.IMG;1", 0)) { g_iop_step = 3; }
    g_iop_step = 4;
    while (!SifIopSync()) { g_iop_step = 5; }
    g_iop_step = 6;
    SifInitRpc(0);
    SifLoadFileInit();
    g_iop_step = 7;
    sceCdInit(SCECdINIT);
    g_iop_step = 8;
    printf("[host] IOP reset with IOPRP.IMG done\n");
    int disc = sceCdGetDiskType();
    g_iop_step = 9;
    sceCdMmode((disc == SCECdPS2DVD || disc == SCECdDVDV) ? SCECdMmodeDvd : SCECdMmodeCd);
    printf("[host] disc type 0x%x\n", disc);
    int id;
    g_iop_step = 10;
#ifdef SQ_FROM_DISC
    do { id = SifLoadModule("cdrom0:\\MODULES\\SQIOPMEM.IRX", 0, NULL); } while (id < 0);
#else
    /* the embedded copy with smaller pools (patch_sqiopmem.py): the disc's own reserves 659 KB of the IOP's 2 MB, too much for the network modules plus the menus */
    sbv_patch_enable_lmb(); sbv_patch_disable_prefix_check();
    { int rr = 0; do { id = SifExecModuleBuffer(emb_sqiopmem, emb_sqiopmem_size, 0, NULL, &rr); } while (id < 0); }
#endif
    printf("[host] SQIOPMEM loaded, module id %d\n", id);
    g_iop_step = 11;
    int r = SifBindRpc(&sq_client, 0x800, 0);
    g_iop_step = 12;
    printf("[host] bind SQIOPMEM RPC 0x800 -> %d server=%08x\n", r, (u32)sq_client.server);
    if (r < 0 || !sq_client.server) return -3;
    sq_ready = 1;
    int rc = 0;
    rc |= sqmem_load("cdrom0:\\MODULES\\SCE000.ERX", "", 1, 0);
    rc |= sqmem_load("cdrom0:\\MODULES\\SCE001.ERX", "", 1, 0);
    rc |= sqmem_load("cdrom0:\\MODULES\\SCE002.ERX", "\n\n-o\t2\t-n\t100\n-m\t3\t-o\t3\t-n\t20\n", 1, 0);
    rc |= sqmem_load("cdrom0:\\MODULES\\HID000.ERX", "", 1, 0);
    printf("[host] Square/Sony IOP modules requested, rc=%d\n", rc);
#ifdef SQ_PROBE
    {   /* query RPC fno 0 (what the kernel's sqmem query does): word at +4 = module number; log reply word 0 */
        u8 *b = (u8 *)((u32)sq_buf & ~63u);
        for (int rep = 0; rep < 4; rep++) {
        for (volatile int w = 0; w < 40000000; w++) { }
        for (u32 n = 18; n < 20; n++) {
            memset(b, 0, 0xd0); *(u32 *)(b + 4) = n;
            int r = SifCallRpc(&sq_client, 0, 0, b, 0xd0, b, 0xd0, NULL, NULL);
            hlog(9, n, (u32)r, *(u32 *)b, *(u32 *)(b + 4), 0, 0, "SQ query n/rc/reply0/reply1:", 0, 0);
        }
        }
    }
#endif
    return rc;
}

/* The kernel's sqmemQuery(n)/sqmemPoll(&w) (donor 0x1ff678 / 0x1ff730) start an asynchronous SQIOPMEM call (fno 0, word at +4 = index n,
   answer = word 0 of the reply) on the kernel's own client structure; under the SDK's SIF layer that call never completes.  Host versions:
   one synchronous call on our aligned client, answer kept for the poll. */
static volatile u32 g_q_word = 0;
int host_sqmem_query(int n)
{
    hlog(9, (u32)n, sq_ready, 0, 0, 0, 0, "host_sqmem_query ENTER n/ready:", 0, 0); hlog_kick();
    if (!sq_ready) return -3;
    u8 *b = (u8 *)((u32)sq_buf & ~63u);
    memset(b, 0, 0xd0); *(u32 *)(b + 4) = (u32)n;
    int r = SifCallRpc(&sq_client, 0, 0, b, 0xd0, b, 0xd0, NULL, NULL);
    g_q_word = *(u32 *)b; { static int nq = 0; if (nq < 30) { nq++; hlog(9, (u32)n, (u32)r, g_q_word, 0, 0, 0, "host_sqmem_query n/rc/word:", 0, 0); hlog_kick(); } }
    return r < 0 ? -3 : 0;
}
int host_sqmem_poll(u32 *w) { *w = g_q_word; return 1; }
