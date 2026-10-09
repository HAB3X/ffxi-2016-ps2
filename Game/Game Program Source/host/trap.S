# Common trap: at = slot index. Saves a0-a3,t0-t3 and ra, calls trap_c(idx, regs), returns its result in v0.
.set noreorder
.set noat
.section .text
.global trap_common
.ent trap_common
trap_common:
  addiu $sp,$sp,-0x60
  sd $ra,0x00($sp)
  sd $a0,0x08($sp)
  sd $a1,0x10($sp)
  sd $a2,0x18($sp)
  sd $a3,0x20($sp)
  sd $8,0x28($sp)
  sd $9,0x30($sp)
  sd $10,0x38($sp)
  sd $11,0x40($sp)
  move $a0,$at
  jal trap_c
  move $a1,$sp
  ld $ra,0x00($sp)
  jr $ra
  addiu $sp,$sp,0x60
.end trap_common

# unresolved call from lifted code: at = index. Same shape as trap_common, calls unres_c(at, regs)
.global host_unresolved
.ent host_unresolved
host_unresolved:
  addiu $sp,$sp,-0x60
  sd $ra,0x00($sp)
  sd $a0,0x08($sp)
  sd $a1,0x10($sp)
  sd $a2,0x18($sp)
  sd $a3,0x20($sp)
  move $a0,$at
  jal unres_c
  move $a1,$sp
  ld $ra,0x00($sp)
  jr $ra
  addiu $sp,$sp,0x60
.end host_unresolved

/* debug: lifted sqLock/sqUnLockObject "BAD LOCK STATE" break is patched to jump here (obj in s0, caller's saved ra at 0x20(sp)) */
    .set noreorder
    .globl lockbug_tramp
lockbug_tramp:
    move $a0, $s0
    ld   $a1, 0x20($sp)
    ld   $a2, 0x30($sp)
    j    lockbug_c
    nop

/* debug (EXC_HOLD): exception parking spot */
    .globl exc_hold
exc_hold:
1:  b 1b
    nop

.section .bss
.global g_badsp
.balign 16
g_badsp: .space 16

    .section .text
/* host_drawtext(x, y, str, color): the 2016 program's own text routine 0x2C5A00 (as called from 0x35BCF0: scale 1.0, flag 0x44) */
    .set noreorder
    .globl host_drawtext
host_drawtext:
    move  $t0, $a3
    move  $a3, $zero
    addiu $t1, $zero, 0x44
    lui   $v0, 0x3f80
    mtc1  $v0, $f12
    mov.s $f13, $f12
    j     0x2c5a00
    nop

/* ---- hook on the program's string draw routine 0x549D40 (x=a0, y=a1, str=a2, color=a3, flag=t0, scale f12/f13).  The first two instructions
   (addiu sp,-160 ; sd ra,144(sp)) are replaced by "j text_hook_entry; nop".  text_probe() returns nonzero when it drew/consumed the call. ---- */
    .section .text
    .set noreorder
    .set noat
    .globl text_hook_entry
text_hook_entry:
    addiu $sp, $sp, -0x50
    sd    $ra, 0x00($sp)
    sd    $a0, 0x08($sp)
    sd    $a1, 0x10($sp)
    sd    $a2, 0x18($sp)
    sd    $a3, 0x20($sp)
    sd    $8,  0x28($sp)
    swc1  $f12, 0x30($sp)
    swc1  $f13, 0x34($sp)
    jal   text_probe
    nop
    bnez  $v0, 1f
    nop
    ld    $ra, 0x00($sp)
    ld    $a0, 0x08($sp)
    ld    $a1, 0x10($sp)
    ld    $a2, 0x18($sp)
    ld    $a3, 0x20($sp)
    ld    $8,  0x28($sp)
    lwc1  $f12, 0x30($sp)
    lwc1  $f13, 0x34($sp)
    addiu $sp, $sp, 0x50
    addiu $sp, $sp, -160            /* the replaced original instructions */
    sd    $ra, 144($sp)
    j     0x549d48
    nop
1:  ld    $ra, 0x00($sp)
    addiu $sp, $sp, 0x50
    jr    $ra
    move  $v0, $zero

