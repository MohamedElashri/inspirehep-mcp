# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.3.0] - 2026-09-04

### Added

- Native Streamable HTTP endpoint mode with stateless JSON responses
- Container image with non-root execution and a health check
- Release-tag publishing to the GitHub Container Registry
- Bounded, per-client token-bucket rate limiting for the MCP HTTP endpoint,
  with health-check exemption and optional trusted-proxy support
- Request-body, HTTP concurrency, tool input/output, and upstream queue limits
- Hardened Docker Compose deployment example

### Changed

- CI now tests only the supported Python versions (3.12–3.14) and the actual
  default branch
- Package version advanced to 0.3.0 for the endpoint deployment release
- Integration documentation now covers Antigravity CLI and removes obsolete
  client instructions
- Container builds now install the exact dependency versions in `uv.lock`
- Runtime version reporting now derives from package metadata, leaving
  `pyproject.toml` as the single version source

### Fixed

- GitHub Releases now download the Python build artifact before attaching it
- The InspireHEP API User-Agent now reports the package version
- Source distributions no longer include local test and package-manager caches
- Removed the public `server_stats` tool to avoid exposing operational metrics

### Security

- Enabled DNS-rebinding Host and Origin validation for remote MCP traffic
- Refreshed dependencies to versions without the advisories found in the prior
  lockfile
- Pinned all GitHub Actions to immutable commit SHAs and reduced release-job
  token permissions

## [0.2.0] - 2026-08-25

Migrated the server to the latest MCP ecosystem: Python SDK v2 and the
2026-07-28 Model Context Protocol specification.

### Changed

- Migrated from `FastMCP` (`mcp.server.fastmcp`) to `MCPServer`
  (`mcp.server.mcpserver`), following the MCP Python SDK v2 rename
- Updated the SDK dependency from `mcp[cli]>=1.0.0` (v1, now in maintenance
  mode) to `mcp[cli]>=2,<3`, which speaks the 2026-07-28 protocol revision
  while remaining compatible with 2025-era clients
- Replaced `httpx` with its drop-in fork `httpx2>=2.5.0` in both the
  dependencies and the API client, matching the SDK's HTTP stack
- Tools now return typed dictionaries instead of JSON-encoded strings,
  producing structured tool results with inferred output schemas
- All tools declare `readOnlyHint`/`idempotentHint` annotations and
  human-readable titles for richer client discovery and safety metadata

### Added

- Server identity metadata: `title`, `description`, expanded usage
  `instructions`, and a reported `version`

### Fixed

- Stale `__version__` in the package `__init__.py` (reported `0.1.0` since
  v0.1.1)

### Verified

- Full test suite passes (unit + live-API integration)
- End-to-end stdio session: initialize, list tools with schemas, call tools
  with structured content round-trips
- All 10 tools exercised successfully through a real third-party MCP client
  (OpenAI Codex CLI)

## [0.1.4] - 2026-05-10

### Fixed

- Support the `arxiv:` prefix in arXiv identifier parsing (#8)

## [0.1.3] - 2026-03-05

### Changed

- Dependency updates (python-dotenv, python-multipart, cryptography,
  pyjwt, pygments)

## [0.1.2] - 2026-03-04

### Added

- `get_paper_figures` tool for retrieving paper figures with captions and
  download URLs (#5)
- Numeric inputs accepted by identifier normalization/detection utilities

## [0.1.1] - 2026-02-15

### Added

- `get_bibtex` tool for retrieving BibTeX citation entries

## [0.1.0] - 2026-02-06

### Added

- Initial release: InspireHEP literature search and retrieval MCP server
  with caching, rate limiting, and 8 literature tools
