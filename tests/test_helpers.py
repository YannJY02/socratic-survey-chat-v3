"""
tests/test_helpers.py — unit tests for the three pure helper functions
defined in app.py: validate_passcode_routing, build_api_messages, and
build_transcript.

External dependencies (streamlit, dotenv, openai) are replaced with
MagicMock objects by conftest.py before this module is imported.
"""

import sys
from unittest.mock import call

import pytest

# ---------------------------------------------------------------------------
# Import the module under test.
# conftest.py has already patched streamlit/dotenv/openai in sys.modules,
# so this import executes app.py's top-level code against the mocks.
# ---------------------------------------------------------------------------
import app
import study_content


# ===========================================================================
#  validate_passcode_routing
# ===========================================================================

class TestValidatePasscodeRouting:
    """Tests for validate_passcode_routing(conditions, n_conditions)."""

    def _st(self):
        """Return the mocked streamlit module."""
        return sys.modules["streamlit"]

    def _reset_st(self):
        """Clear any previous st.error / st.stop call records."""
        st = self._st()
        st.error.reset_mock()
        st.stop.reset_mock()

    # --- happy-path cases ---------------------------------------------------

    def test_survey_mode_no_passcodes_ok(self):
        """Single condition without a passcode is valid (survey mode)."""
        self._reset_st()
        conditions = [{"name": "A", "system_prompt": "…", "model": "m"}]
        app.validate_passcode_routing(conditions, 1)
        self._st().stop.assert_not_called()

    def test_all_conditions_have_unique_passcodes_ok(self):
        """Two conditions each with a unique passcode is valid."""
        self._reset_st()
        conditions = [
            {"name": "A", "passcode": "ALPHA", "system_prompt": "…", "model": "m"},
            {"name": "B", "passcode": "BETA",  "system_prompt": "…", "model": "m"},
        ]
        app.validate_passcode_routing(conditions, 2)
        self._st().stop.assert_not_called()

    def test_passcodes_case_insensitive_uniqueness_ok(self):
        """Passcodes that differ only in case are treated as duplicates."""
        self._reset_st()
        conditions = [
            {"name": "A", "passcode": "alpha", "system_prompt": "…", "model": "m"},
            {"name": "B", "passcode": "ALPHA", "system_prompt": "…", "model": "m"},
        ]
        app.validate_passcode_routing(conditions, 2)
        self._st().error.assert_called_once()
        self._st().stop.assert_called_once()

    def test_extra_conditions_beyond_n_are_ignored(self):
        """Only the first n_conditions entries are validated."""
        self._reset_st()
        conditions = [
            {"name": "A", "passcode": "ALPHA", "system_prompt": "…", "model": "m"},
            {"name": "B", "passcode": "BETA",  "system_prompt": "…", "model": "m"},
            # Extra entry deliberately missing a passcode — should be ignored.
            {"name": "C", "system_prompt": "…", "model": "m"},
        ]
        app.validate_passcode_routing(conditions, 2)
        self._st().stop.assert_not_called()

    # --- error cases --------------------------------------------------------

    def test_partial_passcode_configuration_triggers_error(self):
        """Only some conditions having a passcode is an error."""
        self._reset_st()
        conditions = [
            {"name": "A", "passcode": "ALPHA", "system_prompt": "…", "model": "m"},
            {"name": "B",                      "system_prompt": "…", "model": "m"},
        ]
        app.validate_passcode_routing(conditions, 2)
        self._st().error.assert_called_once()
        self._st().stop.assert_called_once()

    def test_blank_passcode_triggers_error(self):
        """A passcode that is an empty string (or only whitespace) is an error."""
        self._reset_st()
        conditions = [
            {"name": "A", "passcode": "ALPHA", "system_prompt": "…", "model": "m"},
            {"name": "B", "passcode": "   ",   "system_prompt": "…", "model": "m"},
        ]
        app.validate_passcode_routing(conditions, 2)
        self._st().error.assert_called_once()
        self._st().stop.assert_called_once()

    def test_duplicate_passcodes_trigger_error(self):
        """Two conditions sharing the same passcode is an error."""
        self._reset_st()
        conditions = [
            {"name": "A", "passcode": "SAME", "system_prompt": "…", "model": "m"},
            {"name": "B", "passcode": "SAME", "system_prompt": "…", "model": "m"},
        ]
        app.validate_passcode_routing(conditions, 2)
        self._st().error.assert_called_once()
        self._st().stop.assert_called_once()

    def test_three_arm_all_unique_ok(self):
        """Three conditions each with a unique passcode is valid."""
        self._reset_st()
        conditions = [
            {"name": "A", "passcode": "ALPHA", "system_prompt": "…", "model": "m"},
            {"name": "B", "passcode": "BETA",  "system_prompt": "…", "model": "m"},
            {"name": "C", "passcode": "GAMMA", "system_prompt": "…", "model": "m"},
        ]
        app.validate_passcode_routing(conditions, 3)
        self._st().stop.assert_not_called()


