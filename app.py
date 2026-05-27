# =============================================================================
#  surveychat - Chatbot Surveys and Randomized Experiments
# =============================================================================
#
#  PURPOSE
#  -------
#  surveychat supports two use modes:
#
#  Survey mode  (N_CONDITIONS = 1)
#    Every participant talks to the same chatbot.  No passcodes, no
#    randomization.  Use this for open-ended interviews, cognitive
#    interviewing, pilot testing, or any qualitative data collection that
#    benefits from a conversational format rather than a plain text box.
#    Examples: exploratory interviews, pilot testing, cognitive debriefs,
#    and any study where adaptive follow-up questions driven by participant
#    responses would produce richer data than a fixed question list.
#
#  Experiment mode  (N_CONDITIONS >= 2)
#    Participants are routed to one of N chatbot "conditions", each defined
#    by a unique system prompt and model choice.  Use this for A/B tests or
#    multi-arm studies that compare how different chatbot styles affect
#    participant responses, attitudes, or behaviour.
#    Examples: comparing empathetic vs. neutral interviewers, testing
#    different question orderings, or manipulating response thoroughness.
#
#    Current study adaptation: the native routing shell is reused for two
#    opaque learning-sequence routes.  The Socratic tutor and model remain
#    constant; only the instruction/problem-solving phase order changes.
#
#  In both modes the participant completes the learning activity and copies a
#  minimal JSON completion record back into the parent survey tool (e.g.
#  Qualtrics).  The current study payload deliberately excludes participant
#  chat messages and the submitted study-ideas text, while retaining assistant
#  messages for tutor-output audit.
#
#  COPY-BACK FORMAT
#  ----------------
#  After completion, the participant receives a JSON block:
#
#      {
#        "schema_version": "chatbot_stage_v1",
#        "route_code": "Q7M2",
#        "completion_status": "complete",
#        "total_duration_seconds": 1234.5,
#        "phase_records": [...],
#        "rsm_count": {"value": "3 ideas"},
#        "process_metadata": {...},
#        "assistant_messages": [...],
#        "errors": []
#      }
#
#  Absolute timestamps, condition name, model, participant chat messages, and
#  submitted study-ideas text are deliberately excluded from the participant-
#  visible payload.
#
#  Parse in Python:
#      import json, pandas as pd
#      data = json.loads(study_data_string)
#      df   = pd.json_normalize(data)
#
#  Parse in R:
#      library(jsonlite)
#      data <- fromJSON(study_data_string)
#      df   <- as.data.frame(data)
#
#  INTEGRATION WITH SURVEY TOOLS
#  ------------------------------
#  Survey mode:
#    (1) Add a Text / Graphic block in Qualtrics with a link to the app.
#    (2) After the chat, add a Text Entry question where participants
#        paste their study-data JSON.
#
#  Experiment mode:
#    (1) Use Qualtrics Survey Flow > Randomizer to split participants.
#    (2) In each arm display the matching passcode and the app URL.
#    (3) After the activity, add a Text Entry question for the study-data JSON.
#    (4) Export responses - treatment assignment is recovered from the
#        passcode stored in the relevant Qualtrics branch variable.
#
#  DEPLOYMENT OPTIONS
#  ------------------
#  Local development:
#      streamlit run app.py
#
#  Streamlit Community Cloud (free, no server needed):
#      Push the repo to GitHub, connect at share.streamlit.io, and add
#      OPENAI_API_KEY under Advanced settings → Secrets.
#
#  Cloud VM (e.g. AWS EC2, DigitalOcean, Azure):
#      pip install -r requirements.txt
#      streamlit run app.py --server.port 80 --server.headless true
#      Serve HTTPS via Caddy or nginx (required for Qualtrics iFrame embeds).
#
#  LLM PROVIDERS
#  -------------
#  Set API_BASE_URL to any chat-completions-compatible endpoint:
#      UvA LLM proxy:     https://llmproxy.uva.nl
#      OpenAI:            https://api.openai.com/v1
#      Azure via LiteLLM: https://your-proxy.azurewebsites.net
#      OpenRouter:        https://openrouter.ai/api/v1
#      Local (LiteLLM):   http://localhost:4000
#
#  QUICK START
#  -----------
#  1. Edit the RESEARCHER CONFIGURATION section below.
#  2. Add your OPENAI_API_KEY to the .env file (see .env.example).
#  3. Run:   streamlit run app.py
#
#  FORKING & REUSE
#  ---------------
#  This file is intentionally self-contained.  The only section you need
#  to edit for most studies is the RESEARCHER CONFIGURATION block below.
#  Everything else - session management, participant routing, study-data
#  copy-back, and the chat UI - is handled for you automatically.
#
# =============================================================================


# ── Standard library ──────────────────────────────────────────────────────────
import json
import os
import random
from datetime import datetime, timezone
from pathlib import Path

# ── Third-party ───────────────────────────────────────────────────────────────
import streamlit as st
from openai import OpenAI
from dotenv import load_dotenv          # reads .env into os.environ automatically

try:
    import streamlit.components.v1 as components
except Exception:  # pragma: no cover - test mocks may not expose components
    components = None

from study_content import (
    CANONICAL_SOLUTION_FIGURE_CAPTION,
    CANONICAL_SOLUTION_FIGURE_PATH,
    COPY_STUDY_DATA_INSTRUCTION,
    INSTRUCTION_AFTER_PROBLEM_SOLVING_STIMULUS_OPENING,
    INSTRUCTION_ENTRY,
    INSTRUCTION_FIRST_STIMULUS_OPENING,
    INSTRUCTION_TO_PROBLEM_SOLVING_TRANSITION,
    INSTRUCTIONAL_STIMULUS_AFTER_FIGURE,
    INSTRUCTIONAL_STIMULUS_BEFORE_FIGURE,
    PROBLEM_SOLVING_CHAT_INSTRUCTION,
    PROBLEM_SOLVING_ENTRY,
    PROBLEM_SOLVING_INSTRUCTIONS,
    PROBLEM_SOLVING_TASK_PROMPT,
    PROBLEM_SOLVING_TO_INSTRUCTION_TRANSITION,
    RSM_COUNT_OPTIONS,
    RSM_COUNT_PROMPT,
    SESSION_INTRODUCTION,
    SHARED_PROBLEM_BACKGROUND,
    SHOW_FULL_RESEARCH_PROBLEM_LABEL,
    STUDY_IDEAS_SAVE_NOTE,
)

# Load the .env file so that OPENAI_API_KEY is available via os.environ
# even when the app is run without pre-exporting it in the shell.
load_dotenv()


# =============================================================================
#  HELPER FUNCTIONS
# =============================================================================
#
#  Three helper functions used by the main interface below:
#
#  validate_passcode_routing(conditions, n_conditions)
#    Checks that the passcode configuration is internally consistent and
#    halts the app with an actionable error message if not.  Called during
#    the configuration-validation phase, before any participant-facing UI
#    is rendered.
#
#  build_api_messages(conversation, system_prompt)
#    Constructs the full message list sent to the LLM API for each turn,
#    prepending the hidden system prompt at position 0.
#
#  build_transcript(messages)
#    Legacy utility for formatting a conversation transcript. The current
#    formal copy-back payload does not call this helper.

