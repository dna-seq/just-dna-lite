# Getting a Registry Account and API Token

You need an account only to **publish** a module, so other people can install it from the catalog.
Browsing the catalog, downloading modules, building a module, and annotating a genome do not need one.

There is no account form in the app. Module Creator does not have one. The catalog's Publication
tab, which would hold an Account pane, is turned off. Create the account with one of the two
commands below.

## The two commands

Open a terminal in the just-dna-lite folder. That is the folder that contains `pyproject.toml`
and `modules.yaml`, the same folder where you run `uv run start`.

Change `your-name` before you run either command. Use lowercase letters, digits, and hyphens only.
`livia-zaharia` is accepted. `Livia_Zaharia` is rejected.

The two servers do not share accounts. A token from one is rejected by the other. Run the command
for the server you are publishing to. Run both if you want an account on each.

On macOS or Linux, replace `.\.venv\Scripts\python.exe -m just_dna_lite.cli` with `uv run pipelines`.

### Main catalog

This is the public catalog, `https://module-registry.just-dna.life`. Modules published here are
what other people install. A published module is not deleted.

```powershell
.\.venv\Scripts\python.exe -m just_dna_lite.cli registry register your-name --url https://module-registry.just-dna.life
```

The command prints `install-id` and `API key` once. Save both. Open `.env` in that same folder
(copy `.env.template` to `.env` if you do not have one yet) and add the API key on this line:

```
REGISTRY_TOKEN=paste-the-api-key-here
```

### Test server

This is the practice catalog, `https://module-polygon.just-dna.life`. What you publish here can
be removed.

```powershell
.\.venv\Scripts\python.exe -m just_dna_lite.cli registry register your-name --url https://module-polygon.just-dna.life
```

Save this API key on its own line. Do not put the test key in `REGISTRY_TOKEN`.

```
REGISTRY_TOKEN_POLYGON=paste-the-api-key-here
```

If you already registered on the main catalog, pass that install-id so this is the same account
name on the test server:

```powershell
.\.venv\Scripts\python.exe -m just_dna_lite.cli registry register your-name --install-id PASTE-INSTALL-ID --url https://module-polygon.just-dna.life
```

The install-id is the only way to get an account back. There is no email, no password, and nobody
who can reset it. Running the command again without `--install-id` creates a different account.

Either command creates the account only. It does not publish a module and it does not claim a
namespace (the folder name modules are published under). Claiming is a later command, below.

The rest of this page writes out where `.env` lives and what to do when a message comes back.

## Do I need this at all?

Only if you want to **put something into** the catalog.

| You want to... | Account needed? |
|---|---|
| Browse the catalog, download modules, annotate your genome | No |
| Build a module and run it on your own genome | No |
| Publish a module so other people can install it | **Yes** |
| Claim a namespace (your own "folder" in the catalog) | **Yes** |
| Ask the server to validate or dry-run your module before publishing | **Yes** |

If you only want to use modules, ignore the two commands above. Nothing else on this page is required.

## The four things you will get

It helps to know the words before you start.

- **Account.** Who you are on the catalog server. There is no email and no password. The
  account is created by your computer and identified by the next two items.
- **API token** (also called an API key). A long secret string. Every time you publish, the
  program sends it to the server to prove it is you. Treat it like a password.
- **Install-id.** A second secret string, created once on your computer. It is your **only
  way to recover the account** if you lose the token. There is no "forgot password" link and
  no administrator who can reset it, so keep a copy.
- **Namespace.** The name your modules are published under, for example
  `livia-zaharia/diabetes_genetics`. You claim it once, and **a claim on the public catalog
  is permanent**, so pick something you are happy to keep.

Naming rules, which the server enforces:

- Account and namespace: lowercase letters, digits and single hyphens (`livia-zaharia`).
  Underscores are rejected.
- Module name: lowercase letters, digits and underscores (`diabetes_genetics`). Hyphens are
  rejected.

## Two servers, two separate accounts

| | Test server ("polygon") | Public catalog ("production") |
|---|---|---|
| Address | `https://module-polygon.just-dna.life` | `https://module-registry.just-dna.life` |
| What it is for | Practising. You can delete what you publish. | The real catalog everyone installs from. |
| Can you delete a published module? | Yes | **No.** You can hide a version, but it is never removed. |
| Token variable in `.env` | `REGISTRY_TOKEN_POLYGON` | `REGISTRY_TOKEN` |

The two servers share nothing. An account, a token and a namespace on one do not exist on the
other, so if you use both you register twice and get two tokens. A token from one server is
simply rejected by the other.

If this is your first module, practise on the test server first. On the test server, put
`test-` in front of the namespace and `test_` in front of the module name (for example
`test-livia/test_diabetes_genetics`) so the operators' clean-up job can find and remove it.
The public catalog refuses those prefixes.

## Where the `.env` file goes

**In the root folder of the just-dna-lite copy you run the app from.** That is the folder that
contains `pyproject.toml`, `modules.yaml` and `.env.template`, and where you type
`uv run start`. For example:

```
just-dna-lite/            <- .env goes HERE
├── .env.template
├── modules.yaml
├── pyproject.toml
├── just-dna-pipelines/   <- not here
├── webui/                <- not here
└── data/
```

- Not in `webui/` or `just-dna-pipelines/`. Both the app and the command line read the file
  from the root folder.
- Not in any other repository (`just-prs`, `just-dna-format`, the marketplace repo and so on).
  They do not read this file.
- If you have several copies of just-dna-lite on your computer, it is the copy you actually
  run commands in. Each copy has its own `.env`.

To check you are in the right place, run this in the terminal. It should print `True`:

```powershell
Test-Path .\modules.yaml
```

If there is no `.env` yet, make one from the template:

