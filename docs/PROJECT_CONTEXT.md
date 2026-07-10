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
| `ai-landing-skills` | 公开 | 四个可独立安装和发布的 Agent Skill | `skills/<slug>/` 与 `registry.json` |
| `rithmic-signup` | 私有 | Rithmic 注册助手 App | 私有 GitHub 仓库 |
| 本地网盘运行时 | 仅本机 | AList、aria2、数据库、日志与下载文件 | 忽略的本地 `runtime/` 目录 |

私有 App 不进入公开 monorepo，也不发布到 ClawHub、skills.sh 或其他公共 Skill 平台。

## 公开 Skill 目录

| 唯一 ID | 展示名 | 目录 |
| --- | --- | --- |
| `aiaaaa4.video-download` | 一键加速视频下载 | `skills/video-download` |
| `aiaaaa4.video-translate` | 人工级视频字幕翻译 | `skills/video-translate` |
| `aiaaaa4.video-publish` | 极简视频封装 | `skills/video-publish` |
| `aiaaaa4.cloud-file-mgmt` | 网盘文件管理 | `skills/cloud-file-mgmt` |

`registry.json` 是 ID、展示名称、路径、版本、ClawHub 包名和主题标签的唯一来源。不要在多个文件里手工维护另一份版本号。

## 本地运行策略

- 公开 Skill 包只包含可安装的说明、脚本和必要引用资料；绝不提交 `runtime/`、数据库、日志、下载内容、输出文件或凭据。
- 网盘 Skill 的本机运行时可以存放在忽略的本地项目目录中；它不是公开发布源。公开脚本的修改应先写入 `skills/cloud-file-mgmt/`，本机运行副本需要同步验证。
- AList Finder WebDAV 的默认挂载点是 `~/AList-WebDAV`，不依赖仓库路径。移动项目后，重新启动服务并重新挂载，不复制或公开运行时数据。
- Finder 适合浏览和确认后删除。百度网盘可能拒绝 Finder 拖拽时创建的空临时文件；上传、下载 Office 文件、视频或大文件优先由 Agent 调用 `cloud-upload.sh` 与 `cloud-download.sh`。
- 视频下载后若继续翻译字幕，先在用户指定位置创建 `<中文视频名> [<视频 ID>]` 媒体项目文件夹。视频、直接下载的音频、ASS/SRT 都放在项目根目录；中间文件放在隐藏 `.work/`，不散落在桌面或 Skill 源码目录。
- 字幕翻译优先复用同名的音频下载文件；只有没有可复用音频时才用 FFmpeg 从视频提取上传音频。
- 视频发布封装只处理用户明确给出的本地视频、字幕和输出路径。每次都确认免责声明、水印、字幕烧录、裁切、编码质量和覆盖行为；除首次经同意安装 FFmpeg 外，不访问网络或云端服务。

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
  -> ClawHub 安全扫描 / skills.sh 异步发现
```

- GitHub：公开源码与完整提交历史的可信来源。
- ClawHub：一个 Skill 一次发布一个不可复用的版本；发布前必须 dry run。
- skills.sh：无需单独上传，可直接从公开 GitHub 仓库安装；搜索索引并非实时。
- SkillsMP、SkillHub 等：发现或镜像渠道，不是版本发布的可信来源。

完整操作步骤见 [RELEASING.md](RELEASING.md)。

## 安全边界

- 禁止将 AList 密码、RPC 密钥、API Key、Cookie、`.env`、数据库或日志提交到 GitHub。
- 不在对话、Issue、README、Skill 描述或发布说明中粘贴凭据。
- 删除远程文件、覆盖本地文件、发布公共版本前，必须显式确认目标和影响范围。

## 维护入口

以后可直接在总控对话中说明目标，例如“测试视频下载”“优化网盘上传”“发布字幕翻译新版本”或“修改私有 Rithmic App”。执行时先以本文件、`registry.json`、目标 Skill 的 `SKILL.md` 和 Git 当前状态为准。