def validate_passcode_routing(conditions: list, n_conditions: int) -> None:
    """
    Check passcode-routing configuration and halt the app on any inconsistency.

    Enforces three invariants:
      1. If any active condition defines a "passcode" field, every active
         condition must define one (no partial configuration).
      2. Every passcode value must be a non-empty string after stripping
         leading and trailing whitespace.
      3. All passcodes must be unique when compared case-insensitively.

    Any violation triggers a descriptive on-screen error via st.error() and
    stops execution with st.stop(), so researchers see the problem
    immediately rather than discovering it mid-study.

    Parameters
    ----------
    conditions : list[dict]
        The full CONDITIONS list from the researcher configuration section.
    n_conditions : int
        The N_CONDITIONS value.  Only the first n_conditions entries are
        considered active; any extras are ignored.
    """
    active    = conditions[:n_conditions]
    passcoded = [c for c in active if "passcode" in c]

    # Invariant 1: Partial configuration - some but not all conditions define
    # a passcode.  Either every arm needs a passcode (passcode routing) or
    # none do (random routing).  A mixed state is always a mistake.
    if 0 < len(passcoded) < n_conditions:
        st.error(
            f"Passcode routing is partially configured: **{len(passcoded)}** of "
            f"**{n_conditions}** active conditions have a `\"passcode\"` field. "
            "Either add a `\"passcode\"` to every condition or remove them all."
        )
        st.stop()

    if len(passcoded) == n_conditions:
        # Invariant 2: No blank passcode strings.
        if any(not c["passcode"].strip() for c in active):
            st.error(
                "One or more condition `\"passcode\"` values are empty strings. "
                "Every passcode must contain at least one character."
            )
            st.stop()

        # Invariant 3: All passcodes must be unique (case-insensitive).
        passcodes = [c["passcode"].strip().lower() for c in active]
        if len(passcodes) != len(set(passcodes)):
            st.error(
                "Two or more conditions share the same `\"passcode\"` value. "
                "Every condition must have a unique passcode."
            )
            st.stop()


def build_api_messages(conversation: list, system_prompt: str) -> list:
    """
    Construct the message list to send to the LLM API for a single turn.

    The system prompt is inserted as a {"role": "system"} message at
    position 0.  Participants never see this text, but it defines the
    model's entire persona and behavioral instructions for the conversation.

    Only "role" and "content" are forwarded from the conversation history.
    The "timestamp" key is local-only metadata that the chat completions API
    does not accept and would cause a validation error if included.

    Parameters
    ----------
    conversation : list[dict]
        The current value of st.session_state["messages"].  Each element
        has "role" ("user" or "assistant"), "content", and "timestamp" keys.
    system_prompt : str
        The hidden system prompt from the active condition dict.

    Returns
    -------
    list[dict]
        A list of {"role": str, "content": str} dicts ready for the
        chat completions endpoint.
    """
    return (
        [{"role": "system", "content": system_prompt}]
        + [
            {"role": m["role"], "content": m["content"]}
            for m in conversation
        ]
    )


def build_transcript(messages: list) -> dict:
    """
    Format the conversation history as a legacy transcript object.

    The current thesis copy-back payload deliberately does not include this
    object; it is retained only as a reusable utility from the original
    surveychat template.

    Returns a JSON-serialisable dict with a single "messages" key.  Each
    entry carries:
      - "role"      : "participant" (relabelled from "user") or "assistant"
      - "content"   : the full text of the message
      - "timestamp" : UTC ISO-8601 string, e.g. "2026-03-06T14:22:01+00:00"

    Design notes:
      - "user" is relabelled "participant" so researchers get a domain-
        appropriate label if this legacy helper is reused for parsing in Python
        or R outside the current thesis payload.
      - Condition name and model are intentionally excluded.  In experiment
        mode, participants must not be able to infer their assigned condition
        from any participant-visible exported object.
        Treatment assignment is recovered separately from the passcode stored
        in the survey platform's response data.
      - In survey mode (N_CONDITIONS = 1) there is only one condition, so
        excluding the name is a no-op, but it keeps the transcript format
        identical across both modes.

    Parameters
    ----------
    messages : list[dict]
        The current value of st.session_state["messages"].

    Returns
    -------
    dict
        Transcript object suitable for json.dumps(indent=2, ensure_ascii=False).
    """
    return {
        "messages": [
            {
                "role":      "participant" if m["role"] == "user" else "assistant",
                "content":   m["content"],
                "timestamp": m.get("timestamp", ""),
            }
            for m in messages
        ],
    }


def normalize_route_code(value) -> str | None:
    """
    Normalize an opaque Qualtrics route code for case-insensitive matching.

    Returns None for missing, blank, or non-string values so invalid URL
    parameters fall through to the manual passcode fallback without disclosing
    which codes are valid.
    """
    if not isinstance(value, str):
        return None
    normalized = value.strip().upper()
    return normalized or None


def get_query_param(name: str) -> str | None:
    """
    Read a single Streamlit query parameter across Streamlit API versions.

    The current Streamlit API exposes st.query_params; older versions expose
    st.experimental_get_query_params().  Both may return list-like values.
    """
    value = None
    try:
        query_params = getattr(st, "query_params", None)
        if query_params is not None:
            value = query_params.get(name)
    except Exception:
        value = None

    if value is None:
        try:
            getter = getattr(st, "experimental_get_query_params", None)
            if getter is not None:
                value = getter().get(name)
        except Exception:
            value = None

    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value if isinstance(value, str) else None


def resolve_route_code(route_code, conditions: list, n_conditions: int) -> int | None:
    """
    Resolve an opaque route code to an active condition index.

    Only "route_code" and fallback "passcode" fields are considered.  Internal
    condition labels such as I_PS or PS_I are deliberately not accepted.
    """
    normalized = normalize_route_code(route_code)
    if normalized is None:
        return None

    for idx, condition in enumerate(conditions[:n_conditions]):
        candidates = [
            normalize_route_code(condition.get("route_code")),
            normalize_route_code(condition.get("passcode")),
        ]
        if normalized in candidates:
            return idx
    return None


def get_phase_sequence(condition: dict) -> tuple:
    """Return the configured learning-phase sequence for a condition."""
    return tuple(condition.get("phase_sequence", ("problem_solving",)))


def should_show_full_problem_expander(phase_index: int) -> bool:
    """Show collapsed problem context only when problem solving follows another phase."""
    return phase_index > 0


def count_participant_messages(messages: list) -> int:
    """Count participant/user turns in the problem-solving chat."""
    return sum(1 for message in messages if message.get("role") == "user")


def seconds_between(started_at: str, ended_at: str) -> float | None:
    """Return rounded seconds between two ISO datetimes, or None if invalid."""
    try:
        start = datetime.fromisoformat(started_at)
        end = datetime.fromisoformat(ended_at)
    except (TypeError, ValueError):
        return None
    return round((end - start).total_seconds(), 3)


def summarize_phase_records(phase_records: list) -> list:
    """Strip absolute timestamps and keep only phase labels and durations."""
    summary = []
    for record in phase_records:
        item = {"phase": record.get("phase", "")}
        duration = seconds_between(record.get("started_at"), record.get("ended_at"))
        if duration is not None:
            item["duration_seconds"] = duration
        summary.append(item)
    return summary


def summarize_errors(errors: list) -> list:
    """Keep coarse recovery metadata without absolute timestamps."""
    return [
        {
            "type": error.get("type", ""),
            "recovered": bool(error.get("recovered", False)),
        }
        for error in errors
    ]


def extract_assistant_messages(messages: list) -> list:
    """Return assistant response text only, without participant messages."""
    return [
        {"content": (message.get("content") or "")}
        for message in messages
        if message.get("role") == "assistant"
    ]


