#!/usr/bin/env python3
from __future__ import annotations

import argparse


SINGLE = """开始下载前，请一次性确认以下内容：
1. 下载质量：默认选择最高可用画质和最佳音频；如需 MP4 兼容版或限制分辨率，请填写。
2. 保存位置：默认保存到桌面，并为视频创建独立项目文件夹；如需其他位置，请填写绝对路径。
3. 命名方式：默认使用中文视频标题加视频 ID，视频、封面和后续文件保持同名；如需自定义，请填写。
4. 播放列表：默认只下载当前视频，不下载播放列表。

如全部使用默认设置，请回复：确认默认设置。"""


COMBINED = """开始“视频下载 → 字幕翻译 → 视频封装”组合流程前，请先准备固定转写服务的凭据：
- OkFile：把本地音频临时上传为 Fun-ASR 可读取的 HTTPS 地址，需要 `OKFILE_TOKEN`。注册地址：https://www.okfile.com/；API Key 页面：https://www.okfile.com/en/account/api-keys
- 阿里 Fun-ASR：固定负责长音频转写和词级时间戳，需要 `DASHSCOPE_API_KEY` 与 `ALIYUN_WORKSPACE_ID`。获取 API Key：https://help.aliyun.com/zh/model-studio/get-api-key；Fun-ASR 说明：https://help.aliyun.com/zh/model-studio/fun-asr-recorded-speech-recognition-http-api
- 请把凭据填写到本机 `.env`，不要在聊天中发送。缺失时，Agent 会在获得同意后创建并打开配置文件。

请一次性确认以下内容：
1. 下载质量：默认选择最高可用画质和最佳音频；如需 MP4 兼容版或限制分辨率，请填写。
2. 项目位置：默认在桌面创建“中文视频标题 [视频 ID]”项目文件夹；如需其他位置，请填写绝对路径。
3. 文件命名：默认让视频、字幕和发布版使用同一个中文名称并保留视频 ID；如需自定义，请填写。
4. 源语言：默认英语；如不是英语，请填写实际语言。
5. 翻译目标与交付：默认翻译为简体中文，并固定输出中文在上、原文在下的双语 ASS 和 SRT；如需其他目标语言，请填写，否则回复“默认”。
6. 翻译模型：默认选择 A；如选择 B，请明确回复“Codex 翻译”。
   A. `qwen-mt-plus`：稳定、性价比高，使用同一个阿里 DashScope API Key 调用，适合作为公开 Skill 的默认方案。
   B. 当前 Codex / 编排模型：由当前 Agent 在通读全文后直接翻译，不需要额外翻译 API Key，但会消耗当前 Agent 的模型额度，耗时和质量取决于所选模型。
7. 屏幕上下文：默认关闭；如果 PPT、图表、软件界面、代码或画面文字会影响理解，请回复“开启”。
8. 外发处理：是否同意将处理音频上传至 OkFile，并将临时链接发送给阿里 Fun-ASR？选择 A 时字幕文本还会发送给阿里 `qwen-mt-plus`；选择 B 时字幕文本由当前 Agent 模型服务处理。
9. 发布封装：默认添加 3 秒免责声明、抽取 5 张封面候选，并为双语 SRT 生成时间轴校准后的发布版 SRT；默认不烧录字幕、不加水印、不做全片重编码。
10. 文件覆盖：默认不覆盖任何已存在的同名文件；如允许覆盖，请明确说明。

如除外发处理外全部使用默认设置（包括选择 A），请回复：确认默认设置，并同意外发处理。"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Print the exact video workflow confirmation questionnaire.")
    parser.add_argument("--mode", choices=("single", "combined"), default="single")
    args = parser.parse_args()
    print(COMBINED if args.mode == "combined" else SINGLE)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