# ===========================================================================
#  build_api_messages
# ===========================================================================

class TestBuildApiMessages:
    """Tests for build_api_messages(conversation, system_prompt)."""

    def test_empty_conversation_returns_system_message_only(self):
        """With no prior conversation, only the system message is returned."""
        result = app.build_api_messages([], "Be helpful.")
        assert result == [{"role": "system", "content": "Be helpful."}]

    def test_conversation_is_prepended_with_system_message(self):
        """The system message is always the first element."""
        conversation = [
            {"role": "user",      "content": "Hello",     "timestamp": "…"},
            {"role": "assistant", "content": "Hi there!", "timestamp": "…"},
        ]
        result = app.build_api_messages(conversation, "System prompt.")
        assert result[0] == {"role": "system", "content": "System prompt."}

    def test_timestamps_are_stripped_from_output(self):
        """The 'timestamp' key must not appear in the messages sent to the API."""
        conversation = [
            {"role": "user", "content": "Test", "timestamp": "2026-01-01T00:00:00+00:00"},
        ]
        result = app.build_api_messages(conversation, "Prompt.")
        for msg in result:
            assert "timestamp" not in msg

    def test_roles_and_content_are_preserved(self):
        """Role and content are forwarded exactly as-is."""
        conversation = [
            {"role": "user",      "content": "Question?", "timestamp": "t1"},
            {"role": "assistant", "content": "Answer.",   "timestamp": "t2"},
        ]
        result = app.build_api_messages(conversation, "System.")
        assert result[1] == {"role": "user",      "content": "Question?"}
        assert result[2] == {"role": "assistant", "content": "Answer."}

    def test_output_length_equals_conversation_plus_one(self):
        """The returned list has exactly len(conversation) + 1 items."""
        conversation = [{"role": "user", "content": f"msg {i}", "timestamp": ""} for i in range(5)]
        result = app.build_api_messages(conversation, "System.")
        assert len(result) == 6


# ===========================================================================
#  build_transcript
# ===========================================================================

class TestBuildTranscript:
    """Tests for build_transcript(messages)."""

    def test_returns_dict_with_messages_key(self):
        """The transcript is a dict with a 'messages' key."""
        result = app.build_transcript([])
        assert isinstance(result, dict)
        assert "messages" in result

    def test_empty_conversation_gives_empty_messages_list(self):
        result = app.build_transcript([])
        assert result["messages"] == []

    def test_user_role_relabelled_to_participant(self):
        """'user' must be renamed 'participant' in the transcript."""
        messages = [{"role": "user", "content": "Hello", "timestamp": "t"}]
        result = app.build_transcript(messages)
        assert result["messages"][0]["role"] == "participant"

    def test_assistant_role_unchanged(self):
        """'assistant' role must remain 'assistant'."""
        messages = [{"role": "assistant", "content": "Hi", "timestamp": "t"}]
        result = app.build_transcript(messages)
        assert result["messages"][0]["role"] == "assistant"

    def test_content_is_preserved(self):
        messages = [{"role": "user", "content": "My answer.", "timestamp": "t"}]
        result = app.build_transcript(messages)
        assert result["messages"][0]["content"] == "My answer."

    def test_timestamp_is_included(self):
        messages = [{"role": "user", "content": "x", "timestamp": "2026-03-06T14:22:01+00:00"}]
        result = app.build_transcript(messages)
        assert result["messages"][0]["timestamp"] == "2026-03-06T14:22:01+00:00"

    def test_multi_turn_conversation_length(self):
        """Every message in the input appears in the transcript."""
        messages = [
            {"role": "user",      "content": "Q1", "timestamp": "t1"},
            {"role": "assistant", "content": "A1", "timestamp": "t2"},
            {"role": "user",      "content": "Q2", "timestamp": "t3"},
            {"role": "assistant", "content": "A2", "timestamp": "t4"},
        ]
        result = app.build_transcript(messages)
        assert len(result["messages"]) == 4

    def test_condition_name_and_model_are_not_exposed(self):
        """Condition name and model identifiers must not appear in the transcript."""
        messages = [{"role": "user", "content": "Hello", "timestamp": "t"}]
        result = app.build_transcript(messages)
        for msg in result["messages"]:
            assert "condition" not in msg
            assert "model" not in msg


# ===========================================================================
#  study-specific route, phase, and payload helpers
# ===========================================================================

