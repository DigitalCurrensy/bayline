# Bayline

Was this a real charger fault?

An alert, or a charger that has just gone to faulted, becomes a repair job. The charger is locked first. The job is not opened before the lock.

It takes the fault from the charger's own management system. It hands a repair-job id to Loadclear.

It refuses the old charger protocol, a stream of updates used as a fault, a fault that is already cleared, a status update, the same fault twice, and a job opened before the lock.

It does not open a connection to the charger, and it does not turn the charger back on.

Copyright 2026 DIGITAL CURRENSY INC / Module Kinetic Ltd. Apache-2.0. See [LICENSE](LICENSE).
Parent: [module-kinetic-ltd](https://github.com/DigitalCurrensy/module-kinetic-ltd)
