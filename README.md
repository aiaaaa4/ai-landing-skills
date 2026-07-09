# AI落地第四声 SkillHub

这是 `aiaaaa4` 的公开 agent skills monorepo。GitHub 作为源码可信来源；每个 skill 独立展示、独立版本、独立发布。

## Catalog

| ID | Display name | Path | Type | Version |
| --- | --- | --- | --- | --- |
| `aiaaaa4.video-download` | AI落地第四声：一键加速视频下载 skill | `skills/video-download` | skill | `1.0.1` |
| `aiaaaa4.video-translate` | AI落地第四声：人工级视频字幕翻译 skill | `skills/video-translate` | skill | `1.3.1` |
| `aiaaaa4.cloud-file-mgmt` | AI落地第四声：网盘文件管理 skill | `skills/cloud-file-mgmt` | skill | `1.0.0` |

## Install

ClawHub:

```bash
clawhub install @aiaaaa4/video-download
clawhub install @aiaaaa4/video-translate
clawhub install @aiaaaa4/cloud-file-mgmt
```

skills.sh / `npx skills` direct GitHub install:

```bash
npx skills add aiaaaa4/ai-landing-skills --list --full-depth
npx skills add aiaaaa4/ai-landing-skills --skill video-download --full-depth
npx skills add aiaaaa4/ai-landing-skills --skill video-translate --full-depth
npx skills add aiaaaa4/ai-landing-skills --skill cloud-file-mgmt --full-depth
```

The `rithmic-signup` app is private and is not part of this public repository.

## Repository Rules

- `registry.json` is the source for public IDs, names, paths, versions, and platform targets.
- Installable skill folders stay lean: `SKILL.md` plus required `agents/`, `scripts/`, `references/`, or assets.
- Generated outputs, private `.env` files, local runtime data, logs, downloaded media, subtitle outputs, zip packages, and `local-projects/` stay out of Git.
- Publish one skill at a time. Combined workflows are intentionally deferred.
- Public release to GitHub, ClawHub, skills.sh, or any other platform requires explicit confirmation.

## Local Structure

```text
skills/
  video-download/
  video-translate/
  cloud-file-mgmt/
registry.json
```

Private/local-only app projects are kept outside this public catalog.
