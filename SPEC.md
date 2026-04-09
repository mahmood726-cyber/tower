# TruthCert / Burhan — Evidence Graph Spec (v0.8 "Nets-Level, Witness-Governed")

**Status:** Draft for open-source release (PR-driven)
**Mission:** Build a living evidence system that never asks to be trusted—it **shows its chain of proof**.

---

## 0) Charter (inspiration → enforceable engineering)

This spec is inspired by:
- **Fatiha-style "straight path" governance:** compact, memorable rules that keep the system corrigible.
- **Hadith / scholarly method:** *isnad* (chain-of-transmission), witness grading, explicit disagreement handling.
- **Burhan mindset:** every published number ships with its proof bundle (capsule).
- **Promised Messiah / Musleh Maud inspirations (operational):** disciplined truthfulness, systematic documentation, service—implemented as provenance, conservative gates, and reproducibility.
- **Chinese systems thinking:** **rectification of names** (ontology-first), **yin–yang pairing** (generator vs validator), and rule-of-law governance (validators are law).

**Non-negotiable:** This is not theology. A claim is accepted only if supported by **provenance + deterministic validation + reproducible computation**.

---

## 1) The Seven Straight-Path Rules (Fatiha-inspired governance)

1. **Witness-first:** no published number without a witness chain (immutable snapshot + locator + hash).
2. **Guardianship:** validators never generate; they only recompute/check/veto.
3. **Right names:** ontology is law; free-text is quarantined until mapped.
4. **Mercy-by-impact:** maps publish early; meta/transport/HTA require stronger gates.
5. **Consultation:** disagreements become explicit objects; adjudications are logged and replayable.
6. **Change-aware:** everything is versioned; diffs + drift ledgers are mandatory.
7. **Abstention:** "insufficient certainty—do not publish" is first-class.

---

## 2) Assurance Ladder (TrustCert Badges)

Badges are algorithmic and versioned.

| Badge | Name | Requirements |
|-------|------|--------------|
| 🥉 | **Bronze (Map-grade)** | Navigable graph + provenance; P0 schema validators pass; warnings allowed |
| 🥈 | **Silver (Meta-grade)** | Publishable meta outputs; all P0 validators pass; quorum satisfied; conflicts resolved/abstained |
| 🥇 | **Gold (Decision-grade)** | Stable meta over ≥N releases; transport/HTA eligible; strong witness density; drift controlled; signed artifacts + full reproducibility |

---

## 3) Source Fusion (triangulate; don't merely append)

**Fusion rule:** no single source is "truth." Truth = **claims + witnesses + consensus**.

Typical sources:
- Trial universe: CT.gov/AACT + ICTRP + CTIS + others
- Publications: PubMed/Europe PMC + OpenAlex/Crossref/OpenCitations
- Syntheses: PROSPERO/OSF + evidence maps + SRDR/SRDR+
- Context: WHO / World Bank / IHME-type covariates

---

## 4) Canonical Evidence Graph

### 4.1 Core Node Types (required)
- Trial, RegistrySnapshot (immutable), Publication
- ExtractedResult, OutcomeDefinition
- Claim, Witness, Consensus
- LinkageDecision, Conflict, Adjudication, Abstention
- CapsuleRun, DriftEvent, ExplainReport

### 4.2 Extension Node Types (optional)
- SystematicReview, MetaAnalysis
- TransportModel, TargetPopulationSchema, DecisionContext
- HTAModel, ContextDatum, OntologyTerm, RoBAssessment

### 4.3 IDs (CURIE-like)
- Trials: `trial:ctgov:NCT...`, `trial:isrctn:...`
- Snapshots: `reg:<registry>:<id>:snap:<sha256>`
- Publications: `pub:pmid:...`, `pub:doi:...`
- Runs: `run:<UTC_ISO8601>:<git_sha>:<machine_id>`

---

## 5) Right Names (Ontology-First)

**Ontology is law.** Analysis cannot run on unmapped free-text.

### 5.1 Timepoint Window Model
Each timepoint: `target_value`, `unit`, `lower_window`, `upper_window`
Match types: `exact` (preferred), `windowed`, `inferred` (discouraged)

### 5.2 Unit Normalization
Canonical unit per outcome; conversions are explicit, versioned transforms.

### 5.3 OutcomeDefinition Governance
- One **canonical** OutcomeDefinition per primary endpoint per topic
- Variants allowed only if in `allowable_variants[]`
- Unmapped results → conflict/abstain

### 5.4 Enrollment-Lock Snapshot Rule
For missingness defense: use `trial_lock_snapshot_id` (earliest snapshot on/after enrollment date).

---

## 6) Study Design + Timepoint Selection

### 6.1 StudyDesign Field
`study_design ∈ {parallel, cluster, crossover, factorial, other}`

### 6.2 Timepoint Selection Policy
Meta must declare: `primary_prespecified` | `longest_followup` | `hierarchical_rule`

---

## 7) Witness Ladder (isnad → engineering)

### 7.1 Witness Grades
- **Grade A:** Registry results table; primary paper table with clear arms/outcome/timepoint
- **Grade B:** SR extract with traceable trial list
- **Grade C:** Inferred text; fuzzy linkage

