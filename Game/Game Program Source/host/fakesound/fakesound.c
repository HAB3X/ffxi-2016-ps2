/* Silent stand-in for Square's IOPSOUND driver: answers the game's two sound RPC servers (0x1000, 0x1001).
   The game only needs the servers to exist and to acknowledge; the real driver is a later step. */
#include <types.h>
#include "irx_imports.h"
#include "variant.h"
#include <irx.h>
#include <loadcore.h>
#include <thbase.h>
#include <sifcmd.h>
#include <stdio.h>
#include <sysclib.h>

IRX_ID("fakesound", 1, 1);

static SifRpcDataQueue_t qd __attribute__((aligned(64)));
static SifRpcServerData_t sd0 __attribute__((aligned(64))), sd1 __attribute__((aligned(64)));
static u8 buf0[4096] __attribute__((aligned(64))), buf1[4096] __attribute__((aligned(64)));
static volatile u32 g_calls;

static void *handler(int fno, void *data, int size) { g_calls++; return data; }

#ifndef V_STAGE
#define V_STAGE 3
#endif
static void rpc_thread(void *arg)
{
#ifdef V_NOREG
    printf("fakesound: V_NOREG idle\n"); for (;;) DelayThread(1000000);
#endif
    if (V_STAGE >= 1) sceSifSetRpcQueue(&qd, GetThreadId());
    if (V_STAGE >= 2) {
        sceSifRegisterRpc(&sd0, 0x1000, handler, buf0, NULL, NULL, &qd);
        sceSifRegisterRpc(&sd1, 0x1001, handler, buf1, NULL, NULL, &qd);
    }
    printf("fakesound: stage %d up\n", V_STAGE);
    if (V_STAGE >= 3) sceSifRpcLoop(&qd);
    for (;;) DelayThread(1000000);
}

int _start(int argc, char *argv[])
{
    iop_thread_t t; t.attr = TH_C; t.thread = rpc_thread; t.priority = 0x28; t.stacksize = 0x4000; t.option = 0;
    int id = CreateThread(&t);
    if (id <= 0) return MODULE_NO_RESIDENT_END;
    StartThread(id, NULL);
    return MODULE_RESIDENT_END;
}
