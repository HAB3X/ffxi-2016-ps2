/* IOP bring-up: reset the IOP, load the SDK's HDD / file system modules from buffers linked into this ELF. */
#include <stdio.h>
#include <string.h>
#include <tamtypes.h>
#include <kernel.h>
#include <sifrpc.h>
#include <loadfile.h>
#include <iopcontrol.h>
#include <fileXio_rpc.h>
#include <io_common.h>
#include <sbv_patches.h>
#include <hdd-ioctl.h>
#include "host.h"

#define IRX(n) extern u8 irx_##n[], irx_##n##_end[]
IRX(iomanX); IRX(fileXio); IRX(ps2dev9); IRX(ps2atad); IRX(ps2hdd); IRX(ps2fs);

int iop_ok = 0;

static int load(const char *name, void *buf, void *end, int al, const char *args)
{
    int ret = 0;
    int id = SifExecModuleBuffer(buf, (u32)((u8 *)end - (u8 *)buf), al, args, &ret);
    printf("[host] iop module %-8s id=%d ret=%d\n", name, id, ret);
    return id >= 0 && ret != 1;     /* ret 1 = module asked to be unloaded (failed) */
}

int iop_init(void)
{
    SifInitRpc(0);
    while (!SifIopReset("", 0)) { }
    while (!SifIopSync()) { }
    SifInitRpc(0);
    SifLoadFileInit();
    sbv_patch_enable_lmb();               /* LoadModuleBuffer support for older IOP loadfile */
    sbv_patch_disable_prefix_check();
    printf("[host] IOP reset done, LMB patched\n");
    int ok = 1;
    ok &= load("iomanX",  irx_iomanX,  irx_iomanX_end,  0, 0);
    ok &= load("fileXio", irx_fileXio, irx_fileXio_end, 0, 0);
    ok &= load("ps2dev9", irx_ps2dev9, irx_ps2dev9_end, 0, 0);
    ok &= load("ps2atad", irx_ps2atad, irx_ps2atad_end, 0, 0);
    ok &= load("ps2hdd",  irx_ps2hdd,  irx_ps2hdd_end,  sizeof("-o\0" "2\0" "-n\0" "8"), "-o\0" "2\0" "-n\0" "8");
    ok &= load("ps2fs",   irx_ps2fs,   irx_ps2fs_end,   sizeof("-m\0" "2\0" "-o\0" "4\0" "-n\0" "8"), "-m\0" "2\0" "-o\0" "4\0" "-n\0" "8");
    { int r = 0; int id = SifLoadStartModule("rom0:LIBSD", 0, NULL, &r); printf("[host] rom0:LIBSD id=%d ret=%d\n", id, r); }
    { int r = 0; int id = SifLoadStartModule("cdrom0:\\MODULES\\SQIOPMEM.IRX;1", 0, NULL, &r); printf("[host] SQIOPMEM id=%d ret=%d\n", id, r); }
    fileXioInit(); printf("[host] fileXioInit done\n");
    {
        int st = fileXioDevctl("hdd0:", HDIOC_STATUS, NULL, 0, NULL, 0);
        int fv = fileXioDevctl("hdd0:", HDIOC_FORMATVER, NULL, 0, NULL, 0);
        printf("[host] hdd0: status=%d formatver=%d\n", st, fv);
        iox_dirent_t de; int fd = fileXioDopen("hdd0:");
        printf("[host] hdd0: dopen -> %d\n", fd);
        if (fd >= 0) { int n = 0; while (fileXioDread(fd, &de) > 0 && n < 40) { printf("[host]   part %-34s size=%u mode=%x\n", de.name, (u32)de.stat.size, (u32)de.stat.mode); n++; } fileXioDclose(fd); }
    }
    iop_ok = ok;
    return ok;
}
