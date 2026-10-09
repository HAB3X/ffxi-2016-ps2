# Loading test builds over the network (ps2link)

For console testing: start a host build on a real PS2 from the PC, without copying it to a USB stick.
Not needed to play.

## PS2 side

[ps2link](https://github.com/ps2dev/ps2link) (built from commit 0c6138c) with `ps2link-clean-exec.patch` applied.

Stock ps2link runs the loaded ELF as a thread next to itself, and its SIF interrupt handler stays installed. The host resets the IOP and
replaces the kernel services the game needs, so that is not the environment the game runs in from a USB launcher. With the patch, `execee`
loads the ELF, removes ps2link's handler, resets the IOP and starts the ELF with `ExecPS2`, the same way a launcher does. ps2link is then gone
until the PS2 is restarted.

    cd ps2link && git apply ps2link-clean-exec.patch && make      # needs PS2SDK and ps2-packer

Use the packed `bin/PS2LINK.ELF` (ps2-packer with its default lzma-1d00 stub). The unpacked `ee/ps2link.elf` loads at 0x94000, below
where launchers expect a program, and started from uLaunchELF it only gave a black screen.

Copy `bin/PS2LINK.ELF` to the USB stick as `PS2LINK/PS2LINK.ELF`, with an `IPCONFIG.DAT` beside it: one line,
`<PS2 address> <netmask> <gateway>`, e.g. `192.168.1.11 255.255.255.0 192.168.1.1`. Start it from your launcher.

## PC side

`ps2run.py` stands in for ps2client's `execee`. It connects to ps2link, asks it to run `host:<file>` and serves that one file, read only,
from the folder you give. Python 3, no other packages.

    python ps2run.py --ps2 192.168.1.11 --dir <folder with the builds> NETDIAG40.ELF

ps2link's console output stops as soon as the host resets the IOP (at start-up), so in-game diagnostics still come from the `-DNETDIAG`
reports through the proxy.

## Live debug link (`-DNETDIAG` builds)

`-DNETDIAG` builds also start a debug link (`host/dbg.c`) once the network is up: the PS2 connects out to the PC (`NETDIAG_PC_IP`, TCP
port 54100) and keeps reconnecting, so the console can be started before or after the game. It runs at the highest thread priority and
keeps answering while the game is stuck, as long as the EE still takes interrupts.

    python ps2dbg.py --sym host2016.sym          # sym: nm output of the build, for symbol names in addresses and crash reports

It shows a status line every few seconds and logs everything (status, host log, reports, caught CPU exceptions) to `ps2dbg/ps2dbg.log`.
Commands are typed in the console or appended to `ps2dbg/cmd.txt`: `peek ADDR [LEN]`, `poke ADDR VALUE`, `thr`, `sema`, `report`,
`beat`, `log`, `ping`, `rate MS`, `stream 0|1`, and hardware watchpoints `watch` / `iwatch` / `unwatch` (run `wtest` once first).
`help` lists them. Memory dumps contain whatever is in RAM, sign-in details included: keep them on your own PC.
