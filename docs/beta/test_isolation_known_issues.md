# Test Isolation Known Issues

**created:** 2026-08-30  
**status:** OPEN — tracked as K-001 in docs/final/MASTER_FINAL_GAP_REGISTER.md  
**reference:** scripts/deploy-staging.sh — deselect list (lines 715-731)

---

## Overview

Five backend tests fail when run as part of the full test suite (`python -m pytest tests/ -q`) due to cross-test state contamination. They pass reliably in isolation. They are currently DESELECTED in the staging deploy gate to prevent false negatives.

This is a known quality gap. The tests exercise real behaviour. The deselection is a temporary workaround, not an endorsement of the behaviour they test.

---

## Affected tests

### 1. `test_rate_limiting.py::test_login_spike_emits_security_log`

**Root cause:** The rate limiting subsystem uses an in-process dedup window to suppress duplicate alert emissions within a short interval. Tests earlier in the full suite generate enough login activity to prime the dedup window. When this test runs, the dedup window is already active — the alert it expects to see is suppressed.

**Passes in isolation because:** No prior tests have primed the dedup window.

**Fix approach:** Add an autouse conftest fixture that resets the rate limiter's dedup state between tests (or between test modules).

---

### 2. `test_rate_limiting.py::test_login_spike_repeats_on_subsequent_multiples`

**Root cause:** Same as above. This test expects a second alert to fire on a subsequent spike, but the dedup window from earlier tests prevents it.

**Fix approach:** Same as test 1 — shared dedup reset fixture.

---

### 3. `test_rate_limiting.py::test_5xx_spike_emits_security_log`

**Root cause:** Same dedup window contamination. The 5xx spike alert is suppressed because the window was already primed by error-generating tests earlier in the suite.

**Fix approach:** Same dedup reset fixture.

---

### 4. `test_timing.py::test_bulk_schedules_match_single_endpoint_exactly`

**Root cause:** The rate limiter is exhausted by the time this test runs. The full test suite makes 2000+ API calls before this test. The rate limiter triggers a 429 response for the bulk schedule endpoint call in this test, causing an assertion failure (`assert 429 == 200`).

**Passes in isolation because:** No prior rate limiter exhaustion.

**Fix approach:** Either: (a) add a per-test or per-module rate limiter reset in conftest.py, or (b) move this test to run before rate-exhausting suites, or (c) configure the test server to use a higher rate limit threshold in test mode.

---

### 5. `test_year_context.py::test_year_listing_includes_future_years_with_no_row`

**Root cause:** The `ensure_year_context` endpoint materialises future-year rows as a side effect of other training and planning tests earlier in the suite. By the time this test runs, every expected "unmaterialised future year" has already been materialised, so the assertion that "future years with no row must still be listed" finds no such years to list.

**Passes in isolation because:** Database starts clean with no prior ensure_year_context side effects.

**Fix approach:** Add a conftest fixture that deletes `ensure_year_context`-materialised rows (those with a specific marker or created_at timestamp from the test run) in teardown, restoring the "no future year row" baseline before this test.

---

## Risk assessment

The deselection of rate limiting tests (tests 1–3) is the highest-risk aspect of this workaround. These tests verify that the security alert subsystem fires correctly on attack-pattern detection. A regression in this subsystem would not be caught by the deploy gate while these tests are deselected.

The timing test (test 4) and year context test (test 5) verify functional correctness of less security-critical paths.

**Recommended fix priority:** Rate limiting tests first (security relevance), then timing and year context.

---

## Tracking

See docs/final/MASTER_FINAL_GAP_REGISTER.md gap K-001 for implementation plan and status tracking.
