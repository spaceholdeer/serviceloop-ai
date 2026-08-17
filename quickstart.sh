#!/usr/bin/env bash

set -Eeuo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
BACKEND_DIR="$PROJECT_DIR/backend"
FRONTEND_DIR="$PROJECT_DIR/frontend"
BACKEND_PID=""
FRONTEND_PID=""

if [[ -t 1 ]]; then
  GREEN='\033[0;32m'
  YELLOW='\033[0;33m'
  RED='\033[0;31m'
  BOLD='\033[1m'
  RESET='\033[0m'
else
  GREEN=''
  YELLOW=''
  RED=''
  BOLD=''
  RESET=''
fi

info() { printf "%b\n" "${GREEN}✓${RESET} $1"; }
warn() { printf "%b\n" "${YELLOW}!${RESET} $1"; }
fail() {
  printf "%b\n" "${RED}✗${RESET} $1" >&2
  exit 1
}

require_command() {
  command -v "$1" >/dev/null 2>&1 || fail "缺少 $1。$2"
}

port_is_in_use() {
  if command -v lsof >/dev/null 2>&1; then
    lsof -nP -iTCP:"$1" -sTCP:LISTEN >/dev/null 2>&1
  else
    nc -z 127.0.0.1 "$1" >/dev/null 2>&1
  fi
}

require_free_port() {
  if port_is_in_use "$1"; then
    fail "端口 $1 已被占用。请回到之前的启动终端按 Ctrl+C，或运行：lsof -nP -iTCP:$1 -sTCP:LISTEN"
  fi
}

cleanup() {
  trap - EXIT INT TERM
  if [[ -z "$BACKEND_PID" ]] && [[ -z "$FRONTEND_PID" ]]; then
    return
  fi
  printf "\n"
  info "正在关闭 FastAPI 和 React 开发服务器…"
  if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
    kill "$BACKEND_PID" 2>/dev/null || true
  fi
  if [[ -n "$FRONTEND_PID" ]] && kill -0 "$FRONTEND_PID" 2>/dev/null; then
    kill "$FRONTEND_PID" 2>/dev/null || true
  fi
  [[ -z "$BACKEND_PID" ]] || wait "$BACKEND_PID" 2>/dev/null || true
  [[ -z "$FRONTEND_PID" ]] || wait "$FRONTEND_PID" 2>/dev/null || true
  info "前后端已关闭；MySQL 容器和数据继续保留。"
}

trap cleanup EXIT INT TERM

printf "%b\n" "${BOLD}ServiceLoop AI · Quickstart${RESET}"
printf "%s\n\n" "一条命令启动 MySQL、FastAPI 和 React"

require_command docker "请先安装并启动 Docker Desktop。"
require_command uv "请先安装 uv：https://docs.astral.sh/uv/"
require_command node "请安装 Node.js 22。"
require_command pnpm "请执行：npm install --global pnpm@11"

[[ -f "$PROJECT_DIR/.env" ]] || fail "缺少根目录 .env，请先执行：cp .env.example .env"

docker compose version >/dev/null 2>&1 || \
  fail "Docker Compose 不可用，请打开 Docker Desktop 并启用 CLI tools。"

if ! docker info >/dev/null 2>&1; then
  if [[ "$(uname -s)" == "Darwin" ]] && [[ -d "/Applications/Docker.app" ]]; then
    warn "Docker Desktop 尚未运行，正在启动…"
    open -a Docker
    for _ in {1..45}; do
      docker info >/dev/null 2>&1 && break
      sleep 2
    done
  fi
fi

docker info >/dev/null 2>&1 || fail "Docker daemon 未就绪，请确认 Docker Desktop 已完成启动。"
info "Docker Desktop 已就绪"

require_free_port 8000
require_free_port 5173

grep -Eq '^DEEPSEEK_API_KEY=$' "$PROJECT_DIR/.env" && \
  warn "DEEPSEEK_API_KEY 为空：页面可以启动，但发送聊天消息会返回 503。"
grep -Eq '^DASHSCOPE_API_KEY=$' "$PROJECT_DIR/.env" && \
  warn "DASHSCOPE_API_KEY 为空：知识库检索暂时不能调用在线 Embedding。"

printf "\n%b\n" "${BOLD}[1/4] 启动 MySQL${RESET}"
docker compose --project-directory "$PROJECT_DIR" up -d mysql

MYSQL_READY=false
for _ in {1..30}; do
  if docker compose --project-directory "$PROJECT_DIR" exec -T mysql sh -c \
    'mysqladmin ping --host=127.0.0.1 --user="$MYSQL_USER" --password="$MYSQL_PASSWORD" --silent' \
    >/dev/null 2>&1; then
    MYSQL_READY=true
    break
  fi
  sleep 2
done
[[ "$MYSQL_READY" == "true" ]] || \
  fail "MySQL 在 60 秒内没有就绪，请运行 docker compose logs mysql 查看日志。"
info "MySQL 已就绪，数据保存在 Docker volume serviceloop-ai_mysql_data"

printf "\n%b\n" "${BOLD}[2/4] 准备后端${RESET}"
(
  cd "$BACKEND_DIR"
  uv sync --extra rag --extra dev
  uv run python -m app.db.init_db
  uv run python -m app.db.seed_operations_demo
)
info "FastAPI 依赖、数据库表和幂等业务演示数据已准备"

printf "\n%b\n" "${BOLD}[3/4] 准备前端${RESET}"
(
  cd "$FRONTEND_DIR"
  pnpm install --frozen-lockfile
)
info "React 依赖已准备"

printf "\n%b\n" "${BOLD}[4/4] 启动应用${RESET}"
(
  cd "$BACKEND_DIR"
  exec "$BACKEND_DIR/.venv/bin/uvicorn" app.main:app --host 127.0.0.1 --port 8000
) &
BACKEND_PID=$!

(
  cd "$FRONTEND_DIR"
  exec node "$FRONTEND_DIR/node_modules/vite/bin/vite.js" \
    --host 127.0.0.1 --port 5173 --strictPort
) &
FRONTEND_PID=$!

sleep 2
kill -0 "$BACKEND_PID" 2>/dev/null || fail "FastAPI 启动失败。"
kill -0 "$FRONTEND_PID" 2>/dev/null || fail "React 启动失败。"

printf "\n%b\n" "${GREEN}${BOLD}ServiceLoop AI 已启动${RESET}"
printf "%s\n" "客户前端:  http://127.0.0.1:5173/customer"
printf "%s\n" "客服工作台: http://127.0.0.1:5173/agent"
printf "%s\n" "运营后台:  http://127.0.0.1:5173/operations"
printf "%s\n" "API 文档:  http://127.0.0.1:8000/docs"
printf "%s\n" "健康检查:  http://127.0.0.1:8000/health"
printf "\n%s\n" "按 Ctrl+C 关闭前后端；MySQL 数据会继续保留。"

while kill -0 "$BACKEND_PID" 2>/dev/null && kill -0 "$FRONTEND_PID" 2>/dev/null; do
  sleep 1
done

fail "有一个开发服务器意外退出，请查看上方日志。"
