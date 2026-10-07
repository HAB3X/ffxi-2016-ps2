#ifndef HOST_H
#define HOST_H
#define PEX_BASE   0x280000u
#define PEX_END    0x5fc580u   /* end of the 2016 image; bss follows to 0x800000 */
#define PEX_TOP    0x800000u
#define SLOT_TABLE 0x101000u   /* pol.pex export table the 2016 program jumps through */
#define NSLOTS     1537
const char *slot_name(int k);
void hlog(unsigned kind, unsigned a, unsigned b, unsigned c, unsigned d, unsigned e, unsigned f, const char *s0, const char *s1, const char *s2);
void hlog_kick(void); void hlog_start(void); void hlog_poke(void);
typedef struct { unsigned idx; void *fn; } LiftExt;
typedef struct { unsigned addr, size; const unsigned char *p; } LiftData;
typedef struct { unsigned slot, addr; } LiftSlot;
typedef struct { const char *name; unsigned addr; } LiftEntry;
typedef struct { unsigned code_base, code_words; const unsigned *code; const LiftExt *ext; const LiftData *data; const LiftSlot *slots; const char *name; const LiftEntry *entries; } LiftSet;
void lift_place(const LiftSet *s, unsigned *tab);
unsigned lift_entry_addr(const LiftSet *s, const char *name);
int host_printf(const char *fmt, ...);
void host_puts(const char *s);
#define printf host_printf
#endif
