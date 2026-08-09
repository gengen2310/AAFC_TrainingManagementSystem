# UI copy review checklist

Companion to `defence-writing-ui-standard.md`. Use this checklist when
writing or reviewing any user-facing string in Main TMS or Planning
Workspace: page headings, field labels, buttons, help text, tooltips, empty
states, warnings, errors, success/confirmation messages, chart titles/
subtitles, table headings, status labels, system notices.

For each string, check:

- [ ] **Accuracy** — does it state exactly what is true? (Manual §2.14)
- [ ] **Brevity** — can any word be removed without losing meaning? (§2.16)
- [ ] **Empathy** — will a Training Officer with no technical background
      understand this? (§2.17)
- [ ] **Relevance** — does the user need this information at this point in
      the task? (§2.18)
- [ ] **Logic** — is information in the order the user needs it? (§2.20)
- [ ] **Completeness** — does the user have enough to act correctly? (§2.21)
- [ ] **Timeliness** — is a "current as at" or freshness indicator needed?
      (§2.22)
- [ ] **Plain word test** — is this the plainest, most precise word
      available? (§2.13.e)
- [ ] **No officialese** — could this be said more directly? (§2.13.f)
- [ ] **No jargon/software terms** — API, endpoint, UUID, 404, React,
      backend/frontend, token, schema must not appear (§2.13.g, this
      program's §7)
- [ ] **No contractions** in formal copy — "cannot" not "can't" (§2.13.h)
- [ ] **Active voice** — subject-verb-object, not passive, unless a
      technical/objective register is deliberately needed (§2.53)
- [ ] **Australian English** — organisation, authorise, colour, program
      (one m) (§3.4, §3.15)
- [ ] **Given name / Family name**, not First name / Surname, for personal-name
      fields (§3.34)
- [ ] **Dates**: unambiguous, one of the two Manual forms, never mixed
      (§5.67–5.73)
- [ ] **Time**: 24-hour only for operational time (§5.79–5.80)
- [ ] **Numbers**: one to nine in words in prose; numerals in tables/metrics/
      counts (§5.7, with the tabular exception)
- [ ] **No raw technical errors** exposed (e.g. a React error boundary
      message) — normal-user text must have a `[Technical details]`
      disclosure instead, not the raw error inline
- [ ] **Headings describe their content**, not generic labels like
      "Overview"/"Information"/"Status" (this program's §15)
- [ ] **Error messages** follow WHAT HAPPENED / WHAT IT AFFECTS / WHAT TO DO
      NEXT (this program's §23)
- [ ] **Empty states** distinguish NOT CONFIGURED / NO DATA / NO RESULTS FOR
      FILTER / NOT APPLICABLE / NO PERMISSION / FAILED TO LOAD, not one
      generic "No data." (this program's §24)
- [ ] **Confirmations** for irreversible actions state what will change,
      what will not, and whether it can be undone (this program's §25)

## Scope note

Do not rewrite strings that already work well merely to tick every box —
the goal is correctness and clarity, not churn. Use this checklist when
writing new copy, and when a specific string has been reported as confusing
or has failed a first-time-user test scenario.

## Tracking

Findings from applying this checklist go into
`docs/product-review/interface-language-inventory.csv` (per the governing
program's §22) — not yet generated as a full inventory in this pass; that is
a large, separate sweep across both frontends' source, tracked as follow-up
work.
