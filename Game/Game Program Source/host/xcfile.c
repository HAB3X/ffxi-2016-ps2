/* xcfile.c (b50_pack / b53_perf, v4) - transparent decompression of XCZ3-packed game files inside the host's file-service slots.
   v4 (6 Oct 2026): which files are packed is told by an INDEX file next to the tables, image/ffxi/XCINDEX.DAT, instead of
   PFS inode tags, so a drive written by Square Enix's installer (which cannot set inode tags) works too:
       u32 'XCIX' | u32 n | n x { u32 key, u32 orig }   sorted by key & 0xFFFFF
       key = (packed size & 0xFFF) << 20 | set << 16 | dir << 7 | file      (ROM = set 1, ROMn = set n)
   A file counts as packed only when its path is in the index AND its real size matches the index (low 12 bits, and smaller
   than the original): a file that was later replaced by a plain copy is read as it is.
   951 getstat: st_size := orig for packed files.  938 open: every open of a packed file is registered (also opens without a
   getstat first - v3 missed those: ROM/2/126.DAT at a zone change).  940 read: whole read -> streamed read into the buffer tail
   + in-place decode by a decoder thread; other reads -> block-range decode.  942 lseek: virtual position.  939 close: forget.
   v5 (6 Oct 2026 installer): optional CONTAINER layout - every game folder ROMn/<dir>/ may be one file ROMn/<dir>.PAK
   (far fewer files to create when installing: ~1,050 instead of ~44,000). image/ffxi/XCPACK.DAT says which folders are packs:
       u32 'XCPK' | u32 1 | u8 map[16][64]   bit (dir & 7) of map[set][dir >> 3] = ROMn/<dir>.PAK exists
   A pack: u32 'XCP1' | u32 128 | 128 x { u32 loc, u32 stored size, u32 original size }, then the files' bytes (each stored exactly
   like the per-file layout: XCZ3-packed when stored < original, else plain). loc = chunk << 24 | offset in that chunk file;
   chunk 0 = ROMn/<dir>.PAK (holds the header), chunk k = ROMn/<dir>_k.PAK (chunks stay < 6 MB so Square Enix's installer can copy
   each one as a plain record); loc 0 = no such file; loc 0xFFFFFFFF = the file is a normal file at its usual path.
   getstat/open of ROMn/<dir>/<file>.DAT in a pack folder: the pack is opened for real, the file is a window into it (all reads and
   seeks of that fd are served here). Pack headers are cached (32, in the index memory: a pack drive has no XCINDEX).
   Index, scratch and decoder stack live in .xcmem (NOLOAD, between the lifted kernel and the game program, see host.ld). */
#include <tamtypes.h>
#include <string.h>
#include <kernel.h>
#include "host.h"
#include "xc.c"
typedef u64 (*svc8x)(u64, u64, u64, u64, u64, u64, u64, u64);
extern volatile u32 g_real[];
#define XC_IDXMAX 16384
#define XCMEM __attribute__((section(".xcmem"), aligned(64)))
u8 g_xc_scratch[XC_SCRATCH] XCMEM;
static u8 dstack[8192] XCMEM;
u32 g_xc_idx[2 * XC_IDXMAX] XCMEM;                 /* {key, orig} pairs */
volatile u32 g_xc_idxn = 0; volatile int g_xc_idx_state = 0;   /* 0 not loaded yet, 1 loaded, -1 no index (no packed files) */
volatile u32 g_xc_idx_sum = 0;                      /* additive checksum of the loaded index (tests compare it over PINE at the end of a run) */
typedef struct { int fd; u32 orig, fsize, pos, bs, nb, base, packed; } XcFd;
static XcFd fds[16];
volatile u32 g_xc_stats[10];   /* 0 getstat packed, 1 opens packed, 2 whole reads, 3 range reads, 4 errors, 5 bytes out (KB), 6 whole-read wall cycles>>10, 7 decoder-thread cycles>>10, 8 index entries, 9 range-read wall cycles>>10 */
volatile u32 g_xc_lasterr[4];
static struct { u32 h, fsz; } lst[4]; static u32 lstn;
static u32 phash(const char *p) { u32 h = 2166136261u; while (*p) h = (h ^ (u8)*p++) * 16777619u; return h; }
static u64 R(int slot, u64 a, u64 b, u64 c) { return ((svc8x)g_real[slot])(a, b, c, 0, 0, 0, 0, 0); }
static XcFd *find(int fd) { for (int i = 0; i < 16; i++) if (fds[i].orig && fds[i].fd == fd) return &fds[i]; return 0; }
static XcFd *new_fd(int fd) { for (int i = 0; i < 16; i++) if (!fds[i].orig || fds[i].fd == fd) return &fds[i]; return 0; }
static inline u32 cyc(void) { u32 c; __asm__ volatile("mfc0 %0, $9" : "=r"(c)); return c; }

