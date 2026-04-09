# Tower GUI Add-on

Local-only web interface for Tower control and monitoring.

## Overview

Tower GUI provides a browser-based interface for managing Tower workflows. It runs locally on your machine and does not expose any network ports to external hosts.

## Features

- **Kanban Board**: Visual card management with drag-and-drop
- **Action Buttons**: Quick access to common Tower operations
- **Real-time Status**: Auto-refreshing dashboard
- **Token Gate**: Quota tracking and consumption display
- **Event Log**: Live view of recent ledger events
- **SLO Panel**: Error budget and SLO status visualization

## Quick Start

```bash
# Install dependencies (one-time)
pip install flask

# Start the GUI server
python tower/addons/gui/tower_gui.py

# Or with custom port
python tower/addons/gui/tower_gui.py --port 5001

# Open in browser
# http://localhost:5000
```

## Security

The GUI is designed for **local use only**:

- Binds to `127.0.0.1` (localhost) by default
- Does NOT accept external connections
- No authentication required (local trust model)
- Read-only by default; write actions require confirmation

## API Endpoints

### Read Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /` | Main dashboard |
| `GET /api/status` | Tower status.json |
| `GET /api/cards` | All cards with states |
| `GET /api/card/<id>` | Single card details |
| `GET /api/slo` | SLO status |
| `GET /api/quota` | Token quota status |
| `GET /api/events` | Recent ledger events |
| `GET /api/freeze` | Merge freeze status |

### Action Endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /api/actions/validate` | Run validation |
| `POST /api/actions/gatecheck/<card_id>` | Run gatecheck for card |
| `POST /api/actions/dashboard` | Regenerate dashboard |
| `POST /api/actions/freeze` | Activate merge freeze |
| `POST /api/actions/unfreeze` | Clear merge freeze |

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `TOWER_GUI_PORT` | 5000 | Server port |
| `TOWER_GUI_HOST` | 127.0.0.1 | Bind address |
| `TOWER_ROOT` | auto-detect | Tower root directory |
| `TOWER_GUI_READONLY` | false | Disable action endpoints |

### Config File

Create `tower/addons/gui/gui_config.json`:

```json
{
  "port": 5000,
  "host": "127.0.0.1",
  "readonly": false,
  "refresh_interval_ms": 5000,
  "theme": "light"
}
```

## User Interface

### Kanban Board

Cards are displayed in columns by state:

| Column | States |
|--------|--------|
| Backlog | BACKLOG |
| Active | ACTIVE, IN_REVIEW |
| Validating | VALIDATING |
| Green | GREEN |
| Merged | MERGED |
| Blocked | ESCALATED, BLOCKED, ROLLED_BACK |

### Action Buttons

- **Validate All**: Run `tower_validate_all.sh`
- **Gatecheck**: Run `tower_gatecheck.sh` for selected card
- **Refresh**: Force dashboard regeneration
- **Freeze**: Activate/deactivate merge freeze

### Token Quota Panel

Displays:
- Current quota utilization
- Remaining budget
- Consumption rate
- Projected exhaustion date

## Files

| File | Description |
|------|-------------|
| `tower_gui.py` | Flask application server |
| `templates/index.html` | Main dashboard template |
| `templates/card_detail.html` | Card detail view |
| `static/style.css` | Stylesheet |
| `static/app.js` | Frontend JavaScript |

## Integration

### With Systemd (Linux)

```ini
# /etc/systemd/user/tower-gui.service
[Unit]
Description=Tower GUI Server
After=network.target

[Service]
Type=simple
WorkingDirectory=/path/to/project
ExecStart=/usr/bin/python3 tower/addons/gui/tower_gui.py
Restart=on-failure

[Install]
WantedBy=default.target
```

### With LaunchAgent (macOS)

```xml
<!-- ~/Library/LaunchAgents/com.tower.gui.plist -->
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.tower.gui</string>
    <key>ProgramArguments</key>
    <array>
        <string>/usr/bin/python3</string>
        <string>/path/to/tower/addons/gui/tower_gui.py</string>
    </array>
    <key>RunAtLoad</key>
    <true/>
    <key>WorkingDirectory</key>
    <string>/path/to/project</string>
</dict>
</plist>
```

## Troubleshooting

### Port Already in Use

```bash
# Find process using port
lsof -i :5000

# Use different port
python tower/addons/gui/tower_gui.py --port 5001
```

### Cannot Access from Browser

Ensure you're using `http://localhost:5000` or `http://127.0.0.1:5000`.
The server does NOT bind to external interfaces.

### Actions Not Working

Check that `TOWER_GUI_READONLY` is not set, and that the Tower scripts are executable.

### Missing Data

Ensure Tower control files exist:
```bash
ls tower/control/status.json
ls tower/control/quota.json
```

## Development

### Running in Debug Mode

```bash
FLASK_DEBUG=1 python tower/addons/gui/tower_gui.py
```

### Modifying Templates

Templates use Jinja2 syntax. Edit files in `tower/addons/gui/templates/`.

### Adding API Endpoints

Add routes to `tower_gui.py`:

```python
@app.route('/api/custom')
def custom_endpoint():
    return jsonify({"status": "ok"})
```
