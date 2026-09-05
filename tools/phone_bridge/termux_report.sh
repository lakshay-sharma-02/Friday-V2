#!/data/data/com.termux/files/usr/bin/bash
#
# Friday phone telemetry reporter (Termux)
#
# Reads phone state the PC cannot see and POSTs it to Friday's /v1/phone
# endpoint so /friday phone|status and the planner's PHONE: context reflect
# *you*, not just the PC.
#
# Requires (inside Termux):
#   pkg install termux-api curl jq
#   termux-setup-storage  (for SMS permission prompt)
#   Android: grant Termux SMS access; enable Notification access for Termux
#            (Settings > Apps > Termux > Notifications access) for
#            termux-notification-list to return anything.
#
# Setup:
#   1. Point FRIDAY_URL at your PC (LAN IP if the API runs on the same
#      network, Tailscale IP otherwise). The API must be bound with a token:
#        FRIDAY_API_TOKEN=<token> python -m friday_mcu api --host 0.0.0.0
#   2. FRIDAY_TOKEN must match FRIDAY_API_TOKEN. Leave empty only if the API
#      runs on loopback of the same device (never for remote).
#   3. Run once by hand; then schedule every few minutes via:
#        pkg install cronie && crontab -e
#      or Termux:Widget / Tasker (Termux:Tasker plugin).
#
# What it reports:
#   battery %, charging, sms_unread, sms_latest, notifications (count),
#   notifications_top. Location is intentionally NOT read by default — set
#   REPORT_LOCATION=1 to include it (termux-location needs location access).
#
# Anything the reader cannot see (missing permission/package) is simply
# omitted from the payload — Friday only persists keys it receives.

FRIDAY_URL="${FRIDAY_URL:-http://192.168.1.10:8080}"
FRIDAY_TOKEN="${FRIDAY_TOKEN:-}"
REPORT_LOCATION="${REPORT_LOCATION:-0}"

json='{}'

# --- battery + charging -------------------------------------------------
if command -v termux-battery-status >/dev/null 2>&1; then
  b=$(termux-battery-status 2>/dev/null)
  if [ -n "$b" ]; then
    pct=$(printf '%s' "$b" | jq -r '.percentage // empty' 2>/dev/null)
    plugged=$(printf '%s' "$b" | jq -r '.plugged // empty' 2>/dev/null)
    if [ -n "$pct" ]; then
      json=$(printf '%s' "$json" | jq --argjson v "$pct" '.battery=$v')
    fi
    if [ -n "$plugged" ]; then
      if [ "$plugged" = "UNPLUGGED" ]; then
        json=$(printf '%s' "$json" | jq --argjson v false '.charging=$v')
      else
        json=$(printf '%s' "$json" | jq --argjson v true '.charging=$v')
      fi
    fi
  fi
fi

# --- SMS: unread count + latest sender/body ----------------------------
if command -v termux-sms-list >/dev/null 2>&1; then
  sms=$(termux-sms-list -l 20 2>/dev/null)
  if [ -n "$sms" ] && [ "$sms" != "[]" ]; then
    unread=$(printf '%s' "$sms" | jq '[.[] | select((.read|tostring)=="false")] | length' 2>/dev/null)
    if [ -n "$unread" ]; then
      json=$(printf '%s' "$json" | jq --argjson v "$unread" '.sms_unread=$v')
    fi
    latest=$(printf '%s' "$sms" | jq -r '.[] | select(.body != null) | "\(.sender // "?") : \(.body)"' 2>/dev/null | head -1 | cut -c1-120)
    if [ -n "$latest" ]; then
      json=$(printf '%s' "$json" | jq --arg v "$latest" '.sms_latest=$v')
    fi
  fi
fi

# --- notifications: count + top package --------------------------------
if command -v termux-notification-list >/dev/null 2>&1; then
  n=$(termux-notification-list 2>/dev/null)
  if [ -n "$n" ] && [ "$n" != "[]" ]; then
    count=$(printf '%s' "$n" | jq 'length' 2>/dev/null)
    if [ -n "$count" ]; then
      json=$(printf '%s' "$json" | jq --argjson v "$count" '.notifications=$v')
    fi
    top=$(printf '%s' "$n" | jq -r '[.[].packageName // empty] | group_by(.) | max_by(length) | .[0]' 2>/dev/null)
    if [ -n "$top" ] && [ "$top" != "null" ]; then
      json=$(printf '%s' "$json" | jq --arg v "$top" '.notifications_top=$v')
    fi
  fi
fi

# --- optional location ---------------------------------------------------
if [ "$REPORT_LOCATION" = "1" ] && command -v termux-location >/dev/null 2>&1; then
  loc=$(termux-location -p network 2>/dev/null)
  if [ -n "$loc" ]; then
    label=$(printf '%s' "$loc" | jq -r '"\(.latitude),\(.longitude) (acc \(.accuracy // "?"))"' 2>/dev/null)
    if [ -n "$label" ] && [ "$label" != "null" ]; then
      json=$(printf '%s' "$json" | jq --arg v "$label" '.location=$v')
    fi
  fi
fi

if [ "$json" = "{}" ]; then
  echo "Friday bridge: nothing to report (is termux-api installed and granted access?)" >&2
  exit 1
fi

auth=()
[ -n "$FRIDAY_TOKEN" ] && auth=(-H "Authorization: Bearer $FRIDAY_TOKEN")

if curl -sS -m 10 -o /dev/null -X POST "$FRIDAY_URL/v1/phone" \
  -H "Content-Type: application/json" "${auth[@]}" -d "$json"; then
  echo "Friday bridge: reported $(printf '%s' "$json" | jq -c 'keys')"
else
  echo "Friday bridge: POST failed ($FRIDAY_URL) — check URL/token/network" >&2
  exit 1
fi
