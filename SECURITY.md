# Security

easy-context-mcp indexes source code for local search. This page states what it protects and what it does not.

## Reporting a problem

Open a GitHub issue on `thunderkds/easy-context-mcp`. For a vulnerability you prefer not to post in public, contact the repository owner through the email on their GitHub profile.

## Confinement

- Every call is bound to exactly one project root. The server reads only files under that root.
- The root comes from the `X-Easy-Context-Root` header, the `root` argument, `EASY_CONTEXT_ROOT` (stdio) or the working directory (stdio). The server resolves it with `realpath` and walks up to the nearest ancestor that holds a `.git` file or directory. It never climbs to `$HOME` or above, unless you give `$HOME` itself.
- In the Docker service, the server accepts only roots inside `EASY_CONTEXT_WORKSPACE`. A root outside it is rejected. The workspace is mounted read-only.
- A `path` or `path_prefix` argument is resolved with `realpath` before use. A path that leaves the root (`..`, absolute path, symlink) is rejected.
- The server never executes indexed code. It reads files as text and parses them with tree-sitter.
- Slices from project A are not returned for a call bound to project B. `get_stats` with a `project_id` of another project returns counts, root and timestamps only, never slice text.

## Symlink policy

The server never follows or reads a symlink. A symlinked file or directory is skipped, whether it points inside or outside the root. This is stricter than needed on purpose.

## Secret-file policy

The server skips files with these names (case-insensitive, checked after `.gitignore`, so a `!.env` rule cannot unlock them): `.env`, `.env.*`, `*.pem`, `*.key`, `id_rsa*`, `id_dsa*`, `id_ecdsa*`, `id_ed25519*`, `credentials.json`, `credentials`, `*.p12`, `*.pfx`, `.netrc`, `_netrc`, `.pgpass`, `.npmrc`, `.pypirc`, `.git-credentials`, `.htpasswd`, `*.jks`, `*.keystore`, `*.kdbx`, `*.ppk`. It also skips binary files, files over `EASY_CONTEXT_MAX_FILE_BYTES` (default 512 KiB), files that `.gitignore` excludes, and nested git repositories. `get_stats` reports the count per skip reason.

## Limitation: hardcoded secrets are not detected

The server filters secret files by name. It does not scan the content of normal source files. A password, token or key written inside a `.py`, `.js`, `.md` or similar file is indexed and can come back in a search result. Keep secrets out of source files, or add the file to `.gitignore`.

## Service: loopback only, no authentication

The Docker service binds `127.0.0.1` only (host networking, so that is the host loopback). It has no authentication. While it runs, any local process of any user on the machine can call it and search every project that was indexed. Do not run it on a shared machine you do not trust. Do not expose its port.

The container runs as your user, with a read-only root file system, `cap_drop: ALL`, `no-new-privileges`, and a read-only workspace mount. The stdio compose service has no network at all.

## Network and telemetry

The server makes no network calls at run time and sends no telemetry. The embedding model is baked into the image or cached on disk. The one exception is the optional remote embedder (`EASY_CONTEXT_EMBED_BASE_URL`): when you set it, the server sends chunk text to that endpoint. It accepts only `https`, or `http` to a loopback host. The API key goes only in the `Authorization` header and never appears in error messages.
