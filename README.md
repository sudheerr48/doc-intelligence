# Doc Intelligence

A fast, local file indexing tool with duplicate detection, full-text search, and real-time monitoring. Built with Python and DuckDB.

## Features

- **Parallel scanning** - Multiprocessing file hashing across all CPU cores
- **Smart hashing** - xxHash by default (13x faster than SHA256), with SHA256/MD5 options
- **Incremental scans** - Only re-hashes new or modified files
- **Text extraction** - Extracts searchable text from PDFs, TXT, CSV, JSON, HTML, Markdown, and source code
- **Full-text search** - Search by filename, path, or document content
- **Duplicate detection** - Find exact duplicates by content hash with actionable cleanup
- **Duplicate management** - Stage duplicates for review, auto-stage keeping newest, dry-run preview, restore or permanently delete
- **Real-time monitoring** - Watchdog-based file watcher updates the index on create/modify/delete/move
- **DuckDB storage** - Fast analytical queries on file metadata with bulk insert optimization
- **Unified CLI** - Single `doc-intelligence` command with six subcommands

## Quick Start

```bash
# Install
pip install -e ".[dev]"

# Configure folders to scan (edit config/config.yaml with your paths)

# Scan your files
doc-intelligence scan

# Search by filename or content
doc-intelligence search "quarterly report"

# Find and manage duplicates
doc-intelligence duplicates
doc-intelligence duplicates --auto-stage    # stage duplicates, keep newest
doc-intelligence duplicates --dry-run       # preview without moving files
doc-intelligence cleanup                    # review staged files
doc-intelligence cleanup --confirm          # permanently delete staged files

# Monitor for changes
doc-intelligence watch

# View statistics
doc-intelligence stats
```

You can also scan a single directory without editing the config:

```bash
doc-intelligence scan --path ~/Documents --category docs
doc-intelligence search "invoice" --extension pdf
```

## CLI Commands

| Command | Description | Key Flags |
|---------|-------------|-----------|
| `scan` | Scan folders and build the file index | `--path`, `--algorithm` |
| `search` | Search files by name, path, or content | `--extension`, `--limit` |
| `duplicates` | Find and report duplicate files | `--auto-stage`, `--dry-run`, `--export-csv` |
| `cleanup` | Review and manage staged files | `--confirm`, `--restore` |
| `watch` | Monitor directories for real-time changes | `--path`, `--category` |
| `stats` | Show database statistics | `--config` |

## Configuration

Edit `config/config.yaml`:

```yaml
scan_folders:
  - path: ~/Documents
    category: documents
  - path: ~/Downloads
    category: downloads

exclude_patterns:
  - ".git"
  - "node_modules"
  - "__pycache__"

deduplication:
  hash_algorithm: xxhash  # or sha256, md5
  min_size_bytes: 1024    # skip files under 1KB

database:
  path: ./data/files.duckdb
```

## Project Structure

```
doc-intelligence/
├── config/
│   └── config.yaml          # Scan configuration
├── data/                     # Database storage (gitignored)
├── scripts/
│   ├── cli.py               # Unified CLI entry point
│   ├── scan.py              # Scanner CLI
│   ├── search.py            # Search CLI
│   ├── find_duplicates.py   # Duplicates CLI (--auto-stage, --dry-run)
│   ├── cleanup.py           # Staged file management CLI
│   └── watch.py             # File watcher CLI
├── src/
│   ├── scanner.py           # Parallel file scanning & hashing
│   ├── storage.py           # DuckDB operations (bulk insert, full-text search)
│   ├── extractors.py        # Text extraction (PDF, plaintext)
│   ├── staging.py           # Duplicate staging & cleanup lifecycle
│   ├── watcher.py           # Watchdog event handler
│   └── utils.py             # Config loading, formatting helpers
├── tests/
│   ├── conftest.py          # Shared fixtures
│   ├── test_scanner.py      # 32 tests
│   ├── test_storage.py      # 32 tests
│   ├── test_extractors.py   # 21 tests
│   ├── test_staging.py      # 27 tests
│   ├── test_watcher.py      # 18 tests
│   └── test_cli.py          # 28 tests
├── pyproject.toml
└── README.md
```

## How It Works

1. **Scan** - Recursively walks directories, collecting file metadata
2. **Hash** - Computes content hashes in parallel across CPU cores
3. **Extract** - Pulls searchable text from PDFs and text-based files
4. **Store** - Bulk-inserts metadata into DuckDB with indexed columns
5. **Query** - Search by name/path/content, find duplicates, view stats
6. **Watch** - Optional real-time monitoring updates the index on file changes
7. **Manage** - Stage duplicates for review, then confirm deletion or restore

## Testing

```bash
pip install -e ".[dev]"
pytest                    # run all 158 tests
pytest tests/test_scanner.py -v   # run a specific module
```

## Dependencies

- **duckdb** - Fast analytical database for metadata storage
- **xxhash** - High-speed content hashing
- **pypdf** - PDF text extraction
- **watchdog** - Filesystem event monitoring
- **typer** - CLI framework
- **rich** - Terminal formatting and tables
- **pyyaml** - Configuration parsing
- **tqdm** - Progress bars

## Requirements

- Python 3.9+

## License

MIT
