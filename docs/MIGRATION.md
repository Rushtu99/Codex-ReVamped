# Migration

Codex-ReVamped replaces the older `codex-portable-setup` naming.

New canonical runtime path:

- `~/.codex-revamped`

Legacy compatibility path:

- `~/.codex-portable-setup`

Compatibility behavior:

- wrappers and launchers look for `~/.codex-revamped/runtime.env` first
- if it is missing, they fall back to `~/.codex-portable-setup/runtime.env`
- account tooling continues to work with existing `~/.codex-lb` data

Recommended migration:

```sh
mv ~/.codex-portable-setup ~/.codex-revamped
cd ~/.codex-revamped
./install.sh
```

If you cannot move the directory yet, the compatibility fallback keeps the old path working until you reinstall.
