#!/usr/bin/env bash
# One-shot setup for a fresh Ubuntu/Debian VPS (Oracle Cloud Always Free, Google Cloud e2-micro, ...).
# Safe to re-run: it updates the code and restarts the bot.
#
#   curl -fsSL <raw-url-of-this-file> | bash            # or: bash deploy/setup-server.sh
#
# Variables you can override:
#   REPO_URL  git URL (for a private repo: https://<token>@github.com/<owner>/<repo>.git)
#   BRANCH    branch to deploy (default: the repository default branch, or the current one when updating)
#   DIR       install directory (default: ~/lifeagent)
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/Kyzen-dev/LifeAgent.git}"
BRANCH="${BRANCH:-}"
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
  if [ -n "$BRANCH" ]; then
    git -C "$DIR" fetch origin "$BRANCH" && git -C "$DIR" checkout "$BRANCH"
  fi
  git -C "$DIR" pull --ff-only
else
  say "Cloning ${BRANCH:-default branch} into $DIR"
  command -v git >/dev/null || { sudo apt-get update -y && sudo apt-get install -y git; }
  git clone ${BRANCH:+--branch "$BRANCH"} "$REPO_URL" "$DIR"
fi
cd "$DIR"

# 4. Personal settings: run the wizard when .env is missing or incomplete.
needs_config() {
  ! python3 deploy/configure.py --complete
}
if needs_config; then
  if [ -t 0 ]; then
    say "Let's configure the bot (keys are checked as you type them)"
    python3 deploy/configure.py
  fi
  if needs_config; then
    echo "Required values are missing. Run:  cd $DIR && python3 deploy/configure.py   then re-run this script." >&2
    exit 1
  fi
else
  say "Checking the keys in .env"
  python3 deploy/configure.py --check || { echo "Fix .env with: python3 deploy/configure.py" >&2; exit 1; }
fi
[ -f workspace/memory/profile.md ] || echo "Tip: copy your personal profile.md to $DIR/workspace/memory/profile.md before the first chat."

# 5. The container runs as this user, so the bot and git can both write the files.
uid=$(id -u); gid=$(id -g)
grep -q '^LIFEAGENT_UID=' .env && sed -i "s/^LIFEAGENT_UID=.*/LIFEAGENT_UID=$uid/" .env || echo "LIFEAGENT_UID=$uid" >> .env
grep -q '^LIFEAGENT_GID=' .env && sed -i "s/^LIFEAGENT_GID=.*/LIFEAGENT_GID=$gid/" .env || echo "LIFEAGENT_GID=$gid" >> .env
mkdir -p data/home
sudo chown -R "$uid:$gid" data workspace

# 6. Build and start.
say "Building and starting the bot (first build takes a few minutes)"
$DOCKER compose up -d --build

# 7. Health check.
say "Running health checks"
$DOCKER compose run --rm lifeagent python -m lifeagent.doctor || true

say "Done. Logs: cd $DIR && $DOCKER compose logs -f"
echo "Send /start to your bot in Telegram."