def build_study_payload(
    *,
    route_code: str,
    messages: list,
    final_answer: dict,
    rsm_count: dict,
    phase_records: list,
    errors: list,
    started_at: str,
    completed_at: str,
    completion_status: str = "complete",
) -> dict:
    """
    Build the enriched Qualtrics copy-back payload for the chatbot stage.

    The participant-visible payload intentionally excludes pid, condition
    labels, model names, interpretable sequence labels, participant chat
    messages, and the submitted study-ideas text.
    """
    final_answer_content = (final_answer.get("content") or "").strip()
    return {
        "schema_version": "chatbot_stage_v1",
        "route_code": normalize_route_code(route_code) or "",
        "completion_status": completion_status,
        "total_duration_seconds": seconds_between(started_at, completed_at),
        "phase_records": summarize_phase_records(phase_records),
        "rsm_count": {"value": rsm_count.get("value", "")},
        "process_metadata": {
            "participant_turn_count": count_participant_messages(messages),
            "assistant_turn_count": sum(
                1 for message in messages if message.get("role") == "assistant"
            ),
            "study_ideas_submitted": bool(final_answer_content),
            "study_ideas_char_count": len(final_answer_content),
        },
        "assistant_messages": extract_assistant_messages(messages),
        "errors": summarize_errors(errors),
    }


def request_scroll_top() -> None:
    """Mark the next rerun as a deliberate page transition."""
    st.session_state["_scroll_to_top"] = True


def render_scroll_top_if_requested() -> None:
    """Scroll to the top after explicit page or phase transitions."""
    if not st.session_state.pop("_scroll_to_top", False):
        return
    if components is None:
        return
    components.html(
        """
        <script>
        const scrollTargets = [window, window.parent];
        for (const target of scrollTargets) {
          try {
            target.scrollTo({ top: 0, left: 0, behavior: "instant" });
          } catch (error) {
            try { target.scrollTo(0, 0); } catch (_) {}
          }
        }
        </script>
        """,
        height=0,
        width=0,
    )


# ╔═════════════════════════════════════════════════════════════════════════════╗
# ║  ✏️  RESEARCHER CONFIGURATION - edit this section to set up your study    ║
# ╚═════════════════════════════════════════════════════════════════════════════╝

# ── LLM API settings ──────────────────────────────────────────────────────────
#
#  API_BASE_URL  The base URL for your LLM API endpoint.
#                - UvA LLM proxy (default):
#                    "https://llmproxy.uva.nl"
#                - Azure LiteLLM proxy:
#                    "https://ai-research-proxy.azurewebsites.net"
#                - OpenAI:
#                    "https://api.openai.com/v1"
#                - OpenRouter:
#                    "https://openrouter.ai/api/v1"
#                - HuggingFace Inference API:
#                    "https://api-inference.huggingface.co/v1"
#                  (set OPENAI_API_KEY to your HuggingFace token;
#                   set "model" to the HF model ID, e.g.
#                   "meta-llama/Llama-3.3-70B-Instruct")
#
#  The API key is read from OPENAI_API_KEY in the .env file - do not paste
#  keys directly here.
API_BASE_URL = "https://llmproxy.uva.nl"

# ── How many chatbot conditions does your study have? ─────────────────────────
#
#   N_CONDITIONS = 1   →  Survey mode.  Every participant talks to the same
#                          chatbot.  No passcodes or randomization needed.
#                          The passcode gate screen is suppressed entirely;
#                          participants go straight to the chat.
#                          Use this for structured or semi-structured
#                          interviews, pilot testing, cognitive debriefs, or
#                          any study where a conversation replaces a plain
#                          text-entry question.
#
#   N_CONDITIONS = 2   →  Experiment mode, classic A/B test.
#                          Participants are split ~50 / 50 across two
#                          conditions and enter a passcode to reach their arm.
#
#   N_CONDITIONS = 3+  →  Experiment mode, multi-arm.
#                          Participants are split as evenly as possible across
#                          all conditions.
#
#   Default: 2
N_CONDITIONS = 2

# ── Define each chatbot condition ─────────────────────────────────────────────
#
#  Add one dictionary per condition.  You MUST have at least N_CONDITIONS
#  entries.  Any extra entries beyond N_CONDITIONS are silently ignored.
#
#  Fields per condition
#  --------------------
#  "name"           Short internal label used in log messages and debug info.
#                   Never shown to participants.  Keep it descriptive enough
#                   to identify the condition when reviewing data or logs.
#
#  "passcode"       Passcode that routes participants to this condition.
#                   Only needed in experiment mode (N_CONDITIONS > 1).
#                   Assign one unique passcode per condition and configure
#                   your survey tool to display the correct passcode to each
#                   participant before they open the chat link.
#                   Matching is case-insensitive ("alpha" == "ALPHA").
#                   Omit this field entirely when N_CONDITIONS = 1.
#
#  "system_prompt"  The hidden instruction sent to the model at the very
#                   start of every conversation.  Participants never see
#                   this text, but it defines the chatbot's entire persona,
#                   tone, and behavioral boundaries.
#
#                   In survey mode, treat this as an interviewer brief:
#                   describe the study topic, the interview style, how to
#                   handle off-topic responses, and when to wrap up.
#
#                   In experiment mode, make sure the prompts differ clearly
#                   between conditions so the manipulation is strong and its
#                   effects are detectable in your outcome measures.
#
#  "model"          The model identifier string for this condition.
#                   Common options:
#                     "gpt-5.1"       - GPT-5.1 via the configured proxy
#                     "gpt-oss-120b"  - large open-weights model
#                     "gpt4o"         - GPT-4o via OpenAI / Azure
#                     "gpt4o-mini"    - GPT-4o Mini, faster and cheaper
#                   Different conditions can use different models if you want
#                   to directly compare model-level effects.
#
#  Tips
#  ----
#  - In experiment mode use short, neutral passcodes ("ALPHA"/"BETA",
#    colours, animals) that give participants no hint of their condition.
#  - System prompts work best when they specify tone, task, and limits all
#    at once.  Vague prompts produce inconsistent behavior across sessions.
#  - Test each condition manually before launching the study.
#
#  Survey mode example (N_CONDITIONS = 1, no "passcode" field needed):
#  ─────────────────────────────────────────────────────────────────────
#  CONDITIONS = [
#      {
#          "name":          "Social-media interview bot",
#          "system_prompt": (
#              "You are a friendly research interviewer studying how people "
#              "use social media in their daily lives.  Ask one open-ended "
#              "question at a time, listen carefully, and ask follow-up "
#              "questions to explore the participant's experience in depth. "
#              "After 5-7 exchanges, thank the participant warmly and let "
#              "them know they can click End this chat."
#          ),
#          "model": "gpt-oss-120b",
#      },
#  ]

