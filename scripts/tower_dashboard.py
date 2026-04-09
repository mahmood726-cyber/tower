#!/usr/bin/env python3
"""
Tower Cockpit Dashboard Generator (Python version)
Generates both dashboard.json and dashboard.html
HTML is file:// safe with embedded JSON (no fetch required)
"""

import json
import os
from pathlib import Path
from datetime import datetime

TOWER_ROOT = Path(__file__).parent.parent
CONTROL_DIR = TOWER_ROOT / "control"
PAPERS_DIR = TOWER_ROOT / "papers"

def load_json_safe(path: Path) -> dict:
    """Load JSON file, return empty dict if missing or invalid."""
    try:
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
    except:
        pass
    return {}

def get_inbox_items(backlog: dict, status: dict, drift_config: dict) -> list:
    """Get inbox items sorted by pain (ESCALATED > drift > REVIEW_PENDING > BLOCKED)."""
    items = []

    # Collect cards from all streams
    for stream_name, stream_data in backlog.get("streams", {}).items():
        for card_id in stream_data.get("active_cards", []):
            card_status = status.get("active_cards", {}).get(card_id, {})
            state = card_status.get("state", "UNKNOWN")
            last_heartbeat = card_status.get("last_heartbeat_iso", "")

            # Calculate pain score
            pain = 0
            reason = state
            if state == "ESCALATED":
                pain = 100
                reason = "ESCALATED - needs attention"
            elif state == "BLOCKED":
                pain = 30
                reason = "BLOCKED - waiting"
            elif state == "REVIEW_PENDING":
                pain = 40
                reason = "REVIEW_PENDING"
            elif state == "ACTIVE":
                pain = 10
                # Check for drift
                if last_heartbeat:
                    try:
                        hb_time = datetime.fromisoformat(last_heartbeat.replace('Z', '+00:00'))
                        now = datetime.now().astimezone()
                        age_min = (now - hb_time).total_seconds() / 60
                        threshold = drift_config.get("thresholds", {}).get("interactive_minutes", 20)
                        if age_min > threshold:
                            pain = 60
                            reason = f"DRIFT ({int(age_min)}m stale)"
                    except:
                        pass

            items.append({
                "card_id": card_id,
                "stream": stream_name,
                "state": state,
                "pain": pain,
                "reason": reason,
                "last_heartbeat": last_heartbeat,
                "agent": card_status.get("agent", "unknown"),
            })

    # Sort by pain descending
    items.sort(key=lambda x: x["pain"], reverse=True)
    return items

def get_merge_ready_cards(backlog: dict) -> list:
    """Get cards that are ready to merge (GOLD status)."""
    items = []
    for stream_name, stream_data in backlog.get("streams", {}).items():
        for card_id in stream_data.get("gold_cards", []):
            items.append({
                "card_id": card_id,
                "stream": stream_name,
                "merge_cmd": f"bash tower/scripts/merge_gold.sh {card_id}",
            })
    return items

def get_all_cards(backlog: dict, status: dict) -> list:
    """Get all cards from all states."""
    items = []
    for stream_name, stream_data in backlog.get("streams", {}).items():
        for state_key in ["ready_cards", "active_cards", "review_cards", "gold_cards"]:
            state_name = state_key.replace("_cards", "").upper()
            for card_id in stream_data.get(state_key, []):
                card_status = status.get("active_cards", {}).get(card_id, {})
                items.append({
                    "card_id": card_id,
                    "stream": stream_name,
                    "state": card_status.get("state", state_name),
                    "agent": card_status.get("agent", "-"),
                    "machine": card_status.get("machine", "-"),
                })
    return items

def get_quota_summary(quota: dict, machines: dict) -> dict:
    """Get quota and PC summary."""
    return {
        "quotas": quota.get("quotas", {}),
        "machines": machines.get("machines", {}),
    }

def get_alerts(control_dir: Path) -> list:
    """Get recent alerts from alerts directory."""
    alerts = []
    alerts_dir = control_dir / "alerts"
    if alerts_dir.exists():
        for f in sorted(alerts_dir.glob("*.json"), reverse=True)[:20]:
            try:
                with open(f, 'r', encoding='utf-8') as fp:
                    alert = json.load(fp)
                    alert["_file"] = f.name
                    alerts.append(alert)
            except:
                pass
    return alerts

def get_papers_summary(papers_dir: Path) -> list:
    """Get papers registry summary."""
    registry_path = papers_dir / "paper_registry.json"
    if registry_path.exists():
        try:
            with open(registry_path, 'r', encoding='utf-8') as f:
                registry = json.load(f)
                return registry.get("papers", [])
        except:
            pass
    return []