/* same idea for the low-level text routine 0x2C5A00 (x=a0 y=a1 str=a2 a3 color=t0 flags=t1, scale f12/f13): first two instructions
   (addiu sp,-160 ; sd ra,112(sp)) replaced by "j text2_hook_entry; nop"; text2_probe() != 0 means consumed */
    .globl text2_hook_entry
text2_hook_entry:
    addiu $sp, $sp, -0x60
    sd    $ra, 0x00($sp)
    sd    $a0, 0x08($sp)
    sd    $a1, 0x10($sp)
    sd    $a2, 0x18($sp)
    sd    $a3, 0x20($sp)
    sd    $8,  0x28($sp)
    sd    $9,  0x30($sp)
    swc1  $f12, 0x38($sp)
    swc1  $f13, 0x3c($sp)
    jal   text2_probe
    nop
    sltiu $8, $v0, 2                 /* 0 = draw as is, 1 = consumed, anything else = a replacement string to draw instead */
    bnez  $8, 3f
    nop
    sd    $v0, 0x18($sp)
    move  $v0, $zero
3:  bnez  $v0, 1f
    nop
    ld    $ra, 0x00($sp)
    ld    $a0, 0x08($sp)
    ld    $a1, 0x10($sp)
    ld    $a2, 0x18($sp)
    ld    $a3, 0x20($sp)
    ld    $8,  0x28($sp)
    ld    $9,  0x30($sp)
    lwc1  $f12, 0x38($sp)
    lwc1  $f13, 0x3c($sp)
    addiu $sp, $sp, 0x60
    addiu $sp, $sp, -160
    sd    $ra, 112($sp)
    j     0x2c5a08
    nop
1:  ld    $ra, 0x00($sp)
    addiu $sp, $sp, 0x60
    jr    $ra
    move  $v0, $zero

/* hook on the menu manager's open-by-name 0x365150 (this=a0, name=a1, flag=a2, a3): first two instructions (addiu sp,-144 ; sd ra,80(sp)) replaced.
   menu_probe() != 0 means "refused": return 0 to the caller. */
    .globl menu_hook_entry
menu_hook_entry:
    addiu $sp, $sp, -0x50
    sd    $ra, 0x00($sp)
    sd    $a0, 0x08($sp)
    sd    $a1, 0x10($sp)
    sd    $a2, 0x18($sp)
    sd    $a3, 0x20($sp)
    jal   menu_probe
    nop
    bnez  $v0, 1f
    nop
    ld    $ra, 0x00($sp)
    ld    $a0, 0x08($sp)
    ld    $a1, 0x10($sp)
    ld    $a2, 0x18($sp)
    ld    $a3, 0x20($sp)
    addiu $sp, $sp, 0x50
    addiu $sp, $sp, -144
    sd    $ra, 80($sp)
    j     0x365158
    nop
1:  ld    $ra, 0x00($sp)
    addiu $sp, $sp, 0x50
    jr    $ra
    move  $v0, $zero

# u64 call8s(u32 fn, u64 *regs, u64 *stk): call fn with the 8 register args (a0..a3,t0..t3 from regs) and a copy of the caller's first 8 stack dwords at 0(sp);
# SDK functions with more than 8 arguments (sceGsSetDefClear) read the rest from the stack, which trap_c's C call does not forward
    .section .text
    .set noreorder
    .globl call8s
call8s:
    addiu $sp, $sp, -0x70
    sd    $ra, 0x60($sp)
    move  $25, $4
    ld $2, 0($6);  sd $2, 0($sp)
    ld $2, 8($6);  sd $2, 8($sp)
    ld $2, 16($6); sd $2, 16($sp)
    ld $2, 24($6); sd $2, 24($sp)
    ld $2, 32($6); sd $2, 32($sp)
    ld $2, 40($6); sd $2, 40($sp)
    ld $2, 48($6); sd $2, 48($sp)
    ld $2, 56($6); sd $2, 56($sp)
    move  $3, $5
    ld $4, 0($3)
    ld $5, 8($3)
    ld $6, 16($3)
    ld $7, 24($3)
    ld $8, 32($3)
    ld $9, 40($3)
    ld $10, 48($3)
    ld $11, 56($3)
    jalr  $25
    nop
    ld    $ra, 0x60($sp)
    jr    $ra
    addiu $sp, $sp, 0x70

