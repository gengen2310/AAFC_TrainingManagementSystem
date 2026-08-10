# AAFC TMS — Original Remediation Instruction (Recovered Verbatim)

**Provenance**: This is the full, verbatim text of the instruction that
launched the "Complete System Remediation, Integration and Workflow Program"
(see `master_remediation_plan.md`, `.claude/rules/capability-preservation.md`).
It was pasted directly into a Claude Code chat session on **2026-08-04T15:10:30Z**,
immediately before the `remediation/2026-08-04-complete-system-remediation`
branch was created from `main` @ `ab1dd8d`. It was never saved as a file in the
repo or on GitHub at the time — only its derivative durable-record files
(`master_remediation_plan.md`, `master_gap_register.csv`, etc., created per its
own Section 2) were committed. It was not lost — it survived in that chat
session's own transcript — and was recovered from there on 2026-08-10 by
reading that session's raw JSONL history directly, after the user could not
locate it on GitHub.

Its real title, as pasted, is below (not a paraphrase — earlier casual
references to this document in conversation used a slightly different,
hedged wording; this is the exact original).

**Length**: 57,665 characters. **Structure**: a MISSION statement plus 27
numbered sections (0–27), reproduced in full below with no edits, paraphrase,
or omission.

This file is the authoritative reference for any future audit of gap-register
items that say "not yet audited against this instruction" (e.g. REM-04, REM-10,
REM-12, REM-14, REM-15, REM-17, REM-19, REM-20, REM-22) — check the relevant
section number below directly rather than relying on secondhand summaries.

---

AAFC TMS — COMPLETE SYSTEM REMEDIATION, INTEGRATION AND WORKFLOW PROGRAM

MISSION

Resolve the complete attached AAFC TMS risk register and redesign the system
around an efficient Training Officer workflow while preserving all current
capabilities.

This is not permission to rewrite the application indiscriminately.

This is not permission to remove existing features because another feature looks
similar.

This is not permission to merge the Main TMS and Planning Workspace frontend
builds.

The objective is:

- one authoritative operational system;
- two intentionally separate frontends;
- consistent records, permissions and business rules;
- a workflow that follows how Squadron Training Officers actually plan,
  communicate, deliver and review training;
- Squadron functionality available at higher command levels, plus aggregation,
  comparison and authorised intervention;
- no silent loss of existing capability.

Work through every registered item.

Use staged implementation, small commits, evidence and regression testing.

Do not stop merely because one independent item is blocked. Record the blocker
and continue with other independent stages.

Do not deploy production under this instruction.

Staging deployment is authorised only after the relevant automated test gates
pass.

======================================================================
0. AUTHORITATIVE PROJECT
======================================================================

Local repository:

/Users/jennydv/Desktop/AAFC_TMS_National_Connected_Pilot_Package_v17_1_source

GitHub:

https://github.com/gengen2310/AAFC_TrainingManagementSystem

Main TMS:

connected-frontend/

Planning Workspace:

frontend/

Backend:

backend/

The two frontends are intentionally separate deployments.

Do not:

- replace connected-frontend with the React/Vite build;
- combine the frontend output;
- delete either frontend;
- introduce a third operational frontend;
- create a second backend;
- treat one frontend as disposable legacy code.

Both frontends must use the same FastAPI backend and canonical domain records.

Before work:

1. Read:
   - CLAUDE.md;
   - every applicable `.claude/rules/*.md`;
   - `architecture.md`;
   - `final_feature_inventory.md`;
   - Planning Workspace documentation;
   - release and gap-register documents;
   - existing migration documentation;
   - testing documentation.
2. Run:
   - git status;
   - git branch --show-current;
   - git log -15 --oneline;
   - git remote -v;
   - git fetch --all --prune.
3. Report:
   - current branch;
   - current HEAD;
   - remote branch HEAD;
   - origin/main HEAD;
   - uncommitted files;
   - untracked files;
   - commits not yet pushed;
   - current database migration head.
4. Create a dedicated remediation branch from the most current complete
   implementation branch.
5. Do not discard, reset, overwrite or rebase away existing work.

======================================================================
1. NEW NON-NEGOTIABLE PROJECT RULES
======================================================================

Create:

`.claude/rules/capability-preservation.md`

Import it from the existing root CLAUDE.md using the repository's established
memory structure.

Do not duplicate an equivalent existing rule file.

The rule must contain the following requirements.

----------------------------------------------------------------------
1.1 Capability preservation
----------------------------------------------------------------------

DO NOT TOUCH, ALTER, REMOVE, RENAME, HIDE OR DELETE AN EXISTING FEATURE,
CAPABILITY, ROUTE, ENDPOINT, ROLE, DATA FIELD, IMPORT FORMAT OR WORKFLOW WITHOUT:

1. identifying the existing capability;
2. identifying all users and roles that depend on it;
3. recording the proposed impact;
4. proving an equivalent or improved replacement;
5. preserving data and historical access;
6. preserving a compatibility path where required;
7. obtaining explicit user authorisation where the capability is to be removed.

A bug fix must not cause unrelated features to disappear.

A visual redesign must not silently remove actions.

A navigation consolidation must not remove deep links.

A model consolidation must not discard historical records.

A new implementation is not proof of parity.

Before modifying a functional area, compare:

- frontend pages;
- routes;
- buttons and actions;
- backend endpoints;
- permissions;
- database fields;
- imports and exports;
- tests;
- audit events;
- help documentation.

After modifying it, repeat the comparison.

Any reduction must be recorded as:

`USER-AUTHORISED REMOVAL`

or treated as a regression.

The following removal is already authorised:

- merge all Training Summary content into Dashboard;
- remove the separate Training Summary navigation tab only after complete content
  and action parity is proven;
- preserve a route redirect or compatibility message for old deep links.

No other feature removal is authorised.

----------------------------------------------------------------------
1.2 Proper bug-resolution protocol
----------------------------------------------------------------------

For every bug:

1. Reproduce it.
2. Record:
   - role;
   - organisation scope;
   - frontend;
   - route;
   - exact request;
   - response status;
   - response payload category;
   - backend log;
   - browser console result;
   - current Git SHA.
3. Identify the root cause.
4. Search the current official documentation for the framework, library, protocol
   or platform involved where behaviour is unclear.
5. Prefer:
   - official documentation;
   - primary specifications;
   - current package documentation;
   - repository source;
   - existing tests.
6. Do not copy a random workaround from a blog without validating it.
7. Record relevant documentation references in an engineering decision note.
8. Produce a brief impact assessment before changing code:
   - affected features;
   - affected roles;
   - affected data;
   - migration requirement;
   - security implications;
   - compatibility implications.
