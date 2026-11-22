#!/bin/sh
# Installs or updates «مصادر» on the feedsnews VPS, next to the sites already there.
# Run as root on the server:
#
#   curl -fsSL https://raw.githubusercontent.com/osamafa86-dotcom/masader/main/deploy/vps/install.sh | sh
#
# Safe to run again: it pulls the latest main, keeps the existing .env and data,
# rebuilds, and reinstalls the Caddy site block only if it changed.
set -eu

DOMAIN="${SITE_DOMAIN:-masader.feedsnews.net}"
SITE_DIR="${SITE_DIR:-/opt/sites/masader}"
REPO="${REPO:-https://github.com/osamafa86-dotcom/masader.git}"
CADDY_DIR="${CADDY_DIR:-/srv/sites/caddy}"
CADDY_CONTAINER="${CADDY_CONTAINER:-deploy-caddy-1}"
CADDY_MAIN="${CADDY_MAIN:-/etc/caddy/Caddyfile}"
NETWORK="${SHARED_CADDY_NETWORK:-deploy_default}"
# For a dry run against prebuilt images: COMPOSE_EXTRA=extra.yml BUILD_FLAG=""
COMPOSE_EXTRA="${COMPOSE_EXTRA:-}"
BUILD_FLAG="${BUILD_FLAG---build}"

log() { printf '\n== %s\n' "$*"; }
die() { printf '\n!! %s\n' "$*" >&2; exit 1; }

log "checks"
command -v docker >/dev/null || die "docker is not installed"
docker compose version >/dev/null || die "docker compose plugin is missing"
docker network inspect "$NETWORK" >/dev/null 2>&1 || die "shared network $NETWORK not found (is the shared Caddy running?)"
docker inspect "$CADDY_CONTAINER" >/dev/null 2>&1 || die "Caddy container $CADDY_CONTAINER not found"
[ -d "$CADDY_DIR" ] || die "$CADDY_DIR not found"
if command -v free >/dev/null; then
  avail=$(free -m | awk '/^Mem:/ {print $7}')
  echo "available memory: ${avail} MB (the stack needs roughly 1200 MB)"
  [ "$avail" -ge 900 ] || die "not enough free memory to run the stack safely; stopping before changing anything"
fi

log "code -> $SITE_DIR"
if [ -d "$SITE_DIR/.git" ]; then
  git -C "$SITE_DIR" fetch -q origin main
  git -C "$SITE_DIR" reset -q --hard origin/main
else
  mkdir -p "$(dirname "$SITE_DIR")"
  git clone -q "$REPO" "$SITE_DIR"
fi
cd "$SITE_DIR"
echo "at $(git log --oneline -1)"

log "settings (.env)"
if [ ! -f .env ]; then
  rnd() { head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c "$1"; }
  sed -e "s|^SITE_DOMAIN=.*|SITE_DOMAIN=$DOMAIN|" \
      -e "s|^MARSAD_SITE_URL=.*|MARSAD_SITE_URL=https://$DOMAIN|" \
      -e "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$(rnd 40)|" \
      -e "s|^MARSAD_SECRET_KEY=.*|MARSAD_SECRET_KEY=$(rnd 64)|" \
      .env.example > .env
  chmod 600 .env
  echo "created .env with fresh secrets. Add a model key (ANTHROPIC_API_KEY, or MARSAD_LLM_BACKEND=gemini with MARSAD_GEMINI_API_KEY; optionally Voyage/SMTP) to $SITE_DIR/.env, then run this script again."
else
  echo "keeping the existing .env"
fi

log "containers"
COMPOSE="docker compose -f docker-compose.yml -f deploy/vps/docker-compose.vps.yml${COMPOSE_EXTRA:+ -f $COMPOSE_EXTRA}"
$COMPOSE up -d $BUILD_FLAG --remove-orphans
$COMPOSE ps

log "Caddy site block"
out="$CADDY_DIR/masader.caddy"
tmp=$(mktemp)
sed "s|__SITE_DOMAIN__|$DOMAIN|" deploy/vps/masader.caddy.tmpl > "$tmp"
if [ -f "$out" ] && cmp -s "$tmp" "$out"; then
  echo "unchanged"
  rm -f "$tmp"
else
  [ -f "$out" ] && cp "$out" "$out.bak"
  install -m 644 "$tmp" "$out"
  rm -f "$tmp"
  if docker exec "$CADDY_CONTAINER" caddy validate --config "$CADDY_MAIN" >/dev/null 2>&1; then
    docker exec "$CADDY_CONTAINER" caddy reload --config "$CADDY_MAIN"
    echo "installed $out and reloaded Caddy"
  else
    if [ -f "$out.bak" ]; then mv "$out.bak" "$out"; else rm -f "$out"; fi
    docker exec "$CADDY_CONTAINER" caddy validate --config "$CADDY_MAIN" || true
    die "Caddy rejected the new config; rolled back, nothing changed for the other sites"
  fi
fi
if ! docker exec "$CADDY_CONTAINER" caddy adapt --config "$CADDY_MAIN" 2>/dev/null | grep -q "$DOMAIN"; then
  echo "!! Caddy's main config does not load $out."
  echo "   The import lines it has now:"
  docker exec "$CADDY_CONTAINER" grep -n import "$CADDY_MAIN" || true
  die "add an import for masader.caddy next to the one for newsfeed.caddy, then run this script again"
fi

log "done"
echo "site: https://$DOMAIN  (needs a DNS A record for $DOMAIN pointing at this server)"
echo "first editor account:"
echo "  cd $SITE_DIR && $COMPOSE exec api marsad create-user EMAIL 'هيئة التحرير' --role admin"