/* "..../ROM<set>/<dir>/<file>.DAT" -> set<<16 | dir<<7 | file, or 0; *pre = length of the part before "ROM" */
static u32 num(const char *p, int *k) { u32 v = 0; while (p[*k] >= '0' && p[*k] <= '9') { v = v * 10 + (u32)(p[*k] - '0'); (*k)++; } return v; }
static u32 path_code(const char *p, int *pre)
{
    int n, k;
    if ((u32)p < 0x100000 || (u32)p >= 0x2000000) return 0;
    for (n = 0; n < 120 && p[n] >= 0x20 && p[n] < 0x7f; n++) { }
    if (n < 12 || p[n - 4] != '.' || p[n - 3] != 'D' || p[n - 2] != 'A' || p[n - 1] != 'T') return 0;
    for (k = n - 5; k > 0; k--) if (p[k - 1] == '/' && p[k] == 'R' && p[k + 1] == 'O' && p[k + 2] == 'M') break;
    if (k <= 0) return 0;
    int j = k + 3; u32 set = 1, dir, file;
    if (p[j] >= '0' && p[j] <= '9') set = num(p, &j);
    if (p[j++] != '/') return 0;
    dir = num(p, &j); if (p[j++] != '/') return 0;
    file = num(p, &j); if (p[j] != '.' || set < 1 || set > 15 || file > 127 || dir > 511) return 0;
    if (pre) *pre = k;
    return (set << 16) | (dir << 7) | file;
}
static void idx_load(const char *p, int pre)
{
    char ip[128]; int fd, k;
    g_xc_idx_state = -1;
    if (pre <= 0 || pre > 100) return;
    memcpy(ip, p, pre); memcpy(ip + pre, "XCINDEX.DAT", 12);
    fd = (int)R(938, (u32)ip, 1, 0);
    if (fd < 0) { hlog(9, 0, 0, 0, 0, 0, 0, "XC: no index (plain drive)", 0, 0); return; }
    u32 h[2];
    if ((int)R(940, fd, (u32)h, 8) == 8 && h[0] == 0x58494358u && h[1] <= XC_IDXMAX &&
        (int)R(940, fd, (u32)g_xc_idx, 8 * h[1]) == (int)(8 * h[1])) {
        u32 s = 0; for (k = 0; k < (int)(2 * h[1]); k++) s += g_xc_idx[k];
        g_xc_idxn = h[1]; g_xc_idx_sum = s; g_xc_idx_state = 1; g_xc_stats[8] = h[1];
        hlog(9, h[1], s, 0, 0, 0, 0, "XC: index loaded entries/sum:", 0, 0);
    } else hlog(9, h[0], h[1], 0, 0, 0, 0, "XC: BAD index, packed files disabled:", 0, 0);
    R(939, fd, 0, 0);
}
static int idx_find(u32 code)
{
    int lo = 0, hi = (int)g_xc_idxn - 1;
    while (lo <= hi) {
        int m = (lo + hi) >> 1; u32 k = g_xc_idx[2 * m] & 0xFFFFF;
        if (k == code) return m;
        if (k < code) lo = m + 1; else hi = m - 1;
    }
    return -1;
}
/* -> orig size of a packed file, or 0. fsize = the file's real size on the drive */
static u32 idx_orig(u32 code, u32 fsize)
{
    int m = idx_find(code); if (m < 0) return 0;
    u32 o = g_xc_idx[2 * m + 1];
    return ((g_xc_idx[2 * m] >> 20) == (fsize & 0xFFF) && fsize < o) ? o : 0;
}
static u32 lookup(const char *p, u32 fsize)
{
    int pre = 0; u32 c = path_code(p, &pre);
    if (!c) return 0;
    if (g_xc_idx_state == 0) idx_load(p, pre);
    return g_xc_idx_state > 0 ? idx_orig(c, fsize) : 0;
}

