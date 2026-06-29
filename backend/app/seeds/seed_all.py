"""Seed national HQ, 7 Wing, all squadrons, users/access codes, curriculum, 703 demo.

The architecture supports many Wings; 7 Wing is seeded as demo data only.
"""
from datetime import datetime, timezone
from ..database import SessionLocal, init_db, reset_db
from ..security import hash_code
from ..models import (NationalEntity, Wing, Squadron, Flight, User, AccessCode,
                      CurriculumItem, Facilitator, FacilitatorRankHistory,
                      TrainingArea, Equipment, ParadeNight, Session, Cadet,
                      TimingTemplate, TimingBlock)

UNITS = [
    ("7WG", "7 Wing HQ", "7WG", "RAAF Base Pearce, Bullsbrook WA 6084", "Tuesday", "19:00", "22:00", 2, True),
    ("701", "701 Squadron — Bullsbrook", "701SQN", "Great Northern Highway, Bullsbrook WA 6084", "Friday", "18:00", "22:00", 3, False),
    ("702", "702 Squadron — Cannington", "702SQN", "Gate 3, 1-5 Station Street, Cannington WA 6107", "Wednesday", "18:00", "21:30", 3, False),
    ("703", "703 Squadron — City of Fremantle", "703SQN", "Leeuwin Barracks, Riverside Road, East Fremantle WA 6158", "Friday", "18:00", "22:00", 3, False),
    ("704", "704 Squadron — Madeley", "704SQN", "Kingsway Regional Sporting Complex, Madeley WA 6065", "Friday", "18:00", "22:00", 3, False),
    ("705", "705 Squadron — City of Albany", "705SQN", "Cnr Spencer St and Serpentine Rd, Albany WA 6330", "Wednesday", "17:20", "21:15", 2, False),
    ("707", "707 Squadron — Mandurah", "707SQN", "Coodanup Drive, Coodanup WA 6210", "Wednesday", "18:15", "22:00", 3, False),
    ("708", "708 Squadron — Rockingham", "708SQN", "127 Dixon Road, Rockingham WA 6168", "Friday", "18:15", "22:00", 3, False),
    ("709", "709 Squadron — Kalgoorlie-Boulder", "709SQN", "23 Cheetham Street, Kalgoorlie WA 6430", "Monday", "17:45", "21:30", 2, False),
    ("710", "710 Squadron — Bunbury", "710SQN", "Cnr Wilson Rd and Proffit St, Bunbury WA 6230", "Friday", "18:00", "21:30", 2, False),
    ("711", "711 Squadron — City of Greater Geraldton", "711SQN", "189 Lester Avenue, Geraldton WA 6530", "Monday", "17:30", "21:00", 2, False),
    ("712", "712 Squadron — City of Belmont", "712SQN", "Palmer Barracks, Beavis Drive, South Guildford WA 6055", "Wednesday", "17:45", "21:30", 3, False),
    ("713", "713 Squadron — Cannington", "713SQN", "Cannington Exhibition Centre, Gate 3 Station St, Cannington WA 6107", "Friday", "18:00", "22:30", 3, False),
    ("714", "714 Squadron — Karrakatta", "714SQN", "Irwin Barracks, Stubbs Terrace, Karrakatta WA 6010", "Friday", "18:00", "22:00", 3, False),
    ("715", "715 Squadron — City of Belmont", "715SQN", "Palmer Barracks, Beavis Drive, South Guildford WA 6055", "Friday", "18:30", "22:00", 3, False),
    ("721", "721 Squadron — Madeley", "721SQN", "Cnr Hartman Drive and Sporting Drive, Madeley WA 6065", "Wednesday", "18:30", "21:30", 2, False),
    ("723", "723 Squadron — Joondalup", "723SQN", "63 McLarty Avenue, Joondalup WA 6027", "Wednesday", "18:30", "21:30", 2, False),
]