9. Implement the smallest safe correction that addresses the root cause.
10. Add a regression test that fails before the fix and passes after it.
11. Run affected tests.
12. Run the relevant complete suite.
13. Verify in staging through the rendered authenticated application.
14. Do not mark the bug closed from source inspection alone.

If the minimum fix would damage an existing feature:

- do not remove the feature;
- document the conflict;
- design a compatibility solution;
- implement the least disruptive option;
- record any residual limitation.

----------------------------------------------------------------------
1.3 No false closure
----------------------------------------------------------------------

Do not close an issue because:

- the database contains the value but the frontend does not render it;
- the button exists but the endpoint returns 403;
- the endpoint works for System Administrator but not the intended role;
- staging works but production has not been checked;
- a summary card works but its chart fails;
- one frontend works but the other does not;
- a test passes only because it bypasses the real login or UI workflow;
- no records exist and the UI treats the empty set as success;
- an inherited record was copied instead of inherited;
- the error was hidden by changing the message.

Every closure requires user-visible and backend evidence where relevant.

----------------------------------------------------------------------
1.4 Data safety
----------------------------------------------------------------------

Do not:

- reset a database;
- reseed production;
- delete operational history;
- delete audit history;
- run destructive production tests;
- use raw SQL for ordinary application operations;
- auto-merge ambiguous records;
- silently change organisation ownership;
- alter credentials;
- expose access codes or hashes;
- put secrets in source, reports, screenshots or logs.

All destructive operations require:

- dependency preview;
- reason;
- confirmation;
- audit event;
- safe failure;
- archive alternative.

Archive remains the normal operational action.

Permanent deletion is restricted to erroneous, unused records with no required
historical dependency.

----------------------------------------------------------------------
1.5 Git and release safety
----------------------------------------------------------------------

Use small, coherent commits.

Each commit message must identify:

- functional area;
- behaviour changed;
- tests added or updated.

Do not combine unrelated fixes in one commit.

Do not merge main.

Do not deploy production.

Do not rewrite published history.

After every stage:

- push the remediation branch;
- update the master gap register;
- record tests and evidence;
- confirm no capability disappeared.

----------------------------------------------------------------------
1.6 Security
----------------------------------------------------------------------

Do not weaken security to eliminate a 403.

Do not broaden a role globally because one route uses the wrong scope helper.

Do not return access-code hashes.

Do not create a master login code.

Do not retrieve existing access codes.

Do not remove Proxy or Intervention requirements from protected delegated writes.

Do not use `dangerously-skip-permissions`.

======================================================================
2. DURABLE EXECUTION RECORDS
======================================================================

Create:

- `docs/remediation/master_remediation_plan.md`
- `docs/remediation/master_gap_register.csv`
- `docs/remediation/capability_manifest_before.json`
- `docs/remediation/domain_model_inventory.md`
- `docs/remediation/reference_key_inventory.md`
- `docs/remediation/environment_variable_inventory.md`
- `docs/remediation/api_contract_inventory.md`
- `docs/remediation/role_capability_matrix.md`
- `docs/remediation/data_migration_plan.md`
- `docs/remediation/staging_verification_report.md`

These documents are the durable source of context.

Update them continuously so a future Claude Code session can resume without
relying on this conversation.

The gap register must contain:

- gap ID;
- source report;
- functional area;
- symptom;
- severity;
- affected roles;
- affected frontend;
- root cause;
- proposed correction;
- files changed;
- migration;
- tests;
- staging evidence;
- status;
- residual limitation.

Statuses:

- NOT STARTED;
- REPRODUCED;
- ROOT CAUSE CONFIRMED;
- IMPLEMENTING;
- AUTOMATED TESTED;
- STAGING VERIFIED;
- BLOCKED;
- CLOSED.

Do not use CLOSED without evidence.

======================================================================
3. CAPABILITY BASELINE
======================================================================

Before functional changes, build a complete capability manifest.

Inventory:

- every Main TMS page ID;
- every Planning Workspace route;
- every navigation item by role and scope;
- every backend route;
- every database model and table;
- every role;
- every permission helper;
- every Proxy and Intervention function;
- every import and export;
- every account action;
- every organisation action;
- every Planning Year action;
- every Parade Night action;
- every Activities action;
- every Facilitator action;
- every Training Area and Equipment action;
- every dashboard chart and summary;
- every audit action type;
- every help or Getting Started workflow.

Run and record the current baseline tests.

Do not assume older documented test totals remain current.

Produce:

`capability_manifest_before.json`

At the end, produce:

`capability_manifest_after.json`

Compare them automatically.

No unexplained loss is acceptable.

======================================================================
4. KEYS, VARIABLES AND DUPLICATE-CONCEPT AUDIT
======================================================================

Analyse all keys and variables throughout the system.

Do not expose secret values.

Record names, definitions, types, defaults and use sites only.

Audit:

- database table names;
- database columns;
- foreign keys;
- unique constraints;
- enum values;
- Pydantic fields;
- API response fields;
- query parameters;
- route parameters;
- frontend state variables;
- sessionStorage keys;
- localStorage keys;
- cache keys;
- selected-scope keys;
- Training Year keys;
- organisation IDs;
- Parade Night IDs;
- activity identifiers;
- CEA identifiers;
- facilitator identifiers;
- Training Area identifiers;
- equipment identifiers;
- environment-variable names;
- Railway variable names;
- feature flags;
- test-fixture keys;
- CSV headers;
- Learning Hub URL fields;
- display labels.

Identify:

- duplicates;
- near-duplicates;
- synonyms;
- conflicting definitions;
- case-only differences;
- singular/plural variants;
- old and new names;
- fields with the same name but different meaning;
- fields with different names but the same meaning;
- strings functioning as undeclared enums.

Examples to inspect include, but are not limited to:

- TrainingArea versus PlanningLocation;
- Activity versus CeaActivity;
- year versus training_year versus planning_year versus planning_year_id;
- unit_id versus squadron_id versus organisation_id;
- room versus location versus training_area;
- Core versus Foundation versus Extension versus Optional;
- cancelled versus canceled;
- not_delivered versus undelivered;
- ready versus staffed versus assigned;
- API_BASE versus AAFC_API_BASE versus BACKEND_URL;
- selectedYear storage keys;
- selectedScope storage keys;
- role and access-type names.

For every duplicate or near-duplicate, provide:

| Existing names | Meaning | Canonical name | Compatibility plan | Migration |

Do not consolidate merely because names look similar.

