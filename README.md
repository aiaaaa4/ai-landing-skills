<div align="center">
  <h1 align="center">AI落地第四声 · Agent Skills</h1>
  <p align="center">面向真实任务的 Agent Skills：下载、字幕翻译、视频封装与多网盘文件管理。</p>
  <p align="center">
    <a href="#skills">浏览 Skills</a> ·
    <a href="#install">安装</a> ·
    <a href="docs/PROJECT_CONTEXT.md">项目策略</a> ·
    <a href="docs/RELEASING.md">发布流程</a> ·
    <a href="https://github.com/aiaaaa4/ai-landing-skills/issues">反馈问题</a>
  </p>
  <p align="center">
    <a href="LICENSE"><img src="https://img.shields.io/badge/license-MIT--0-111111.svg" alt="MIT-0 License"></a>
    <a href="https://github.com/aiaaaa4/ai-landing-skills"><img src="https://img.shields.io/badge/source-GitHub-181717.svg?logo=github" alt="GitHub source"></a>
    <a href="https://clawhub.ai"><img src="https://img.shields.io/badge/publish-ClawHub-111111.svg" alt="Published on ClawHub"></a>
    <a href="https://skills.sh"><img src="https://img.shields.io/badge/install-skills.sh-111111.svg" alt="Install with skills.sh"></a>
  </p>
</div>

