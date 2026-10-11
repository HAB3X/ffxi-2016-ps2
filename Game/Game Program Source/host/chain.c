/* chain.c - start a game program downloaded by the in-game update (update.c) instead of the one on the disc (Fan Project by Habex).
   Called right after the IOP is up (the hard drive can be read). UPDATE/HOST.TXT:  "<size> <crc32 hex> <name>\n<unconfirmed starts>\n".
   The new program is read into RAM at STAGE, checked (size, CRC, ELF layout), and a small copy routine placed at STUB moves its segments to
   their addresses and starts it with ExecPS2 (argv[1] = "chained"). Every start that is not confirmed (update.c confirm_host, on the sign-in
   page) counts; at the third the update is dropped (BAD.TXT remembers its CRC) and the disc program runs. Any problem on the way: return and
   carry on with the program on the disc. */
#ifdef NETDIAG
volatile int g_chained = 0, g_chain_dropped = 0;     /* debug link builds: no update client (see update.c) */
void chain_boot(void) { }
#else
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <tamtypes.h>
#include <kernel.h>
#include <delaythread.h>
extern void _ps2sdk_deinit_timer(void);
#include <sifrpc.h>
#include <loadfile.h>
#include <iopheap.h>
#include "host.h"

#define UD "pfs1:/image/ffxi/UPD"
#define STAGE 0x1000000u
#define STAGE_MAX 0x800000u
#define STUB 0x900000u
#define SEG_MAX 8

volatile int g_chained = 0;
#define SLOT(n) (((u32 *)SLOT_TABLE)[n])
static int io_open(const char *p, int fl, int m) { return ((int (*)(const char *, int, int))SLOT(938))(p, fl, m); }
static int io_close(int fd) { return ((int (*)(int))SLOT(939))(fd); }
static int io_read(int fd, void *b, int n) { return ((int (*)(int, void *, int))SLOT(940))(fd, b, n); }
static int io_write(int fd, const void *b, int n) { return ((int (*)(int, const void *, int))SLOT(941))(fd, b, n); }
static int io_mount(const char *mp, const char *dev) { return ((int (*)(const char *, const char *, int, void *, int))SLOT(956))(mp, dev, 0, 0, 0); }
static int io_umount(const char *mp) { return ((int (*)(const char *))SLOT(957))(mp); }
extern char g_self_path[96];

/* position independent: segment records {src, dst, filesz, memsz} after {entry, gp, argc, argv, nseg}; a0 = the block */
extern void chain_stub_start(void), chain_stub_end(void);
__asm__(".set push\n.set noreorder\n.set noat\n"
        ".globl chain_stub_start\n.globl chain_stub_end\n"
        "chain_stub_start:\n"
                "  lw   $8, 0($4)\n  lw   $9, 4($4)\n  lw   $10, 8($4)\n  lw   $11, 12($4)\n  lw   $12, 16($4)\n"
        "  addiu $5, $4, 20\n"
        "1: beqz $12, 5f\n  nop\n"
        "  lw   $6, 0($5)\n  lw   $7, 4($5)\n  lw   $2, 8($5)\n  lw   $3, 12($5)\n"
        "  subu $3, $3, $2\n"
        "2: beqz $2, 3f\n  nop\n"
        "  lbu  $13, 0($6)\n  addiu $6, $6, 1\n  sb   $13, 0($7)\n  addiu $7, $7, 1\n"
        "  b    2b\n  addiu $2, $2, -1\n"
        "3: beqz $3, 4f\n  nop\n"
        "  sb   $0, 0($7)\n  addiu $7, $7, 1\n"
        "  b    3b\n  addiu $3, $3, -1\n"
        "4: addiu $5, $5, 16\n"
        "  b    1b\n  addiu $12, $12, -1\n"
        "5: move $16, $8\n  move $17, $9\n  move $18, $10\n  move $19, $11\n"
        "  li   $3, 0x64\n  li   $4, 0\n  syscall\n  nop\n"
        "  li   $3, 0x64\n  li   $4, 2\n  syscall\n  nop\n"
        "  move $4, $16\n  move $5, $17\n  move $6, $18\n  move $7, $19\n"
        "  li   $3, 7\n  syscall\n  nop\n"
        "6: b 6b\n  nop\n"
        "chain_stub_end:\n"
        ".set pop\n");

static u32 crc32u(u32 c, const u8 *p, u32 n)
{
    c = ~c;
    while (n--) { c ^= *p++; for (int k = 0; k < 8; k++) c = (c >> 1) ^ (0xEDB88320u & (0u - (c & 1))); }
    return ~c;
}
static int rd_small(const char *path, char *buf, int max)
{
    int fd = (int)io_open(path, 1, 0), n;
    if (fd < 0) return -1;
    n = (int)io_read(fd, buf, max - 1); io_close(fd);
    if (n < 0) return -1;
    buf[n] = 0; return n;
}
static int put_small(const char *path, const char *buf, int n)
{
    int fd = (int)io_open(path, 0x0002 | 0x0200 | 0x0400, 0666), w;
    if (fd < 0) return -1;
    w = (int)io_write(fd, (void *)buf, n); io_close(fd);
    return w == n ? 0 : -1;
}

volatile int g_chain_dropped = 0;          /* 1: an update was dropped because it did not start */
static void quiesce(void)                  /* the threads of this program (logger, watchdog) must not outlive the code they run */
{
    int me = GetThreadId();
    for (int t = 1; t < 64; t++) if (t != me) { TerminateThread(t); DeleteThread(t); }
}

