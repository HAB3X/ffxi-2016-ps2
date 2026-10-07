/* Runtime half of lift.py: place the lifted donor code and data, patch calls to host functions, fill the slot table. */
#include <stdio.h>
#include <string.h>
#include <tamtypes.h>
#include <kernel.h>
#include "host.h"

void lift_place(const LiftSet *s, unsigned *tab)
{
    u32 *dst = (u32 *)s->code_base;
    if (s->code) memcpy(dst, s->code, s->code_words * 4);   /* blob sets are linked in place */
    for (int i = 0; s->ext[i].fn; i++) {
        u32 w = dst[s->ext[i].idx];
        dst[s->ext[i].idx] = (w & 0xFC000000u) | ((((u32)s->ext[i].fn) >> 2) & 0x03FFFFFFu);
    }
    if (s->data) for (int i = 0; s->data[i].p; i++) memcpy((void *)s->data[i].addr, s->data[i].p, s->data[i].size);
    int n = 0;
#ifndef LIFT_SKIP
#define LIFT_SKIP {0}
#endif
    static const unsigned skip[] = LIFT_SKIP;
#ifdef LIFT_USE
    static const unsigned use[] = LIFT_USE;
#endif
    for (int i = 0; s->slots[i].addr; i++) {
        int sk = 0; for (unsigned k = 0; k < sizeof skip / sizeof skip[0]; k++) if (skip[k] == s->slots[i].slot) sk = 1;
        if (sk) continue;
#ifdef LIFT_USE
        { int u = 0; for (unsigned k = 0; k < sizeof use / sizeof use[0]; k++) if (use[k] == s->slots[i].slot) u = 1; if (!u) continue; }
#endif
        tab[s->slots[i].slot] = s->slots[i].addr; n++;
    }
    printf("[host] lifted %s: %u words at %08x, %d slots\n", s->name, s->code_words, s->code_base, n);
}

/* helpers the lifted graphics code calls (donor 0x111dc8 / 0x106f30) */
static u8 gs_state[64] __attribute__((aligned(16)));
void *host_gs_state(void) { return gs_state; }
int host_noprint(void) { return 0; }

/* calls the lifted code could not resolve end up here, with $at = index into lift_k_unres[] */
extern const unsigned lift_k_unres[];
u32 unres_c(u32 id, u64 *r)
{
    static int n = 0;
    if (n < 40) { n++; hlog(9, lift_k_unres[id], (u32)r[0], 0, 0, 0, 0, "UNRESOLVED donor call", 0, 0); }
    return 0;
}

/* host-callable kernel entry points (lift2 "entries") */
#include <sifrpc.h>
unsigned lift_entry_addr(const LiftSet *s, const char *name)
{
    for (int i = 0; s->entries && s->entries[i].name; i++) if (!strcmp(s->entries[i].name, name)) return s->entries[i].addr;
    return 0;
}
void host_sifinitrpc(int mode) { (void)mode; /* the SDK layer is already up; re-initialising it re-arms SIF0 and strands pending DMAs */ }
void host_sifexitrpc(void) { /* no-op: tearing the SDK RPC layer down mid-run kills in-flight IOP->EE DMAs (padman "DMA Busy") */ }

/* kernel sceSifAddCmdHandler (donor 0x1dfda8) writes into the kernel libsif's own table, which is never set up here (the SDK's SIF
   command layer is the live one); route it to the SDK so IOP->EE command packets (0x80000011/13 of the sceFs library) arrive. */
#include <sifcmd.h>
/* handlers are wrapped so each IOP->EE command is visible in the log (counter g_cmd_seen, hlog kind 9) */
typedef void (*cmdh_t)(void *, void *);
static struct { u32 cid; cmdh_t h; } cmdtab[8]; static int ncmd = 0;
volatile u32 g_cmd_seen[8];
#define TR(n) static void cmd_tr##n(void *d, void *a) { g_cmd_seen[n]++; cmdtab[n].h(d, a); }
TR(0) TR(1) TR(2) TR(3) TR(4) TR(5) TR(6) TR(7)
static const cmdh_t trs[8] = { cmd_tr0, cmd_tr1, cmd_tr2, cmd_tr3, cmd_tr4, cmd_tr5, cmd_tr6, cmd_tr7 };
void host_sifaddcmd(u32 cid, void *handler, void *arg)
{
    int i = ncmd < 8 ? ncmd++ : 7;
    cmdtab[i].cid = cid; cmdtab[i].h = (cmdh_t)handler;
    hlog(9, cid, (u32)handler, (u32)arg, 0, 0, 0, "SifAddCmdHandler cid/handler/arg:", 0, 0);
    SifAddCmdHandler(cid, (SifCmdHandler_t)trs[i], arg);
}

/* kernel libsif command layer -> SDK: the kernel's own tables are never initialised here */
void host_sifinitcmd(void) { SifInitCmd(); }
void host_sifexitcmd(void) { SifExitCmd(); }
void *host_sifremovecmdhandler(u32 id) { SifRemoveCmdHandler(id); return 0; }

void lockbug_tramp(void);
void lockbug_c(u32 obj, u32 ra, u32 ra2)
{
    hlog(9, obj, ra, ra2, 0, 0, 0, "LOCKBUG obj/ra(unlock)/ra(lock):", 0, 0);
    for (;;) SleepThread();
}
void lockbug_install(const LiftSet *s)
{
    unsigned u = lift_entry_addr(s, "sqUnLockObject"), l = lift_entry_addr(s, "sqLockObject");
    unsigned t = (unsigned)lockbug_tramp;
    if (u) *(u32 *)(u + 0x2c) = 0x08000000 | ((t >> 2) & 0x3FFFFFF);
    if (l) *(u32 *)(l + 0x34) = 0x08000000 | ((t >> 2) & 0x3FFFFFF);
}

/* kernel sqDelay(hsync ticks) (donor 0x1ffeb0): the original sleeps on an alarm; replaced by a CPU-count busy wait (1 hsync ~ 18750 cycles) */
void host_sqdelay(u32 ticks)
{
    u32 t0, now; ticks &= 0xFFFF;
    __asm__ volatile("mfc0 %0, $9" : "=r"(t0));
    u32 want = ticks * 18750u;
    do { __asm__ volatile("mfc0 %0, $9" : "=r"(now)); } while ((now - t0) < want);
}
