from __future__ import annotations

import pytest

from whero.aiflect import (
    GenerationConfig,
    GenerationRequest,
    MessageItem,
    ReasoningConfig,
    RemoteContextHint,
    ReplayMode,
    ReplayPolicy,
)


def test_generation_config_does_not_accept_stop_sequences() -> None:
    with pytest.raises(TypeError):
        GenerationConfig(stop=["END"])  # type: ignore[call-arg]


def test_generation_request_accepts_remote_context_hint() -> None:
    remote_context = RemoteContextHint(
        enable_cache=True,
        session_key="session-1",
        new_items_start_index=1,
        provider_options={"metadata": {"trace_id": "t-1"}},
    )

    request = GenerationRequest(
        model="gpt-test",
        items=[MessageItem.user("hello")],
        remote_context=remote_context,
    )

    assert request.remote_context is remote_context
    assert request.remote_context.enable_cache is True
    assert request.remote_context.session_key == "session-1"
    assert request.remote_context.new_items_start_index == 1


def test_remote_context_hint_validates_session_key() -> None:
    with pytest.raises(ValueError):
        RemoteContextHint(session_key=" ")


def test_remote_context_hint_validates_new_items_start_index() -> None:
    with pytest.raises(ValueError):
        RemoteContextHint(new_items_start_index=-1)


def test_generation_request_validates_remote_context_coverage_bounds() -> None:
    with pytest.raises(ValueError):
        GenerationRequest(
            model="gpt-test",
            items=[MessageItem.user("hello")],
            remote_context=RemoteContextHint(enable_cache=True, new_items_start_index=2),
        )


def test_reasoning_config_accepts_mode_and_provider_options() -> None:
    reasoning = ReasoningConfig(
        mode="auto",
        effort="low",
        provider_options={"summary": "auto"},
    )

    assert reasoning.mode == "auto"
    assert reasoning.provider_options == {"summary": "auto"}


def test_replay_policy_normalizes_modes() -> None:
    policy = ReplayPolicy(mode="require_provider_native")

    assert policy.mode == ReplayMode.REQUIRE_PROVIDER_NATIVE
    assert policy.cross_provider == "unsupported"

    with pytest.raises(ValueError):
        ReplayPolicy(cross_provider="translate")
