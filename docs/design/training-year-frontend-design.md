# Training Year — frontend design

Date: 2026-08-28
Spec: `docs/superpowers/specs/2026-08-28-training-year-context-model.md`
Prototype: `docs/design/training-year-frontend-prototype.html` (open it; every
measurement below comes from it)

**Design task, from the instruction §32:** make the Training Year almost
invisible as administration. The user should experience it as context.

---

## 1. What this design is not

It is not a new visual identity. The palette and typeface are fixed by
`.claude/rules/frontend.md` (AAFC VIG tokens, Montserrat), and §34 is explicit
that the dominant information is the year number rather than status. Inventing a
look here would break the first and contradict the second. Every colour below is
an existing token; the design work is structure, hierarchy and words.

## 2. The one idea

**The year is the subject of the page, not a field on it.**

Today it is a dropdown in a toolbar beside Create, Rename, Archive and Rollover —
which is what teaches people that a year is a record they administer. The design
moves it to where the page title goes and sets it at display size:

```
  ‹  ›   2026 ▾                                      704 Squadron
         CURRENT YEAR

         TRAINING CLASSES   PARADE NIGHTS   SESSIONS   ACTIVITIES
         5                  16              12         3
```

Everything else is subordinate to that numeral. The row of counts underneath is
deliberate: it answers "what is in this year", which is the question a Training
Cell actually has, and it makes the year read as content rather than as a
container.

### The craft detail that makes it work

`font-variant-numeric: tabular-nums` on the numeral. Stepping ‹ › from 2026 to
2027 — or to 2088 — **does not change its width**. Measured: 120px → 120px. A
proportional font would shift every element to its right on each press, which is
exactly the kind of small ugliness that makes a control feel like a form.

## 3. State without badges

§34 warns against recreating lifecycle complexity through labels. So there is one
quiet uppercase line under the year, and no chips anywhere:

| year | line |
|---|---|
| past | `← Previous year · training record` |
| current | `Current year` |
| future | `→ Future year · planning ahead` |

**The current year carries no arrow, and that is the design.** The arrows mean
"away from now", so their absence is what says you are in it. An earlier draft
had a `●` bullet before "Current year" for symmetry; it was removed because it
communicated nothing the word did not, and its absence now carries meaning.

Nothing here depends on colour. Verified by rendering the prototype under
`filter: grayscale(1)` and reading the state lines back:

```
["Current year", "→ Future year · planning ahead", "← Previous year · training record"]
```

## 4. The empty future year

§23: never say the year does not exist.

```
  ‹  ›   2028 ▾                                      704 Squadron
         → FUTURE YEAR · PLANNING AHEAD

  ┌ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┐
    Nothing has been set up for 2028 yet. You can start from
    scratch, or bring across the class structure you used last year.

    [ Set up 2028 ]   [ Copy setup from 2027 ]
  └ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ┘
```

A dashed border, not a solid card: the year is real, its configuration is empty.
The copy names the year rather than saying "this year", and the second button
names the source year rather than "copy previous" — both so the sentence is true
without the reader reconstructing context.

The buttons are the only two things that can usefully be done, which is what
§23 asks for. "Set up 2028" is primary; copying is deliberately secondary,
because §2.2 of the spec says nothing is copied unless the user asks.

## 5. The past year

```
  ‹  ›   2025 ▾                                      704 Squadron
         ← PREVIOUS YEAR · TRAINING RECORD

  🔒  Read-only. 2025 is complete. Its records stay available to
      review. To correct something, a Wing administrator can open
      Delegated Intervention.
```

Read-only is stated in words, in bold, at the start — the lock glyph is
redundant reinforcement rather than the message. The notice names the escape
route, because an interface that blocks you without saying what to do instead is
just a wall.

## 6. The year menu

Past years appear because they hold records. The current year and two ahead
appear because those can be planned — the cap is the user's decision of
2026-08-28, overriding the instruction's own "no cap" recommendation.

