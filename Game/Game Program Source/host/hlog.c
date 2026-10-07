/* Logging that is safe to call from any thread (game threads have tiny stacks): calls only fill a ring buffer; one
   dedicated thread with a big stack formats and prints. */
#include <stdio.h>
#include <string.h>
#include <tamtypes.h>
#include <kernel.h>
#include "host.h"

#define RN 128
typedef struct { u32 kind; u32 v[6]; char s[3][40]; } HRec;
static HRec ring[RN]; static volatile u32 wp = 0, rp = 0; static int logger_tid = -1;
static u8 logstack[32768] __attribute__((aligned(16)));

static void copystr(char *d, const char *s)
{
    int i = 0;
    if (s && (u32)s >= 0x100000 && (u32)s < 0x2000000) for (; i < 39 && s[i] >= 0x20 && s[i] < 0x7f; i++) d[i] = s[i];
    d[i] = 0;
}
void hlog(u32 kind, u32 a, u32 b, u32 c, u32 d, u32 e, u32 f, const char *s0, const char *s1, const char *s2)
{
    if (wp - rp >= RN) return;                       /* ring full: drop */
    HRec *r = &ring[wp & (RN - 1)];
    r->kind = kind; r->v[0] = a; r->v[1] = b; r->v[2] = c; r->v[3] = d; r->v[4] = e; r->v[5] = f;
    copystr(r->s[0], s0); copystr(r->s[1], s1); copystr(r->s[2], s2);
    wp++;
}
static void flush(void)
{
    while (rp != wp) {
        HRec *r = &ring[rp & (RN - 1)]; rp++;
        switch (r->kind) {
        case 1: { const char *n = slot_name(r->v[0]);
            printf("[host] slot %u (%s) first call ra=%08x a0=%08x a1=%08x a2=%08x a3=%08x%s%s%s%s%s%s%s%s%s\n", r->v[0], n ? n : "?", r->v[1], r->v[2], r->v[3], r->v[4], r->v[5],
                   r->s[0][0] ? " a0=\"" : "", r->s[0], r->s[0][0] ? "\"" : "", r->s[1][0] ? " a1=\"" : "", r->s[1], r->s[1][0] ? "\"" : "", r->s[2][0] ? " a2=\"" : "", r->s[2], r->s[2][0] ? "\"" : ""); break; }
        case 2: printf("[host] open(%s, %x) -> %d\n", r->s[0], r->v[0], (int)r->v[1]); break;
        case 3: printf("[host] read(fd=%d, %u) -> %d dst=%08x\n", (int)r->v[0], r->v[1], (int)r->v[2], r->v[3]); break;
        case 4: printf("[host] getstat(%s) -> %d\n", r->s[0], (int)r->v[0]); break;
        case 5: printf("[host] BindRpc id=%x -> %d server=%08x%s\n", r->v[0], (int)r->v[1], r->v[2], r->s[0]); break;
        case 6: printf("[host] CallRpc server=%08x fno=%d mode=%d send=%08x/%d recv=%08x/%d%s\n", r->v[0], (int)r->v[1], (int)r->v[2], r->v[3], (int)r->v[4], r->v[5], 0, r->s[0]); break;
        case 7: printf("[host] SifSetDma src=%08x dest(IOP)=%08x size=%d attr=%x (swallowed)\n", r->v[0], r->v[1], (int)r->v[2], r->v[3]); break;
        case 8: printf("[host] load IOP module %s\n", r->s[0]); break;
        case 9: printf("[host] %s %08x %08x %08x %08x\n", r->s[0], r->v[0], r->v[1], r->v[2], r->v[3]); break;
        }
    }
}
static void logger(void *arg) { for (;;) { flush(); SleepThread(); } }
void hlog_start(void)
{
    ee_thread_t t; t.func = (void *)logger; t.stack = logstack; t.stack_size = sizeof logstack; t.gp_reg = &_gp;
    t.initial_priority = 3; t.attr = 0; t.option = 0;
    logger_tid = CreateThread(&t); StartThread(logger_tid, NULL);
}
void hlog_poke(void)                                  /* called from the 1 ms alarm (interrupt context) */
{
    if (rp != wp && logger_tid >= 0) iWakeupThread(logger_tid);
}

void hlog_kick(void) { if (logger_tid >= 0) WakeupThread(logger_tid); }   /* thread-context wake-up (net.c) */

#ifdef THRDBG
/* debug: every 5 s print the state of all EE threads (status / wait type / wait id / priority / entry) and of the first semaphores */
volatile u32 g_thrd[24][20];   /* live copy of the thread dump: {tid,status,waitType|id<<8,prio,func,stack,nrets,rets[12]} */
static u8 thrdbg_stack[6144] __attribute__((aligned(16)));
static void thrdbg(void *arg)
{
    for (;;) {
        for (int rep = 0; rep < 10; rep++) { for (volatile int w = 0; w < 5000000; w++) { } hlog_kick(); }   /* ~5 s busy wait (interrupts keep running), logger poked every 0.2 s */
        for (int tid = 1; tid < 24; tid++) {
            ee_thread_status_t st;
            if (ReferThreadStatus(tid, &st) < 0) continue;
            g_thrd[tid][0] = tid; g_thrd[tid][1] = st.status; g_thrd[tid][2] = st.waitType | (st.waitId << 8); g_thrd[tid][3] = st.current_priority; g_thrd[tid][4] = (u32)st.func; g_thrd[tid][5] = (u32)st.stack; g_thrd[tid][6] = 0;
            hlog(9, tid, st.status, st.waitType | (st.waitId << 8), st.current_priority | (st.initial_priority << 16), (u32)st.func, 0, "THREAD tid/status/wait(type|id<<8)/prio:", 0, 0);
            if (st.status == 4 && (u32)st.stack >= 0x100000 && (u32)st.stack < 0x2000000) {          /* a waiting thread: entry, stack and the return addresses found on it */
                hlog(9, tid, (u32)st.func, (u32)st.stack, st.stack_size, 0, 0, "THR func/stack/size:", 0, 0);
                u32 rets[12]; int nr = 0;
                for (u32 o = 0; o + 4 <= (u32)st.stack_size && nr < 12; o += 4) {
                    u32 v = *(volatile u32 *)((u32)st.stack + o);
                    if (v >= 0x280000 && v < 0x5fc580 && !(v & 3)) {
                        u32 w = *(volatile u32 *)(v - 8);
                        if ((w >> 26) == 3 || ((w >> 26) == 0 && (w & 0x3f) == 9)) rets[nr++] = v;
                    }
                }
                g_thrd[tid][6] = nr; for (int k = 0; k < nr; k++) g_thrd[tid][7 + k] = rets[k];
                for (int k = 0; k < nr; k += 4) hlog(9, rets[k], k + 1 < nr ? rets[k + 1] : 0, k + 2 < nr ? rets[k + 2] : 0, k + 3 < nr ? rets[k + 3] : 0, 0, 0, "THR rets(near sp first):", 0, 0);
            }
        }
    }
}
void thrdbg_start(void)
{
    ee_thread_t t; memset(&t, 0, sizeof t);
    t.func = (void *)thrdbg; t.stack = thrdbg_stack; t.stack_size = sizeof thrdbg_stack; t.initial_priority = 60; t.gp_reg = &_gp;
    int id = CreateThread(&t); if (id >= 0) StartThread(id, NULL);
}
#endif
