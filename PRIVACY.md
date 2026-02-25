# Privacy Policy — Doc Intelligence

**Last updated:** February 2026

## Our Promise: Your Files Never Leave Your Machine

Doc Intelligence is a **local-first** tool. All file scanning, indexing, duplicate detection, and search happens entirely on your computer. We have no servers, no cloud storage, no telemetry by default.

## What We Do

- **Scan files locally** — file metadata (names, sizes, hashes) is stored in a local DuckDB database on your machine
- **Extract text locally** — PDF and document text extraction runs on your CPU
- **Search locally** — all queries run against your local database

## What We Don't Do

- We **never** upload your files anywhere
- We **never** send file names, paths, or content to our servers
- We **never** collect personal information without explicit opt-in
- We **never** sell or share any data

## Optional AI Features

If you enable AI-powered features (tagging, semantic search, NL queries), file metadata and text snippets are sent to your chosen AI provider:

| Feature | Data Sent | Provider |
|---------|-----------|----------|
| AI Tagging | File name, extension, path, content snippet (500 chars) | Anthropic or OpenAI |
| Semantic Search | Content text for embedding generation | Voyage AI or OpenAI |
| NL Queries | Your search query + database schema | Anthropic or OpenAI |

**Important:**
- AI features require **your own API keys** — we never see them
- You choose your provider (Anthropic, OpenAI, Voyage AI)
- You can use Doc Intelligence fully without any AI features
- AI features are clearly marked in the UI and CLI

## Optional Telemetry

Telemetry is **OFF by default**. If you opt in:

- We collect: feature usage counts, error types, platform info
- We **never** collect: file names, paths, content, personal data
- Data is stored locally in `~/.config/doc-intelligence/telemetry.jsonl`
- You can opt out at any time: `doc-intelligence telemetry --disable`
- Opting out deletes all collected telemetry data

## PII Detection

The PII scanner detects sensitive data patterns (SSNs, credit cards, etc.) in your files. This runs **entirely locally** using regex patterns. No file content is sent anywhere for PII detection.

## Data Storage

All data is stored locally:

| Data | Location |
|------|----------|
| File index | `./data/files.duckdb` (configurable) |
| Configuration | `config/config.yaml` |
| License key | `~/.config/doc-intelligence/license.json` |
| Telemetry (if enabled) | `~/.config/doc-intelligence/telemetry.jsonl` |

## Deleting Your Data

To completely remove all Doc Intelligence data:

```bash
# Remove the database
rm -rf ./data/

# Remove user config and license
rm -rf ~/.config/doc-intelligence/

# Uninstall
pip uninstall doc-intelligence
```

## Contact

For privacy questions or concerns, open an issue on our GitHub repository.

---

**TL;DR:** Doc Intelligence runs on your machine, your files stay on your machine, and we don't collect anything unless you explicitly opt in.
