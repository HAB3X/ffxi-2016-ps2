/* xc.c - "XCZ3" block-compressed DAT format for the 2016 host. Shared by the Mac packer (-DXC_PACKER, links liblz4)
   and the EE host (decoder only). LOSSLESS: every packed file is decoded back and compared byte for byte at pack time.
   File layout:  u32 magic 'XCZ2' | u32 orig size | u32 block size | u32 nblk | u32 tb | u32 off[nblk+1]
                 then the TAIL records tb..nblk-1 (at most XC_TAILMAX bytes), then records 0..tb-1; each record:
                 u32 len (bit31 raw, bit30 deflate, else LZ4) | len bytes; off[] holds each record's file offset.
   Whole-file read (the game's usual getstat + open + read(all) + close): the file is read into the TAIL of the game's own
   buffer (dst + orig - fsize). Records tb..nblk-1 (at most XC_TAILMAX bytes) are first copied to a small scratch, then
   blocks 0..tb-1 are decoded forward in place and blocks tb.. from the scratch. The packer proves every file in-place
   safe by running exactly this code on the Mac and comparing with the original.
   Partial reads (item tables, d_msg tables, some texture banks): xc_range() decodes only the touched blocks through a
   scratch of XC_SCRATCH bytes. */
#include <stdint.h>
#include <string.h>
#ifndef _EE
typedef uint8_t u8; typedef uint16_t u16; typedef uint32_t u32;
#endif
#define XC_MAGIC 0x335A4358u   /* "XCZ3" */
#define XC_HDR(nblk) (20u + 4u * ((nblk) + 1u))
#define XC_BS 16384u
#define XC_TAILMAX 16384u
#define XC_SCRATCH (2u * XC_BS + 64u)   /* >= XC_TAILMAX and >= one record + one decoded block */

static inline u32 rd32(const u8 *p) { u32 v; __builtin_memcpy(&v, p, 4); return v; }

/* LZ4 block decode, exact (never writes past op+olen, never reads past ip+ilen). Forward copies only. -1 on bad data. */
static inline void cp8(u8 *d, const u8 *s) { uint64_t t; __builtin_memcpy(&t, s, 8); __builtin_memcpy(d, &t, 8); }
static int lz4_dec(const u8 *ip, u32 ilen, u8 *op, u32 olen)
{
    const u8 *ie = ip + ilen; u8 *o0 = op, *oe = op + olen;
    while (ip < ie) {
        u32 tok = *ip++, L = tok >> 4, M;
        /* fast path: short literals copied 16 bytes at once when there is room before the output end and before the unread
           input (in place the input lies above the output; with a separate input buffer below, ip < op) */
        if (L < 15 && oe - op >= 32 && ie - ip >= 18 && (ip < op || ip - op >= 32)) {
            cp8(op, ip); cp8(op + 8, ip + 8); op += L; ip += L;
        } else {
            if (L == 15) { u32 s; do { if (ip >= ie) return -1; s = *ip++; L += s; } while (s == 255); }
            if ((u32)(ie - ip) < L || (u32)(oe - op) < L) return -1;
            while (L >= 8) { cp8(op, ip); ip += 8; op += 8; L -= 8; }
            while (L--) *op++ = *ip++;
        }
        if (ip >= ie) break;                                   /* last sequence: literals only */
        if (ie - ip < 2) return -1;
        u32 off = ip[0] | (ip[1] << 8); ip += 2;
        if (!off || (u32)(op - o0) < off) return -1;
        M = tok & 15;
        const u8 *mp = op - off;
        if (M < 15 && off >= 8 && oe - op >= 32 && (ip < op || ip - op >= 32)) {   /* short match, no overlap: 3 x 8 bytes */
            cp8(op, mp); cp8(op + 8, mp + 8); cp8(op + 16, mp + 16); op += M + 4; continue;
        }
        if (M == 15) { u32 s; do { if (ip >= ie) return -1; s = *ip++; M += s; } while (s == 255); }
        M += 4;
        if ((u32)(oe - op) < M) return -1;
        if (off < 8 && M >= 16) {                              /* short period (e.g. zero padding): first d bytes one by one, */
            u32 d = off * ((8 + off - 1) / off), k;              /* then 8-byte copies from distance d = a multiple of the period >= 8 */
            for (k = 0; k < d; k++) op[k] = mp[k];
            op += d; M -= d; mp = op - d;
        }
        if (mp + 8 <= op) { while (M >= 8) { cp8(op, mp); mp += 8; op += 8; M -= 8; } }
        while (M--) *op++ = *mp++;
    }
    return (int)(op - o0);
}


