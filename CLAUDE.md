# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository Purpose

A collection of small self-hosted web apps deployed on a personal NUC server via NixOS. Apps are served at `https://app.nphilou.ch/<service>/` through nginx. There is no traditional package manager—all dependencies are managed declaratively via Nix.

## Architecture

Code changes in this repo trigger a GitHub Actions workflow (`deploy-nuc.yml`) on push to `main`. The workflow dispatches a deploy to the separate `nphilou/nixos-config` repo, which runs `nixos-rebuild` on the server, restarting affected systemd services. On success, a Telegram notification is sent using metadata from `.deploy/labs-notification.json`.

Each app has two parts:
- **App source**: `apps/<name>/` — Python (`app.py`) for Streamlit apps, `index.html` for static sites
- **NixOS config**: `nixos/apps/<name>.nix` — systemd service definition and nginx proxy location

## Deployment Notification Requirement

**Every change to a user-facing service must update `.deploy/labs-notification.json`** in the same commit. This file is read by CI to send the Telegram deploy summary:

```json
{
  "service": "apartment-tracker",
  "url": "https://app.nphilou.ch/apartment-tracker",
  "summary": "Short human-readable description of what changed."
}
```

If a change touches multiple services, set `service` to `"multiple"` and `url` to `"https://app.nphilou.ch/"`.

## Adding a New App

1. Create `apps/<name>/app.py` (Streamlit) or `apps/<name>/index.html` (static)
2. Assign a unique port in `nixos/ports.nix` — the NixOS module asserts uniqueness and `nixos-rebuild` will fail if a port is reused
3. Create `nixos/apps/<name>.nix` with a systemd service and nginx proxy location (follow existing app configs as templates)
4. Import the new `.nix` file in `nixos/module.nix`
5. If the app produces a build artifact, add a derivation to `flake.nix`
6. Update `.deploy/labs-notification.json`

## NixOS App Config Conventions

- Services use `DynamicUser = true` (no fixed UID)
- All services restart on failure with a 5-second delay (`Restart = "always"; RestartSec = 5`)
- Streamlit apps need WebSocket proxy headers in nginx; static sites use `python3 -m http.server`
- Ports are in the 9101–910x range, assigned in `nixos/ports.nix`

## Nix Build Commands

```bash
nix build .#hello              # Build hello static app
nix build .#liana              # Build liana static app
nix build .#send-deploy-email  # Build the email notification script
nix run .#send-deploy-email -- hello  # Send a deploy email for the 'hello' app
```

## Current Services

| Service            | Port | Type     | URL                                          |
|--------------------|------|----------|----------------------------------------------|
| `hello`            | 9101 | Static   | https://app.nphilou.ch/hello                 |
| `streamlit-basic`  | 9102 | Streamlit| https://app.nphilou.ch/streamlit-basic       |
| `buyvsrent`        | 9103 | Streamlit| https://app.nphilou.ch/buyvsrent             |
| `liana`            | 9104 | Static   | https://app.nphilou.ch/liana                 |
| `apartment-tracker`| 9105 | Streamlit| https://app.nphilou.ch/apartment-tracker     |

`buyvsrent` is unusual: its NixOS config (`nixos/apps/buyvsrent.nix`) git-clones an external repo (`ulupo/buyvsrent`) at service start rather than managing source locally.
