# Reasonable EXP

Based on the "reasonable_exp" module by LoxleyXI (https://github.com/LoxleyXI/Modules), GPL-3.0.

After the level 55 cap break the experience needed per level jumps by 1,200 to 2,000 each level. This sets levels 53 to 76 to a
flat +200 per level (the 2002 pre-limit-break design), so the total to reach 75 drops from 801,350 to 490,550.

Use the switch in the Server App (World > Modes). It changes the `exp_base` table in the running database, remembers the old numbers
and puts them back when you switch it off. The game reads the table when it starts, so restart the server afterwards.
