/* install disc: no saved logins (no accounts, passwords or server addresses are compiled in). */
typedef struct { const char *label, *acct, *pass, *ip, *port; } DevProfile;
static const DevProfile g_profiles[] = {
    { "(type your login)", "", "", "", "54001" },
};