```powershell
Copy-Item .env.template .env
```

```bash
cp .env.template .env
```

`.env` is already listed in `.gitignore`, so git will not commit it. Never paste the token or
the install-id into a module, a commit, an issue, a chat or a screenshot.

> Using the **just-module-creator** plugin for Claude as well? It uses its own variable names
> (`JMC_INSTALL_ID`, `JMC_API_KEY` for production, `JMC_TEST_API_KEY` for the test server) and
> has its own setup. This guide covers just-dna-lite only.

## There is no account form in the app

Do not look for an Account pane in Module Creator or on the Module Catalog page. The Publication
tab that contains that pane is switched off (`REGISTRY_PUBLICATION_ENABLED` is `False` in
`webui/src/webui/features.py`). Browsing and installing modules still work. Creating an account
from the screen does not, until that flag is turned back on.

Use the command at the top of this page.

## Create the account from the command line

Run every command from the just-dna-lite root folder.

On Windows, use `.\.venv\Scripts\python.exe -m just_dna_lite.cli` where the examples say
`uv run pipelines`. It does the same thing, and it still works on locked-down laptops that block
the `.exe` wrappers uv creates.

### Step 1. Register

Pick an account name and choose the server with `--url`.

Public catalog:

```bash
uv run pipelines registry register livia-zaharia --url https://module-registry.just-dna.life
```

Test server:

```bash
uv run pipelines registry register livia-zaharia --url https://module-polygon.just-dna.life
```

This takes a few seconds while your computer does a small proof-of-work puzzle, which is how
the server limits spam without asking for an email. It then prints two things: your
**install-id** and your **API key**. Both are printed only once.

If you already have an install-id (for example you registered on the test server and now want
the public catalog, or the app created one for you), reuse it so both accounts are recognisably
yours:

```bash
uv run pipelines registry register livia-zaharia --install-id <your-install-id> --url https://module-registry.just-dna.life
```

On Windows you can take the install-id straight from the app's identity file, so it never has
to be copied by hand:

```powershell
$iid = (Get-Content data\interim\registry_identity.json -Raw | ConvertFrom-Json).install_id; .\.venv\Scripts\python.exe -m just_dna_lite.cli registry register livia-zaharia --install-id $iid --url https://module-registry.just-dna.life
```

### Step 2. Keep the install-id somewhere safe

Put it in your password manager. If you lose the token, registering again **with the same
install-id** gives you a new token for the same account. Registering again **without** it
creates a brand-new, different account, and your namespaces stay with the old one, which you
can no longer reach.

Registering again always issues a fresh token. The most recent one is the one that works.

### Step 3. Save the token in `.env`

Open `.env` in the just-dna-lite root folder and add the lines for the server you registered on.

Public catalog:

```
REGISTRY_URL=https://module-registry.just-dna.life
REGISTRY_TOKEN=paste-the-api-key-here
```

Test server:

```
REGISTRY_TOKEN_POLYGON=paste-the-test-api-key-here
```

`REGISTRY_URL` decides which server the command line talks to by default, and which server the
app's catalog page opens on. Leave it pointing at the public catalog unless you are working
mainly on the test server.

Keep the two tokens in their own variables. Putting the test server's token in `REGISTRY_TOKEN`
produces a confusing `403 insufficient_capability` error from the public catalog, which looks
like a permissions problem rather than the wrong key.

The command line reads `REGISTRY_TOKEN` automatically. For the test server, pass its token and
address explicitly:

```powershell
.\.venv\Scripts\python.exe -m just_dna_lite.cli registry validate test-livia test_my_module path\to\spec --url https://module-polygon.just-dna.life --token $env:REGISTRY_TOKEN_POLYGON
```

(`$env:REGISTRY_TOKEN_POLYGON` only has a value in your terminal if you set it there. Otherwise,
paste the token into the command in your own terminal, not into a document.)

### Step 4. Check that it works

These two commands need no token and are safe to run as often as you like:

```bash
uv run pipelines registry version
uv run pipelines registry namespace-available livia-zaharia
```

`version` should report the server as contract-compatible. `namespace-available` says whether
the name is free.

The first command that actually tests your token is a server-side validation of one of your
modules. It publishes nothing:

```bash
uv run pipelines registry validate livia-zaharia diabetes_genetics data/interim/registered_modules/diabetes_genetics
```

If this says the token was rejected, the usual cause is a token from the other server, or an
old token replaced by a later registration.

### Step 5. Claim your namespace

```bash
uv run pipelines registry claim-namespace livia-zaharia
```

On the public catalog **this cannot be undone**. Check the spelling first.

From here, publishing is covered in [PUBLISHING.md](PUBLISHING.md).

## Common problems

| Message or symptom | What it usually means |
|---|---|
| `a token is required (pass --token or set $REGISTRY_TOKEN)` | `.env` is missing, in the wrong folder, or does not contain `REGISTRY_TOKEN`. Check that you are in the just-dna-lite root folder. |
| `the registry rejected your token` | Wrong server's token, or an older token replaced by a newer registration. |
| `403 insufficient_capability` on the public catalog | The test server's token was saved in `REGISTRY_TOKEN`. |
| `422 test_data_on_prod` | A `test-` namespace or `test_` module name was sent to the public catalog. |
| The namespace name is rejected | Uppercase letters or underscores. Use lowercase letters, digits and hyphens. |
| `uv run` fails with "being used by another process" on Windows | The running app is holding a file in uv's cache. Stop the app, or use `.\.venv\Scripts\python.exe -m just_dna_lite.cli` instead. |
| Lost the token | Register again with the same `--install-id` to get a new token for the same account. |
| Lost the install-id and the token | The account cannot be recovered. Register a new account and claim a new namespace. |