class TestStudyRoutingHelpers:
    """Tests for opaque route-code mapping and phase sequencing."""

    def test_normalize_route_code_strips_and_uppercases(self):
        assert app.normalize_route_code(" q7m2 ") == "Q7M2"

    def test_normalize_route_code_rejects_blank_values(self):
        assert app.normalize_route_code("   ") is None

    def test_resolve_route_code_uses_opaque_codes_only(self):
        conditions = [
            {"route_code": "Q7M2", "passcode": "Q7M2"},
            {"route_code": "L9T4", "passcode": "L9T4"},
        ]
        assert app.resolve_route_code("q7m2", conditions, 2) == 0
        assert app.resolve_route_code("L9T4", conditions, 2) == 1
        assert app.resolve_route_code("I_PS", conditions, 2) is None

    def test_get_phase_sequence_returns_configured_order(self):
        condition = {"phase_sequence": ("problem_solving", "instruction")}
        assert app.get_phase_sequence(condition) == ("problem_solving", "instruction")

    def test_count_participant_messages_counts_only_user_turns(self):
        messages = [
            {"role": "user", "content": "one"},
            {"role": "assistant", "content": "reply"},
            {"role": "user", "content": "two"},
        ]
        assert app.count_participant_messages(messages) == 2

    def test_rsm_options_match_canonical_labels(self):
        assert study_content.RSM_COUNT_OPTIONS == (
            "1 idea",
            "2 ideas",
            "3 ideas",
            "4 or more ideas",
        )


class TestBuildStudyPayload:
    """Tests for the enriched Qualtrics copy-back payload."""

    def test_payload_contains_required_copy_back_fields(self):
        payload = app.build_study_payload(
            route_code="Q7M2",
            messages=[{"role": "user", "content": "Hello", "timestamp": "t1"}],
            final_answer={"content": "My design", "submitted_at": "t2"},
            rsm_count={"value": "3 ideas", "submitted_at": "t3"},
            phase_records=[
                {"phase": "instruction", "started_at": "t0", "ended_at": "t1"},
                {"phase": "problem_solving", "started_at": "t1", "ended_at": "t3"},
            ],
            errors=[],
            started_at="t0",
            completed_at="t4",
        )

        assert payload["schema_version"] == "chatbot_stage_v1"
        assert payload["route_code"] == "Q7M2"
        assert payload["completion_status"] == "complete"
        assert payload["started_at"] == "t0"
        assert payload["completed_at"] == "t4"
        assert payload["phase_records"][0]["phase"] == "instruction"
        assert payload["chat_transcript"][0]["role"] == "participant"
        assert payload["final_answer"]["content"] == "My design"
        assert payload["rsm_count"]["value"] == "3 ideas"
        assert payload["errors"] == []

    def test_payload_does_not_expose_condition_identity_or_pid(self):
        payload = app.build_study_payload(
            route_code="L9T4",
            messages=[],
            final_answer={"content": "", "submitted_at": ""},
            rsm_count={"value": "1 idea", "submitted_at": ""},
            phase_records=[],
            errors=[],
            started_at="",
            completed_at="",
        )

        serialized = str(payload)
        assert "I_PS" not in serialized
        assert "PS_I" not in serialized
        assert "I->PS" not in serialized
        assert "PS->I" not in serialized
        assert "condition_internal" not in serialized
        assert "method_label" not in serialized
        assert "pid" not in serialized


class TestStudyContentSync:
    """Regression checks for canonical participant-facing content."""

    def test_shared_background_uses_canonical_researcher_labels(self):
        background = study_content.SHARED_PROBLEM_BACKGROUND
        assert "Dr. De Jong" in background
        assert "Dr. Jansen" in background
        assert "Dr. De Vries" in background
        assert "Dr. de Vries" not in background
        assert "Dr. Bakker" not in background

    def test_problem_task_prompt_is_split_from_shared_background(self):
        assert "This is your task" not in study_content.SHARED_PROBLEM_BACKGROUND
        assert "This is your task" in study_content.PROBLEM_SOLVING_TASK_PROMPT

    def test_no_identifying_information_warning_is_present(self):
        assert "Do not enter your name" in study_content.PROBLEM_SOLVING_INSTRUCTIONS
        assert "Study ideas to submit" in study_content.PROBLEM_SOLVING_INSTRUCTIONS

    def test_exact_runtime_prompt_shape_is_synchronized(self):
        assert "ROLE AND INVARIANCE" in app.SOCRATIC_TUTOR_PROMPT
        assert "AUTHORIZED RESOURCES" in app.SOCRATIC_TUTOR_PROMPT
        assert "DIAGNOSTIC CUEING AND CORRECTNESS GUARDRAILS" in app.SOCRATIC_TUTOR_PROMPT
        assert "OUTPUT SHAPE" in app.SOCRATIC_TUTOR_PROMPT