/* variant 2: one combined room check per sequence; common case = short literal run + short non-overlapping match */
#define LIKELY(x) __builtin_expect(!!(x), 1)
static int lz4_dec2(const u8 *ip, u32 ilen, u8 *op, u32 olen)
{
    const u8 *ie = ip + ilen; u8 *o0 = op, *oe = op + olen;
    const u8 *ifast = ilen > 20 ? ie - 20 : ip; u8 *ofast = olen > 48 ? oe - 48 : op;
    while (ip < ie) {
        u32 tok = *ip++, L = tok >> 4, M = tok & 15;
        if (LIKELY(L < 15 && M < 15 && ip < ifast && op < ofast && (ip < op || ip - op >= 64))) {
            cp8(op, ip); cp8(op + 8, ip + 8); op += L; ip += L;
            u32 off = ip[0] | (ip[1] << 8); ip += 2;
            const u8 *mp = op - off;
            if (LIKELY(off >= 8 && (u32)(op - o0) >= off)) { cp8(op, mp); cp8(op + 8, mp + 8); cp8(op + 16, mp + 16); op += M + 4; continue; }
            if (!off || (u32)(op - o0) < off) return -1;
            M += 4; while (M--) *op++ = *mp++;
            continue;
        }
        if (L == 15) { u32 s; do { if (ip >= ie) return -1; s = *ip++; L += s; } while (s == 255); }
        if ((u32)(ie - ip) < L || (u32)(oe - op) < L) return -1;
        while (L >= 8) { cp8(op, ip); ip += 8; op += 8; L -= 8; }
        while (L--) *op++ = *ip++;
        if (ip >= ie) break;
        if (ie - ip < 2) return -1;
        u32 off = ip[0] | (ip[1] << 8); ip += 2;
        if (!off || (u32)(op - o0) < off) return -1;
        const u8 *mp = op - off;
        if (M == 15) { u32 s; do { if (ip >= ie) return -1; s = *ip++; M += s; } while (s == 255); }
        M += 4;
        if ((u32)(oe - op) < M) return -1;
        if (off < 8 && M >= 16) { u32 d = off * ((8 + off - 1) / off), k; for (k = 0; k < d; k++) op[k] = mp[k]; op += d; M -= d; mp = op - d; }
        if (mp + 8 <= op) { while (M >= 8) { cp8(op, mp); mp += 8; op += 8; M -= 8; } }
        while (M--) *op++ = *mp++;
    }
    return (int)(op - o0);
}
int (*xc_lz4)(const u8 *, u32, u8 *, u32) = lz4_dec2;
void xc_use_dec(int v) { xc_lz4 = v == 2 ? lz4_dec2 : lz4_dec; }