/* debug: hook on the error-report routine 0x3CEF40 (a0 = error code): remembers {code, caller} of the last 16 reports; first two instructions
   (addiu sp,-1584 ; sd ra,32(sp)) are replaced by "j err_hook_entry; nop" */
    .set noreorder
    .set at
    .globl err_hook_entry
err_hook_entry:
    la    $t0, g_err_n
    lw    $t1, 0($t0)
    andi  $t2, $t1, 15
    sll   $t2, $t2, 2
    la    $t3, g_err_a0
    addu  $t3, $t3, $t2
    sw    $a0, 0($t3)
    la    $t3, g_err_ra
    addu  $t3, $t3, $t2
    sw    $ra, 0($t3)
    addiu $t1, $t1, 1
    sw    $t1, 0($t0)
    addiu $sp, $sp, -1584
    sd    $ra, 32($sp)
    j     0x3cef48
    nop
    .set noat

/* ---- 6 Oct 2026: emote probes (diagnostics, read over PINE: g_emo_*). Both game functions start with
   (addiu sp,-112 ; sd ra,80(sp)), replaced by "j <entry>; nop". The probes only copy a few words (no printf: game stacks are small). ---- */
    .section .text
    .set noreorder
    .set noat
    .globl emote_hook_entry
emote_hook_entry:                       /* 0x30D5F0: s2c 0x05A handler, a2 = packet */
    addiu $sp, $sp, -0x60
    sd    $ra, 0x00($sp)
    sd    $a0, 0x08($sp)
    sd    $a1, 0x10($sp)
    sd    $a2, 0x18($sp)
    sd    $a3, 0x20($sp)
    sd    $8,  0x28($sp)
    sd    $9,  0x30($sp)
    jal   emote_probe
    nop
    ld    $ra, 0x00($sp)
    ld    $a0, 0x08($sp)
    ld    $a1, 0x10($sp)
    ld    $a2, 0x18($sp)
    ld    $a3, 0x20($sp)
    ld    $8,  0x28($sp)
    ld    $9,  0x30($sp)
    addiu $sp, $sp, 0x60
    addiu $sp, $sp, -112
    sd    $ra, 80($sp)
    j     0x30d5f8
    nop
    .globl motion_hook_entry
motion_hook_entry:                      /* 0x30DBB0: start an emote motion (a0 actor index, a1 target index, a2 emote, a3 param) */
    addiu $sp, $sp, -0x60
    sd    $ra, 0x00($sp)
    sd    $a0, 0x08($sp)
    sd    $a1, 0x10($sp)
    sd    $a2, 0x18($sp)
    sd    $a3, 0x20($sp)
    sd    $8,  0x28($sp)
    sd    $9,  0x30($sp)
    jal   motion_probe
    nop
    ld    $ra, 0x00($sp)
    ld    $a0, 0x08($sp)
    ld    $a1, 0x10($sp)
    ld    $a2, 0x18($sp)
    ld    $a3, 0x20($sp)
    ld    $8,  0x28($sp)
    ld    $9,  0x30($sp)
    addiu $sp, $sp, 0x60
    addiu $sp, $sp, -112
    sd    $ra, 80($sp)
    j     0x30dbb8
    nop

/* CommandCalc (0x3A9ED0) hook: social chat commands (/befriend /unfriend /fmsg /friends) are handled by soc_cmd_filter;
   everything else continues into the original function (its first two instructions are re-executed here) */
    .globl soc_cmd_entry
soc_cmd_entry:
    addiu $sp, $sp, -0x50
    sd    $ra, 0x00($sp)
    sd    $a0, 0x08($sp)
    sd    $a1, 0x10($sp)
    jal   soc_cmd_filter
    nop
    bnez  $v0, 1f
    nop
    ld    $ra, 0x00($sp)
    ld    $a0, 0x08($sp)
    ld    $a1, 0x10($sp)
    addiu $sp, $sp, 0x50
    addiu $sp, $sp, -1200
    sd    $ra, 128($sp)
    j     0x3A9ED8
    nop
1:  ld    $ra, 0x00($sp)
    addiu $sp, $sp, 0x50
    jr    $ra
    li    $v0, 1
