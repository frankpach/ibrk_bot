---
name: 910-rotate-docker-tags
description: Rotate Docker image tags in registry — keep latest + max 3 versioned tags
---

## Registry info

- **Registry**: `aiutox-nas.tail2a2cda.ts.net:5010` (Generic Registry V2, self-hosted)
- **Backend image**: `aiutox-nas.tail2a2cda.ts.net:5010/aiutox/backend`
- **Frontend image**: `aiutox-nas.tail2a2cda.ts.net:5010/aiutox/frontend`
- **Tag format**: `<short-sha>` (7-char git commit hash, e.g. `c82733c`) + `latest`
- **Max versioned tags**: `3` sha-* tags per image (oldest removed automatically)

## Related scripts

- **`scripts/50-deploy/build-and-deploy.ps1`** — full deploy: build + push + git push (includes tests)
- **`scripts/50-deploy/rotate-and-push-registry-tags.ps1`** ← build, push and rotate tags (this workflow)

---

## Steps

### 1. Build and push new image (latest + sha tag)

Run the main deploy script to build the new image and push both tags:

```powershell
# Full build (backend + frontend)
.\scripts\50-deploy\build-and-deploy.ps1

# Backend only (skip tests for speed)
.\scripts\50-deploy\build-and-deploy.ps1 -BackendOnly -SkipTests
```

This pushes `aiutox-nas.tail2a2cda.ts.net:5010/aiutox/backend:latest` and `...:c82733c`.

### 2. Rotate tags — keep max 3 sha versions, delete oldest

```powershell
# Preview what would be deleted (safe)
.\scripts\50-deploy\rotate-registry-tags.ps1 -DryRun

# Execute rotation (backend + frontend)
.\scripts\50-deploy\rotate-registry-tags.ps1

# Backend only
.\scripts\50-deploy\rotate-registry-tags.ps1 -BackendOnly

# Custom max versions
.\scripts\50-deploy\rotate-registry-tags.ps1 -MaxVersions 5
```

The script:
1. Queries `GET /v2/aiutox/<image>/tags/list` from the registry
2. Filters sha tags (7-char hex)
3. Orders them by **git commit history** (newest first)
4. Keeps first 3, deletes the rest via `DELETE /v2/.../manifests/<digest>`

### 3. Verify registry state

```powershell
$REGISTRY = "aiutox-nas.tail2a2cda.ts.net:5010"
Invoke-RestMethod "http://$REGISTRY/v2/aiutox/backend/tags/list"
Invoke-RestMethod "http://$REGISTRY/v2/aiutox/frontend/tags/list"
```

Expected: `{ "tags": ["latest", "<sha1>", "<sha2>", "<sha3>"] }` — 4 entries max per image.

---

## Notes

- Registry must have delete enabled: `REGISTRY_STORAGE_DELETE_ENABLED=true` in its config
- The registry is accessible via Tailscale (`tail2a2cda.ts.net`) — must be connected to run this
- SHA ordering uses local `backend/` git history; ensure submodule is up to date before running
- No `gh` CLI or Docker Hub credentials needed — uses Docker Registry HTTP API v2 directly