/* ---- raw DEFLATE (RFC 1951) decoder: 10-bit first-level tables, bit-serial fallback for longer codes. Exact bounds. ---- */
typedef struct { u16 cnt[16], sym[288]; u16 fast[1024]; } XHuff;   /* fast[]: (len<<9)|sym, 0 = slow path */
static int xh_build(XHuff *h, const u8 *len, int n)
{
    u16 offs[16]; int i;
    memset(h->cnt, 0, sizeof h->cnt);
    for (i = 0; i < n; i++) h->cnt[len[i]]++;
    h->cnt[0] = 0; offs[1] = 0;
    for (i = 1; i < 15; i++) offs[i + 1] = offs[i] + h->cnt[i];
    for (i = 0; i < n; i++) if (len[i]) h->sym[offs[len[i]]++] = (u16)i;
    memset(h->fast, 0, sizeof h->fast);
    {   int code = 0, k = 0; u32 l;
        for (l = 1; l <= 10; l++) {
            for (u32 c = 0; c < h->cnt[l]; c++, code++, k++) {
                u32 rev = 0, x = (u32)code; for (u32 b = 0; b < l; b++) { rev = (rev << 1) | (x & 1); x >>= 1; }
                for (u32 f = rev; f < 1024; f += 1u << l) h->fast[f] = (u16)((l << 9) | h->sym[k]);
            }
            code <<= 1;
        }
    }
    return 0;
}
typedef struct { const u8 *p, *e; u32 bb; int bc; } XBits;
static inline void xb_fill(XBits *b) { while (b->bc <= 24) { b->bb |= (u32)(b->p < b->e ? *b->p : 0) << b->bc; b->p++; b->bc += 8; } }
static inline u32 xb_get(XBits *b, int n) { xb_fill(b); u32 v = b->bb & ((1u << n) - 1); b->bb >>= n; b->bc -= n; return v; }
static int xh_dec(XBits *b, const XHuff *h)
{
    xb_fill(b);
    u32 f = h->fast[b->bb & 1023];
    if (f) { b->bb >>= f >> 9; b->bc -= f >> 9; return f & 511; }
    int code = 0, first = 0, index = 0;
    for (int l = 1; l < 16; l++) {
        code |= (int)xb_get(b, 1); int c = h->cnt[l];
        if (code - c < first) return h->sym[index + (code - first)];
        index += c; first += c; first <<= 1; code <<= 1;
    }
    return -1;
}
static const u16 XLB[29] = {3,4,5,6,7,8,9,10,11,13,15,17,19,23,27,31,35,43,51,59,67,83,99,115,131,163,195,227,258};
static const u8  XLE[29] = {0,0,0,0,0,0,0,0,1,1,1,1,2,2,2,2,3,3,3,3,4,4,4,4,5,5,5,5,0};
static const u16 XDB[30] = {1,2,3,4,5,7,9,13,17,25,33,49,65,97,129,193,257,385,513,769,1025,1537,2049,3073,4097,6145,8193,12289,16385,24577};
static const u8  XDE[30] = {0,0,0,0,1,1,2,2,3,3,4,4,5,5,6,6,7,7,8,8,9,9,10,10,11,11,12,12,13,13};
static XHuff xh_l, xh_d;                  /* 2 x 2.6 KB; the host's file reads are serialised (one game file thread) */
static int inflate_raw(const u8 *ip, u32 ilen, u8 *op, u32 olen)
{
    XBits b = { ip, ip + ilen, 0, 0 }; u8 *o0 = op, *oe = op + olen; int last;
    do {
        last = (int)xb_get(&b, 1); int type = (int)xb_get(&b, 2);
        if (type == 0) {
            b.bb >>= b.bc & 7; b.bc -= b.bc & 7;                  /* to a byte boundary; unread whole bytes go back */
            while (b.bc >= 8) { b.p--; b.bc -= 8; } b.bb = 0; b.bc = 0;
            if (b.e - b.p < 4) return -1;
            u32 n = b.p[0] | (b.p[1] << 8); b.p += 4;
            if ((u32)(b.e - b.p) < n || (u32)(oe - op) < n) return -1;
            while (n--) *op++ = *b.p++;
            continue;
        }
        if (type == 1) {
            static u8 fl[320]; int i;
            for (i = 0; i < 144; i++) fl[i] = 8; for (; i < 256; i++) fl[i] = 9; for (; i < 280; i++) fl[i] = 7; for (; i < 288; i++) fl[i] = 8;
            for (i = 0; i < 30; i++) fl[288 + i] = 5;
            xh_build(&xh_l, fl, 288); xh_build(&xh_d, fl + 288, 30);
        } else if (type == 2) {
            static const u8 ord[19] = {16,17,18,0,8,7,9,6,10,5,11,4,12,3,13,2,14,1,15};
            u8 ln[320]; int hl = (int)xb_get(&b, 5) + 257, hd = (int)xb_get(&b, 5) + 1, hc = (int)xb_get(&b, 4) + 4, i;
            if (hl > 286 || hd > 30) return -1;
            memset(ln, 0, 19); for (i = 0; i < hc; i++) ln[ord[i]] = (u8)xb_get(&b, 3);
            xh_build(&xh_l, ln, 19);
            for (i = 0; i < hl + hd;) {
                int s = xh_dec(&b, &xh_l), r = 0, v = 0;
                if (s < 0) return -1;
                if (s < 16) { ln[i++] = (u8)s; continue; }
                if (s == 16) { if (!i) return -1; v = ln[i - 1]; r = 3 + (int)xb_get(&b, 2); }
                else if (s == 17) r = 3 + (int)xb_get(&b, 3); else r = 11 + (int)xb_get(&b, 7);
                if (i + r > hl + hd) return -1;
                while (r--) ln[i++] = (u8)v;
            }
            xh_build(&xh_l, ln, hl); xh_build(&xh_d, ln + hl, hd);
        } else return -1;
        for (;;) {
            int s = xh_dec(&b, &xh_l);
            if (s < 256) { if (s < 0 || op >= oe) return -1; *op++ = (u8)s; continue; }
            if (s == 256) break;
            s -= 257; if (s >= 29) return -1;
            u32 len = XLB[s] + xb_get(&b, XLE[s]);
            int ds = xh_dec(&b, &xh_d); if (ds < 0 || ds >= 30) return -1;
            u32 dist = XDB[ds] + xb_get(&b, XDE[ds]);
            if ((u32)(op - o0) < dist || (u32)(oe - op) < len) return -1;
            const u8 *mp = op - dist;
            if (dist >= 8) { while (len >= 8) { uint64_t t; __builtin_memcpy(&t, mp, 8); __builtin_memcpy(op, &t, 8); mp += 8; op += 8; len -= 8; } }
            while (len--) *op++ = *mp++;
        }
        if (b.p - (int)(b.bc / 8) > b.e) return -1;
    } while (!last);
    return (int)(op - o0);
}

