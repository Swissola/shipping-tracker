# Phase 1: Scaffold - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-05-31
**Phase:** 1-Scaffold
**Areas discussed:** Entry point behavior, HTTP client, Logging library, mypy strictness, Dependency groups, Python version pinning, CI runner / OS

---

## Entry Point Behavior

| Option | Description | Selected |
|--------|-------------|----------|
| Run the pipeline directly | No flags needed for cron — just runs the pipeline | ✓ |
| Require explicit --run flag | Gate execution behind a flag so accidental invocations are safe | |
| Add --dry-run / --verbose flags | Run with optional --dry-run and --verbose flags from day 1 | |

**User's choice:** Run the pipeline directly — zero-argument, cron-friendly.

| Option | Description | Selected |
|--------|-------------|----------|
| Zero-argument, no flags | Everything configured via .env | ✓ |
| --dry-run flag only | One escape hatch for safe testing of the Gmail + parser path | |
| You decide | Claude picks the minimal CLI surface | |

**User's choice:** Zero-argument, no flags.

| Option | Description | Selected |
|--------|-------------|----------|
| Both __main__.py + console_scripts | Enables both `python -m shipping_tracker` and `shipping-tracker` command | ✓ |
| __main__.py only | Only `python -m shipping_tracker` works | |
| console_scripts only | Install-time command only | |

**User's choice:** Both — `__main__.py` for `python -m` and `console_scripts` for the installed command.

| Option | Description | Selected |
|--------|-------------|----------|
| Synchronous | Simpler, easier to test, cron use case doesn't benefit from async | ✓ |
| Async with asyncio.run() | Future-proofs against async clients | |

**User's choice:** Synchronous, with potential to move to async. Architecture must not block async adoption.

---

## HTTP Client

| Option | Description | Selected |
|--------|-------------|----------|
| httpx | Modern API, first-class type annotations, async-capable | ✓ |
| requests | Battle-tested, sync only, familiar | |

**User's choice:** httpx.

| Option | Description | Selected |
|--------|-------------|----------|
| Sync only for now (httpx.Client) | No async complexity until needed | ✓ |
| Async client from the start (httpx.AsyncClient) | Consistent with async-ready intent, adds complexity | |

**User's choice:** Sync only for now.

---

## Logging Library

| Option | Description | Selected |
|--------|-------------|----------|
| structlog | Clean structured API, first-class key=value binding, one extra dependency | ✓ |
| stdlib + JSON formatter | Zero additional dependency, more boilerplate | |

**User's choice:** structlog. Additional requirement: compact JSON output (no whitespace) for token efficiency when output may be parsed by LLMs.

| Option | Description | Selected |
|--------|-------------|----------|
| Rotating file (10MB, keep 3) | Cron-friendly, never fills disk | ✓ |
| Fixed file, no rotation | Simple but risks filling disk | |
| Configurable via .env | Flexible but adds config surface area | |

**User's choice:** Rotating file — 10MB max, 3 rotations.

| Option | Description | Selected |
|--------|-------------|----------|
| WARNING | Only logs problems during normal operation | ✓ |
| INFO | Logs each processed email and API call | |
| Configurable via .env | Operator-tunable without source changes | |

**User's choice:** WARNING default.

---

## mypy Strictness

| Option | Description | Selected |
|--------|-------------|----------|
| Strict (--strict) | Full enforcement, no silent Any propagation, every function typed | ✓ |
| Moderate (disallow_untyped_defs only) | Signatures typed but Any can propagate silently | |

**User's choice:** Strict (--strict). User asked for a full explanation of the consequences before deciding.
**Notes:** User understood that --strict with Gmail API's patchy stubs will require explicit `cast()` calls in a few places. Decided strict is worth it for the type safety guarantees across the parser/dedup/API layer interfaces.

---

## Dependency Groups

| Option | Description | Selected |
|--------|-------------|----------|
| Split into optional groups | [project.dependencies] runtime + [project.optional-dependencies] dev group | ✓ |
| Flat — all in [project.dependencies] | Simpler, dev tools end up on the Pi | |

**User's choice:** Split — `pip install -e '.[dev]'` for full setup; production install skips dev tools.

---

## Python Version Pinning

| Option | Description | Selected |
|--------|-------------|----------|
| 3.11 only | Matches Pi 5 / Bookworm target exactly | |
| Matrix: 3.11 + 3.12 | Two CI jobs per push | |
| Matrix: 3.11 + 3.12 + 3.13 | Broadest coverage, useful for open-source | ✓ |

**User's choice:** Matrix 3.11 + 3.12 + 3.13 — anticipating open-source release and multi-environment support.

---

## CI Runner / OS

| Option | Description | Selected |
|--------|-------------|----------|
| ubuntu-latest | Standard, fast, free, Linux-first ecosystem | ✓ |
| ubuntu-latest + macos-latest | Catches macOS-specific issues for contributors | |
| Self-hosted arm64 | Closest to Pi hardware, significant setup overhead | |

**User's choice:** ubuntu-latest — sufficient for this project's needs.

---

## Claude's Discretion

None — all areas had explicit user decisions.

## Deferred Ideas

None — discussion stayed within phase scope.
