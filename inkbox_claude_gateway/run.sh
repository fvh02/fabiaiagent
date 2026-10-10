#!/usr/bin/env bash
# Entry point of the Home Assistant add-on: configure the Inkbox identity on
# first start (or when it changes), then run the gateway in the foreground.
set -euo pipefail

OPTIONS=/data/options.json
opt() { jq -r --arg k "$1" '.[$k] // empty' "$OPTIONS"; }

INKBOX_API_KEY_OPT="$(opt inkbox_api_key)"
IDENTITY="$(opt inkbox_identity)"
IDENTITY="${IDENTITY#@}"
ANTHROPIC_API_KEY_OPT="$(opt anthropic_api_key)"
CLAUDE_OAUTH_TOKEN_OPT="$(opt claude_oauth_token)"
PROJECT_DIR="$(opt project_dir)"
VOICE_AI="$(opt voice_ai)"
CLAUDE_MODEL_OPT="$(opt claude_model)"
REPLY_LANGUAGE="$(opt reply_language)"

die() { echo "[inkbox] FEHLER: $*" >&2; exit 1; }

[ -n "$INKBOX_API_KEY_OPT" ] || die "inkbox_api_key ist nicht gesetzt (Add-on → Konfiguration)."
[ -n "$IDENTITY" ] || die "inkbox_identity ist nicht gesetzt."
[ -n "$ANTHROPIC_API_KEY_OPT$CLAUDE_OAUTH_TOKEN_OPT" ] \
  || die "Setze anthropic_api_key oder claude_oauth_token (aus 'claude setup-token'), sonst kann Claude nicht antworten."

# Keep Claude and Inkbox state in /data so it survives restarts and updates.
export HOME=/data/home
export INKBOX_CLAUDE_HOME="$HOME/.inkbox-claude"
export INKBOX_CLAUDE_ENV_FILE="$INKBOX_CLAUDE_HOME/.env"
mkdir -p "$INKBOX_CLAUDE_HOME" "$PROJECT_DIR"
touch "$INKBOX_CLAUDE_ENV_FILE"
chmod 600 "$INKBOX_CLAUDE_ENV_FILE"

[ -n "$ANTHROPIC_API_KEY_OPT" ] && export ANTHROPIC_API_KEY="$ANTHROPIC_API_KEY_OPT"
[ -n "$CLAUDE_OAUTH_TOKEN_OPT" ] && export CLAUDE_CODE_OAUTH_TOKEN="$CLAUDE_OAUTH_TOKEN_OPT"
[ -n "$CLAUDE_MODEL_OPT" ] && export CLAUDE_MODEL="$CLAUDE_MODEL_OPT"

# The gateway's Claude sessions load ~/.claude/CLAUDE.md; keep the reply
# language rule in a managed block there and leave anything else untouched.
USER_MEMORY="$HOME/.claude/CLAUDE.md"
BEGIN_MARK="<!-- inkbox-addon:reply-language:begin -->"
END_MARK="<!-- inkbox-addon:reply-language:end -->"
mkdir -p "$(dirname "$USER_MEMORY")"
touch "$USER_MEMORY"
sed -i "\|$BEGIN_MARK|,\|$END_MARK|d" "$USER_MEMORY"
if [ -n "$REPLY_LANGUAGE" ] && [ "$REPLY_LANGUAGE" != "Automatisch" ]; then
  cat >> "$USER_MEMORY" <<EOF
$BEGIN_MARK
## Reply language

Reply in $REPLY_LANGUAGE by default, on every channel (iMessage, SMS, email, calls).

Switch to another language only when:
- the person writes to you in that language, or
- the person sends a file, document or forwarded text in that language.

In those cases reply in that language; go back to $REPLY_LANGUAGE once the person writes in $REPLY_LANGUAGE again. If the person explicitly asks for a language, use it.
$END_MARK
EOF
  echo "[inkbox] Antwortsprache: $REPLY_LANGUAGE"
else
  echo "[inkbox] Antwortsprache: automatisch"
fi

# Rotate the webhook signing key only when this add-on doesn't hold one for
# this identity yet; otherwise reuse it so restarts don't break delivery.
saved_identity="$(sed -n 's/^INKBOX_IDENTITY=//p' "$INKBOX_CLAUDE_ENV_FILE" | tail -n1)"
args=(bootstrap --api-key-stdin --identity "$IDENTITY" --base-url https://inkbox.ai --project-dir "$PROJECT_DIR")
if ! grep -q '^INKBOX_SIGNING_KEY=.' "$INKBOX_CLAUDE_ENV_FILE" || [ "$saved_identity" != "$IDENTITY" ]; then
  echo "[inkbox] Neuer Signing-Key für @$IDENTITY wird erzeugt (andere Gateways dieser Identität verlieren den Empfang)."
  args+=(--rotate-signing-key)
fi
[ "$VOICE_AI" = "true" ] && args+=(--voice-ai)

echo "[inkbox] Richte @$IDENTITY ein ..."
result="$(printf '%s' "$INKBOX_API_KEY_OPT" | inkbox-claude "${args[@]}")" || true
echo "$result"
status="$(printf '%s' "$result" | jq -r '.status // empty' 2>/dev/null || true)"
case "$status" in
  configured) ;;
  requires_human) die "Manueller Schritt nötig: $(printf '%s' "$result" | jq -r '.human_actions[]?')" ;;
  *) die "Bootstrap fehlgeschlagen. Siehe Ausgabe oben." ;;
esac

inkbox-claude doctor || true

echo "[inkbox] Starte Gateway ..."
cd "$PROJECT_DIR"
exec inkbox-claude run
