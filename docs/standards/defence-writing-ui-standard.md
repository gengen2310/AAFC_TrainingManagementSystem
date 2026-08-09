# Defence Writing UI standard

Source: *Writing Manual* (Defence Publishing Service, DPS: February 2014,
first edition, sponsor Commander Australian Defence College) — the actual PDF
supplied at `~/Downloads/Defence Writing Manual - 2014.pdf` (317 pages) was
read directly for this document; paragraph numbers below are cited from that
text, not reconstructed from memory or paraphrase. Chapters 2 (Effective
writing), 3 (Word presentation) and 5 (Numbers, the calendar, time, locations
and symbols) were read in full for this pass. Chapters 4, 6, 14, 23 and 24
were reviewed at the table-of-contents level only — their paragraph-level
detail is not yet extracted; do not cite specific paragraph numbers from
those chapters until a follow-up pass reads them directly.

This document translates the Manual's rules — written for Defence
correspondence, letters, minutes and reports — into an application content
standard for AAFC TMS. Where the Manual's original context does not apply to
software UI (email headers, signature blocks, message precedence, etc.), it
is not translated here at all, rather than forced into an inapplicable rule.

## 1. Plain English (Manual §2.4–2.7)

> "Plain English is writing that imparts a clear message, using only as many
> words as necessary." (§2.4)

The Manual lists what plain English emphasises (§2.5): words appropriate to
the reader and subject; active over passive voice; varied sentence length;
positive, direct construction; numbered/bulleted lists where useful; headings
to break up text; concise, courteous language. Apply all of these to TMS
interface copy, not only to formal documents.

## 2. Characteristics of effective writing (Manual §2.12–2.22)

The Manual's checklist, applied to UI copy:

| Manual characteristic | UI application |
|---|---|
| Accuracy (§2.14) | State exactly what is true — never "Saved" unless persistence is confirmed (see error-message standard below) |
| Brevity (§2.16) | Cut every word that doesn't change meaning |
| Empathy (§2.17) | Write with the actual reader in mind — a Training Officer, not a developer |
| Relevance (§2.18) | Don't show information the user doesn't need at this point in the task |
| Logic (§2.20) | Present information in the order the user needs it |
| Completeness (§2.21) | Give the user enough to act correctly, first time |
| Timeliness (§2.22) | Show when data is current as at, when relevant |

## 3. Word choice (Manual §2.13)

- **Choose the plainest, most precise word** (§2.13.e) — familiar,
  uncomplicated words over complex ones.
- **Avoid officialese** (§2.13.f) — "Communicate clearly and directly", with
  the Manual's own example pairs: *try* instead of *endeavour*, *confuse*
  instead of *obfuscate*, *consider* instead of *give consideration to*, *now*
  instead of *at this point in time*.
- **Avoid jargon** (§2.13.g) — "Do not use shortened forms or phrases that
  are unfamiliar to the intended reader." Applied to TMS: no `API`,
  `endpoint`, `payload`, `schema`, `UUID`, `404`/`500` in normal-user copy.
- **Avoid contractions** (§2.13.h) — the Manual's own examples: do not use
  "can't", "won't", "we'll", "they're". Applied throughout formal TMS copy
  (not button labels, which may stay concise per §14 below).

## 4. Accuracy of the written record (Manual §2.14–2.15)

> "The written word provides a permanent record. It is, therefore, important
> to present facts and record discussions and decisions with absolute
> accuracy." (§2.14)

Applied directly to TMS's error/success messaging standard: never claim a
save succeeded unless it did; never show a stale "Saved" state.

## 5. Active and passive voice (Manual §2.53–2.58)

> "Use the active voice wherever possible to clearly identify the action and
> the 'doer' of the action." (§2.53)

Active voice: subject, verb, object — *"TMS saved the Session"*, not *"The
Session was saved"*. The Manual explicitly permits passive voice for an
"objective, impersonal style" in technical contexts (§2.56) — not a blanket
ban, a preference.

Orders/Instructions/directives (§2.57) use the pattern: **identity of the
responsible person/role + "must"/"is to"/"are to" + the specific required
action**, expressed as one complete sentence. Applied to TMS's required-field
and permission copy: *"Squadron Admin must select a Training Year before
generating Parade Nights."*

## 6. Shortened forms (Manual §2.23–2.24)

Spell out on first use, with the short form in parentheses, when the term
first appears in the document/page. Do not spell out if the term appears
only once, or in headings unless it's a common Defence/AAFC term. Applied:
*"Training Management System (TMS)"* on first use per page/Help article,
`TMS` thereafter.

