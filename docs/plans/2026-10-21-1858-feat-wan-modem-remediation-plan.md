---
title: WAN modem PDU remediation
date: 2026-10-21
type: feat
topic: wan-modem-remediation
artifact_contract: ce-unified-plan/v1
product_contract_source: ce-brainstorm
execution: code
status: requirements-only
---

## Goal Capsule

**Objective:** When internet is sustained-down, automatically power-cycle the ISP modem/ONT on the UniFi PDU with enough confirmation and a hard attempt budget that saturation no longer causes repeated daily outages.

**Means:** Composite VictoriaMetrics alert → Alertmanager (gap + inhibit circuit breaker) → Fission HTTPTrigger → function that only power-cycles the modem outlet; after three unsuccessful cycles, a budget-exhausted alert inhibits further remediation until WAN recovers.

**Product authority:** This plan. Surrounding monitoring polish (extra dashboards, Gatus tweaks) is not active scope.

**Open blockers:** None.

## Product Contract

### Summary

Replace UniFi’s built-in “internet down → outlet” behavior with alert-stack-owned remediation policy and a thin Fission executor: dual-signal sustained WAN-down detection, a 10-minute minimum gap between cycles, and a circuit breaker that stops after three cycles by inhibiting via a synthetic alert visible in Alertmanager/Karma. The Fission function does not decide whether to remediate—it only runs the UniFi PDU power-cycle when Alertmanager invokes it.

### Problem Frame

UniFi’s outlet power-cycle thresholds treat brief WAN saturation as outages and reboot the modem repeatedly. The UDM and LAN stay up during those events; the needed behavior is a longer sustain window, an external confirmation signal, and a hard stop after a few failed self-heals—not a more sensitive controller feature. A custom webhook-to-Job shim would reimplement what Fission’s HTTPTrigger already provides in this cluster.

### Key Decisions

- **Remediate the ISP modem/ONT outlet, not the UDM Pro** — LAN and the UniFi API remain reachable during the cycle. `(session-settled: user-directed — chosen over UDM reboot: keep controller reachable)` — Governs R1, R8.
- **Alertmanager owns policy; Fission owns execution only** — AM delivers via webhook to an existing-style Fission `HTTPTrigger`; no custom shim and no one-shot Job. `(session-settled: user-directed — chosen over webhook-shim→Job: avoid rewriting Fission)` — Governs R6, R7, R10.
- **Composite alert owns “should remediate”** — UniFi WAN down and at least one external probe failing for a continuous 5m. `(session-settled: user-approved — chosen over UniFi-only or executor-side AND: fewer false cycles)` — Governs R2, R3.
- **Circuit breaker via inhibit + budget-exhausted alert in the alert stack** — gap via AM route timing; stop-after-N via inhibit. Function does not implement backoff/breaker branching. `(session-settled: user-directed — chosen over executor-side exponential backoff or Job-private state: keep policy in AM)` — Governs R4, R5, R9.
- **Trip after 3 cycles; ≥10m between cycles while closed** — `(session-settled: user-directed — chosen over 2/5 attempts and 15/30m gaps)` — Governs R4, R5.

### Actors

- **Operator** — receives Pushover for WAN-down and budget-exhausted; may clear or investigate when the breaker opens.
- **VictoriaMetrics / vmalert** — evaluates sustained dual-signal condition and budget-exhausted from cycle evidence.
- **Alertmanager** — human notify; remediation webhook route; `repeat_interval` / grouping for the 10m gap; inhibits remediation when budget-exhausted fires.
- **Fission router + HTTPTrigger** — receives the AM webhook (same pattern as `ics-proxy`).
- **Remediation function** — executes the UniFi PDU modem-outlet power-cycle only when invoked.
- **UniFi UDM Pro + PDU** — source of WAN status (via existing unpoller scrape) and outlet control target.

### Key Flows

**F1. Successful self-heal**

1. UniFi reports WAN down and an external probe fails continuously for 5m → composite alert fires.
2. Alertmanager notifies Pushover and, with breaker closed and gap elapsed, POSTs to the Fission HTTPTrigger.
3. Function power-cycles the modem outlet (execution only) and leaves a cycle signal the metrics stack can count.
4. WAN recovers → composite alert resolves; budget-exhausted (if any) clears; attempt budget resets.

**F2. Breaker trips**

1. Same as F1 for three cycles with WAN still down, spaced by AM’s ≥10m remediation cadence.
2. After the third unsuccessful cycle, budget-exhausted alert fires in the alert stack.
3. Inhibit rule suppresses the remediation webhook route; Pushover still surfaces budget-exhausted / WAN-down as configured.
4. No further PDU cycles until WAN recovers and state resets (per R5).

**F3. Policy blocks invocation**

1. Composite condition is still true, but AM does not deliver to the remediation webhook (inside `repeat_interval`, or inhibited by budget-exhausted).
2. Function is not invoked; no outlet action.

### Requirements

**Detection**

- R1. The remediator power-cycles only the ISP modem/ONT PDU outlet, never the UDM Pro.
- R2. Remediation is eligible only when UniFi WAN status indicates down **and** at least one configured external probe is failing, both sustained for a continuous **5 minutes**.
- R3. Eligibility is expressed as a single composite alert (or equivalent recording-rule + alert) so Alertmanager only invokes remediation when both signals agree.

**Circuit breaker (Alertmanager / metrics)**

