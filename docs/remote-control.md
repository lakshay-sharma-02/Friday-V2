# Friday Remote Control — Phone Integration

Control Friday from your phone using Tailscale (free mesh VPN) and the HTTP API.

## Architecture

```
┌─────────┐     Tailscale      ┌──────────────────┐
│  Phone  │ ◄─── VPN tunnel ──► │  Windows PC      │
│ (iOS/   │                     │                  │
│ Android)│     HTTP API        │  localhost:8080  │
│         │ ◄─────────────────► │  (Friday API)    │
└─────────┘                     └──────────────────┘
```

**How it works:**
1. Tailscale creates a private network between your PC and phone
2. Friday runs an HTTP API server on your PC
3. Phone calls the API over the Tailscale tunnel
4. Everything stays on your private network (no public internet exposure)

## Step 1: Install Tailscale (5 minutes)

### On your PC (Windows)

```powershell
# Download and install from:
# https://tailscale.com/download/windows

# Or use winget:
winget install tailscale.tailscale

# Sign in with your Google/GitHub/Microsoft account
tailscale up
```

### On your phone

- **iOS**: App Store → "Tailscale"
- **Android**: Play Store → "Tailscale"

Sign in with the **same account** as your PC.

### Verify connection

```powershell
# On your PC, find your phone's Tailscale IP:
tailscale status

# You'll see something like:
# 100.x.x.x    phone-name     user@   ios/android
```

## Step 2: Start Friday API Server

```powershell
# From the Friday V2 project directory:
cd "C:\Users\Lakshay Sharma\Desktop\Projects\Friday V2"

# Start the API server (default port 8080):
.venv\Scripts\python -m friday.api_server

# Or with custom port:
.venv\Scripts\python -m friday.api_server --port 9000
```

You'll see:
```
🤖 Friday API Server v0.8.0
   Listening on http://0.0.0.0:8080
   Auth: disabled (open access)

   Endpoints:
     GET  /health       - Health check
     GET  /status       - System status
     GET  /triggers     - List triggers
     GET  /memory?q=... - Query memory
     GET  /logs?n=20    - Recent logs
     GET  /primitives   - List primitives
     POST /goal         - Execute a goal
```

## Step 3: Access from Your Phone

### Find your PC's Tailscale IP

```powershell
tailscale ip -4
# Returns: 100.x.x.x
```

### Test the connection

From your phone's browser or a REST client (like Postman/Insomnia):

```
http://100.x.x.x:8080/health
```

You should see:
```json
{"status": "ok", "server": "friday-api", "version": "0.8.0", "uptime_s": 42}
```

## API Reference

### Health Check
```
GET /health
```
Always returns 200. Use to verify connectivity.

### System Status
```
GET /status
```
Returns:
```json
{
  "status": "ok",
  "version": "0.8.0",
  "primitives": {"total": 97, "blocked": 1},
  "triggers": {"enabled": 9, "total": 20},
  "tasks": {"passing": 45, "total": 67},
  "memory": {"entries": 15}
}
```

### Execute a Goal
```
POST /goal
Content-Type: application/json

{"goal": "take a screenshot and describe what you see"}
```

Returns immediately with:
```json
{
  "status": "accepted",
  "run_id": "api-1692900000",
  "goal": "take a screenshot and describe what you see",
  "message": "Goal accepted. Poll GET /goal/{run_id} for result."
}
```

The goal runs in the background. To get the result, save it to a file:

### List Triggers
```
GET /triggers
```
Returns all configured triggers with their status.

### Query Memory
```
GET /memory              # Summary
GET /memory?q=gmail      # Search
```

### Recent Logs
```
GET /logs?n=50           # Last 50 entries
```

### List Primitives
```
GET /primitives
```

## Step 4: Phone Apps

### iOS/Android REST Clients

**Postman** (iOS/Android):
- Create a new request
- Enter `http://100.x.x.x:8080/status`
- Tap Send

**HTTP Shortcuts** (Android):
- Create a new shortcut
- URL: `http://100.x.x.x:8080/goal`
- Method: POST
- Body: `{"goal": "show me my calendar"}`

**Scriptable** (iOS):
```javascript
let url = "http://100.x.x.x:8080/status"
let response = await Request.get(url).response
console.log(JSON.parse(response))
```

### Quick Commands (curl from Termux)

```bash
# Install Termux on Android, then:
pkg install curl

# Check status
curl http://100.x.x.x:8080/status

# Execute a goal
curl -X POST http://100.x.x.x:8080/goal \
  -H "Content-Type: application/json" \
  -d '{"goal": "what time is it?"}'

# Search memory
curl http://100.x.x.x:8080/memory?q=gmail
```

## Step 5: Security (Optional)

### Add API Key Authentication

```powershell
# Set an API key:
setx FRIDAY_API_KEY "your-secret-key-here"

# Restart the API server
```

Now all requests need the key:
```
Authorization: Bearer your-secret-key-here
```

### Restrict to Tailscale Only

The API server binds to `0.0.0.0` by default. To restrict to localhost only:

```powershell
.venv\Scripts\python -m friday.api_server --host 127.0.0.1
```

Then access only via Tailscale's encrypted tunnel.

## Example Use Cases

### "Send me a screenshot"
```
POST /goal
{"goal": "take a screenshot of my screen and describe what you see"}
```

### "What's on my calendar?"
```
POST /goal
{"goal": "show me my calendar events for today"}
```

### "Check my email"
```
POST /goal
{"goal": "check my unread emails and summarize the latest one"}
```

### "Pause my music"
```
POST /goal
{"goal": "pause whatever is playing"}
```

## Troubleshooting

| Problem | Solution |
|---------|----------|
| Phone can't reach PC | Verify both devices are on Tailscale: `tailscale status` |
| Connection refused | Ensure Friday API is running: `curl http://localhost:8080/health` |
| Timeout | Check firewall allows port 8080: `netsh advfirewall firewall add rule name="Friday API" dir=in action=allow protocol=TCP localport=8080` |
| Auth errors | If FRIDAY_API_KEY is set, include `Authorization: Bearer <key>` header |

## Running as a Service (Windows)

To start the API server automatically:

```powershell
# Create a scheduled task:
schtasks /create /tn "FridayAPI" /tr "C:\Users\Lakshay Sharma\Desktop\Projects\Friday V2\.venv\Scripts\python.exe -m friday.api_server" /sc onlogon /rl highest
```

Or add to `deploy/start-friday-services.bat`.