LH = "https://airforcecadets.net.au/lh/index.php/cadet-program/"
CORE = [
    ("ORI-M01", "New Cadet Welcome", "A. Orientation", "Service", "T1", 120, 1),
    ("ORI-M03", "Cyber Awareness", "A. Orientation", "PDL", "T1", 180, 3),
    ("INL-M00", "PDL Critical Qualities", "B. Initial", "PDL", "T1", 180, 5),
    ("INL-M02", "RAAF Aircraft Presentations", "B. Initial", "Air_Space", "T1", 480, 7),
    ("INL-M08", "Drill and Ceremonial", "B. Initial", "Drill", "T1", 1140, 13),
    ("JNR-M01", "Junior Drill and Ceremonial", "C. Junior", "Drill", "T2", 450, 16),
    ("JNR-M02", "Junior Air and Space", "C. Junior", "Air_Space", "T1", 420, 17),
    ("BCLP-M01", "Bronze CLP", "I. Bronze", "PDL", "T1", 1260, 19),
    ("INT-M03", "Intermediate Field Skills", "D. Intermediate", "Field", "T1", 300, 22),
    ("INT-M04", "Intermediate Facilitation", "D. Intermediate", "PDL", "T1", 600, 23),
    ("SCLP-M01", "Silver CLP", "J. Silver", "PDL", "T2", 1530, 24),
    ("SNR-M01", "Senior Mission — Defence", "E. Senior", "PDL", "T3", 600, 25),
    ("GCLP-M01", "Gold CLP Part 1", "K. Gold", "PDL", "T1", 1200, 30),
]


