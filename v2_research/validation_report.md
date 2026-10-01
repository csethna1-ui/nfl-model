# V2 Validation Results — 2021–2022 (one run, frozen protocol)

Primary comparison on V2-defined games only (fallback games excluded).
Gates: G1 paired bootstrap p<0.05 & MAE<V1; G2 better both seasons; G3 |bias|<1.0 & slope∈[0.8,1.2]; G4 leakage audit; G5 err-corr<0.98; G6 timestamps. No ATS/ROI.

## V2-A (alpha=None, n=543, fallback=0)
- MAE: 10.5554 vs V1 10.0592 (diff -0.4962, 95% CI [-0.8371, -0.1557], p=0.0042)
- RMSE 13.5404, bias +1.1534, calib a=+1.2901 b=0.8025, err_sd 13.5036, pred-corr 0.2633, err-corr-v1 0.9471
- by season: 2021: 11.3264 vs V1 11.1393 (n=272); 2022: 9.7817 vs V1 8.9751 (n=271)
- gates: G1_paired_improvement=FAIL, G2_both_seasons=FAIL, G3_calibration=FAIL, G4_leakage_audit=PASS, G5_not_twin=PASS, G6_timestamps=PASS
- **GATES FAILED**

## V2-B (alpha=None, n=543, fallback=0)
- MAE: 10.573 vs V1 10.0592 (diff -0.5138, 95% CI [-0.8401, -0.1842], p=0.0018)
- RMSE 13.5159, bias +1.1575, calib a=+1.2919 b=0.8045, err_sd 13.4786, pred-corr 0.27, err-corr-v1 0.9508
- by season: 2021: 11.3653 vs V1 11.1393 (n=272); 2022: 9.7778 vs V1 8.9751 (n=271)
- gates: G1_paired_improvement=FAIL, G2_both_seasons=FAIL, G3_calibration=FAIL, G4_leakage_audit=PASS, G5_not_twin=PASS, G6_timestamps=PASS
- **GATES FAILED**

## V2-C (alpha=None, n=543, fallback=0)
- MAE: 10.3948 vs V1 10.0592 (diff -0.3356, 95% CI [-0.6374, -0.0440], p=0.0236)
- RMSE 13.3565, bias +1.2086, calib a=+1.2885 b=0.8746, err_sd 13.314, pred-corr 0.3051, err-corr-v1 0.9594
- by season: 2021: 11.21 vs V1 11.1393 (n=272); 2022: 9.5765 vs V1 8.9751 (n=271)
- gates: G1_paired_improvement=FAIL, G2_both_seasons=FAIL, G3_calibration=FAIL, G4_leakage_audit=PASS, G5_not_twin=PASS, G6_timestamps=PASS
- **GATES FAILED**

## V2-D (alpha=None, n=543, fallback=0)
- MAE: 10.6725 vs V1 10.0592 (diff -0.6133, 95% CI [-0.9484, -0.2757], p=0.0006)
- RMSE 13.6028, bias +1.1264, calib a=+1.3384 b=0.7051, err_sd 13.5686, pred-corr 0.2608, err-corr-v1 0.9463
- by season: 2021: 11.398 vs V1 11.1393 (n=272); 2022: 9.9444 vs V1 8.9751 (n=271)
- gates: G1_paired_improvement=FAIL, G2_both_seasons=FAIL, G3_calibration=FAIL, G4_leakage_audit=PASS, G5_not_twin=PASS, G6_timestamps=PASS
- **GATES FAILED**
