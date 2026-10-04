# Post-hoc Idea 8: fade vs follow leg reconciliation

## 2026-10-04 04:12 ET (x = 0.2, from committed training outputs 1e241e6; no rerun, no number changed)

Diagnostic only. Skip reasons for the missing legs were recomputed read-only with the committed script's
evaluate_game (4217cce) on those 141 games only; nothing was written to the results files.

**Finding: no bug.** The legs are consistent game by game. The trade count gap and the mean-I and mean-fill
differences come from games where only one leg filled, which are concentrated in lopsided games.

### 1. Games with one leg only

- Follow trade, no fade trade: 115 games. Fade skip reason: no trade within 5 min 82, fill at 0.99 33, other 0.
- Fade trade, no follow trade: 26 games. Follow skip reason: no trade within 5 min 25, fill at 0.99 1, other 0.
- Net gap 115 - 26 = 89 = 881 - 792.
- The 115 follow-only games are lopsided: mean I -0.713, mean follow fill 0.133. Pressure is on the heavy
  favorite, so the fade leg must buy that favorite at about 0.87 or more. Either the fill would be 0.99 (33) or the
  favorite's market had no trade in [t + 1 s, t + 301 s] (82). The fade-only games have mean fade fill 0.350.
- These 141 games explain the all-entered differences: mean I -0.122 (fade) vs -0.211 (follow), and mean fills
  0.529 + 0.449 = 0.978. The follow leg includes 115 cheap-underdog fills that the fade leg lacks.

### 2. Games where both legs traded (766)

- Both legs bought the same team: 0.
- Mean I: fade -0.13578, follow -0.13578 (identical in every game; max abs difference 0).
- Mean fade fill + mean follow fill: 1.0320 (per-game sum median 1.03), within the expected 1.02 to 1.04.

### 3. Hand checks (game_id is away_home; I >= 0.2 -> fade buys away, I <= -0.2 -> fade buys home)

| game | I | fade team, fill, payout | follow team, fill, payout | check |
|---|---|---|---|---|
| cfb_20250823_fres_ku | +0.4869 | FRES (away), 0.18, 0 | KU (home), 0.85, 1 | fade = away: correct; fills sum 1.03 |
| cfb_20251003_wku_del | -0.2265 | DEL (home), 0.58, 0 | WKU (away), 0.45, 1 | fade = home: correct; 1.03 |
| cfb_20251101_duke_clem | -0.6546 | CLEM (home), 0.64, 0 | DUKE (away), 0.40, 1 | fade = home: correct; 1.04 |
| cfb_20251123_csu_bsu | +0.9928 | CSU (away), 0.13, 0 | BSU (home), 0.89, 1 | fade = away: correct; 1.02 |
| nfl_20250921_ari_sf | +0.2780 | ARI (away), 0.49, 0 | SF (home), 0.54, 1 | fade = away: correct; 1.03 |

Payouts in each game are complementary (0 and 1), as expected from one Kalshi settlement.

### Implication for reading the table

The fade and follow rows are not computed on the same game set: follow includes 115 lopsided games where it buys
a cheap underdog, and fade excludes them. A same-game comparison would restrict both legs to the 766 games where
both traded. That comparison is not part of the committed results and was not run.

### Game lists

Follow trade, no fade trade (115); reason the fade leg skipped:

