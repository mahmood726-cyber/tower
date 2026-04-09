#!/usr/bin/env bash
#
# Tower Cockpit Dashboard Generator
# Generates dashboard.json and dashboard.html (file:// safe, read-only GUI)
#
# Usage:
#   tower_dashboard.sh
#
# Output:
#   tower/control/dashboard.json (machine-readable)
#   tower/control/dashboard.html (self-contained GUI)
#

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TOWER_ROOT="$(dirname "$SCRIPT_DIR")"

# Detect Python command (python3 or python)
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "ERROR: Neither python3 nor python found"
    exit 1
fi

SPEC_VERSION="v1.5.7"

JSON_OUTPUT="$TOWER_ROOT/control/dashboard.json"
HTML_OUTPUT="$TOWER_ROOT/control/dashboard.html"

echo "============================================================"
echo "Tower Cockpit Dashboard Generator"
echo "Output JSON: $JSON_OUTPUT"
echo "Output HTML: $HTML_OUTPUT"
echo "============================================================"

$PYTHON_CMD << 'PYTHON_SCRIPT'
import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from html import escape

tower_root = Path(os.environ.get('TOWER_ROOT', Path(__file__).parent.parent))
spec_version = "v1.5.5"

def load_json(path):
    try:
        with open(path) as f:
            return json.load(f)
    except:
        return None

def safe_get(d, *keys, default=None):
    for key in keys:
        if isinstance(d, dict):
            d = d.get(key, default)
        else:
            return default
    return d

# Load all control files
status = load_json(tower_root / "control" / "status.json") or {}
quota = load_json(tower_root / "control" / "quota.json") or {}
machines = load_json(tower_root / "control" / "machines.json") or {}
backlog = load_json(tower_root / "control" / "backlog.json") or {}
papers_registry = load_json(tower_root / "papers" / "paper_registry.json") or {}

# Load alerts
drift_alerts = load_json(tower_root / "control" / "alerts" / "drift_alerts.json") or []
efficiency_alerts = load_json(tower_root / "control" / "alerts" / "efficiency_alerts.json") or {}

# Count cards by state
cards_data = status.get("cards", {})
state_counts = {}
for card_id, card in cards_data.items():
    state = card.get("state", "UNKNOWN")
    state_counts[state] = state_counts.get(state, 0) + 1

# Build cards list with enrichment
cards_list = []
now = datetime.now()

# Discover artifacts and proofpacks (bounded to last 30 days)
artifacts_dir = tower_root / "artifacts"
proofpacks_dir = tower_root / "proofpacks"

def find_latest_path(base_dir, card_id, max_days=30):
    """Find the most recent path for a card in date-organized folders."""
    if not base_dir.exists():
        return None

    # Check recent date folders
    try:
        date_dirs = sorted(
            [d for d in base_dir.iterdir() if d.is_dir() and d.name.startswith("20")],
            reverse=True
        )[:max_days]
    except:
        return None

    for date_dir in date_dirs:
        card_path = date_dir / card_id
        if card_path.exists():
            return str(card_path.relative_to(tower_root))

    return None

# Check for drift alerts per card
drift_alert_cards = set()
if isinstance(drift_alerts, list):
    for alert in drift_alerts:
        if isinstance(alert, dict):
            drift_alert_cards.add(alert.get("card_id", ""))
elif isinstance(drift_alerts, dict):
    for alert in drift_alerts.get("alerts", []):
        if isinstance(alert, dict):
            drift_alert_cards.add(alert.get("card_id", ""))

# Check for quota pauses (simplified - if any model at >95% usage)
quota_paused_models = set()
for model_id, model in quota.get("models", {}).items():
    daily_limit = model.get("daily_limit", 0)
    used_today = model.get("used_today", 0)
    if daily_limit > 0 and used_today / daily_limit >= 0.95:
        quota_paused_models.add(model_id)

