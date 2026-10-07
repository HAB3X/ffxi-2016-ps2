/* Console output without the SDK's C library glue.
   The glue (cwd, stdio, RTC) opens files on the IOP's cdrom0 before main(); that kept the disc busy when the IOP updater
   needed to read IOPRP.IMG. printf is redirected to the EE serial port, which PCSX2 shows in its EE console log. */
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <tamtypes.h>

/* disable the glue (all weak in libcglue) */
void _libcglue_init(void) { }
void _libcglue_deinit(void) { }
void _libcglue_args_parse(int argc, char **argv) { (void)argc; (void)argv; }
void _libcglue_rtc_update(void) { }
void _libcglue_timezone_update(void) { }

#define SIO_TXFIFO (*(volatile u8 *)0x1000F180)
#define SIO_ISR    (*(volatile u32 *)0x1000F130)
void host_puts(const char *s)
{
    for (; *s; s++) {
        if (*s == '\n') SIO_TXFIFO = '\r';
        SIO_TXFIFO = (u8)*s;
    }
}
int host_printf(const char *fmt, ...)
{
    char buf[400];
    va_list ap; va_start(ap, fmt);
    int n = vsnprintf(buf, sizeof buf, fmt, ap);
    va_end(ap);
    host_puts(buf);
    return n;
}
