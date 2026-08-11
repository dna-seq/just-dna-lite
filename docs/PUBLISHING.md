# Publishing a Module to the Marketplace

How to register an account, claim a namespace, and publish an annotation module to the public
marketplace using the `marketplace-client` CLI (shipped with the `just-dna-marketplace` client
install).

Registration is self-service via a proof-of-work install-id. Namespaces are claimed separately —
an account does not get one automatically. Once you own a namespace you can publish spec
directories into it; the server recompiles and verifies each one, so `compile_success` and the
artifact digest are trusted.

## 0. Point the client at the public marketplace

```bash
export MARKETPLACE_URL=https://module-registry.just-dna.life
```

## 1. Register an account

Grinds a proof-of-work install-id (default 20 bits, a few seconds) and mints an API key. Pick a
lowercase account handle.

```bash
uv run marketplace-client register eric
```

It prints two lines you must keep:

```
install-id: <keep this to re-register / recover>
API key:    mk_live_xxxxxxxx
```

Export the key so publish/claim commands can authenticate:

```bash
export MARKETPLACE_TOKEN=mk_live_xxxxxxxx      # paste the printed key
```

To reuse an existing install-id instead of grinding a new one:

```bash
uv run marketplace-client register eric --install-id <id>
```

## 2. Claim a namespace

The namespace is not the same as your account name — it can be anything valid and free. Each
account may hold a small number (default 2).

```bash
uv run marketplace-client namespace-available eric-mods    # check it's free
uv run marketplace-client claim-namespace     eric-mods    # claim it (uses your token)
```

## 3. Publish the module

Args: `<namespace> <name> <version> <spec_dir>`. `spec_dir` is the authored spec folder
(`module_spec.yaml` + the CSVs, plus any logs) — **not** the compiled parquets. The server
recompiles server-side.

```bash
uv run marketplace-client publish eric-mods lactose-tolerance 1.0.0 ./lactose-tolerance \
  --changelog "Initial release: rs4988235 (MCM6/LCT) + rs182549 tag SNP; 5 verified PMIDs"
```

If all you have is a packaged `zip`/`tar.gz` archive rather than a spec directory, use
`import-module` instead:

```bash
uv run marketplace-client import-module eric-mods lactose-tolerance 1.0.0 ./lactose-tolerance.tar.gz \
  --changelog "Initial release"
```

## 4. Confirm it landed

```bash
uv run marketplace-client list --q lactose
```

## Publishing later versions

`update-module-version` enforces that the new version is greater than the current latest.

```bash
uv run marketplace-client update-module-version eric-mods lactose-tolerance 1.1.0 ./lactose-tolerance \
  --changelog "Refine weights; add rs182549 study"
```

## Metadata-only amendments (no version bump)

The artifact stays immutable, but you can update its changelog or logo:

```bash
uv run marketplace-client amend-changelog eric-mods lactose-tolerance 1.0.0 "Corrected PMID list"
uv run marketplace-client amend-logo      eric-mods lactose-tolerance 1.0.0 ./logo.png
```

## Notes

- **Keep both the install-id and the API key.** The key authenticates all publishes; the install-id
  lets you re-register or recover the account.
- If `marketplace-client` isn't found, run it from a `just-dna-marketplace` checkout with the
  `uv run` prefix shown above.
