# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 1.0.x   | Yes                |
| < 1.0   | No                 |

## Reporting a Vulnerability

If you discover a security vulnerability in Chronometry, please report it responsibly.

**Do not open a public issue for security vulnerabilities.**

Instead, please email: **security@chronometry.dev** (or open a private security advisory on GitHub).

### What to Include

- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

### Response Timeline

- **Acknowledgment** — Within 48 hours
- **Initial assessment** — Within 1 week
- **Fix timeline** — Depends on severity; critical issues targeted within 2 weeks

## Security Design

Chronometry is designed with privacy and security as core principles:

- **Local only** — All data (screenshots, annotations, digests) stays on your machine in `~/.chronometry/`.
- **No telemetry** — No data is sent to external servers. LLM inference runs locally via Ollama.
- **Localhost binding** — The web server binds to `127.0.0.1` by default, not accessible from the network.
- **CORS restricted** — API only accepts requests from `localhost:8051` and `127.0.0.1:8051`.
- **Path traversal protection** — File-serving endpoints validate paths against the data directory.
- **Input validation** — All API parameters are validated (date formats, day ranges, timestamps).
- **Secret key generation** — A unique Flask secret key is generated per installation via `secrets.token_hex(32)`.
- **No credentials stored** — Chronometry does not store any passwords, API keys, or tokens.

## Scope

The following are in scope for security reports:

- Path traversal or file access outside `~/.chronometry/`
- Command injection via AppleScript or subprocess calls
- Cross-site scripting (XSS) in the web dashboard
- Information disclosure through API endpoints
- Denial of service through resource exhaustion
- Privilege escalation via launchd service configuration

The following are out of scope:

- Vulnerabilities in third-party dependencies (report upstream)
- Issues requiring physical access to the machine
- Social engineering attacks
- Screenshot content privacy (this is the intended functionality)
