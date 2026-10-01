# Experiment 008 — Validation Report (frozen protocol, one run)

n=543 (2021–2022 REG). V1 MAE = 10.0592, V1 bias = +1.210.

## 008-A separate home/away scores
- MAE 10.3662 (Δ vs V1 -0.3071), RMSE 13.3566, bias +0.624
- calibration: intercept +0.837, slope 0.826; pred–actual corr 0.299; V1 error corr 0.961
- bootstrap: p=0.9803, 95% CI Δ [-0.6043353635521382, -0.014504533906273813]
- by season: 2021: cand 11.244 vs V1 11.139 (worse); 2022: cand 9.485 vs V1 8.975 (worse)
- by |pred|: lt3 (n=220): cand 9.497 vs V1 9.463; b3_7 (n=225): cand 10.247 vs V1 9.718; gt7 (n=98): cand 12.591 vs V1 12.181
- gates: G4_both_seasons=FAIL, G5_magnitude_2of3=FAIL, G6_bias_within_1_of_v1=PASS, G6_slope_in_range=PASS, G8_p_lt_0_05=FAIL, all_questionA_gates=FAIL

## 008-B quantile margin (median point forecast)
- MAE 10.0836 (Δ vs V1 -0.0244), RMSE 12.9693, bias +0.702
- calibration: intercept +0.876, slope 0.848; pred–actual corr 0.378; V1 error corr 0.995
- bootstrap: p=0.6591, 95% CI Δ [-0.13899767478988276, 0.09215098398551001]
- by season: 2021: cand 11.064 vs V1 11.139 (better); 2022: cand 9.099 vs V1 8.975 (worse)
- by |pred|: lt3 (n=193): cand 9.060 vs V1 9.109; b3_7 (n=199): cand 9.590 vs V1 9.604; gt7 (n=151): cand 12.042 vs V1 11.874
- coverage [q10,q90]: 0.805 (nominal 0.80); [q25,q75]: 0.517 (nominal 0.50)
- gates: G4_both_seasons=FAIL, G5_magnitude_2of3=PASS, G6_bias_within_1_of_v1=PASS, G6_slope_in_range=PASS, G8_p_lt_0_05=FAIL, all_questionA_gates=FAIL

## 008-C heteroskedastic (Question B only)
- MAE 10.0592 (Δ vs V1 +0.0000), RMSE 12.9494, bias +1.210
- calibration: intercept +1.246, slope 0.944; pred–actual corr 0.383; V1 error corr 1.000
- bootstrap: p=1.0000, 95% CI Δ [0.0, 0.0]
- by season: 2021: cand 11.139 vs V1 11.139 (worse); 2022: cand 8.975 vs V1 8.975 (worse)
- by |pred|: lt3 (n=219): cand 9.617 vs V1 9.617; b3_7 (n=204): cand 9.393 vs V1 9.393; gt7 (n=120): cand 11.998 vs V1 11.998
- log score: pred-σ -4.6317 vs const-σ -3.9731; 80% PI coverage 0.578
- gates: G4_both_seasons=FAIL, G5_magnitude_2of3=FAIL, G6_bias_within_1_of_v1=PASS, G6_slope_in_range=PASS, G8_p_lt_0_05=FAIL, all_questionA_gates=FAIL

## Gate verdict
- 008a: DOES NOT ADVANCE
- 008b: DOES NOT ADVANCE
- 008c: Question B only — cannot advance as margin predictor by protocol.
