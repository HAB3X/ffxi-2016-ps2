--
-- Reasonable EXP Curve
--
-- Based on the "reasonable_exp" module by LoxleyXI (https://github.com/LoxleyXI/Modules), GPL-3.0.
-- Sets the experience needed for levels 53 to 76 to a flat +200 per level. The number after "--" on each line is the value it replaces.
-- The Server App (World > Modes) applies and undoes this itself in the running database; the file is also fine for dbtool.
--
UPDATE `exp_base` SET exp =  8200 WHERE level = 53; -- 9200
UPDATE `exp_base` SET exp =  8400 WHERE level = 54; -- 10400
UPDATE `exp_base` SET exp =  8600 WHERE level = 55; -- 11600
UPDATE `exp_base` SET exp =  8800 WHERE level = 56; -- 12800
UPDATE `exp_base` SET exp =  9000 WHERE level = 57; -- 14000
UPDATE `exp_base` SET exp =  9200 WHERE level = 58; -- 15200
UPDATE `exp_base` SET exp =  9400 WHERE level = 59; -- 16400
UPDATE `exp_base` SET exp =  9600 WHERE level = 60; -- 17600
UPDATE `exp_base` SET exp =  9800 WHERE level = 61; -- 18800
UPDATE `exp_base` SET exp = 10000 WHERE level = 62; -- 20000
UPDATE `exp_base` SET exp = 10200 WHERE level = 63; -- 21500
UPDATE `exp_base` SET exp = 10400 WHERE level = 64; -- 23000
UPDATE `exp_base` SET exp = 10600 WHERE level = 65; -- 24500
UPDATE `exp_base` SET exp = 10800 WHERE level = 66; -- 26000
UPDATE `exp_base` SET exp = 11000 WHERE level = 67; -- 27500
UPDATE `exp_base` SET exp = 11200 WHERE level = 68; -- 29000
UPDATE `exp_base` SET exp = 11400 WHERE level = 69; -- 30500
UPDATE `exp_base` SET exp = 11600 WHERE level = 70; -- 32000
UPDATE `exp_base` SET exp = 11800 WHERE level = 71; -- 34000
UPDATE `exp_base` SET exp = 12000 WHERE level = 72; -- 36000
UPDATE `exp_base` SET exp = 12200 WHERE level = 73; -- 38000
UPDATE `exp_base` SET exp = 12400 WHERE level = 74; -- 40000
UPDATE `exp_base` SET exp = 12600 WHERE level = 75; -- 42000
UPDATE `exp_base` SET exp = 12800 WHERE level = 76; -- 44000