def seed_all():
    reset_db()
    db = SessionLocal()
    nat = NationalEntity(name="AAFC National Headquarters", short_name="NATIONAL")
    db.add(nat); db.commit()

    wing = Wing(national_id=nat.id, code="7WG", name="7 Wing (Western Australia)", short_name="7WG")
    db.add(wing); db.commit()

    sqn_by_code = {}
    for code, name, short, addr, day, st, et, sc, is_wing_hq in UNITS:
        if is_wing_hq:
            # Wing HQ users
            wv = User(display_name="7 Wing Viewer", role="wing_viewer", wing_id=wing.id, national_id=nat.id)
            wa = User(display_name="7 Wing Admin", role="wing_admin", wing_id=wing.id, national_id=nat.id)
            db.add_all([wv, wa]); db.commit()
            db.add(AccessCode(user_id=wv.id, code_hash=hash_code("7WG2026")))
            db.add(AccessCode(user_id=wa.id, code_hash=hash_code("ADMIN7WG")))
            db.commit()
            continue
        s = Squadron(wing_id=wing.id, code=code, unit_number=code, name=name, short_name=short,
                     address=addr, default_parade_day=day, default_start_time=st, default_end_time=et,
                     default_session_count=sc)
        db.add(s); db.commit()
        sqn_by_code[code] = s
        gen = User(display_name=f"{code} General", role="sqn_general", wing_id=wing.id, squadron_id=s.id)
        adm = User(display_name=f"{code} Admin", role="sqn_admin", wing_id=wing.id, squadron_id=s.id)
        db.add_all([gen, adm]); db.commit()
        db.add(AccessCode(user_id=gen.id, code_hash=hash_code(f"{code}SQN2026")))
        db.add(AccessCode(user_id=adm.id, code_hash=hash_code(f"ADMIN{code}")))
        db.commit()

    # National + system + auditor users
    nadm = User(display_name="National Admin", role="national_admin", national_id=nat.id)
    nview = User(display_name="National Viewer", role="national_viewer", national_id=nat.id)
    sysadm = User(display_name="System Admin", role="system_admin", national_id=nat.id)
    auditor = User(display_name="Auditor", role="auditor", national_id=nat.id)
    db.add_all([nadm, nview, sysadm, auditor]); db.commit()
    db.add_all([
        AccessCode(user_id=nadm.id, code_hash=hash_code("ADMINNATIONAL")),
        AccessCode(user_id=nview.id, code_hash=hash_code("NATIONAL2026")),
        AccessCode(user_id=sysadm.id, code_hash=hash_code("SYSADMIN2026")),
        AccessCode(user_id=auditor.id, code_hash=hash_code("AUDITOR2026")),
    ]); db.commit()

    # National core curriculum
    now = datetime.now(timezone.utc)
    cur_by_code = {}
    for ccode, title, phase, el, term, dur, seq in CORE:
        c = CurriculumItem(owning_level="national", code=ccode,
                           title=title, phase=phase, element=el, duration_minutes=dur,
                           recommended_term=term, recommended_sequence=seq,
                           learning_hub_url=LH, created_at=now, updated_at=now)
        db.add(c); db.commit()
        cur_by_code[c.code] = c

    # 703 demo data
    s703 = sqn_by_code["703"]
    facs = {}
    for first, last, rank, ftype in [("", "Daniels", "CIV", "Civilian"), ("", "Flanders", "CIV", "Civilian"),
                                     ("", "McGhie", "FLTLT(AAFC)", "Staff"), ("", "Milligen", "CSGT", "Senior Cadet"),
                                     ("", "Daley", "PLTOFF(AAFC)", "Staff")]:
        f = Facilitator(squadron_id=s703.id, wing_id=wing.id, first_name=first, last_name=last,
                        current_rank=rank, type=ftype, subject_areas=["PDL"])
        db.add(f); db.commit()
        db.add(FacilitatorRankHistory(facilitator_id=f.id, rank=rank, effective_from="2026-01-01")); db.commit()
        facs[last] = f
    rooms = {}
    for nm, tp, cap, io in [("Bravo", "Classroom", 30, "Indoor"), ("Major Parade Ground", "Parade", 100, "Outdoor"),
                            ("Seniors Working Room", "Classroom", 15, "Indoor")]:
        r = TrainingArea(squadron_id=s703.id, name=nm, type=tp, capacity=cap, indoor_outdoor=io)
        db.add(r); db.commit(); rooms[nm] = r
    db.add(Equipment(squadron_id=s703.id, name="Projector", type="AV", quantity=2, available_quantity=2)); db.commit()

    # Default timing template for 703 SQN — Friday night parade schedule.
    # effective_from 2026-01-01, is_default=True so _effective_template() picks it up
    # for any parade date ≥ 2026-01-01 that has no override.
    # Fatigues adjusted to 2105–2115 and Final Parade to 2115–2125 to avoid overlap.
    tmpl_703 = TimingTemplate(
        squadron_id=s703.id,
        name="703 Standard Friday Night",
        effective_from="2026-01-01",
        is_default=True,
        active_status=True,
        notes="Default template for all 703 SQN parade nights from 2026.",
    )
    db.add(tmpl_703); db.commit()
    _703_BLOCKS = [
        # order, name,                  type,                  start,   end,    dur, is_ip, pnum
        (0,  "Arrival",               "arrival",             "18:00", "18:15",  15, False, None),
        (1,  "Roll Call",             "roll_call",           "18:15", "18:25",  10, False, None),
        (2,  "Cadets Forming Up",     "administration",      "18:25", "18:30",   5, False, None),
        (3,  "Parade",                "parade",              "18:30", "18:45",  15, False, None),
        (4,  "Period 1",              "instructional_period","18:50", "19:25",  35, True,  1),
        (5,  "Period 2",              "instructional_period","19:25", "20:00",  35, True,  2),
        (6,  "Drinks Break",          "break",               "20:00", "20:30",  30, False, None),
        (7,  "Period 3",              "instructional_period","20:30", "21:05",  35, True,  3),
        (8,  "Fatigues",              "fatigues",            "21:05", "21:15",  10, False, None),
        (9,  "Final Parade",          "parade",              "21:15", "21:25",  10, False, None),
        (10, "Debrief",               "debrief",             "21:25", "21:30",   5, False, None),
        (11, "Dismissal",             "dismissal",           "21:30", "21:30",   0, False, None),
    ]
    for order, name, btype, start, end, dur, is_ip, pnum in _703_BLOCKS:
        db.add(TimingBlock(
            timing_template_id=tmpl_703.id,
            display_order=order,
            block_name=name,
            block_type=btype,
            start_time=start,
            end_time=end,
            duration_minutes=dur,
            is_instructional_period=is_ip,
            period_number=pnum,
        ))
    db.commit()

    demo_pns = [
        ("2026-02-06", "T1", [(1, "A. Orientation", "ORI-M01", "Bravo", "Daley", "delivered"),
                              (2, "B. Initial", "INL-M00", "Bravo", "McGhie", "delivered"),
                              (3, "D. Intermediate", "INT-M04", "Seniors Working Room", "Flanders", "delivered")]),
        ("2026-05-01", "T2", [(1, "B. Initial", "INL-M08", "Major Parade Ground", "Milligen", "delivered"),
                              (2, "C. Junior", "JNR-M01", "Major Parade Ground", "Milligen", "not_delivered")]),
        ("2026-07-24", "T3", [(1, "B. Initial", "INL-M02", "Bravo", "Daniels", "planned"),
                              (2, "C. Junior", "JNR-M01", "Major Parade Ground", "Milligen", "planned"),
                              (3, "D. Intermediate", "INT-M04", "Seniors Working Room", "Flanders", "planned")]),
    ]
    for date, term, sessions in demo_pns:
        published = all(x[5] in ("delivered", "not_delivered") for x in sessions)
        pn = ParadeNight(squadron_id=s703.id, wing_id=wing.id, date=date, term=term,
                         start_time=s703.default_start_time, end_time=s703.default_end_time,
                         session_count=len(sessions), published_status=published,
                         timing_template_id=tmpl_703.id)
        db.add(pn); db.commit()
        for period, phase, code, room, faclast, status in sessions:
            c = cur_by_code.get(code)
            f = facs.get(faclast)
            r = rooms.get(room)
            db.add(Session(parade_night_id=pn.id, squadron_id=s703.id, period_number=period,
                           curriculum_item_id=c.id if c else None,
                           curriculum_code_at_time=code, curriculum_title_at_time=c.title if c else code,
                           phase_at_time=phase, facilitator_id=f.id if f else None,
                           facilitator_rank_at_time=f.current_rank if f else None,
                           facilitator_display_name_at_time=(f.current_rank + " " + f.last_name) if f else None,
                           training_area_id=r.id if r else None, training_area_name_at_time=room,
                           expected_attendance=15, status=status))
        db.commit()

    for sn, rank, fn, ln, phase, att, trend, s1 in [
        ("8000001", "CDT", "Avery", "Brooks", "Initial", 82.0, "steady", "complete"),
        ("8000002", "CDT", "Bailey", "Chen", "Initial", 61.0, "declining", "pending"),
        ("8000003", "LCDT", "Casey", "Donovan", "Junior", 90.0, "steady", "complete"),
    ]:
        db.add(Cadet(squadron_id=s703.id, service_number=sn, rank=rank, first_name=fn, last_name=ln,
                     phase=phase, attendance_percentage=att, recent_attendance_trend=trend,
                     sitrep_part_1_status=s1, support_flag=(att < 75)))
    db.commit()
    # Demo flights for 703 SQN (local display groupings — no separate permissions)
    s703_flights = [
        Flight(squadron_id=s703.id, name="Alpha Flight", active_status=True),
        Flight(squadron_id=s703.id, name="Bravo Flight", active_status=True),
    ]
    db.add_all(s703_flights); db.commit()

    # Assign the 703 sqn_general demo user to Alpha Flight
    alpha = s703_flights[0]
    gen703 = db.query(User).filter(User.squadron_id == s703.id, User.role == "sqn_general").first()
    if gen703:
        gen703.flight_id = alpha.id
        db.commit()

    seed_program(db, nat, wing, sqn_by_code, cur_by_code)
    seed_planning_data(db, wing, sqn_by_code)
    db.close()
    print("Seeded: National HQ, 7 Wing, 16 squadrons, users/access codes, 13 core curriculum items, 703 demo data (incl. Alpha/Bravo flights, planning year, WA holidays).")


