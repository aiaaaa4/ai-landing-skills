# 发布流程（SkillHub 打包）

源码真身在 `work/`（scripts、references、中文说明书、tools、tests、eval）。
`skill/人工级视频字幕翻译/` 中的 `scripts/`、`references/` 和顶层中文说明书是打包时同步生成的产物；
只有 `SKILL.md` 和 `agents/openai.yaml` 是 skills 侧手工维护的分发专属文件。

以下命令均在 `work/` 目录下执行。

## 发布步骤

1. 完成并验证改动：

   ```bash
   python3 -m unittest discover -s tests
   python3 tools/eval_report.py --compare   # QA 指标不应意外退化
   ```

2. 更新版本号（两处必须一致，打包校验会检查）：
   - `skill/人工级视频字幕翻译/SKILL.md` frontmatter 的 `metadata.version` 和正文 `## Version` 段
   - `work/README.md` 的 `Workflow version`

3. 同步 + 校验 + 打包：

   ```bash
   python3 tools/package_skill.py
   ```

   校验内容（任一失败则不出包）：
   - 包内不得出现 `.env` / env example / `.DS_Store` / `__pycache__` / `.bak`
   - `SKILL.md`、`agents/openai.yaml`、中文说明书、术语库、修复规则齐全
   - work 与 skills 的脚本清单一致
   - 作者署名 `AI落地第四声` 存在
   - 版本号 frontmatter 与正文一致，README 同步
   - zip 内文件名以 UTF-8 写入（中文说明书文件名跨平台可读）

4. 提交并打 tag：

   ```bash
   git add -A && git commit -m "Release vX.Y.Z"
   git tag vX.Y.Z
   ```

5. 上传 `skill/人工级视频字幕翻译.zip` 到 SkillHub，展示文案保持中文优先。

## 红线（改动前先确认）

- `SRC_RAW` 时间轴契约、Fun-ASR + OkFile 固定栈
- ASS 中文 42 / 源语言 24、中文在上、单 Dialogue 双行
- OCR/屏幕上下文默认关闭
- 真实 `.env` 只存在于 `work/`，永不进包、永不入库
- 作者署名 `AI落地第四声` 不可移除
