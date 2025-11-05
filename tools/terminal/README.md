# AWARE Terminal Experience

Boot once, come back to the exact workspace every time. AWARE Terminal stitches together tmux, GNOME, and AI providers so threads in Studio or aware-cli reopen with all panes running—no manual tab herding.

## Everyday Flow

1. **One-time bootstrap**  
   `uv run aware-terminal setup --auto` installs tmux + plugins, enables the user systemd service, and applies the GNOME Auto Move Windows rules. If providers (Codex, Claude, Gemini) are available, setup auto-installs them too—doctor shows confirmations and remediation hints. Prefer to approve provider installs manually? Append `--provider-policy skip` and the guided flow will prompt before updating each agent.

   Provider manifests refresh automatically when you run setup from the repo. In packaged builds we reuse the bundled manifest data; a banner will tell you whether a refresh happened or if the bundled versions are in use.
   Provider prompts highlight installed vs latest versions (`codex-cli 0.48.0 → 0.49.0`) with release notes so you can upgrade confidently.

2. **Thread-scoped terminals**  
   `aware-cli object call --type terminal --function create --id <thread> ...` spins up a tmux window tied to a thread. Descriptors land in `.aware/threads/<thread>/terminals/<id>.json`, so Studio or Control Center can render panels instantly, and `terminal attach` reopens the shell without re-running commands.

3. **Daemons that persist**  
   Terminal sessions survive reboots: the tmux service starts on login, `aware_terminal.runtime` restores panes, and Studio/CLI poll the manifest to reconnect. Providers launch in the same window, so agent runs (Codex/Claude/Gemini) share the thread history.

4. **Control Center (optional)**  
   `uv run aware-terminal control` opens the TUI overlay for live streaming; it reads the same manifests as Studio, so actions stay in sync. We’re refining this view to match the new lifecycle (thread → terminal → optional provider).

## Why it matters

- **Zero setup drift**: once auto-configured, every terminal reappears on the right workspace with the same panes; no manual tmux scripts or window moves.
- **Provider-ready**: AI launchers inherit thread context—`ensure_provider_session` plugs Codex, Claude, or Gemini into the same tmux session used for human work.
- **CLI ↔ Studio parity**: descriptors + pane manifests give both aware-cli and Studio the same contract, letting us bundle a consistent open-source experience (aware-cli + aware-terminal + providers + rules/release helpers).

Looking ahead: provider binding (`terminal bind-provider`) and Control Center updates will round out the Studio integration. For install specifics and release bundling guidance, see `tools/terminal/RELEASE.md`.
