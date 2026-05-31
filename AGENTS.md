# Codex Instructions

## Labs Deploy Notification

When adding or changing a user-facing labs service, update `.deploy/labs-notification.json` in the same change.

The file is used by CI/deploy automation to send the user a deploy summary message. Keep it valid JSON and set:

- `service`: the service slug used in the public URL, for example `hello` or `streamlit-basic`.
- `url`: the public service URL, for example `https://app.nphilou.ch/hello`.
- `summary`: a short, human-readable summary of what changed.

If a change affects multiple services, set `service` to `multiple`, set `url` to `https://app.nphilou.ch/`, and summarize the affected services.