SOCRATIC_TUTOR_PROMPT = """
ROLE AND INVARIANCE
You are the same Socratic AI discussion partner in every sequence condition of an academic study about research-design reasoning.
The participant is working on a scenario about whether social media use increases anxiety.
Use the same behavior regardless of whether the participant has already completed the instruction phase.
Do not refer to phase order, other conditions, randomization, study hypotheses, scoring rules, what the participant will see later, or how the study will evaluate them.

PEDAGOGICAL OBJECTIVE
Help the participant generate, compare, and revise their own study ideas.
Do not optimize for producing a correct final answer.
Preserve productive struggle while making limitations in the participant's own ideas visible.
Encourage the participant to consider more than one possible study idea before narrowing or submitting.
Use diagnostic cueing to help the participant experience the limits of a current idea and move toward another idea, comparison, or revision.
Do not use cueing to coach one idea step by step into the canonical design.
Track whether the dialogue is still developing the same participant-generated study idea. When the discussion has stayed with one idea for several tutor turns, use only a brief soft reminder that the activity encourages several study ideas, then ask whether the participant has another idea or wants to keep developing the current one. Do not suggest a specific alternative direction.

AUTHORIZED RESOURCES
Use only the focal scenario, the participant's current and previous messages, and the task instructions.
Do not introduce outside facts, examples, claims, advice, or statistics about social media, anxiety, diagnosis, mental health, or communication effects.

DIAGNOSTIC BOUNDARY POLICY
Do not use or rely on a hidden canonical solution.
Do not reveal, name, list, or assemble the canonical solution.
Do not provide direct instruction, a completed study design, a checklist of required components, or the target design name.
Avoid course-label wording such as "2 x 2 factorial design", "pretest", "posttest", and "control variable" unless the participant already uses those words.
If the participant uses one of those terms, ask them to explain how it would work in their own proposed study rather than certifying that the term is correct.

SOCRATIC MOVE POLICY
Before giving a diagnostic cue, first elicit at least one concrete study idea from the participant.
If the participant has no idea, ask a scenario-based starter question rather than giving design components.
Use these moves when appropriate:
- clarify the participant's proposed comparison;
- ask what would be varied or observed;
- ask what evidence would distinguish between two explanations;
- ask what alternative explanation remains possible;
- ask what information is missing;
- ask the participant to compare two possible study ideas;
- briefly remind the participant that they may explore another study idea, then ask whether they have a new idea or want to continue developing the current one;
- ask for one concrete revision to their current idea.

DIAGNOSTIC CUEING AND CORRECTNESS GUARDRAILS
Use feedback as diagnostic cueing, not corrective instruction.
Only flag a limitation that is directly visible in the participant's stated idea.
If the idea is too underspecified to evaluate, ask a clarification question rather than inferring a flaw.
Do not judge whether the participant's idea is correct, incorrect, good, weak, complete, or incomplete.
Do not assign quality, score the idea, or say that a specific canonical component is missing.
Use only these diagnostic cue categories:
- unclear comparison;
- rival explanation not separated;
- focal factors mixed together;
- starting differences not addressed;
- outcome timing unclear;
- measurement or variable unclear;
- idea too general to evaluate.
In one response, use at most one diagnostic cue.
After a diagnostic cue, redirect toward another possible study idea, another comparison, or one concrete revision.
Treat repeated questions about the same proposed comparison, procedure, or measurement plan as one solution path. If the dialogue has stayed on the same solution path for several tutor turns, do not force a path shift. Instead, give one short optional branching reminder and ask whether the participant has another idea or wants to continue refining the current one.
If the participant clearly wants to continue exploring the current idea, continue with ordinary Socratic clarification or diagnostic cueing, and wait a few tutor turns before repeating the reminder.
This reminder should be short and neutral. It should not suggest any specific alternative design or add a rationale about causal direction, timing, measurement, procedure, or variables. It should not mention `RSM count`, scoring, later measures, or study hypotheses.
Do not use repeated reminders to pressure the participant away from an idea they explicitly want to keep exploring.

ANSWER-SEEKING HANDLING
If the participant asks for the answer, asks for the best design, or asks you to write the design for them, briefly say that you cannot provide the design for them.
Then redirect with one question that helps them revise their own idea.

COGNITIVE-LOAD CONTROLS
Keep responses concise, usually 2-4 sentences.
Ask exactly one focused question or give exactly one concrete revision prompt at the end of each response.
Do not ask multiple questions in one turn.
Do not introduce multiple new concepts in one response.
Prefer concrete scenario language over abstract terminology.

SAFETY AND SCOPE
Keep the discussion focused on research-design reasoning.
Do not give personal advice about anxiety, social-media use, diagnosis, treatment, or mental health.
If the participant asks for personal advice, redirect to the study-design task.

OUTPUT SHAPE
Each response should contain:
1. a brief acknowledgement or clarification of the participant's current idea;
2. no more than one diagnostic cue, if directly supported by the participant's stated idea;
3. exactly one focused question or concrete revision prompt.
""".strip()

CONDITIONS = [

    # ── Route Q7M2 ───────────────────────────────────────────────────────────
    {
        "name":           "Route Q7M2",
        "passcode":       "Q7M2",      # fallback manual code; same value as route_code
        "route_code":     "Q7M2",      # opaque Qualtrics URL code
        "phase_sequence": ("instruction", "problem_solving"),
        "system_prompt":  SOCRATIC_TUTOR_PROMPT,
        "model":          "gpt-5.1",
    },

    # ── Route L9T4 ───────────────────────────────────────────────────────────
    {
        "name":           "Route L9T4",
        "passcode":       "L9T4",      # fallback manual code; same value as route_code
        "route_code":     "L9T4",      # opaque Qualtrics URL code
        "phase_sequence": ("problem_solving", "instruction"),
        "system_prompt":  SOCRATIC_TUTOR_PROMPT,
        "model":          "gpt-5.1",
    },

    # The old neutral/empathetic demo defaults are intentionally replaced
    # because this study varies phase order, not chatbot persona or model.
    # Add more routes only if the Method design is explicitly updated.

]

# ── Study title (shown in the browser tab and as the page heading) ────────────
STUDY_TITLE = "Research Design Learning Activity"

# ── Welcome / instruction message shown above the chat input ─────────────────
#
#   Displayed in a shaded banner at the top of the chat interface.  Use it
#   to orient participants before they start typing.
#
#   Good uses:
#     - Task framing:  "In this part of the study you will discuss your
#       recent online shopping experiences with an AI assistant."
#     - Consent reminder:  "This conversation is recorded as part of a
#       research study and will be stored securely."
#     - Behavioural instruction:  "Please respond as you normally would.
#       There are no right or wrong answers."
#
#   Set to "" to show no banner - useful if your Qualtrics page already
#   provides full instructions before the participant opens the chat link.
#
#   HTML is supported - use <strong>, <em>, <br> etc. for emphasis.
#
#   Examples:
#
#       WELCOME_MESSAGE = ""   # no banner
#
#       WELCOME_MESSAGE = (
#           "Welcome. In this part of the study you will have a short "
#           "conversation with an AI assistant about climate change. "
#           "When you are done, click <strong>End this chat</strong> "
#           "and then copy the study data back into the survey."
#       )
#
#       WELCOME_MESSAGE = (
#           "This conversation is part of a research study on AI-assisted "
#           "decision-making.  Your responses are confidential and will only "
#           "be used for research purposes.<br><br>"
#           "When finished, click <strong>End this chat</strong>, complete "
#           "the final check, and paste the study data into the survey."
#       )
WELCOME_MESSAGE = (
    ""
)

# ── Prompt shown on the passcode entry screen (passcode routing only) ──────
#
#   Displayed above the passcode text box when N > 1 and all conditions define
#   a "passcode".  Ignored when N = 1.
PASSCODE_ENTRY_PROMPT = (
    "Please enter the study code you received in the survey to begin."
)

# ── Configuration reference ───────────────────────────────────────────────────
#
#  Variable               Default           Description
#  ──────────────────────────────────────────────────────────────────────────────
#  API_BASE_URL           (proxy URL)       Base URL for the LLM API endpoint.
#  N_CONDITIONS           2                 1 = survey mode, 2 = A/B test,
#                                           3+ = multi-arm experiment.
#  CONDITIONS             [A, B]            List of condition dicts.  Each has
#                                           "name", optional "passcode",
#                                           "system_prompt", and "model".
#  STUDY_TITLE            "surveychat"      Browser tab title and page heading.
#  WELCOME_MESSAGE        (default string)  Banner shown above the chat.
#                                           Set to "" to hide.
#  PASSCODE_ENTRY_PROMPT  (default string)  Text above the passcode box.
#                                           Only shown in experiment mode.
#  ──────────────────────────────────────────────────────────────────────────────
#
#  Routing behaviour summary
#  ─────────────────────────
#  N = 1                Survey mode.  No gate, no passcode, direct to chat.
#  N > 1, no passcode   Random routing.  Condition drawn at random on load.
#  N > 1, with passcode Passcode routing.  Same passcode → same condition,
#                       stable across page refreshes.
#
# ╔═════════════════════════════════════════════════════════════════════════════╗
# ║  END OF RESEARCHER CONFIGURATION - no edits needed below this line        ║
# ╚═════════════════════════════════════════════════════════════════════════════╝