`aiaaaa4/ai-landing-skills` 是 [AI落地第四声](https://github.com/aiaaaa4) 的公开 Skill 源码库。每个 Skill 都有独立目录、唯一 ID、版本与发布记录；GitHub 是唯一可信源码，ClawHub 是发布渠道，`skills.sh` 可直接从 GitHub 安装。

这里不收集泛泛的提示词。每个 Skill 都把一个重复、容易出错或需要人机确认的实际任务，整理成 Agent 可以稳定执行的流程。

## Skills

### [一键加速视频下载](skills/video-download)

**`aiaaaa4.video-download` · v1.2.6 · [查看源码](skills/video-download) · [ClawHub](https://clawhub.ai/aiaaaa4/video-download)**

把一个视频链接交给 Agent，先看清可下载的画质、编码、大小和容器，再决定下载。适合希望保留选择权、又不想手动研究 `yt-dlp` 参数的人。

- 支持 YouTube、YouTube Shorts、Vimeo、TikTok、Instagram、X/Twitter、Facebook、Twitch、Bilibili、Dailymotion、SoundCloud、Bandcamp、Reddit 等常见来源，以及 [yt-dlp 官方列出的完整站点清单](https://github.com/yt-dlp/yt-dlp/blob/master/supportedsites.md)。yt-dlp 的官方定义是支持数千个站点，因此以该清单为准，而不是维护一份很快过期的静态列表。
- 下载前由 Agent 检查可用格式，并按最高质量、MP4 兼容、较小体积、仅音频等目标给出可理解的选项。
- 下载媒体时同时保存平台提供的最高质量作者封面，统一转换并命名为 `原始封面.png`；不会额外下载一组不同尺寸。
- 进入三 Skill 组合流程时，额外把独立音频和一份最佳原语言字幕（如有）放入隐藏 `.work/input/`，供 Fun-ASR 与内容校正使用，翻译成功后自动清理。
- 可选择分辨率、帧率、HDR/SDR、编码、音轨和输出文件名；默认不把播放列表当作单个视频误下载。
- 基于 `yt-dlp` 下载，使用 [FFmpeg](https://ffmpeg.org/ffmpeg.html) 完成音视频合并、容器转换、提取音频、嵌入字幕/封面等后处理。FFmpeg 是通用媒体转换工具，能读取、过滤与转码多种音视频格式。

> 请只下载你有权保存、使用或处理的内容。受站点登录、地区、DRM 或账号权限限制的资源，仍可能无法下载。

### [人工级视频字幕翻译](skills/video-translate)

**`aiaaaa4.video-translate` · v1.5.2 · [查看源码](skills/video-translate) · [ClawHub](https://clawhub.ai/aiaaaa4/video-translate)**

面向课程、培训、访谈、演示和录屏等本地视频，把“识别出字幕”升级为“能直接交付的双语字幕”。编排模型先通读完整源文，生成领域提示、术语和歧义判断供翻译模型初译；之后再次通读原文与译文，完成重译审校、语义重分段、确定性 QA 和最终全文 QC。

- 适合英语、法语、西班牙语、意大利语等本地视频翻译为中文。
- 固定转写链路：OkFile + Fun-ASR 获取词级时间戳；初译公开默认使用带 `domains/terms/tm_list` 的 `qwen-mt-plus`，也可选择当前 Codex / 编排模型直接翻译。两条路径都经过译前全文分析、全文重译审校、确定性 QA 和最终全文 QC。
- 支持重要 PPT、图表、UI、代码或屏幕文字的上下文处理，并为长视频持续反馈进度。
- [查看完整工作流说明](docs/video-translate/视频翻译工作流说明书.md)。

### [极简视频封装](skills/video-publish)

**`aiaaaa4.video-publish` · v1.0.9 · [查看源码](skills/video-publish) · [ClawHub](https://clawhub.ai/aiaaaa4/video-publish)**

为已经下载或翻译完成的本地视频快速生成 B 站发布素材。它在视频开头轻量添加 3 秒固定免责声明，并优先通过音频内容匹配，把双语 SRT 转为时间轴准确的发布版双语 BCC；默认不重新编码视频主体。

- 抽取 `抽帧封面1.png` 至 `抽帧封面5.png` 默认关闭；字幕烧录、水印和其他完整重编码功能保留为高级模式。
- 支持开篇全屏黑底或半透明免责声明、动态漂移/四角水印、裁切片段、速度或画质优先、网页快速起播。
- 缺少 FFmpeg 时会停止并提示用户自行安装可信版本；Skill 不调用 Homebrew、`sudo` 或其他包管理器。

### 三 Skill 组合工作流

`video-download → video-translate → video-publish` 共用一个媒体项目目录。下载阶段把独立音频和原语言字幕放进隐藏输入区；翻译阶段始终用 Fun-ASR 取得词级时间戳，并用原字幕校正内容，成功后删除临时音频和原字幕；发布阶段增加免责声明，并按实际语音偏移把双语 SRT 转为发布版双语 BCC。抽帧封面默认关闭，可按需开启。

正常完成后的可见交付为：原版视频和发布版视频 `2` 个；双语 ASS、双语 SRT、发布版双语 BCC `3` 个；原始封面 `1` 张。开启抽帧封面后会额外生成 `5` 张候选；独立音频和原语言字幕均为 `0`。运行记录与时间线清单保留在隐藏 `.work/`，不污染交付目录。

### [视频生产工作流](flows/video-flow)

**`aiaaaa4.video-flow` · v1.0.1 · [查看工作流](flows/video-flow/FLOW.md)**

组合 Flow 只负责编排，不复制三个 Skill 的代码。它固定按 `video-download → video-translate → video-publish` 顺序运行，共用一个媒体项目目录，并通过 `flows/video-flow/flow.json` 锁定三个组件的当前版本。任意组件 Skill 更新后，运行 `python3 tools/sync_video_flow.py --write` 更新 Flow 依赖锁；CI 会阻止 Flow 使用旧版本。

Flow 默认下载最高可用质量、输出简体中文双语 ASS/SRT、添加 3 秒免责声明并生成发布版双语 BCC；抽帧封面、水印、烧录字幕、裁切、滤镜和全片重编码均保持关闭，除非用户明确开启。

### [网盘文件管理](skills/cloud-file-mgmt)

**`aiaaaa4.cloud-file-mgmt` · v1.2.2 · [查看源码](skills/cloud-file-mgmt) · [ClawHub](https://clawhub.ai/aiaaaa4/cloud-file-mgmt)**

把 AList 已配置的多种网盘、对象存储、文件协议与 Mac 本地文件系统放进同一套 Agent 工作流。常见驱动包括阿里云盘、115、123 云盘、百度网盘、夸克、OneDrive、Google Drive、Dropbox、PikPak、迅雷、S3、WebDAV、SMB、FTP/SFTP 等；完整范围以 [AList 官方驱动目录](https://alistgo.com/guide/drivers/) 为准。

- 通过本地 AList WebDAV 管理任意已配置的顶层存储挂载；可启动/停止服务、检查运行状态、在 Finder 挂载或卸载 WebDAV。
- Agent 可确认本地源路径与目标网盘后流式上传或下载文件；上传文件夹时自动临时打包为 ZIP，并在完成后清理临时文件。重要 Office 文件、视频和大文件优先使用脚本，不依赖 Finder 拖拽。
- 删除远程文件前必须再次确认，避免批量操作误删；账号密码、Token、数据库、日志和下载文件始终留在本机，不会被提交到 GitHub。
- 内置 aria2 本地服务运行管理，为后续的直接链接下载和传输任务预留基础。**当前版本不会绕过百度网盘或其他平台的会员、版权、风控与带宽限制**；任何速度提升都取决于文件来源、账户权限与平台规则。

## Install

### 从 ClawHub 安装

```bash
clawhub install @aiaaaa4/video-download
clawhub install @aiaaaa4/video-translate
clawhub install @aiaaaa4/video-publish
clawhub install @aiaaaa4/cloud-file-mgmt
```

### 从 GitHub 直接安装

先查看仓库包含哪些 Skill：

```bash
npx skills add aiaaaa4/ai-landing-skills --list --full-depth
```

按需安装一个：

```bash
npx skills add aiaaaa4/ai-landing-skills --skill video-download --full-depth
npx skills add aiaaaa4/ai-landing-skills --skill video-translate --full-depth
npx skills add aiaaaa4/ai-landing-skills --skill video-publish --full-depth
npx skills add aiaaaa4/ai-landing-skills --skill cloud-file-mgmt --full-depth
```

`skills.sh` 直接读取公开 GitHub 仓库；ClawHub 则使用各 Skill 的独立发布版本。详细兼容性与命令请参考 [skills CLI 文档](https://github.com/vercel-labs/skills)。

## How It Works

```text
本地修改代码或说明
        ↓
运行校验与测试
        ↓
提交并推送 GitHub main
        ↓
GitHub Actions 选择一个 Skill 发布到 ClawHub
        ↓
ClawHub 独立版本更新并完成安全扫描
        ↓
skills.sh 异步刷新 / SkillHub 手动维护或等待镜像
```

- `registry.json` 是公开 ID、展示名称、目录、版本和平台目标的唯一来源。
- 每个 installable Skill 只包含执行需要的 `SKILL.md`、脚本、引用资料和资源；较长的用户文档放在 `docs/`。
- 发布时始终一次选择一个 Skill，并先运行 GitHub Actions 的 dry run。完整步骤见 [发布说明](docs/RELEASING.md)。
- `skills.sh` 的实际安装会克隆 GitHub 最新源码，但目录页面和安全审计异步刷新；SkillHub 镜像不作为发布完成依据。
- 长期项目边界、版本规则和本地运行策略见 [项目总控上下文](docs/PROJECT_CONTEXT.md)。
- `rithmic-signup` 是私有 App，位于独立私有仓库，不会出现在这个公开目录或公共 Skill 平台。

## Repository Layout

```text
skills/
  video-download/       # yt-dlp + FFmpeg 的受确认下载流程
  video-translate/      # 本地视频的高质量字幕翻译流程
  video-publish/        # B 站 3 秒免责声明、可选抽帧封面与 BCC 字幕流程
  cloud-file-mgmt/      # Mac + AList WebDAV 的多网盘管理流程
flows/
  video-flow/           # 视频生产工作流及三个 Skill 的依赖锁
docs/                   # 面向人的产品与发布说明
tests/                  # 可重复运行的回归测试
tools/                  # 校验与独立发布工具
registry.json           # 公开目录与版本的可信来源
```

## Contributing And Updates

问题、使用反馈与功能建议请通过 [GitHub Issues](https://github.com/aiaaaa4/ai-landing-skills/issues) 提交。对外发布的内容会先在本地验证，再推送 GitHub 并以独立版本发布到 ClawHub。

## License

[MIT-0](LICENSE)
