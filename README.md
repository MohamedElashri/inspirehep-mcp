# InspireHEP MCP Server

[![SafeSkill 92/100](https://img.shields.io/badge/SafeSkill-92%2F100_Verified%20Safe-brightgreen)](https://safeskill.dev/scan/mohamedelashri-inspirehep-mcp)

An [MCP](https://modelcontextprotocol.io/) server that integrates [InspireHEP](https://inspirehep.net/) high-energy physics literature with LLMs. Search papers, explore citations, retrieve author metrics, and generate formatted references.

## Installation

```bash
# Using pip
pip install inspirehep-mcp

# Or run directly with uvx (no install needed)
uvx inspirehep-mcp
```

<details>
<summary>Install from source</summary>

```bash
git clone https://github.com/MohamedElashri/inspirehep-mcp.git
cd inspirehep-mcp
uv sync
uv run inspirehep-mcp
```
</details>

## Integration

### Claude Desktop / Cursor / Windsurf

Add to your MCP client config:

```json
{
  "mcpServers": {
    "inspirehep": {
      "command": "uvx",
      "args": ["inspirehep-mcp"]
    }
  }
}
```

### Claude Code

**Option A: Using the CLI**

```bash
# Global scope (available across all projects)
claude mcp add --scope user inspirehep -- uvx inspirehep-mcp

# Project scope (shared via .mcp.json, checked into source control)
claude mcp add --scope project inspirehep -- uvx inspirehep-mcp
```

**Option B: Manual configuration**

For global scope, add to `~/.claude.json`:

```json
{
  "mcpServers": {
    "inspirehep": {
      "command": "uvx",
      "args": ["inspirehep-mcp"]
    }
  }
}
```

For project scope, create `.mcp.json` in your project root:

```json
{
  "mcpServers": {
    "inspirehep": {
      "command": "uvx",
      "args": ["inspirehep-mcp"]
    }
  }
}
```

### Gemini CLI

**Option A: Using the CLI**

```bash
# Project scope (default)
gemini mcp add inspirehep uvx inspirehep-mcp

# User/global scope
gemini mcp add -s user inspirehep uvx inspirehep-mcp
```

**Option B: Manual configuration**

Add to `~/.gemini/settings.json` (user scope) or `.gemini/settings.json` (project scope):

```json
{
  "mcpServers": {
    "inspirehep": {
      "command": "uvx",
      "args": ["inspirehep-mcp"]
    }
  }
}
```

## Tools

| Tool | Description |
|------|-------------|
| `search_papers` | Search papers by topic, author, collaboration, or free text |
| `get_paper_details` | Get full metadata for a paper by Inspire ID, arXiv ID, or DOI |
| `get_author_papers` | Retrieve an author's publications and citation metrics |
| `get_citations` | Explore citation graph — who cites a paper, or what it cites |
| `search_by_collaboration` | Find publications from ATLAS, CMS, LHCb, etc. |
| `get_paper_figures` | Retrieve figures and download URLs for a paper |
| `get_references` | Generate BibTeX, LaTeX, or JSON reference lists |
| `get_bibtex` | Retrieve BibTeX citation entry by DOI, arXiv ID, or Inspire ID |
| `server_stats` | Monitor cache hit rates and API performance |

## Configuration

All settings via environment variables (prefix `INSPIREHEP_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `INSPIREHEP_REQUESTS_PER_SECOND` | `1.5` | API rate limit |
| `INSPIREHEP_CACHE_TTL` | `86400` | Cache TTL in seconds (24h) |
| `INSPIREHEP_CACHE_MAX_SIZE` | `512` | Max cached entries |
| `INSPIREHEP_CACHE_PERSISTENT` | `false` | Enable SQLite persistent cache |
| `INSPIREHEP_CACHE_DB_PATH` | `inspirehep_cache.db` | SQLite cache file path |
| `INSPIREHEP_API_TIMEOUT` | `30` | HTTP request timeout (seconds) |
| `INSPIREHEP_LOG_LEVEL` | `INFO` | Logging level |

## Development

```bash
# Run tests
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ --cov=inspirehep_mcp --cov-report=term-missing

# Unit tests only (no network)
uv run pytest tests/test_utils.py tests/test_cache.py tests/test_errors.py tests/test_config.py
```

## LICENCE

This project is licensed under the AGPL-3.0 License - see the [LICENSE](LICENSE) file for details.