static int xc_block(const u8 *rec, const u8 *end, u8 *out, u32 bl, u32 *reclen)
{
    if (rec > end || end - rec < 4) return -1;
    u32 len = rd32(rec), raw = len >> 31, defl = (len >> 30) & 1; len &= 0x3fffffff;
    if (len > (u32)(end - rec) - 4 || len > bl + 16) return -1;
    *reclen = 4 + len;
    if (raw) {                                                  /* forward copy; in place the source is at or above the target */
        if (len != bl) return -1;
        const u8 *sp = rec + 4; u32 k = 0;
        if (sp == out) return (int)len;
        if (sp < out || sp - out >= 8) for (; k + 8 <= len; k += 8) cp8(out + k, sp + k);
        for (; k < len; k++) out[k] = sp[k];
        return (int)len;
    }
    return defl ? inflate_raw(rec + 4, len, out, bl) : xc_lz4(rec + 4, len, out, bl);
}

int xc_is(const u8 *h) { return rd32(h) == XC_MAGIC; }

/* dst = game buffer of size orig; the whole packed file (fsize bytes) has been read to dst + orig - fsize */
/* f = where the packed file was read: dst + orig - fsize, or up to 63 bytes lower (64-byte aligned for a fast DMA read).
   Streaming: when avail != 0 the file is still arriving; *avail = bytes of it present at f so far, wait() blocks until more
   arrive. The tail records (right after the header) must be present before the call. */
typedef void (*xc_wait_fn)(void);
int xc_inplace_stream(u8 *dst, u32 orig, const u8 *f, u32 fsize, u8 *scratch, volatile u32 *avail, xc_wait_fn wait)
{
    if (fsize < 24 || rd32(f) != XC_MAGIC || rd32(f + 4) != orig) return -1;
    u32 bs = rd32(f + 8), nb = rd32(f + 12), tb = rd32(f + 16), o, h = XC_HDR(nb);
    if (tb > nb || h > fsize) return -1;
    u32 tstart = h, tlen = (tb < nb ? rd32(f + 20 + 4 * tb) : h) - h;     /* tail records sit right after the header */
    const u8 *ip;
    if (tb < nb) {
        u32 last = 0;                                                     /* tail = records tb..nb-1, contiguous from h */
        for (u32 b = tb; b < nb; b++) { u32 ob = rd32(f + 20 + 4 * b); if (ob < h) return -1; if (ob > last) last = ob; }
        tlen = 0; { const u8 *q = f + tstart; for (u32 b = tb; b < nb; b++) { if ((u32)(q - f) + 4 > fsize) return -1; u32 l = 4 + (rd32(q) & 0x3fffffff); q += l; tlen += l; } }
        if (tlen > XC_TAILMAX || tstart + tlen > fsize) return -1;
        memcpy(scratch, f + tstart, tlen);                               /* out of harm's way before any output is written */
    } else tlen = 0;
    ip = f + tstart + tlen;                                               /* records 0..tb-1 follow the tail */
    const u8 *fend = f + fsize, *send = scratch + tlen, *sp = scratch;
    o = 0;
    for (u32 b = 0; b < nb; b++) {
        u32 bl = (orig - o < bs) ? orig - o : bs, rl;
        if (b < tb) {
            if (avail) {                                                  /* wait until this record has fully arrived */
                for (;;) { u32 a = *avail; if (a == 0xFFFFFFFFu) return -1; if ((u32)(ip - f) + 4 <= a && (u32)(ip - f) + 4 + (rd32(ip) & 0x3fffffff) <= a) break; if (a >= fsize) break; wait(); }
            }
            if (xc_block(ip, fend, dst + o, bl, &rl) != (int)bl) return -1;
            ip += rl;
        } else {
            if (xc_block(sp, send, dst + o, bl, &rl) != (int)bl) return -1;
            sp += rl;
        }
        o += bl;
    }
    return o == orig ? (int)orig : -1;
}
int xc_inplace_at(u8 *dst, u32 orig, const u8 *f, u32 fsize, u8 *scratch) { return xc_inplace_stream(dst, orig, f, fsize, scratch, 0, 0); }
int xc_inplace(u8 *dst, u32 orig, u32 fsize, u8 *scratch) { return xc_inplace_at(dst, orig, dst + orig - fsize, fsize, scratch); }

