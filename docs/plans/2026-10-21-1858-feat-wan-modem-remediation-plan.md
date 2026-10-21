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

**Means:** Composite VictoriaMetrics alert → Alertmanager webhook → one-shot Job that cycles the modem outlet; after three unsuccessful cycles, a budget-exhausted alert inhibits further remediation until WAN recovers.

**Product authority:** This plan. Surrounding monitoring polish (extra dashboards, Gatus tweaks) is not active scope.

**Open blockers:** None.

## Product Contract

### Summary

Replace UniFi’s built-in “internet down → outlet” behavior with a cluster-owned remediator: dual-signal sustained WAN-down detection, a 10-minute minimum gap between cycles, and a circuit breaker that stops after three cycles by inhibiting via a synthetic alert visible in Alertmanager/Karma.

### Problem Frame

UniFi’s outlet power-cycle thresholds treat brief WAN saturation as outages and reboot the modem repeatedly. The UDM and LAN stay up during those events; the needed behavior is a longer sustain window, an external confirmation signal, and a hard stop after a few failed self-heals—not a more sensitive controller feature.

### Key Decisions

- **Remediate the ISP modem/ONT outlet, not the UDM Pro** — LAN and the UniFi API remain reachable during the cycle. `(session-settled: user-directed — chosen over UDM reboot: keep controller reachable)` — Governs R1, R8.
- **Alert-driven detection with in-cluster one-shot Jobs** — Alertmanager delivers; a thin webhook creates a Job per remediation attempt. `(session-settled: user-directed — chosen over always-on Deployment or Fission-only: auditable one-shot Jobs)` — Governs R6, R7.
- **Composite alert owns “should remediate”** — UniFi WAN down and at least one external probe failing for a continuous 5m, not Job-side AND alone. `(session-settled: user-approved — chosen over UniFi-only or Job-as-AND-gate: fewer false cycles / fewer noop Jobs)` — Governs R2, R3.
- **Circuit breaker via inhibit + budget-exhausted alert** — not AM `repeat_interval` alone and not exponential remediation backoff. `(session-settled: user-directed — chosen over AM-native timing or exponential Job delays: AM cannot express breaker math; inhibit is visible)` — Governs R4, R5, R9.
- **Trip after 3 cycles; ≥10m between cycles while closed** — Job-native backoff only retries a failed pod inside one Job. `(session-settled: user-directed — chosen over 2/5 attempts and 15/30m gaps)` — Governs R4, R5, R10.

### Actors

- **Operator** — receives Pushover for WAN-down and budget-exhausted; may clear or investigate when the breaker opens.
- **VictoriaMetrics / vmalert** — evaluates sustained dual-signal condition.
- **Alertmanager** — routes remediation webhook; inhibits remediation when budget-exhausted fires; continues human notify.
- **Webhook shim** — authenticates AM calls and creates the remediation Job.
- **Remediation Job** — enforces gap/budget, cycles the PDU outlet via UniFi API, updates breaker state / budget alert.
- **UniFi UDM Pro + PDU** — source of WAN status (via existing unpoller scrape) and outlet control target.

### Key Flows

**F1. Successful self-heal**

1. UniFi reports WAN down and an external probe fails continuously for 5m → composite alert fires.
2. Alertmanager notifies Pushover and posts to the remediation webhook (breaker closed).
3. Shim creates a Job; Job confirms still eligible (≥10m since last cycle, attempts &lt; 3), power-cycles the modem outlet, records attempt.
4. WAN recovers → composite alert resolves; attempt counter resets; budget-exhausted (if any) clears.

**F2. Breaker trips**

1. Same as F1 through three cycles with WAN still down and ≥10m between cycles.
2. After the third unsuccessful cycle, budget-exhausted alert fires.
3. Inhibit rule suppresses the remediation webhook route; Pushover still surfaces budget-exhausted / WAN-down as configured.
4. No further PDU cycles until WAN recovers and state resets (per R5).

**F3. Ineligible fire**

1. Composite alert fires but Job finds open breaker, or last cycle &lt; 10m ago.
2. Job exits without cycling (no outlet action).

### Requirements

**Detection**

- R1. The remediator power-cycles only the ISP modem/ONT PDU outlet, never the UDM Pro.
- R2. Remediation is eligible only when UniFi WAN status indicates down **and** at least one configured external probe is failing, both sustained for a continuous **5 minutes**.
- R3. Eligibility is expressed as a single composite alert (or equivalent recording-rule + alert) so Alertmanager only invokes remediation when both signals agree.