Confirm semantic equivalence first.

Use:

- stable UUIDs for entities;
- stable codes for reference data;
- user-facing names for display only;
- case-insensitive uniqueness where appropriate;
- explicit foreign keys rather than text matching.

Do not drop old fields or tables during this remediation unless separately
authorised.

Use compatibility adapters, aliases or read-through views until every consumer
has migrated.

======================================================================
5. TARGET OPERATING WORKFLOW
======================================================================

Redesign navigation around the actual Training Officer planning cycle.

The core operational workflow is:

1. Configure the Squadron.
2. Map the Training Year.
3. Review inherited and local activities.
4. Identify anchor events.
5. Work backwards to schedule preparation.
6. Schedule curriculum and non-syllabus missions.
7. Allocate facilitators, Training Areas and equipment.
8. resolve or formally override conflicts.
9. Review the Long Range View.
10. Build the next Parade Night.
11. Publish the Weekly Program.
12. Record delivery outcomes.
13. Reschedule cancelled or not-delivered missions.
14. Review readiness, progress and workload.
15. Adjust continuously.

Reduce top-level navigation burden without removing capabilities.

Preferred Squadron navigation:

- Dashboard;
- Training Calendar;
- Plan Training;
- Weekly Program;
- People and Resources;
- Needs Attention;
- Settings.

Within Plan Training:

- Training Year;
- Activities and Anchors;
- Mission Backlog;
- Long Range View;
- Parade Night Builder;
- Planning Checks.

Within People and Resources:

- Facilitators;
- Training Areas;
- Equipment.

Within Settings:

- Squadron Details;
- Timing Templates;
- Program and Reference Data;
- Accounts where authorised;
- Archive and Restore.

Do not delete existing routes.

Use route aliases or redirects.

Do not hide a capability before it is represented in the new workflow.

Higher scopes must use the same functional model:

Wing:

- all Squadron functions when viewing an authorised Squadron;
- Wing-level planning;
- Wing activities;
- subordinate comparison;
- Wing calendar;
- Wing workforce and resource visibility;
- Proxy Mode for protected Squadron writes.

National:

- all Squadron and Wing functions when viewing authorised scope;
- National activities;
- national calendar;
- Wing and Squadron comparison;
- Delegated Intervention for protected subordinate writes.

System Administrator:

- every authorised view;
- complete scope selector;
- system health;
- accounts and organisations;
- all calendars and dashboards;
- protected operational writes only through appropriate mode where required.

Read-only browsing must not require Proxy or Intervention.

Protected subordinate writes must.

======================================================================
6. REFERENCE DATA AND CUSTOM TRAINING STRUCTURE
======================================================================

Create a proper Program and Reference Data capability.

Do not place these records directly inside Account Management.

Provide a link from Account Management and Facilitators where useful.

Administrative scopes:

- System Administrator;
- National Administrator;
- Wing Administrator;
- Squadron Administrator.

Reference entities:

- Training Stage;
- Facilitator Type;
- Facilitator Subject Area;
- Session Status Reason;
- Activity Type;
- Notice Type;
- Training Area Capability;
- Equipment Category where required.

Required fields for scoped reference records:

- id;
- stable code;
- display name;
- description;
- owning level;
- owning organisation;
- inherited status;
- active status;
- display order;
- effective start date;
- effective end date;
- created by;
- updated by;
- created at;
- updated at;
- archived at;
- audit history.

Inheritance:

- National records are visible to Wings and Squadrons;
- Wing records are visible to subordinate Squadrons;
- Squadron records remain local;
- subordinate users cannot edit inherited definitions;
- the source scope is visible;
- inherited and local definitions must not be copied into duplicate records.

Uniqueness:

- stable code must not collide within an applicable scope;
- comparisons must be case-insensitive;
- whitespace must be normalised;
- ambiguous duplicates must be reported, not auto-merged.

Training Stage classification:

- Orientation = Foundation;
- Initial = Foundation;
- Junior = Foundation;
- Intermediate = Foundation;
- Senior = Foundation;
- Bronze = Extension;
- Silver = Extension;
- Gold = Extension;
- Squadron-created programs default to Optional unless an authorised user
  deliberately assigns another classification.

Do not infer classification repeatedly from the stage name.

Store it explicitly.

Custom Training Stages must not automatically appear on every Parade Night.

Implement an applicability model:

- available to the scope;
- enabled for a Training Year;
- enabled for a term;
- enabled for selected Parade Nights;
- hidden when not required;
- historical assignments preserved after deactivation.

Create, edit, archive and restore must be audited.

Permanent deletion must be blocked when referenced.

======================================================================
7. SQUADRON DETAILS AND PERSONALISATION
======================================================================

Rebuild Squadron Details as the authoritative source for local operating
settings.

Fields include:

- Squadron Full Name;
- Squadron Short Name;
- Squadron Crest;
- Parade Day;
- Session Duration;
- Arrival Time;
- Flight Time Start;
- Flight Time End;
- Roll Call;
- First Parade Start;
- First Parade End;
- Dinner Break Start;
- Dinner Break End;
- Fatigues Start;
- Fatigues End;
- Final Parade Start;
- Final Parade End;
- Cadet Dismissal;
- Default Sessions Per Night;
- default Timing Template.

Parade Day must support Monday through Sunday.

Do not assume Friday.

Timing validation:

- parse times consistently;
- ensure sequence is logical;
- detect overlaps;
- detect negative duration;
- allow intentional gaps;
- display 24-hour time;
- identify missing required events.

The system must support a structured nightly sequence, not only numbered training
sessions.

Standard activity blocks may include:

- arrival;
- flight time;
- roll call;
- first parade;
- training session;
- dinner break;
- fatigues;
- final parade;
- dismissal.

Allow:

- zero or more session blocks;
- custom labels;
- reordering where authorised;
- one-off Parade Night overrides;
- stage-specific overrides.

Timing precedence:

1. Parade Night plus Training Stage override;
2. Parade Night override;
3. Squadron default Timing Template;
4. Squadron Session Structure fallback.

Display the effective source clearly.

Changing the default template must offer:

- future new Parade Nights only;
- selected future draft Parade Nights;
- all future draft and planned Parade Nights;
- preview before applying.

Do not overwrite:

- delivered;
- closed;
- archived;
- historical;
- manually protected exceptions.

Squadron Crest:

- optional;
- validated file type;
- validated file size;
- safe file name;
- no executable content;
- no ephemeral Railway filesystem dependency;
- default crest when none is uploaded;
- accessible alt text.

Inspect existing infrastructure before choosing storage.