### 7.2 Quorum Rule
Publishable-grade claim requires:
- **Q1:** 1 Grade-A witness, OR
- **Q2:** ≥2 independent witnesses agreeing within tolerance, OR
- **Q3:** Adjudication logged with explicit reasoning

---

## 8) Prespec Hierarchy + Primary Results Selection

1. SAP (witnessed, pre-unblinding)
2. Registry at lock snapshot
3. Protocol publication
4. Later registry updates (drift-flagged)
5. Paper-only claims

---

## 9) Missingness Ledger (required)

Per trial × outcome × timepoint:
- `planned_status ∈ {planned, not_planned, unknown}`
- `observed_status ∈ {observed, missing, partial, ambiguous}`

---

## 10) Record Linkage

All dedupe/linkage as `LinkageDecision` objects:
- `decision ∈ {link, non_link, possible_link}`
- `score`, `thresholds`, `evidence[]`, `method_version`

---

## 11) Lanes (yin–yang: generator vs validator)

| Lane | Generator | Validator | Gated |
|------|-----------|-----------|-------|
| Map | Always | Schema + linkage | No |
| Meta | Gated | Recompute | Yes |
| Transport | Gated | Overlap + shift | Yes |
| HTA | Gated | Structure + double-count | Yes |

---

## 12-14) Lane-Specific Rules

See full spec for Meta (Section 12), Transport (Section 13), and HTA (Section 14) requirements.

---

## 15) Minimal RoB / Certainty Stub

Per meta output: missingness signals, witness grade density, linkage confidence, drift stability.
Emit: `certainty_level ∈ {low, moderate, high}` + top drivers.

---

## 16) Validators as Law

### Severity Levels
- **P0:** Block (must pass)
- **P1:** Warn (badge cap)
- **P2:** Info

### Circuit Breaker Escalation
1. 1st trigger: warn + map-only
2. 2nd trigger: freeze meta/transport/HTA
3. 3rd trigger: require maintainer signoff

---

## 17) Drift Ledger (required)

DriftEvents for: sign flip, effect magnitude, inclusion changes, outcome remaps, missingness, registry edits.

---

## 18-19) Operations

- Serialization: GRAPH/ (Parquet), VIEWS/, indices/ (DuckDB)
- Deterministic merge semantics
- Query contract views required

---

## 20) EXPLAIN.json + NUMBER_CARD.json

### EXPLAIN.json
Top blockers, warnings, drift, next actions, badge summary, incidents.

### NUMBER_CARD.json
For any published number: value, uncertainty, badge, witnesses, consensus rule, limitations.

---

## 21-24) Reproduction, Security, Copyright

- Reproduction modes: Public (no restricted text) / Full (local validation)
- Key rotation + revocation
- Sensitivity tags: public | restricted | internal
- No paywalled redistribution

---

## 25) Capsule Contract

Each run emits:
- `MANIFEST.json` (capsule_id = sha256)
- `GRAPH/`, `OUTPUT/`, `VIEWS/`, `VALIDATION/`, `LINEAGE/`
- `EXPLAIN.json`, `NUMBER_CARD.json` templates
- `PROVENANCE.md`, `CHANGELOG.md`, `CITATION.cff`

---

## 26) Schema Evolution

SemVer: MAJOR (breaking), MINOR (additive), PATCH (clarification)
RFC required for breaking changes.

---

## 27-28) Burhan Volumes + Review Rituals

Signed, diffable bundles with capsule index, drift ledger, coverage dashboards.
Release ceremonies with go/no-go checklist.

---

## Schemas

All schemas are in `qa/schemas/truthcert/`:

```
qa/schemas/truthcert/
├── index.json                    # Schema index
├── curie_ids.schema.json         # CURIE ID patterns
├── trial.schema.json             # Trial node
├── registry_snapshot.schema.json # Immutable snapshot
├── publication.schema.json       # Publication node
├── extracted_result.schema.json  # Extracted result
├── outcome_definition.schema.json # Canonical outcomes
├── claim.schema.json             # Claim with witnesses
├── witness.schema.json           # Witness with grades
├── quorum.schema.json            # Quorum rules
├── consensus.schema.json         # Consensus resolution
├── conflict.schema.json          # Conflict tracking
├── adjudication.schema.json      # Adjudication decisions
├── abstention.schema.json        # Abstention records
├── linkage_decision.schema.json  # Record linkage
├── capsule_run.schema.json       # Run provenance
├── drift_event.schema.json       # Drift events
├── missingness_ledger.schema.json # Missingness tracking
├── lane_config.schema.json       # Lane configuration
├── meta_method_registry.schema.json # Meta methods
├── transport_config.schema.json  # Transport config
├── hta_config.schema.json        # HTA config
├── explain_report.schema.json    # EXPLAIN.json
├── number_card.schema.json       # NUMBER_CARD.json
└── capsule_manifest.schema.json  # MANIFEST.json
```

---

## 3-Box Architecture

```
Box A (RCT Graph)     Box B (Context)      Box C (Methods)
├── Map lane          ├── Transport lane   ├── Meta lane
├── Ingest            ├── Context          ├── HTA lane
├── Trials            ├── WHO/WB/IHME      ├── Validators
├── Snapshots         ├── Covariates       ├── Capsules
└── Linkages          └── Parquets         └── Volumes
```

---

*End of SPEC.md*