void chain_boot(void)                       /* returns when there is nothing (valid) to start */
{
    static char b[96], name[64], p[120]; static u32 blk[20 + 4 * SEG_MAX] __attribute__((aligned(16)));
    u32 size, crc; int n, tries, i, mounted = 0;
    char *q;
    printf("[host] chain: start\n"); hlog_kick();
    for (i = 0; i < 5 && !mounted; i++) {
        int mr = (int)io_mount("pfs1:", "hdd0:PP.SCUS-97266.0001.FFXI,NARINARI");
        printf("[host] chain: mount rc %d\n", mr); hlog_kick();
        if (mr >= 0) mounted = 1; else DelayThread(300 * 1000);
    }
    if (!mounted) return;
    n = rd_small(UD "HOST.TXT", b, sizeof b);
    printf("[host] chain: HOST.TXT %d\n", n);
    if (n < 8) goto out;
    size = (u32)strtoul(b, &q, 10); crc = (u32)strtoul(q, &q, 16);
    while (*q == ' ') q++;
    for (i = 0; *q && *q != '\n' && i < 63; ) name[i++] = *q++;
    name[i] = 0;
    if (*q == '\n') q++;
    tries = atoi(q);
    if (size < 4096 || size > STAGE_MAX || !name[0] || strchr(name, '/')) goto out;
    if (tries >= 1) {                                                  /* started once without reaching the sign-in page: give it up (the disc program runs) */
        put_small(UD "HOST.TXT", "", 0); g_chain_dropped = 1;
        goto out;
    }
    strcpy(p, "pfs1:/image/ffxi/U_"); strcat(p, name);
    {
        u8 *st = (u8 *)STAGE; u32 got = 0; int fd = (int)io_open(p, 1, 0);
        if (fd < 0) goto out;
        while (got < size) { int r = (int)io_read(fd, st + got, size - got > 0x10000 ? 0x10000 : size - got); if (r <= 0) break; got += (u32)r; }
        io_close(fd);
        if (got != size || crc32u(0, st, size) != crc) goto out;
        /* ELF checks */
        if (*(u32 *)st != 0x464C457Fu || st[4] != 1 || st[5] != 1 || *(u16 *)(st + 18) != 8) goto out;
        u32 entry = *(u32 *)(st + 24), phoff = *(u32 *)(st + 28); u32 phn = *(u16 *)(st + 44), phs = *(u16 *)(st + 42), nseg = 0;
        if (phs != 32 || phn == 0 || phn > 16 || phoff + phn * 32 > size) goto out;
        for (u32 k = 0; k < phn; k++) {
            u32 *ph = (u32 *)(st + phoff + 32 * k);
            if (ph[0] != 1) continue;                                   /* PT_LOAD */
            u32 off = ph[1], va = ph[2], fs = ph[4], ms = ph[5];
            if (ms < fs || off + fs > size || va < 0x100000 || va + ms > 0x1F00000 || nseg >= SEG_MAX) goto out;
            if (va < STUB + 0x1000 && va + ms > STUB) goto out;
            if (va < STAGE + size && va + ms > STAGE) goto out;
            blk[5 + 4 * nseg] = STAGE + off; blk[6 + 4 * nseg] = va; blk[7 + 4 * nseg] = fs; blk[8 + 4 * nseg] = ms; nseg++;
        }
        if (!nseg || entry < 0x100000 || entry >= 0x1F00000) goto out;
        blk[0] = entry; blk[1] = 0; blk[2] = 2; blk[3] = STUB + 0x300; blk[4] = nseg;          /* ExecPS2 gets gp 0: the new program's start-up sets its own */
        { char t2[96]; int m = snprintf(t2, sizeof t2, "%u %08x %s\n%d\n", size, crc, name, tries + 1); if (put_small(UD "HOST.TXT", t2, m) < 0) goto out; }
    }
    io_umount("pfs1:");
    mounted = 0;
    printf("[host] starting the updated game program %s\n", name);
    quiesce();
    SifExitIopHeap(); SifLoadFileExit(); SifExitRpc();
    _ps2sdk_deinit_timer();                                        /* the library's DelayThread timer handler lives in this program's memory */
    { int o2 = DIntr();                                            /* no interrupt or DMA source reaches code that is about to be replaced (timer 3, the kernel's alarms, stays) */
      for (int k = 0; k < 15; k++) if (k != 12) DisableIntc(k);
      for (int k = 0; k < 10; k++) DisableDmac(k);
      if (o2) EIntr(); }
    { char *as = (char *)(STUB + 0x320); u32 *av = (u32 *)(STUB + 0x300);          /* argv for the new program: outside everything it loads */
      strcpy(as, g_self_path); strcpy(as + 0x60, "chained"); av[0] = (u32)as; av[1] = (u32)as + 0x60; av[2] = 0; }
    memcpy((void *)(STUB + 0x100), (void *)blk, sizeof blk);
    memcpy((void *)(STUB + 0x400), (void *)chain_stub_start, (u32)chain_stub_end - (u32)chain_stub_start);
    FlushCache(0); FlushCache(2);
    ((void (*)(void *))(STUB + 0x400))((void *)(STUB + 0x100));
out:
    if (mounted) io_umount("pfs1:");
}

#endif /* NETDIAG */