Do not implement unsafe base64 or public unauthenticated storage as a shortcut.

======================================================================
8. TRAINING YEAR LIFECYCLE
======================================================================

Provide consistent Training Year management in both frontends.

Administrative scope:

- System;
- National;
- Wing;
- Squadron.

Actions:

- create;
- rename;
- activate;
- archive;
- show archived;
- restore;
- prepare next year;
- carry forward selected reusable configuration;
- update future Parade Nights;
- dependency-protected permanent delete.

Use consistent language:

- Training Year;
- Prepare the 2027 Training Year;
- Change active Training Year from 2026 to 2027;
- Add anchor event;
- Update future Parade Nights;
- Guided year setup.

Do not show unexplained arrow notation as the only label.

Rollover must not:

- alter historical results;
- move delivered sessions;
- change old activity ownership;
- duplicate inherited records;
- overwrite manually configured future records.

Permanent delete requires dependency preview covering:

- Parade Nights;
- sessions;
- activities;
- notices;
- holidays;
- facilitators;
- assignments;
- conflicts;
- audit records.

Where dependencies exist, block deletion and offer Archive.

======================================================================
9. PARADE NIGHT GENERATION AND EDITING
======================================================================

Restore and expose Parade Night auto-generation.

Inspect the existing backend generation capability before creating another
endpoint.

Required generation inputs:

- start date;
- end date;
- start time;
- end time;
- Parade Day;
- recurrence frequency:
  - daily;
  - weekly;
  - fortnightly;
  - monthly;
  - yearly;
- recurrence end date;
- optional occurrence limit;
- explicit skip dates;
- holiday handling;
- default Timing Template;
- default Training Stages;
- status.

Use plain labels.

Provide a preview before creation.

Preview classifications:

- will create;
- already exists;
- conflicts with holiday;
- explicitly skipped;
- invalid date;
- outside Training Year;
- duplicate;
- requires decision.

Holiday options:

- skip all conflicting dates;
- include selected conflicting dates;
- include all with warning.

Do not silently create duplicates.

Use stable Parade Night IDs.

Main TMS and Planning Workspace must use the same Parade Night record.

Required integration test:

1. Create in Main TMS.
2. Observe the same ID in Planning Workspace.
3. Edit in Planning Workspace.
4. Observe the change in Main TMS.
5. Archive.
6. Verify active views in both.
7. Restore.
8. Verify both.
9. Delete only an unused test Parade Night through the normal protected path.

Users must be able to edit a Parade Night after creation, subject to status and
permissions.

Historical and delivered records must be protected.

Repair the Annual Program capability.

Determine whether it is:

- a broken route;
- a stale page;
- an old parallel model;
- an obsolete name for the Training Year Plan.

Do not simply delete it.

Either:

- repair it against canonical data; or
- redirect it to the equivalent current Training Year Plan while preserving all
  functions and deep-link compatibility.

======================================================================
10. ACTIVITIES, CEA IMPORT, HOLIDAYS AND ANCHORS
======================================================================

Create one authoritative Activities capability used by both frontends.

Administrative levels:

- Squadron;
- Wing;
- National;
- System Administrator.

Higher levels must have feature parity with Squadron plus broader scope.

Activities page capabilities:

- list;
- calendar;
- create;
- edit;
- archive;
- restore;
- search;
- filters;
- upcoming;
- historical;
- inherited;
- local;
- CEA import;
- import history;
- priority decisions;
- target audience;
- anchor status;
- add Holiday.

Holiday entry on the Activities page:

- name;
- start date;
- end date;
- jurisdiction;
- affects Parade Nights;
- owning scope;
- notes.

Do not create another Holiday model if a canonical model exists.

CEA operational identity:

- CEA ActivityID or SeqNr;
- source organisation;
- source system.

Preserve local decisions across re-import:

- importance;
- target audiences;
- reviewed status;
- local notes;
- anchor status;
- local recommendation;
- override decisions.

CEA imports must not overwrite these local decisions.

CEA import must support:

- preview;
- validation;
- recognised columns;
- row-level errors;
- create;
- update;
- unchanged;
- conflict;
- removed-from-CEA;
- idempotent re-import;
- batch audit;
- import timestamp;
- imported by;
- source date range.

Required fields may include:

- SeqNr;
- Name;
- Start date;
- Start time;
- End date;
- End time;
- Unit;
- Location;
- Activity Notes;
- ActivityID;
- nomination dates;
- status;
- linked unit;
- include-child-unit where available.

Consolidate Activity and CeaActivity carefully.

Preferred outcome:

- Activity is the operational canonical record;
- a CEA import row or staging record may exist for review and provenance;
- CeaActivity must not remain a second operational calendar source.

Do not drop the old model in this release.

Create a compatibility and migration plan.

Audience filters:

- Staff Only;
- Seniors;
- Junior leaders;
- First Year cadets;
- All.

Use AAFC-appropriate rank descriptions in help text.

Activity priority:

1. Must attend;
2. Key event;
3. Weekly Parade;
4. Optional;
5. Noting;
6. Irrelevant.

Show:

- current as-at date;
- activity coverage end date;
- source;
- last import;
- new or changed on CEA;
- removed from CEA;
- reviewed status.

Inheritance:

- National activity appears nationally, at all Wings and all Squadrons;
- Wing activity appears at the Wing and subordinate Squadrons;
- Squadron activity remains local;
- inherited activity is read-only at subordinate scope;
- owner edits propagate;
- owner archive removes it from active subordinate views;
- no copied duplicates.

Anchor events:

- identify Must Attend and Key Events;
- allow anchor designation;
- show preparation requirements;
- support rule-based preparation recommendations;
- explain why each recommendation was generated;
- retain manual override.

======================================================================
11. UNIFIED TRAINING CALENDAR
======================================================================

Create one backend calendar projection.

It must combine:

- Parade Nights;
- Squadron activities;
- Wing activities;
- National activities;
- inherited activities;
- holidays;
- stand-down periods;
- notices;
- deadlines;
- anchor events.

Each projected calendar item must include:

- stable source ID;
- source type;
- title;
- start;
- end;
- all-day status;
- owning level;
- owning organisation;
- inherited source;
- target audience;
- status;
- importance;
- archive status;
- authoritative detail route.

Scope rules:

Squadron:

- own Parade Nights;
- own activities;
- inherited Wing activities;
- inherited National activities;
- holidays;
- relevant notices and deadlines.

Wing:

- subordinate Squadron Parade Nights;
- subordinate Squadron activities;
- own Wing activities;
- inherited National activities;
- holidays;
- Wing notices and deadlines.

