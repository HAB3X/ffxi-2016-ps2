#!/bin/bash
# build fakesound.irx (IOP stand-in) and copy it next to the host; optional first arg: extra -D flags written as #defines
cd "$(dirname "$0")"; source ~/ps2dev/env.sh; export PATH=$PATH:$PS2DEV/iop/bin
rm -rf obj *.elf fakesound.irx; : > variant.h; for d in "$@"; do echo "#define $d" >> variant.h; done
make fakesound.irx 2>&1 | grep -E " error |Error" ; ls -l fakesound.irx | awk '{print $5,$9}'; cp fakesound.irx ../irx/
