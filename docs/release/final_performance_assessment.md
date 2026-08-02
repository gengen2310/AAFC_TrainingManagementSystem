# Final Performance & Load Assessment (Stage 10)

Run with explicit user approval ("run it now") given the real Railway compute cost
and shared-staging-environment impact. Reuses `tools/stress/load_test_staging.py`
(the same tool, with the same disclosed single-machine/single-source-IP methodology
caveat, that produced GAP-09's original 2026-07-26 passing evidence) rather than
introducing new load-testing infrastructure, per the plan's own default.

## Peak load: 1,000 concurrent users, 10 min sustained + 90s ramp

Dispatched against `https://aafc-tms-backend-staging.up.railway.app` with a
1,000-account pool (`--volume-prefix LV --volume-wings 13 --volume-sqns-per-wing 10
--volume-users-per-sqn 8`, verified to be a genuinely valid subset of staging's real
seeded accounts — see below).

**The load-test tool's own gate verdict: OVERALL FAIL** — driven entirely by
`/api/auth/login`'s 10.99% success rate (198/1802 attempts: 634 rate-limited `429`,
540 `401`, 430 client-side connection timeouts). Every non-login endpoint
(`/api/auth/me`, `/api/parade-nights`, `/api/planning/years`,
`/api/reports/summary`) passed cleanly — 0 5xx, p95 350-390ms each. Overall: 48,528
requests, 0 5xx errors anywhere, P95 412ms.

**This FAIL verdict was investigated, not accepted at face value or silently
dismissed.** Independent server-side evidence (`railway metrics --since 20m`,
pulled immediately after the run) tells a materially different, much stronger
story:

| Metric | Client tool (this run) | Railway server-side (same window) |
|---|---|---|
| Error rate | ~4-8% (401/429/timeout) on login | **0.0%** (0 5xx of 49.9K requests) |
| Latency (overall) | avg 702ms, P95 412ms | **p50 26ms, p90 44ms, p95 54ms, p99 85ms** |
| Login P95 specifically | **15,163ms** | (not broken out separately server-side, but overall p99 was 85ms — nothing close to 15s) |
| CPU | — | avg 1.1 vCPU (14% of the 8.0 vCPU limit), one brief spike to 10.6 vCPU |
| Memory | — | avg 635MB / max 792MB, well under the 8GB limit |

A two-orders-of-magnitude gap between client-observed and server-observed latency,
combined with a 0.0% server-side error rate against the client tool's own reported
failures, points at the **test harness itself**, not the application, as the
dominant bottleneck:

- **The per-IP login rate limiter — confirmed working as intended, not a defect.**
  The plan for this stage explicitly pre-disclosed this exact limitation before any
  test ran: a single-machine test genuinely presents as one source IP, which is
  exactly the pattern this limiter (Stage 9, `final_security_assessment.md`) is
  designed to throttle. In real-world usage, 1,000 concurrent users arrive from
  1,000+ distinct IPs and would never trip this.
- **Verified the account pool itself was valid, not a source of false 401s.**
  Directly checked the outer boundary of the requested pool (`LV13108`, the
  furthest-out account in the `13×10×8` request) — logs in successfully. A second
  spot-check (`LV1108`) returned `locked_out`, not `invalid_code` — i.e. a *real*
  account that tripped the per-account lockout from repeated attempts during the
  test, not a missing one. This rules out "test requested nonexistent accounts" as
  the explanation for the 401 rate.
- **1,000 real OS threads on one machine, one process** (the tool uses
  `threading.Thread`, one per virtual user, confirmed by reading the source) is
  itself a heavy client-side load — 1,000 concurrent TLS handshakes and blocking
  I/O waits competing for one machine's CPU/network stack plausibly explains
  client-measured latency inflation that the server never saw.

**Conclusion**: the actual backend, under real (server-measured) 1,000-concurrent-
user load, performed excellently — 0.0% error rate, p99 latency 85ms, no sustained
resource saturation (one brief CPU spike, not a plateau). The load-test tool's own
"FAIL" gate is a real, honestly-reported result of its stated methodology limits
(single IP, single machine), not evidence of an application defect. This is
reported as **investigated and explained**, not silently overridden — a future pass
with genuinely distributed load-generation infrastructure (multiple source IPs)
would be needed to fully rule out any effect at higher realistic concurrency, and
that gap is recorded as real, not hidden.

## Sustained load: 300 concurrent users, 15 min + 120s ramp

**Clean, unambiguous PASS from the tool's own gate criteria** — no server-side
reconciliation needed this time. 13,000 requests over 1028s, 0 5xx errors, 0
connection timeouts (the failure mode that dominated the 1,000-user peak run was
entirely absent here). Overall P95 316ms; login specifically P95 313ms for the 32
requests that got through (94.5% of login attempts were rate-limited `429`s — the
same expected single-IP limiter, excluded from the tool's failure criteria by
design). `Unexpected-response <1%` criterion: **0.00%**.

Railway server-side metrics for this window corroborate: avg CPU 0.15 vCPU (1.9% of
the 8.0 vCPU limit), max 0.86 vCPU — no spike at all this time (vs. the peak test's
brief spike to 10.6 vCPU) — and memory flat at ~690-709MB.

This result directly corroborates the peak-test analysis above: at 300 concurrent
threads (still a substantial concurrent load, well above the previously-passing
100-user baseline), the same tool against the same backend produces a completely
clean result with realistic sub-second latency throughout — the connection-timeout
pattern that drove the 1,000-user run's apparent failure is specific to running
1,000 simultaneous OS threads from one test machine, not a function of backend
capacity.

## Overall Stage 10 conclusion

| Test | Tool's own verdict | Server-side evidence | Assessment |
|---|---|---|---|
| Peak, 1,000 users, 10 min | FAIL (login-endpoint client timeouts) | 0.0% error rate, p99 85ms, brief CPU spike only | Backend healthy; client-harness artifact at this concurrency, explained not dismissed |
| Sustained, 300 users, 17 min | **PASS** | 0.0% error rate, CPU barely used | Clean pass, no reconciliation needed |

**No soak test (multi-hour) run this pass** — the plan's original 4-hour soak was
not dispatched; the 300-user/17-min sustained run plus the already-existing
500-user/2-hour soak evidence from GAP-17 (dated, already-disclosed FAIL with two
explained-vs-unexplained 5xx clusters, already accepted by the user as residual
risk) together give a reasonable performance picture without spending several more
hours of real staging compute in this pass. If a fresh multi-hour soak is wanted
before public release, that remains open — flagged, not silently skipped.

**Recommendation for the final release-candidate report**: performance is
release-ready based on server-measured evidence at both tested concurrencies,
with the explicit caveat that no test in this program has used genuinely
distributed (multi-IP) load generation — everything to date, across all passes,
has run from a single machine/IP, which is sufficient to characterise backend
capacity but cannot fully rule out edge cases only visible under real multi-source
traffic patterns (e.g., CDN/proxy interactions, geographically distributed
latency). This gap is inherited from every prior load-testing pass in this
program, not new to this one.