def seed_planning_data(db, wing, sqn_by_code):
    """Seed 703 SQN 2026 planning year with WA holidays, parade dates, and prep rules."""
    from datetime import date, timedelta
    from ..models.planning import (
        PlanningYear, ParadeDate, HolidayPeriod, AnchorEvent, AnchorPrepRule,
    )
    from ..models import ParadeNight

    s703 = sqn_by_code.get("703")
    if not s703:
        return

    now = datetime.now(timezone.utc)

    # 2026 Planning Year for 703 SQN
    py = PlanningYear(
        unit_id=s703.id, wing_id=s703.wing_id, year=2026,
        name="703 SQN Training Year 2026",
        active_status=True,
        created_at=now, updated_at=now,
    )
    db.add(py); db.commit()

    # WA 2026 school holidays and public holidays
    wa_holidays = [
        ("Labour Day 2026", "2026-03-02", "2026-03-02", "public_holiday", "state", True),
        ("Good Friday 2026", "2026-04-03", "2026-04-03", "public_holiday", "national", True),
        ("Term 1 School Holidays", "2026-04-04", "2026-04-19", "school_holiday", "state", True),
        ("Anzac Day", "2026-04-25", "2026-04-25", "public_holiday", "national", True),
        ("Term 2 School Holidays", "2026-07-04", "2026-07-19", "school_holiday", "state", True),
        ("WA Day 2026", "2026-06-01", "2026-06-01", "public_holiday", "state", True),
        ("Term 3 School Holidays", "2026-09-26", "2026-10-11", "school_holiday", "state", True),
        ("King's Official Birthday 2026", "2026-09-28", "2026-09-28", "public_holiday", "state", True),
        ("Term 4 / Summer Holidays", "2026-12-18", "2027-01-31", "school_holiday", "state", True),
    ]
    for name, start, end, htype, jur, affects in wa_holidays:
        db.add(HolidayPeriod(
            planning_year_id=py.id, name=name, start_date=start, end_date=end,
            holiday_type=htype, jurisdiction=jur, affects_parade=affects,
            created_at=now, updated_at=now,
        ))
    db.commit()

    # Generate Friday parade dates for 703 SQN (2026-01-30 to 2026-12-11, skip holidays)
    holiday_ranges = [(s, e) for _, s, e, _, _, _ in wa_holidays]

    def in_holiday(d: date) -> bool:
        ds = d.isoformat()
        return any(s <= ds <= e for s, e in holiday_ranges)

    # Term date ranges for labeling
    term_ranges = {
        "T1": ("2026-01-28", "2026-04-11"),
        "T2": ("2026-04-28", "2026-06-27"),
        "T3": ("2026-07-14", "2026-09-19"),
        "T4": ("2026-10-06", "2026-12-12"),
    }

    def get_term(ds: str) -> str | None:
        for t, (ts, te) in term_ranges.items():
            if ts <= ds <= te:
                return t
        return None

    # Get existing parade nights for 703 SQN (from demo data seeded above)
    existing_pn_dates = {
        pn.date for pn in db.query(ParadeNight).filter(
            ParadeNight.squadron_id == s703.id,
            ParadeNight.is_archived == False,
        ).all()
    }

    start_date = date(2026, 1, 30)  # First Friday
    end_date   = date(2026, 12, 11)
    d = start_date
    week_num = 1
    while d <= end_date:
        if d.weekday() == 4 and not in_holiday(d):  # 4 = Friday
            ds = d.isoformat()
            # Find linked parade night
            pn_id = None
            pn = db.query(ParadeNight).filter(
                ParadeNight.squadron_id == s703.id,
                ParadeNight.date == ds,
                ParadeNight.is_archived == False,
            ).first()
            if not pn:
                pn = ParadeNight(
                    squadron_id=s703.id, wing_id=s703.wing_id,
                    date=ds, term=get_term(ds),
                    start_time=s703.default_start_time, end_time=s703.default_end_time,
                    session_count=s703.default_session_count, parade_type="normal",
                )
                db.add(pn); db.flush()
            pn_id = pn.id
            db.add(ParadeDate(
                planning_year_id=py.id, unit_id=s703.id,
                parade_date=ds, parade_type="standard",
                term=get_term(ds), week_number=week_num,
                is_active=True, parade_night_id=pn_id,
                created_at=now, updated_at=now,
            ))
            week_num += 1
        d += timedelta(days=1)
    db.commit()

    # Anchor events — demo for 703 SQN 2026
    anchors = [
        ("7 Wing Camp — Bullsbrook", "adventure_training", "must_attend", 1,
         "2026-06-05", "2026-06-07", "T2", True, True, True, True, True),
        ("Anzac Day Service", "ceremonial", "must_attend", 1,
         "2026-04-25", "2026-04-25", "T1", True, True, True, True, True),
        ("703 Annual Dinner", "dining_in", "key_event", 2,
         "2026-11-20", "2026-11-20", "T4", False, False, True, True, True),
        ("Orientation Weekend", "orientation_weekend", "key_event", 2,
         "2026-03-28", "2026-03-29", "T1", True, False, False, False, False),
    ]
    for ename, etype, imp, imp_lvl, sd, ed, term, ori, ini, jnr, inter, snr in anchors:
        db.add(AnchorEvent(
            planning_year_id=py.id, owning_level="unit",
            wing_id=s703.wing_id, unit_id=s703.id,
            event_name=ename, event_type=etype,
            importance=imp, importance_level=imp_lvl,
            start_date=sd, end_date=ed,
            audience_orientation=ori, audience_initial=ini, audience_junior=jnr,
            audience_intermediate=inter, audience_senior=snr,
            is_archived=False,
            created_at=now, updated_at=now,
        ))
    db.commit()

    # Prep rules — seeded nationally (reusable across units)
    existing_rules = db.query(AnchorPrepRule).count()
    if existing_rules == 0:
        prep_rules = [
            ("adventure_training", "Field", "Fieldcraft, navigation, first aid basics",
             "Field skills revision session", 2, 4),
            ("adventure_training", "PDL", "Leadership preparation",
             "Leadership briefing", 1, 2),
            ("ceremonial", "Drill", "Drill and ceremonial",
             "Ceremonial drill practice", 3, 6),
            ("ceremonial", "Service", "Dress and bearing standards",
             "Uniform inspection preparation", 1, 2),
            ("dining_in", "PDL", "Etiquette and protocol",
             "Dining-in briefing", 2, 3),
            ("orientation_weekend", "Service", "Overview of cadet service",
             "Orientation program brief", 1, 2),
            ("inspection", "Drill", "Parade drill and dress",
             "Inspection preparation drill", 4, 8),
            ("fieldcraft", "Field", "Navigation and camping skills",
             "Field exercise preparation", 2, 4),
        ]
        for etype, subject, tags, activity, wmin, wmax in prep_rules:
            db.add(AnchorPrepRule(
                event_type=etype, subject_area=subject,
                suggested_curriculum_tags=tags, suggested_activity=activity,
                weeks_before_min=wmin, weeks_before_max=wmax,
            ))
        db.commit()


