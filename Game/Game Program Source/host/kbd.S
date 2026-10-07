/* keyboard layout table (1941 bytes, as PlayOnline passed it to sqPolSetKeyboardId): kcd00N.dat from the 2007 POL install data */
#ifndef KBD_LAYOUT
#define KBD_LAYOUT 2   /* 6 Oct 2026: 2 = US (1 = German: Z/Y and -/ swapped; 0 = Japanese, 4 = French) */
#endif
.section .rodata
.balign 16
.globl kbd_layout_table
kbd_layout_table:
#if KBD_LAYOUT == 0
.incbin "kbd/kcd000.dat"
#elif KBD_LAYOUT == 1
.incbin "kbd/kcd001.dat"
#elif KBD_LAYOUT == 2
.incbin "kbd/kcd002.dat"
#elif KBD_LAYOUT == 3
.incbin "kbd/kcd003.dat"
#elif KBD_LAYOUT == 4
.incbin "kbd/kcd004.dat"
#elif KBD_LAYOUT == 5
.incbin "kbd/kcd005.dat"
#else
.incbin "kbd/kcd006.dat"
#endif
.balign 16