- cfb_20250823_shsu_wku: no post-decision trade (fade team WKU, I -0.3989)
- cfb_20250828_dsu_del: no post-decision trade (fade team DEL, I -0.968)
- cfb_20250828_elon_duke: no post-decision trade (fade team DUKE, I -1.0)
- cfb_20250828_sfpa_ulm: no post-decision trade (fade team ULM, I -0.8303)
- cfb_20250829_alst_uab: no post-decision trade (fade team UAB, I -0.2445)
- cfb_20250829_ston_sdsu: no post-decision trade (fade team SDSU, I -0.6882)
- cfb_20250829_wag_ku: fill at 0.99 (fade team KU, I -0.9983)
- cfb_20250829_wiu_ill: no post-decision trade (fade team ILL, I -0.9342)
- cfb_20250830_aamu_ark: no post-decision trade (fade team ARK, I -0.9223)
- cfb_20250830_alby_iowa: no post-decision trade (fade team IOWA, I -0.9809)
- cfb_20250830_arpb_ttu: no post-decision trade (fade team TTU, I -1.0)
- cfb_20250830_ccsu_conn: no post-decision trade (fade team CONN, I -1.0)
- cfb_20250830_chso_van: no post-decision trade (fade team VAN, I -0.9732)
- cfb_20250830_duq_pitt: no post-decision trade (fade team PITT, I -1.0)
- cfb_20250830_eky_lou: fill at 0.99 (fade team LOU, I -0.9983)
- cfb_20250830_for_bc: no post-decision trade (fade team BC, I -0.7397)
- cfb_20250830_gast_miss: no post-decision trade (fade team MISS, I -1.0)
- cfb_20250830_ilst_okla: fill at 0.99 (fade team OKLA, I -0.987)
- cfb_20250830_liu_fla: no post-decision trade (fade team FLA, I -1.0)
- cfb_20250830_mrsh_uga: no post-decision trade (fade team UGA, I -0.8361)
- cfb_20250830_mtst_ore: fill at 0.99 (fade team ORE, I -0.7937)
- cfb_20250830_nev_psu: fill at 0.99 (fade team PSU, I -1.0)
- cfb_20250830_unlv_shsu: no post-decision trade (fade team SHSU, I -0.9668)
- cfb_20250830_unm_mich: no post-decision trade (fade team MICH, I -0.731)
- cfb_20250830_vmi_navy: no post-decision trade (fade team NAVY, I -1.0)
- cfb_20250831_idho_wsu: no post-decision trade (fade team WSU, I -0.9875)
- cfb_20250831_prst_byu: no post-decision trade (fade team BYU, I -1.0)
- cfb_20250831_tamc_smu: no post-decision trade (fade team SMU, I -1.0)
- cfb_20250905_wiu_nw: no post-decision trade (fade team NW, I -1.0)
- cfb_20250906_akr_neb: no post-decision trade (fade team NEB, I -0.4188)
- cfb_20250906_ball_aub: no post-decision trade (fade team AUB, I -1.0)
- cfb_20250906_cook_mia: no post-decision trade (fade team MIA, I -1.0)
- cfb_20250906_etsu_tenn: fill at 0.99 (fade team TENN, I -0.3891)
- cfb_20250906_ewu_bsu: no post-decision trade (fade team BSU, I -0.5757)
- cfb_20250906_fiu_psu: no post-decision trade (fade team PSU, I -0.9881)
- cfb_20250906_gram_osu: no post-decision trade (fade team OSU, I -1.0)
- cfb_20250906_kent_ttu: fill at 0.99 (fade team TTU, I -1.0)
- cfb_20250906_lib_jvst: no post-decision trade (fade team JVST, I -0.4891)
- cfb_20250906_linw_app: fill at 0.99 (fade team APP, I -1.0)
- cfb_20250906_ncat_ucf: no post-decision trade (fade team UCF, I -0.6758)
- cfb_20250906_nwst_minn: fill at 0.99 (fade team MINN, I -1.0)
- cfb_20250906_okst_ore: fill at 0.99 (fade team ORE, I -0.498)
- cfb_20250906_peay_uga: no post-decision trade (fade team UGA, I -1.0)
- cfb_20250906_scst_scar: no post-decision trade (fade team SCAR, I -0.7302)
- cfb_20250906_sjsu_tex: fill at 0.99 (fade team TEX, I -0.9912)
- cfb_20250906_tamc_fsu: no post-decision trade (fade team FSU, I -1.0)
- cfb_20250906_troy_clem: fill at 0.99 (fade team CLEM, I -0.9834)
- cfb_20250906_txso_cal: no post-decision trade (fade team CAL, I -1.0)
- cfb_20250906_ulm_ala: no post-decision trade (fade team ALA, I -0.3394)
- cfb_20250907_ucd_wash: no post-decision trade (fade team WASH, I -0.916)
- cfb_20250912_colg_syr: fill at 0.99 (fade team SYR, I -0.9275)
- cfb_20250912_inst_ind: fill at 0.99 (fade team IND, I -0.8372)
- cfb_20250913_alcn_msst: no post-decision trade (fade team MSST, I -1.0)
- cfb_20250913_ecu_ccar: no post-decision trade (fade team CCAR, I -1.0)
- cfb_20250913_fau_fiu: no post-decision trade (fade team FIU, I -0.8093)
- cfb_20250913_hcu_neb: no post-decision trade (fade team NEB, I -1.0)
- cfb_20250913_mass_iowa: no post-decision trade (fade team IOWA, I -1.0)
- cfb_20250913_morg_tol: no post-decision trade (fade team TOL, I -0.3045)
- cfb_20250913_nwst_cin: no post-decision trade (fade team CIN, I -0.8857)
- cfb_20250913_ohio_osu: fill at 0.99 (fade team OSU, I -0.9856)
- cfb_20250913_sam_bay: no post-decision trade (fade team BAY, I -1.0)
- cfb_20250913_smu_mosu: fill at 0.99 (fade team SMU, I 0.8839)
- cfb_20250913_tows_md: no post-decision trade (fade team MD, I -0.5673)
- cfb_20250913_vill_psu: no post-decision trade (fade team PSU, I -1.0)
- cfb_20250914_ac_tcu: no post-decision trade (fade team TCU, I -0.701)
- cfb_20250914_navy_tlsa: no post-decision trade (fade team NAVY, I 0.6375)
- cfb_20250914_prst_haw: fill at 0.99 (fade team HAW, I -0.7817)
- cfb_20250914_sou_fres: no post-decision trade (fade team FRES, I -1.0)
- cfb_20250920_ball_conn: no post-decision trade (fade team CONN, I -0.6158)
- cfb_20250920_idho_sjsu: no post-decision trade (fade team SJSU, I -0.9294)
- cfb_20250920_kent_fsu: fill at 0.99 (fade team FSU, I -1.0)
- cfb_20250920_mrsh_mtu: no post-decision trade (fade team MTU, I -0.9554)
- cfb_20250920_murr_jvst: no post-decision trade (fade team JVST, I -0.2701)
- cfb_20250920_orst_ore: fill at 0.99 (fade team ORE, I -0.8584)
- cfb_20250920_scst_usf: fill at 0.99 (fade team USF, I -0.8674)
- cfb_20250920_sela_lsu: no post-decision trade (fade team LSU, I -1.0)
- cfb_20250920_tem_gt: no post-decision trade (fade team GT, I -0.7701)
- cfb_20250920_uab_tenn: no post-decision trade (fade team TENN, I -0.9804)
- cfb_20250920_ull_emu: no post-decision trade (fade team ULL, I 0.532)
- cfb_20250927_akr_tol: no post-decision trade (fade team TOL, I -1.0)
- cfb_20250927_gaso_jmu: no post-decision trade (fade team JMU, I -1.0)
- cfb_20250927_mass_mizz: fill at 0.99 (fade team MIZZ, I -0.9831)
- cfb_20250927_uri_wmu: no post-decision trade (fade team WMU, I -0.9432)
- cfb_20250928_mrsh_ull: no post-decision trade (fade team ULL, I -1.0)
- cfb_20251004_camp_ncst: no post-decision trade (fade team NCST, I -0.5214)
- cfb_20251004_cmu_akr: no post-decision trade (fade team AKR, I -0.9884)
- cfb_20251004_kent_okla: fill at 0.99 (fade team OKLA, I -0.6637)
- cfb_20251004_utsa_tem: no post-decision trade (fade team TEM, I -0.4475)
- cfb_20251011_mass_kent: no post-decision trade (fade team MASS, I 0.6347)
- cfb_20251011_rice_utsa: no post-decision trade (fade team UTSA, I -0.7851)
- cfb_20251018_kent_tol: no post-decision trade (fade team TOL, I -0.9995)
- cfb_20251018_utsa_unt: no post-decision trade (fade team UTSA, I 0.6079)
- cfb_20251025_okst_ttu: fill at 0.99 (fade team TTU, I -0.9995)
- cfb_20251025_wis_ore: fill at 0.99 (fade team ORE, I -0.8098)
- cfb_20251101_nd_bc: fill at 0.99 (fade team ND, I 0.6266)
- cfb_20251108_char_ecu: no post-decision trade (fade team ECU, I -0.9605)
- cfb_20251108_cit_miss: no post-decision trade (fade team MISS, I -1.0)
- cfb_20251108_osu_pur: fill at 0.99 (fade team OSU, I 0.9465)
- cfb_20251108_syr_mia: no post-decision trade (fade team MIA, I -0.7344)
- cfb_20251115_ccar_gaso: no post-decision trade (fade team GASO, I -0.2082)
- cfb_20251115_mrsh_gast: no post-decision trade (fade team GAST, I -0.75)
- cfb_20251115_nmsu_tenn: fill at 0.99 (fade team TENN, I -0.9958)
- cfb_20251115_sjsu_nev: no post-decision trade (fade team NEV, I -0.2468)
- cfb_20251116_ucla_osu: fill at 0.99 (fade team OSU, I -0.5221)
- cfb_20251119_mass_ohio: fill at 0.99 (fade team OHIO, I -0.8422)
- cfb_20251122_char_uga: fill at 0.99 (fade team UGA, I -1.0)
- cfb_20251122_eiu_ala: no post-decision trade (fade team ALA, I -1.0)
- cfb_20251122_fur_clem: no post-decision trade (fade team CLEM, I -0.8914)
- cfb_20251122_gast_troy: no post-decision trade (fade team GAST, I 0.9981)
- cfb_20251122_rutg_osu: fill at 0.99 (fade team OSU, I -0.9197)
- cfb_20251122_sam_txam: no post-decision trade (fade team TXAM, I -1.0)
- cfb_20251122_syr_nd: fill at 0.99 (fade team ND, I -0.9998)
- cfb_20251129_gast_odu: no post-decision trade (fade team ODU, I -0.9727)
- cfb_20251130_nd_stan: fill at 0.99 (fade team ND, I 0.7049)
- nfl_20250815_ten_atl: no post-decision trade (fade team TEN, I 0.6141)