def seed_program(db, nat, wing, sqn_by_code, cur_by_code):
    """Seed phases, Learning Hub resources, and National/Wing/Squadron program packages."""
    from ..models import (Phase, ProgramPackage, ProgramItem, LearningHubResource)
    LH = "https://airforcecadets.net.au/lh/index.php/cadet-program/"
    phases = [
        ("Orientation", "ORI", 1, True, False), ("Initial", "INL", 2, True, False),
        ("Junior", "JNR", 3, True, False), ("Intermediate", "INT", 4, True, False),
        ("Senior", "SNR", 5, True, False), ("Bronze Extension", "BRZ", 6, False, True),
        ("Silver Extension", "SLV", 7, False, True), ("Gold Extension", "GLD", 8, False, True),
        ("Personal Development & Leadership", "PDL", 9, True, False), ("Custom / Local", "LOC", 10, False, False),
    ]
    phase_by_name = {}
    for name, short, order, core, ext in phases:
        ph = Phase(name=name, short_name=short, display_order=order, is_core=core,
                   is_extension=ext, learning_hub_url=LH)
        db.add(ph); db.commit(); phase_by_name[name] = ph

    # Learning Hub resources (links only — never content)
    lh_by_code = {}
    for c in cur_by_code.values():
        r = LearningHubResource(title=f"{c.code} — {c.title}", url=c.learning_hub_url or LH,
                                phase=c.phase, resource_type="page", source="Learning Hub")
        db.add(r); db.commit(); lh_by_code[c.code] = r

    # National package — items mirror the national curriculum (code match drives coverage)
    nat_pkg = ProgramPackage(title="National Cadet Program 2026", owning_scope="national",
                             national_id=nat.id, program_year=2026, version=1, status="published",
                             published_by=None)
    db.add(nat_pkg); db.commit()
    phase_name_map = {"A. Orientation": "Orientation", "B. Initial": "Initial", "C. Junior": "Junior",
                      "D. Intermediate": "Intermediate", "E. Senior": "Senior", "I. Bronze": "Bronze Extension",
                      "J. Silver": "Silver Extension", "K. Gold": "Gold Extension"}
    for c in cur_by_code.values():
        pname = phase_name_map.get(c.phase, c.phase)
        ph = phase_by_name.get(pname)
        core = "core" if c.core_status == "core" else "optional"
        if ph and ph.is_extension:
            core = "extension"
        db.add(ProgramItem(package_id=nat_pkg.id, owning_scope="national", national_id=nat.id,
                           code=c.code, title=c.title, phase_id=ph.id if ph else None,
                           phase_name_at_time=pname, element=c.element, core_status=core,
                           foundation_or_extension=("extension" if ph and ph.is_extension else "foundation"),
                           duration_minutes=c.duration_minutes,
                           learning_hub_resource_id=lh_by_code[c.code].id, status="active"))
    db.commit()

    # Wing package — one wing-specific item, visible only within 7 Wing
    wing_pkg = ProgramPackage(title="7 Wing Supplementary Program 2026", owning_scope="wing",
                              wing_id=wing.id, program_year=2026, status="published")
    db.add(wing_pkg); db.commit()
    db.add(ProgramItem(package_id=wing_pkg.id, owning_scope="wing", wing_id=wing.id,
                       code="7WG-LOC01", title="7 Wing Field Navigation Day", phase_name_at_time="Intermediate",
                       element="Field", core_status="wing_required", duration_minutes=300, status="active"))
    db.commit()

    # 703 squadron-local package — visible only to 703 (peers must not see it)
    s703 = sqn_by_code["703"]
    sq_pkg = ProgramPackage(title="703 Squadron Local Activities 2026", owning_scope="squadron",
                            wing_id=wing.id, squadron_id=s703.id, program_year=2026, status="published")
    db.add(sq_pkg); db.commit()
    db.add(ProgramItem(package_id=sq_pkg.id, owning_scope="squadron", wing_id=wing.id, squadron_id=s703.id,
                       code="703-LOC01", title="703 Heritage Visit", phase_name_at_time="Custom / Local",
                       element="SQN", core_status="local", foundation_or_extension="local",
                       duration_minutes=180, status="active"))
    db.commit()
