# 视频素材准备工作流

这是公开的素材准备 Flow，固定按“视频下载 → 字幕翻译”顺序执行。它只负责编排，不复制两个 Skill 的代码：

1. `aiaaaa4.video-download`
2. `aiaaaa4.video-translate`

本 Flow 不执行平台发布封装，不添加免责声明，不生成发布版视频或 BCC，也不包含个人平台模板。

## 固定交接

两个步骤共用一个媒体项目目录：

```text
PROJECT_DIR/
├── 原版视频.mp4
├── 原始封面.png
├── 原版视频.中英双语字幕.ass
├── 原版视频.中英双语字幕.srt
└── .work/
    ├── input/
    │   ├── 原版视频.m4a
    │   └── 原版视频.原语言字幕.srt
    └── translate/
        └── 翻译上下文、术语与质检记录
```

下载阶段产生的独立音频和原语言字幕只用于翻译交接。翻译成功导出后，`video-translate` 删除临时音频和原语言字幕；原版视频、原始封面、双语 ASS 与双语 SRT 是公开 Flow 的最终可见交付。

## 执行顺序

### 1. Download

- 原样发送 `skills/video-download/scripts/preflight.py --mode combined` 的素材准备问卷。
- 一次确认链接、画质、项目目录、命名、源语言、翻译模式、屏幕上下文、外发同意和覆盖策略。
- 默认下载原版视频、最高质量原始封面、隐藏独立音频和最多一份最佳原语言字幕。
- 默认只下载当前视频，不下载整个播放列表。

### 2. Translate

- 只接收 Download 交接的视频路径；用户直接提供音频时仍然拒绝。
- 固定使用 OkFile + Fun-ASR 获取词级时间戳。原语言字幕只做内容校正，不能替代 ASR 时间轴。
- 先通读完整源文建立上下文，再按用户选择使用 `qwen-mt-plus` 或当前 Agent 模型翻译。
- 完整通读原文与译文，完成重译、语义重分段、确定性 QA 和最终全文 QC。
- 只有全部门禁通过后，才导出一个双语 ASS 和一个双语 SRT。

## 版本同步

`flow.json` 是两个公开 Skill 的依赖版本锁，不是脚本副本。任一组成 Skill 版本变化后运行：

```bash
python3 tools/sync_video_flow.py --write
python3 tools/sync_video_flow.py --check
```

CI 会拒绝依赖版本落后或路径不一致的 Flow。Flow 自身的编排或交付契约变化时，单独更新 `flow.json` 的版本。

## 运行边界

- 长任务必须保持前台运行或持续轮询同一个 session，不得以“完成后自动继续”结束当前 Agent 轮次。
- 任一步失败时保留 `.work/` 运行记录，报告失败步骤和可恢复命令，不跳过门禁或伪造下游输出。
- 外发、凭据和覆盖行为沿用两个组成 Skill 的固定问卷与安全边界。
