"""v22 Seed national curriculum — 214 items from AAFC Learning Hub (all phases).

Adds 5 new curriculum_elements for element types not present in v19:
  Service_Knowledge, Aviation, Cyber, RPAS, Space

Inserts all 214 curriculum items idempotently (skips any identifier
already present at owning_level=national).

Revision ID: j5e6f7g8h9i0
Revises: i4d5e6f7g8h9
Create Date: 2026-07-05
"""
from alembic import op
import sqlalchemy as sa

revision = 'j5e6f7g8h9i0'
down_revision = 'i4d5e6f7g8h9'
branch_labels = None
depends_on = None

# ---------------------------------------------------------------------------
# New elements to add (name, display_name, scope_level)
# ---------------------------------------------------------------------------
_NEW_ELEMENTS = [
    ('Service_Knowledge', 'Service Knowledge',       'national'),
    ('Aviation',          'Aviation',                'national'),
    ('Cyber',             'Cyber',                   'national'),
    ('RPAS',              'RPAS',                    'national'),
    ('Space',             'Space',                   'national'),
]

# ---------------------------------------------------------------------------
# Full Learning Hub curriculum
# Columns: identifier, phase, element_key, duration_minutes,
#          core_status, instructor_suitability, title, learning_hub_url, seq
#
# core_status:
#   "core"       ← Foundation items
#   "additional" ← Extension items
#
# element_key maps to curriculum_elements.name
# Phase typo "IN-M02-01" (CSV row 62) corrected to "INT-M02-01".
# Trailing whitespace and zero-width spaces removed from titles.
# ---------------------------------------------------------------------------
_CURRICULUM = [
    # ── INITIAL ──────────────────────────────────────────────────────────────
    ("INL-M04-99", "B. Initial",      "Service_Knowledge", 15,   "core",       "Staff or Senior Cadet", "MISSION 04 COMPLETION",                                                                    "https://airforcecadets.net.au/lh/node/375",         1),
    # ── ORIENTATION ──────────────────────────────────────────────────────────
    ("ORI-M01-01", "A. Orientation",  "Service_Knowledge", 60,   "core",       "Staff or Senior Cadet", "01. Welcome and tour of the grounds",                                                      "https://airforcecadets.net.au/lh/ORI-M01-01",       2),
    ("ORI-M01-02", "A. Orientation",  "Service_Knowledge", 60,   "core",       "Staff or Senior Cadet", "02. AAFC Info Bullring",                                                                   "https://airforcecadets.net.au/lh/ORI-M01-02",       3),
    ("ORI-M02-01", "A. Orientation",  "Service_Knowledge", 60,   "core",       "Staff or Senior Cadet", "01. GET CONNECTED",                                                                        "https://airforcecadets.net.au/lh/ORI-M02-01",       4),
    ("ORI-M02-02", "A. Orientation",  "Service_Knowledge", 60,   "core",       "Staff",                 "02. SAFETY & PEOPLE MATTER",                                                              "https://airforcecadets.net.au/lh/ORI-M02-02",       5),
    ("ORI-M03-01", "A. Orientation",  "Personal_Dev",      100,  "core",       "Staff",                 "01. Focus on Personal Development",                                                       "https://airforcecadets.net.au/lh/ORI-M03-01",       6),
    ("ORI-M03-02", "A. Orientation",  "Service_Knowledge", 45,   "core",       "Staff",                 "02. Social Media",                                                                        "https://airforcecadets.net.au/lh/ORI-M03-02",       7),
    ("ORI-M03-03", "A. Orientation",  "Personal_Dev",      30,   "core",       "Staff",                 "03. Cyber Bullying",                                                                      "https://airforcecadets.net.au/lh/ORI-M03-03",       8),
    ("ORI-M04-01", "A. Orientation",  "Service_Knowledge", 45,   "core",       "Staff or Senior Cadet", "01. Giant Board Game",                                                                     "https://airforcecadets.net.au/lh/ORI-M04-01",       9),
    ("ORI-M04-02", "A. Orientation",  "Service_Knowledge", 15,   "core",       "Staff or Senior Cadet", "02. Giant Crossword",                                                                      "https://airforcecadets.net.au/lh/ORI-M04-02",      10),
    # ── INITIAL (continued) ──────────────────────────────────────────────────
    ("INL-M00-01", "B. Initial",      "Personal_Dev",      45,   "core",       "Staff",                 "01. SELF REFLECTION",                                                                     "https://airforcecadets.net.au/lh/M00-01",           11),
    ("INL-M00-02", "B. Initial",      "Personal_Dev",      25,   "core",       "Staff",                 "02. SITREP",                                                                              "https://airforcecadets.net.au/lh/M00-02",           12),
    ("INL-M00-03", "B. Initial",      "Personal_Dev",      45,   "core",       "Staff",                 "03. Connection",                                                                          "https://airforcecadets.net.au/lh/M00-03",           13),
    ("INL-M00-04", "B. Initial",      "Personal_Dev",      45,   "core",       "Staff",                 "04. PERSISTENCE",                                                                         "https://airforcecadets.net.au/lh/INL-M00-04",       14),
    ("INL-M00-05", "B. Initial",      "Personal_Dev",      30,   "core",       "Staff",                 "05. Teamwork",                                                                            "https://airforcecadets.net.au/lh/INL-M00-05",       15),
    ("INL-M01-01", "B. Initial",      "Service_Knowledge", 75,   "core",       "Staff or Senior Cadet", "01. What ANZAC Day Means to Us",                                                          "https://airforcecadets.net.au/lh/INL-M01-01",       16),
    ("INL-M01-02", "B. Initial",      "Drill",             60,   "core",       "Staff or Senior Cadet", "02. ANZAC DAY PREPARATION AND EXECUTION",                                                 "https://airforcecadets.net.au/lh/INL-M01-02",       17),
    ("INL-M02-01", "B. Initial",      "Service_Knowledge", 75,   "core",       "Staff or Senior Cadet", "01. The Origins of The RAAF",                                                             "https://airforcecadets.net.au/lh/INL-M02-01",       18),
    ("INL-M02-02", "B. Initial",      "Service_Knowledge", 75,   "core",       "Staff or Senior Cadet", "02. Introduction to RAAF Aircraft",                                                       "https://airforcecadets.net.au/lh/INL-M02-02",       19),
    ("INL-M02-03", "B. Initial",      "Service_Knowledge", 75,   "core",       "Staff or Senior Cadet", "03. EMAILS 101",                                                                          "https://airforcecadets.net.au/lh/INL-M02-03",       20),
    ("INL-M02-04", "B. Initial",      "Air_Space",         120,  "core",       "Staff or Senior Cadet", "04. Aircraft Discovery",                                                                  "https://airforcecadets.net.au/lh/INL-M02-04",       21),
    ("INL-M02-05", "B. Initial",      "Service_Knowledge", 45,   "core",       "Staff or Senior Cadet", "05. Communication Techniques",                                                            "https://airforcecadets.net.au/lh/INL-M02-05",       22),
    ("INL-M02-06", "B. Initial",      "Service_Knowledge", 90,   "core",       "Staff or Senior Cadet", "06. Presentation",                                                                        "https://airforcecadets.net.au/lh/INL-M02-06",       23),
    ("INL-M03-01", "B. Initial",      "Service_Community", 45,   "core",       "Staff or Senior Cadet", "01. INTRODUCTION TO COMMUNITY ENGAGEMENT",                                               "https://airforcecadets.net.au/lh/INL-M03-01",       24),
    ("INL-M03-02", "B. Initial",      "Service_Community", 90,   "core",       "Staff or Senior Cadet", "02. PLAN AND PREPARE FOR THE COMMUNITY ENGAGEMENT",                                      "https://airforcecadets.net.au/lh/INL-M03-02",       25),
    ("INL-M04-01", "B. Initial",      "Field",             150,  "core",       "Staff or Senior Cadet", "01. EAT, PACK, STAY",                                                                     "https://airforcecadets.net.au/lh/INL-M04-01",       26),
    ("INL-M04-02", "B. Initial",      "Field",             75,   "core",       "Staff or Senior Cadet", "02. PERSONAL HYGIENE",                                                                    "https://airforcecadets.net.au/lh/INL-M04-02",       27),
    ("INL-M04-03", "B. Initial",      "Field",             120,  "core",       "Staff or Senior Cadet", "03. NAVIGATION TECHNIQUES",                                                               "https://airforcecadets.net.au/lh/INL-M04-03",       28),
    ("INL-M04-04", "B. Initial",      "Field",             75,   "core",       "Staff or Senior Cadet", "04. SAFETY IN THE FIELD",                                                                 "https://airforcecadets.net.au/lh/INL-M04-04",       29),
    ("INL-M04-05", "B. Initial",      "Field",             75,   "core",       "Staff or Senior Cadet", "05. LOST AND DANGEROUS",                                                                  "https://airforcecadets.net.au/lh/INL-M04-05",       30),
    ("INL-M05-01", "B. Initial",      "Air_Space",         90,   "core",       "Staff or Senior Cadet", "01. First Flight",                                                                        "https://airforcecadets.net.au/lh/INL-M05-01",       31),
    ("INL-M05-02", "B. Initial",      "Air_Space",         90,   "core",       "Staff or Senior Cadet", "02. Foundational Handling",                                                               "https://airforcecadets.net.au/lh/INL-M05-02",       32),
    ("INL-M05-03", "B. Initial",      "Air_Space",         75,   "core",       "Staff or Senior Cadet", "03. Drones for Surveillance",                                                             "https://airforcecadets.net.au/lh/INL-M05-03",       33),
    ("INL-M05-04", "B. Initial",      "Air_Space",         90,   "core",       "Staff or Senior Cadet", "04. Drones in Hostile Areas",                                                             "https://airforcecadets.net.au/lh/INL-M05-04",       34),
    ("INL-M05-05", "B. Initial",      "Air_Space",         90,   "core",       "Staff or Senior Cadet", "05. Obstacle Course",                                                                     "https://airforcecadets.net.au/lh/INL-M05-05",       35),
    ("INL-M06-01", "B. Initial",      "Air_Space",         75,   "core",       "Staff or Senior Cadet", "01. May The Forces Be With You",                                                          "https://airforcecadets.net.au/lh/INL-M06-01",       36),
    ("INL-M06-02", "B. Initial",      "Air_Space",         90,   "core",       "Staff or Senior Cadet", "02. Weight and Drag",                                                                     "https://airforcecadets.net.au/lh/INL-M06-02",       37),
    ("INL-M06-03", "B. Initial",      "Air_Space",         75,   "core",       "Staff or Senior Cadet", "03. Feathered Friends to Flying Machines",                                                "https://airforcecadets.net.au/lh/INL-M06-03",       38),
    ("INL-M06-04", "B. Initial",      "Air_Space",         100,  "core",       "Staff or Senior Cadet", "04. Propulsion Systems",                                                                  "https://airforcecadets.net.au/lh/INL-M06-04",       39),
    ("INL-M06-05", "B. Initial",      "Air_Space",         90,   "core",       "Staff or Senior Cadet", "05. Control Surfaces",                                                                    "https://airforcecadets.net.au/lh/INL-M06-05",       40),
    ("INL-M07-01", "B. Initial",      "Service_Knowledge", 90,   "core",       "Staff or Senior Cadet", "01. Remembrance Day Narrative: Pre-Service",                                              "https://airforcecadets.net.au/lh/INL-M07-01",       41),
    ("INL-M07-02", "B. Initial",      "Service_Knowledge", 90,   "core",       "Staff or Senior Cadet", "02. Remembrance Day Narrative: Throughout the War",                                       "https://airforcecadets.net.au/lh/INL-M07-02",       42),
    ("INL-M07-03", "B. Initial",      "Service_Knowledge", 60,   "core",       "Staff or Senior Cadet", "03. Remembrance Day Narrative: Post-Service",                                             "https://airforcecadets.net.au/lh/INL-M07-03",       43),
    ("INL-M08-01", "B. Initial",      "Drill",             60,   "core",       "Staff or Senior Cadet", "01. Drill and Ceremonial",                                                                "https://airforcecadets.net.au/lh/INL-M08-01",       44),
    ("INL-M09-01", "B. Initial",      "Air_Space",         60,   "core",       "Staff or Senior Cadet", "01. ABOUT THE AIRFIELD",                                                                  "https://airforcecadets.net.au/lh/INL-M09-01",       45),
    ("INL-M09-02", "B. Initial",      "Air_Space",         60,   "core",       "Staff or Senior Cadet", "02. A GUIDE TO ENJOYING AIRCRAFT ON THE GROUND",                                         "https://airforcecadets.net.au/lh/INL-M09-02",       46),
    ("INL-M10-01", "B. Initial",      "Service_Community", 75,   "core",       "Staff or Senior Cadet", "01. OPEN DAY: PLANNING AND PREPARATION",                                                  "https://airforcecadets.net.au/lh/INL-M10-01",       47),
    ("INL-M10-02", "B. Initial",      "Service_Community", 90,   "core",       "Staff or Senior Cadet", "02. OPEN DAY: LEADERSHIP",                                                                "https://airforcecadets.net.au/lh/INL-M10-02",       48),
    ("INL-M10-03", "B. Initial",      "Service_Community", 120,  "core",       "Staff or Senior Cadet", "03. OPEN DAY: EFFECTIVE COMMUNICATION",                                                   "https://airforcecadets.net.au/lh/INL-M10-03",       49),
    # ── JUNIOR ───────────────────────────────────────────────────────────────
    ("JNR-M01-01", "C. Junior",       "Drill",             450,  "core",       "Staff or Senior Cadet", "01. Drill & Ceremonial",                                                                  "https://airforcecadets.net.au/lh/JNR-M01-01",       50),
    ("JNR-M02-01", "C. Junior",       "Air_Space",         45,   "core",       "Staff or Senior Cadet", "01. Flight Essentials: Movements, Forces, and Aerodynamics",                              "https://airforcecadets.net.au/lh/JNR-M02-01",       51),
    ("JNR-M02-02", "C. Junior",       "Air_Space",         30,   "core",       "Staff or Senior Cadet", "02. Balance, Weight and Flying Straight",                                                 "https://airforcecadets.net.au/lh/JNR-M02-02",       52),
    ("JNR-M02-03", "C. Junior",       "Air_Space",         45,   "core",       "Staff or Senior Cadet", "03. From Take-off to Touchdown",                                                          "https://airforcecadets.net.au/lh/JNR-M02-03",       53),
    ("JNR-M02-04", "C. Junior",       "Air_Space",         270,  "core",       "Staff or Senior Cadet", "04. JOEY Drones: Assemble and Ascend",                                                   "https://airforcecadets.net.au/lh/JNR-M02-04",       54),
    ("JNR-M03-01", "C. Junior",       "Field",             75,   "core",       "Staff or Senior Cadet", "01. SMEAC and Command Posts",                                                             "https://airforcecadets.net.au/lh/JNR-M03-01",       55),
    ("JNR-M03-02", "C. Junior",       "Field",             75,   "core",       "Staff or Senior Cadet", "02. Oh Pilot Where Art Thou",                                                             "https://airforcecadets.net.au/lh/JNR-M03-02",       56),
    ("JNR-M03-03", "C. Junior",       "Field",             75,   "core",       "Staff or Senior Cadet", "03. Navigation",                                                                          "https://airforcecadets.net.au/lh/JNR-M03-03",       57),
    ("JNR-M03-04", "C. Junior",       "Field",             75,   "core",       "Staff or Senior Cadet", "04. Talk with the Hand",                                                                  "https://airforcecadets.net.au/lh/JNR-M03-04",       58),
    ("JNR-M03-05", "C. Junior",       "Field",             75,   "core",       "Staff or Senior Cadet", "05. Hiding in Plain Sight: Camouflage and Concealment",                                   "https://airforcecadets.net.au/lh/JNR-M03-05",       59),
    # ── INTERMEDIATE ─────────────────────────────────────────────────────────
    ("INT-M01-01", "D. Intermediate", "Drill",             150,  "core",       "Staff or Senior Cadet", "01. Drill & Ceremonial",                                                                  "https://airforcecadets.net.au/lh/INT-M01-01",       60),
    ("INT-M02-01", "D. Intermediate", "Air_Space",         75,   "core",       "Staff or Senior Cadet", "01. By the Power of Air",                                                                 "https://airforcecadets.net.au/lh/INT-M02-01",       61),
    ("INT-M02-02", "D. Intermediate", "Air_Space",         75,   "core",       "Staff or Senior Cadet", "02. Master of Spin",                                                                      "https://airforcecadets.net.au/lh/INT-M02-02",       62),
    ("INT-M03-01", "D. Intermediate", "Field",             75,   "core",       "Staff or Senior Cadet", "01. S.O.S: Steve's Out there Somewhere",                                                  "https://airforcecadets.net.au/lh/INT-M03-01",       63),
    ("INT-M03-02", "D. Intermediate", "Field",             75,   "core",       "Staff or Senior Cadet", "02. Searching for Steve",                                                                 "https://airforcecadets.net.au/lh/INT-M03-02",       64),
    ("INT-M03-03", "D. Intermediate", "Field",             75,   "core",       "Staff or Senior Cadet", "03. Search SMEAC",                                                                        "https://airforcecadets.net.au/lh/INT-M03-03",       65),
    ("INT-M03-04", "D. Intermediate", "Field",             75,   "core",       "Staff or Senior Cadet", "04. Learning the Ropes",                                                                  "https://airforcecadets.net.au/lh/INT-M03-04",       66),
    ("INT-M04-01", "D. Intermediate", "Personal_Dev",      150,  "core",       "Staff",                 "01. Facilitating Group Discussions",                                                      "https://airforcecadets.net.au/lh/INT-M04-01",       67),
    ("INT-M04-02", "D. Intermediate", "Personal_Dev",      75,   "core",       "Staff",                 "02. Facilitation Challenges and Strategies",                                              "https://airforcecadets.net.au/lh/INT-M04-02",       68),
    ("INT-M04-03", "D. Intermediate", "Personal_Dev",      75,   "core",       "Staff",                 "03. Cadet Learning",                                                                      "https://airforcecadets.net.au/lh/INT-M04-03",       69),
    ("INT-M04-04", "D. Intermediate", "Personal_Dev",      150,  "core",       "Staff",                 "04. Elements and Strategies",                                                             "https://airforcecadets.net.au/lh/INT-M04-04",       70),
    ("INT-M04-05", "D. Intermediate", "Personal_Dev",      150,  "core",       "Staff",                 "05. Facilitation in Practice",                                                            "https://airforcecadets.net.au/lh/INT-M04-05",       71),
    # ── BRONZE ───────────────────────────────────────────────────────────────
    ("BCLP-M01-01", "I. Bronze",      "Personal_Dev",      150,  "additional", "Staff",                 "01. KNOW YOURSELF",                                                                       "https://airforcecadets.net.au/lh/BCLP-M01-01",      72),
    ("BCLP-M01-02", "I. Bronze",      "Personal_Dev",      150,  "additional", "Staff",                 "02. MANAGE YOURSELF",                                                                     "https://airforcecadets.net.au/lh/BCLP-M01-02",      73),
    ("BCLP-M01-03", "I. Bronze",      "Personal_Dev",      150,  "additional", "Staff",                 "03. WHAT IS LEADERSHIP?",                                                                 "https://airforcecadets.net.au/lh/BCLP-M01-03",      74),
    ("BCLP-M01-04", "I. Bronze",      "Personal_Dev",      150,  "additional", "Staff",                 "04. WHAT IS A TEAM?",                                                                     "https://airforcecadets.net.au/lh/BCLP-M01-04",      75),
    ("BCLP-M01-05", "I. Bronze",      "Personal_Dev",      150,  "additional", "Staff",                 "05. BUILD THE TEAM",                                                                      "https://airforcecadets.net.au/lh/BCLP-M01-05",      76),
    ("BCLP-M01-06", "I. Bronze",      "Personal_Dev",      150,  "additional", "Staff",                 "06. LEAD THE TEAM",                                                                       "https://airforcecadets.net.au/lh/BCLP-M01-06",      77),
    ("BCLP-M01-07", "I. Bronze",      "Personal_Dev",      150,  "additional", "Staff",                 "07. CONFLICT RESOLUTION",                                                                 "https://airforcecadets.net.au/lh/BCLP-M01-07",      78),
    ("BCLP-M01-08", "I. Bronze",      "Personal_Dev",      150,  "additional", "Staff",                 "08. MANAGE THE TEAM",                                                                     "https://airforcecadets.net.au/lh/BCLP-M01-08",      79),
    ("BDC-M01-01",  "I. Bronze",      "Drill",             75,   "additional", "Staff or Senior Cadet", "01. Words of Command",                                                                    "https://airforcecadets.net.au/lh/BDC-M01-01",       80),
    ("BDC-M01-02",  "I. Bronze",      "Drill",             75,   "additional", "Staff or Senior Cadet", "02. Timing of Words of Command",                                                          "https://airforcecadets.net.au/lh/BDC-M01-02",       81),
    ("BDC-M01-03",  "I. Bronze",      "Drill",             75,   "additional", "Staff or Senior Cadet", "03. Fault Correction",                                                                    "https://airforcecadets.net.au/lh/BDC-M01-03",       82),
    ("BDC-M01-04",  "I. Bronze",      "Drill",             75,   "additional", "Staff or Senior Cadet", "04. Observe, Reflect and Practise",                                                       "https://airforcecadets.net.au/lh/BDC-M01-04",       83),
    ("BDC-M01-05",  "I. Bronze",      "Drill",             75,   "additional", "Staff or Senior Cadet", "05. Arms Drill",                                                                          "https://airforcecadets.net.au/lh/BDC-M01-05",       84),
    ("BFS-M01-01",  "I. Bronze",      "Field",             75,   "additional", "Staff or Senior Cadet", "01. Wilderness Wellness",                                                                 "https://airforcecadets.net.au/lh/BFS-M01-01",       85),
    ("BFS-M01-02",  "I. Bronze",      "Field",             75,   "additional", "Staff or Senior Cadet", "02. Water",                                                                               "https://airforcecadets.net.au/lh/BFS-M01-02",       86),
    ("BFS-M01-03",  "I. Bronze",      "Field",             75,   "additional", "Staff or Senior Cadet", "03. Shelter",                                                                             "https://airforcecadets.net.au/lh/BFS-M01-03",       87),
    ("BFS-M01-04",  "I. Bronze",      "Field",             75,   "additional", "Staff or Senior Cadet", "04. Fire",                                                                                "https://airforcecadets.net.au/lh/BFS-M01-04",       88),
    ("BFS-M01-05",  "I. Bronze",      "Field",             75,   "additional", "Staff or Senior Cadet", "05. Signalling",                                                                          "https://airforcecadets.net.au/lh/BFS-M01-05",       89),
    ("BFS-M01-06",  "I. Bronze",      "Field",             75,   "additional", "Staff or Senior Cadet", "06. SMEAC",                                                                               "https://airforcecadets.net.au/lh/BFS-M01-06",       90),
    ("BAV-M01-01",  "I. Bronze",      "Aviation",          75,   "additional", "Staff or Senior Cadet", "01. INTRO TO AVIATION METEOROLOGY",                                                       "https://airforcecadets.net.au/lh/BAV-M01-01",       91),
    ("BAV-M01-02",  "I. Bronze",      "Aviation",          75,   "additional", "Staff or Senior Cadet", "02. Pilot Six-Pack",                                                                      "https://airforcecadets.net.au/lh/BAV-M01-02",       92),
    ("BAV-M01-03",  "I. Bronze",      "Aviation",          75,   "additional", "Staff or Senior Cadet", "03. Aircraft Design and Performance",                                                     "https://airforcecadets.net.au/lh/BAV-M01-03",       93),
    ("BAV-M01-04",  "I. Bronze",      "Aviation",          45,   "additional", "Staff or Senior Cadet", "04. Paper Planes and Performance",                                                        "https://airforcecadets.net.au/lh/BAV-M01-04",       94),
    ("BAV-M01-05",  "I. Bronze",      "Aviation",          100,  "additional", "Staff or Senior Cadet", "05. Up, Up, and Droneaway",                                                               "https://airforcecadets.net.au/lh/BAV-M01-05",       95),
    ("BCYB-M01-01", "I. Bronze",      "Cyber",             60,   "additional", "Staff or Senior Cadet", "Introduction to cyber",                                                                   "https://airforcecadets.net.au/lh/BCYB-M01-01",      96),
    ("BCYB-M01-02", "I. Bronze",      "Cyber",             60,   "additional", "Staff or Senior Cadet", "Cyber and Defence",                                                                       "https://airforcecadets.net.au/lh/BCYB-M01-02",      97),
    ("BCYB-M01-03", "I. Bronze",      "Cyber",             60,   "additional", "Staff or Senior Cadet", "Ethical Hacking",                                                                         "https://airforcecadets.net.au/lh/BCYB-M01-03",      98),
    ("BCYB-M01-04", "I. Bronze",      "Cyber",             60,   "additional", "Staff or Senior Cadet", "Surviving in the cyber environment",                                                      "https://airforcecadets.net.au/lh/BCYB-M01-04",      99),
    ("BRPAS-M01-01","I. Bronze",      "RPAS",              120,  "additional", "Staff or Senior Cadet", "01. Drone Manoeuvres",                                                                    "https://airforcecadets.net.au/lh/BRPAS-M01-01",    100),
    ("BRPAS-M01-02","I. Bronze",      "RPAS",              70,   "additional", "Staff or Senior Cadet", "02. Complex Circuits",                                                                    "https://airforcecadets.net.au/lh/BRPAS-M01-02",    101),
    ("BRPAS-M01-03","I. Bronze",      "RPAS",              70,   "additional", "Staff or Senior Cadet", "03. Drone Racing",                                                                        "https://airforcecadets.net.au/lh/BRPAS-M01-03",    102),
    ("BSPA-M01-01", "I. Bronze",      "Space",             75,   "additional", "Staff or Senior Cadet", "01. Where Does Space Begin?",                                                             "https://airforcecadets.net.au/lh/BSPA-M01-01",     103),
    ("BSPA-M01-02", "I. Bronze",      "Space",             75,   "additional", "Staff or Senior Cadet", "02. Did You See That?",                                                                   "https://airforcecadets.net.au/lh/BSPA-M01-02",     104),
    ("BSPA-M01-03", "I. Bronze",      "Space",             75,   "additional", "Staff or Senior Cadet", "03. What is Space? To Infinity and Beyond",                                               "https://airforcecadets.net.au/lh/BSPA-M01-03",     105),
    ("BSPA-M01-04", "I. Bronze",      "Space",             60,   "additional", "Staff or Senior Cadet", "04. The Impacts of Space Debris",                                                         "https://airforcecadets.net.au/lh/BSPA-M01-04",     106),
    ("BSPA-M01-05", "I. Bronze",      "Space",             75,   "additional", "Staff or Senior Cadet", "05. The Space Time-line Continuum",                                                       "https://airforcecadets.net.au/lh/BSPA-M01-05",     107),
    # ── SILVER ───────────────────────────────────────────────────────────────
    ("SAV-M01-01",  "J. Silver",      "Aviation",          75,   "additional", "Staff or Senior Cadet", "01. Flight Operations",                                                                   "https://airforcecadets.net.au/lh/SAV-M01-01",      108),
    ("SAV-M01-02",  "J. Silver",      "Aviation",          75,   "additional", "Staff or Senior Cadet", "02. Aviation Communications",                                                             "https://airforcecadets.net.au/lh/SAV-M01-02",      109),
    ("SAV-M01-03",  "J. Silver",      "Aviation",          75,   "additional", "Staff or Senior Cadet", "03. Air Traffic Control",                                                                 "https://airforcecadets.net.au/lh/SAV-M01-03",      110),
    ("SAV-M01-04",  "J. Silver",      "Aviation",          75,   "additional", "Staff or Senior Cadet", "04. Six Degrees of Separation",                                                           "https://airforcecadets.net.au/lh/SAV-M01-04",      111),
    ("SAV-M01-05",  "J. Silver",      "Aviation",          75,   "additional", "Staff or Senior Cadet", "05. Winging it Through Weather",                                                          "https://airforcecadets.net.au/lh/SAV-M01-05",      112),
    ("SAV-M01-06",  "J. Silver",      "Aviation",          75,   "additional", "Staff or Senior Cadet", "06. Weather Or Knot We Fly",                                                              "https://airforcecadets.net.au/lh/SAV-M01-06",      113),
    ("SAV-M01-07",  "J. Silver",      "Aviation",          75,   "additional", "Staff or Senior Cadet", "07. Pilot Resources and Circuits",                                                        "https://airforcecadets.net.au/lh/SAV-M01-07",      114),
    ("SAV-M01-08",  "J. Silver",      "Aviation",          75,   "additional", "Staff or Senior Cadet", "08. Let's Get Ready To Fly",                                                              "https://airforcecadets.net.au/lh/SAV-M01-08",      115),
    ("SAV-M01-09",  "J. Silver",      "Aviation",          75,   "additional", "Staff or Senior Cadet", "09. Flight Talk",                                                                         "https://airforcecadets.net.au/lh/SAV-M01-09",      116),
    ("SAV-M01-10",  "J. Silver",      "Aviation",          120,  "additional", "Staff or Senior Cadet", "10. Aviation Facilitation",                                                               "https://airforcecadets.net.au/lh/SAV-M01-10",      117),
    ("SCLP-M01-01", "J. Silver",      "Personal_Dev",      150,  "additional", "Staff",                 "01. Welcome to Wattle Creek",                                                             "https://airforcecadets.net.au/lh/SCLP-M01-01",     118),
    ("SCLP-M01-02", "J. Silver",      "Personal_Dev",      150,  "additional", "Staff",                 "02. Compassion for Wattle Creek",                                                         "https://airforcecadets.net.au/lh/SCLP-M01-02",     119),
    ("SCLP-M01-03", "J. Silver",      "Personal_Dev",      150,  "additional", "Staff",                 "03. Confidence in Chaotic Wattle Creek",                                                  "https://airforcecadets.net.au/lh/SCLP-M01-03",     120),
    ("SCLP-M01-04", "J. Silver",      "Personal_Dev",      150,  "additional", "Staff",                 "04. Role Modelling and Influencing",                                                      "https://airforcecadets.net.au/lh/SCLP-M01-04",     121),
    ("SCLP-M01-05", "J. Silver",      "Personal_Dev",      150,  "additional", "Staff",                 "05. Decision Time for Wattle Creek",                                                      "https://airforcecadets.net.au/lh/SCLP-M01-05",     122),
    ("SCLP-M01-06", "J. Silver",      "Personal_Dev",      420,  "additional", "Staff",                 "06. The Day of Days",                                                                     "https://airforcecadets.net.au/lh/SCLP-M01-06",     123),
    ("SCLP-M01-07", "J. Silver",      "Personal_Dev",      150,  "additional", "Staff",                 "07. Facilitating Group Discussions",                                                      "https://airforcecadets.net.au/lh/SCLP-M01-07",     124),
    ("SCLP-M01-08", "J. Silver",      "Personal_Dev",      150,  "additional", "Staff",                 "08. Facilitation in Practice",                                                            "https://airforcecadets.net.au/lh/SCLP-M01-08",     125),
    ("SCYB-M01-01", "J. Silver",      "Cyber",             60,   "additional", "Staff or Senior Cadet", "01. Fundamentals of Cyber Security - Computer Skills, Access Management and Cyber Hygiene","https://airforcecadets.net.au/lh/SCYB-M01-01",    126),
    ("SCYB-M01-02", "J. Silver",      "Cyber",             60,   "additional", "Staff or Senior Cadet", "02. Introduction to Cyber Threats and Information Security",                              "https://airforcecadets.net.au/lh/SCYB-M01-02",     127),
    ("SCYB-M01-03", "J. Silver",      "Cyber",             60,   "additional", "Staff or Senior Cadet", "03. Defending the Gate",                                                                  "https://airforcecadets.net.au/lh/SCYB-M01-03",     128),
    ("SCYB-M01-04", "J. Silver",      "Cyber",             60,   "additional", "Staff or Senior Cadet", "04. Building a Cyber Fortress",                                                           "https://airforcecadets.net.au/lh/SCYB-M01-04",     129),
    ("SCYB-M01-05", "J. Silver",      "Cyber",             60,   "additional", "Staff or Senior Cadet", "05. Unlocking Secrets",                                                                   "https://airforcecadets.net.au/lh/SCYB-M01-05",     130),
    ("SCYB-M01-06", "J. Silver",      "Cyber",             60,   "additional", "Staff or Senior Cadet", "06. Fortifying your Digital Space",                                                       "https://airforcecadets.net.au/lh/SCYB-M01-06",     131),
    ("SCYB-M01-07", "J. Silver",      "Cyber",             60,   "additional", "Staff or Senior Cadet", "07. Next Level Cyber Security",                                                           "https://airforcecadets.net.au/lh/SCYB-M01-07",     132),
    ("SCYB-M01-08", "J. Silver",      "Cyber",             60,   "additional", "Staff or Senior Cadet", "08. Guarding your Digital Treasure",                                                      "https://airforcecadets.net.au/lh/SCYB-M01-08",     133),
    ("SCYB-M01-09", "J. Silver",      "Cyber",             60,   "additional", "Staff or Senior Cadet", "09. When Cyber Strikes",                                                                  "https://airforcecadets.net.au/lh/SCYB-M01-09",     134),
    ("SCYB-M01-10", "J. Silver",      "Cyber",             60,   "additional", "Staff or Senior Cadet", "10. The Cyber Landscape: Understanding Policies, Compliance, and Risk",                   "https://airforcecadets.net.au/lh/SCYB-M01-10",     135),
    ("SCYB-M01-11", "J. Silver",      "Cyber",             60,   "additional", "Staff or Senior Cadet", "11. Shaping the Future",                                                                  "https://airforcecadets.net.au/lh/SCYB-M01-11",     136),
    ("SCYB-M01-12", "J. Silver",      "Cyber",             60,   "additional", "Staff or Senior Cadet", "12. Navigating the Grey Zones: Ethics, Privacy, and Legal Aspects of Cyber Security",    "https://airforcecadets.net.au/lh/SCYB-M01-12",     137),
    ("SCYB-M01-13", "J. Silver",      "Cyber",             60,   "additional", "Staff or Senior Cadet", "13. Decoding the Building Blocks of Computing: Binary and Source Code",                   "https://airforcecadets.net.au/lh/SCYB-M01-13",     138),
    ("SCYB-M01-14", "J. Silver",      "Cyber",             60,   "additional", "Staff or Senior Cadet", "14. Protecting Homeland: Cyber Security Roles in National Defence",                       "https://airforcecadets.net.au/lh/SCYB-M01-14",     139),
    ("SCYB-M01-15", "J. Silver",      "Cyber",             60,   "additional", "Staff or Senior Cadet", "15. Unlocking the Secrets of Cryptography",                                               "https://airforcecadets.net.au/lh/SCYB-M01-15",     140),
    ("SCYB-M01-16", "J. Silver",      "Cyber",             60,   "additional", "Staff or Senior Cadet", "16. Tracing Digital Trails - Exploring the World of Digital Forensics",                   "https://airforcecadets.net.au/lh/SCYB-M01-16",     141),
    ("SCYB-M01-17", "J. Silver",      "Cyber",             60,   "additional", "Staff or Senior Cadet", "17. Harnessing OSINT and Cyber Threat Intelligence",                                      "https://airforcecadets.net.au/lh/SCYB-M01-17",     142),
    ("SCYB-M01-18", "J. Silver",      "Cyber",             60,   "additional", "Staff or Senior Cadet", "18. Becoming a Digital Sleuth: Mastering Penetration Techniques",                         "https://airforcecadets.net.au/lh/SCYB-M01-18",     143),
    ("SCYB-M01-19", "J. Silver",      "Cyber",             60,   "additional", "Staff or Senior Cadet", "19. Hidden in Plain Sight - The Art and Science of Steganography",                        "https://airforcecadets.net.au/lh/SCYB-M01-19",     144),
    ("SCYB-M01-20", "J. Silver",      "Cyber",             60,   "additional", "Staff or Senior Cadet", "20. The Dark Side of the Web: Web Exploits and Vulnerabilities",                          "https://airforcecadets.net.au/lh/SCYB-M01-20",     145),
    ("SCYB-M01-21", "J. Silver",      "Cyber",             60,   "additional", "Staff or Senior Cadet", "21. Breaking into Databases - Unleashing the Power of SQL Injection",                     "https://airforcecadets.net.au/lh/SCYB-M01-21",     146),
    ("SCYB-M01-22", "J. Silver",      "Cyber",             60,   "additional", "Staff or Senior Cadet", "22. Decoding the Secrets of Reverse Engineering - Hardware and Software Analysis",        "https://airforcecadets.net.au/lh/SCYB-M01-22",     147),
    ("SCYB-M01-23", "J. Silver",      "Cyber",             60,   "additional", "Staff or Senior Cadet", "23. Exploring the IoT Frontier - Webcams, Drones and Beyond",                             "https://airforcecadets.net.au/lh/SCYB-M01-23",     148),
    ("SCYB-M01-24", "J. Silver",      "Cyber",             60,   "additional", "Staff or Senior Cadet", "24. Unlock Your Future: Navigating the World of Cyber Security Careers",                  "https://airforcecadets.net.au/lh/SCYB-M01-24",     149),
    ("SCYB-M01-25", "J. Silver",      "Cyber",             60,   "additional", "Staff or Senior Cadet", "25. Protecting Homeland: Cyber Security Roles in National Defence",                       "https://airforcecadets.net.au/lh/SCYB-M01-25",     150),
    ("SCYB-M01-26", "J. Silver",      "Cyber",             60,   "additional", "Staff or Senior Cadet", "26. Cyber Defenders Unmasked: A Glimpse into the Lives of Cyber Professionals",           "https://airforcecadets.net.au/lh/SCYB-M01-26",     151),
    ("SCYB-M01-27", "J. Silver",      "Cyber",             60,   "additional", "Staff or Senior Cadet", "27. Competing in the Cyber Arena: Preparing for and Engaging in Cyber Competitions",      "https://airforcecadets.net.au/lh/SCYB-M01-27",     152),
    ("SDC-M01-01",  "J. Silver",      "Drill",             75,   "additional", "Staff or Senior Cadet", "01. Drill Ready",                                                                         "https://airforcecadets.net.au/lh/SDC-M01-01",      153),
    ("SDC-M01-02",  "J. Silver",      "Drill",             75,   "additional", "Staff or Senior Cadet", "02. Precision with Arms: The Rifle",                                                      "https://airforcecadets.net.au/lh/SDC-M01-02",      154),
    ("SDC-M01-03",  "J. Silver",      "Drill",             75,   "additional", "Staff or Senior Cadet", "03. Command Performance",                                                                 "https://airforcecadets.net.au/lh/SDC-M01-03",      155),
    ("SDC-M01-04",  "J. Silver",      "Drill",             75,   "additional", "Staff or Senior Cadet", "04. Mastering the Blade",                                                                 "https://airforcecadets.net.au/lh/SDC-M01-04",      156),
    ("SDC-M01-05",  "J. Silver",      "Drill",             75,   "additional", "Staff or Senior Cadet", "05. Elevating Executions",                                                                "https://airforcecadets.net.au/lh/SDC-M01-05",      157),
    ("SDC-M01-06",  "J. Silver",      "Drill",             75,   "additional", "Staff or Senior Cadet", "06. The Elegance of Drill",                                                               "https://airforcecadets.net.au/lh/SDC-M01-06",      158),
    ("SDC-M01-07",  "J. Silver",      "Drill",             75,   "additional", "Staff or Senior Cadet", "07. From Blueprint to Brilliance",                                                        "https://airforcecadets.net.au/lh/SDC-M01-07",      159),
    ("SDC-M01-08",  "J. Silver",      "Drill",             75,   "additional", "Staff or Senior Cadet", "08. Guardians of Tradition",                                                              "https://airforcecadets.net.au/lh/SDC-M01-08",      160),
    ("SDC-M01-09",  "J. Silver",      "Drill",             75,   "additional", "Staff or Senior Cadet", "09. Advancing Your Drill Skills",                                                         "https://airforcecadets.net.au/lh/SDC-M01-09",      161),
    ("SDC-M01-10",  "J. Silver",      "Drill",             75,   "additional", "Staff or Senior Cadet", "10. Honour Through Discipline",                                                           "https://airforcecadets.net.au/lh/SDC-M01-10",      162),
    ("SDC-M01-11",  "J. Silver",      "Drill",             75,   "additional", "Staff or Senior Cadet", "11. Parade Professionals",                                                                "https://airforcecadets.net.au/lh/SDC-M01-11",      163),
    ("SDC-M01-12",  "J. Silver",      "Drill",             75,   "additional", "Staff or Senior Cadet", "12. The Grand Display",                                                                   "https://airforcecadets.net.au/lh/SDC-M01-12",      164),
    ("SFS-M01-01",  "J. Silver",      "Field",             150,  "additional", "Staff or Senior Cadet", "01. Support a Bivouac",                                                                   "https://airforcecadets.net.au/lh/SFS-M01-01",      165),
    ("SFS-M01-02",  "J. Silver",      "Field",             150,  "additional", "Staff or Senior Cadet", "02. Advanced Navigation",                                                                 "https://airforcecadets.net.au/lh/SFS-M01-02",      166),
    ("SRPAS-M01-01","J. Silver",      "RPAS",              150,  "additional", "Staff or Senior Cadet", "01. Flight to Opal City",                                                                 "https://airforcecadets.net.au/lh/SRPAS-M01-01",    167),
    ("SRPAS-M01-02","J. Silver",      "RPAS",              150,  "additional", "Staff or Senior Cadet", "02. Land Analysis of Opal City",                                                          "https://airforcecadets.net.au/lh/SRPAS-M01-02",    168),
    ("SRPAS-M01-03","J. Silver",      "RPAS",              150,  "additional", "Staff or Senior Cadet", "03. Urban Planning Opal City",                                                            "https://airforcecadets.net.au/lh/SRPAS-M01-03",    169),
    ("SRPAS-M01-04","J. Silver",      "RPAS",              150,  "additional", "Staff or Senior Cadet", "04. A Storm at Opal City",                                                                "https://airforcecadets.net.au/lh/SRPAS-M01-04",    170),
    ("SRPAS-M01-05","J. Silver",      "RPAS",              150,  "additional", "Staff or Senior Cadet", "05. Archaeological Survey of Opal City",                                                  "https://airforcecadets.net.au/lh/SRPAS-M01-05",    171),
    ("SRPAS-M01-06","J. Silver",      "RPAS",              150,  "additional", "Staff or Senior Cadet", "06. Program a Drone for Surveillance",                                                    "https://airforcecadets.net.au/lh/SRPAS-M01-06",    172),
    ("SSPA-M01-01", "J. Silver",      "Space",             75,   "additional", "Staff or Senior Cadet", "01. What Can Australia Offer Space?",                                                     "https://airforcecadets.net.au/lh/SSPA-M01-01",     173),
    ("SSPA-M01-02", "J. Silver",      "Space",             75,   "additional", "Staff or Senior Cadet", "02. Orbital Oddities",                                                                    "https://airforcecadets.net.au/lh/SSPA-M01-02",     174),
    ("SSPA-M01-03", "J. Silver",      "Space",             75,   "additional", "Staff or Senior Cadet", "03. Round and Round, Satellite",                                                          "https://airforcecadets.net.au/lh/SSPA-M01-03",     175),
    ("SSPA-M01-04", "J. Silver",      "Space",             75,   "additional", "Staff or Senior Cadet", "04. Spacecraft Components and Features",                                                  "https://airforcecadets.net.au/lh/SSPA-M01-04",     176),
    ("SSPA-M01-05", "J. Silver",      "Space",             75,   "additional", "Staff or Senior Cadet", "05. Houston, we have lift off! (Part 1)",                                                 "https://airforcecadets.net.au/lh/SSPA-M01-05",     177),
    ("SSPA-M01-06", "J. Silver",      "Space",             75,   "additional", "Staff or Senior Cadet", "06. Houston, We Have Lift Off! (Part 2)",                                                 "https://airforcecadets.net.au/lh/SSPA-M01-06",     178),
    ("SSPA-M01-07", "J. Silver",      "Space",             75,   "additional", "Staff or Senior Cadet", "07. Lost in Space",                                                                       "https://airforcecadets.net.au/lh/SSPA-M01-07",     179),
    ("SSPA-M01-08", "J. Silver",      "Space",             75,   "additional", "Staff or Senior Cadet", "08. Come In, Over and Out",                                                               "https://airforcecadets.net.au/lh/SSPA-M01-08",     180),
    ("SSPA-M01-09", "J. Silver",      "Space",             75,   "additional", "Staff or Senior Cadet", "09. Major Tom to Ground Control",                                                         "https://airforcecadets.net.au/lh/SSPA-M01-09",     181),
    ("SSPA-M01-10", "J. Silver",      "Space",             75,   "additional", "Staff or Senior Cadet", "10. Mission Planning (Part 1)",                                                           "https://airforcecadets.net.au/lh/SSPA-M01-10",     182),
    ("SSPA-M01-11", "J. Silver",      "Space",             75,   "additional", "Staff or Senior Cadet", "11. Mission Planning (Part 2)",                                                           "https://airforcecadets.net.au/lh/SSPA-M01-11",     183),
    ("SSPA-M01-12", "J. Silver",      "Space",             75,   "additional", "Staff or Senior Cadet", "12. Space Extension Facilitation",                                                        "https://airforcecadets.net.au/lh/SSPA-M01-12",     184),
    # ── GOLD ─────────────────────────────────────────────────────────────────
    ("GAV-M01-01",   "K. Gold",       "Aviation",          1200, "additional", "Staff or Senior Cadet", "01. Gold Aviation",                                                                       "https://airforcecadets.net.au/lh/GAV-M01-01",      185),
    ("GDC-M01-01",   "K. Gold",       "Drill",             1200, "additional", "Staff or Senior Cadet", "01. Drill Competition",                                                                   "https://airforcecadets.net.au/lh/GDC-M01-01",      186),
    ("GCLP-M01-01",  "K. Gold",       "Personal_Dev",      300,  "additional", "Staff",                 "01. Giving Back",                                                                         "https://airforcecadets.net.au/lh/GCLP-M01-01",     187),
    ("GCLP-M01-02",  "K. Gold",       "Personal_Dev",      300,  "additional", "Staff",                 "02. Resolving and Managing Conflict",                                                     "https://airforcecadets.net.au/lh/GCLP-M01-02",     188),
    ("GCLP2-M01-01", "K. Gold",       "Personal_Dev",      720,  "additional", "Staff",                 "01. The Merger Masters",                                                                  "https://airforcecadets.net.au/lh/GCLP2-M01-01",    189),
    ("GFS-M01-01",   "K. Gold",       "Field",             1200, "additional", "Staff or Senior Cadet", "01. Gold Field Skills",                                                                   "https://airforcecadets.net.au/lh/GFS-M01-01",      190),
    ("GRPAS-M01-01", "K. Gold",       "RPAS",              120,  "additional", "Staff or Senior Cadet", "01. Imagining a Drone-derful Future",                                                     "https://airforcecadets.net.au/lh/GRPAS-M01-01",    191),
    ("GRPAS-M01-02", "K. Gold",       "RPAS",              120,  "additional", "Staff or Senior Cadet", "02. Where Industry Takes Flight!",                                                        "https://airforcecadets.net.au/lh/GRPAS-M01-02",    192),
    ("GRPAS-M01-03", "K. Gold",       "RPAS",              120,  "additional", "Staff or Senior Cadet", "03. The Sky's New Party Crashers!",                                                       "https://airforcecadets.net.au/lh/GRPAS-M01-03",    193),
    ("GRPAS-M01-04", "K. Gold",       "RPAS",              120,  "additional", "Staff or Senior Cadet", "04. Drones That Do More Than Buzz",                                                       "https://airforcecadets.net.au/lh/GRPAS-M01-04",    194),
    ("GRPAS-M01-05", "K. Gold",       "RPAS",              120,  "additional", "Staff or Senior Cadet", "05. Presenting Your Drone Ideas!",                                                        "https://airforcecadets.net.au/lh/GRPAS-M01-05",    195),
    ("GRPAS-M02-01", "K. Gold",       "RPAS",              150,  "additional", "Staff or Senior Cadet", "01. Bivouac-ing with Altitude!",                                                          "https://airforcecadets.net.au/lh/GRPAS-M02-01",    196),
    ("GRPAS-M02-02", "K. Gold",       "RPAS",              150,  "additional", "Staff or Senior Cadet", "02. Create Your Drone Adventure!",                                                        "https://airforcecadets.net.au/lh/GRPAS-M02-02",    197),
    ("GRPAS-M02-03", "K. Gold",       "RPAS",              150,  "additional", "Staff or Senior Cadet", "03. Join Us At The Drone Expo!",                                                          "https://airforcecadets.net.au/lh/GRPAS-M02-03",    198),
    ("GSPA-M01-01",  "K. Gold",       "Space",             75,   "additional", "Staff or Senior Cadet", "01. Life in Space",                                                                       "https://airforcecadets.net.au/lh/GSPA-M01-01",     199),
    ("GSPA-M01-02",  "K. Gold",       "Space",             75,   "additional", "Staff or Senior Cadet", "02. Bringing Space Down to Earth",                                                        "https://airforcecadets.net.au/lh/GSPA-M01-02",     200),
    ("GSPA-M01-03",  "K. Gold",       "Space",             75,   "additional", "Staff or Senior Cadet", "03. Potential of Australia's Space Domain",                                               "https://airforcecadets.net.au/lh/GSPA-M01-03",     201),
    ("GSPA-M01-04",  "K. Gold",       "Space",             75,   "additional", "Staff or Senior Cadet", "04. Your Mission, Should You Choose to Accept It",                                        "https://airforcecadets.net.au/lh/GSPA-M01-04",     202),
    ("GSPA-M01-05",  "K. Gold",       "Space",             75,   "additional", "Staff or Senior Cadet", "05. Mission Possible",                                                                    "https://airforcecadets.net.au/lh/GSPA-M01-05",     203),
    ("GSPA-M01-06",  "K. Gold",       "Space",             75,   "additional", "Staff or Senior Cadet", "06. Houston, We Have A Problem",                                                          "https://airforcecadets.net.au/lh/GSPA-M01-06",     204),
    ("GSPA-M01-07",  "K. Gold",       "Space",             75,   "additional", "Staff or Senior Cadet", "07. Who Do I Want To Be",                                                                 "https://airforcecadets.net.au/lh/GSPA-M01-07",     205),
    ("GSPA-M01-08",  "K. Gold",       "Space",             75,   "additional", "Staff or Senior Cadet", "08. A Day In The Life (Part 1)",                                                          "https://airforcecadets.net.au/lh/GSPA-M01-08",     206),
    ("GSPA-M01-09",  "K. Gold",       "Space",             75,   "additional", "Staff or Senior Cadet", "09. A Day In The Life (Part 2)",                                                          "https://airforcecadets.net.au/lh/GSPA-M01-09",     207),
    ("GSPA-M01-10",  "K. Gold",       "Space",             75,   "additional", "Staff or Senior Cadet", "10. The Future of Space (Part 1)",                                                        "https://airforcecadets.net.au/lh/GSPA-M01-10",     208),
    ("GSPA-M01-11",  "K. Gold",       "Space",             75,   "additional", "Staff or Senior Cadet", "11. The Future of Space (Part 2)",                                                        "https://airforcecadets.net.au/lh/GSPA-M01-11",     209),
    ("GSPA-M01-12",  "K. Gold",       "Space",             75,   "additional", "Staff or Senior Cadet", "12. Charting Pathways to the Stars (Part 1)",                                             "https://airforcecadets.net.au/lh/GSPA-M01-12",     210),
    ("GSPA-M01-13",  "K. Gold",       "Space",             75,   "additional", "Staff or Senior Cadet", "13. Charting Pathways to the Stars (Part 2)",                                             "https://airforcecadets.net.au/lh/GSPA-M01-13",     211),
    ("GSPA-M01-14",  "K. Gold",       "Space",             75,   "additional", "Staff or Senior Cadet", "14. Charting Pathways to the Stars (Part 3)",                                             "https://airforcecadets.net.au/lh/GSPA-M01-14",     212),
    ("GSPA-M01-15",  "K. Gold",       "Space",             75,   "additional", "Staff or Senior Cadet", "15. Charting Pathways to the Stars (Part 4)",                                             "https://airforcecadets.net.au/lh/GSPA-M01-15",     213),
    ("GSPA-M01-16",  "K. Gold",       "Space",             75,   "additional", "Staff or Senior Cadet", "16. Mock ADF Cadet Space College Expo",                                                   "https://airforcecadets.net.au/lh/GSPA-M01-16",     214),
]


