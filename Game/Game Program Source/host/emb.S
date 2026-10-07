/* Square Enix / Sony IOP modules (copies of the install disc's MODULES files) + embfs.irx, for starting without the disc.
   Linked at 0x01E00000 (section .embmods, game memory that is only used after the host has set up the IOP). */
.macro EMB name, file
    .section .embmods, "a"
    .balign 64
    .globl emb_\name
emb_\name:
    .incbin "\file"
emb_\name\()_end:
    .section .rodata
    .balign 4
    .globl emb_\name\()_size
emb_\name\()_size: .word emb_\name\()_end - emb_\name
.endm
    EMB ioprp, "emb/IOPRP.IMG"
    EMB sqiopmem, "emb/SQIOPMEM.IRX"
    EMB embfs, "emb/EMBFS.IRX"
    EMB sce000, "emb/SCE000.ERX"
    EMB sce001, "emb/SCE001.ERX"
    EMB sce002, "emb/SCE002.ERX"
    EMB hid000, "emb/HID000.ERX"
