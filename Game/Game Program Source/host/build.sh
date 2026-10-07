#!/bin/bash
# build host2016.elf with ps2dev
cd "$(dirname "$0")"; source ~/ps2dev/env.sh; G=mips64r5900el-ps2-elf-gcc; F="$EXTRA -D_EE -DNEWLIB_PORT_AWARE -G0 -O2 -Wall -I$PS2SDK/ee/include -I$PS2SDK/common/include"
set -e
XO=''; case "$EXTRA" in *XCOMP*) XO='xcfile.o'; $G $F -c xcfile.c -o xcfile.o;; esac
for f in host iop iop_sony sioout fileio slotnames lift_rt lifted_k hlog input net devdlg userfile social perf ime; do $G $F -c $f.c -o $f.o; done
for f in slots trap pex irx lifted_k_blob emb; do $G -c $f.S -o $f.o; done
$G -DKBD_LAYOUT=${KBD_LAYOUT:-2} -c kbd.S -o kbd.o
$G -T host.ld -O2 -o host2016.elf $XO host.o iop.o iop_sony.o sioout.o fileio.o lift_rt.o lifted_k.o hlog.o input.o net.o devdlg.o userfile.o social.o perf.o ime.o slotnames.o slots.o kbd.o trap.o pex.o irx.o lifted_k_blob.o emb.o -L$PS2SDK/ee/lib -Wl,-zmax-page-size=128 -lpad -lfileXio -liopreboot -lpatches -ldebug -lc -lkernel
ls -l host2016.elf
