# Tower Usability Improvement Plan
## Target: Scientists who struggle with installation, CLI, and coding

**Scope**: Minimal changes, maximum usability impact
**Timeline**: 2-3 focused sessions
**Principle**: If it needs documentation, it's too complex

---

## Phase 1: Zero-Friction Setup (Priority: CRITICAL)

### 1.1 One-Command Installer
**Problem**: Scientists don't want to clone repos, set paths, install deps
**Solution**: Single copy-paste command

```bash
# Create: tower/scripts/install.sh
curl -sSL https://raw.githubusercontent.com/.../install.sh | bash
```

Features:
- [ ] Detect OS (Windows/Mac/Linux)
- [ ] Check Python version (3.8+)
- [ ] Create `~/tower/` directory structure
- [ ] Add `tower` to PATH
- [ ] Print "Ready! Try: tower status"

**Effort**: 2-3 hours
**Impact**: Removes biggest adoption barrier

### 1.2 Friendly Error Messages
**Problem**: "ERROR: Neither python3 nor python found" is scary
**Solution**: Helpful, non-technical messages

```bash
# Before:
echo "ERROR: Neither python3 nor python found"

# After:
echo ""
echo "  Tower needs Python to run."
echo ""
echo "  To install Python:"
echo "    Mac:     brew install python3"
echo "    Windows: Download from python.org/downloads"
echo "    Linux:   sudo apt install python3"
echo ""
echo "  Then run this command again."
```

**Effort**: 1 hour (update all 4 scripts)
**Impact**: Reduces support requests by ~50%

---

## Phase 2: Simple CLI Wrapper (Priority: HIGH)

### 2.1 Single Entry Point
**Problem**: Scientists don't know which script to run
**Solution**: One command with subcommands

```bash
# Create: tower/tower (main entry point)

tower status              # Show all cards and their state
tower new "Fix Table 3"   # Create CARD-NNN with description
tower run "pytest"        # Run command under current card
tower check               # Run gatecheck on current card
tower pack                # Generate proofpack
tower merge               # Merge if GOLD + in window
tower help                # Show all commands
```

**Effort**: 3-4 hours
**Impact**: Scientists only learn ONE command

### 2.2 Interactive Mode
**Problem**: Scientists forget flags and syntax
**Solution**: Prompt when flags missing

```bash
$ tower run
No command specified. What would you like to run?
> pytest tests/

Running under card CARD-042...
```

```bash
$ tower new
What is this card for? (short description)
> Fix correlation matrix in Table 3

Created CARD-043: "Fix correlation matrix in Table 3"
Worktree: ~/tower/worktrees/CARD-043
```

**Effort**: 2-3 hours
**Impact**: No need to memorize syntax

---

## Phase 3: Status at a Glance (Priority: HIGH)

### 3.1 Colorful Status Display
**Problem**: status.json is unreadable for humans
**Solution**: Pretty terminal output

```bash
$ tower status

╭─────────────────────────────────────────────────────╮
│  TOWER STATUS                      Feb 6, 2026     │
├─────────────────────────────────────────────────────┤
│                                                     │
│  CARD-041  Fix meta-regression      🟢 GOLD        │
│            Tests ✓  Validators ✓  Proofpack ✓      │
│                                                     │
│  CARD-042  Update forest plot       🟡 REVIEW      │
│            Tests ✓  Validators ✗  Proofpack ·      │
│                                                     │
│  CARD-043  Add sensitivity analysis 🔴 DRAFT       │
│            Tests ·  Validators ·  Proofpack ·      │
│                                                     │
├─────────────────────────────────────────────────────┤
│  Next merge window: 19:00-19:20 (in 3h 42m)        │
╰─────────────────────────────────────────────────────╯
```

**Effort**: 3-4 hours
**Impact**: Scientists can see progress instantly

### 3.2 Card Context Awareness
**Problem**: Scientists forget which card they're working on
**Solution**: Auto-detect from worktree or prompt

```bash
$ cd ~/tower/worktrees/CARD-042
$ tower run "pytest"
# Automatically knows it's CARD-042

$ cd ~/some/other/folder
$ tower run "pytest"
Which card? [CARD-041, CARD-042, CARD-043]:
```

