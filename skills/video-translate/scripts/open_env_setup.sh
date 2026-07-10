#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${VIDEO_TRANSLATE_ENV_FILE:-$ROOT/.env}"

if [[ ! -f "$ENV_FILE" ]]; then
  umask 077
  cat > "$ENV_FILE" <<'EOF'
# Local-only video translation credentials. Never commit this file.
DASHSCOPE_API_KEY=
ALIYUN_WORKSPACE_ID=
ALIYUN_REGION=cn-beijing
ALIYUN_ASR_MODEL=fun-asr
ALIYUN_ASR_UPLOAD=okfile
ALIYUN_ASR_VOCABULARY_ID=
OKFILE_UPLOAD_URL=https://www.okfile.com/api/upload/quick
OKFILE_TOKEN=
EOF
  chmod 600 "$ENV_FILE"
fi

echo "Local env file: $ENV_FILE"
echo "Fill DASHSCOPE_API_KEY, ALIYUN_WORKSPACE_ID, and OKFILE_TOKEN. Do not commit this file."

if [[ "${VIDEO_TRANSLATE_OPEN_EDITOR:-1}" == "1" && "$(uname)" == "Darwin" ]]; then
  open -e "$ENV_FILE"
fi
