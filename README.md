# ProDR_Writer v2

Generate professional **Disaster Recovery technical proposals** as Microsoft Word documents, using a CrewAI multi-agent pipeline and any OpenAI-compatible LLM endpoint.

Built for international bidding: English-first output (Chinese optional), Western document conventions, standards-aligned content (ISO 22301 / ISO 27031 / NIST SP 800-34), and pluggable industry/regulatory profiles.

## Features

- **Staged agent pipeline** — BIA → current-state assessment → DR strategy → architecture → independent review loop (≤3 rounds) → document build. Every stage output is validated against a Pydantic schema; invalid LLM output is retried with the validation errors fed back.
- **Real review loop** — the optimizer's corrected architecture is fed into the next review round (not re-reviewed stale data).
- **Custom LLM support** — point it at any OpenAI-compatible endpoint (`base_url` + `api_key` + `model`): MiniMax, DeepSeek, OpenAI, Azure, Ollama, vLLM, …
- **Compliance profiles** — `generic-enterprise` (ISO 22301/27031) and `thailand-oic` (Thailand OIC + PDPA) built in; add your own YAML in `~/.prodr/profiles/`.
- **Rule engine wired in** — machine-checked RTO/RPO tier limits, system coverage, P0 strategy constraints; findings appear in the document's *Automated Validation Results* chapter instead of hardcoded "passed review" claims.
- **Professional Word formatting** — real TOC field, working page-number fields, Document Control page, captioned tables/figures, numbered chapters, data-driven charts, confidentiality notice.

## Installation

### One command, from nothing (recommended)

Downloads the source, creates a virtualenv, and installs — one command per OS:

Linux / macOS:

```bash
curl -fsSL https://raw.githubusercontent.com/ilysom0611/ProDR_Writer/main/install.sh | bash
```

Windows (PowerShell or cmd):

```bat
curl -fsSL https://raw.githubusercontent.com/ilysom0611/ProDR_Writer/main/install.bat -o install.bat && install.bat
```

The source lands in `./ProDR_Writer` (override with `PRODR_DEST=... bash install.sh`); everything else happens inside it.

### Inside an existing checkout

Four commands manage the whole lifecycle:

| Action | Linux / macOS | Windows |
|--------|---------------|---------|
| Install / reinstall | `./install.sh` | `install.bat` |
| Start (web UI on this host's LAN address) | `./start.sh` | `start.bat` |
| Stop | `./stop.sh` | `stop.bat` |
| Update (`git pull` + reinstall + restart) | `./update.sh` | `update.bat` |

### Manual

```bash
pip install -e .          # from a clone
prodr-writer --help       # or: python main.py
```

## Web UI

`start.sh` / `start.bat` (or `prodr-writer web`) opens a browser UI with three tabs:

- **Generate** — fill in project parameters, watch each pipeline stage complete live, then download the finished `.docx`. A **Try demo** button builds a full sample document with no API key.
- **Configuration** — set base URL / API key / model for any OpenAI-compatible endpoint, pick default language and profile, and test the connection without leaving the page.
- **History** — every past run with review score, validation findings, and one-click download.

By default the server binds to all interfaces and prints both URLs:

```
✔ Started (PID 12345)
  Local:   http://127.0.0.1:8000
  Network: http://192.168.1.10:8000   (access token: xK9…)
```

The LAN URL includes an auto-generated access token (persisted in `.web-token`, reused across restarts); opening it drops you straight in. Set `PRODR_WEB_TOKEN` yourself to control the token, or `PRODR_HOST=127.0.0.1 ./start.sh` for loopback-only access with no token.

> **Security note:** the Web UI can read/modify the stored LLM configuration and trigger generation that spends your API key. Any non-loopback bind therefore requires a bearer token (`PRODR_WEB_TOKEN`) on every `/api/*` route, and Host-header validation rejects DNS-rebinding origins. For exposure beyond a trusted LAN, put a reverse proxy with TLS + its own auth in front.

## Quick start

Requires Python 3.10+. Charts need matplotlib fonts available on the host (a CJK font is required for Chinese labels).

```bash
# 1. Configure your LLM endpoint once (saved to ~/.prodr/config.yaml)
prodr-writer config

# 2. Test connectivity
prodr-writer config --test

# 3. Generate a proposal
prodr-writer generate -p "Core Banking DR Program" \
    --client "Example Bank" --vendor "Acme Continuity" \
    --industry banking --rto "< 4 hours" --rpo "< 1 hour" \
    --budget "USD 250k-350k" --language en --profile generic-enterprise

# or fully interactive:
prodr-writer -i
```

Output lands in `outputs/<project>_<timestamp>/`: the `.docx`, every stage's validated JSON (`bia.json`, `strategy.json`, …), charts, and a `run.json` summary.

## Configuration

Precedence: CLI flags > environment variables (`PRODR_BASE_URL`, `PRODR_API_KEY`, `PRODR_MODEL`) > `~/.prodr/config.yaml`.

```yaml
llm:
  base_url: https://api.minimax.chat/v1
  api_key: sk-...
  model: MiniMax-M2.5        # provider prefix added automatically for custom endpoints
  temperature: 0.3
  request_timeout: 300
language: en                  # en | zh
profile: generic-enterprise   # or thailand-oic, or your own profile name
output_dir: outputs
```

Never commit API keys. Keys live in `~/.prodr/config.yaml` (created with restrictive permissions) or environment variables.

### Compliance profiles

A profile is YAML providing regulatory context injected into prompts, per-tier RTO/RPO limits enforced by the rule engine, review dimensions, and compliance-framework requirements rendered in Chapter 7. See `src/prodr_writer/profiles/*.yaml`; drop your own into `~/.prodr/profiles/<name>.yaml`.

## Exit codes

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Generation failed (LLM/pipeline error) |
| 2 | Configuration incomplete |
| 3 | Document generated but fatal validation findings remain |

## Development

```bash
pip install -e ".[dev]"
pytest
```

Tests cover JSON extraction, rule-engine parsing/checks, and full document assembly from fixture data — no API key needed.

## License

MIT
