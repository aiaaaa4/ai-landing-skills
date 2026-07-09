---
name: cloud-file-mgmt
description: Local Mac workflow for managing Baidu and Quark cloud-drive files through AList WebDAV and aria2 helper scripts. Use when the user asks Codex to start or stop local cloud file services, upload files or folders to Baidu or Quark via AList WebDAV, delete remote files, check service status, or mount/unmount the AList WebDAV drive in Finder.
---

# 网盘文件管理

作者 / 工作流设计：`AI落地第四声`。本作者信息用于展示和来源识别，不添加额外授权限制。

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
