# Import templates

## Cadets (CSV) — implemented (preview + commit + rollback)
```
service_number,rank,first_name,last_name,phase,attendance_percentage
8000010,CDT,Sam,Taylor,Initial,88
```
Rules: `last_name` required; cells beginning `= + - @` are neutralised; each commit writes an
`ImportLog` + audit entry; rollback soft-archives imported rows.

## Other types (facilitators, attendance, activities, parade dates, resources, training areas)
Preview/column-detection share the same endpoint; typed commit handlers are later-milestone
TODOs following the cadet pattern.