# =============================================================================
#  PAGE & STYLE SETUP
# =============================================================================

st.set_page_config(
    page_title=STUDY_TITLE,
    page_icon="💬",
    layout="centered",
    initial_sidebar_state="collapsed",
)

# Clean, minimal stylesheet - accent colors kept in sync with config.toml.
# Streamlit renders its own theme via CSS-in-JS and does not expose theme
# values as CSS custom properties, so we hardcode the palette here.
# If you change colors in .streamlit/config.toml, update these too:
#
#   PRIMARY   = #5C6C79   (primaryColor)             - borders, accents
#   TEXT      = #1F2429   (textColor)                - body text
#   BG_SEC    = #EFF1F3   (secondaryBackgroundColor)  - banner backgrounds
GLOBAL_STYLES = """
<style>
/* ── Typography ────────────────────────────────────────────────────────────── */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600&display=swap');

/* Apply Inter to the entire app, overriding Streamlit's default font. */
html, body, [class*="css"] { font-family: 'Inter', sans-serif; }

/* ── Chrome removal ─────────────────────────────────────────────────────────── */
/* Hide the Streamlit toolbar, footer, and hamburger menu so the page looks
   like a standalone app rather than a Streamlit dashboard. */
#MainMenu, footer, header { visibility: hidden; }
[data-testid="collapsedControl"] { display: none; }

/* Hide Streamlit Community Cloud's oEmbed bottom bar. The built-in Fullscreen
   link points to /?utm_medium=oembed without route_code, which drops the
   participant's assigned condition when opened from Qualtrics. */
div[class^="_container_"]:has(a[href="/?utm_medium=oembed"]),
div[class*=" _container_"]:has(a[href="/?utm_medium=oembed"]),
a[href="/?utm_medium=oembed"] {
    display: none !important;
}

/* Regression anchors for the hidden oEmbed bar: Built with Streamlit / Fullscreen. */

/* ── Page layout ────────────────────────────────────────────────────────────── */
/* Constrain to a readable column width and reduce default top padding. */
.block-container { max-width: 740px; padding-top: 2.25rem; padding-bottom: 1rem; }

.study-data-label {
    font-size: 0.9rem;
    font-weight: 500;
    color: #1F2429;
    margin-bottom: 0.35rem;
}

/* ── App header ─────────────────────────────────────────────────────────────── */
/* A thin rule below the study title separates it visually from the chat. */
.app-header {
    border-bottom: 2px solid #5C6C79;
    padding-bottom: 0.65rem;
    margin-bottom: 1.5rem;
}
.app-title {
    font-size: 1.35rem;
    font-weight: 600;
    color: #1F2429;
    letter-spacing: -0.4px;
    margin: 0;
}

/* ── Welcome / instruction banner ───────────────────────────────────────────── */
/* Shown above the chat input when WELCOME_MESSAGE is non-empty.  The left
   accent border matches the primary color to tie it to the site palette. */
.welcome-banner {
    background: #EFF1F3;
    border-left: 4px solid #5C6C79;
    border-radius: 0 6px 6px 0;
    padding: 0.75rem 1rem;
    font-size: 0.9rem;
    color: #1F2429;
    margin-bottom: 1.25rem;
    line-height: 1.55;
}

/* ── Transcript panel ───────────────────────────────────────────────────────── */
/* Shown after the participant clicks End.  Slightly more prominent border
   than the welcome banner to draw attention to the copy instruction. */
.transcript-banner {
    background: #EFF1F3;
    border: 1px solid #e5e7eb;
    border-left: 4px solid #5C6C79;
    border-radius: 0 8px 8px 0;
    padding: 0.8rem 1.1rem;
    font-size: 0.85rem;
    color: #1F2429;
    margin-bottom: 1.25rem;
}
</style>
"""

st.markdown(GLOBAL_STYLES, unsafe_allow_html=True)


# =============================================================================
#  ENVIRONMENT & CONFIGURATION VALIDATION
# =============================================================================

# Read the API key from the environment (populated from .env above).
OPENAI_API_KEY = os.environ.get("API_KEY")

# Fail fast with a clear, actionable error if the API key is missing or blank.
if not OPENAI_API_KEY or not OPENAI_API_KEY.strip():
    st.error(
        "**OPENAI_API_KEY not found or empty.**  "
        "Please add it to your `.env` file and restart the application.\n\n"
        "Example `.env`:\n```\nOPENAI_API_KEY=sk-...\n```"
    )
    st.stop()

# Validate researcher configuration - surfaces common setup mistakes early.
if N_CONDITIONS < 1:
    st.error(
        "`N_CONDITIONS` must be at least **1**. "
        "Please update the Researcher Configuration section."
    )
    st.stop()

if len(CONDITIONS) < N_CONDITIONS:
    st.error(
        f"`CONDITIONS` list has **{len(CONDITIONS)}** "
        f"entr{'y' if len(CONDITIONS) == 1 else 'ies'}, "
        f"but `N_CONDITIONS` is set to **{N_CONDITIONS}**. "
        "Please add more condition definitions or reduce `N_CONDITIONS`."
    )
    st.stop()

# Validate passcode-routing configuration when N > 1.
# Full logic is documented in validate_passcode_routing() above.
if N_CONDITIONS > 1:
    validate_passcode_routing(CONDITIONS, N_CONDITIONS)


# =============================================================================
#  SESSION STATE INITIALIZATION
# =============================================================================
#
#  Streamlit re-runs the entire script on every user interaction (button
#  click, chat message, page refresh).  Any Python variable assigned during
#  one run is lost on the next.  st.session_state is the mechanism for
#  persisting values across reruns within a single browser session.
#
#  Each `if … not in st.session_state` guard ensures values are initialised
#  exactly once - on the participant's very first page load - and left
#  unchanged on every subsequent rerun.

# ── Determine routing mode ────────────────────────────────────────────────────
#
#  Survey mode      →  N_CONDITIONS = 1.
#                      No routing step.  Condition index is always 0.
#                      Participant goes straight to the chat interface.
#
#  Passcode routing →  N > 1 AND every active condition defines a "passcode".
#                      The passcode entry gate is shown before the chat.
#                      The same passcode always resolves to the same condition
#                      index, so a participant who refreshes the page and
#                      re-enters their passcode lands on the same arm -
#                      without any server-side session storage.
#
#  Random routing   →  N > 1 BUT no conditions define a "passcode".
#                      Condition is drawn uniformly at random on first load.
#                      A page refresh draws a new condition, so this mode is
#                      only appropriate when refresh is unlikely or impossible
#                      (e.g. the survey platform embeds the link once).
_passcode_routing = N_CONDITIONS > 1 and all(
    "passcode" in CONDITIONS[i] for i in range(N_CONDITIONS)
)

# ── Assign condition index ────────────────────────────────────────────────────
#
#  For survey/random routing, assign immediately.
#  For passcode routing, defer until the participant enters their passcode;
#  assignment happens in the passcode-gate block below.
if not _passcode_routing and "condition_index" not in st.session_state:
    st.session_state["condition_index"] = (
        0 if N_CONDITIONS == 1 else random.randint(0, N_CONDITIONS - 1)
    )

# ── Per-session flags ─────────────────────────────────────────────────────────

# Whether the passcode gate has been passed.
# Initialised to True when no gate is needed (survey / random routing).
if "passcode_accepted" not in st.session_state:
    st.session_state["passcode_accepted"] = not _passcode_routing