Fade trade, no follow trade (26); reason the follow leg skipped:

- cfb_20250830_hc_niu: no post-decision trade (follow team NIU, I 0.9857)
- cfb_20250906_camp_ecu: no post-decision trade (follow team ECU, I 1.0)
- cfb_20250906_cp_utah: no post-decision trade (follow team UTAH, I 0.2934)
- cfb_20250906_gaso_usc: fill at 0.99 (follow team USC, I 0.8337)
- cfb_20250906_idst_unm: no post-decision trade (follow team UNM, I 0.7345)
- cfb_20250906_mtu_wis: no post-decision trade (follow team WIS, I 0.4157)
- cfb_20250906_nccu_odu: no post-decision trade (follow team ODU, I 1.0)
- cfb_20250906_tuln_usa: no post-decision trade (follow team USA, I 0.781)
- cfb_20250906_webb_gt: no post-decision trade (follow team GT, I 0.3679)
- cfb_20250913_jvst_gaso: no post-decision trade (follow team JVST, I -0.9461)
- cfb_20250913_norf_rutg: no post-decision trade (follow team RUTG, I 0.6963)
- cfb_20250913_ull_mizz: no post-decision trade (follow team ULL, I -0.7039)
- cfb_20250913_unh_ball: no post-decision trade (follow team UNH, I -0.4374)
- cfb_20250920_webb_ohio: no post-decision trade (follow team OHIO, I 0.2914)
- cfb_20250927_tuln_tlsa: no post-decision trade (follow team TLSA, I 0.9938)
- cfb_20251004_ohio_ball: no post-decision trade (follow team BALL, I 0.7919)
- cfb_20251005_tlsa_mem: no post-decision trade (follow team MEM, I 0.4277)
- cfb_20251010_usm_gaso: no post-decision trade (follow team GASO, I 0.3867)
- cfb_20251011_odu_mrsh: no post-decision trade (follow team ODU, I -0.7105)
- cfb_20251018_buff_mass: no post-decision trade (follow team BUFF, I -0.3714)
- cfb_20251018_tem_char: no post-decision trade (follow team CHAR, I 1.0)
- cfb_20251018_wyo_afa: no post-decision trade (follow team WYO, I -0.6652)
- cfb_20251122_ulm_txst: no post-decision trade (follow team TXST, I 0.7592)
- nfl_20250823_chi_kc: no post-decision trade (follow team CHI, I -0.727)
- nfl_20250823_la_cle: no post-decision trade (follow team CLE, I 0.8135)
- nfl_20250824_lac_sf: no post-decision trade (follow team LAC, I -0.4752)
