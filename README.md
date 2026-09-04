# InspireHEP MCP Server

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

## Remote endpoint deployment

The installed command remains a stdio server by default, so existing desktop
configurations continue to work. To run it natively as a remote MCP endpoint,
select the Streamable HTTP transport:

```bash
INSPIREHEP_ALLOWED_HOSTS="mcp.example.org" \
  INSPIREHEP_HTTP_RATE_LIMIT=60 \
  inspirehep-mcp --transport streamable-http --host 0.0.0.0 --port 8000
```

The MCP endpoint is `http://localhost:8000/mcp` and the unauthenticated health
probe is `http://localhost:8000/health`. `PORT` is also honored when a hosting
platform injects it. Put the service behind HTTPS for internet deployment.

### Docker

Release tags publish a container to the GitHub Container Registry. The image
uses Streamable HTTP by default:

```bash
docker run --rm -p 8000:8000 \
  ghcr.io/mohamedelashri/inspirehep-mcp:latest
```

For a public hostname, add it to the host allowlist:

```bash
docker run --rm -p 8000:8000 \
  -e INSPIREHEP_ALLOWED_HOSTS="mcp.example.org" \
  -e INSPIREHEP_HTTP_RATE_LIMIT=60 \
  ghcr.io/mohamedelashri/inspirehep-mcp:latest
```

The image runs as a non-root user, has a built-in health check, and uses
stateless JSON responses so replicas do not need shared MCP session state.

### Docker Compose

The included [`docker-compose.yml`](docker-compose.yml) can build the current
checkout or run the published image:

```bash
# Local deployment
docker compose up --build -d

# Add the public hostname when deploying behind a domain
INSPIREHEP_ALLOWED_HOSTS="mcp.example.org" docker compose up -d
```

The Compose service is read-only, drops Linux capabilities, enables
`no-new-privileges`, and retains the image health check.

### Inbound rate limiting

Streamable HTTP requests are limited per client IP with a token bucket. The
default is 60 requests per minute with a burst of 20; `/health` is exempt. Set
`INSPIREHEP_HTTP_RATE_LIMIT=0` to disable it.

Requests to `/mcp` are limited to 256 KiB. The native server also accepts at
most 100 concurrent connections or tasks, closes idle keep-alive connections
after 5 seconds, and admits at most 32 pending INSPIRE API cache misses. Excess
upstream work fails fast instead of accumulating in memory.

By default, the limiter uses the direct peer address and ignores forwarded
headers. Only enable `INSPIREHEP_TRUST_PROXY_HEADERS` when a trusted reverse
proxy overwrites `X-Forwarded-For`; otherwise clients can choose their own
rate-limit identity. The limiter is in-memory and per process, so multi-replica
deployments should also enforce a shared limit at the proxy or gateway.

> [!IMPORTANT]
> Read-only tools avoid mutation risk, but a public endpoint can still be used
> to consume your compute and upstream API allowance. This server does not add
> authentication. Use an authenticating reverse proxy if the endpoint should
> not be open to everyone, and retain an edge rate limit for distributed
> deployments. Keep DNS-rebinding protection enabled and set
> `INSPIREHEP_ALLOWED_ORIGINS` for clients that send an Origin header.

## Integration

### Claude Desktop / Cursor

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

### Antigravity CLI

Open the interactive MCP manager with `/mcp`, or configure the server manually.
Antigravity reads global MCP servers from `~/.gemini/config/mcp_config.json`
and workspace-local servers from `.agents/mcp_config.json`:

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

## Configuration

All settings via environment variables (prefix `INSPIREHEP_`):

| Variable | Default | Description |
|----------|---------|-------------|
| `INSPIREHEP_REQUESTS_PER_SECOND` | `1.5` | API rate limit |
| `INSPIREHEP_UPSTREAM_MAX_PENDING` | `32` | Maximum admitted INSPIRE API cache misses |
| `INSPIREHEP_CACHE_TTL` | `86400` | Cache TTL in seconds (24h) |
| `INSPIREHEP_CACHE_MAX_SIZE` | `512` | Max cached entries |
| `INSPIREHEP_CACHE_PERSISTENT` | `false` | Enable SQLite persistent cache |
| `INSPIREHEP_CACHE_DB_PATH` | `inspirehep_cache.db` | SQLite cache file path |
| `INSPIREHEP_API_TIMEOUT` | `30` | HTTP request timeout (seconds) |
| `INSPIREHEP_TRANSPORT` | `stdio` | `stdio` or `streamable-http` |
| `INSPIREHEP_HOST` | `127.0.0.1` | HTTP bind address |
| `INSPIREHEP_PORT` | `8000` | HTTP port; falls back to `PORT` |
| `INSPIREHEP_HTTP_PATH` | `/mcp` | Streamable HTTP endpoint path |
| `INSPIREHEP_HTTP_STATELESS` | `true` | Disable server-side MCP session state |
| `INSPIREHEP_HTTP_JSON_RESPONSE` | `true` | Prefer JSON responses over SSE streams |
| `INSPIREHEP_HTTP_RATE_LIMIT` | `60` | Inbound requests per minute per client; `0` disables |
| `INSPIREHEP_HTTP_RATE_LIMIT_BURST` | `20` | Maximum immediate requests per client |
| `INSPIREHEP_HTTP_RATE_LIMIT_MAX_CLIENTS` | `10000` | Maximum in-memory client buckets |
| `INSPIREHEP_HTTP_MAX_BODY_SIZE` | `262144` | Maximum `/mcp` request body bytes; `0` disables |
| `INSPIREHEP_HTTP_MAX_CONCURRENCY` | `100` | Maximum concurrent HTTP connections or tasks |
| `INSPIREHEP_HTTP_KEEP_ALIVE_TIMEOUT` | `5` | Idle HTTP keep-alive timeout in seconds |
| `INSPIREHEP_TRUST_PROXY_HEADERS` | `false` | Trust the first `X-Forwarded-For` address |
| `INSPIREHEP_MAX_INPUT_LENGTH` | `2048` | Maximum general text input characters |
| `INSPIREHEP_MAX_IDENTIFIER_LENGTH` | `512` | Maximum identifier input characters |
| `INSPIREHEP_MAX_RESPONSE_BYTES` | `1048576` | Maximum serialized tool-result bytes |
| `INSPIREHEP_MAX_REFERENCES` | `250` | Maximum references returned per tool call |
| `INSPIREHEP_MAX_FIGURES` | `100` | Maximum figures returned per tool call |
| `INSPIREHEP_ALLOWED_HOSTS` | `127.0.0.1:*,localhost:*` | Comma-separated valid HTTP Host headers |
| `INSPIREHEP_ALLOWED_ORIGINS` | empty | Comma-separated valid browser origins |
| `INSPIREHEP_DNS_REBINDING_PROTECTION` | `true` | Validate Host and Origin headers |
| `INSPIREHEP_LOG_LEVEL` | `INFO` | Logging level |

## Development

```bash
# Run tests
uv run pytest tests/ -v

# Run with coverage
uv run pytest tests/ --cov=inspirehep_mcp --cov-report=term-missing

# Unit tests only (no network)
uv run pytest tests/test_utils.py tests/test_cache.py tests/test_errors.py \
  tests/test_config.py tests/test_rate_limit.py tests/test_server.py \
  tests/test_api_client_safety.py tests/test_tools_safety.py
```

## LICENCE

This project is licensed under the AGPL-3.0 License - see the [LICENSE](LICENSE) file for details.
