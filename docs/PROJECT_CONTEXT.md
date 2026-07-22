# 项目总控上下文

本文件记录 `aiaaaa4` 项目的长期维护约定。它是对话之外的持久上下文，不保存密码、Token、Cookie、网盘目录内容或任何个人文件清单。

## 品牌与账号

- 对外中文品牌：AI落地第四声
- 统一账号 ID：`aiaaaa4`
- 公开 Skill 源码库：`aiaaaa4/ai-landing-skills`
- 默认分支：`main`

## 项目边界

| 项目 | 可见性 | 用途 | 可信来源 |
| --- | --- | --- | --- |
| `ai-landing-skills` | 公开 | 两个可独立安装的视频素材 Skill，以及公开素材准备 Flow | `skills/<slug>/`、`flows/video-flow/` 与 `registry.json` |
| `aaron-video-workflow` | 私有 | Aaron 的视频发布 Skill、个人配置与私人总 Flow | 独立私有 GitHub 仓库 |
| `cloud-file-mgmt` | 私有、暂停 | 网盘文件管理 Skill 的历史源码与重构基线 | 独立私有 GitHub 仓库 |
| `rithmic-signup` | 私有 | Rithmic 注册助手 App | 私有 GitHub 仓库 |
| 本地网盘运行时 | 仅本机 | AList、aria2、数据库、日志与下载文件 | 忽略的本地 `runtime/` 目录 |

私有 App 不进入公开 monorepo，也不发布到 ClawHub、skills.sh 或其他公共 Skill 平台。

## 公开 Skill 目录

| 唯一 ID | 展示名 | 目录 |
| --- | --- | --- |
| `aiaaaa4.video-download` | 一键加速视频下载 | `skills/video-download` |
| `aiaaaa4.video-translate` | 人工级视频字幕翻译 | `skills/video-translate` |

`registry.json` 是 ID、展示名称、路径、版本、ClawHub 包名和主题标签的唯一来源。不要在多个文件里手工维护另一份版本号。

## 本地运行策略

- 公开 Skill 包只包含可安装的说明、脚本和必要引用资料；绝不提交 `runtime/`、数据库、日志、下载内容、输出文件或凭据。
- 视频下载后若继续翻译字幕，先在用户指定位置创建 `<中文视频名> [<视频 ID>]` 媒体项目文件夹。项目根目录只放可见交付；直接下载的独立音频和一份原语言字幕放入隐藏 `.work/input/`，不散落在桌面或 Skill 源码目录。
- 字幕翻译始终通过 OkFile + Fun-ASR 获取词级时间戳。编排模型在初译前先通读完整源文，生成本视频专属 `domains/terms/tm_list`；初译公开默认使用 qwen-mt-plus，用户也可选择当前 Codex / Agent 模型直接翻译。之后编排模型再次通读原文与译文进行重译审校和语义重分段，最终 QC 通过后才导出并清理 `.work/input/`。
- 私人 `video-publish` 与 `aaron-video-flow` 只在 `aiaaaa4/aaron-video-workflow` 中维护，不进入公开注册表或公共 Skill 平台。公开素材 Flow 的交付边界固定为原版视频、原始封面和双语 ASS/SRT。

## 版本规则

使用三段式版本号 `MAJOR.MINOR.PATCH`，在页面展示时可加 `v` 前缀：

- 从 `1.0.0` 开始，依次使用 `1.0.1` 到 `1.0.9`，然后 `1.1.0`；同样从 `1.2.9` 进入 `1.3.0`。
- 文案修正、稳定性修复和不改变使用方式的小改动递增 `PATCH`，例如 `1.2.0` 到 `1.2.1`。
- 新增清晰、向后兼容的使用能力递增 `MINOR`，例如 `1.2.x` 到 `1.3.0`。
- 只有破坏现有安装或执行约定时才递增 `MAJOR`。
- 已公开发布的版本号永不复用。每次 ClawHub 发布前，确认目标版本大于该 Skill 的最新版本。

## 发布与发现

```text
本地修改
  -> 本地校验和测试
  -> 提交并推送 GitHub main
  -> GitHub 成为最新源码
  -> 对单个 Skill 运行 ClawHub dry run
  -> 发布该 Skill 的独立版本
  -> ClawHub 安全扫描
  -> skills.sh 异步刷新 / SkillHub 手动维护或等待镜像
```

- GitHub：公开源码与完整提交历史的可信来源。
- ClawHub：一个 Skill 一次发布一个不可复用的版本；发布前必须 dry run。
- skills.sh：安装命令直接读取公开 GitHub；目录快照、搜索和安全审计异步刷新，官方没有更新 SLA。
- SkillHub：ClawHub 镜像不完整且可能长期滞后；绑定创作者后优先手动更新现有条目，不能依赖自动同步。
- SkillsMP 等：发现或爬虫渠道，不是版本发布的可信来源。

完整操作步骤见 [RELEASING.md](RELEASING.md)。

## 安全边界

- 禁止将 AList 密码、RPC 密钥、API Key、Cookie、`.env`、数据库或日志提交到 GitHub。
- 不在对话、Issue、README、Skill 描述或发布说明中粘贴凭据。
- 删除远程文件、覆盖本地文件、发布公共版本前，必须显式确认目标和影响范围。

## 维护入口

以后可直接在总控对话中说明目标，例如“测试视频下载”“重新设计网盘管理”“发布字幕翻译新版本”或“修改私有 Rithmic App”。执行时先以本文件、`registry.json`、目标 Skill 的 `SKILL.md` 和 Git 当前状态为准。`cloud-file-mgmt` 在完成重新设计和端到端验证前不得恢复公开分发。
