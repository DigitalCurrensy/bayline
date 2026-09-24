# Bayline — the fault message

Was this a real charger fault?

The charger talks to its management system. That system posts the fault here. Bayline does not open a connection to the charger.

| What arrived | What Bayline does |
| --- | --- |
| An alert that is still open | Keeps it and can open a repair job |
| A change to faulted that is still open | Keeps it |
| A fault that is already cleared | Drops it |
| A status update | Drops it |
| A stream of updates | Refuses it. That stream is not a fault |
| The old one-word status | Refuses it |

The repair job cannot be opened before the charger is locked. The same fault twice stays one record.

The update stream is how the management system sends repeated readings without waiting for a reply. Bayline must not turn one of those readings into a repair job.
