# DM Suppression via AlwaysOnDM Toggle

## Summary

Repurpose the existing `AlwaysOnDM` toggle to control whether driver monitoring alerts and disengagements are active. When off, DM processes continue running but all events are suppressed.

## Behavior

- `AlwaysOnDM` ON: Driver monitoring works as today (alerts, disengagements, engagement blocks)
- `AlwaysOnDM` OFF: DM processes run but all events are suppressed — no alerts, no disengagements, no `DriverTooDistracted` engagement block

## Implementation Scope

### Modified: `selfdrive/monitoring/helpers.py`

When `always_on` is false:
- Skip adding all DM events (preDriverDistracted, promptDriverDistracted, driverDistracted, preDriverUnresponsive, promptDriverUnresponsive, driverUnresponsive, tooDistracted)
- Skip setting the `DriverTooDistracted` param

### Unchanged

- Process config — `dmonitoringd` and `dmonitoringmodeld` keep running regardless
- UI — existing `AlwaysOnDM` toggle in settings already controls the param

## What Stays Working When DM Is Off

- Driver camera view
- Face detection data (not acted upon)
- RHD detection

## What Gets Suppressed

- All distraction/unresponsive alerts (pre, prompt, terminal)
- All soft/immediate disables from DM
- `DriverTooDistracted` engagement block
