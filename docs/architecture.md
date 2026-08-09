# Architecture

Closed-loop read-only advisor: Chromium passive capture -> C++ protocol adapter/state store -> legal actions/simulator/models -> stochastic search -> recommendation -> human move -> observed state -> replan. Python owns corpus/training; TypeScript owns the browser bridge.