- R4. While the breaker is closed, Alertmanager does not invoke the remediation webhook more often than once per **10 minutes** for the same outage (route `repeat_interval` / grouping).
- R5. After **3** remediation cycles in one outage without WAN recovery, the alert stack fires a budget-exhausted alert that **inhibits** further remediation webhooks until WAN recovers, at which point the budget resets.
- R9. Budget-exhausted (and thus “why we stopped”) is visible in Alertmanager/Karma via the inhibit source alert.

**Action path (Fission)**

- R6. Alertmanager delivers remediation via webhook to a Fission **HTTPTrigger** (cluster-internal), not a custom Job-creating shim.
- R7. The Fission function’s responsibility is the UniFi API outlet power-cycle when invoked; it must not implement dual-signal checks, gap logic, or breaker open/closed branching.
- R8. During a cycle, the UDM and cluster remain the control plane (modem is the disrupted device).
- R10. Fission executor/environment retries (cold-start, failed invocation) are not used as remediation spacing or attempt budget; those are owned by R4 and R5.

**Notify**

- R11. Human notification (existing Pushover path) remains for WAN-down and budget-exhausted; the remediation webhook route is action-only and must not replace operator paging.

### Acceptance Examples

- AE1. When UniFi WAN flaps during saturation but external probes stay up, the composite alert does not fire and the function is not invoked. Covers R2, R3.
- AE2. When both signals are down for 5 continuous minutes and the breaker is closed with ≥10m since the last remediation notify, AM invokes Fission once and the modem outlet is power-cycled. Covers R2–R4, R6–R8.
- AE3. When the composite alert remains firing 5m after a cycle, AM does not re-invoke the function (gap). Covers R4, F3.
- AE4. When three cycles have run in one outage without WAN recovery, budget-exhausted fires, inhibit stops further remediation webhooks, and Pushover still informs the operator. Covers R5, R9, R11, F2.
- AE5. When WAN recovers after a tripped breaker, budget resets and a later sustained dual-signal outage can remediate again from attempt zero. Covers R5, F1.
- AE6. When AM is inhibited, a manual or stray call is out of band; under normal AM→Fission flow the function never decides to no-op for policy reasons. Covers R7.

### Success Criteria

- Sustained true WAN loss results in at most three modem power-cycles before human intervention is required.
- Saturation / brief UniFi WAN flaps without external probe failure do not cause modem cycles.
- An operator can see in Alertmanager/Karma whether remediation is active or budget-inhibited without reading Fission logs first.
- No new long-lived “Job factory” service is introduced; remediation execution reuses Fission.

### Scope Boundaries

**In scope:** Detection wiring (metrics/alerts), Alertmanager route + `repeat_interval` + inhibit, Fission HTTPTrigger + function for UniFi PDU cycle, cycle evidence for the budget alert, Pushover coexistence.

**Out of scope:** Custom webhook→Job shim; power-cycling the UDM; Robusta/Keep/StackStorm; Home Assistant as remediator; exponential remediation backoff in Fission executors/environments; changing UniFi’s built-in outlet feature beyond disabling/replacing its use for this outlet; general blackbox estate redesign; putting policy (AND, gap, breaker) inside the function.

### Dependencies / Assumptions

- UniFi WAN state is available (or can be made available) via existing unpoller → VictoriaMetrics scrapes on ~2m cadence; planning confirms the exact metric/labels.
- Cluster can reach `https://unifi` on LAN while the modem is down or rebooting.
- A dedicated UniFi credential (or reuse of an existing secret pattern) can call the outlet power-cycle API.
- External probe target(s) for the dual-signal exist or will be added as part of planning.
- Fission router is reachable in-cluster as an Alertmanager webhook URL (same platform as `kubernetes/apps/fission/functions/ics-proxy/`).
- Cycle evidence for R5 can be derived without putting breaker branching in the function (e.g. a cycle counter/metric emitted as a side effect of successful execution, then a VMRule)—exact mechanism is planning’s choice.

### Outstanding Questions

**Deferred to Planning**

- Exact unpoller metric/label for WAN down and PromQL for the composite alert.
- External probe module/targets and how they join the composite expression.
- UniFi API shape and PDU outlet identifier for the modem.
- How cycle count becomes the budget-exhausted alert while keeping R7 (execution-only function)—e.g. metric + recording/alert rule vs other AM-visible signal.
- AM route `group_*` / `repeat_interval` tuning and webhook auth to the Fission trigger.
- Whether the HTTPTrigger is cluster-only (Service URL) or also exposed via Gateway like `ics-proxy` (prefer cluster-only for AM).

### Sources / Research

- Existing Alertmanager receivers already use webhooks (buddy heartbeat) and Pushover: `kubernetes/apps/observability/victoria-metrics/app/vmalertmanagerconfig.yaml`.
- Unpoller scrapes UniFi including PDU-related metrics on a 2m interval: `kubernetes/apps/observability/unpoller/app/helmrelease.yaml`.
- Blackbox/`VMProbe` patterns exist for ICMP/HTTP probes: `kubernetes/apps/observability/blackbox-exporter/`.
- Fission HTTPTrigger + python-fastapi environment pattern: `kubernetes/apps/fission/functions/ics-proxy/`.
- Fission executors/MQ `maxRetries` address failed invocation / infra retries, not remediation attempt budgets; this cluster has `mqt_keda.enabled: false` on the Fission HelmRelease.