for card_id, card in cards_data.items():
    # Try to find title from card file
    card_file = tower_root / "control" / "cards" / f"{card_id}.json"
    card_details = load_json(card_file) or {}
    title = card_details.get("title") or card.get("title", "")

    # Find latest artifacts and proofpack
    latest_artifacts = find_latest_path(artifacts_dir, card_id)
    latest_proofpack = find_latest_path(proofpacks_dir, card_id)

    # Check for last run_id from artifacts
    last_run_id = None
    if latest_artifacts:
        artifacts_path = tower_root / latest_artifacts
        if artifacts_path.exists():
            run_dirs = sorted([d.name for d in artifacts_path.iterdir() if d.is_dir() and d.name.startswith("run_")], reverse=True)
            if run_dirs:
                last_run_id = run_dirs[0].replace("run_", "")

    cards_list.append({
        "card_id": card_id,
        "title": title,
        "stream": card.get("stream", ""),
        "state": card.get("state", "UNKNOWN"),
        "color": card.get("color", "RED"),
        "last_update": card.get("updated_at", ""),
        "last_run_id": last_run_id,
        "latest_artifacts_path": latest_artifacts,
        "latest_proofpack_path": latest_proofpack,
        "has_drift_alert": card_id in drift_alert_cards,
        "has_efficiency_alert": False,  # TODO: implement per-card efficiency alerts
        "has_quota_pause": len(quota_paused_models) > 0  # Simplified
    })

# Sort cards by last_update descending
cards_list.sort(key=lambda x: x.get("last_update", "") or "", reverse=True)

# Quota summary
quota_summary = []
for model_id, model in quota.get("models", {}).items():
    daily_limit = model.get("daily_limit", 0)
    used_today = model.get("used_today", 0)
    weekly_limit = model.get("weekly_limit", 0)
    used_week = model.get("used_this_week", 0)

    quota_summary.append({
        "model": model_id,
        "daily_limit": daily_limit,
        "daily_used": used_today,
        "daily_percent": round(used_today / daily_limit * 100, 1) if daily_limit > 0 else 0,
        "weekly_limit": weekly_limit,
        "weekly_used": used_week,
        "weekly_percent": round(used_week / weekly_limit * 100, 1) if weekly_limit > 0 else 0
    })

# PC summary
pc_summary = []
for machine_id, machine in machines.get("machines", {}).items():
    if machine.get("type") == "pc":
        pc_summary.append({
            "pc_id": machine_id,
            "online": machine.get("online", False),
            "last_seen": machine.get("last_seen"),
            "cpu_utilization": safe_get(machine, "current_load", "cpu_percent"),
            "ram_utilization": safe_get(machine, "current_load", "ram_percent")
        })

# Alerts summary
alerts_list = []
if isinstance(drift_alerts, list):
    for alert in drift_alerts[:10]:
        if isinstance(alert, dict):
            alerts_list.append({
                "type": "drift",
                "message": alert.get("message", "Drift alert"),
                "card_id": alert.get("card_id"),
                "timestamp": alert.get("timestamp")
            })

for alert in efficiency_alerts.get("alerts", [])[:10]:
    if isinstance(alert, dict):
        alerts_list.append({
            "type": "efficiency",
            "message": alert.get("message", "Efficiency alert"),
            "timestamp": alert.get("timestamp")
        })

# Papers summary
papers = papers_registry.get("papers", [])
paper_counts = {}
for paper in papers:
    status_val = paper.get("status", "unknown")
    paper_counts[status_val] = paper_counts.get(status_val, 0) + 1

# Build dashboard JSON
dashboard = {
    "spec_version": spec_version,
    "generated_at": datetime.now().isoformat(),
    "card_counts_by_state": state_counts,
    "cards": cards_list,
    "quota_summary": quota_summary,
    "pc_summary": pc_summary,
    "alerts": {
        "total_count": len(alerts_list),
        "items": alerts_list
    },
    "papers": {
        "counts_by_status": paper_counts,
        "total": len(papers)
    }
}

# Write JSON atomically
json_file = tower_root / "control" / "dashboard.json"
tmp_file = str(json_file) + ".tmp"
with open(tmp_file, 'w') as f:
    json.dump(dashboard, f, indent=2)
os.replace(tmp_file, str(json_file))
print(f"Generated: {json_file}")