National:

- all Squadron records;
- all Wing records;
- National records;
- holidays;
- National notices and deadlines.

System Administrator:

- everything;
- filters for level, Wing, Squadron, source and record type.

Opening Calendar must default to today.

Filters:

- Training Year;
- date range;
- Wing;
- Squadron;
- target audience;
- source;
- type;
- status;
- importance;
- inherited/local;
- archived where authorised.

Selecting a calendar item must open the authoritative record.

Do not open detached copies.

List and calendar views must agree.

Add contract tests for event counts and source IDs.

======================================================================
12. MISSION BACKLOG AND SESSION STATUS
======================================================================

Create one canonical session lifecycle.

Proposed states:

- not_planned;
- partially_planned;
- ready;
- delivered;
- cancelled;
- not_delivered;
- rescheduled;
- archived.

Define transitions explicitly.

Do not use session existence alone to decide that a mission is scheduled.

Cancelled and not-delivered sessions must remain in the Mission Backlog until:

- rescheduled;
- deliberately resolved;
- archived through an authorised process.

Store:

- original Parade Night;
- original session;
- outcome;
- reason;
- notes;
- rescheduled target;
- actor;
- timestamp.

Provide quick outcome actions:

- Mark delivered;
- Cancelled;
- Not delivered;
- Reschedule.

Provide preset reasons:

- facilitator unavailable;
- weather;
- venue unavailable;
- equipment unavailable;
- insufficient numbers;
- higher-priority activity;
- time lost;
- safety;
- administrative requirement;
- other.

Other requires a note.

Provide:

- Mark all delivered;
- then allow exceptions.

Make this phone-friendly.

Do not force users to open every session individually.

Mission Backlog columns should use one font, one scale and consistent spacing.

Replace `Core` with:

- Foundation;
- Extension;
- Optional.

Remove the standalone Import Review from Mission Backlog only after all import
review functionality is integrated into Activities and parity is proven.

Preserve an old-route redirect.

Non-syllabus missions must be supported as first-class session content.

Seed or support:

- Admin Parade;
- Nominations and CEA Admin;
- Activity Preparation;
- Activity Briefing;
- Activity Debrief;
- Activity Day;
- Guest Speaker;
- Term Briefing;
- Recruit Admin;
- Catch-Up Session;
- Team Building;
- Assessment or Review;
- No home parade — holiday;
- No home parade — activity.

Do not hardcode these so they cannot be extended.

Use scoped reference data.

Long Range View:

- selectable range from one week to one year;
- includes weekly Parade Nights and activities;
- includes warnings;
- includes notes and deadlines;
- supports filters;
- supports direct navigation to the mission;
- reflects canonical schedule state immediately.

Weekly Program:

- shows one or more selected Parade Nights;
- contains lessons, facilitators, Training Areas, equipment and links;
- includes key notices at the top;
- includes upcoming activities and deadlines;
- supports notes created well in advance;
- supports print/PDF-friendly output;
- does not depend on screenshots as the only sharing method.

======================================================================
13. FACILITATORS
======================================================================

Use the canonical Facilitator record.

Do not create a second Facilitator table.

Facilitators include:

- staff;
- cadet facilitators;
- external presenters;
- supervised trainees where authorised.

Fields:

- name;
- person type;
- rank or role;
- facilitator type;
- Subject Areas;
- Training Stages;
- qualifications;
- experience;
- prior delivered sessions;
- scheduled sessions;
- availability;
- leave;
- maximum preferred load;
- maximum authorised load;
- supervision requirement;
- supervising adult where required;
- active status;
- scope;
- audit history.

A facilitator created or edited in either frontend must appear in the other.

Diagnose current non-appearance by checking:

- write commit;
- returned UUID;
- active-status default;
- scope filter;
- Training Year filter;
- endpoint used;
- frontend cache;
- query invalidation;
- archived filter;
- browser request;
- rendered DOM.

Do not fix this by creating another copy.

After every facilitator write:

- update current state;
- invalidate affected queries;
- refetch Facilitators;
- refetch relevant schedules;
- refetch workload;
- refetch conflicts;
- refetch Dashboard summaries.

Facilitator dashboard statistics:

- active facilitators;
- staff facilitators;
- cadet facilitators;
- sessions scheduled;
- sessions delivered;
- upcoming assignments;
- unavailable facilitators;
- overbooked facilitators;
- uncovered Subject Areas;
- median and range of workload;
- supervision requirements.

Charts:

1. Workload timeline
   - week;
   - month;
   - term;
   - semester;
   - year;
   - zoom and date range;
   - scheduled;
   - ready;
   - delivered;
   - cancelled;
   - not delivered;
   - rescheduled.

2. Subject Area coverage
   - number of facilitators by Subject Area;
   - number by Facilitator Type;
   - authorised stage coverage;
   - uncovered capability.

3. Workload distribution
   - identify concentration;
   - identify single-person dependency;
   - identify overuse;
   - identify unused capability.

Do not rely on colour alone.

Use labels, patterns, icons or shapes.

The same summary information must feed Squadron Dashboard.

Wing, National and System dashboards aggregate and compare it.

======================================================================
14. TRAINING AREAS AND EQUIPMENT
======================================================================

Consolidate Rooms, Locations and Training Areas into the canonical concept:

`Training Area`

Do not perform destructive table deletion during this remediation.

Audit:

- TrainingArea;
- PlanningLocation;
- every foreign key;
- every session reference;
- every conflict;
- every import;
- every frontend use.

Training Area fields:

- id;
- name;
- code;
- area type;
- environment;
- capacity;
- owning organisation;
- active status;
- capabilities;
- accessibility notes;
- restrictions;
- fixed equipment;
- availability;
- maintenance state;
- notes.

Recommended actual-environment values:

- indoor;
- outdoor;
- mixed.

Lesson location requirement is separate:

- indoor only;
- outdoor only;
- either indoor or outdoor;
- both indoor and outdoor.

Do not use the same enum for both concepts.

Training Area capability tags may include:

- classroom;
- drill;
- field skills;
- aviation;
- briefing;
- computer;
- practical;
- ceremonial;
- physical training;
- catering;
- storage.

Equipment:

- canonical item;
- category;
- quantity;
- serviceable quantity;
- unavailable quantity;
- owning organisation;
- storage Training Area;
- fixed or portable;
- booking;
- maintenance;
- archive status.

Migration:

