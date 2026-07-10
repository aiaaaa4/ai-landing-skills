#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${VIDEO_TRANSLATE_ENV_FILE:-$ROOT/.env}"
OPEN_EDITOR=0

if [[ "${1:-}" == "--open" ]]; then
  OPEN_EDITOR=1
elif [[ -n "${1:-}" ]]; then
  echo "Usage: bash scripts/open_env_setup.sh [--open]" >&2
  exit 2
fi

if [[ ! -f "$ENV_FILE" ]]; then
  umask 077
  cat > "$ENV_FILE" <<'EOF'
# Local-only video translation credentials. Never commit this file.
DASHSCOPE_API_KEY=
ALIYUN_WORKSPACE_ID=
ALIYUN_REGION=cn-beijing
ALIYUN_ASR_MODEL=fun-asr
ALIYUN_ASR_VOCABULARY_ID=
OKFILE_TOKEN=
EOF
  chmod 600 "$ENV_FILE"
fi

echo "Local env file: $ENV_FILE"
echo "Fill DASHSCOPE_API_KEY, ALIYUN_WORKSPACE_ID, and OKFILE_TOKEN. Do not commit this file."

if [[ "$OPEN_EDITOR" == "1" && "$(uname)" == "Darwin" ]]; then
  open -e "$ENV_FILE"
fi