/* ---- v5 container layout ---- */
volatile int g_xc_pak_state = 0;                 /* 0 unknown, 1 packs present, -1 none */
static u8 pakmap[16][64] XCMEM;                     /* filled completely by pak_load before use */
static char pak_pre[104]; static int pak_prel;
typedef struct { u32 off, stored, orig; } PakEnt;
typedef struct { u32 key, lru; PakEnt e[128]; } PakHdr;
#define PAKN 32
#define pakcache ((PakHdr *)g_xc_idx)               /* 32 x 1544 B: the index memory (a pack drive has no XCINDEX) */
static u32 pak_tick;
volatile u32 g_xc_pak_stats[4];                     /* 0 header loads, 1 header hits, 2 pack opens, 3 pack getstats */
static void pak_load(const char *p, int pre)
{
    char ip[128]; int fd;
    g_xc_pak_state = -1;
    if (pre <= 0 || pre > 100) return;
    memcpy(ip, p, pre); memcpy(ip + pre, "XCPACK.DAT", 11);
    fd = (int)R(938, (u32)ip, 1, 0);
    if (fd < 0) return;
    u32 h[2];
    if ((int)R(940, fd, (u32)h, 8) == 8 && h[0] == 0x4B504358u && (int)R(940, fd, (u32)pakmap, sizeof pakmap) == (int)sizeof pakmap) {
        memcpy(pak_pre, p, pre); pak_prel = pre; pak_pre[pre] = 0;
        g_xc_pak_state = 1; g_xc_idx_state = -1;    /* packs replace the per-file index */
        memset(g_xc_idx, 0, PAKN * sizeof(PakHdr));
        hlog(9, 0, 0, 0, 0, 0, 0, "XC: container layout (XCPACK.DAT)", 0, 0);
    }
    R(939, fd, 0, 0);
}
static char *pak_path_k(char *o, u32 code, u32 k)  /* "<prefix>ROM[n]/<dir>.PAK" (chunk 0) or "<prefix>ROM[n]/<dir>_<k>.PAK" */
{
    u32 set = code >> 16, dir = (code >> 7) & 511; char *q = o, t[8]; int n;
    memcpy(q, pak_pre, pak_prel); q += pak_prel; memcpy(q, "ROM", 3); q += 3;
    if (set > 1) { if (set >= 10) *q++ = '0' + set / 10; *q++ = '0' + set % 10; }
    *q++ = '/'; n = 0; do { t[n++] = '0' + dir % 10; dir /= 10; } while (dir);
    while (n) *q++ = t[--n];
    if (k) { *q++ = '_'; n = 0; do { t[n++] = '0' + k % 10; k /= 10; } while (k); while (n) *q++ = t[--n]; }
    memcpy(q, ".PAK", 5); return o;
}
#define pak_path(o, code) pak_path_k(o, code, 0)
static int in_pak(u32 code) { u32 set = code >> 16, dir = (code >> 7) & 511; return set < 16 && (pakmap[set][dir >> 3] >> (dir & 7)) & 1; }
static PakEnt *pak_entry(u32 code)                  /* header from the cache, or read it; NULL on error */
{
    u32 key = (code >> 7) + 1, i, lru = 0xFFFFFFFFu, victim = 0;
    for (i = 0; i < PAKN; i++) if (pakcache[i].key == key) { pakcache[i].lru = ++pak_tick; g_xc_pak_stats[1]++; return &pakcache[i].e[code & 127]; }
    for (i = 0; i < PAKN; i++) if (pakcache[i].lru < lru) { lru = pakcache[i].lru; victim = i; }
    char pp[128]; int fd = (int)R(938, (u32)pak_path(pp, code), 1, 0);
    if (fd < 0) return 0;
    u32 h[2]; PakHdr *c = &pakcache[victim]; c->key = 0;
    int ok = (int)R(940, fd, (u32)h, 8) == 8 && h[0] == 0x31504358u && h[1] == 128 && (int)R(940, fd, (u32)c->e, sizeof c->e) == (int)sizeof c->e;
    R(939, fd, 0, 0);
    if (!ok) { hlog(9, h[0], h[1], 0, 0, 0, 0, "XC: bad pack header", pp, 0); return 0; }
    c->key = key; c->lru = ++pak_tick; g_xc_pak_stats[0]++;
    return &c->e[code & 127];
}
/* getstat / open of a file in a pack folder: handled completely here (the per-file path does not exist on a pack drive) */
static int pak_pre_call(u32 idx, u64 *r, u64 *ret)
{
    const char *p = (const char *)(u32)r[1]; int pre; u32 code = path_code(p, &pre);
    if (!code) return 0;
    if (g_xc_pak_state == 0) pak_load(p, pre);
    if (g_xc_pak_state <= 0 || !in_pak(code)) return 0;
    PakEnt *e = pak_entry(code);
    if (!e) { *ret = (u64)(s64)-5; return 1; }
    if (!e->off) { *ret = (u64)(s64)-2; return 1; }            /* no such file: what PFS answers */
    if (e->off == 0xFFFFFFFFu) return 0;                       /* a normal file at its usual path */
    PakEnt en = *e; char pp[128]; pak_path_k(pp, code, en.off >> 24); en.off &= 0xFFFFFF;
    if (idx == 951) {
        u8 *st = (u8 *)(u32)r[2];
        int rr = (int)R(951, (u32)pp, (u32)st, 0);
        if (rr < 0) { *ret = (u64)(s64)rr; return 1; }
        memcpy(st + 8, &en.orig, 4); memset(st + 36, 0, 4);       /* size = the file's original size, hisize 0 */
        g_xc_pak_stats[3]++; *ret = (u64)rr; return 1;
    }
    int fd = (int)R(938, (u32)pp, (u32)r[2], (u32)r[3]);
    if (fd < 0) { *ret = (u64)(s64)fd; return 1; }
    XcFd *f = new_fd(fd);
    if (!f) { R(939, fd, 0, 0); hlog(9, (u32)fd, 0, 0, 0, 0, 0, "XC fd table full fd:", 0, 0); *ret = (u64)(s64)-24; return 1; }
    f->fd = fd; f->orig = en.orig; f->fsize = en.stored; f->pos = 0; f->bs = 0; f->nb = 0; f->base = en.off; f->packed = en.stored < en.orig;
    if (f->packed) g_xc_stats[1]++;
    g_xc_pak_stats[2]++; *ret = (u64)(u32)fd; return 1;
}