1. Normalise names only for comparison.
2. Match by organisation and strong identifiers.
3. Auto-map only unambiguous matches.
4. Produce a report for ambiguous records.
5. Do not merge ambiguous records.
6. Populate canonical foreign keys.
7. preserve old IDs through a mapping table.
8. add compatibility adapters.
9. update both frontends.
10. update conflicts.
11. verify historical schedules.
12. leave destructive retirement for separate approval.

Conflict detection:

- same facilitator;
- same Training Area;
- insufficient capacity;
- equipment shortage;
- equipment maintenance;
- facilitator workload;
- facilitator availability;
- stage-suitability mismatch;
- holiday conflict.

Allow authorised override only with:

- reason;
- visible warning;
- actor;
- timestamp;
- audit record.

Warning explanations must work through mouse, keyboard and touch.

Do not rely on hover only.

======================================================================
15. READINESS AND DASHBOARD TRUST
======================================================================

Create one backend readiness service.

Every readiness widget must consume the same result.

Do not separately calculate readiness in each frontend.

A session cannot be ready merely because it exists.

A session is READY only where all applicable conditions are met:

- active session;
- content or mission assigned;
- facilitator assigned;
- facilitator authorised or supervised;
- Training Area assigned where required;
- equipment available where required;
- resource or lesson link available where required;
- no unresolved critical conflict;
- timing valid.

A non-syllabus session may have different resource requirements.

The rule must be explicit and testable.

Readiness output must provide:

- total required sessions;
- ready sessions;
- partially planned sessions;
- not planned sessions;
- missing lesson count;
- missing facilitator count;
- missing area count;
- missing equipment count;
- missing resource count;
- critical conflict count;
- percentage;
- reason list.

Zero required sessions means:

`Not planned`

It does not mean:

- 100% ready;
- fully staffed;
- complete.

Avoid empty-array truth errors.

The "Tonight" panel must always be date-scoped.

Period controls must not silently alter Tonight.

Make the scope of each control visible.

Disambiguate:

- Lesson or Outcome;
- Facilitator;
- Training Area;
- Equipment;
- Readiness.

Do not display "Unassigned" beside an assigned facilitator without explaining
which field is unassigned.

Fix chart failures.

Inspect:

- endpoint status;
- payload schema;
- null values;
- date formats;
- empty arrays;
- chart-library initialisation;
- repeated render lifecycle;
- canvas or container size;
- stale element references;
- frontend exceptions.

Add schema and rendering tests.

Progress by phase:

- begin with the complete applicable Training Stage registry;
- left-join progress;
- display zero-progress phases;
- respect scope;
- respect Training Year;
- do not omit empty phases.

Delivery:

- always display numerator and denominator;
- e.g. 8 of 25;
- show percentage second;
- identify low sample size;
- treat weeks with no scheduled sessions as "No scheduled training", not 0%.

Unknown and missing reasons:

- visually separate from real categories;
- label as "Needs data";
- link to affected sessions;
- never present as a normal phase;
- never hide them.

Merge Training Summary into Dashboard.

Before removing the separate tab:

- inventory every summary;
- inventory every filter;
- inventory every link;
- reproduce every useful function on Dashboard;
- add parity tests;
- add route redirect.

Dashboard sections should lead to action.

Use Needs Attention as the common action queue for:

- unplanned sessions;
- missing facilitator;
- missing area;
- missing equipment;
- missing outcome;
- missing cancellation reason;
- unresolved conflict;
- stale CEA import;
- incomplete setup.

Facilitator workload must be prominent.

Include cadet-facilitated and cadet-under-supervision delivery.

Higher-level dashboards:

Wing:

- same core Squadron metrics;
- comparison by Squadron;
- drill-down;
- summed numerators and denominators;
- readiness matrix;
- workload and capability comparison;
- unresolved risk.

National:

- same hierarchy;
- Wing and Squadron comparison;
- disclose active beta population;
- do not imply complete national coverage where only 7 Wing is active.

System Administrator:

- every available dashboard;
- scope filter;
- data-confidence indicator;
- system-wide operational summary.

======================================================================
16. AUTHENTICATION, REFRESH AND DATA FRESHNESS
======================================================================

Preserve the documented authentication architecture unless evidence supports a
deliberate change.

Primary:

- sessionStorage bearer token.

Fallback:

- secure `aafc_session` cookie for cross-frontend handoff.

Do not tighten SameSite without end-to-end browser verification.

Do not misdiagnose direct API-login test behaviour as product refresh failure.

Reproduce using each frontend's real login form.

Normal browser refresh must remain authenticated.

Startup sequence:

1. load application shell;
2. enter authentication-check state;
3. read sessionStorage token;
4. where absent, attempt cookie-backed `/api/auth/me`;
5. wait for a definitive auth result;
6. restore account, role and scope;
7. restore valid Training Year;
8. render authorised page;
9. show login only for actual invalid, expired, revoked or absent session.

Do not clear authentication because:

- frontend memory reset;
- one data request failed;
- backend was temporarily unavailable;
- `/api/auth/me` was slow;
- chart data failed;
- Activities failed.

Test:

- normal refresh;
- hard refresh;
- new tab;
- Main TMS to Planning Workspace;
- Planning Workspace to Main TMS;
- direct deep link;
- browser back;
- browser forward;
- temporary outage;
- session expiry;
- disabled account;
- archived account;
- role change;
- scope change;
- Proxy Mode refresh;
- Intervention Mode refresh.

Data freshness:

Add a consistent page-level Refresh action to every primary page.

It must:

- refetch the current page;
- not reload the browser;
- preserve filters;
- preserve scope;
- preserve Training Year;
- preserve calendar date;
- preserve scroll or selection where reasonable;
- show Refreshing;
- show Updated at;
- show failure;
- allow Retry;
- be keyboard accessible;
- be screen-reader announced.

After writes:

- invalidate affected data;
- update local state;
- refetch dependent summaries;
- refetch calendar;
- refetch Dashboard;
- refetch other frontend data when next opened.

Refetch on:

- browser focus;
- network reconnection;
- scope change;
- Training Year change;
- Proxy entry and exit;
- Intervention entry and exit.

Use bounded refresh intervals only where operationally useful.

Do not poll every endpoint continuously.

Cancel stale in-flight requests when the user changes scope, page or year.

Include record `updated_at` and response freshness metadata where required.

======================================================================
17. API ERRORS AND 403 RESPONSES
======================================================================

Do not display every failure as "Cannot reach the backend".

Classify:

- transport/network failure;
- timeout;
- cancellation;
- 401 authentication required;
- 403 permission denied;
- 404 record unavailable;
- 409 conflict;
- 422 validation;
- 429 rate limited;
- 500 internal error;
- 502/503/504 temporary service error;
- invalid response.

