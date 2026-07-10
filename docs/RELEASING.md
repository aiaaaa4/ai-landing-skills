# Release Procedure

GitHub is the source of truth. Each public skill is authored in `skills/<slug>/`; `registry.json` is the only source for its stable ID, display name, public version, ClawHub package, and topics.

## Change Types

- Documentation-only changes: validate, commit, and push to `main`.
- Skill behavior, scripts, dependencies, or execution-contract changes: make the change on a short-lived branch, run tests, review the diff, then merge to `main`.
- Public releases: use the GitHub Actions workflow `Publish ClawHub skill`. Always run a dry-run first, then publish the single selected skill after reviewing the result.

## Release Steps

1. Edit only the canonical public skill under `skills/<slug>/`.
2. Bump that skill's version in `registry.json` using semver. Do not duplicate the version in `SKILL.md`, package files, or separate release notes.
3. Run local checks:

   ```bash
   python3 tools/validate_repo.py
   python3 -m unittest discover -s tests
   python3 tools/release_skill.py --skill <slug> --changelog "<summary>" --dry-run
   ```

4. Commit and push. GitHub Actions runs the repository validation workflow.
5. In GitHub Actions, run `Publish ClawHub skill` with the same skill, a short changelog, and `dry_run=true`.
6. Review the dry-run result, then run the workflow again with `dry_run=false`.
7. Read back the ClawHub listing to verify display name, version, bilingual description, source commit, and scan status.

## Platform Expectations

- ClawHub is a release registry. It publishes one versioned skill at a time and starts a security scan after release.
- skills.sh can install directly from the public GitHub repository immediately. Its global search index is asynchronous; do not block release on indexing.
- SkillsMP and similar catalog crawlers are discovery channels, not release authorities.

## Local Boundary

Use `~/Developer/aiaaaa4/ai-landing-skills` for the public monorepo and `~/Developer/aiaaaa4/rithmic-signup` for the private app repository. The ignored `local-projects/` folder is never a public release source, but may hold an active local runtime; keep its database, credentials, logs, and outputs out of Git.