/* ---- streamed whole-file read: the calling (game file) thread reads 64 KB chunks while this decoder thread, one priority
   step lower, decodes the blocks that have arrived (in place, just behind the read pointer). ---- */
extern void *_gp;
static int dtid = -1, s_job = -1, s_prog = -1, s_done = -1;
static struct { u8 *dst; const u8 *f; u32 orig, fsize; volatile u32 avail; volatile int res; } J;
static void dwait(void) { WaitSema(s_prog); }
static void dthread(void *a) { (void)a; for (;;) { WaitSema(s_job); u32 t0 = cyc(); J.res = xc_inplace_stream(J.dst, J.orig, J.f, J.fsize, g_xc_scratch, &J.avail, dwait); g_xc_stats[7] += (cyc() - t0) >> 10; SignalSema(s_done); } }
static int dinit(void)
{
    ee_sema_t sm; sm.init_count = 0; sm.max_count = 0x7fff; sm.option = 0; sm.attr = 0;
    s_job = CreateSema(&sm); s_prog = CreateSema(&sm); s_done = CreateSema(&sm);
    ee_thread_t t; t.func = (void *)dthread; t.stack = dstack; t.stack_size = sizeof dstack; t.gp_reg = &_gp;
    t.initial_priority = 126; t.attr = 0; t.option = 0;
    dtid = CreateThread(&t);
    if (s_job < 0 || s_prog < 0 || s_done < 0 || dtid < 0) { dtid = -2; return -1; }
    StartThread(dtid, 0); return 0;
}
static int stream_read(XcFd *f, u8 *buf, u8 *at)
{
    u32 c0 = f->fsize < 65536u ? f->fsize : 65536u, pos;
    if ((int)R(940, f->fd, (u32)at, c0) != (int)c0) return -1;
    u32 nb = rd32(at + 12);
    if (c0 == f->fsize || XC_HDR(nb) + XC_TAILMAX > c0 || dtid == -2 || (dtid == -1 && dinit() < 0)) {   /* small file: plain path */
        pos = c0;
        if (pos < f->fsize && (int)R(940, f->fd, (u32)(at + pos), f->fsize - pos) != (int)(f->fsize - pos)) return -1;
        return xc_inplace_at(buf, f->orig, at, f->fsize, g_xc_scratch);
    }
    ee_thread_status_t st; int me = GetThreadId(), prio = 64;
    if (ReferThreadStatus(me, &st) >= 0) prio = st.current_priority;
    ChangeThreadPriority(dtid, prio < 127 ? prio + 1 : 127);
    while (PollSema(s_prog) >= 0) { }                                   /* drop stale progress signals */
    J.dst = buf; J.f = at; J.orig = f->orig; J.fsize = f->fsize; J.avail = c0; J.res = -1;
    SignalSema(s_job);
    for (pos = c0; pos < f->fsize;) {
        u32 n = f->fsize - pos < 65536u ? f->fsize - pos : 65536u;
        if ((int)R(940, f->fd, (u32)(at + pos), n) != (int)n) { J.avail = 0xFFFFFFFFu; SignalSema(s_prog); WaitSema(s_done); return -1; }
        pos += n; J.avail = pos; SignalSema(s_prog);
    }
    WaitSema(s_done);
    return J.res;
}
/* partial read of [pos, pos+n): the needed block offsets are read in one call, then each record (<= bs+4 bytes) is read and
   decoded through the scratch. */
