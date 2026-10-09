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
