# Phone bridge — pair your Android phone with Friday

Friday runs on your PC; the phone half of your world (battery, SMS,
notifications, presence) has to be reported in. Pick whichever bridge you
already have:

| Option | Cost | Reads | Effort |
|---|---|---|---|
| **Termux** (`termux_report.sh`) | free | battery, SMS, notifications, (opt-in) location | pkg installs + 2 permissions |
| **Tasker** | paid app | anything you can build (incl. call log, missed calls) | a few HTTP Request actions |
| **HTTP Shortcuts** | free | whatever you feed it | one POST per shortcut |

All three just POST a JSON snapshot to `POST /v1/phone`. Friday keeps only
allowlisted keys: `device, battery, charging, activity, location,
do_not_disturb, wifi, nearby, note, sms_unread, sms_latest, missed_calls,
notifications, notifications_top`. No secrets.

## 0. Prepare the PC side

The API must be reachable from the phone and authenticated:

```bash
# LAN pairing (same WiFi): bind all interfaces with a token
FRIDAY_API_TOKEN=$(openssl rand -hex 24) \
  python -m friday_mcu api --host 0.0.0.0 --port 8080
# or over Tailscale:
FRIDAY_API_TOKEN=$(openssl rand -hex 24) \
  python -m friday_mcu api --host 0.0.0.0   # reachable at the Tailscale IP
```

Note the token and your PC's address (LAN IP or Tailscale IP). If the phone
can't connect, allow the port through Windows Firewall for private networks.
Verify from the PC first:

```bash
curl http://127.0.0.1:8080/health
```

## 1. Termux (recommended, free)

```bash
pkg install termux-api curl jq
termux-setup-storage          # then allow SMS access for Termux when asked
```

Copy the reporter to the phone and configure the two variables at the top:

```bash
# on the phone (in Termux):
cp termux_report.sh $HOME/friday_report.sh
chmod +x $HOME/friday_report.sh
export FRIDAY_URL="http://<PC-LAN-IP>:8080"   # or Tailscale IP
export FRIDAY_TOKEN="<the-token>"
$HOME/friday_report.sh        # run once — watch it print "reported [...]"
```

Then schedule it:

```bash
pkg install cronie
crond
crontab -e
# */5 * * * * FRIDAY_URL=http://<PC>:8080 FRIDAY_TOKEN=<token> $HOME/friday_report.sh >> $HOME/friday_report.log 2>&1
```

(Enable Termux's notification access for `termux-notification-list`:
Settings > Apps > Termux > Notifications. SMS needs the Android SMS
permission for Termux.)

## 2. Tasker

Make a Tasker task that runs every few minutes:
1. **Variables**: `%FRIDAY_URL`, `%FRIDAY_TOKEN` (or read from a file).
2. **HTTP Request**: URL `%FRIDAY_URL/v1/phone`, Method `POST`,
   Headers `Content-Type: application/json`, `Authorization: Bearer %FRIDAY_TOKEN`.
3. **Body** (JavaScriptlet or Variable set from your own sensors):
   ```json
   {"battery": 84, "charging": true, "activity": "walking",
    "sms_unread": 2, "missed_calls": 1, "notifications": 5}
   ```
   Tasker's native **Call Log** and **SMS** sources can fill the SMS/missed-call
   fields Tasker has access to.
4. **Profile** → Time / Any event → run the task.

## 3. HTTP Shortcuts (lightweight)

Create one shortcut: method `POST`, URL `http://<PC>:8080/v1/phone`,
headers `Authorization: Bearer <token>` + `Content-Type: application/json`,
body the JSON above (fill fields from the app's variable syntax), schedule it
with the app's time trigger.

## Verify it worked

From any chat or the REPL:

```
/friday phone        →  Phone: device: Pixel 8, battery: 84%, sms: 2 unread, seen 2m ago
/friday status       →  ...same block appended
```

Or from the PC:

```bash
curl http://127.0.0.1:8080/v1/phone
```

The `PHONE:` block also feeds the planner context, so goals can react to
presence ("you're out — defer notifications", "you're at your desk — go").
