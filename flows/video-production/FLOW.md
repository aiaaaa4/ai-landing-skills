# 视频下载 → 翻译 → 发布 Flow

这是一个只负责编排的组合 Flow，不复制三个 Skill 的脚本。它始终调用仓库中当前版本的：

1. `aiaaaa4.video-download`
2. `aiaaaa4.video-translate`
3. `aiaaaa4.video-publish`

## 固定交接

所有步骤共用一个媒体项目目录：

```text
PROJECT_DIR/
├── 原版视频.mp4
├── 原始封面.png
├── 原版视频.中英双语字幕.ass
├── 原版视频.中英双语字幕.srt
├── 原版视频.发布版.mp4
├── 原版视频.发布版.中英双语字幕.bcc
└── .work/
    └── input/
        ├── 原版视频.m4a
        └── 原版视频.原语言字幕.srt
```

下载阶段产生的独立音频和原语言字幕只用于翻译交接。翻译成功导出后，`video-translate` 删除这两个临时输入；原始封面始终保留。

## 执行顺序

### 1. Download

- 只发送 `skills/video-download/scripts/preflight.py --mode combined` 的组合问卷。
- 确认链接、最高可用画质、项目目录、中文名称、源语言、翻译模式、屏幕上下文、外发同意和覆盖策略。
- 默认下载原版视频、最高质量原始封面、隐藏独立音频和最多一份最佳原语言字幕。
- 默认不下载播放列表。

### 2. Translate

- 只接收 Download 交接的视频路径；用户直接提供音频时仍然拒绝。
- 固定使用 OkFile + Fun-ASR 获取词级时间戳。原语言字幕只做内容校正，不能替代 ASR 时间轴。
- 先通读完整源文建立上下文，再按用户选定的 `qwen-mt-plus` 或 Agent 模式翻译；之后完整通读原文和译文，重译、语义重分段、QA 和全文 QC。
- 只有全部门禁通过后，才导出一个双语 ASS 和一个双语 SRT。

### 3. Publish

- 默认添加 3 秒中英双语免责声明；只编码片头，原视频主体码流复制。
- 如果存在匹配的双语 SRT，按发布版真实正文偏移转换为双语 BCC；源 SRT 不修改。
- 抽帧封面默认关闭，只有用户明确开启时才生成 5 张候选。
- 水印、烧录字幕、裁切、滤镜和全片重编码均须单独确认。

## 版本同步

`flow.json` 是依赖版本锁，不是脚本副本。每次任意组成 Skill 版本变化后运行：

```bash
python3 tools/sync_video_flow.py --write
python3 tools/sync_video_flow.py --check
```

CI 会拒绝依赖版本落后或路径不一致的 Flow。Flow 自身的编排规则变化时，更新 `flow.json` 的 Flow 版本并同步修改本文件；不要把三个 Skill 的代码复制进 Flow。

## 运行边界

- 长任务必须保持前台运行或轮询同一个 session，不得以“完成后自动继续”结束当前 Agent 轮次。
- 任一步失败时保留 `.work/` 运行记录，报告失败步骤和可恢复命令，不跳过门禁或伪造下游输出。
- 外发、凭据、覆盖和高级 FFmpeg 操作沿用各 Skill 的固定问卷与安全边界。