**Circuit breaker**

- R4. While the breaker is closed, consecutive remediation cycles for the same outage are at least **10 minutes** apart.
- R5. After **3** remediation cycles in one outage without WAN recovery, the system fires a budget-exhausted alert that **inhibits** further remediation notifications until WAN recovers, at which point attempt state resets to closed/zero.
- R9. Budget-exhausted (and thus “why we stopped”) is visible in Alertmanager/Karma via the inhibit source alert.

**Action path**

- R6. Alertmanager delivers remediation via webhook to an in-cluster shim that creates a **one-shot Job** per attempt.
- R7. The Job performs the UniFi API outlet power-cycle, updates attempt/breaker state, and is responsible for raising/clearing budget-exhausted as needed.
- R8. During a cycle, the UDM and cluster remain the control plane (modem is the disrupted device).
- R10. Kubernetes Job `backoffLimit` / pod restart backoff applies only to retries of a **failed pod within that Job** (e.g. transient UniFi API errors), not to spacing successful cycles across an outage.

**Notify**

- R11. Human notification (existing Pushover path) remains for WAN-down and budget-exhausted; the remediation webhook route is action-only and must not replace operator paging.

### Acceptance Examples

- AE1. When UniFi WAN flaps during saturation but external probes stay up, the composite alert does not fire and no Job cycles the modem. Covers R2, R3.
- AE2. When both signals are down for 5 continuous minutes and the breaker is closed with no cycle in the last 10m, exactly one Job runs and the modem outlet is power-cycled. Covers R2–R4, R6–R8.
- AE3. When a second composite fire arrives 5m after a successful cycle with WAN still down, the Job no-ops (gap). Covers R4, F3.
- AE4. When three cycles have run in one outage without WAN recovery, budget-exhausted fires, inhibit stops further webhook remediation, and Pushover still informs the operator. Covers R5, R9, R11, F2.
- AE5. When WAN recovers after a tripped breaker, attempt state resets and a later sustained dual-signal outage can remediate again from attempt zero. Covers R5, F1.

### Success Criteria

- Sustained true WAN loss results in at most three modem power-cycles before human intervention is required.
- Saturation / brief UniFi WAN flaps without external probe failure do not cause modem cycles.
- An operator can see in Alertmanager/Karma whether remediation is active or budget-inhibited without reading Job logs first.

### Scope Boundaries

**In scope:** Detection wiring (metrics/alerts), Alertmanager route + inhibit, webhook shim, remediation Job, UniFi PDU cycle for the modem outlet, breaker state + budget-exhausted alert, Pushover coexistence.

**Out of scope:** Power-cycling the UDM; adopting Robusta/Keep/StackStorm; Home Assistant as remediator; exponential remediation backoff; changing UniFi’s built-in outlet feature beyond disabling/replacing its use for this outlet; general blackbox estate redesign.

### Dependencies / Assumptions

- UniFi WAN state is available (or can be made available) via existing unpoller → VictoriaMetrics scrapes on ~2m cadence; planning confirms the exact metric/labels.
- Cluster can reach `https://unifi` on LAN while the modem is down or rebooting.
- A dedicated UniFi credential (or reuse of an existing secret pattern) can call the outlet power-cycle API.
- External probe target(s) for the dual-signal exist or will be added as part of planning (implementation detail).

### Outstanding Questions

**Deferred to Planning**

- Exact unpoller metric/label for WAN down and PromQL for the composite alert.
- External probe module/targets and how they join the composite expression.
- UniFi API shape and PDU outlet identifier for the modem.
- Durable store for attempt count / last-cycle time (and how budget-exhausted is asserted—recording rule, Pushgateway, or alert generated from Job-updated state).
- Webhook authentication and AM route `repeat_interval` / grouping tuned so the Job is not spammed beyond what R4 already enforces.

### Sources / Research

- Existing Alertmanager receivers already use webhooks (buddy heartbeat) and Pushover: `kubernetes/apps/observability/victoria-metrics/app/vmalertmanagerconfig.yaml`.
- Unpoller scrapes UniFi including PDU-related metrics on a 2m interval: `kubernetes/apps/observability/unpoller/app/helmrelease.yaml`.
- Blackbox/`VMProbe` patterns exist for ICMP/HTTP probes: `kubernetes/apps/observability/blackbox-exporter/`.
- Alertmanager’s built-in exponential backoff applies to **failed notification delivery**, not remediation spacing; circuit-breaker / action-budget patterns belong in the remediator with optional inhibit/silence projection into AM.
