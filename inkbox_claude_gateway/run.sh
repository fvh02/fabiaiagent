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
ICLOUD_APPLE_ID_OPT="$(opt icloud_apple_id)"
ICLOUD_APP_PASSWORD_OPT="$(opt icloud_app_password)"
ICLOUD_CALENDAR_OPT="$(opt icloud_calendar)"

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

# The gateway's Claude sessions load ~/.claude/CLAUDE.md; the add-on keeps
# its rules there in managed blocks and leaves anything else untouched.
USER_MEMORY="$HOME/.claude/CLAUDE.md"
mkdir -p "$(dirname "$USER_MEMORY")"
touch "$USER_MEMORY"
# set_block NAME [CONTENT]: replace block NAME with CONTENT, or remove it.
set_block() {
  local begin="<!-- inkbox-addon:$1:begin -->" end="<!-- inkbox-addon:$1:end -->"
  sed -i "\|$begin|,\|$end|d" "$USER_MEMORY"
  if [ -n "${2:-}" ]; then
    printf '%s\n%s\n%s\n' "$begin" "$2" "$end" >> "$USER_MEMORY"
  fi
}

if [ -n "$REPLY_LANGUAGE" ] && [ "$REPLY_LANGUAGE" != "Automatisch" ]; then
  set_block reply-language "## Reply language

Reply in $REPLY_LANGUAGE by default, on every channel (iMessage, SMS, email, calls).

Switch to another language only when:
- the person writes to you in that language, or
- the person sends a file, document or forwarded text in that language.

In those cases reply in that language; go back to $REPLY_LANGUAGE once the person writes in $REPLY_LANGUAGE again. If the person explicitly asks for a language, use it."
  echo "[inkbox] Antwortsprache: $REPLY_LANGUAGE"
else
  set_block reply-language
  echo "[inkbox] Antwortsprache: automatisch"
fi

# Tools Claude may use without asking: the plugin's read-only defaults, plus
# the calendar tool when it is configured.
AUTO_ALLOWED="Read,Glob,Grep,WebFetch,WebSearch,TodoWrite,Task,NotebookRead"
if [ -n "$ICLOUD_APPLE_ID_OPT" ] && [ -n "$ICLOUD_APP_PASSWORD_OPT" ]; then
  export ICLOUD_APPLE_ID="$ICLOUD_APPLE_ID_OPT" ICLOUD_APP_PASSWORD="$ICLOUD_APP_PASSWORD_OPT"
  export ICLOUD_CALENDAR="$ICLOUD_CALENDAR_OPT"
  AUTO_ALLOWED="$AUTO_ALLOWED,Bash(apple-calendar:*)"
  set_block apple-calendar "## Apple calendar

The person's Apple (iCloud) calendar is available through the \`apple-calendar\` command. Use it whenever the person asks to add, check, move or remove appointments, reminders or events. Run it directly (not combined with other commands); it prints JSON.

- \`apple-calendar calendars\` – list calendars and the default one
- \`apple-calendar list [--from \"YYYY-MM-DD HH:MM\"] [--to ...] [--days N] [--calendar NAME]\` – events, default next 7 days, all calendars
- \`apple-calendar add --title T --start \"YYYY-MM-DD HH:MM\" [--end ... | --duration MIN] [--location L] [--notes N] [--alarm MIN] [--calendar NAME]\`
- \`apple-calendar add --all-day --title T --start YYYY-MM-DD [--end YYYY-MM-DD]\` – all-day, end date inclusive
- \`apple-calendar delete --uid UID\` – UID from \`list\`

Rules:
- Times are local time (${TZ:-UTC}). Resolve relative dates such as \"tomorrow\" or \"next Friday\" yourself from today's date.
- Without an end time, events last 60 minutes. Without a calendar, the default calendar is used.
- Ask before guessing when the date or time is ambiguous.
- To move an event, add the new one, then delete the old one.
- Before deleting, make sure you have the right event; if several match, ask.
- After a change, confirm briefly with title, date, time and calendar."
  echo "[inkbox] Apple-Kalender: aktiv${ICLOUD_CALENDAR_OPT:+ (Standard: $ICLOUD_CALENDAR_OPT)}"
else
  set_block apple-calendar
  echo "[inkbox] Apple-Kalender: nicht eingerichtet"
fi
export INKBOX_AUTO_ALLOWED_TOOLS="$AUTO_ALLOWED"

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
