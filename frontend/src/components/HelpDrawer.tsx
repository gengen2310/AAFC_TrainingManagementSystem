import { useState } from "react";

type HelpTab = "overview" | "tasks" | "glossary" | "support";

interface Props {
  onClose: () => void;
}

const GLOSSARY: { term: string; definition: string }[] = [
  {
    term: "Training Management System (TMS)",
    definition:
      "The AAFC system for managing squadron accounts, facilitators, training areas, activities, and curriculum. TMS is the organisation's record of truth. Access it at the main URL your wing provided.",
  },
  {
    term: "Planning Workspace",
    definition:
      "The AAFC training planner. Use it to set up a Training Year, schedule parade nights, assign curriculum to sessions, and track training delivery.",
  },
  {
    term: "Training Year",
    definition:
      "A container that groups all parade nights and training records for one academic year — typically July to June. A Training Year must exist before you can schedule parade nights or record outcomes.",
  },
  {
    term: "Training Stage",
    definition:
      "A defined AAFC curriculum level, such as Initial, Junior, Intermediate, Senior, Bronze, Silver, or Gold. Each stage has a national set of required modules that all squadrons deliver.",
  },
  {
    term: "Training Class",
    definition:
      "A squadron-specific group completing a Training Stage in a given Training Year. A squadron with 30 senior cadets might have two classes — Senior 1 and Senior 2 — each with its own independent progress record. The distinction matters because two classes at the same stage can be at different points in the curriculum: Senior 1 may have completed a module that Senior 2 still has planned. The system tracks them separately so you can see exactly what each class still needs.",
  },
  {
    term: "Parade Night",
    definition:
      "A scheduled training evening. Each parade night appears as a date on the planning calendar and can hold multiple sessions across different time periods.",
  },
  {
    term: "Training Period",
    definition:
      "One training block within a parade night — a specific curriculum item, period number, one or more Training Classes, facilitator, and room. A Training Period can serve a single class or several classes at once (for example, Senior 1 and Senior 2 attending the same lesson together). A parade night typically has six Training Periods and may run several in parallel.",
  },
  {
    term: "Mission Backlog",
    definition:
      "A list of curriculum modules that are required for your active Training Classes but have not yet been scheduled. The backlog tells you what still needs to be planned and for which classes.",
  },
  {
    term: "Anchor Event",
    definition:
      "A fixed event that appears on the planning calendar but is not a curriculum session — for example, a wing parade, camp, or stand-down. Anchor events help frame the training year.",
  },
  {
    term: "Facilitator",
    definition:
      "A person who can deliver training — an officer, NCO, or civilian staff member. Facilitators are managed in TMS and assigned to sessions in Planning Workspace.",
  },
  {
    term: "Training Area",
    definition:
      "A room, space, or facility available for training — for example, a classroom, gym, or parade ground. Training areas are managed in TMS and assigned to sessions.",
  },
  {
    term: "Activities",
    definition:
      "The national and local curriculum items available for scheduling. National activities come from the AAFC curriculum; your wing and squadron can add local activities. Activities appear in the bottom panel of Planning Workspace.",
  },
  {
    term: "Command Centre",
    definition:
      "A summary panel showing your squadron's planning health: how many nights are scheduled, how many sessions are assigned, and how many curriculum requirements remain unscheduled.",
  },
  {
    term: "Rollover",
    definition:
      "Copying a Training Year's settings (parade-day, timing template) into a new year. Use rollover at the start of a new academic year instead of setting everything up from scratch.",
  },
];

