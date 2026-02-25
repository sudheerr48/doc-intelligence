# Security Policy — Doc Intelligence

## Security Model

Doc Intelligence is a local-first application. The security model is straightforward:

1. **No network access by default** — the core tool runs entirely offline
2. **No remote servers** — no data exfiltration surface
3. **Read-only by default** — scanning only reads file metadata; no files are modified
4. **Explicit deletion** — files are only moved/deleted through the staging workflow with confirmation

## Optional Network Features

These features make outbound API calls and require explicit configuration:

| Feature | Destination | Required Config |
|---------|------------|-----------------|
| AI Tagging | Anthropic API or OpenAI API | API key in environment |
| Embeddings | Voyage AI or OpenAI API | API key in environment |
| NL Queries | Anthropic API or OpenAI API | API key in environment |
| Sentry (opt-in) | Sentry.io | DSN in config |

**To disable all network features:**
```yaml
# config/config.yaml
ai:
  provider: "none"
```

## API Key Security

- API keys are read from environment variables, **never** stored in config files
- Use a `.env` file (gitignored) for local development
- Keys are passed directly to provider SDKs and never logged

## SQL Injection Protection

The `run_query()` method only allows `SELECT` statements and blocks dangerous keywords (`DROP`, `DELETE`, `INSERT`, `UPDATE`, `ALTER`, `CREATE`, `TRUNCATE`).

## File System Safety

- The scanner only reads files — it never modifies them
- Duplicate cleanup uses a two-stage process: stage first, then confirm deletion
- Staged files are moved (not deleted) to a review folder
- Permanent deletion requires explicit `--confirm` flag

## Supported Versions

| Version | Supported |
|---------|-----------|
| 5.x     | Yes       |
| < 5.0   | No        |

## Reporting Vulnerabilities

If you discover a security vulnerability:

1. **Do NOT** open a public issue
2. Email: security@doc-intelligence.dev (or open a private GitHub security advisory)
3. Include: description, reproduction steps, and potential impact
4. We aim to respond within 48 hours

## Responsible Disclosure

We follow responsible disclosure practices:
- Acknowledgment within 48 hours
- Fix timeline: 7 days for critical, 30 days for moderate
- Credit given to reporters (unless anonymity is preferred)
