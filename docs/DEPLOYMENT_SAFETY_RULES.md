# DEPLOYMENT SAFETY RULES — GitHub Ownership + Free Hosting Migration

Frozen 2026-10-01. Binding for the entire migration. These rules override convenience at every step.

## Absolute research protections (from the project owner)

1. DO NOT change V1 model methodology.
2. DO NOT change V1 weights.
3. DO NOT retrain V1.
4. DO NOT alter the locked 2023–2025 game-model test.
5. DO NOT modify the Vault.
6. DO NOT alter any preregistered experiment results.
7. DO NOT rerun experiments merely because deployment requires code changes.
8. DO NOT change Props Model D.
9. DO NOT retrain Props Model D.
10. DO NOT change Experiment 003A or 003B frozen artifacts.
11. DO NOT reopen completed NULL experiments.
12. DO NOT reinterpret research conclusions.
13. DO NOT modify historical predictions to make the website look better.
14. DO NOT modify prediction values manually.
15. DO NOT introduce new modeling features.
16. DO NOT introduce new data sources unless required purely for deployment.
17. DO NOT silently replace an existing data source.
18. DO NOT change timestamps, as-of dates, freeze logic, or research cutoffs.
19. DO NOT modify the research protocol.
20. DO NOT modify experiment preregistrations.
21. DO NOT modify experiment reports except where absolutely necessary to document deployment architecture.

Goal: SAME MODEL, SAME RESULTS, NEW OWNERSHIP, NEW HOSTING.

## Operational rules

- All migration work happens in a **staging copy** at `~/workspace/nfl-model-github/` (created by the migration; the live project at `~/workspace/nfl-model/` is never restructured, renamed, or edited in ways that could affect its outputs).
- Live crons (`nfl-picks-weekly-build`, `nfl-grading-tuesday`, `nfl-market-lines-hourly`, Tuesday snapshots) keep running against the ORIGINAL paths until the handoff report is reviewed and approved. The migration must not break the Friday pipeline.
- Baseline sha256 checksums of `data/ui_json/v1/*` are recorded BEFORE any migration change (`docs/DEPLOYMENT_BASELINE_CHECKSUMS.txt`).
- Any deployment adapter (path change, packaging change, export change) must be output-identical: same parsed values for every model artifact, verified by checksum comparison, not by eyeballing.
- If a deployment change could potentially affect a model output, STOP and report it. Never silently change it. Document the blocker before touching anything.
- Writing NEW files (docs, workflows, configs, staging copies) is allowed. Modifying frozen research files, locked test data, or the Vault is not.
- Nothing is pushed to GitHub until the owner explicitly approves the push step. Preparing the repo is not pushing the repo.
- No secrets, credentials, tokens, or private identifiers enter the staging copy or any commit. When in doubt, exclude and document.