static int range_read(XcFd *f, u32 pos, u8 *out, u32 n)
{
    u32 done = 0, offs[33];
    if (!f->bs) {                                                         /* first partial read of this open: the header */
        u32 h[4];
        if ((u32)R(942, f->fd, f->base, 0) != f->base || (int)R(940, f->fd, (u32)h, 16) != 16 || h[0] != XC_MAGIC || h[1] != f->orig || h[2] == 0 || h[2] > XC_BS) return -1;
        f->bs = h[2]; f->nb = h[3];
    }
    if (pos >= f->orig) return 0;
    if (n > f->orig - pos) n = f->orig - pos;
    while (done < n) {
        u32 b0 = (pos + done) / f->bs, b1 = (pos + n - 1) / f->bs, cnt;
        if (b1 - b0 + 1 > 32) b1 = b0 + 31;
        cnt = b1 - b0 + 2;
        if ((u32)R(942, f->fd, f->base + 20 + 4 * b0, 0) != f->base + 20 + 4 * b0 || (int)R(940, f->fd, (u32)offs, 4 * cnt) != (int)(4 * cnt)) return -1;
        for (u32 b = b0; b <= b1; b++) {
            u32 p = pos + done, bo = p - b * f->bs, bl = (f->orig - b * f->bs < f->bs) ? f->orig - b * f->bs : f->bs, rl;
            u32 off = offs[b - b0], len = f->bs + 4;
            if (off + len > f->fsize) len = f->fsize - off;
            if ((u32)R(942, f->fd, f->base + off, 0) != f->base + off || (int)R(940, f->fd, (u32)g_xc_scratch, len) != (int)len) return -1;
            u32 rlen = 4 + (rd32(g_xc_scratch) & 0x3fffffff);
            if (rlen > len) return -1;
            u8 *blk = g_xc_scratch + ((rlen + 63) & ~63u);
            if (rd32(g_xc_scratch) >> 31) blk = g_xc_scratch + 4;
            else if (xc_block(g_xc_scratch, g_xc_scratch + rlen, blk, bl, &rl) != (int)bl) return -1;
            u32 k = bl - bo; if (k > n - done) k = n - done;
            memcpy(out + done, blk + bo, k); done += k;
            if (done >= n) break;
        }
    }
    return (int)n;
}
/* before the real call: return 1 if handled (ret set) */
int xc_pre(u32 idx, u64 *r, u64 *ret)
{
    if ((idx == 951 || idx == 938) && g_xc_pak_state >= 0 && pak_pre_call(idx, r, ret)) return 1;
    if (idx == 940) {
        XcFd *f = find((int)r[1]); if (!f) return 0;
        u8 *buf = (u8 *)(u32)r[2]; u32 n = (u32)r[3];
        if (f->pos >= f->orig) { *ret = 0; return 1; }
        u32 t0 = cyc();
        if (!f->packed) {                                          /* plain file inside a pack: a window */
            u32 k = n < f->orig - f->pos ? n : f->orig - f->pos;
            if ((u32)R(942, f->fd, f->base + f->pos, 0) != f->base + f->pos) goto err;
            int g = (int)R(940, f->fd, (u32)buf, k); if (g < 0) { *ret = (u64)(s64)g; return 1; }
            f->pos += (u32)g; *ret = (u32)g; return 1;
        }
        if (f->pos == 0 && n >= f->orig) {
            if ((u32)R(942, f->fd, f->base, 0) != f->base) goto err;
            u8 *at = (u8 *)((u32)(buf + f->orig - f->fsize) & ~63u);           /* 64-byte aligned: Sony's read DMAs straight into it */
            if (at < buf) at = buf + f->orig - f->fsize;
            if (stream_read(f, buf, at) != (int)f->orig) goto err;
            g_xc_stats[6] += (cyc() - t0) >> 10;
            f->pos = f->orig; *ret = f->orig; g_xc_stats[2]++;
        } else {
            int k = range_read(f, f->pos, buf, n);
            if (k < 0) goto err;
            f->pos += (u32)k; *ret = (u32)k; g_xc_stats[3]++; g_xc_stats[9] += (cyc() - t0) >> 10;
        }
        g_xc_stats[5] += (u32)*ret >> 10;
        return 1;
    err:
        g_xc_stats[4]++; g_xc_lasterr[0] = f->orig; g_xc_lasterr[1] = f->fsize; g_xc_lasterr[2] = f->pos; g_xc_lasterr[3] = n;
        hlog(9, f->orig, f->fsize, f->pos, n, 0, 0, "XC decode error orig/fsize/pos/n:", 0, 0);
        *ret = (u64)(s64)-5; return 1;
    }
    if (idx == 942) {
        XcFd *f = find((int)r[1]); if (!f) return 0;
        int off = (int)r[2], wh = (int)r[3]; int np = wh == 0 ? off : wh == 1 ? (int)f->pos + off : (int)f->orig + off;
        if (np < 0 || (u32)np > f->orig) { *ret = (u64)(s64)-22; return 1; }
        f->pos = (u32)np; *ret = (u32)np; return 1;
    }
    if (idx == 939) { XcFd *f = find((int)r[1]); if (f) f->orig = 0; return 0; }
    return 0;
}
/* after the real call */
void xc_post(u32 idx, u64 *r, u64 ret)
{
    if (g_xc_idx_state < 0 || g_xc_pak_state > 0) return;
    if (idx == 951 && (int)ret >= 0) {
        const char *p = (const char *)(u32)r[1]; u8 *st = (u8 *)(u32)r[2]; u32 fsz, orig;
        if ((u32)st < 0x100000 || (u32)st >= 0x2000000) return;
        memcpy(&fsz, st + 8, 4);
        if ((orig = lookup(p, fsz)) != 0) { memcpy(st + 8, &orig, 4); g_xc_stats[0]++; lst[lstn & 3].h = phash(p); lst[lstn & 3].fsz = fsz; lstn++; }
    } else if (idx == 938 && (int)ret >= 0) {
        const char *p = (const char *)(u32)r[1]; int fd = (int)ret;
        int pre; u32 code = path_code(p, &pre); if (!code) return;
        if (g_xc_idx_state == 0) idx_load(p, pre);
        if (g_xc_idx_state <= 0 || idx_find(code) < 0) return;
        int fsz = -1; u32 h = phash(p);
        for (int i = 0; i < 4; i++) if (lst[i].h == h && lst[i].fsz) { fsz = (int)lst[i].fsz; lst[i].fsz = 0; break; }   /* size from the getstat just before */
        if (fsz < 0) {                                                     /* opened without a getstat: real size (SEEK_END), back to 0 */
            fsz = (int)R(942, fd, 0, 2);
            if (fsz <= 0 || (int)R(942, fd, 0, 0) != 0) return;
        }
        u32 orig = lookup(p, (u32)fsz); if (!orig) return;
        for (int i = 0; i < 16; i++) if (!fds[i].orig || fds[i].fd == fd) { fds[i].fd = fd; fds[i].orig = orig; fds[i].fsize = (u32)fsz; fds[i].pos = 0; fds[i].bs = 0; fds[i].nb = 0; fds[i].base = 0; fds[i].packed = 1; g_xc_stats[1]++; return; }
        hlog(9, (u32)ret, 0, 0, 0, 0, 0, "XC fd table full fd:", 0, 0);
    }
}
