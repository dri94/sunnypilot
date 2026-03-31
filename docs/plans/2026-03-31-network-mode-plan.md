# Network Mode Toggle Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Add a tristate NetworkMode param (Default/Privacy/Offline) that controls which external server communications are allowed, with reboot required to apply.

**Architecture:** Add `NetworkMode` integer param (0=Default, 1=Privacy, 2=Offline) and two bypass boolean params. Gate processes in `process_config.py` using condition functions that read NetworkMode. Guard sentry init. Add a tristate selector in Device settings UI using the existing `MultiOptionDialog` pattern.

**Tech Stack:** Python, C++ (params_keys.h), cereal params system, sunnypilot UI widgets

---

### Task 1: Add param keys

**Files:**
- Modify: `common/params_keys.h`

**Step 1: Add NetworkMode param**

In `common/params_keys.h`, add these entries in alphabetical order within the existing keys map:

```cpp
{"NetworkBypassBackup", {CLEAR_ON_MANAGER_START, BOOL}},
{"NetworkBypassOTA", {CLEAR_ON_MANAGER_START, BOOL}},
{"NetworkMode", {PERSISTENT | BACKUP, INT, "0"}},
```

`NetworkBypassBackup` and `NetworkBypassOTA` go after the `Network` entries (around line 170). `NetworkMode` goes right after them. All `Network*` params should be adjacent. The bypass params use `CLEAR_ON_MANAGER_START` so they reset every boot. `NetworkMode` uses `PERSISTENT | BACKUP` with default `"0"` (Default mode).

**Step 2: Commit**

```bash
git add common/params_keys.h
git commit -m "feat: add NetworkMode, NetworkBypassOTA, NetworkBypassBackup param keys"
```

---

### Task 2: Write failing tests for process gating condition functions

**Files:**
- Create: `system/manager/test_network_mode.py`

**Step 1: Write the failing tests**

```python
import pytest
from unittest.mock import MagicMock

# Network mode constants (will be defined in process_config.py)
NETWORK_MODE_DEFAULT = 0
NETWORK_MODE_PRIVACY = 1
NETWORK_MODE_OFFLINE = 2


def make_params(network_mode=0, bypass_ota=False, bypass_backup=False):
    """Create a mock Params object that returns network mode values."""
    params = MagicMock()
    def get_side_effect(key, **kwargs):
        values = {
            "NetworkMode": network_mode,
        }
        return values.get(key)
    def get_bool_side_effect(key, **kwargs):
        values = {
            "NetworkBypassOTA": bypass_ota,
            "NetworkBypassBackup": bypass_backup,
        }
        return values.get(key, False)
    params.get = get_side_effect
    params.get_bool = get_bool_side_effect
    return params


class TestNetworkModeConditions:
    """Test the network mode condition functions from process_config."""

    def _import_conditions(self):
        from openpilot.system.manager.process_config import (
            not_privacy_mode, not_offline_mode, updated_with_bypass,
        )
        return not_privacy_mode, not_offline_mode, updated_with_bypass

    # --- not_privacy_mode (gates uploader, sentry, statsd) ---

    def test_uploader_allowed_in_default_mode(self):
        not_privacy_mode, _, _ = self._import_conditions()
        params = make_params(network_mode=NETWORK_MODE_DEFAULT)
        assert not_privacy_mode(True, params, MagicMock()) is True

    def test_uploader_blocked_in_privacy_mode(self):
        not_privacy_mode, _, _ = self._import_conditions()
        params = make_params(network_mode=NETWORK_MODE_PRIVACY)
        assert not_privacy_mode(True, params, MagicMock()) is False

    def test_uploader_blocked_in_offline_mode(self):
        not_privacy_mode, _, _ = self._import_conditions()
        params = make_params(network_mode=NETWORK_MODE_OFFLINE)
        assert not_privacy_mode(True, params, MagicMock()) is False

    # --- not_offline_mode (gates athenad) ---

    def test_athenad_allowed_in_default_mode(self):
        _, not_offline_mode, _ = self._import_conditions()
        params = make_params(network_mode=NETWORK_MODE_DEFAULT)
        assert not_offline_mode(True, params, MagicMock()) is True

    def test_athenad_allowed_in_privacy_mode(self):
        _, not_offline_mode, _ = self._import_conditions()
        params = make_params(network_mode=NETWORK_MODE_PRIVACY)
        assert not_offline_mode(True, params, MagicMock()) is True

    def test_athenad_blocked_in_offline_mode(self):
        _, not_offline_mode, _ = self._import_conditions()
        params = make_params(network_mode=NETWORK_MODE_OFFLINE)
        assert not_offline_mode(True, params, MagicMock()) is False

    # --- updated_with_bypass (gates OTA in offline, allows bypass) ---

    def test_updated_allowed_in_default_mode(self):
        _, _, updated_with_bypass = self._import_conditions()
        params = make_params(network_mode=NETWORK_MODE_DEFAULT)
        assert updated_with_bypass(False, params, MagicMock()) is True

    def test_updated_allowed_in_privacy_mode(self):
        _, _, updated_with_bypass = self._import_conditions()
        params = make_params(network_mode=NETWORK_MODE_PRIVACY)
        assert updated_with_bypass(False, params, MagicMock()) is True

    def test_updated_blocked_in_offline_mode(self):
        _, _, updated_with_bypass = self._import_conditions()
        params = make_params(network_mode=NETWORK_MODE_OFFLINE)
        assert updated_with_bypass(False, params, MagicMock()) is False

    def test_updated_bypass_in_offline_mode(self):
        _, _, updated_with_bypass = self._import_conditions()
        params = make_params(network_mode=NETWORK_MODE_OFFLINE, bypass_ota=True)
        assert updated_with_bypass(False, params, MagicMock()) is True
```