For 403:

1. identify the route;
2. identify intended role;
3. identify target scope;
4. identify whether the action is:
   - own-scope write;
   - subordinate read;
   - Proxy write;
   - Intervention write;
   - prohibited operation.
5. inspect the permission helper;
6. use the correct tenancy and mode-aware helper;
7. do not broaden global permission;
8. return an actionable explanation.

Examples:

- "Enter Proxy Mode for 703 Squadron before editing this record."
- "You can view this Squadron but cannot modify it."
- "This record belongs to another Wing."
- "Your Intervention session has expired."

Test backend enforcement directly.

Frontend hiding is not sufficient.

======================================================================
18. ROLE PARITY, PROXY AND INTERVENTION
======================================================================

Update the complete role matrix.

Roles include:

- system_admin;
- national_admin;
- national_viewer;
- wing_admin;
- wing_viewer;
- sqn_admin;
- sqn_general;
- auditor.

Higher command access principle:

- they retain the underlying Squadron views and functions;
- they gain broader visibility and comparison;
- read-only inspection does not require an acting mode;
- protected subordinate writes require Proxy or Intervention where designed.

Verify every role through a real staging account.

Do not retrieve existing access codes.

Use dedicated staging verification accounts created through the authorised
workflow.

Proxy Mode:

- Wing Administrator;
- subordinate Squadron only;
- mandatory reason;
- visible banner;
- exact target;
- protected write;
- audit;
- exit;
- post-exit denial.

Intervention Mode:

- National or System authority as designed;
- mandatory reason;
- exact Wing or Squadron;
- visible banner;
- protected write;
- audit;
- exit;
- post-exit denial.

Test:

- refresh;
- logout;
- target switch;
- altered UUID;
- archived target;
- expired session;
- unrelated Wing;
- direct API attempt.

======================================================================
19. SYSTEM ADMINISTRATOR ACCOUNTS AND ORGANISATIONS
======================================================================

System Administrator Account Management must render:

- Name;
- Role;
- Scope;
- Unit;
- Status;
- Last Login;
- Code Last Changed;
- Actions.

Actions:

- Edit;
- change role;
- change access type;
- change scope;
- reset access code;
- disable;
- reactivate;
- archive;
- restore;
- safe permanent delete.

Changing role or scope:

- validate combination;
- preview effect;
- mandatory reason where appropriate;
- revoke sessions;
- increment token version;
- require reauthentication;
- audit old and new values.

Protect the final active System Administrator.

Do not reveal existing access codes.

Reset codes are one-time display only.

Account ordering:

1. System;
2. National;
3. Wing;
4. Squadron;
5. Flight grouping where used for display, not tenancy.

Within organisation:

- numeric Wing/Squadron code;
- Administrator;
- Viewer or General;
- Auditor/read-only;
- display name.

Do not sort by creation date by default.

Organisation management:

- edit;
- archive;
- restore;
- parent correction where safe;
- dependency-protected permanent delete.

Do not treat Flight as a tenancy level.

Permanent delete of Wing or Squadron must be blocked when linked to:

- subordinate organisation;
- account;
- cadet;
- Parade Night;
- session;
- activity;
- facilitator;
- Training Area;
- equipment;
- Planning Year;
- audit;
- historical record.

Provide guided archive instead.

======================================================================
20. LEARNING HUB LINKS
======================================================================

Fix Learning Hub links at the source.

Do not link to a generic completion page.

Each experiential or mission must resolve to its actual Learning Hub resource.

Audit:

- imported URL;
- curriculum URL;
- module code;
- part identifier;
- parent code;
- generated URL;
- displayed URL;
- Weekly Program link;
- Mission Backlog link;
- Dashboard link.

Determine whether incorrect links result from:

- using the wrong module parent;
- truncating the code;
- stale imported URLs;
- generating URLs from an identifier that does not match Learning Hub;
- completion-page links supplied in source data;
- frontend fallback.

Prefer an exact authoritative URL stored with the experiential.

Do not invent a URL where the mapping is uncertain.

Provide:

- validation report;
- broken-link indicator;
- admin correction;
- bulk correction import;
- no silent redirect to a generic page.

Where Learning Hub requires authentication, verify the target pattern without
exposing credentials.

======================================================================
21. VISUAL DESIGN, LANGUAGE AND ACCESSIBILITY
======================================================================

Planning Workspace must feel like part of the same TMS.

Do not make it identical merely by copying CSS.

Create shared visual rules:

- typography;
- spacing;
- headings;
- buttons;
- form labels;
- cards;
- tables;
- loading states;
- empty states;
- warnings;
- errors;
- filters;
- navigation;
- status indicators.

Use existing AAFC Visual Identity guidance.

Be restrained.

Prioritise readability and operational clarity.

Warnings must state:

- what is wrong;
- where;
- why it matters;
- affected record;
- recommended action;
- whether override is allowed.

Do not depend on colour alone.

Hover information must also work by:

- keyboard focus;
- click or tap;
- screen reader.

Replace native `alert`, `confirm` and `prompt` for operational actions with
accessible application dialogs.

Maintain mandatory confirmation and reason fields.

Mission Backlog typography must be consistent.

Use plain language.

Standard terms:

- Training Year;
- Parade Night;
- Training Stage;
- Session;
- Activity;
- Mission Backlog;
- Facilitator;
- Subject Area;
- Training Area;
- Equipment;
- Holiday;
- Notice;
- Deadline;
- Archive;
- Restore.

Remove legacy terms from user-facing navigation only after mapped replacements
exist and deep links are preserved.

Accessibility gates:

- zero critical axe violations;
- zero serious axe violations;
- WCAG AA contrast;
- keyboard navigation;
- visible focus;
- accessible names;
- error association;
- mobile usability;
- no colour-only information.

======================================================================
22. GETTING STARTED
======================================================================

Create one guided setup workflow.

Steps:

1. Confirm organisation.
2. Confirm Training Year.
3. Configure Squadron Details.
4. Configure Parade Day.
5. Configure Session Structure.
6. Configure Timing Template.
7. Add or import holidays.
8. Review inherited National and Wing activities.
9. Import or add local activities.
10. Set activity priority and audiences.
11. Add facilitators.
12. Add Training Areas.
13. Add equipment.
14. Generate Parade Nights.
15. Review anchor events.
16. Review warnings.
17. Publish initial program.

Show status:

- complete;
- incomplete;
- inherited;
- not configured;
- requires review;
- blocked.

Each step must open the authoritative page.

Do not duplicate settings inside the setup wizard.

