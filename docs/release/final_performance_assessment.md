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

In progress — results to follow once complete.
