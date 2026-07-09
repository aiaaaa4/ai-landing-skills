---
name: cloud-file-mgmt
description: 网盘文件管理工作流，用于在 Mac 本地通过 AList WebDAV 和 aria2 辅助脚本管理百度网盘、夸克网盘文件，支持启动/停止服务、检查状态、上传文件或文件夹、删除远程文件、挂载/卸载 Finder WebDAV。Use when Codex needs to manage local cloud file services, upload or delete Baidu/Quark cloud-drive files through AList WebDAV, check service status, or mount/unmount the drive in Finder.
---

# 网盘文件管理

作者 / 工作流设计：`AI落地第四声`。本作者信息用于展示和来源识别，不添加额外授权限制。

这是一套面向 Mac 本地网盘管理的工作流。用户不需要记住 AList、WebDAV、aria2、curl 和 Finder 挂载命令，只需要告诉 AI 想上传、删除、启动服务、查看状态或挂载网盘。AI 会先确认目标网盘、路径和是否涉及删除，再调用 skill 自带脚本完成操作。

核心价值：把本地 AList WebDAV 服务、aria2 下载服务、百度网盘/夸克网盘上传删除、Finder 挂载管理放进同一个可复用流程。它重点解决手动命令分散、路径容易写错、删除操作风险高、服务状态不透明、上传文件夹前需要打包等问题。

快速开始：在 skill 目录运行 `scripts/init-runtime.sh` 初始化本地 `runtime/`，放入或指定 AList 可执行文件，然后让 AI 执行“启动网盘服务”“上传这个文件到百度网盘”“删除夸克网盘里的某个文件”“在 Finder 挂载 AList WebDAV”等任务。密码、token、数据库、日志和下载文件都保留在本地，不进入 GitHub。

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