def generate_html(dashboard_data: dict) -> str:
    """Generate the HTML dashboard with embedded JSON."""
    json_data = json.dumps(dashboard_data, indent=2)

    html = f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Tower Cockpit v1.5.5</title>
    <style>
        :root {{
            --bg-dark: #1a1a2e;
            --bg-card: #16213e;
            --accent: #0f3460;
            --highlight: #e94560;
            --text: #eaeaea;
            --text-dim: #888;
            --green: #4ade80;
            --yellow: #fbbf24;
            --red: #f87171;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: 'Segoe UI', system-ui, sans-serif;
            background: var(--bg-dark);
            color: var(--text);
            min-height: 100vh;
        }}
        .header {{
            background: var(--accent);
            padding: 1rem 2rem;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid var(--highlight);
        }}
        .header h1 {{ font-size: 1.5rem; }}
        .header .meta {{ font-size: 0.85rem; color: var(--text-dim); }}
        .tabs {{
            display: flex;
            background: var(--bg-card);
            border-bottom: 1px solid var(--accent);
        }}
        .tab {{
            padding: 0.75rem 1.5rem;
            cursor: pointer;
            border-bottom: 3px solid transparent;
            transition: all 0.2s;
        }}
        .tab:hover {{ background: var(--accent); }}
        .tab.active {{
            border-bottom-color: var(--highlight);
            background: var(--accent);
        }}
        .tab-content {{ display: none; padding: 1.5rem; }}
        .tab-content.active {{ display: block; }}
        .card {{
            background: var(--bg-card);
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 1rem;
            border-left: 4px solid var(--accent);
        }}
        .card.escalated {{ border-left-color: var(--red); }}
        .card.drift {{ border-left-color: var(--yellow); }}
        .card.gold {{ border-left-color: var(--green); }}
        .card-header {{
            display: flex;
            justify-content: space-between;
            margin-bottom: 0.5rem;
        }}
        .card-id {{ font-weight: bold; font-family: monospace; }}
        .badge {{
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
            font-size: 0.75rem;
            font-weight: bold;
        }}
        .badge.red {{ background: var(--red); color: #000; }}
        .badge.yellow {{ background: var(--yellow); color: #000; }}
        .badge.green {{ background: var(--green); color: #000; }}
        table {{
            width: 100%;
            border-collapse: collapse;
            background: var(--bg-card);
            border-radius: 8px;
            overflow: hidden;
        }}
        th, td {{
            padding: 0.75rem;
            text-align: left;
            border-bottom: 1px solid var(--accent);
        }}
        th {{ background: var(--accent); }}
        tr:hover {{ background: rgba(255,255,255,0.05); }}
        .btn {{
            background: var(--highlight);
            color: white;
            border: none;
            padding: 0.5rem 1rem;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.85rem;
        }}
        .btn:hover {{ opacity: 0.9; }}
        .search {{
            width: 100%;
            padding: 0.75rem;
            margin-bottom: 1rem;
            background: var(--accent);
            border: 1px solid var(--text-dim);
            border-radius: 4px;
            color: var(--text);
        }}
        .quota-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 1rem;
        }}
        .quota-card {{
            background: var(--bg-card);
            padding: 1rem;
            border-radius: 8px;
        }}
        .quota-bar {{
            height: 8px;
            background: var(--accent);
            border-radius: 4px;
            overflow: hidden;
            margin-top: 0.5rem;
        }}
        .quota-fill {{
            height: 100%;
            background: var(--green);
            transition: width 0.3s;
        }}
        .quota-fill.warning {{ background: var(--yellow); }}
        .quota-fill.danger {{ background: var(--red); }}
        .empty-state {{
            text-align: center;
            padding: 3rem;
            color: var(--text-dim);
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>Tower Cockpit v1.5.5</h1>
        <div class="meta">
            <span id="gen-time"></span> |
            <span id="status-summary"></span>
        </div>
    </div>

    <div class="tabs">
        <div class="tab active" data-tab="inbox">Inbox</div>
        <div class="tab" data-tab="merge">Merge Ready</div>
        <div class="tab" data-tab="cards">Cards</div>
        <div class="tab" data-tab="quotas">Quotas &amp; PCs</div>
        <div class="tab" data-tab="alerts">Alerts</div>
        <div class="tab" data-tab="papers">Papers</div>
    </div>

    <div id="inbox" class="tab-content active"></div>
    <div id="merge" class="tab-content"></div>
    <div id="cards" class="tab-content"></div>
    <div id="quotas" class="tab-content"></div>
    <div id="alerts" class="tab-content"></div>
    <div id="papers" class="tab-content"></div>

    <script id="dashboard-data" type="application/json">
{json_data}
    </script>

    <script>
        const data = JSON.parse(document.getElementById('dashboard-data').textContent);

        // Update header
        document.getElementById('gen-time').textContent = data.generated_at || 'Unknown';
        document.getElementById('status-summary').textContent =
            `${{data.inbox?.length || 0}} active | ${{data.merge_ready?.length || 0}} merge-ready`;

        // Tab switching
        document.querySelectorAll('.tab').forEach(tab => {{
            tab.addEventListener('click', () => {{
                document.querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
                document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
                tab.classList.add('active');
                document.getElementById(tab.dataset.tab).classList.add('active');
            }});
        }});

        // Render Inbox
        const inboxEl = document.getElementById('inbox');
        if (data.inbox?.length) {{
            inboxEl.innerHTML = data.inbox.map(item => `
                <div class="card ${{item.pain >= 60 ? 'drift' : item.pain >= 100 ? 'escalated' : ''}}">
                    <div class="card-header">
                        <span class="card-id">${{item.card_id}}</span>
                        <span class="badge ${{item.pain >= 60 ? 'yellow' : item.pain >= 100 ? 'red' : 'green'}}">${{item.reason}}</span>
                    </div>
                    <div style="color: var(--text-dim); font-size: 0.85rem;">
                        Stream: ${{item.stream}} | Agent: ${{item.agent || 'unknown'}} | Last HB: ${{item.last_heartbeat || 'N/A'}}
                    </div>
                </div>
            `).join('');
        }} else {{
            inboxEl.innerHTML = '<div class="empty-state">No active cards in inbox</div>';
        }}

        // Render Merge Ready
        const mergeEl = document.getElementById('merge');
        if (data.merge_ready?.length) {{
            mergeEl.innerHTML = data.merge_ready.map(item => `
                <div class="card gold">
                    <div class="card-header">
                        <span class="card-id">${{item.card_id}}</span>
                        <span class="badge green">GOLD</span>
                    </div>
                    <div style="display: flex; gap: 1rem; margin-top: 0.5rem;">
                        <code style="flex: 1; background: var(--accent); padding: 0.5rem; border-radius: 4px; font-size: 0.85rem;">${{item.merge_cmd}}</code>
                        <button class="btn" onclick="navigator.clipboard.writeText('${{item.merge_cmd}}').then(() => this.textContent = 'Copied!').catch(() => {{}})">Copy</button>
                    </div>
                </div>
            `).join('');
        }} else {{
            mergeEl.innerHTML = '<div class="empty-state">No cards ready to merge</div>';
        }}

        // Render Cards table
        const cardsEl = document.getElementById('cards');
        cardsEl.innerHTML = `
            <input type="text" class="search" placeholder="Search cards..." id="card-search">
            <table>
                <thead><tr><th>Card ID</th><th>Stream</th><th>State</th><th>Agent</th><th>Machine</th></tr></thead>
                <tbody id="cards-body"></tbody>
            </table>
        `;
        const cardsBody = document.getElementById('cards-body');
        const renderCards = (filter = '') => {{
            const filtered = (data.all_cards || []).filter(c =>
                c.card_id.toLowerCase().includes(filter.toLowerCase()) ||
                c.stream.toLowerCase().includes(filter.toLowerCase())
            );
            cardsBody.innerHTML = filtered.map(c => `
                <tr><td>${{c.card_id}}</td><td>${{c.stream}}</td><td>${{c.state}}</td><td>${{c.agent}}</td><td>${{c.machine}}</td></tr>
            `).join('') || '<tr><td colspan="5" style="text-align:center">No cards found</td></tr>';
        }};
        renderCards();
        document.getElementById('card-search').addEventListener('input', e => renderCards(e.target.value));

        // Render Quotas & PCs
        const quotasEl = document.getElementById('quotas');
        const quotaData = data.quota_summary || {{}};
        let quotaHtml = '<h3 style="margin-bottom:1rem">Model Quotas</h3><div class="quota-grid">';
        for (const [model, info] of Object.entries(quotaData.quotas || {{}})) {{
            const pct = info.limit_usd > 0 ? (info.used_usd / info.limit_usd * 100) : 0;
            const barClass = pct > 90 ? 'danger' : pct > 70 ? 'warning' : '';
            quotaHtml += `
                <div class="quota-card">
                    <div style="display:flex;justify-content:space-between"><strong>${{model}}</strong><span>${{pct.toFixed(1)}}%</span></div>
                    <div class="quota-bar"><div class="quota-fill ${{barClass}}" style="width:${{Math.min(pct,100)}}%"></div></div>
                    <div style="font-size:0.85rem;color:var(--text-dim);margin-top:0.5rem">$${{info.used_usd?.toFixed(2) || 0}} / $${{info.limit_usd?.toFixed(2) || 0}}</div>
                </div>
            `;
        }}
        quotaHtml += '</div><h3 style="margin:1.5rem 0 1rem">Machines</h3><div class="quota-grid">';
        for (const [name, info] of Object.entries(quotaData.machines || {{}})) {{
            const statusColor = info.status === 'online' ? 'green' : info.status === 'busy' ? 'yellow' : 'red';
            quotaHtml += `
                <div class="quota-card">
                    <div style="display:flex;justify-content:space-between"><strong>${{name}}</strong><span class="badge ${{statusColor}}">${{info.status}}</span></div>
                    <div style="font-size:0.85rem;color:var(--text-dim);margin-top:0.5rem">
                        ${{info.current_card || 'idle'}} | Last seen: ${{info.last_seen_iso || 'never'}}
                    </div>
                </div>
            `;
        }}
        quotaHtml += '</div>';
        quotasEl.innerHTML = quotaHtml;

        // Render Alerts
        const alertsEl = document.getElementById('alerts');
        if (data.alerts?.length) {{
            alertsEl.innerHTML = data.alerts.map(a => `
                <div class="card ${{a.level === 'error' ? 'escalated' : a.level === 'warning' ? 'drift' : ''}}">
                    <div class="card-header">
                        <span class="badge ${{a.level === 'error' ? 'red' : a.level === 'warning' ? 'yellow' : 'green'}}">${{a.level?.toUpperCase() || 'INFO'}}</span>
                        <span style="color:var(--text-dim);font-size:0.85rem">${{a.timestamp || a._file}}</span>
                    </div>
                    <div style="margin-top:0.5rem">${{a.message || JSON.stringify(a)}}</div>
                </div>
            `).join('');
        }} else {{
            alertsEl.innerHTML = '<div class="empty-state">No alerts</div>';
        }}

        // Render Papers
        const papersEl = document.getElementById('papers');
        if (data.papers?.length) {{
            papersEl.innerHTML = `
                <table>
                    <thead><tr><th>Paper ID</th><th>Title</th><th>Status</th><th>Venue</th></tr></thead>
                    <tbody>${{data.papers.map(p => `
                        <tr><td>${{p.paper_id}}</td><td>${{p.title}}</td><td>${{p.status}}</td><td>${{p.venue || '-'}}</td></tr>
                    `).join('')}}</tbody>
                </table>
            `;
        }} else {{
            papersEl.innerHTML = '<div class="empty-state">No papers registered</div>';
        }}
    </script>
</body>
</html>'''
    return html

def main():
    print("=" * 60)
    print("Tower Cockpit Dashboard Generator")
    print(f"Output JSON: {CONTROL_DIR / 'dashboard.json'}")
    print(f"Output HTML: {CONTROL_DIR / 'dashboard.html'}")
    print("=" * 60)

    # Load control files
    backlog = load_json_safe(CONTROL_DIR / "backlog.json")
    status = load_json_safe(CONTROL_DIR / "status.json")
    quota = load_json_safe(CONTROL_DIR / "quota.json")
    machines = load_json_safe(CONTROL_DIR / "machines.json")
    drift_config = load_json_safe(CONTROL_DIR / "drift_config.json")

    # Build dashboard data
    dashboard_data = {
        "generated_at": datetime.now().isoformat(),
        "tower_version": "1.5.5",
        "inbox": get_inbox_items(backlog, status, drift_config),
        "merge_ready": get_merge_ready_cards(backlog),
        "all_cards": get_all_cards(backlog, status),
        "quota_summary": get_quota_summary(quota, machines),
        "alerts": get_alerts(CONTROL_DIR),
        "papers": get_papers_summary(PAPERS_DIR),
    }

    # Write JSON
    json_path = CONTROL_DIR / "dashboard.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(dashboard_data, f, indent=2)
    print(f"\n[+] Generated: {json_path}")

    # Write HTML
    html_path = CONTROL_DIR / "dashboard.html"
    html_content = generate_html(dashboard_data)
    with open(html_path, 'w', encoding='utf-8') as f:
        f.write(html_content)
    print(f"[+] Generated: {html_path}")

    # Summary
    print("\n" + "-" * 60)
    print("Dashboard Summary:")
    print(f"  Inbox items:      {len(dashboard_data['inbox'])}")
    print(f"  Merge ready:      {len(dashboard_data['merge_ready'])}")
    print(f"  Total cards:      {len(dashboard_data['all_cards'])}")
    print(f"  Alerts:           {len(dashboard_data['alerts'])}")
    print(f"  Papers:           {len(dashboard_data['papers'])}")
    print("-" * 60)
    print("\nDashboard generated successfully!")
    print(f"Open in browser: file://{html_path.as_posix()}")

if __name__ == "__main__":
    main()