======================================================================
23. OPERATIONS, CAPACITY AND SUPPORT
======================================================================

Current practical trial requirement:

- at least 12 simultaneous users.

Test staging at:

- 12 concurrent authenticated users;
- 25 concurrent authenticated users as safety margin.

Use realistic workflows:

- login;
- Dashboard;
- Calendar;
- Activities;
- Planning;
- Weekly Program;
- facilitator reads;
- low-frequency safe writes.

Record:

- response success;
- p50;
- p95;
- p99;
- 4xx by category;
- 5xx;
- timeouts;
- CPU;
- memory;
- database connections.

Do not run load tests against production.

Document:

- Railway project ownership;
- billing ownership;
- operational owner;
- backup owner;
- recovery contact;
- deployment runbook;
- access continuity if Gen is unavailable.

Do not print secret values.

Audit environment variables for:

- duplicate names;
- stale Render references;
- stale Supabase references;
- wrong API base;
- staging/production crossover;
- unused variables;
- contradictory variables.

Record variable names and purpose only.

Monitoring:

- backend health;
- readiness;
- 5xx;
- login failure;
- latency;
- database connections;
- worker restart;
- frontend errors where available.

Create actionable thresholds appropriate to the 12–25-user trial.

Do not claim zero downtime with one replica.

======================================================================
24. REQUIRED AUTOMATED TESTS
======================================================================

Backend:

- canonical Parade Night integration;
- canonical Activity integration;
- CEA import idempotency;
- preservation of local activity decisions;
- calendar projection;
- Training Area migration mapping;
- Equipment availability;
- facilitator create/read/update across endpoints;
- session lifecycle;
- Mission Backlog;
- readiness;
- zero-session readiness;
- all phases including zero;
- Planning Year lifecycle;
- Parade Night generation;
- holiday conflict;
- timing-template precedence;
- reference-data inheritance;
- account role/scope change;
- organisation deletion protection;
- permission helpers;
- Proxy;
- Intervention;
- IDOR;
- Learning Hub mapping;
- API error classification.

Main TMS:

- real login;
- refresh persistence;
- Dashboard;
- chart rendering;
- Activities;
- Calendar;
- Parade Nights;
- Facilitators;
- Account Management;
- scope and role visibility;
- Refresh action;
- route compatibility.

Planning Workspace:

- real login/cookie handoff;
- refresh persistence;
- Training Year;
- Parade Nights;
- Activities;
- Mission Backlog;
- Long Range;
- Weekly Program;
- Facilitators;
- Training Areas;
- Equipment;
- Holidays;
- Notices;
- conflict warnings;
- accessible dialogs;
- Refresh action.

Cross-interface E2E:

1. Main TMS Parade Night → Planning Workspace.
2. Planning Workspace edit → Main TMS.
3. Main TMS facilitator → Planning Workspace.
4. Planning Workspace facilitator edit → Main TMS.
5. Activity inheritance National → Wing → Squadron.
6. Activity inheritance Wing → Squadron.
7. CEA import re-import preserves local decisions.
8. Training Area appears identically in both.
9. Equipment change appears identically in both.
10. Holiday appears in generation preview and Calendar.
11. Notice appears in Weekly Program.
12. Outcome change updates Mission Backlog and Dashboard.
13. Cancel and reschedule.
14. Browser refresh remains authenticated.
15. Page Refresh preserves state.
16. higher-level drill-down.
17. Proxy write.
18. Intervention write.
19. 403 outside authority.
20. archived records hidden and restorable.

Accessibility:

- every principal route;
- all supported browsers;
- mobile viewport;
- no critical or serious violations.

======================================================================
25. STAGED IMPLEMENTATION ORDER
======================================================================

Use this order.

Stage 0:

- ground rules;
- baseline;
- capability manifest;
- gap register;
- key/variable inventory.

Stage 1:

- canonical domain map;
- API contracts;
- duplicate-model migration designs.

Stage 2:

- authentication hydration;
- refresh;
- error classification;
- stale-data invalidation.

Stage 3:

- Training Stage, Facilitator Type and Subject Area reference data.

Stage 4:

- Squadron Details;
- Timing Templates;
- Parade Night generation and editing.

Stage 5:

- Parade Night cross-interface synchronisation;
- Planning Year lifecycle.

Stage 6:

- Activities;
- CEA;
- Holidays;
- anchors;
- unified Calendar.

Stage 7:

- Mission Backlog;
- status lifecycle;
- Long Range;
- Weekly Program;
- notices.

Stage 8:

- Facilitators;
- Training Areas;
- Equipment;
- conflicts.

Stage 9:

- readiness;
- dashboards;
- charts;
- higher-level parity;
- Training Summary migration.

Stage 10:

- Accounts;
- organisations;
- Proxy;
- Intervention;
- 403 corrections.

Stage 11:

- Learning Hub links;
- terminology;
- accessibility;
- visual consistency.

Stage 12:

- capacity;
- monitoring;
- complete regression;
- staging deployment;
- authenticated staging verification.

Do not start destructive data consolidation before migration and rollback plans
exist.

======================================================================
26. STAGING DEPLOYMENT
======================================================================

Deploy exact tested commits to staging only.

Before every Railway command verify:

- project;
- environment;
- service;
- intended SHA;
- intended domain;
- intended backend;
- intended database.

Verify:

- no localhost;
- no production backend from staging;
- no staging request from production;
- correct migration;
- correct build fingerprint.

Use authenticated staging accounts for every role.

Do not use production credentials.

Do not deploy production.

======================================================================
27. FINAL EVIDENCE
======================================================================

Return a final report containing:

- branch;
- exact HEAD;
- commits;
- capability diff;
- models consolidated;
- compatibility paths retained;
- migrations;
- reference keys consolidated;
- environment variables consolidated;
- bugs reproduced;
- root causes;
- fixes;
- backend tests;
- Main TMS tests;
- Planning Workspace tests;
- cross-interface tests;
- role tests;
- accessibility tests;
- capacity test;
- staging deployment IDs;
- build fingerprints;
- authenticated staging results;
- every gap-register status;
- unresolved blockers;
- residual risks;
- items requiring explicit future removal approval.

Include a final table:

| Gap ID | Requirement | Root cause | Correction | Automated evidence | Staging evidence | Status |

No item may disappear from the register.

Final line must be exactly one of:

ALL REGISTERED GAPS CLOSED AND VERIFIED ON STAGING

STAGING VERIFIED — RESIDUAL LIMITATIONS RECORDED

or:

REMEDIATION BLOCKED — UNRESOLVED CRITICAL GAPS
