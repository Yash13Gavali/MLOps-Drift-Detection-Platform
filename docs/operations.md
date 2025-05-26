# Operational runbook

## Release procedure

1. Run the GitHub Actions validation workflow and inspect test and inference timing results.
2. Download the validated container artifact and load it with `docker load`. Transfer this exact image into your controlled registry; resolve and record its immutable digest in the release system.
3. Set `PLATFORM_IMAGE` to that digest and supply `API_KEY` through the deployment secret manager. Restrict access to the data volume and webhook destination.
4. Train inside that image using `drift-platform train --root /data`. For custom input mount a read-only NPZ and pass `--dataset` with its container path. Training rejects unsupported schemas and weak candidates before promotion.
5. Start the API, check readiness, run `drift-platform smoke`, then route traffic through the TLS ingress. Keep the prior image and data backup until validation completes.

The release workflow validates deployment locally on its runner. Infrastructure deployment requires an operator-supplied target, registry credentials, secret manager, and traffic-routing configuration. The five-minute gate measures training plus service startup plus validated inference after image construction.

## Drift response

Inspect `GET /drift`, especially feature statistics and sample counts. A statistic above 0.10 triggers regardless of the p-value. Discrete measurements, sample size, and repeated monitoring affect false-alarm rates; calibrate the reference data and window size against accepted operating data while preserving the specified threshold.

Check schema changes, upstream transformations, sensor failures, and population changes. Drift does not establish model accuracy degradation. Obtain labels and evaluate a candidate on representative held-out data before promotion. Do not automatically retrain on untrusted anomalous traffic.

## Alert delivery

Reports and pending webhook payloads commit atomically. Delivery is at least once: a crash after receiver acceptance can lead to redelivery. Consumers must deduplicate the `Idempotency-Key` header within this database's lifetime. Use a separate endpoint or receiver namespace per platform instance. Configure `ALERT_WEBHOOK` before relying on external notification; otherwise inspect the durable outbox through `/metrics` and `/drift`.

Failed delivery stays pending and retries in later cycles. Review application warnings, receiver availability, outbound HTTPS connectivity, and certificate trust. Redirects are disabled. An alert backlog can delay monitoring because delivery shares the worker; alarm on `alert_pending` and size worker capacity accordingly.

## Model rollback

Stop the serving process. Restore the previous known-good `active` pointer and its immutable bundle from the data backup, together with the matching image digest. Restart and run the smoke check before routing traffic. The active pointer is read at startup; an already-running process continues using its loaded model. Never edit bundle contents or bypass the environment check.

## Storage and recovery

SQLite runs with WAL and full synchronization on local persistent storage. Do not use a shared network filesystem or run multiple serving replicas against this volume. Use SQLite's backup API for an online consistent database copy, or stop the API and snapshot the entire volume. Preserve model bundles and `active` alongside the database. Restore into a separate volume and validate readiness and inference before cutover.

Feature observations are retained without automatic deletion. Set disk-capacity alerts and an organization-approved retention policy. Archive and prune only observations at or below each model's committed report checkpoint, after verifying backup recovery. A database write failure returns an inference error instead of silently dropping monitoring data.

## Capacity and security

The default worker consumes at most 200 observations per 30-second cycle; increase window size or reduce interval based on measured traffic. The API bounds each batch to 256 observations, bodies to 128 KiB, and active connections through Uvicorn's concurrency limit. Enforce slow-client deadlines, traffic quotas, TLS, and network allowlists at ingress. Run only one Uvicorn worker.

Rotate API secrets through controlled process restarts. Limit artifact volume writes to the trusted training process and serving identity. Checksums detect corruption; they are not signatures against a malicious writer. Promote only trusted images and restrict workflow modification rights. Pin a reviewed base-image digest in a controlled release process; the development Dockerfile uses an explicit version tag, which upstream can still republish.

## Diagnostics

Readiness failure can indicate database errors or a failed monitoring cycle. Inspect process logs and storage permissions. Startup failures commonly indicate a missing model, corrupt bundle, or environment mismatch; retrain using the deployment image instead of disabling checks. Prometheus inference counters are process-local and reset on restart; persisted report counts and alert backlog survive restarts.

Runtime records use sequence identifiers and model hashes without wall-clock metadata. Use the hosting platform's external log collection for incident correlation. The application does not store creation dates or update headers.