# Generate HTML
dashboard_json_str = json.dumps(dashboard, indent=2)

html_content = '''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tower Cockpit v''' + spec_version + '''</title>
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #1a1a2e; color: #eee; min-height: 100vh; }
        .header { background: #16213e; padding: 15px 20px; border-bottom: 2px solid #0f3460; display: flex; justify-content: space-between; align-items: center; }
        .header h1 { font-size: 1.5em; color: #e94560; }
        .header .meta { color: #888; font-size: 0.85em; }
        .container { max-width: 1600px; margin: 0 auto; padding: 20px; }

        /* Summary tiles */
        .tiles { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; margin-bottom: 20px; }
        .tile { background: #16213e; border-radius: 8px; padding: 15px; border-left: 4px solid #0f3460; }
        .tile.green { border-left-color: #28a745; }
        .tile.yellow { border-left-color: #ffc107; }
        .tile.red { border-left-color: #dc3545; }
        .tile-title { color: #888; font-size: 0.8em; text-transform: uppercase; margin-bottom: 5px; }
        .tile-value { font-size: 2em; font-weight: bold; }
        .tile-sub { font-size: 0.85em; color: #aaa; margin-top: 5px; }

        /* Tabs */
        .tabs { display: flex; gap: 5px; margin-bottom: 20px; flex-wrap: wrap; }
        .tab { background: #16213e; border: none; color: #888; padding: 10px 20px; border-radius: 6px 6px 0 0; cursor: pointer; font-size: 0.9em; }
        .tab:hover { background: #1f2b47; }
        .tab.active { background: #0f3460; color: #fff; }
        .tab-content { display: none; background: #16213e; border-radius: 0 8px 8px 8px; padding: 20px; min-height: 400px; }
        .tab-content.active { display: block; }

        /* Tables */
        table { width: 100%; border-collapse: collapse; }
        th, td { padding: 10px 12px; text-align: left; border-bottom: 1px solid #0f3460; }
        th { background: #0f3460; font-weight: 600; font-size: 0.85em; color: #aaa; text-transform: uppercase; }
        tr:hover { background: #1f2b47; }

        /* Badges */
        .badge { display: inline-block; padding: 3px 8px; border-radius: 4px; font-size: 0.75em; font-weight: bold; }
        .badge-green { background: #28a745; color: white; }
        .badge-yellow { background: #ffc107; color: #333; }
        .badge-red { background: #dc3545; color: white; }
        .badge-blue { background: #17a2b8; color: white; }
        .badge-gray { background: #6c757d; color: white; }

        /* Status */
        .status-online { color: #28a745; }
        .status-offline { color: #dc3545; }

        /* Progress */
        .progress { background: #0f3460; border-radius: 4px; height: 8px; overflow: hidden; width: 100px; display: inline-block; vertical-align: middle; margin-right: 8px; }
        .progress-bar { height: 100%; transition: width 0.3s; }
        .progress-bar.low { background: #28a745; }
        .progress-bar.medium { background: #ffc107; }
        .progress-bar.high { background: #dc3545; }

        /* Links */
        a { color: #17a2b8; text-decoration: none; }
        a:hover { text-decoration: underline; }

        /* Controls */
        .controls { display: flex; gap: 10px; margin-bottom: 15px; flex-wrap: wrap; }
        .search-input { background: #0f3460; border: 1px solid #1f2b47; color: #fff; padding: 8px 12px; border-radius: 4px; min-width: 200px; }
        .search-input::placeholder { color: #666; }
        select { background: #0f3460; border: 1px solid #1f2b47; color: #fff; padding: 8px 12px; border-radius: 4px; }

        /* Buttons */
        .btn { background: #0f3460; border: 1px solid #1f2b47; color: #fff; padding: 6px 12px; border-radius: 4px; cursor: pointer; font-size: 0.85em; }
        .btn:hover { background: #1f2b47; }
        .btn-copy { background: #17a2b8; border-color: #17a2b8; }
        .btn-copy:hover { background: #138496; }

        /* Alerts */
        .alert-item { background: #1f2b47; padding: 10px 15px; border-radius: 4px; margin-bottom: 8px; border-left: 3px solid #ffc107; }
        .alert-item.drift { border-left-color: #dc3545; }
        .alert-item .alert-type { font-size: 0.75em; color: #888; text-transform: uppercase; }
        .alert-item .alert-message { margin-top: 4px; }

        /* Empty state */
        .empty { text-align: center; padding: 40px; color: #666; }

        /* Footer */
        .footer { margin-top: 30px; padding: 20px; text-align: center; color: #666; font-size: 0.85em; border-top: 1px solid #0f3460; }
        .footer a { color: #888; }
    </style>
</head>
<body>
    <div class="header">
        <h1>Tower Cockpit</h1>
        <div class="meta">Spec ''' + spec_version + ''' | Generated: <span id="gen-time"></span></div>
    </div>

    <div class="container">
        <!-- Summary Tiles -->
        <div class="tiles" id="summary-tiles"></div>

        <!-- Tabs -->
        <div class="tabs">
            <button class="tab active" data-tab="inbox">Inbox</button>
            <button class="tab" data-tab="merge">Merge Ready</button>
            <button class="tab" data-tab="cards">All Cards</button>
            <button class="tab" data-tab="quotas">Quotas & PCs</button>
            <button class="tab" data-tab="alerts">Alerts</button>
            <button class="tab" data-tab="papers">Papers</button>
        </div>

        <!-- Tab Contents -->
        <div class="tab-content active" id="tab-inbox"></div>
        <div class="tab-content" id="tab-merge"></div>
        <div class="tab-content" id="tab-cards"></div>
        <div class="tab-content" id="tab-quotas"></div>
        <div class="tab-content" id="tab-alerts"></div>
        <div class="tab-content" id="tab-papers"></div>

        <div class="footer">
            <a href="dashboard.json">dashboard.json</a> |
            <a href="../artifacts/">artifacts/</a> |
            <a href="../proofpacks/">proofpacks/</a>
        </div>
    </div>

    <script type="application/json" id="dash-data">
''' + dashboard_json_str + '''
    </script>

    <script>
    (function() {
        const data = JSON.parse(document.getElementById('dash-data').textContent);

        // Update generation time
        document.getElementById('gen-time').textContent = new Date(data.generated_at).toLocaleString();

        // Helper functions
        function getStateBadge(state, color) {
            const colorClass = {GREEN: 'badge-green', YELLOW: 'badge-yellow', RED: 'badge-red'}[color] || 'badge-gray';
            return `<span class="badge ${colorClass}">${state}</span>`;
        }

        function getProgressBar(percent) {
            const cls = percent < 50 ? 'low' : percent < 80 ? 'medium' : 'high';
            return `<div class="progress"><div class="progress-bar ${cls}" style="width:${Math.min(percent, 100)}%"></div></div>${percent.toFixed(1)}%`;
        }

        // Render summary tiles
        const tiles = document.getElementById('summary-tiles');
        const counts = data.card_counts_by_state || {};
        const total = Object.values(counts).reduce((a,b) => a+b, 0);
        const green = (counts['GOLD'] || 0) + (counts['MERGED'] || 0) + (counts['VALIDATORS_PASS'] || 0);
        const yellow = (counts['ACTIVE'] || 0) + (counts['READY'] || 0) + (counts['REVIEW'] || 0);
        const red = (counts['BLOCKED'] || 0) + (counts['ESCALATED'] || 0);

        tiles.innerHTML = `
            <div class="tile"><div class="tile-title">Total Cards</div><div class="tile-value">${total}</div></div>
            <div class="tile green"><div class="tile-title">GREEN</div><div class="tile-value">${green}</div><div class="tile-sub">GOLD + MERGED</div></div>
            <div class="tile yellow"><div class="tile-title">In Progress</div><div class="tile-value">${yellow}</div><div class="tile-sub">ACTIVE + READY</div></div>
            <div class="tile red"><div class="tile-title">Needs Attention</div><div class="tile-value">${red}</div><div class="tile-sub">BLOCKED + ESCALATED</div></div>
            <div class="tile"><div class="tile-title">Alerts</div><div class="tile-value">${data.alerts?.total_count || 0}</div></div>
            <div class="tile"><div class="tile-title">PCs Online</div><div class="tile-value">${(data.pc_summary || []).filter(p => p.online).length}/${(data.pc_summary || []).length}</div></div>
        `;

        // Inbox: ESCALATED first, then drift alerts, then REVIEW, then BLOCKED
        const inboxCards = (data.cards || []).filter(c =>
            ['ESCALATED', 'BLOCKED', 'REVIEW'].includes(c.state) || c.has_drift_alert
        ).sort((a, b) => {
            const priority = {'ESCALATED': 0, 'drift': 1, 'REVIEW': 2, 'BLOCKED': 3};
            const pa = a.state === 'ESCALATED' ? 0 : a.has_drift_alert ? 1 : priority[a.state] || 4;
            const pb = b.state === 'ESCALATED' ? 0 : b.has_drift_alert ? 1 : priority[b.state] || 4;
            return pa - pb;
        });

        document.getElementById('tab-inbox').innerHTML = inboxCards.length ? `
            <table>
                <tr><th>Card</th><th>Title</th><th>State</th><th>Issue</th><th>Last Update</th></tr>
                ${inboxCards.map(c => `
                    <tr>
                        <td>${c.card_id}</td>
                        <td>${c.title || '-'}</td>
                        <td>${getStateBadge(c.state, c.color)}</td>
                        <td>${c.has_drift_alert ? '<span class="badge badge-red">DRIFT</span>' : c.state}</td>
                        <td>${c.last_update ? new Date(c.last_update).toLocaleString() : '-'}</td>
                    </tr>
                `).join('')}
            </table>
        ` : '<div class="empty">No items need attention</div>';

        // Merge Ready: GREEN with proofpack
        const mergeCards = (data.cards || []).filter(c => c.color === 'GREEN' && c.latest_proofpack_path);

        document.getElementById('tab-merge').innerHTML = mergeCards.length ? `
            <table>
                <tr><th>Card</th><th>Proofpack</th><th>Action</th></tr>
                ${mergeCards.map(c => `
                    <tr>
                        <td>${c.card_id}</td>
                        <td><a href="../${c.latest_proofpack_path}">${c.latest_proofpack_path}</a></td>
                        <td><button class="btn btn-copy" onclick="navigator.clipboard.writeText('bash tower/scripts/merge_gold.sh --card ${c.card_id} --do-merge').then(() => alert('Copied!'))">Copy Merge Command</button></td>
                    </tr>
                `).join('')}
            </table>
        ` : '<div class="empty">No cards ready for merge</div>';

        // All Cards with search and filter
        let allCards = data.cards || [];
        const cardsTab = document.getElementById('tab-cards');

        function renderCards(cards) {
            return cards.length ? `
                <table>
                    <tr><th>Card</th><th>Title</th><th>Stream</th><th>State</th><th>Artifacts</th><th>Last Update</th></tr>
                    ${cards.map(c => `
                        <tr>
                            <td>${c.card_id}</td>
                            <td>${c.title || '-'}</td>
                            <td>${c.stream || '-'}</td>
                            <td>${getStateBadge(c.state, c.color)}</td>
                            <td>${c.latest_artifacts_path ? `<a href="../${c.latest_artifacts_path}">View</a>` : '-'}</td>
                            <td>${c.last_update ? new Date(c.last_update).toLocaleString() : '-'}</td>
                        </tr>
                    `).join('')}
                </table>
            ` : '<div class="empty">No cards</div>';
        }

        cardsTab.innerHTML = `
            <div class="controls">
                <input type="text" class="search-input" id="card-search" placeholder="Search cards...">
                <select id="state-filter">
                    <option value="">All States</option>
                    ${[...new Set((data.cards || []).map(c => c.state))].map(s => `<option value="${s}">${s}</option>`).join('')}
                </select>
                <select id="stream-filter">
                    <option value="">All Streams</option>
                    ${[...new Set((data.cards || []).map(c => c.stream).filter(Boolean))].map(s => `<option value="${s}">${s}</option>`).join('')}
                </select>
            </div>
            <div id="cards-table">${renderCards(allCards)}</div>
        `;

        function filterCards() {
            const search = document.getElementById('card-search').value.toLowerCase();
            const state = document.getElementById('state-filter').value;
            const stream = document.getElementById('stream-filter').value;

            const filtered = allCards.filter(c => {
                if (search && !c.card_id.toLowerCase().includes(search) && !(c.title || '').toLowerCase().includes(search)) return false;
                if (state && c.state !== state) return false;
                if (stream && c.stream !== stream) return false;
                return true;
            });

            document.getElementById('cards-table').innerHTML = renderCards(filtered);
        }

        document.getElementById('card-search').addEventListener('input', filterCards);
        document.getElementById('state-filter').addEventListener('change', filterCards);
        document.getElementById('stream-filter').addEventListener('change', filterCards);

        // Quotas & PCs
        document.getElementById('tab-quotas').innerHTML = `
            <h3 style="margin-bottom:15px">Quota Utilization</h3>
            <table>
                <tr><th>Model</th><th>Daily Usage</th><th>Weekly Usage</th></tr>
                ${(data.quota_summary || []).map(q => `
                    <tr>
                        <td>${q.model}</td>
                        <td>${getProgressBar(q.daily_percent)} (${q.daily_used}/${q.daily_limit})</td>
                        <td>${getProgressBar(q.weekly_percent)} (${q.weekly_used}/${q.weekly_limit})</td>
                    </tr>
                `).join('')}
            </table>

            <h3 style="margin:25px 0 15px">PC Fleet</h3>
            <table>
                <tr><th>PC</th><th>Status</th><th>Last Seen</th><th>CPU</th><th>RAM</th></tr>
                ${(data.pc_summary || []).map(p => `
                    <tr>
                        <td>${p.pc_id}</td>
                        <td><span class="status-${p.online ? 'online' : 'offline'}">${p.online ? 'ONLINE' : 'OFFLINE'}</span></td>
                        <td>${p.last_seen ? new Date(p.last_seen).toLocaleString() : '-'}</td>
                        <td>${p.cpu_utilization != null ? p.cpu_utilization + '%' : '-'}</td>
                        <td>${p.ram_utilization != null ? p.ram_utilization + '%' : '-'}</td>
                    </tr>
                `).join('')}
            </table>
        `;

        // Alerts
        document.getElementById('tab-alerts').innerHTML = (data.alerts?.items || []).length ? `
            ${(data.alerts.items).map(a => `
                <div class="alert-item ${a.type}">
                    <div class="alert-type">${a.type}${a.card_id ? ' - ' + a.card_id : ''}</div>
                    <div class="alert-message">${a.message}</div>
                </div>
            `).join('')}
        ` : '<div class="empty">No active alerts</div>';

        // Papers
        const paperCounts = data.papers?.counts_by_status || {};
        document.getElementById('tab-papers').innerHTML = `
            <div class="tiles" style="margin-bottom:20px">
                ${Object.entries(paperCounts).map(([status, count]) => `
                    <div class="tile"><div class="tile-title">${status}</div><div class="tile-value">${count}</div></div>
                `).join('')}
            </div>
            <p>Total papers: ${data.papers?.total || 0}</p>
        `;

        // Tab switching
        document.querySelectorAll('.tab').forEach(tab => {
            tab.addEventListener('click', function() {
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                this.classList.add('active');
                document.getElementById('tab-' + this.dataset.tab).classList.add('active');
            });
        });
    })();
    </script>
</body>
</html>
'''

# Write HTML atomically
html_file = tower_root / "control" / "dashboard.html"
tmp_file = str(html_file) + ".tmp"
with open(tmp_file, 'w', encoding='utf-8') as f:
    f.write(html_content)
os.replace(tmp_file, str(html_file))
print(f"Generated: {html_file}")
PYTHON_SCRIPT

echo ""
echo "============================================================"
echo "Dashboard generated successfully"
echo "Open: file://$HTML_OUTPUT"
echo "============================================================"
