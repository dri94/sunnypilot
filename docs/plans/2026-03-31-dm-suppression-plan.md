# DM Suppression via AlwaysOnDM Toggle — Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Suppress all driver monitoring alerts and disengagements when the `AlwaysOnDM` toggle is off, while keeping DM processes running.

**Architecture:** Add an early return in `_update_events()` when `always_on` is false, so no events are emitted and no `DriverTooDistracted` param is set. The `_update_states()` call continues normally so face detection, pose calibration, and RHD detection remain functional.

**Tech Stack:** Python, cereal messaging, pytest

---

### Task 1: Write failing test — DM off suppresses events for distracted driver

**Files:**
- Modify: `selfdrive/monitoring/test_monitoring.py`

**Step 1: Write the failing test**

Add this test to the `TestMonitoring` class:

```python
# DM off (always_on=False), engaged, always distracted
#  - should produce no events when DM is disabled
def test_dm_off_suppresses_distracted_events(self):
    DM = DriverMonitoring(always_on=False)
    events = []
    for idx in range(len(always_distracted)):
        DM._update_states(always_distracted[idx], [0, 0, 0], 0, always_true[idx], always_false[idx])
        DM._update_events(always_false[idx], always_true[idx], always_false[idx], 0, 0)
        events.append(DM.current_events)
    self._assert_no_events(events)
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/adevezin/Documents/GitHub/sunnypilot && python -m pytest selfdrive/monitoring/test_monitoring.py::TestMonitoring::test_dm_off_suppresses_distracted_events -v`
Expected: FAIL — events will still be generated because suppression is not yet implemented

---

### Task 2: Write failing test — DM off suppresses events for invisible driver

**Files:**
- Modify: `selfdrive/monitoring/test_monitoring.py`

**Step 1: Write the failing test**

Add this test to the `TestMonitoring` class:

```python
# DM off (always_on=False), engaged, no face detected
#  - should produce no events when DM is disabled
def test_dm_off_suppresses_invisible_events(self):
    DM = DriverMonitoring(always_on=False)
    events = []
    for idx in range(len(always_no_face)):
        DM._update_states(always_no_face[idx], [0, 0, 0], 0, always_true[idx], always_false[idx])
        DM._update_events(always_false[idx], always_true[idx], always_false[idx], 0, 0)
        events.append(DM.current_events)
    self._assert_no_events(events)
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/adevezin/Documents/GitHub/sunnypilot && python -m pytest selfdrive/monitoring/test_monitoring.py::TestMonitoring::test_dm_off_suppresses_invisible_events -v`
Expected: FAIL

---

### Task 3: Write failing test — DM off prevents DriverTooDistracted engagement block

**Files:**
- Modify: `selfdrive/monitoring/test_monitoring.py`

**Step 1: Write the failing test**

Add this test to the `TestMonitoring` class:

```python
# DM off (always_on=False), engaged, distracted past terminal threshold
#  - should never set too_distracted flag
def test_dm_off_no_engagement_block(self):
    DM = DriverMonitoring(always_on=False)
    for idx in range(len(always_distracted)):
        DM._update_states(always_distracted[idx], [0, 0, 0], 0, always_true[idx], always_false[idx])
        DM._update_events(always_false[idx], always_true[idx], always_false[idx], 0, 0)
    assert not DM.too_distracted
```

**Step 2: Run test to verify it fails**

Run: `cd /Users/adevezin/Documents/GitHub/sunnypilot && python -m pytest selfdrive/monitoring/test_monitoring.py::TestMonitoring::test_dm_off_no_engagement_block -v`
Expected: FAIL

---

### Task 4: Write failing test — DM on still produces events (regression guard)

**Files:**
- Modify: `selfdrive/monitoring/test_monitoring.py`

**Step 1: Write the failing test**

Add this test to the `TestMonitoring` class:

```python
# DM on (always_on=True), engaged, always distracted
#  - should still produce distraction events as before
def test_dm_on_still_produces_events(self):
    DM = DriverMonitoring(always_on=True)
    events = []
    for idx in range(len(always_distracted)):
        DM._update_states(always_distracted[idx], [0, 0, 0], 0, always_true[idx], always_false[idx])
        DM._update_events(always_false[idx], always_true[idx], always_false[idx], 0, 0)
        events.append(DM.current_events)
    has_events = any(len(e) > 0 for e in events)
    assert has_events, "DM on should produce distraction events"
```

**Step 2: Run test to verify it passes**

Run: `cd /Users/adevezin/Documents/GitHub/sunnypilot && python -m pytest selfdrive/monitoring/test_monitoring.py::TestMonitoring::test_dm_on_still_produces_events -v`
Expected: PASS (this is a regression guard, should pass even before implementation)

---

### Task 5: Implement DM suppression

**Files:**
- Modify: `selfdrive/monitoring/helpers.py:326` (the `_update_events` method)

**Step 1: Add early return when always_on is false**

At the top of `_update_events`, after `self._reset_events()` (line 327), add:

```python
def _update_events(self, driver_engaged, op_engaged, standstill, wrong_gear, car_speed):
    self._reset_events()

    # When DM is disabled (AlwaysOnDM off), suppress all events
    if not self.always_on:
      return

    # Block engaging until ignition cycle after max number or time of distractions
    ...  # rest of method unchanged
```

**Step 2: Run all tests to verify they pass**

Run: `cd /Users/adevezin/Documents/GitHub/sunnypilot && python -m pytest selfdrive/monitoring/test_monitoring.py -v`
Expected: ALL PASS

---

### Task 6: Commit

**Step 1: Commit tests and implementation**

```bash
git add selfdrive/monitoring/helpers.py selfdrive/monitoring/test_monitoring.py
git commit -m "feat: suppress DM alerts when AlwaysOnDM is off

When AlwaysOnDM toggle is disabled, all driver monitoring events
(distraction alerts, unresponsive alerts, engagement blocks) are
suppressed. DM processes continue running for face detection and
RHD calibration."
```