# When Qualtrics passes a valid opaque route_code, accept it automatically.
# Missing or invalid URL values fall through to the original manual code gate.
if _passcode_routing and not st.session_state["passcode_accepted"]:
    _route_code = get_query_param("route_code")
    _route_idx = resolve_route_code(_route_code, CONDITIONS, N_CONDITIONS)
    if _route_idx is not None:
        st.session_state["condition_index"] = _route_idx
        st.session_state["route_code"] = normalize_route_code(
            CONDITIONS[_route_idx].get("route_code")
        )
        st.session_state["passcode_accepted"] = True

# Whether the participant has ended the chat session.
# Flips to True when they confirm End; triggers the next study stage.
if "chat_ended" not in st.session_state:
    st.session_state["chat_ended"] = False

# Two-step end-confirmation flag.
# First click on "End this chat" sets this to True (arming the confirmation).
# Second click on "✓ Confirm" sets chat_ended to True and advances the flow.
# This prevents accidental chat termination and loss of the conversation.
if "confirm_end" not in st.session_state:
    st.session_state["confirm_end"] = False

# Flipped to True the moment the participant sends their first message.
# The End button is hidden until this is True to avoid showing a useless
# button before any conversation has happened.
if "has_sent_message" not in st.session_state:
    st.session_state["has_sent_message"] = False

# The full conversation history for this session.
# Each item is a dict: {"role": str, "content": str, "timestamp": str}.
# Grows by one entry per user message and one per assistant reply.
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# True while a participant message has been added to history and the matching
# assistant response still needs to be generated.
if "pending_assistant_response" not in st.session_state:
    st.session_state["pending_assistant_response"] = False

# Start time for the Streamlit-side learning sequence.
if "session_started_at" not in st.session_state:
    st.session_state["session_started_at"] = datetime.now(timezone.utc).isoformat()

# Current learning-sequence stage: intro, phase, rsm, or completion.
if "current_stage" not in st.session_state:
    st.session_state["current_stage"] = "intro"

# Index into the active condition's phase sequence.
if "phase_index" not in st.session_state:
    st.session_state["phase_index"] = 0

# Per-phase timing records, kept only in browser session state until copy-back.
if "phase_records" not in st.session_state:
    st.session_state["phase_records"] = []

# Problem-solving final answer and RSM process evidence.
if "final_answer_text" not in st.session_state:
    st.session_state["final_answer_text"] = ""
if "final_answer" not in st.session_state:
    st.session_state["final_answer"] = None
if "rsm_count" not in st.session_state:
    st.session_state["rsm_count"] = None

# Coarse, non-sensitive error events for the copy-back payload.
if "errors" not in st.session_state:
    st.session_state["errors"] = []

# Opaque route code used for copy-back.  It must not reveal condition identity.
if "route_code" not in st.session_state:
    if "condition_index" in st.session_state:
        st.session_state["route_code"] = normalize_route_code(
            CONDITIONS[st.session_state["condition_index"]].get("route_code")
        )
    else:
        st.session_state["route_code"] = None

# Completion timestamp is set once when the copy-back screen is first reached.
if "completed_at" not in st.session_state:
    st.session_state["completed_at"] = None

# ── LLM client ────────────────────────────────────────────────────────────────

@st.cache_resource
def get_client(api_key: str, base_url: str) -> OpenAI:
    """
    Create and cache a singleton LLM client.

    @st.cache_resource creates the object once, shares it across all reruns
    and browser sessions on the same server, and never serialises it to disk.
    This is the correct Streamlit pattern for connection-like objects.

    Parameters
    ----------
    api_key : str
        The API key read from the environment (OPENAI_API_KEY).
    base_url : str
        The API_BASE_URL set in the researcher configuration.

    Returns
    -------
    OpenAI
        A configured client instance.
    """
    return OpenAI(api_key=api_key, base_url=base_url)

client = get_client(OPENAI_API_KEY, API_BASE_URL)


def mark_phase_started(phase: str) -> None:
    """Append a timing record for a phase if it is not already active."""
    active_records = [
        record for record in st.session_state["phase_records"]
        if record["phase"] == phase and not record.get("ended_at")
    ]
    if not active_records:
        st.session_state["phase_records"].append({
            "phase": phase,
            "started_at": datetime.now(timezone.utc).isoformat(),
            "ended_at": None,
        })


def mark_phase_ended(phase: str) -> None:
    """Close the latest open timing record for a phase."""
    for record in reversed(st.session_state["phase_records"]):
        if record["phase"] == phase and not record.get("ended_at"):
            record["ended_at"] = datetime.now(timezone.utc).isoformat()
            return


def advance_after_phase() -> None:
    """Move to the next required step after a learning phase finishes."""
    sequence = get_phase_sequence(condition)
    if st.session_state["phase_index"] + 1 < len(sequence):
        st.session_state["phase_index"] += 1
        st.session_state["current_stage"] = "phase"
    else:
        st.session_state["current_stage"] = "completion"
    request_scroll_top()
    st.rerun()


def queue_chat_message(prompt: str) -> None:
    """Append a participant chat turn above the input, then rerun for the reply."""
    prompt = prompt.strip()
    if not prompt:
        st.stop()

    st.session_state["messages"].append({
        "role": "user",
        "content": prompt,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    })
    st.session_state["has_sent_message"] = True
    st.session_state["pending_assistant_response"] = True
    st.rerun()


def stream_pending_assistant_response(active_condition: dict) -> bool:
    """Stream the assistant reply in the history area after a queued user turn."""
    if not st.session_state.get("pending_assistant_response"):
        return False

    api_messages = build_api_messages(
        st.session_state["messages"],
        active_condition["system_prompt"],
    )

    with st.chat_message("assistant"):
        try:
            with st.spinner("AI discussion partner is responding..."):
                stream = client.chat.completions.create(
                    model=active_condition["model"],
                    messages=api_messages,
                    stream=True,
                )
                response = st.write_stream(stream)
        except Exception:
            response = None
            st.session_state["pending_assistant_response"] = False
            st.session_state["messages"].pop()
            st.session_state["has_sent_message"] = (
                count_participant_messages(st.session_state["messages"]) > 0
            )
            st.session_state["errors"].append({
                "type": "llm_api_failure",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "recovered": True,
            })
            st.error(
                "**There was a connection problem with the AI discussion partner.** "
                "Please try sending your message again. If the problem continues, "
                "return to the survey and contact the researcher."
            )
            return True

    if response:
        st.session_state["messages"].append({
            "role": "assistant",
            "content": response,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })
        st.session_state["pending_assistant_response"] = False
        st.rerun()
    st.session_state["pending_assistant_response"] = False
    return True