```
  2028   FUTURE
  2027   FUTURE
  2026   CURRENT     <- aria-current="true"
  2025   RECORD
  2024   RECORD
```

`RECORD` rather than `PAST`, because it says what the year is *for* rather than
where it sits in time — and it is the word the read-only notice uses, so the
vocabulary holds across the flow.

## 7. TMS → Planning Workspace

The handoff carries **squadron and year integer**, not a `planning_year_id`. A
year with no row is still a valid context, so a UUID cannot express it — which is
why `aafc_pw_year_id` has to go (spec §8).

PW renders the identical year bar in its context strip. The user sees the same
numeral in the same position, so the two applications read as one system rather
than two that happen to agree. Returning to TMS carries the year back the same
way.

**No second selection, no activation, no create prompt** — §21.

## 8. When the year rolls over mid-session

1 January changes a derived value, not stored state, so nothing happens to the
data. But a session open across midnight would silently be looking at last year.

The bar shows a one-line notice offering the switch, and does not move the user:

```
  2027 is now the current training year.   [ Switch to 2027 ]
```

Explicit, reversible, and it never swaps the data underneath someone mid-task
(§36).

## 9. Accessibility — measured, not asserted

Run against the prototype at 1120px, 390px, and 200% text.

| gate | result |
|---|---|
| **G1** contrast | **PASS** — 10 pairs enumerated, 10 pass body text at 4.5:1. Lowest is 3.26:1 on the disabled stepper glyph, which is above the 3:1 non-text threshold |
| **G2** non-colour | **PASS** — greyscale render; all three state lines and all five menu tags readable |
| **G3** 200% text | **PASS** — no horizontal overflow at `font-size: 32px` on `:root` |
| **G4** keyboard | **PASS** — every control reachable; focus ring `2px solid` visible on all |
| **G5** hit targets | **PASS** — 0 controls under 44×44 |
| layout stability | **PASS** — year width unchanged 2026 → 2088 |
| mobile 390px | **PASS** — no horizontal overflow |

**G5 failed on the first build** and is worth recording: the year button was
38px tall, because its height came from the type's line box. Fixed with
`min-height: 44px` and negative-margin padding, so the *hit area* is 44px while
the *type* is unchanged. Type size and touch target are different measurements
and the glyph should never determine the target.

**G1 also failed on the first build.** The disabled stepper used `--lgrey`
(#b0b7bb) on `--surface-2`, which is **1.85:1**. WCAG exempts disabled controls,
so this could have been left and justified — it was changed to #7e8992 (3.26:1)
instead, because the exemption is a technicality rather than a reason, and the
state is carried by the `disabled` attribute and an aria-label regardless.

### Exception recorded

The high-contrast theme redefines the same tokens (`--text: #000000`,
`--muted: #404040`, `--surface-2: #f0f0f0`). Every pair above gets *more*
contrast under it, so no pair needs re-checking — but `#7e8992` is hard-coded
rather than tokenised, so it does **not** darken with the theme. It stays at
3.26:1 there. Acceptable for a disabled control; worth a token if a
`--disabled-fg` is ever introduced.

**HUMAN VALIDATION PENDING** — no 5-second test, first-click test or
screen-reader pass has been run. The structural audit above is not a substitute.

## 10. What this removes from the interface

Per §51, subject to the migration staying safe:

Create Training Year · Manage Training Years · Rename · Active chip · Archive ·
Restore · Promote · Rollover · "Planning year required before continuing"

Replaced by: a year, two arrows, and the two actions that are true for the year
you are looking at.

`GuidedYearSetupModal` loses its opening question entirely. It currently starts
by asking "new year or roll over?" — under this model both answers are wrong,
because the year already exists. It becomes **Set up 2027**, with copying offered
as one optional step rather than as the premise.

`SetupPanel` loses step 1 ("create planning year") and the generated
`2026–2027 Training Year` name that produced the hyphenated wording §13 objects
to.
