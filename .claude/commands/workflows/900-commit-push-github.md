---
name: 900-commit-push-github
auto_execution_mode: 3
---
1. Identify all new and modified files, stage them, create a single commit with a descriptive message, and push to the remote GitHub repository. Include updates from all initialized submodules. Do not leave uncommitted changes.
2. Verify that the GitHub Actions tests pass for the repository.
3. Verify that the repository is updated with the latest changes.
4. Build and push Docker images to the private registry `aiutox-nas.tail2a2cda.ts.net:5010` by running the `/910-rotate-docker-tags` workflow, which covers:
   a. Build and push new images (backend + frontend) with `latest` and `<sha>` tags via `.\scripts\50-deploy\build-and-deploy.ps1`.
   b. Rotate registry tags — keep max 3 sha-versioned tags, delete oldest — via `.\scripts\50-deploy\rotate-registry-tags.ps1`.
   c. Verify registry state: both backend and frontend images must show `["latest", "<sha1>", "<sha2>", "<sha3>"]` (4 entries max).