**Effort**: 1-2 hours
**Impact**: Fewer mistakes, less typing

---

## Phase 4: Gentle Onboarding (Priority: MEDIUM)

### 4.1 First-Run Tutorial
**Problem**: Scientists don't know where to start
**Solution**: Interactive first-run experience

```bash
$ tower

Welcome to Tower! Let's get you set up.

Tower helps you track research tasks with proof artifacts.
Each task is a "card" (like CARD-001, CARD-002...).

Let's create your first card:
What are you working on? (e.g., "Analyze patient data")
> Run meta-analysis on RCT data

Great! Created CARD-001: "Run meta-analysis on RCT data"

To run a command and track it:
  tower run "python analyze.py"

To check your progress:
  tower status

Need help anytime?
  tower help
```

**Effort**: 2 hours
**Impact**: Scientists productive in < 5 minutes

### 4.2 Contextual Help
**Problem**: --help is overwhelming
**Solution**: Short, example-based help

```bash
$ tower help run

  tower run "command"

  Examples:
    tower run "python analysis.py"
    tower run "Rscript model.R"
    tower run "pytest tests/"

  This tracks your command with:
    - Start/end time
    - Exit code (success/failure)
    - Output logs

  See also: tower status, tower check
```

**Effort**: 1-2 hours
**Impact**: Self-service answers

---

## Phase 5: Escape Hatches (Priority: MEDIUM)

### 5.1 Export to Familiar Formats
**Problem**: Scientists want results in formats they know
**Solution**: Export commands

```bash
tower export markdown    # Creates REPORT.md with all cards
tower export csv         # Creates cards.csv for Excel
tower export html        # Creates interactive report.html
```

**Effort**: 3-4 hours
**Impact**: Integrates with existing workflows

### 5.2 Undo / Recovery
**Problem**: Scientists panic when things go wrong
**Solution**: Safe undo and clear recovery messages

```bash
$ tower undo
Last action: Created CARD-043
Undo this? [y/N]: y
Removed CARD-043. Status restored.

$ tower recover
Found 2 backups from today:
  1. status_20260206_140532.json (2 hours ago)
  2. status_20260206_093021.json (7 hours ago)
Restore which? [1/2/cancel]:
```

**Effort**: 2-3 hours
**Impact**: Reduces fear of breaking things

---

## Implementation Order

| Phase | Effort | Impact | Do First? |
|-------|--------|--------|-----------|
| 1.1 One-command installer | 2-3h | 🔥🔥🔥 | YES |
| 1.2 Friendly errors | 1h | 🔥🔥 | YES |
| 2.1 Single entry point | 3-4h | 🔥🔥🔥 | YES |
| 3.1 Colorful status | 3-4h | 🔥🔥🔥 | YES |
| 2.2 Interactive mode | 2-3h | 🔥🔥 | After 2.1 |
| 3.2 Card context | 1-2h | 🔥🔥 | After 2.1 |
| 4.1 First-run tutorial | 2h | 🔥🔥 | After 2.1 |
| 4.2 Contextual help | 1-2h | 🔥 | After 2.1 |
| 5.1 Export formats | 3-4h | 🔥🔥 | Later |
| 5.2 Undo/recovery | 2-3h | 🔥 | Later |

---

## What NOT To Build

| Feature | Why Skip |
|---------|----------|
| Web dashboard | tower_js exists; complexity explosion |
| Config files | Scientists won't edit YAML |
| Plugin system | Premature; adds complexity |
| Cloud sync | Out of scope; security concerns |
| GUI installer | CLI is fine with good UX |
| Internationalization | English-first; translate later |

---

## Success Metrics

1. **Time to first card**: < 5 minutes from zero
2. **Commands to memorize**: Just `tower` + subcommands
3. **Error recovery**: Always recoverable, never data loss
4. **Documentation needed**: Minimal (help is built-in)

---

## First Session Deliverable

Build Phase 1 + 2.1 + 3.1:
- One-command install
- Friendly error messages
- `tower` CLI wrapper with status/new/run/check/pack/merge
- Colorful status display

**Total effort**: ~10-12 hours
**Result**: Scientists can install and use Tower without reading docs
