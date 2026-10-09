ENTRY(__start);
PHDRS { text PT_LOAD; lift PT_LOAD; pex PT_LOAD; emb PT_LOAD; }
SECTIONS {
	.text 0x00103000: { _ftext = . ; *(.text) *(.text.*) *(.gnu.linkonce.t*) KEEP(*(.init)) KEEP(*(.fini)) QUAD(0) } :text
	PROVIDE(_etext = .); PROVIDE(etext = .);
	.ctors ALIGN(16): { KEEP(*crtbegin*.o(.ctors)) KEEP(*(EXCLUDE_FILE(*crtend*.o) .ctors)) KEEP(*(SORT(.ctors.*))) KEEP(*(.ctors)) }
	.dtors ALIGN(16): { KEEP(*crtbegin*.o(.dtors)) KEEP(*(EXCLUDE_FILE(*crtend*.o) .dtors)) KEEP(*(SORT(.dtors.*))) KEEP(*(.dtors)) }
	.reginfo : { *(.reginfo) }
	.data ALIGN(128): { _fdata = . ; *(.data) *(.data.*) *(.gnu.linkonce.d*) SORT(CONSTRUCTORS) }
	.rodata ALIGN(128): { *(.rodata) *(.rodata.*) *(.gnu.linkonce.r*) }
	.rdata ALIGN(128): { *(.rdata) }
	.gcc_except_table ALIGN(128): { *(.gcc_except_table) }
	_gp = ALIGN(128) + 0x7ff0;
	.lit4 ALIGN(128): { *(.lit4) }
	.lit8 ALIGN(128): { *(.lit8) }
	.sdata ALIGN(128): { *(.sdata) *(.sdata.*) *(.gnu.linkonce.s*) }
	_edata = .; PROVIDE(edata = .);
	.sbss ALIGN(128) : { _fbss = . ; *(.sbss) *(.sbss.*) *(.gnu.linkonce.sb*) *(.scommon) }
	.bss ALIGN(128) : { *(.bss) *(.bss.*) *(.gnu.linkonce.b*) *(COMMON) }
	_end_bss = .; _end = . ; PROVIDE(end = .);
	.lift_k 0x001D6000 : { *(.lift_k) } :lift
	/* NETDIAG builds: the debug link code (dbg.c, sections renamed .dbgk* by build.sh) */
	.dbgk ALIGN(64) : { *(.dbgk*) } :lift
	/* packed-file index + decoder scratch/stack (xcfile.c), not loaded: the gap between the lifted kernel and the game */
	.xcmem (NOLOAD) : ALIGN(64) { _xcmem_start = .; *(.xcmem) _xcmem_end = .; } :lift
	ASSERT(_xcmem_end <= 0x00280000, "xcmem overlaps the game program")
	/* the 2016 program, fixed at its link address */
	.pex 0x00280000 : { *(.pex) } :pex
	/* embedded IOP modules for starting without the disc (emb.S) */
	.embmods 0x01E00000 : { *(.embmods) } :emb
	.spad 0x70000000: { *(.spad) }
	PROVIDE(_heap_size = 0x2000);
	PROVIDE(_stack = -1);
	PROVIDE(_stack_size = 128 * 1024);
}
