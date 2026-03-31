# Network Mode Toggle Design

## Summary

Add a tristate `NetworkMode` param (Default / Privacy / Offline) to control what external server communications are allowed. Reboot required to apply changes.

## Modes

- **Default (0):** Everything works as today
- **Privacy (1):** Functional connectivity (athena, registration, OTA, SSH) but no data leaves the device (no log uploads, crash reports, stats)
- **Offline (2):** All external connections killed except sunnylink (managed independently). User can temporarily bypass for OTA updates and backup/restore via explicit UI actions.

## Behavior Matrix

| Process/Feature | Default (0) | Privacy (1) | Offline (2) |
|---|---|---|---|
| Athena (comma.ai WebSocket) | On | On | Off |
| Comma uploader (logs/qlogs) | On | Off | Off |
| Sentry (crash reports) | On | Off | Off |
| Stats forwarding | On | Off | Off |
| Registration | On | On | Off |
| OTA updates (updated) | On | On | Off* |
| Backup/restore | On | On | Off* |
| Nav from phone (via athena) | On | On | Off |
| SSH tunnel (via athena) | On | On | Off |
| Sunnylink | Independent | Independent | Independent |

*Temporarily bypassable via explicit user action

## Implementation Scope

### New param
`NetworkMode` — integer, 0/1/2. Persists across reboots.

### Bypass params
- `NetworkBypassOTA` — set by "Check for Updates" button in Offline mode. Added to CLEAR_ON_MANAGER_START.
- `NetworkBypassBackup` — set by backup/restore UI action in Offline mode. Added to CLEAR_ON_MANAGER_START.

### Modified files

1. `common/params_keys.h` — Add NetworkMode, NetworkBypassOTA, NetworkBypassBackup param keys
2. `system/manager/process_config.py` — Add condition functions gating processes on NetworkMode:
   - uploader: off in Privacy + Offline
   - manage_athenad: off in Offline
   - statsd: off in Privacy + Offline
   - updated: off in Offline unless NetworkBypassOTA set
3. `system/sentry.py` — Check NetworkMode in init(), return False if Privacy or Offline
4. `selfdrive/ui/layouts/settings/device.py` — Add tristate toggle (Default / Privacy / Offline)
5. `system/loggerd/uploader.py` — Check NetworkMode before uploading (defense in depth)

### Unchanged
- Sunnylink stack (independent toggle)
- All onroad driving processes
- Local logging (still written to disk)

## Testing
- Unit tests for condition functions (given NetworkMode, assert correct process enable/disable)
- Unit test for sentry init() returning False in Privacy/Offline
- Verify bypass params work and clear on boot

## Error Handling
- Missing/corrupt NetworkMode defaults to 0 (Default) — fail-open
- Bypass params in CLEAR_ON_MANAGER_START so they reset every boot
