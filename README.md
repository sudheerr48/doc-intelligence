# Doc Intelligence

**Your files, understood.**

AI-powered local file intelligence with duplicate detection, PII scanning, smart organization suggestions, full-text search, and a web dashboard. 100% local and private — your files never leave your machine.

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-green.svg)](https://www.python.org)

## Features

### Core
- **Parallel scanning** — Multiprocessing file hashing across all CPU cores with xxHash (13x faster than SHA256)
- **Incremental scans** — Only re-hashes new or modified files
- **Full-text search** — Search inside PDFs, documents, code files, and more
- **Duplicate detection** — Find exact duplicates with safe two-step cleanup workflow
- **Real-time monitoring** — Watchdog-based file watcher keeps the index current
- **DuckDB storage** — Fast analytical queries on file metadata

### AI-Powered (Pro)
- **Smart tagging** — AI-powered file classification with Claude or GPT
- **PII detection** — Scan for SSNs, credit cards, emails, phone numbers (runs locally)
- **Smart suggestions** — Get recommendations for organizing scattered files
- **Image classification** — Classify images as screenshots, photos, documents, diagrams
- **Semantic search** — Search files by meaning using embeddings
- **Natural language queries** — Ask questions in plain English
- **MCP server** — Expose your file index to AI assistants (Claude Desktop, VS Code)

### Dashboard
- **Web UI** — Streamlit dashboard with 13 pages: overview, file browser, duplicates, tags, health, search, PII scanner, suggestions, image classification, analytics, git branches, license management, and settings

## Privacy & Security

**Your files never leave your machine.** Doc Intelligence is local-first by design:
- No cloud storage, no accounts, no uploads
- Zero telemetry by default (opt-in only)
- AI features use your own API keys — we never see them
- PII detection runs entirely offline with regex patterns
- See [PRIVACY.md](PRIVACY.md) and [SECURITY.md](SECURITY.md) for details

## Quick Start

```bash
# Install
pip install doc-intelligence

# First-time setup wizard
doc-intelligence setup

# Or manually: scan your files
doc-intelligence scan

# Search by filename or content
doc-intelligence search "quarterly report"

# Find and manage duplicates
doc-intelligence duplicates
doc-intelligence duplicates --auto-stage

# Scan for sensitive data (PII)
doc-intelligence pii-scan

# Get organization suggestions
doc-intelligence suggest

# Open the web dashboard
doc-intelligence dashboard

# View health report
doc-intelligence health
```

## Installation

### pip (All Platforms)
```bash
pip install doc-intelligence           # Core features
pip install 'doc-intelligence[all]'    # All features including AI
```

### From Source
```bash
git clone https://github.com/user/doc-intelligence
cd doc-intelligence
make install-all   # or: pip install -e ".[all]"
```

### Platform Notes

| Platform | Status | Notes |
|----------|--------|-------|
| **macOS** | Fully supported | `brew install python3` if needed |
| **Linux** | Fully supported | Works on all major distributions |
| **Windows** | Fully supported | Use PowerShell or Windows Terminal |

Run `doc-intelligence platform-info` to see platform-specific paths and settings.

## CLI Commands

| Command | Description |
|---------|-------------|
| `setup` | First-time setup wizard |
| `scan` | Scan folders and build the file index |
| `search` | Search files by name, path, or content |
| `duplicates` | Find and report duplicate files |
| `cleanup` | Review and manage staged files |
| `watch` | Monitor directories for real-time changes |
| `stats` | Show database statistics |
| `health` | File system health report with scoring |
| `pii-scan` | Scan for PII (SSNs, credit cards, emails) |
| `suggest` | Smart file organization suggestions |
| `image-classify` | Classify images by type |
| `tag` | AI-powered file classification |
| `tags` | Browse tags and tagged files |
| `ask` | Natural language queries about your files |
| `embed` | Generate embeddings for semantic search |
| `semantic-search` | Search files by meaning |
| `dashboard` | Launch the web UI |
| `activate` | Activate a Pro license key |
| `license` | Show current license status |
| `telemetry` | Manage anonymous analytics |
| `serve` | Start MCP server for AI assistants |
| `platform-info` | Show platform and installation info |

## Pricing

| Feature | Free | Pro ($29) | Team ($99/yr) |
|---------|------|-----------|---------------|
| Files | 1,000 | Unlimited | Unlimited |
| Search & duplicates | Yes | Yes | Yes |
| Health reports | Yes | Yes | Yes |
| Web dashboard | Yes | Yes | Yes |
| AI tagging | — | Yes | Yes |
| PII detection | — | Yes | Yes |
| Semantic search | — | Yes | Yes |
| Image classification | — | Yes | Yes |
| MCP server | — | Yes | Yes |
| Priority support | — | — | Yes |

```bash
doc-intelligence activate DI-PRO-XXXXXXXX-...
```

## Configuration

Edit `config/config.yaml`:

```yaml
scan_folders:
  - path: ~/Documents
    category: documents
  - path: ~/Downloads
    category: downloads

deduplication:
  hash_algorithm: xxhash  # or sha256, md5
  min_size_bytes: 1024

database:
  path: ./data/files.duckdb
```

## Testing

```bash
pip install -e ".[dev]"
pytest                    # run all tests
pytest tests/ -v          # verbose output
```

## Dependencies

- **duckdb** — Fast analytical database
- **xxhash** — High-speed content hashing
- **pypdf** — PDF text extraction
- **watchdog** — Filesystem monitoring
- **typer** + **rich** — Beautiful CLI
- **streamlit** — Web dashboard (optional)
- **anthropic** / **openai** — AI features (optional)

## License

MIT — see [LICENSE](LICENSE) for details.
