/* ime.c - a minimal "closed" input-method layer (sqImm*) for the 2016 program (6 Oct 2026).
   Outside Japan the game's text boxes only receive characters through the console input-method library: the game posts each
   key to it (sqImmKeyTyped / sqImmKeyPushed; the on-screen keyboard uses sqImmInsertSJISDirect), the library calls the game's
   callback (registered with sqImmInit3) with message 5 and flag 0x800 (a finished "result string", the Win32 IMM model), and
   the game fetches the text with sqImmGetCompositionString(ctx, 0x800, buf, size) and inserts it (0x36EB50).
   This layer never composes anything: every typed or inserted character is handed back at once as the result string. */
#include <tamtypes.h>
#include "host.h"

#define IME_MSG_COMPOSITION 5
#define GCS_RESULTSTR 0x800

typedef void (*ime_cb_t)(u32 msg, u32 wparam, u32 lparam);
static ime_cb_t ime_cb;
static char ime_res[16];
static int ime_len, ime_busy;
static u32 ime_open, ime_conv, ime_sent;

static void ime_deliver(const char *s, int n)
{
    if (!ime_cb || n <= 0 || ime_busy) return;
    if (n > (int)sizeof ime_res - 1) n = sizeof ime_res - 1;
    for (int i = 0; i < n; i++) ime_res[i] = s[i];
    ime_res[n] = 0; ime_len = n;
    ime_busy = 1; ime_cb(IME_MSG_COMPOSITION, 0, GCS_RESULTSTR); ime_busy = 0;
    ime_len = 0; ime_sent++;
}

u32 ime_svc_init3(u32 cb, u32 a1, u32 a2) { (void)a1; (void)a2; ime_cb = (ime_cb_t)cb; return 0; }      /* 1271 */
u32 ime_svc_uninit(void) { ime_cb = 0; return 0; }                                                         /* 709 */
u32 ime_svc_getcontext(u32 a0) { (void)a0; return 1; }                                                     /* 726: any non-zero handle */
u32 ime_svc_keytyped(u32 c, u32 c2)                                                                        /* 714: one (or a 2-byte) character */
{
    char s[2]; int n = 0;
    c &= 0xff; c2 &= 0xff;
    if (c < 0x20 || c == 0x7f) return 0;                    /* control keys (Enter, Backspace, Tab, Esc) are the game's own */
    s[n++] = (char)c; if (c2) s[n++] = (char)c2;
    ime_deliver(s, n); return 1;
}
u32 ime_svc_keypushed(u32 vk, u32 sh, u32 ct, u32 al) { (void)vk; (void)sh; (void)ct; (void)al; return 0; } /* 715: not consumed */
u32 ime_svc_insertsjis(u32 code)                                                                           /* 713: on-screen keyboard; bytes lo, hi */
{
    char s[2]; int n = 0; u32 lo = code & 0xff, hi = (code >> 8) & 0xff;
    if (!lo) return 0;
    s[n++] = (char)lo; if (hi) s[n++] = (char)hi;
    ime_deliver(s, n); return 1;
}
u32 ime_svc_getcompstr(u32 ctx, u32 flag, u32 buf, u32 size)                                               /* 730 */
{
    (void)ctx;
    if (!(flag & GCS_RESULTSTR) || !ime_len || !buf) return 0;
    int n = ime_len < (int)size ? ime_len : (int)size;
    for (int i = 0; i < n; i++) ((char *)buf)[i] = ime_res[i];
    return (u32)n;
}
u32 ime_svc_zero(void) { return 0; }                                                                       /* 731/732/733/744: nothing composed */
u32 ime_svc_getconv(u32 ctx, u32 pconv, u32 psent) { (void)ctx; if (pconv) *(u32 *)pconv = ime_conv; if (psent) *(u32 *)psent = 0; return 1; } /* 735 */
u32 ime_svc_setconv(u32 ctx, u32 conv, u32 sent) { (void)ctx; (void)sent; ime_conv = conv; return 1; }    /* 736 */
u32 ime_svc_getopen(u32 ctx) { (void)ctx; return ime_open; }                                               /* 737 */
u32 ime_svc_setopen(u32 ctx, u32 open) { (void)ctx; ime_open = open ? 1 : 0; return 1; }                   /* 738 */
volatile u32 g_ime_sent;                                                                                    /* PINE-readable count of delivered strings */
void ime_frame(void) { g_ime_sent = ime_sent; }

void ime_install(u32 *tab)
{   /* IME_FULL = every sqImm routine (context handle, open/conversion status); otherwise only the text-delivering ones */
    tab[1271] = (u32)ime_svc_init3; tab[714] = (u32)ime_svc_keytyped; tab[713] = (u32)ime_svc_insertsjis; tab[730] = (u32)ime_svc_getcompstr;
#ifdef IME_FULL
    tab[709] = (u32)ime_svc_uninit; tab[726] = (u32)ime_svc_getcontext; tab[715] = (u32)ime_svc_keypushed;
    tab[731] = tab[732] = tab[733] = tab[744] = (u32)ime_svc_zero;
    tab[735] = (u32)ime_svc_getconv; tab[736] = (u32)ime_svc_setconv; tab[737] = (u32)ime_svc_getopen; tab[738] = (u32)ime_svc_setopen;
#endif
}

/* the real fix: sqFepKatakanaToFullshape(src, dst, n) (slot 1132). Every character the game inserts into a text box
   (keyboard or on-screen keyboard, 0x56D320) is first passed through it; with the slot unimplemented dst stayed empty, the
   insert failed (-1) and the game played the error beep. The kernel converts half-width katakana to full width; for the
   English game the text is copied unchanged. */
u32 ime_svc_fep_k2f(u32 src, u32 dst, u32 n)
{
    (void)n;
    const char *s = (const char *)src; char *d = (char *)dst; u32 i = 0;
    if (!s || !d) return 0;
    while (s[i] && i < 255) { d[i] = s[i]; i++; }
    d[i] = 0;
    return i;
}
void fep_install(u32 *tab) { tab[1132] = (u32)ime_svc_fep_k2f; }
