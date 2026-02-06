# InspireHEP MCP Server

An [MCP](https://modelcontextprotocol.io/) server that integrates [InspireHEP](https://inspirehep.net/) high-energy physics literature with LLMs. Search papers, explore citations, retrieve author metrics, and generate formatted references.

## Quick Start

```bash
# Install
uv sync

# Run the server
uv run inspirehep-mcp
```

### Claude Desktop / Cursor / Windsurf

Add to your MCP client config:

```json
{
  "mcpServers": {
    "inspirehep": {
      "command": "uv",
      "args": ["--directory", "/path/to/inspirehep-mcp", "run", "inspirehep-mcp"]
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
| `get_references` | Generate BibTeX, LaTeX, or JSON reference lists |
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