const TASKS: { title: string; steps: string[] }[] = [
  {
    title: "Set up a Training Year",
    steps: [
      "Open Planning Workspace.",
      "If no Training Year exists, the setup panel appears automatically. Fill in the year number and name, then select 'Create planning year'.",
      "On the next step, choose your parade weekday, start date, end date, and frequency.",
      "Select 'Generate parade dates'. Your parade nights appear on the calendar.",
      "If a year already exists, select 'Guided year setup…' in the toolbar to add another year or roll over from the previous year.",
    ],
  },
  {
    title: "Add a Facilitator",
    steps: [
      "In TMS, select 'Facilitators' from the navigation menu.",
      "Select 'Add facilitator'.",
      "Enter the facilitator's name, rank, and type (Officer, NCO, Senior Cadet, or Civilian).",
      "Select 'Save'. The facilitator is now available for session assignment in Planning Workspace.",
    ],
  },
  {
    title: "Add a Training Area",
    steps: [
      "In TMS, select 'Training Areas & Equipment' from the navigation menu.",
      "Select 'Add training area'.",
      "Enter the area name, type, and capacity.",
      "Select 'Save'. The area is now available for session assignment in Planning Workspace.",
    ],
  },
  {
    title: "Schedule a training session",
    steps: [
      "In Planning Workspace, select a parade night date on the calendar.",
      "Click an empty time-period cell to open the session panel.",
      "Select the curriculum item, one or more Training Classes, facilitator, and room.",
      "Select 'Save'. The session appears on the parade night.",
    ],
  },
  {
    title: "Schedule one session for two or more Training Classes",
    steps: [
      "Click an empty time-period cell to open the session panel.",
      "Select the curriculum item and then select all the Training Classes that will attend this session together — for example, Senior 1 and Senior 2.",
      "Select the facilitator and room.",
      "Select 'Save'. The system records the delivery against each selected class independently.",
      "If one of the classes already has a session assigned to this period, a conflict warning appears. You can override it if the combined arrangement is correct.",
    ],
  },
  {
    title: "Record a training outcome",
    steps: [
      "After the parade night, open Planning Workspace and find the night.",
      "Click the session you want to update.",
      "Change the status to Delivered, Cancelled, or Not Delivered.",
      "Add any notes about the outcome.",
      "Select 'Save'.",
    ],
  },
  {
    title: "Create several classes for one Training Stage",
    steps: [
      "In TMS, go to Curriculum.",
      "Select 'Training Classes', then 'Add Training Class'.",
      "Select the Training Stage (for example, Senior) and enter the class name (for example, Senior 1).",
      "Repeat to create Senior 2, Senior 3, and so on.",
      "Each class has its own independent progress records in Planning Workspace.",
    ],
  },
  {
    title: "Understand the Mission Backlog",
    steps: [
      "Open Planning Workspace. The left panel shows the Mission Backlog.",
      "Each item in the backlog is a curriculum module required for at least one Training Class but not yet scheduled.",
      "Select an item to see which classes still need it.",
      "Drag or click the item to schedule it on a parade night.",
    ],
  },
  {
    title: "Generate Parade Nights for a new training year",
    steps: [
      "Open Planning Workspace and select 'Guided year setup…' in the toolbar.",
      "Choose 'Roll over from previous year' to copy settings, or 'Create new year' to start fresh.",
      "Set the parade weekday, start date, end date, and frequency.",
      "Select 'Generate'. Review the date preview before confirming.",
    ],
  },
];