## 7. Style and tone (Manual §2.25–2.34)

> "Do not include humour in formal or business writing." (§2.29)

A neutral style "puts neither distance nor undue familiarity into the
relationship with readers" (§2.27). Applied: no marketing language, no
exclamation marks, no game-like copy ("Awesome!") in operational TMS text —
matches this program's own §11.

## 8. Australian spelling (Manual §3.2–3.5, §3.15)

Macquarie Dictionary is the Defence standard reference (§3.2). Rules with
direct examples from the Manual:

- 's' spelling over 'z' — *organise*, *rationalise*, not *organize*, *rationalize* (§3.4.a).
- '-our' over '-or' — *colour*, *harbour*, not *color*, *harbor* (§3.4.b).
- **"Program. Spell 'program' with a single 'm' unless citing an existing or
  official name"** (§3.15) — confirms this program's own instruction exactly;
  cite this paragraph if the terminology check (§22 below) needs a reference.

## 9. Given name / Family name (Manual §3.34)

> "In formal correspondence, address officers in the armed Services by their
> rank, given name or initials, family name and any postnominals." (§3.34)

Confirms the addendum's requested UI relabelling of "First name"/"Surname"
fields to **Given name**/**Family name** is a real, citable Manual
convention, not an invented preference.

## 10. Dates (Manual §5.67–5.73)

Table 5.2 gives the exact reference forms:

| Form | Long | Short |
|---|---|---|
| Full form | Wednesday 07 November 2009 | 07 November 2009 |
| Abbreviated form | Wed 07 Nov 09 | 07 Nov 09 |

> **"Unacceptable date formats. The 07/11/09 format, meaning 07 November
> 2009, is not to be used in Defence writing because of the potential for
> confusion with other standards, where 07/11/09 means 11 July 2009."** (§5.72)

> "Do not mix the full form and abbreviated form elements." (§5.73)

This is the direct source for this program's date-format rule — cited
exactly, not paraphrased.

## 11. Time (Manual §5.79–5.82)

> "The 24-hour system is used in internal Defence correspondence and
> communication between government departments." (§5.79)

> "In general, use the 24-hour system to describe time... When the terms
> 'midnight', '0000' (start of the day) and '2400' (end of the day) might
> lead to misunderstanding, number the hours and minutes from 0001 to 2359."
> (§5.80)

Directly confirms this program's 24-hour-only rule for TMS operational time
display (`1830`, not `6:30 PM`).

## 12. Numbers (Manual §5.4–5.20)

> "When numbers appear in text, write one to nine in words and 10 and above
> in numerals." (§5.7)

Applied to TMS prose (Help text, empty states, confirmations) — **not**
applied to tables, metrics, counts or compact operational displays, where
numerals improve scanning regardless of magnitude (this is the addendum's own
explicit carve-out, §19, and is consistent with the Manual's own §5.13
exception for tabular data: *"In tables, however, where consistent spacing is
essential for clarity... the four-digit rule just described does not
apply"* — the Manual itself treats tabular/numeric-dense contexts differently
from prose, supporting the same distinction for TMS).

## 13. Non-discriminatory and inclusive language (Manual §2.35–2.52)

Gender-neutral language preferred; refer to a person's characteristics only
when relevant (§2.36); avoid masculine/feminine singular pronouns for an
unspecified person — the Manual's own preferred fix is to "rewrite the
sentence in the plural" (§2.45.a), e.g. "Candidates must provide copies... to
their referees." This matches this session's own standing convention (default
to they/them when a real person's pronouns are unknown) and extends it to
TMS's own generated copy about unspecified users/roles.

## Not yet translated this pass

Chapter 4 (Punctuation), Chapter 6 (Document presentation — headings/lists/
tables), Chapter 14 (Preparing text, graphics and images for projection),
Chapter 23 (Editing), Chapter 24 (Publications) were reviewed only at the
table-of-contents level for this pass (paragraph numbers not yet read). The
program's headings/lists/chart-construction guidance (§15/16/26-29 of the
addendum) is currently implemented from the addendum's own text, not yet
cross-cited against the Manual's actual Chapter 6/14 paragraphs — flagged as
a follow-up pass, not fabricated here.

## Change control

If a newer controlled Defence Writing Manual or current AAFC policy is
supplied, diff it against this document's citations before replacing any
rule — do not silently assume continuity (per the addendum's own instruction).
