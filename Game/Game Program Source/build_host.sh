#!/bin/bash
# build the merged 2016 host (6 Oct 2026, b5x merge). MODE=main (default): the local test/play build (debug logging, THRDBG);
# MODE=release: no tracer/recorder/debug scans, direct slot dispatch; MODE=disc: release + DISC_BUILD (no saved logins compiled in).
# Always: XCOMP (packed files XCINDEX + container packs), B55_GEAR5 (PC-content weapon looks). Step-2 fixes: ALARM_VBL, FASTFILEWAIT=33
# (see work/b53_perf report). Check the size line - a wrong flag set links fine but runs the old binary.
cd "$(dirname "$0")/host" || exit 1
BASE="-DSONY_IOP -DNET_USE_DHCP=1 -DINPUT_HID_INIT -DNO_NETBOOT -DDEV_DIALOG -DDEV_AUTOLOGIN -DDEV_NATIVE -DDEV_SHOW -DNET_REAL_UDP -DPOL_ARG=1 -DXCOMP -DB55_GEAR5 -DFEP_FIX -DNO_GS_MODE2 -DALARM_VBL -DLOGOUT_FIX ${STEP2:-}"
case "${MODE:-main}" in
  main) X="$BASE -DTHRDBG";;
  release) X="$BASE -DRELEASE";;
  disc) X="$BASE -DTHRDBG -DDISC_BUILD -DDEV_IP=\"0.0.0.0\"";;   # the install disc build: no logins or addresses compiled in
  *) echo "MODE?"; exit 1;;
esac
EXTRA="$X" bash ./build.sh 2>&1 | grep -E 'error|host2016.elf'
