# 📁 Doc Intelligence

A fast, local file indexing and duplicate detection tool built with Python and DuckDB.

## Features

- **Fast scanning** - Parallel file hashing with multiprocessing
- **Smart hashing** - Uses xxHash (13x faster than SHA256)
- **Incremental scans** - Only re-hashes new/modified files
- **Duplicate detection** - Find exact duplicates by content hash
- **DuckDB storage** - Lightning-fast queries on file metadata
- **Beautiful CLI** - Rich terminal output with progress bars

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure folders to scan
# Edit config/config.yaml with your paths

# Run the scanner
python scripts/scan.py

# Find duplicates
python scripts/find_duplicates.py

# Search for files
python scripts/search.py "keyword"
```

## Configuration

Edit `config/config.yaml` to specify:

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
  - ".DS_Store"

deduplication:
  hash_algorithm: xxhash  # or sha256, md5
  min_size_bytes: 1024    # skip tiny files
```

## Project Structure

```
doc-intelligence/
├── config/
│   └── config.yaml       # Scan configuration
├── data/                  # Database storage (gitignored)
├── scripts/
│   ├── scan.py           # Main scanner entry point
│   ├── find_duplicates.py
│   └── search.py
├── src/
│   ├── scanner.py        # File scanning & hashing
│   └── storage.py        # DuckDB operations
├── requirements.txt
└── README.md
```

## How It Works

1. **Scan** - Recursively walks directories, collecting file metadata
2. **Hash** - Computes content hashes in parallel (configurable algorithm)
3. **Store** - Saves metadata to DuckDB with indexes on hash & extension
4. **Query** - Find duplicates, search by name, analyze by category

## Requirements

- Python 3.9+
- ~50MB RAM for 10,000 files

## Dependencies

- `duckdb` - Fast analytical database
- `xxhash` - High-speed hashing
- `typer` - CLI framework
- `rich` - Beautiful terminal output
- `pyyaml` - Config parsing
- `tqdm` - Progress bars

## License

MIT
