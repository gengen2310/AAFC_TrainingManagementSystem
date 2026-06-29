# Role matrix

| Capability | sqn_general | sqn_admin | wing_viewer | wing_admin | national_viewer | national_admin | system_admin | auditor |
|---|---|---|---|---|---|---|---|---|
| View own squadron | ✓ | ✓ | ✓ (in wing) | ✓ (in wing) | ✓ | ✓ | ✓ | ✓ |
| View other squadron | ✗ | ✗ | wing only | wing only | ✓ | ✓ | ✓ | ✓ |
| Edit own squadron | ✗ | ✓ | ✗ | via Proxy | ✗ | via Intervention | via Intervention | ✗ |
| View cadets / sensitive notes | ✗ / ✗ | ✓ / ✓ | ✓ / ✗ | ✓ / ✓ | ✓ / ✗ | ✓ / ✓ | ✓ / ✓ | ✗ / ✗ |
| Wing overview | ✗ | ✗ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| National overview | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ | ✓ | ✓ |
| Read audit | own | own | wing | wing | all | all | all | all |
| Reset access codes | ✗ | own sqn | ✗ | own wing | ✗ | ✓ | ✓ | ✗ |
| **System Console access** | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ |
| **Maintenance mode** | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ |
| **Platform backup** | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ |
| **Full scope map** | ✗ | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | ✗ |

Cross-level edits always require a reason and produce an audit entry.

---

## V6 — Account creation authority

| Creator role | May create accounts with role |
|---|---|
| `system_admin` | `system_admin`, `national_admin`, `national_viewer`, `auditor`, `wing_admin`, `wing_viewer`, `sqn_admin`, `sqn_general` |
| `national_admin` | `national_admin`, `national_viewer`, `auditor`, `wing_admin`, `wing_viewer`, `sqn_admin`, `sqn_general` |
| `wing_admin` | `wing_viewer`, `sqn_admin`, `sqn_general` — own Wing only |
| `sqn_admin` | `sqn_general` — own Squadron only |
| `national_viewer`, `wing_viewer`, `sqn_general`, `auditor` | Cannot create accounts (403) |

Scope enforcement is backend-authoritative. Wing admin is limited to their own Wing and its Squadrons. SQN admin is limited to their own Squadron.

## V6 — Flight assignment rules

A Flight is a local Squadron display grouping only.

| Rule | Detail |
|---|---|
| Flight scope | Must belong to the same Squadron as the account |
| Flight and permissions | Flight assignment does NOT change RBAC or tenancy |
| Flight and scope | Squadron-scoped users only (`sqn_admin`, `sqn_general`) |
| Standalone Flight accounts | Not permitted |
| Archive behaviour | Archiving a flight clears `flight_id` from all assigned users |


## V11 — TRGO Planning Module access

| Action | sqn_general | sqn_admin | wing_viewer | wing_admin | national_viewer | national_admin | system_admin | auditor |
|--------|-------------|-----------|-------------|------------|-----------------|----------------|--------------|---------|
| View planning years | ✗ | own unit | wing only | own wing | all | all | all | all |
| Create / edit planning year | ✗ | own unit | ✗ | own wing | ✗ | all | all | ✗ |
| View parade dates | ✗ | own unit | wing only | own wing | all | all | all | all |
| Add / delete parade dates | ✗ | own unit | ✗ | own wing | ✗ | all | all | ✗ |
| View holidays | ✗ | own unit | wing only | own wing | all | all | all | all |
| Add / delete holidays | ✗ | own unit | ✗ | own wing | ✗ | all | all | ✗ |
| View anchor events | ✗ | own unit | wing only | own wing | all | all | all | all |
| Create / edit / archive anchors | ✗ | own unit | ✗ | own wing | ✗ | all | all | ✗ |
| View sessions / term planner | ✗ | own unit | wing only | own wing | all | all | all | all |
| Create / edit / delete sessions | ✗ | own unit | ✗ | own wing | ✗ | all | all | ✗ |
| View weekly program | ✗ | own unit | wing only | own wing | all | all | all | all |
| Manage locations | ✗ | own unit | ✗ | own wing | ✗ | all | all | ✗ |
| View facilitators (planning) | ✗ | own unit | wing only | own wing | all | all | all | all |
| Run conflict checks | ✗ | own unit | ✗ | own wing | ✗ | all | all | ✗ |
| Override conflict | ✗ | own unit | ✗ | own wing | ✗ | all | all | ✗ |

All override actions require a non-empty reason and are audited.

## V12 — Curriculum tab access and Night Builder integration

| Action | sqn_general | sqn_admin | wing_viewer | wing_admin | national_viewer | national_admin | system_admin | auditor |
|--------|-------------|-----------|-------------|------------|-----------------|----------------|--------------|---------|
| View Curriculum tab (frontend) | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| View national curriculum | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| View wing curriculum | own wing | own wing | own wing | own wing | all | all | all | all |
| View squadron curriculum | own sqn | own sqn | wing | wing | all | all | all | all |
| Create squadron curriculum (`POST /api/curriculum`) | ✗ | own sqn | ✗ | via Proxy | ✗ | via Intervention | via Intervention | ✗ |
| Create wing curriculum (`POST /api/curriculum/wing`) | ✗ | ✗ | ✗ | own wing | ✗ | ✓ | ✓ | ✗ |
| Create national curriculum (`POST /api/curriculum/national`) | ✗ | ✗ | ✗ | ✗ | ✗ | ✓ | ✓ | ✗ |
| Night Builder — view (`GET /api/parade-nights/{id}/builder`) | ✗ | own unit | via Proxy | via Proxy | ✗ | via Intervention | via Intervention | ✗ |
| Night Builder — schedule session (real `Session`) | ✗ | own unit | ✗ | via Proxy | ✗ | via Intervention | via Intervention | ✗ |
