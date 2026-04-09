#!/usr/bin/env python3
"""
Tower GUI - Local-only web interface for Tower control.
Part of Tower v1.5.5 GUI Add-on

Usage:
    python tower_gui.py [--port PORT] [--host HOST] [--readonly]

The server binds to localhost (127.0.0.1) by default for security.
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from flask import Flask, jsonify, render_template, request, send_from_directory
except ImportError:
    print("Error: Flask is required. Install with: pip install flask")
    sys.exit(1)


# Find Tower root
def find_tower_root() -> Path:
    """Find the Tower root directory."""
    # Check environment variable
    if "TOWER_ROOT" in os.environ:
        return Path(os.environ["TOWER_ROOT"])

    # Search upward from current directory
    current = Path.cwd()
    while current != current.parent:
        # Check if current dir is tower root (has control/status.json)
        if (current / "control" / "status.json").is_file():
            return current
        # Check if parent has tower subdir with control
        if (current / "tower" / "control" / "status.json").is_file():
            return current / "tower"
        current = current.parent

    # Fallback to relative path
    return Path("tower")


TOWER_ROOT = find_tower_root()
CONTROL_DIR = TOWER_ROOT / "control"
SCRIPTS_DIR = TOWER_ROOT / "scripts"
ADDONS_DIR = TOWER_ROOT / "addons"

# Flask app
app = Flask(
    __name__,
    template_folder=str(Path(__file__).parent / "templates"),
    static_folder=str(Path(__file__).parent / "static"),
)

# Configuration
READONLY_MODE = os.environ.get("TOWER_GUI_READONLY", "").lower() in ("true", "1", "yes")


def read_json_file(path: Path) -> Optional[Dict[str, Any]]:
    """Safely read a JSON file."""
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
    except (json.JSONDecodeError, IOError):
        pass
    return None


def read_jsonl_file(path: Path, limit: int = 50) -> List[Dict[str, Any]]:
    """Read last N lines from a JSONL file."""
    events = []
    try:
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        try:
                            events.append(json.loads(line))
                            if len(events) > limit:
                                events.pop(0)
                        except json.JSONDecodeError:
                            pass
    except IOError:
        pass
    return events


def run_script(script_path: str, args: List[str] = None) -> Dict[str, Any]:
    """Run a Tower script and return result."""
    if READONLY_MODE:
        return {"success": False, "error": "Server is in read-only mode"}

    script = SCRIPTS_DIR / script_path
    if not script.exists():
        return {"success": False, "error": f"Script not found: {script_path}"}

    try:
        cmd = ["bash", str(script)] + (args or [])
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=300,
            cwd=str(TOWER_ROOT.parent),
        )
        return {
            "success": result.returncode == 0,
            "stdout": result.stdout,
            "stderr": result.stderr,
            "returncode": result.returncode,
        }
    except subprocess.TimeoutExpired:
        return {"success": False, "error": "Script timed out"}
    except Exception as e:
        return {"success": False, "error": str(e)}


# ============================================================================
# HTML Routes
# ============================================================================


@app.route("/")
def index():
    """Main dashboard page."""
    status = read_json_file(CONTROL_DIR / "status.json") or {}
    slo = read_json_file(CONTROL_DIR / "slo_status.json") or {}
    quota = read_json_file(CONTROL_DIR / "quota.json") or {}
    freeze = read_json_file(CONTROL_DIR / "merge_freeze.json") or {}

    # Organize cards by state for Kanban
    cards = status.get("cards", [])
    kanban = {
        "backlog": [],
        "active": [],
        "validating": [],
        "green": [],
        "merged": [],
        "blocked": [],
    }

    state_mapping = {
        "BACKLOG": "backlog",
        "ACTIVE": "active",
        "IN_REVIEW": "active",
        "VALIDATING": "validating",
        "GREEN": "green",
        "MERGED": "merged",
        "ESCALATED": "blocked",
        "BLOCKED": "blocked",
        "ROLLED_BACK": "blocked",
    }

    for card in cards:
        state = card.get("state", "BACKLOG")
        column = state_mapping.get(state, "backlog")
        kanban[column].append(card)

    return render_template(
        "index.html",
        status=status,
        kanban=kanban,
        slo=slo,
        quota=quota,
        freeze=freeze,
        readonly=READONLY_MODE,
        timestamp=datetime.now().isoformat(),
    )


@app.route("/card/<card_id>")
def card_detail(card_id: str):
    """Card detail page."""
    status = read_json_file(CONTROL_DIR / "status.json") or {}
    cards = status.get("cards", [])

    card = None
    for c in cards:
        if c.get("card_id") == card_id:
            card = c
            break

    if not card:
        return "Card not found", 404

    # Get card events from ledger
    ledger_path = CONTROL_DIR / "event_ledger.jsonl"
    events = [e for e in read_jsonl_file(ledger_path, 200) if e.get("card_id") == card_id]

    return render_template(
        "card_detail.html",
        card=card,
        events=events[-50:],
        readonly=READONLY_MODE,
    )


# ============================================================================
# API Routes - Read
# ============================================================================


@app.route("/api/status")
def api_status():
    """Get Tower status."""
    status = read_json_file(CONTROL_DIR / "status.json")
    if status:
        return jsonify(status)
    return jsonify({"error": "status.json not found"}), 404


@app.route("/api/cards")
def api_cards():
    """Get all cards."""
    status = read_json_file(CONTROL_DIR / "status.json") or {}
    return jsonify(status.get("cards", []))


@app.route("/api/card/<card_id>")
def api_card(card_id: str):
    """Get single card."""
    status = read_json_file(CONTROL_DIR / "status.json") or {}
    for card in status.get("cards", []):
        if card.get("card_id") == card_id:
            return jsonify(card)
    return jsonify({"error": "Card not found"}), 404


@app.route("/api/slo")
def api_slo():
    """Get SLO status."""
    slo = read_json_file(CONTROL_DIR / "slo_status.json")
    if slo:
        return jsonify(slo)
    return jsonify({"status": "N/A", "message": "No SLO data available"})


@app.route("/api/quota")
def api_quota():
    """Get quota status."""
    quota = read_json_file(CONTROL_DIR / "quota.json")
    if quota:
        return jsonify(quota)
    return jsonify({"status": "N/A", "message": "No quota data available"})


@app.route("/api/events")
def api_events():
    """Get recent events from ledger."""
    limit = request.args.get("limit", 50, type=int)
    ledger_path = CONTROL_DIR / "event_ledger.jsonl"
    events = read_jsonl_file(ledger_path, limit)
    return jsonify(events)


@app.route("/api/freeze")
def api_freeze():
    """Get merge freeze status."""
    freeze = read_json_file(CONTROL_DIR / "merge_freeze.json")
    if freeze:
        return jsonify(freeze)
    return jsonify({"active": False})


@app.route("/api/dashboard-plus")
def api_dashboard_plus():
    """Get dashboard plus status."""
    status = read_json_file(CONTROL_DIR / "dashboard_plus_status.json")
    if status:
        return jsonify(status)
    return jsonify({"status": "UNKNOWN"})


# ============================================================================
# API Routes - Actions
# ============================================================================


@app.route("/api/actions/validate", methods=["POST"])
def action_validate():
    """Run validation."""
    result = run_script("tower_validate_all.sh")
    return jsonify(result)


def _validate_card_id(card_id: str) -> bool:
    """Validate card_id format (CARD-NNN or similar safe pattern)."""
    import re
    # Allow CARD-XXX format or alphanumeric with hyphens/underscores
    return bool(re.match(r'^[A-Za-z0-9_-]{1,50}$', card_id))


@app.route("/api/actions/gatecheck/<card_id>", methods=["POST"])
def action_gatecheck(card_id: str):
    """Run gatecheck for a card."""
    if not _validate_card_id(card_id):
        return jsonify({"success": False, "error": "Invalid card_id format"}), 400
    result = run_script("tower_gatecheck.sh", [card_id])
    return jsonify(result)


@app.route("/api/actions/dashboard", methods=["POST"])
def action_dashboard():
    """Regenerate dashboard."""
    result = run_script("tower_dashboard.sh")
    return jsonify(result)


@app.route("/api/actions/freeze", methods=["POST"])
def action_freeze():
    """Activate merge freeze."""
    if READONLY_MODE:
        return jsonify({"success": False, "error": "Server is in read-only mode"})

    reason = request.json.get("reason", "Manual freeze via GUI") if request.json else "Manual freeze via GUI"

    try:
        freeze_data = {"active": True, "reason": reason, "activated_at": datetime.now().isoformat()}
        freeze_path = CONTROL_DIR / "merge_freeze.json"
        with open(freeze_path, "w", encoding="utf-8") as f:
            json.dump(freeze_data, f, indent=2)
        return jsonify({"success": True, "freeze": freeze_data})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


@app.route("/api/actions/unfreeze", methods=["POST"])
def action_unfreeze():
    """Clear merge freeze."""
    if READONLY_MODE:
        return jsonify({"success": False, "error": "Server is in read-only mode"})

    try:
        freeze_path = CONTROL_DIR / "merge_freeze.json"
        if freeze_path.exists():
            freeze_path.unlink()
        return jsonify({"success": True})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)})


# ============================================================================
# Static Files
# ============================================================================


@app.route("/static/<path:filename>")
def static_files(filename):
    """Serve static files."""
    return send_from_directory(app.static_folder, filename)


# ============================================================================
# Main
# ============================================================================


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Tower GUI Server")
    parser.add_argument("--port", type=int, default=int(os.environ.get("TOWER_GUI_PORT", 5000)), help="Server port")
    parser.add_argument(
        "--host", default=os.environ.get("TOWER_GUI_HOST", "127.0.0.1"), help="Bind address (default: localhost only)"
    )
    parser.add_argument("--readonly", action="store_true", help="Run in read-only mode")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")

    args = parser.parse_args()

    global READONLY_MODE
    READONLY_MODE = args.readonly or READONLY_MODE

    print(f"Tower GUI Server")
    print(f"  Tower root: {TOWER_ROOT}")
    print(f"  Control dir: {CONTROL_DIR}")
    print(f"  Read-only: {READONLY_MODE}")
    print(f"  URL: http://{args.host}:{args.port}")
    print()

    if args.host != "127.0.0.1":
        print("WARNING: Binding to non-localhost address. This is not recommended.")
        print("         Tower GUI is designed for local use only.")
        print()

    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
