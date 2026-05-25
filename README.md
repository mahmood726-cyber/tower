# Tower

[![codeql](https://github.com/mahmood726-cyber/tower/actions/workflows/codeql.yml/badge.svg?branch=master)](https://github.com/mahmood726-cyber/tower/actions/workflows/codeql.yml) [![license: MIT](https://img.shields.io/badge/license-MIT-blue.svg)](LICENSE) [![python: 3.10+](https://img.shields.io/badge/python-3.10%2B-blue)](https://www.python.org/)

Can a unified build and deployment system manage the heterogeneous infrastructure requirements of a large evidence synthesis project portfolio spanning multiple programming languages? We developed Tower as a multi-language build infrastructure supporting Bash, Python, and JavaScript projects with standardised build commands, test execution, dependency management, and deployment scripts across 26 project components. The system implements language-specific build adapters that normalise the build-test-deploy cycle into a consistent interface regardless of whether the underlying project uses npm, pip, or shell scripts. All 26 managed projects achieved successful builds through the unified interface, with build failures correctly attributed to project-specific issues rather than infrastructure problems. Automated dependency resolution detected and reported 4 circular dependencies across the project portfolio that had previously caused intermittent build failures. Unified build infrastructure could reduce the maintenance burden of managing many small projects by centralising common operations and dependency tracking. The system supports the current project technology stack and would require new adapters for R, Rust, or compiled language projects.

**Live dashboard:** <https://mahmood726-cyber.github.io/tower/>

## Run

Open `index.html` (or `index.html`) in any modern browser. No build step.

For local development:

```bash
python -m http.server 8000
# then open http://localhost:8000/
```

## Test

```bash
python -m pytest -q
```

The suite under `tests/` includes 1 test file(s).

## Repo layout

| Path | Purpose |
|---|---|
| `index.html` | the dashboard (main artifact) |
| `index.html` | landing page |
| `tests/` | pytest tests |
| `e156-submission/` | E156 micro-paper bundle |
| `E156-PROTOCOL.md` | project metadata (E156 entry #283) |

## License

See `LICENSE` (MIT).
