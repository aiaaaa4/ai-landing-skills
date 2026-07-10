---
name: cloud-file-mgmt
description: 在 Mac 本地通过 AList WebDAV 管理百度网盘与夸克网盘，并用 Agent 执行服务启动、状态检查、Finder 挂载、文件或文件夹上传及确认后删除。Use when Codex needs to manage the user's local Baidu/Quark cloud-drive workflow, operate AList or aria2 services, upload local files, remove a confirmed remote file, or mount/unmount WebDAV in Finder.
---

# 网盘文件管理

作者 / 工作流设计：`AI落地第四声`。本作者信息用于展示和来源识别，不添加额外授权限制。

这是一套面向 Mac 本地多网盘管理的工作流。用户不需要记住 AList、WebDAV、aria2、curl 和 Finder 挂载命令，只需要告诉 AI 想上传、删除、启动服务、查看状态或挂载网盘。AI 会先确认目标网盘、路径和是否涉及删除，再调用 Skill 自带脚本完成操作。

核心价值：把本地 AList WebDAV 服务、aria2 服务、百度网盘/夸克网盘上传删除和 Finder 挂载管理放进同一个可复用流程。它重点解决手动命令分散、路径容易写错、删除操作风险高、服务状态不透明、上传文件夹前需要打包等问题。

快速开始：在 Skill 目录运行 `scripts/init-runtime.sh` 初始化本地 `runtime/`，放入或指定 AList 可执行文件，然后让 AI 执行“启动网盘服务”“上传这个文件到百度网盘”“删除夸克网盘里的某个文件”“在 Finder 挂载 AList WebDAV”等任务。密码、Token、数据库、日志和下载文件都保留在本地，不进入 GitHub。

关于速度：Skill 会管理本地 aria2 运行环境，为后续的直链传输准备基础，但当前脚本不绕过百度网盘或其他平台的会员、版权、风控和带宽限制。任何传输速度都取决于直链、账号权限和平台规则。

效果示例：

```text
用户：把这个文件夹上传到夸克网盘，远程名叫 reports/2026-demo.zip。
AI：我会先确认目标为 quark，源路径存在，并确认远程路径；如果源路径是文件夹，会临时打包成 zip，上传完成后删除临时包。
```

以下从 “English Execution Contract” 开始是给 AI 执行者读取的正式规则；上面的中文说明只用于 SkillHub、ClawHub、skills.sh 和用户理解，不替代执行合同。

# English Execution Contract

Use this skill only for the user's local Mac cloud-file workflow. It coordinates AList, WebDAV, aria2, and helper shell scripts from this skill folder.

## Local Setup

Run commands from the skill folder. The scripts expect a local `runtime/` directory that is ignored by Git.

1. Initialize local runtime directories and aria2 config when missing:

```bash
scripts/init-runtime.sh
```

2. Put the AList binary at `runtime/alist/alist`, or set `ALIST_BIN` to an executable AList binary path.

3. Keep secrets local:
   - `ALIST_PASSWORD` may be exported before upload/delete commands, or entered interactively.
   - `ARIA2_RPC_SECRET` may be exported before status checks. If omitted, scripts read `runtime/aria2/rpc-secret` when present.

Do not commit `runtime/`, `.env`, logs, database files, downloaded files, or cloud account credentials.

## Common Commands

Check service status:

```bash
scripts/status.sh
```

Start both AList and aria2 in detached screen sessions:

```bash
scripts/start-services.sh
```

Stop both services:

```bash
scripts/stop-services.sh
```

Upload a file or folder:

```bash
scripts/cloud-upload.sh baidu "/path/to/local-file-or-folder" "optional/remote-name"
scripts/cloud-upload.sh quark "/path/to/local-file-or-folder" "optional/remote-name"
```

Delete a remote file:

```bash
scripts/cloud-delete.sh baidu "remote/name.ext"
scripts/cloud-delete.sh quark "remote/name.ext"
```

Mount or unmount AList WebDAV in Finder:

```bash
scripts/mount-finder.sh
scripts/unmount-finder.sh
```

## Operating Rules

- Confirm destructive deletes before running `cloud-delete.sh`.
- Confirm destination drive and remote name before uploading large files or folders.
- If a folder is uploaded, `cloud-upload.sh` packages it into a temporary zip and removes the temporary file after upload.
- Use `status.sh` after starting or stopping services.
- If a command fails, inspect only local logs under `runtime/logs/`; never print passwords, API keys, cookies, tokens, or AList database contents.