/* partial read: rd(ctx, file_off, buf, n) reads n bytes of the packed file at file_off; scratch >= XC_SCRATCH */
typedef int (*xc_reader)(void *ctx, u32 off, u8 *buf, u32 n);
int xc_range(xc_reader rd, void *ctx, u32 pos, u8 *out, u32 n, u8 *scratch)
{
    u8 h[16], ob[8]; u32 done = 0;
    if (rd(ctx, 0, h, 16) != 16 || rd32(h) != XC_MAGIC) return -1;
    u32 orig = rd32(h + 4), bs = rd32(h + 8);
    if (bs > XC_BS || pos >= orig) return pos >= orig ? 0 : -1;
    if (n > orig - pos) n = orig - pos;
    while (done < n) {
        u32 p = pos + done, b = p / bs, bo = p % bs, bl = (orig - b * bs < bs) ? orig - b * bs : bs;
        if (rd(ctx, 20 + 4 * b, ob, 4) != 4) return -1;
        u32 off = rd32(ob), rlen;
        int got = rd(ctx, off, scratch, bs + 4);                 /* the record is at most bs + 4 bytes; a short read at EOF is fine */
        if (got < 4) return -1;
        rlen = 4 + (rd32(scratch) & 0x3fffffff);
        if (rlen > (u32)got) return -1;
        u8 *blk = scratch + ((rlen + 15) & ~15u);
        if (rd32(scratch) >> 31) blk = scratch + 4;
        else { u32 rl; if (xc_block(scratch, scratch + rlen, blk, bl, &rl) != (int)bl) return -1; }
        u32 k = bl - bo; if (k > n - done) k = n - done;
        memcpy(out + done, blk + bo, k); done += k;
    }
    return (int)n;
}

#ifdef XC_PACKER
#include <stdlib.h>
#include <lz4.h>
#include <lz4hc.h>
#include <zlib.h>
#include <math.h>
static int defl_block(const u8 *in, u32 n, u8 *out, u32 cap)
{
    z_stream z; memset(&z, 0, sizeof z);
    if (deflateInit2(&z, 9, Z_DEFLATED, -15, 9, Z_DEFAULT_STRATEGY) != Z_OK) return -1;
    z.next_in = (Bytef *)in; z.avail_in = n; z.next_out = out; z.avail_out = cap;
    int r = deflate(&z, Z_FINISH); int sz = (int)z.total_out; deflateEnd(&z);
    return r == Z_STREAM_END ? sz : -1;
}
#define XC_HZ 294912000.0
#define XCM_MARGIN 0.75                     /* real EE assumed 25 % slower than PCSX2's cycle count */
static double xcm[4] = { 74.4, 1.91, 2.37, 1.0 };   /* cycles per LZ4 sequence, literal byte, match byte (decoder v2, runs/bench4 fit), raw-copied byte (assumed) */
double stats_cost[2];
void xc_set_model(double seq, double lit, double mat, double rawb) { xcm[0] = seq; xcm[1] = lit; xcm[2] = mat; xcm[3] = rawb; }
double xc_last_cost(int which) { return stats_cost[which ? 1 : 0]; }
static void lz4_feats(const u8 *p, u32 n, u32 *f)
{
    const u8 *e = p + n; f[0] = f[1] = f[2] = 0;
    while (p < e) {
        u32 t = *p++, L = t >> 4, M; if (L == 15) { u32 s; do { s = *p++; L += s; } while (s == 255); }
        p += L; f[1] += L; f[0]++;
        if (p >= e) break;
        p += 2; M = t & 15; if (M == 15) { u32 s; do { s = *p++; M += s; } while (s == 255); }
        f[2] += M + 4;
    }
}
/* per-block codec choice. policy 0 = smallest; 2 = LZ4 only, 3 = deflate only (benchmarks);
   4 = sequential load model: read(packed) + decode < read(raw);
   5 = streamed load model (host reads chunk k+1 while a decoder thread decodes chunk k):
       max(read(packed) + decode(last chunk), read(first chunk) + decode(all)) < read(raw).
   Decode cost from the measured EE model xcm[] (cycles per LZ4 sequence / literal byte / match byte / raw-copied byte),
   with a 25 % margin for real hardware. stats[0..2] = blocks raw / lz4 / deflate.
   Returns packed size (> 0), 0 = not worth it, -1 = no in-place-safe layout. Every result is decoded and compared. */