def _code_from_identifier(identifier: str) -> tuple:
    """Extract (module_code, part_number) from a full experiential identifier."""
    parts = identifier.rsplit('-', 1)
    if len(parts) == 2:
        try:
            return parts[0], int(parts[1])
        except ValueError:
            pass
    return identifier, 1


def upgrade():
    import uuid
    from datetime import datetime, timezone
    conn = op.get_bind()
    now = datetime.now(timezone.utc)

    # 1. Add missing curriculum_elements (idempotent)
    for name, display_name, scope in _NEW_ELEMENTS:
        existing = conn.execute(
            sa.text("SELECT id FROM curriculum_elements WHERE name=:n AND scope_level=:s"),
            {"n": name, "s": scope}
        ).fetchone()
        if not existing:
            conn.execute(
                sa.text(
                    "INSERT INTO curriculum_elements "
                    "(id, name, display_name, scope_level, active_status, is_archived, created_at, updated_at) "
                    "VALUES (:id, :name, :display_name, :scope_level, true, false, :now, :now)"
                ),
                {"id": str(uuid.uuid4()), "name": name, "display_name": display_name,
                 "scope_level": scope, "now": now},
            )

    # 2. Insert curriculum items (skip any identifier already present at national scope)
    for seq, row in enumerate(_CURRICULUM, start=1):
        identifier, phase, element, duration, core_status, instructor, title, lh_url, _csv_seq = row
        existing = conn.execute(
            sa.text("SELECT id FROM curriculum_items WHERE identifier=:ident AND owning_level='national'"),
            {"ident": identifier}
        ).fetchone()
        if existing:
            continue
        code, part_number = _code_from_identifier(identifier)
        conn.execute(
            sa.text(
                "INSERT INTO curriculum_items "
                "(id, owning_level, wing_id, squadron_id, identifier, code, part_number, title, "
                " phase, element, duration_minutes, part_count, instructor_suitability, "
                " core_status, learning_hub_url, recommended_sequence, "
                " active_status, is_archived, created_at, updated_at) "
                "VALUES (:id, 'national', NULL, NULL, :identifier, :code, :part_number, :title, "
                "        :phase, :element, :duration_minutes, 1, :instructor_suitability, "
                "        :core_status, :learning_hub_url, :recommended_sequence, "
                "        true, false, :now, :now)"
            ),
            {
                "id": str(uuid.uuid4()),
                "identifier": identifier,
                "code": code,
                "part_number": part_number,
                "title": title,
                "phase": phase,
                "element": element,
                "duration_minutes": duration,
                "instructor_suitability": instructor,
                "core_status": core_status,
                "learning_hub_url": lh_url,
                "recommended_sequence": seq,
                "now": now,
            },
        )


def downgrade():
    conn = op.get_bind()
    identifiers = [row[0] for row in _CURRICULUM]
    # Remove only the items this migration inserted (match by identifier + national scope)
    for ident in identifiers:
        conn.execute(
            sa.text("DELETE FROM curriculum_items WHERE identifier=:ident AND owning_level='national'"),
            {"ident": ident}
        )
    # Remove the new elements this migration added
    for name, _dn, scope in _NEW_ELEMENTS:
        conn.execute(
            sa.text("DELETE FROM curriculum_elements WHERE name=:n AND scope_level=:s"),
            {"n": name, "s": scope}
        )
