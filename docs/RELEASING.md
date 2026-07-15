# Release Procedure

The local repository and GitHub are redundant copies of the complete source history, but they have different roles: the local clone is the working/runtime copy; GitHub `main` is the durable public release authority. Unpushed local commits remain recoverable work, but only a commit present on GitHub `main` may be distributed. Each public skill is authored in `skills/<slug>/`; `registry.json` is the canonical source for its stable ID, display name, public version, platform targets, ClawHub package, and topics. README metadata is a validated human-facing mirror.

## Start And Finish In Sync

Before editing:

```bash
git status --short
git fetch origin
git pull --ff-only origin main
```

Never pull over uncommitted work. After finishing, validate, commit, push, and verify that local and GitHub resolve to the same commit:

```bash
git rev-parse HEAD
git ls-remote origin refs/heads/main
```

After a release, run the read-only distribution audit:

```bash
python3 tools/audit_distribution.py
```

The private `rithmic-signup` repository follows the same backup rule, but it is never copied into this public monorepo or any public Skill platform.

## Change Types

- Documentation-only changes: validate, commit, and push to `main`.
- Skill behavior, scripts, dependencies, or execution-contract changes: make the change on a short-lived branch, run tests, review the diff, then merge to `main`.
- Public releases: use the GitHub Actions workflow `Publish ClawHub skill`. A GitHub push does not publish ClawHub automatically. Always run a dry-run first, then publish the single selected skill after reviewing the result.

## Release Steps

1. Edit only the canonical public skill under `skills/<slug>/`.
2. Bump that skill's version with the alignment helper. It updates `registry.json` and the validated README display line together:

   ```bash
   python3 tools/bump_skill_version.py --skill <slug> --version <new-version>
   ```

   Do not put a version in `SKILL.md`, package files, or separate release notes.
   When the changed skill is one of the three video Flow dependencies, also run:

   ```bash
   python3 tools/sync_video_flow.py --write
   ```

   The Flow is an orchestration layer, not a copy of the component scripts. Its `flow.json` must lock the exact versions from `registry.json`.
3. Run local checks:

   ```bash
   python3 tools/validate_repo.py
   python3 tools/sync_video_flow.py --check
   python3 -m unittest discover -s tests
   python3 tools/release_skill.py --skill <slug> --changelog "<summary>" --dry-run
   ```

4. Commit and push. Wait for the GitHub `validate` workflow to pass.
5. In GitHub Actions, run `Publish ClawHub skill` with the same skill, a short changelog, and `dry_run=true`.
6. Review the dry-run result, then run the workflow again with `dry_run=false`.
7. The release tool rejects a dirty/unpushed commit, a reused version, a non-canonical package, or an identity mismatch. It reads the new ClawHub version back automatically. After the asynchronous scan finishes, the public page must show `Security audit Pass` before the release is considered complete.

## Platform Distribution

### GitHub

- Canonical public source and history. A release is invalid until the exact local commit exists on `origin/main` and CI passes.
- Never edit generated platform copies and copy them back over GitHub. Fix the canonical local files, then push again.

### ClawHub

- Versioned release registry. Publish one canonical `@aiaaaa4/<slug>` package at a time through GitHub Actions.
- The release workflow pins the ClawHub CLI, serializes releases per Skill, runs tests, rejects version reuse, and verifies the published identity.
- ClawHub is normally current within minutes because we explicitly publish after GitHub; this is controlled automation, not passive mirroring.

### skills.sh

- Installation runs such as `npx skills add aiaaaa4/ai-landing-skills --skill <slug>` clone the current public GitHub repository, so installation can receive current source immediately.
- Catalog pages, search, stored file snapshots, install counts, and partner audits are a separate asynchronous pipeline triggered by anonymous CLI telemetry. skills.sh publishes no refresh SLA. Its documented detail-page HTTP cache is about five minutes after ingestion, but ingestion and re-audit may take longer.
- After a release, trigger one isolated install outside the repository. Never run `--all` from this repository because the CLI may create Agent links in the working tree:

  ```bash
  temp_dir="$(mktemp -d)"
  (cd "$temp_dir" && npx --yes skills@latest add https://github.com/aiaaaa4/ai-landing-skills --skill <slug> --yes)
  rm -rf "$temp_dir"
  ```

- A stale skills.sh page does not roll back GitHub. Recheck later; review new Snyk/Socket/Gen findings when the snapshot date changes.

### SkillHub

- SkillHub states that it continuously synchronizes selected ClawHub Skills, but it publishes no timing guarantee and the mirror is not complete or reliably current.
- Do not treat the mirror as an automatic release channel. After signing in with WeChat/mobile and binding the creator account, use `发布 Skill` or the creator dashboard to update/claim the existing listing. Never create a second ClawHub package to work around a SkillHub slug collision.
- For an existing mirrored listing, update or claim that listing rather than creating a duplicate. If no claim/update control is available, submit the GitHub path, canonical ClawHub URL, expected version, and stale SkillHub version through [SkillHub feedback](https://wj.qq.com/s2/26026989/0c20).
- `video-translate` currently collides with another globally routed `video-translate` entry on SkillHub. Resolve that only inside SkillHub support/manual publishing; keep GitHub ID `aiaaaa4.video-translate` and ClawHub package `@aiaaaa4/video-translate` unchanged.

### SkillsMP And Other Crawlers

- Discovery channels, not release authorities. Let them crawl GitHub and link users back to the canonical repository.

## Security Feedback Policy

- Treat scanner output as engineering input, not a badge to silence. Remove undeclared package installation, arbitrary endpoints, dynamic execution, broad file access, and missing consent.
- ClawHub must pass before completion. SkillHub requires all of its own gates to pass before listing.
- skills.sh may retain a medium capability warning for a downloader that reads third-party metadata or a translator that sends explicitly approved text to a fixed cloud API. Document and constrain that boundary; do not delete the core feature solely to force a green badge.
- Every scanner-driven behavior change receives a version bump, tests, GitHub CI, a canonical ClawHub release, and another platform review.

### Composite Flow Changes

- A component Skill change is authoritative in `skills/<slug>/`; update the Flow lock with `tools/sync_video_flow.py --write` in the same commit.
- A Flow-only orchestration change belongs in `flows/video-production/FLOW.md` and `flow.json`; do not patch component Skill code indirectly.
- If the Flow changes its user-facing defaults or handoff contract, increment its `flow.json` version and run the full test suite.

## Local Boundary

Use `~/Developer/aiaaaa4/ai-landing-skills` for the public monorepo and `~/Developer/aiaaaa4/rithmic-signup` for the private app repository. The ignored `local-projects/` folder is never a public release source, but may hold an active local runtime; keep its database, credentials, logs, and outputs out of Git.
