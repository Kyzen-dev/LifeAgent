#!/usr/bin/env bash
# One-shot setup for a fresh Ubuntu/Debian VPS (Oracle Cloud Always Free, Google Cloud e2-micro, ...).
# Safe to re-run: it updates the code and restarts the bot.
#
#   curl -fsSL <raw-url-of-this-file> | bash            # or: bash deploy/setup-server.sh
#
# Variables you can override:
#   REPO_URL  git URL (for a private repo: https://<token>@github.com/<owner>/<repo>.git)
#   BRANCH    branch to deploy (default: main)
#   DIR       install directory (default: ~/lifeagent)
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/Kyzen-dev/LifeAgent.git}"
BRANCH="${BRANCH:-main}"
DIR="${DIR:-$HOME/lifeagent}"

say() { printf '\n\033[1;32m==> %s\033[0m\n' "$*"; }

# 1. Swap on small machines (Docker builds and the agent need headroom on 1 GB VMs).
mem_mb=$(awk '/MemTotal/ {print int($2/1024)}' /proc/meminfo)
if [ "$mem_mb" -lt 2500 ] && ! swapon --show | grep -q .; then
  say "RAM is ${mem_mb} MB — adding a 2 GB swap file"
  sudo fallocate -l 2G /swapfile || sudo dd if=/dev/zero of=/swapfile bs=1M count=2048
  sudo chmod 600 /swapfile && sudo mkswap /swapfile && sudo swapon /swapfile
  grep -q '/swapfile' /etc/fstab || echo '/swapfile none swap sw 0 0' | sudo tee -a /etc/fstab >/dev/null
fi

# 2. Docker + compose plugin.
if ! command -v docker >/dev/null 2>&1; then
  say "Installing Docker"
  curl -fsSL https://get.docker.com | sudo sh
  sudo usermod -aG docker "$USER" || true
fi
DOCKER="docker"
docker info >/dev/null 2>&1 || DOCKER="sudo docker"

# 3. Code.
if [ -d "$DIR/.git" ]; then
  say "Updating code in $DIR"
  git -C "$DIR" fetch origin "$BRANCH" && git -C "$DIR" checkout "$BRANCH" && git -C "$DIR" pull --ff-only origin "$BRANCH"
else
  say "Cloning $BRANCH into $DIR"
  command -v git >/dev/null || { sudo apt-get update -y && sudo apt-get install -y git; }
  git clone --branch "$BRANCH" "$REPO_URL" "$DIR"
fi
cd "$DIR"

# 4. Personal files.
if [ ! -f .env ]; then
  cp .env.example .env
  say "Created .env from the example. Fill in TELEGRAM_BOT_TOKEN, TELEGRAM_ALLOWED_USER_IDS and ANTHROPIC_API_KEY:"
  echo "    nano $DIR/.env      # then re-run this script"
  exit 0
fi
if grep -qE '^(TELEGRAM_BOT_TOKEN|TELEGRAM_ALLOWED_USER_IDS|ANTHROPIC_API_KEY)=\s*$' .env; then
  echo "Some required values in .env are still empty. Edit $DIR/.env and re-run." >&2
  exit 1
fi
[ -f workspace/memory/profile.md ] || echo "Tip: copy your personal profile.md to $DIR/workspace/memory/profile.md"

# 5. Permissions for the container user (uid 1000).
mkdir -p data
sudo chown -R 1000:1000 data workspace

# 6. Build and start.
say "Building and starting the bot (first build takes a few minutes)"
$DOCKER compose up -d --build

# 7. Health check.
say "Running health checks"
$DOCKER compose run --rm lifeagent python -m lifeagent.doctor || true

say "Done. Logs: cd $DIR && $DOCKER compose logs -f"
echo "Send /start to your bot in Telegram."