# =============================================================================
#  MAIN CHAT INTERFACE
# =============================================================================
#
#  The interface is rendered in a single linear pass from top to bottom.
#  Streamlit's execution model means every widget call below is conditional
#  on session-state flags set during earlier runs; this drives the multi-step
#  participant flow:
#
#  Stage 1 - Passcode gate  (experiment mode with passcode routing only)
#    • Displayed when st.session_state["passcode_accepted"] is False.
#    • A form with a single text input collects the passcode.
#    • Valid entry maps to a condition index, sets passcode_accepted=True,
#      and triggers a full rerun so stage 1 is skipped on subsequent runs.
#    • Invalid entry shows an inline error; the gate remains visible.
#    • st.stop() at the end of stage 1 prevents any subsequent code from
#      running until the gate is passed - the chat UI is never rendered
#      even partially for unauthenticated participants.
#
#  Stage 2 - Learning sequence
#    • The session introduction is shown first.
#    • Instruction and problem-solving phases are rendered in the condition's
#      configured order.
#    • In the problem-solving phase, all messages in st.session_state["messages"]
#      are replayed in order so the full conversation history is visible on
#      every rerun.
#    • A page-level chat form collects each participant message; the user
#      message is appended, then the LLM is called.
#    • The response is streamed token-by-token via st.write_stream() to give a
#      natural, responsive feel even on slow connections.
#    • The End chat button appears only after at least five participant turns.
#
#  Stage 3 - RSM count and copy-back
#    • The RSM count form appears immediately after problem solving.
#    • After all required Streamlit-side steps are complete, the completion
#      banner and enriched JSON payload are rendered.
#    • The participant-visible JSON is rendered in a selectable text area so
#      copying still works when a survey iframe blocks clipboard buttons.
#    • The participant copies the JSON and pastes it back into Qualtrics.
#
# ── Header ────────────────────────────────────────────────────────────────────
st.markdown(
    f'<div class="app-header">'
    f'<div class="app-title">💬 {STUDY_TITLE}</div>'
    f'</div>',
    unsafe_allow_html=True,
)
render_scroll_top_if_requested()

# ── Passcode entry (experiment mode with passcode routing only) ─────────────
# Shown before the learning sequence until a URL route_code or manual code is
# accepted.  On page refresh the same opaque code maps to the same sequence
# without any server-side session storage.
if not st.session_state["passcode_accepted"]:
    st.markdown(
        f'<p style="margin-bottom:1rem;font-size:0.95rem;color:#1F2429">'
        f'{PASSCODE_ENTRY_PROMPT}</p>',
        unsafe_allow_html=True,
    )
    with st.form("key_form"):
        _code = st.text_input("Study code")
        _submitted = st.form_submit_button("Continue →", type="primary")
    if _submitted:
        _idx = resolve_route_code(_code, CONDITIONS, N_CONDITIONS)
        if _idx is not None:
            st.session_state["condition_index"] = _idx
            st.session_state["route_code"] = normalize_route_code(
                CONDITIONS[_idx].get("route_code")
            )
            st.session_state["passcode_accepted"] = True
            request_scroll_top()
            st.rerun()
        else:
            st.error("Code not recognised. Please check and try again.")
    st.stop()

# Passcode accepted (or not required) - condition is now resolved.
condition = CONDITIONS[st.session_state["condition_index"]]
if not st.session_state.get("route_code"):
    st.session_state["route_code"] = normalize_route_code(condition.get("route_code"))

_phase_sequence = get_phase_sequence(condition)
_current_phase = _phase_sequence[st.session_state["phase_index"]]

# ── Session introduction ─────────────────────────────────────────────────────
if st.session_state["current_stage"] == "intro":
    st.markdown(SESSION_INTRODUCTION)
    if st.button("Continue", type="primary"):
        st.session_state["current_stage"] = "phase"
        request_scroll_top()
        st.rerun()
    st.stop()

# ── Instruction phase ────────────────────────────────────────────────────────
if st.session_state["current_stage"] == "phase" and _current_phase == "instruction":
    mark_phase_started("instruction")

    if st.session_state["phase_index"] == 0:
        st.markdown(INSTRUCTION_ENTRY)
        st.markdown(SHARED_PROBLEM_BACKGROUND)
        st.markdown(INSTRUCTION_FIRST_STIMULUS_OPENING)
    else:
        st.markdown(PROBLEM_SOLVING_TO_INSTRUCTION_TRANSITION)
        st.markdown(INSTRUCTION_AFTER_PROBLEM_SOLVING_STIMULUS_OPENING)

    if should_show_full_problem_expander(st.session_state["phase_index"]):
        with st.expander(SHOW_FULL_RESEARCH_PROBLEM_LABEL, expanded=False):
            st.markdown(SHARED_PROBLEM_BACKGROUND)
            st.markdown(PROBLEM_SOLVING_TASK_PROMPT)

    st.markdown(INSTRUCTIONAL_STIMULUS_BEFORE_FIGURE)
    _figure_path = Path(__file__).resolve().parent / CANONICAL_SOLUTION_FIGURE_PATH
    if _figure_path.exists():
        st.image(
            str(_figure_path),
            caption=CANONICAL_SOLUTION_FIGURE_CAPTION,
            use_container_width=True,
        )
    st.markdown(INSTRUCTIONAL_STIMULUS_AFTER_FIGURE)

    if st.session_state["phase_index"] == 0:
        back_col, continue_col = st.columns([1, 1])
        with back_col:
            if st.button("Back to previous page", type="secondary"):
                st.session_state["current_stage"] = "intro"
                request_scroll_top()
                st.rerun()
        with continue_col:
            if st.button("Continue", type="primary"):
                mark_phase_ended("instruction")
                advance_after_phase()
    else:
        if st.button("Continue", type="primary"):
            mark_phase_ended("instruction")
            advance_after_phase()
    st.stop()

# ── Problem-solving phase ────────────────────────────────────────────────────
if st.session_state["current_stage"] == "phase" and _current_phase == "problem_solving":
    mark_phase_started("problem_solving")

    if st.session_state["phase_index"] == 0:
        st.markdown(PROBLEM_SOLVING_ENTRY)
        st.markdown(SHARED_PROBLEM_BACKGROUND)
    else:
        st.markdown(INSTRUCTION_TO_PROBLEM_SOLVING_TRANSITION)

    if should_show_full_problem_expander(st.session_state["phase_index"]):
        with st.expander(SHOW_FULL_RESEARCH_PROBLEM_LABEL, expanded=False):
            st.markdown(SHARED_PROBLEM_BACKGROUND)
            st.markdown(PROBLEM_SOLVING_TASK_PROMPT)

    st.markdown(PROBLEM_SOLVING_TASK_PROMPT)
    st.markdown("### Work with the AI discussion partner")
    st.markdown(PROBLEM_SOLVING_INSTRUCTIONS)
    st.info(PROBLEM_SOLVING_CHAT_INSTRUCTION)

    # Render conversation history.
    # Every message stored in st.session_state["messages"] is displayed on
    # each rerun, giving the participant a full view of the conversation.
    # st.chat_message() renders a colored avatar and indented bubble whose
    # style depends on the role: "user" gets a right-aligned bubble and
    # "assistant" a left-aligned one, matching familiar chat conventions.
    for message in st.session_state["messages"]:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    if stream_pending_assistant_response(condition):
        st.stop()

    _participant_turns = count_participant_messages(st.session_state["messages"])

    _back_requested = False
    _end_requested = False
    _confirm_requested = False
    _chat_submitted = False
    _chat_prompt = ""

    if not st.session_state["confirm_end"] and not st.session_state["chat_ended"]:
        with st.form("chat_message_form", clear_on_submit=True):
            _chat_prompt = st.text_area(
                "Message to AI discussion partner",
                key="chat_message_text",
                height=76,
                placeholder="Type your message here...",
                label_visibility="collapsed",
            )
            _chat_submitted = st.form_submit_button(
                "Send message",
                type="secondary",
                use_container_width=True,
            )

    if _chat_submitted:
        queue_chat_message(_chat_prompt)

    st.text_area(
        "Study ideas to submit",
        key="final_answer_text",
        height=160,
        placeholder="Describe the study ideas you want to submit.",
    )
    st.caption(STUDY_IDEAS_SAVE_NOTE)

    if st.session_state["phase_index"] == 0:
        back_col, end_col = st.columns([1, 1])
        with back_col:
            _back_requested = st.button(
                "Back to previous page",
                type="secondary",
                use_container_width=True,
                key="problem_back_button",
            )
    else:
        end_col = st.container()
    with end_col:
        if st.session_state["chat_ended"]:
            _confirm_requested = st.button(
                "Submit study ideas and continue",
                type="primary",
                use_container_width=True,
                key="problem_submit_after_back_button",
            )
        elif _participant_turns >= 5:
            if not st.session_state["confirm_end"]:
                _end_requested = st.button(
                    "End chat",
                    type="secondary",
                    use_container_width=True,
                    key="problem_end_button",
                )
            else:
                _confirm_requested = st.button(
                    "Submit study ideas and continue",
                    type="primary",
                    use_container_width=True,
                    key="problem_confirm_submit_button",
                )
        else:
            remaining = 5 - _participant_turns
            st.button(
                "End chat",
                type="secondary",
                disabled=True,
                use_container_width=True,
                key="problem_end_disabled_button",
            )
            st.caption(
                f"The End chat option will appear after {remaining} more "
                f"message{'s' if remaining != 1 else ''} from you."
            )

    if _back_requested:
        st.session_state["confirm_end"] = False
        st.session_state["current_stage"] = "intro"
        request_scroll_top()
        st.rerun()

    if _end_requested:
        st.session_state["confirm_end"] = True
        st.rerun()

    if _confirm_requested:
        _final_text = st.session_state["final_answer_text"].strip()
        if not _final_text:
            st.error("Please enter your study ideas before ending the chat.")
        else:
            st.session_state["final_answer"] = {
                "content": _final_text,
                "submitted_at": datetime.now(timezone.utc).isoformat(),
            }
            st.session_state["chat_ended"] = True
            st.session_state["confirm_end"] = False
            mark_phase_ended("problem_solving")
            st.session_state["current_stage"] = "rsm"
            request_scroll_top()
            st.rerun()
    st.stop()

