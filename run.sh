#!/usr/bin/env bash
# file: run.sh

# 强制启用错误检查
set -e

# 进入项目目录
cd "$(dirname "$0")/backend"

# 自动检测虚拟环境路径
VENV_PYTHON="$HOME/anaconda3/envs/SCaudit/bin/python"

# 检查 Python 是否存在
if [ ! -f "$VENV_PYTHON" ]; then
  echo "❌ 未找到虚拟环境 Python: $VENV_PYTHON"
  echo "请确认你的 Conda 环境名是否为 SCAudit"
  exit 1
fi

echo "✅ 使用虚拟环境 Python 启动服务..."
"$VENV_PYTHON" -m uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1
