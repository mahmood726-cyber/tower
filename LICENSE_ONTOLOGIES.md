# LICENSE_ONTOLOGIES.md

## Ontology and Vocabulary Licenses

This document lists the ontologies and controlled vocabularies used in the TruthCert/Burhan evidence system, along with their licenses and attribution requirements.

---

## Medical/Clinical Ontologies

### MeSH (Medical Subject Headings)
- **Source:** National Library of Medicine
- **License:** Public Domain (US Government work)
- **URL:** https://www.nlm.nih.gov/mesh/
- **Usage:** Outcome classification, condition mapping
- **Attribution:** "MeSH data are produced by the U.S. National Library of Medicine"

### SNOMED CT
- **Source:** SNOMED International
- **License:** SNOMED CT License (free for certain uses)
- **URL:** https://www.snomed.org/
- **Usage:** Clinical concept mapping
- **Note:** Requires license agreement for commercial use

### ICD-10/ICD-11
- **Source:** World Health Organization
- **License:** WHO terms of use
- **URL:** https://www.who.int/standards/classifications/
- **Usage:** Disease classification
- **Attribution:** Required per WHO terms

### RxNorm
- **Source:** National Library of Medicine
- **License:** UMLS License
- **URL:** https://www.nlm.nih.gov/research/umls/rxnorm/
- **Usage:** Drug normalization
- **Note:** Requires UMLS license

---

## Study Design Vocabularies

### CONSORT
- **Source:** CONSORT Group
- **License:** Open/Academic
- **URL:** http://www.consort-statement.org/
- **Usage:** Trial reporting terms

### Cochrane
- **Source:** Cochrane Collaboration
- **License:** Creative Commons
- **URL:** https://www.cochrane.org/
- **Usage:** Review methodology terms

---

## Statistical Vocabularies

### Effect Measures
- **Source:** Internal (TruthCert)
- **License:** MIT
- **Terms:** RR, OR, HR, RD, MD, SMD, Fisher_z

### Model Types
- **Source:** Internal (TruthCert)
- **License:** MIT
- **Terms:** fixed_effect, random_effects_dl, random_effects_reml, etc.

---

## Context Data Sources

### WHO Global Health Observatory
- **Source:** World Health Organization
- **License:** CC BY-NC-SA 3.0 IGO
- **URL:** https://www.who.int/data/gho
- **Usage:** Health context covariates
- **Attribution:** Required

### World Bank Open Data
- **Source:** World Bank
- **License:** CC BY 4.0
- **URL:** https://data.worldbank.org/
- **Usage:** Socioeconomic covariates
- **Attribution:** Required

### IHME Global Burden of Disease
- **Source:** Institute for Health Metrics and Evaluation
- **License:** IHME terms (free for non-commercial)
- **URL:** https://www.healthdata.org/
- **Usage:** Disease burden data
- **Note:** Check terms for commercial use

---

## Registry Data

### ClinicalTrials.gov
- **Source:** National Library of Medicine
- **License:** Public Domain
- **URL:** https://clinicaltrials.gov/
- **Usage:** Trial registry data

### ICTRP
- **Source:** World Health Organization
- **License:** WHO terms
- **URL:** https://trialsearch.who.int/
- **Usage:** International trial registry

### EU Clinical Trials Register
- **Source:** European Medicines Agency
- **License:** EMA terms
- **URL:** https://www.clinicaltrialsregister.eu/
- **Usage:** EU trial data

---

## Internal Ontologies

### TruthCert Core
- **License:** MIT
- **Location:** `qa/schemas/truthcert/`
- **Terms:** All node types, edge types, CURIE patterns

### Outcome Definitions
- **License:** MIT
- **Location:** `ontologies/outcomes/`
- **Terms:** Canonical outcomes per domain

### Timepoint Vocabulary
- **License:** MIT
- **Location:** `ontologies/timepoints/`
- **Terms:** Timepoint window model

---

## Attribution Template

When using this system, include:

```
This analysis uses the TruthCert/Burhan evidence system.
Ontologies used include MeSH (NLM), WHO ICD, and internal classifications.
Context data from WHO GHO and World Bank Open Data.
See LICENSE_ONTOLOGIES.md for full attribution.
```

---

## Updates

This file is updated when new ontologies are added.
Last updated: 2026-02-07