**Step 2: Run tests to verify they fail**

Run: `cd /Users/adevezin/Documents/GitHub/sunnypilot && python -m pytest system/manager/test_network_mode.py -v`
Expected: FAIL with ImportError (functions don't exist yet)

**Step 3: Commit**

```bash
git add system/manager/test_network_mode.py
git commit -m "test: add failing tests for network mode condition functions"
```

---

### Task 3: Implement network mode condition functions in process_config.py

**Files:**
- Modify: `system/manager/process_config.py:55-98`

**Step 1: Add constants and condition functions**

After the existing `use_copyparty` function (line 69) and before the `sunnylink_ready_shim` function (line 71), add:

```python
# Network mode constants
NETWORK_MODE_DEFAULT = 0
NETWORK_MODE_PRIVACY = 1
NETWORK_MODE_OFFLINE = 2

def _get_network_mode(params: Params) -> int:
  mode = params.get("NetworkMode")
  if mode is None:
    return NETWORK_MODE_DEFAULT
  return mode

def not_privacy_mode(started: bool, params: Params, CP: car.CarParams) -> bool:
  """Returns False in Privacy or Offline mode. Gates uploaders, sentry, stats."""
  return _get_network_mode(params) < NETWORK_MODE_PRIVACY

def not_offline_mode(started: bool, params: Params, CP: car.CarParams) -> bool:
  """Returns False in Offline mode. Gates athenad, registration."""
  return _get_network_mode(params) < NETWORK_MODE_OFFLINE

def updated_with_bypass(started: bool, params: Params, CP: car.CarParams) -> bool:
  """Gates OTA updates. Off in Offline unless NetworkBypassOTA is set."""
  mode = _get_network_mode(params)
  if mode < NETWORK_MODE_OFFLINE:
    return not started  # original only_offroad behavior
  return not started and params.get_bool("NetworkBypassOTA")
```

**Step 2: Update process entries to use the new conditions**

Change these lines in the `procs` list:

Line 107 — athenad daemon:
```python
DaemonProcess("manage_athenad", "system.athena.manage_athenad", "AthenadPid"),
```
becomes:
```python
DaemonProcess("manage_athenad", "system.athena.manage_athenad", "AthenadPid", enabled_fn=not_offline_mode),
```

Wait — `DaemonProcess` may not support `enabled_fn`. Let me check. If it doesn't, we wrap athenad in a conditional. Actually, looking at the pattern, `DaemonProcess` doesn't take a condition function the same way. Instead, we need to wrap it differently.

Alternative approach: Change athenad from `DaemonProcess` to gated differently. Looking at the codebase, `DaemonProcess` takes `(name, module, pid_param)` — no condition function. The simplest approach is to keep the daemon but have it check NetworkMode internally.

**Revised approach for athenad:** Instead of gating the DaemonProcess (which doesn't support conditions), we gate it by having `manage_athenad` check NetworkMode on startup. Read `system/athena/manage_athenad.py` to understand the entry point, then add a check.

For the uploader and statsd processes that DO take condition functions, update their entries:

Line 149 — uploader:
```python
PythonProcess("uploader", "system.loggerd.uploader", uploader_ready),
```
becomes:
```python
PythonProcess("uploader", "system.loggerd.uploader", and_(uploader_ready, not_privacy_mode)),
```

Line 150 — statsd:
```python
PythonProcess("statsd", "system.statsd", always_run),
```
becomes:
```python
PythonProcess("statsd", "system.statsd", and_(always_run, not_privacy_mode)),
```

Line 148 — updated:
```python
PythonProcess("updated", "system.updated.updated", only_offroad, enabled=not PC),
```
becomes:
```python
PythonProcess("updated", "system.updated.updated", updated_with_bypass, enabled=not PC),
```

**Step 3: Run tests**

Run: `cd /Users/adevezin/Documents/GitHub/sunnypilot && python -m pytest system/manager/test_network_mode.py -v`
Expected: ALL PASS

**Step 4: Commit**

```bash
git add system/manager/process_config.py
git commit -m "feat: add network mode condition functions and gate processes"
```

---

### Task 4: Gate athenad and sentry on NetworkMode

**Files:**
- Modify: `system/athena/manage_athenad.py`
- Modify: `system/sentry.py:117-143`

**Step 1: Read manage_athenad.py to understand its structure**

Read: `system/athena/manage_athenad.py`

**Step 2: Add NetworkMode check to manage_athenad**

At the start of the main loop or entry point, add:

```python
from openpilot.common.params import Params
from openpilot.system.manager.process_config import NETWORK_MODE_OFFLINE

params = Params()
mode = params.get("NetworkMode")
if mode is not None and mode >= NETWORK_MODE_OFFLINE:
    # In Offline mode, don't start athenad
    while True:
        time.sleep(60)
```

(Exact placement depends on the file structure — the implementer should read the file first.)

**Step 3: Add NetworkMode check to sentry init()**

In `system/sentry.py`, modify the `init()` function (line 117). At the top, before any sentry initialization:

```python
def init(project: SentryProject) -> bool:
  # Don't initialize sentry in Privacy or Offline mode
  params = Params()
  mode = params.get("NetworkMode")
  if mode is not None and mode >= 1:  # Privacy or Offline
    return False

  build_metadata = get_build_metadata()
  # ... rest unchanged
```

Note: `Params` is already imported at line 9.

**Step 4: Commit**

```bash
git add system/athena/manage_athenad.py system/sentry.py
git commit -m "feat: gate athenad and sentry on NetworkMode"
```

---

### Task 5: Add Network Mode selector to Device settings UI

**Files:**
- Modify: `selfdrive/ui/layouts/settings/device.py`

**Step 1: Add the Network Mode button**

In `device.py`, add a new button item in the `_initialize_items` method. Use the `MultiOptionDialog` pattern already used for language selection.

Add to the `DESCRIPTIONS` dict:
```python
'network_mode': tr_noop("Controls network connectivity to external servers. Default: all features enabled. Privacy: no data uploads or crash reports. Offline: all external connections disabled. Requires reboot to apply."),
```

Add a new button in the items list (after the language change button, before the power off button):
```python
button_item(lambda: tr("Network Mode"), lambda: self._network_mode_label(),
            lambda: tr(DESCRIPTIONS['network_mode']),
            callback=self._show_network_mode_dialog),
```

Add helper methods:
```python
_NETWORK_MODE_OPTIONS = ["Default", "Privacy", "Offline"]

def _network_mode_label(self):
    mode = self._params.get("NetworkMode")
    if mode is None:
        mode = 0
    return tr(self._NETWORK_MODE_OPTIONS[mode])

def _show_network_mode_dialog(self):
    current_mode = self._params.get("NetworkMode")
    if current_mode is None:
        current_mode = 0

    def handle_selection(result: DialogResult):
        if result == DialogResult.CONFIRM and self._network_mode_dialog:
            selected = self._network_mode_dialog.selection
            self._params.put("NetworkMode", selected)
        self._network_mode_dialog = None

    self._network_mode_dialog = MultiOptionDialog(
        tr("Select Network Mode"),
        [tr(opt) for opt in self._NETWORK_MODE_OPTIONS],
        current_mode,
        callback=handle_selection,
    )
    gui_app.push_widget(self._network_mode_dialog)
```

Add `self._network_mode_dialog: MultiOptionDialog | None = None` to `__init__`.

**Step 2: Commit**

```bash
git add selfdrive/ui/layouts/settings/device.py
git commit -m "feat: add Network Mode selector to Device settings"
```

---

### Task 6: Add defense-in-depth check to uploader

**Files:**
- Modify: `system/loggerd/uploader.py`

**Step 1: Add NetworkMode guard**

In `system/loggerd/uploader.py`, find the main upload loop. Add a check that skips uploading if NetworkMode >= 1 (Privacy or Offline). This is defense-in-depth — the process shouldn't even be running in those modes, but this prevents uploads if somehow it is.

Find the main loop and add at the top of each iteration:

```python
mode = self.params.get("NetworkMode")
if mode is not None and mode >= 1:
    time.sleep(5)
    continue
```

(Exact placement depends on the upload loop structure — implementer should read the file.)

**Step 2: Commit**

```bash
git add system/loggerd/uploader.py
git commit -m "feat: add NetworkMode defense-in-depth check to uploader"
```

---

### Task 7: Add bypass button wiring for OTA and Backup in Offline mode

**Files:**
- Modify: `selfdrive/ui/layouts/settings/software.py` (for OTA bypass)
- Modify: UI file for backup trigger (implementer: find where backup is triggered in `sunnypilot/sunnylink/backups/` UI code)

**Step 1: Read software.py to find the "Check for Updates" button**

Read: `selfdrive/ui/layouts/settings/software.py`

**Step 2: Add NetworkBypassOTA logic**

When the user presses "Check for Updates" and NetworkMode is Offline, set `NetworkBypassOTA` to true before triggering the update check. The param will be cleared on next boot via `CLEAR_ON_MANAGER_START`.

```python
# In the check-for-updates callback:
mode = self._params.get("NetworkMode")
if mode is not None and mode >= 2:  # Offline mode
    self._params.put_bool("NetworkBypassOTA", True)
```

**Step 3: Find and modify backup trigger**

Search for where backup is initiated in the UI and add similar `NetworkBypassBackup` logic.

**Step 4: Commit**

```bash
git add selfdrive/ui/layouts/settings/software.py <backup-ui-file>
git commit -m "feat: add NetworkBypassOTA and NetworkBypassBackup wiring"
```

---

### Task 8: Final integration test and commit

**Step 1: Run all tests**

Run: `cd /Users/adevezin/Documents/GitHub/sunnypilot && python -m pytest system/manager/test_network_mode.py -v`
Expected: ALL PASS

**Step 2: Verify syntax of all modified files**

```bash
python3 -c "
import ast
files = [
    'system/manager/process_config.py',
    'system/sentry.py',
    'selfdrive/ui/layouts/settings/device.py',
    'system/loggerd/uploader.py',
]
for f in files:
    ast.parse(open(f).read())
    print(f'{f}: OK')
"
```

**Step 3: Final commit if any remaining changes**

```bash
git add -A
git commit -m "feat: network mode toggle complete"
```