export function HelpDrawer({ onClose }: Props) {
  const [tab, setTab] = useState<HelpTab>("overview");
  const [openTask, setOpenTask] = useState<number | null>(null);
  const [openGlossary, setOpenGlossary] = useState<number | null>(null);

  return (
    <div className="pw-help-drawer" role="complementary" aria-label="Help and reference">
      <div className="pw-help-header">
        <div className="pw-help-title">Help &amp; Reference</div>
        <button
          className="pw-help-close"
          aria-label="Close help panel"
          onClick={onClose}
        >
          ✕
        </button>
      </div>

      <div className="pw-help-tabs" role="tablist">
        {(["overview", "tasks", "glossary", "support"] as HelpTab[]).map((t) => (
          <button
            key={t}
            role="tab"
            aria-selected={tab === t}
            className={`pw-help-tab${tab === t ? " active" : ""}`}
            onClick={() => setTab(t)}
          >
            {t === "overview" ? "Overview" : t === "tasks" ? "How to…" : t === "glossary" ? "Glossary" : "Support"}
          </button>
        ))}
      </div>

      <div className="pw-help-body">
        {tab === "overview" && (
          <div className="pw-help-section">
            <h3>Two systems, one program</h3>
            <p>
              The AAFC Training Management System has two parts that work together.
              Understanding the difference helps you know where to go for each task.
            </p>

            <div className="pw-help-compare">
              <div className="pw-help-compare-col">
                <div className="pw-help-compare-head">TMS — Training Management System</div>
                <p>The main system. Manages your organisation's records.</p>
                <ul>
                  <li>Create and manage accounts</li>
                  <li>Manage facilitators</li>
                  <li>Manage training areas and equipment</li>
                  <li>View reports and dashboards</li>
                  <li>Configure squadron settings</li>
                  <li>Manage curriculum and activities</li>
                </ul>
                <p className="pw-help-note">
                  <strong>Access via:</strong> the main TMS URL your wing provided (typically at a different address to Planning Workspace).
                </p>
              </div>

              <div className="pw-help-compare-col">
                <div className="pw-help-compare-head">Planning Workspace — this screen</div>
                <p>The planner. Schedules training and tracks delivery.</p>
                <ul>
                  <li>Create a Training Year</li>
                  <li>Generate parade night dates</li>
                  <li>Schedule curriculum sessions</li>
                  <li>Assign facilitators and rooms</li>
                  <li>Record outcomes after each night</li>
                  <li>Review Mission Backlog</li>
                </ul>
                <p className="pw-help-note">
                  <strong>Access via:</strong> the Planning Workspace link in TMS navigation, or directly via the /planning URL.
                </p>
              </div>
            </div>

            <h3>Before you begin</h3>
            <p>
              Before using Planning Workspace, set up the following in TMS:
            </p>
            <ol className="pw-help-checklist">
              <li>Squadron details (name, parade day, parade location)</li>
              <li>At least one facilitator</li>
              <li>At least one training area</li>
              <li>Training Classes for each active Training Stage</li>
            </ol>
            <p>
              Once those are in place, return to Planning Workspace to create a Training Year, generate parade nights, and start scheduling.
            </p>

            <h3>First time in Planning Workspace?</h3>
            <p>
              If no Training Year exists yet, the setup panel opens automatically. It guides you through creating a year and generating your parade night dates.
            </p>
            <p>
              Once you have a Training Year, use{" "}
              <strong>Guided year setup…</strong> in the toolbar at any time to add another year, roll over to a new year, or adjust your parade settings.
            </p>
          </div>
        )}

        {tab === "tasks" && (
          <div className="pw-help-section">
            <p className="pw-help-intro">
              Select a task below for step-by-step instructions.
            </p>
            <div className="pw-help-accordion">
              {TASKS.map((task, i) => (
                <div key={i} className="pw-help-accordion-item">
                  <button
                    className={`pw-help-accordion-btn${openTask === i ? " open" : ""}`}
                    onClick={() => setOpenTask(openTask === i ? null : i)}
                    aria-expanded={openTask === i}
                  >
                    {task.title}
                    <span className="pw-help-accordion-chevron">{openTask === i ? "▲" : "▼"}</span>
                  </button>
                  {openTask === i && (
                    <div className="pw-help-accordion-body">
                      <ol>
                        {task.steps.map((step, j) => (
                          <li key={j}>{step}</li>
                        ))}
                      </ol>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {tab === "glossary" && (
          <div className="pw-help-section">
            <p className="pw-help-intro">
              Definitions of key terms used throughout TMS and Planning Workspace.
            </p>
            <div className="pw-help-accordion">
              {GLOSSARY.map((entry, i) => (
                <div key={i} className="pw-help-accordion-item">
                  <button
                    className={`pw-help-accordion-btn${openGlossary === i ? " open" : ""}`}
                    onClick={() => setOpenGlossary(openGlossary === i ? null : i)}
                    aria-expanded={openGlossary === i}
                  >
                    {entry.term}
                    <span className="pw-help-accordion-chevron">{openGlossary === i ? "▲" : "▼"}</span>
                  </button>
                  {openGlossary === i && (
                    <div className="pw-help-accordion-body">
                      <p>{entry.definition}</p>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {tab === "support" && (
          <div className="pw-help-section">
            <h3>Get help</h3>
            <p>
              If you cannot find an answer in this Help panel, contact your Wing SOCAD (Squadron Organisation and Cadet Administration) officer.
            </p>
            <p>
              Your Wing SOCAD can help with:
            </p>
            <ul>
              <li>Account access issues</li>
              <li>Missing or incorrect curriculum items</li>
              <li>Wing-level configuration</li>
              <li>New squadron setup</li>
            </ul>

            <h3>Report a technical issue</h3>
            <p>
              If you have found a bug or the system is not working as expected, report it to your Wing SOCAD with the following information:
            </p>
            <div className="pw-help-report-template">
              <div className="pw-help-report-label">What to include in your report:</div>
              <ul>
                <li><strong>Squadron</strong> — your squadron name and number</li>
                <li><strong>Role</strong> — your account role (for example, Sqn Admin)</li>
                <li><strong>What you were trying to do</strong> — for example, "create a new session on 15 August"</li>
                <li><strong>What happened</strong> — the exact error message or unexpected behaviour</li>
                <li><strong>Approximate time</strong> — when the issue occurred</li>
                <li><strong>Browser</strong> — for example, Chrome, Firefox, Safari</li>
              </ul>
            </div>

            <h3>Common problems</h3>
            <div className="pw-help-faq">
              <div className="pw-help-faq-item">
                <div className="pw-help-faq-q">I can see the calendar but no sessions appear.</div>
                <div className="pw-help-faq-a">Check that a Training Year has been created and parade nights have been generated. Use 'Guided year setup…' in the toolbar.</div>
              </div>
              <div className="pw-help-faq-item">
                <div className="pw-help-faq-q">I cannot assign a facilitator to a session.</div>
                <div className="pw-help-faq-a">Facilitators must be set up in TMS first. In TMS, go to Facilitators and add the person, then return to Planning Workspace.</div>
              </div>
              <div className="pw-help-faq-item">
                <div className="pw-help-faq-q">The Mission Backlog shows items I have already delivered.</div>
                <div className="pw-help-faq-a">Make sure the session outcome is recorded as 'Delivered'. Open the session in Planning Workspace and update the status.</div>
              </div>
              <div className="pw-help-faq-item">
                <div className="pw-help-faq-q">My parade nights are on the wrong day.</div>
                <div className="pw-help-faq-a">Use 'Update future parade nights…' in the toolbar to change the day for upcoming nights without affecting past records.</div>
              </div>
              <div className="pw-help-faq-item">
                <div className="pw-help-faq-q">I cannot log in.</div>
                <div className="pw-help-faq-a">Contact your Wing SOCAD to reset your access code. Access codes cannot be retrieved — they can only be reset.</div>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