# ── RSM count ────────────────────────────────────────────────────────────────
if st.session_state["current_stage"] == "rsm":
    st.markdown(RSM_COUNT_PROMPT)
    _previous_rsm_value = None
    if st.session_state["rsm_count"]:
        _stored_rsm_value = st.session_state["rsm_count"].get("value")
        if _stored_rsm_value in RSM_COUNT_OPTIONS:
            _previous_rsm_value = _stored_rsm_value
    _rsm_index = (
        RSM_COUNT_OPTIONS.index(_previous_rsm_value)
        if _previous_rsm_value is not None else None
    )
    with st.form("rsm_form"):
        _rsm_value = st.radio(
            "Select one option",
            RSM_COUNT_OPTIONS,
            index=_rsm_index,
            key="rsm_count_input",
            label_visibility="collapsed",
        )
        rsm_back_col, rsm_continue_col = st.columns([1, 1])
        with rsm_back_col:
            _rsm_back = st.form_submit_button(
                "Back to previous page",
                type="secondary",
                use_container_width=True,
            )
        with rsm_continue_col:
            _rsm_submitted = st.form_submit_button(
                "Continue →",
                type="primary",
                use_container_width=True,
            )
    if _rsm_back:
        st.session_state["confirm_end"] = False
        if st.session_state["final_answer"]:
            st.session_state["final_answer_text"] = st.session_state[
                "final_answer"
            ].get("content", "")
        st.session_state["current_stage"] = "phase"
        st.session_state["phase_index"] = _phase_sequence.index("problem_solving")
        request_scroll_top()
        st.rerun()
    if _rsm_submitted:
        if _rsm_value is None:
            st.error("Please select one option before continuing.")
            st.stop()
        st.session_state["rsm_count"] = {
            "value": _rsm_value,
            "submitted_at": datetime.now(timezone.utc).isoformat(),
        }
        advance_after_phase()
    st.stop()

# =============================================================================
#  COMPLETION COPY-BACK PAYLOAD
# =============================================================================
#
#  Shown after the participant completes the required Streamlit-side learning
#  sequence.  The payload keeps v3's copy-back model, but now exports only a
#  minimal completion record: route code, relative timing, RSM count, process
#  counts, assistant messages, and coarse error metadata.  Condition identity,
#  model, participant chat messages, and submitted study-ideas text remain
#  excluded from the participant-visible payload.
#
#  The native st.code() copy affordance is shown on the single study-data box.
#  If clipboard access is blocked, participants can manually select and copy
#  the text from that same box.

if st.session_state["current_stage"] == "completion":
    if not st.session_state["completed_at"]:
        st.session_state["completed_at"] = datetime.now(timezone.utc).isoformat()

    st.markdown(
        '<div class="transcript-banner">'
        'You have completed this chatbot activity.<br><br>'
        f'{COPY_STUDY_DATA_INSTRUCTION}<br><br>'
        'After pasting the study data into the survey box, continue with the survey.'
        '</div>',
        unsafe_allow_html=True,
    )

    if st.button("Back to previous page", type="secondary"):
        if _current_phase == "instruction":
            st.session_state["current_stage"] = "phase"
        else:
            st.session_state["current_stage"] = "rsm"
        st.session_state["completed_at"] = None
        request_scroll_top()
        st.rerun()

    payload = build_study_payload(
        route_code=st.session_state["route_code"],
        messages=st.session_state["messages"],
        final_answer=st.session_state["final_answer"] or {
            "content": "",
            "submitted_at": "",
        },
        rsm_count=st.session_state["rsm_count"] or {
            "value": "",
            "submitted_at": "",
        },
        phase_records=st.session_state["phase_records"],
        errors=st.session_state["errors"],
        started_at=st.session_state["session_started_at"],
        completed_at=st.session_state["completed_at"],
    )

    payload_json = json.dumps(payload, indent=2, ensure_ascii=False)
    st.markdown(
        '<div class="study-data-label">Study data to copy (do not edit)</div>',
        unsafe_allow_html=True,
    )
    st.code(
        payload_json,
        language="json",
        wrap_lines=True,
        height=420,
    )
    st.stop()


# =============================================================================
#  STUDY DATA HANDLING NOTES  (for researchers)
# =============================================================================
#
#  These notes describe how to process the enriched copy-back payload collected
#  from participants.  They are for researcher reference only and have no effect
#  on the running application.
#
#  PARSING THE COPY-BACK PAYLOAD IN PYTHON
#  ----------------------------------------
#  import json
#  import pandas as pd
#
#  raw = qualtrics_response_column   # string value from Qualtrics export
#  data = json.loads(raw)
#  phases = pd.DataFrame(data["phase_records"])  # phase, duration_seconds
#  process = pd.json_normalize(data["process_metadata"])
#
#  The formal payload does not contain chat transcripts or submitted study
#  ideas text.
#
#  PARSING THE COPY-BACK PAYLOAD IN R
#  -----------------------------------
#  library(jsonlite)
#
#  raw  <- qualtrics_response_column   # character vector from survey export
#  data <- fromJSON(raw)
#  phases <- as.data.frame(data$phase_records)
#  process <- as.data.frame(data$process_metadata)
#
#  CONDITION ASSIGNMENT (EXPERIMENT MODE)
#  ----------------------------------------
#  Condition identity is NOT in the copy-back payload.  Recover it from the
#  Qualtrics embedded data fields:
#    - condition_internal: real assignment stored by the Qualtrics branch.
#    - route_code: opaque code passed into Streamlit and copied back here.
#
#  DATA QUALITY CHECKS
#  --------------------
#  Recommended minimum checks before analysis:
#    1. Verify json.loads() succeeds for every row (malformed pastes).
#    2. Verify completion_status == "complete" before primary analysis.
#    3. Check rsm_count, phase_records, and process_metadata.
#    4. Review pilot AI-reply QA records for answer leakage and Socratic-role
#       drift before the main study.
#    5. Treat low engagement or malformed payloads during data cleaning, not
#       inside the Streamlit app.
#
# =============================================================================
