# Sequential implementation phases

| Phase | Implementation | Acceptance criterion |
| --- | --- | --- |
| 01 | Package and repository structure | Installable `src` package and CLI |
| 02 | Typed configuration | Invalid secrets and window limits fail startup |
| 03 | Dependency pins | Runtime and test versions specified explicitly |
| 04 | Shared Docker image | Training and serving run the same image |
| 05 | Environment fingerprint | Changed interpreter or packages rejects artifact |
| 06 | Feature schema | Four ordered, finite, bounded numeric features |
| 07 | Feature logging | Entire inference batch commits transactionally |
| 08 | Reproducible data | Bundled Iris data with fixed stratified split |
| 09 | Training input validation | NPZ data follows feature and class contract |
| 10 | Model training | Standardization and multinomial logistic regression |
| 11 | Evaluation | Held-out accuracy and log loss recorded |
| 12 | Promotion gate | Accuracy at least 0.90 and log loss at most 0.40 |
| 13 | Model registry | Content-addressed immutable JSON bundles |
| 14 | Integrity validation | Corruption and invalid dimensions fail startup |
| 15 | Reference distribution | Training-only reference rows accompany model |
| 16 | KS engine | Two-sample tests run independently per feature |
| 17 | Trigger policy | Any statistic strictly greater than 0.10 alerts |
| 18 | Report persistence | Unique model/window checkpoints prevent repeats |
| 19 | Alert outbox | Alert insertion and checkpoint share a transaction |
| 20 | Webhook transport | Bounded HTTPS retries and stable delivery keys |
| 21 | Inference service | Stable softmax and canonical class mapping |
| 22 | Health endpoints | Readiness checks model, database, and monitor |
| 23 | API controls | Constant-time key comparison and bounded payloads |
| 24 | Metrics | Request counts, duration sum, reports, pending alerts |
| 25 | Automated monitor | Complete windows processed during API lifecycle |
| 26 | Lifecycle CLI | Train, serve, monitor, and smoke commands |
| 27 | Automated tests | Boundaries, failures, restart recovery, HTTP contracts |
| 28 | CI automation | Container build followed by tests in that image |
| 29 | Release validation | Authenticated smoke inference within measured budget |
| 30 | Operations | Deployment, rollback, alert triage, and backup procedures |
Phase 2 verification update
Phase 3 verification update
Phase 4 verification update
Phase 5 verification update
Phase 6 verification update
Phase 7 verification update
Phase 8 verification update
Phase 9 verification update
Phase 10 verification update
Phase 11 verification update
Phase 12 verification update
Phase 13 verification update
Phase 14 verification update
Phase 15 verification update
Phase 16 verification update
Phase 17 verification update
Phase 18 verification update
Phase 19 verification update
Phase 20 verification update
Phase 21 verification update
Phase 22 verification update
Phase 23 verification update
Phase 24 verification update
Phase 25 verification update
Phase 26 verification update
Phase 27 verification update
Phase 28 verification update
Phase 29 verification update
Phase 30 verification update
