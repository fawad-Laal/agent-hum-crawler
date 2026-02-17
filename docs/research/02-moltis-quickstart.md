# Moltis Quickstart Notes (Project Copy)

Date: 2026-02-17
Source: user-provided quickstart content + Moltis docs

## 1. Install

Primary install command:

```bash
curl -fsSL https://www.moltis.org/install.sh | sh
```

Alternative (Homebrew):

```bash
brew install moltis-org/tap/moltis
```

Windows note for this machine:
- The shell installer URL is reachable, but `sh` is not available in current PowerShell.
- Run the install command in `Git Bash` or `WSL`.

## 2. Start

```bash
moltis
```

Expected output:
- `Moltis gateway starting...`
- `Open http://localhost:13131 in your browser`

## 3. Configure Provider

In Moltis: `Settings -> Providers`

Options:
- OpenAI Codex (OAuth): `Connect` and complete OAuth
- GitHub Copilot (OAuth): `Connect` and complete OAuth
- Local LLM (Offline): choose model and save

## 4. Chat

Example prompt:
- `Write a Python function to check if a number is prime`

## What to Enable Next

### Tool use
Tools are enabled by default with sandbox protection.

Example:
- `Create a hello.py file that prints "Hello, World!" and run it`

### Telegram
1. Create bot with `@BotFather`
2. Copy token
3. In Moltis: `Settings -> Telegram` and save token
4. Message your bot

### MCP servers
Add to `moltis.toml`:

```toml
[[mcp.servers]]
name = "github"
command = "npx"
args = ["-y", "@modelcontextprotocol/server-github"]
env = { GITHUB_TOKEN = "ghp_..." }
```

### Memory
Add to `moltis.toml`:

```toml
[memory]
enabled = true
```

Put markdown knowledge files in `~/.moltis/memory/`.

## Useful Commands

- `/new` start a new session
- `/model <name>` switch model
- `/clear` clear chat history
- `/help` show available commands

## File Locations

- `~/.config/moltis/moltis.toml` configuration
- `~/.config/moltis/provider_keys.json` API keys
- `~/.moltis/` data (sessions, memory, logs)

## Help Links

- Documentation: https://docs.moltis.org
- Issues: https://github.com/moltis-org/moltis/issues
- Discussions: https://github.com/moltis-org/moltis/discussions

## Immediate Project Checklist

1. Install Moltis from Git Bash/WSL
2. Run `moltis` and open `http://localhost:13131`
3. Connect one provider (Codex/Copilot/Local)
4. Run first chat and first tool-use task
5. Enable memory and add starter knowledge markdown files
6. Add first MCP server (GitHub)