#define XC_CHUNK 65536u
static int layout(const u8 *in, u32 n, u8 *out, u32 nb, u32 bs, const u8 *pick, const u32 *clen, u8 *const *cdat, u32 tb)
{
    u32 pos = XC_HDR(nb), v;
    for (u32 pass = 0; pass < 2; pass++)
        for (u32 b = pass ? 0 : tb; b < (pass ? tb : nb); b++) {
            u32 bl = (n - b * bs < bs) ? n - b * bs : bs; memcpy(out + 20 + 4 * b, &pos, 4);
            if (!pick[b]) { v = bl | 0x80000000u; memcpy(out + pos, &v, 4); memcpy(out + pos + 4, in + b * bs, bl); pos += 4 + bl; }
            else { v = clen[b] | (pick[b] == 2 ? 0x40000000u : 0); memcpy(out + pos, &v, 4); memcpy(out + pos + 4, cdat[b], clen[b]); pos += 4 + clen[b]; }
        }
    memcpy(out + 20 + 4 * nb, &pos, 4);
    u32 h[5] = { XC_MAGIC, n, bs, nb, tb }; memcpy(out, h, 20);
    return (int)pos;
}
static int proven(const u8 *in, u32 n, const u8 *out, u32 pos, u8 *t, u8 *sc)
{
    for (u32 sh = 0; sh < 64; sh += 63) {                              /* the host may read the file up to 63 bytes lower */
        if (n - pos < sh) return 0;
        memset(t, 0xA5, n); memcpy(t + n - pos - sh, out, pos); memset(sc, 0x5A, XC_SCRATCH);
        if (xc_inplace_at(t, n, t + n - pos - sh, pos, sc) != (int)n || memcmp(t, in, n)) return 0;
    }
    return 1;
}
int xc_pack2(const u8 *in, u32 n, u8 *out, u32 cap, int policy, double hdd, double dlz4, double dinf, int *stats)
{
    u32 bs = XC_BS, nb = (n + bs - 1) / bs;
    static u8 t1[XC_BS + 1024], t2[XC_BS + 1024];
    if (n == 0 || cap < XC_HDR(nb) + n + 4 * nb + 64) return 0;
    u8 *pick = calloc(nb, 1); u32 *clen = calloc(nb, 4); u8 **cdat = calloc(nb, sizeof(u8 *));
    double *dec = calloc(nb, sizeof(double)), *rawc = calloc(nb, sizeof(double));
    for (u32 b = 0; b < nb; b++) {
        u32 bl = (n - b * bs < bs) ? n - b * bs : bs;
        int c1 = LZ4_compress_HC((const char *)in + b * bs, (char *)t1, (int)bl, (int)sizeof t1, 12);
        int c2 = (policy == 0 || policy == 3) ? defl_block(in + b * bs, bl, t2, sizeof t2) : -1;
        int pk = 0;
        rawc[b] = xcm[3] * bl / XC_HZ / XCM_MARGIN;                       /* raw blocks are copied in place too */
        if (policy == 0) { u32 best = bl; if (c1 > 0 && (u32)c1 < best) { pk = 1; best = c1; } if (c2 > 0 && (u32)c2 < best) pk = 2; }
        else if (policy == 2 || policy == 4 || policy == 5) { if (c1 > 0 && (u32)c1 < bl) pk = 1; }
        else if (policy == 3) { if (c2 > 0 && (u32)c2 < bl) pk = 2; }
        if (pk == 1) { u32 f[3]; lz4_feats(t1, (u32)c1, f); dec[b] = (xcm[0] * f[0] + xcm[1] * f[1] + xcm[2] * f[2]) / XC_HZ / XCM_MARGIN; }
        pick[b] = (u8)pk;
        if (pk) { clen[b] = pk == 1 ? (u32)c1 : (u32)c2; cdat[b] = malloc(clen[b]); memcpy(cdat[b], pk == 1 ? t1 : t2, clen[b]); }
    }
    u8 *t = malloc(n), *sc = malloc(XC_SCRATCH); int res = -1, tries = 0;
    for (;;) {
        /* timing model (policies 4 and 5) */
        if (policy == 4 || policy == 5) {
            double rd = XC_HDR(nb), dt = 0, lastdec = 0; u32 lastbytes = 0;
            for (u32 b = 0; b < nb; b++) { u32 bl = (n - b * bs < bs) ? n - b * bs : bs; rd += 4 + (pick[b] ? clen[b] : bl); dt += pick[b] ? dec[b] : rawc[b]; }
            for (u32 b = nb; b-- > 0 && lastbytes < XC_CHUNK;) { u32 bl = (n - b * bs < bs) ? n - b * bs : bs; lastbytes += 4 + (pick[b] ? clen[b] : bl); lastdec += pick[b] ? dec[b] : rawc[b]; }
            double tp = policy == 4 ? rd / hdd + dt : fmax(rd / hdd + lastdec, fmin(rd, (double)XC_CHUNK) / hdd + dt);
            stats_cost[0] = tp; stats_cost[1] = n / hdd;
            if (tp >= n / hdd) {                                          /* demote the block with the worst decode time per byte saved */
                u32 w = nb; double wr = -1;
                for (u32 b = 0; b < nb; b++) if (pick[b]) { u32 bl = (n - b * bs < bs) ? n - b * bs : bs; double r = (dec[b] - rawc[b]) / (double)(bl - clen[b] + 1); if (r > wr) { wr = r; w = b; } }
                if (w == nb) { res = 0; break; }
                pick[w] = 0; continue;
            }
        }
        u32 nz = 0; for (u32 b = 0; b < nb; b++) nz += pick[b] != 0;
        if (!nz) { res = 0; break; }
        int ok = 0, pos = 0;
        for (u32 tb = nb; ; tb--) {                                       /* smallest tail (<= XC_TAILMAX) giving a proven layout */
            u32 tl = 0; for (u32 b = tb; b < nb; b++) { u32 bl = (n - b * bs < bs) ? n - b * bs : bs; tl += 4 + (pick[b] ? clen[b] : bl); }
            if (tl > XC_TAILMAX) break;
            pos = layout(in, n, out, nb, bs, pick, clen, cdat, tb);
            if ((n + 4095) / 4096 <= ((u32)pos + 4095) / 4096) { res = 0; goto done; }   /* not even one 4 KiB zone saved */
            if (proven(in, n, out, (u32)pos, t, sc)) { ok = 1; break; }
            if (tb == 0) break;
        }
        if (ok) { res = pos; break; }
        /* not provable: store the last packed block raw and retry */
        u32 dem = nb; for (u32 b = nb; b-- > 0;) if (pick[b]) { dem = b; break; }
        if (dem == nb || ++tries > (int)nb) { res = -1; break; }
        pick[dem] = 0;
    }
done:
    stats[0] = stats[1] = stats[2] = 0; for (u32 b = 0; b < nb; b++) stats[pick[b]]++;
    for (u32 b = 0; b < nb; b++) free(cdat[b]);
    free(cdat); free(clen); free(pick); free(dec); free(rawc); free(t); free(sc);
    return res;
}
/* the exact host decode of a packed buffer (independent verification pass) */
int xc_unpack(const u8 *packed, u32 fsize, u8 *dst, u32 orig)
{
    static u8 sc[XC_SCRATCH];
    memcpy(dst + orig - fsize, packed, fsize);
    return xc_inplace(dst, orig, fsize, sc);
}
#endif
