---
name: release-conventions
description: Release pipeline and commit conventions (semantic-release types, release-suppressed scopes, release.yml and .releaserc.js chain, dev and main branching). Use when choosing a commit type or scope, or when reasoning about releases, CHANGELOG or generated catalog files.
---

<!-- Mirror: this skill also exists in kveld-extra-morphe-patches/.agents/skills (.claude/skills is a symlink to .agents/skills in each repo). When editing shared core guidance, replicate the change there. -->

# Semantic Release & CI/CD Lifecycle

## 1. Conventional Commits Standard

Automated semantic releases depend on commit messages adhering strictly to the conventional commits specification configured in `.releaserc.js`:

| Prefix | Semver Impact | Release Notes Section | Trigger Automated Release? |
| :--- | :--- | :--- | :--- |
| `feat:` | **Minor** (`x.Y.0`) | New Features | **Yes** |
| `fix:` | **Patch** (`x.x.Z`) | Bug Fixes | **Yes** |
| `perf:` | **Patch** (`x.x.Z`) | Improvements | **Yes** |
| `bump:` | **Patch** (`x.x.Z`) | Updated App Support | **Yes** |
| `build(Needs bump):` | **Patch** (`x.x.Z`) | Hidden | **Yes** |
| `refactor:` | None | Hidden | **No** |
| `chore:` | None | Hidden | **No** (Skipped) |
| `docs:` | None | Hidden | **No** (Skipped) |

### Release-Suppressed Scopes

`.releaserc.js` maps these scopes to `release: false` regardless of commit type and strips them from release notes: `harness`, `ci`, `test`, `tooling`, `scripts`, `docs`, `governance`, `agents`, `readme`, `github`, `release`, `repo`, `security`, `hygiene`, `git`, `changelog` (matched lowercase, Capitalized or UPPERCASE). `fix(harness): ...` or `feat(scripts): ...` therefore never publish a release. Use an app or `patches`/`shared` scope when a change must reach users; use a suppressed scope for tooling and documentation work that must not.

### Mandatory Atomic Commits Policy

Commit granularity (1 patch / 1 option / 1 fix = 1 commit, code and docs together) is defined in `AGENTS.md`, rule 14. Follow it exactly.

---

## 2. Release Pipeline Chain (`release.yml` & `.releaserc.js`)

When commits are pushed to `main` (stable release) or `dev` (experimental prerelease `vX.Y.Z-experimental.N`), the automated release pipeline executes:

1. **Commit Analysis**: Evaluates commit log since previous release tag (`@semantic-release/commit-analyzer`).
2. **Release Notes Generation**: Formats notes into sections based on conventional commit types (`@semantic-release/release-notes-generator`).
3. **Changelog & Bundle Generation**: `@MorpheApp/changelog` updates `CHANGELOG.md` and generates `patches-bundle.json`.
4. **Gradle Version Bump**: `gradle-semantic-release-plugin` syncs `gradle.properties`.
5. **Catalog & Readme Generation**: Executes prepare commands (`@semantic-release/exec`):
   - `./gradlew generatePatchesList`
   - Patches `patches-list.json` with next release version (`jq '.version="${nextRelease.version}"' patches-list.json`)
   - Generates updated README (`python3 .github/scripts/generate_patches_readme.py $GITHUB_REPOSITORY $GITHUB_REF_NAME patches-list.json README.md`)
   - Syncs contributors (`python3 .github/scripts/sync_contributors.py --repo $GITHUB_REPOSITORY`)
6. **Git Commit**: `@semantic-release/git` commits updated release assets (`.github/contributors.json`, `CHANGELOG.md`, `gradle.properties`, `patches-bundle.json`, `patches-list.json`, `README.md`) with message `chore: Release v${nextRelease.version} [skip ci]`.
7. **GitHub Release & Asset Publishing**: Attaches compiled standalone Morphe Patch Package (`patches/build/libs/patches-*.mpp`) to the GitHub Release (`@semantic-release/github`).
8. **Build Provenance Attestation**: Attests build provenance for `patches/build/libs/patches-*.mpp` via `actions/attest-build-provenance`.
9. **Telegram Broadcast**: Dispatches release tag, version, and notes via `python3 .github/scripts/notify_telegram.py`.
10. **Compilation Verification Fallback**: When semantic-release does not publish a new release (e.g. for `refactor`, `chore`, `docs`), CI executes `./gradlew :patches:buildAndroid --no-daemon` to ensure compilation integrity.

> **CRITICAL REMINDER**: Never manually edit or commit `patches-list.json`, `patches-bundle.json`, or `CHANGELOG.md`. These are generated, formatted, and committed strictly by CI during the automated release pipeline.

---

## 3. Branching Strategy

- Routine development happens on `dev`; `main` is the stable release line, touched ONLY by an explicit user-ordered promotion merge (`dev` into `main`, merge commit, never squash), and there is no PR workflow (`AGENTS.md`, rule 15).
- Automated stable releases trigger from `main`; pushes to `dev` produce experimental prereleases (`vX.Y.Z-experimental.N`).
- **Never force-push** after a release tag has been created.
