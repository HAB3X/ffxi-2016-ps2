# Gameplay modes

Small switches for a small server. They are off until you turn them on in the Server App (World > Rules, under Gameplay modes).
Each one is a copy of a module from LoxleyXI's collection, https://github.com/LoxleyXI/Modules (GPL-3.0, the same licence as LandSandBoat),
changed to work with this server's LandSandBoat and the PS2 game. Credit for the ideas and the original code goes to LoxleyXI.

| Folder | What it does | How it is switched on |
| --- | --- | --- |
| `reasonable_exp` | Levels 53 to 76 need a flat +200 experience per level instead of the steep curve. | The app changes the `exp_base` table (and can put the old numbers back). Restart the server. |
| `helm_claim` | The first player to use a gathering point holds it for 10 seconds. | A line in `modules/init.txt`. Restart the server. |
| `oztroja_escape` | A hole on the top floor of Castle Oztroja lets players leave without a Judgment Key. | A line in `modules/init.txt`. Restart the server. |

Modules from the same collection that were looked at and left out: `ironman_mode` (needs a rebuilt game program and is the
opposite of a relaxed server), `pre_zilart` (rewrites the settings while loading and overlaps the Rules tab), `custom_helm`,
`custom_nm`, `custom_chest`, `custom_clamming` and `custom_util` (toolkits that add nothing until someone writes content for
them), `jeuno_valeriano` (needs `custom_util` and a conquest tie).
