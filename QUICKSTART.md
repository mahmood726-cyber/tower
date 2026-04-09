# QUICKSTART.md

## TruthCert/Burhan Evidence System - Quick Start Guide

**Goal:** Run your first evidence map in 20 minutes.

---

## Prerequisites

- Python 3.9+
- Git
- Bash (Git Bash on Windows)

---

## Step 1: Setup (5 minutes)

```bash
# Clone and enter directory
git clone https://github.com/example/tower.git
cd tower

# Install dependencies
pip install -r requirements.txt

# Verify installation
./tower-cli --version
```

---

## Step 2: Configure Your Machine (2 minutes)

```bash
# Set up as a development machine
./scripts/box_setup.sh --role box_c --hostname my-laptop

# Check status
./scripts/box_status.sh
```

---

## Step 3: Create Your First Capsule (5 minutes)

```bash
# Create a capsule for a topic
./scripts/capsule_create.sh --domain cardiology --topic sglt2i

# View the created capsule
ls -la capsules/$(date +%Y-%m-%d)/cardiology-sglt2i/
```

You should see:
- `MANIFEST.json` - Capsule metadata with ID
- `EXPLAIN.json` - Current status and next actions
- `NUMBER_CARD.json` - Template for published numbers
- `PROVENANCE.md` - Full provenance chain
- `CHANGELOG.md` - Version history
- `CITATION.cff` - How to cite this capsule

---

## Step 4: Run the Map Lane (5 minutes)

```bash
# Run the map lane for your topic
./scripts/lane_run.sh --lane map --topic sglt2i

# Check the output
cat runs/$(date +%Y-%m-%d)/map/EXPLAIN.json
```

---

## Step 5: Verify Your Work (3 minutes)

```bash
# Run gate checks
./scripts/tower_gatecheck.sh

# View status
./tower-cli status
```

---

## Understanding the Output

### Badge Levels (Assurance Ladder)

| Badge | Meaning |
|-------|---------|
| 🥉 Bronze | Map-grade: navigable graph, schema valid |
| 🥈 Silver | Meta-grade: validators pass, quorum satisfied |
| 🥇 Gold | Decision-grade: stable, reproducible, signed |

### Severity Levels

| Level | Meaning |
|-------|---------|
| P0 | Blocker - must fix before proceeding |
| P1 | Warning - caps badge level |
| P2 | Info - for awareness only |

---

## Next Steps

1. **Add Data:** Put trial data in `GRAPH/`
2. **Add Witnesses:** Link to registry snapshots and publications
3. **Run Meta:** `./scripts/lane_run.sh --lane meta --topic sglt2i`
4. **Publish:** Generate signed volume with `./scripts/volume_publish.sh`

---

## Getting Help

```bash
# View all commands
./tower-cli --help

# View lane options
./scripts/lane_run.sh --help

# Check system health
./scripts/pc_health_check.sh
```

---

## The Seven Rules (Always Remember)

1. **Witness-first:** Every number needs a witness chain
2. **Guardianship:** Validators check, never generate
3. **Right names:** Ontology is law
4. **Mercy-by-impact:** Maps publish early; meta/transport/hta need gates
5. **Consultation:** Log disagreements explicitly
6. **Change-aware:** Version everything; track drift
7. **Abstention:** "Insufficient certainty" is valid

---

*Welcome to TruthCert! Build evidence that shows its proof.*
