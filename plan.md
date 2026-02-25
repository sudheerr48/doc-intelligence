# Doc Intelligence — Market Readiness Plan

## Current State
- **v5.0** with Streamlit dashboard (9 pages), AI classification (Claude/OpenAI),
  embeddings, NL-to-SQL, MCP server, 158 tests, provider plugin system
- CLI with 15+ subcommands
- DuckDB storage, xxHash scanning, watchdog monitoring

## 10 Gaps to Address

### 1. Web UI (FastAPI + Enhanced Frontend)
- Add **FastAPI REST API** (`src/api/`) wrapping all existing database/AI functionality
- Endpoints: `/api/stats`, `/api/files`, `/api/search`, `/api/duplicates`, `/api/health`, `/api/tags`, `/api/scan`
- WebSocket for real-time scan progress
- CLI command: `doc-intelligence serve-api`
- This provides a proper REST API any frontend can consume (React, mobile, etc.)
- Keep existing Streamlit dashboard as alternative UI

### 2. AI Layer Enhancements
- **PII Detection** module (`src/ai/pii.py`) — regex + AI patterns for SSNs, credit cards, emails, phone numbers, addresses
- **Smart Suggestions** (`src/ai/suggestions.py`) — cluster files by tags/path/type, suggest folder reorganization
- **Image Classification** (`src/ai/image_classify.py`) — classify images as screenshots/photos/documents/diagrams using metadata heuristics (resolution, filename patterns) + optional AI vision
- New CLI commands: `doc-intelligence pii-scan`, `doc-intelligence suggest`
- New API endpoints for each

### 3. Installer / Distribution
- Polish `pyproject.toml` for PyPI: add classifiers, URLs, author info, keywords
- Add `MANIFEST.in` for sdist
- Create `Makefile` with `make install`, `make build`, `make publish` targets
- Add `scripts/build_installer.py` for PyInstaller single-file binary
- Homebrew formula template (`packaging/homebrew/doc-intelligence.rb`)

### 4. Landing Page
- Static HTML/CSS landing page in `docs/site/`
- Sections: hero, features, screenshots, download, privacy promise, pricing
- Ready to deploy to GitHub Pages or Vercel
- Single `index.html` + `style.css` — no build step needed

### 5. Monetization / Licensing
- License key module (`src/licensing/`) — local validation with HMAC signatures
- Tier system: Free (1000 files, no AI), Pro (unlimited files + AI + PII), Team
- `src/licensing/tiers.py` — feature gating logic
- `src/licensing/keys.py` — key generation/validation
- Integration points in scanner + AI commands to check tier limits

### 6. Onboarding / First-Run Experience
- `src/onboarding/` module with guided first-run wizard
- Auto-detect common folders (Documents, Downloads, Desktop, Photos)
- Interactive folder picker in CLI (Rich-powered)
- Progress display during first scan with ETA
- "Here's what I found" summary report
- Config auto-generation
- API endpoint for web-based onboarding

### 7. Analytics / Crash Reporting
- Optional, privacy-respecting telemetry module (`src/telemetry/`)
- Tracks: scan count, file count, feature usage, errors (no file names/paths)
- Sentry integration for crash reports (opt-in)
- Local analytics log for self-hosted usage stats
- Clear opt-in/opt-out in config + first-run

### 8. Cross-Platform Support
- Platform detection utility (`src/core/platform.py`)
- OS-specific default paths (macOS ~/Library, Windows %APPDATA%, Linux ~/.local)
- macOS: Spotlight integration hints, .app bundle config
- Windows: registry-based install, context menu integration config
- README update with per-platform instructions

### 9. Security / Privacy Messaging
- `PRIVACY.md` — detailed data handling policy (local-only, no cloud, no telemetry by default)
- `SECURITY.md` — vulnerability reporting, security model
- Privacy badge/banner in landing page and dashboard
- Config option to disable all network features

### 10. Branding
- Project identity: keep "Doc Intelligence" but add tagline "Your files, understood."
- ASCII art logo for CLI
- SVG logo for web (`docs/site/logo.svg`)
- Consistent color scheme definition
- Update README with new branding

## Implementation Order
1. Core infrastructure: FastAPI API, platform detection, licensing module
2. AI enhancements: PII, suggestions, image classification
3. Onboarding + first-run experience
4. Distribution: packaging, Makefile, installer
5. Landing page + branding + privacy/security docs
6. Analytics/telemetry (opt-in)
7. Tests for all new modules
