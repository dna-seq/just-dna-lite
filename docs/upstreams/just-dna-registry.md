# Upstream ledger: just-dna-registry

Kept by the correspondence seat (`docs/seats/CORRESPONDENCE.md`).

- **Publishes:** PyPI
- **What we use:** the Catalog's client; it moves with the format pin, since a mismatched pair refuses to publish
- **Read mark:** 0.34.1, read 2026-11-19.
- **Last checked:** 2026-11-19 (release watcher baseline)

## Entries

### 0.30.0 to 0.34.0 (read 2026-11-19)

The floor moved to >=0.33.1 on `main` in da6311b. Branch `bump/just-dna-format` (4d71343) locks 0.34.0. 0.34.0 adds the server's deploy over the API and a one-line `registry-client deploy` refusal, and floors format at >=0.8.6. Nothing the catalog client calls changed. 0.34.1 (key rotation, a folder lock, a format floor of 0.8.9) is published on 2026-11-19 at 01:13Z; the branch now locks it (002fd99), and all 67 registry tests pass with the proxy unset. Registry tests: the 3 in `test_registry_error_messages.py` fail on this cluster with the proxy set, on 0.33.1 as well as 0.34.0, and pass 19/19 with it unset. Verdict: **bump handed to the lead**.
