/* the lifted blob, linked at its final address by host.ld (section .lift_k) */
.section .lift_k,"aw",@progbits
.incbin "lifted_k.bin"
