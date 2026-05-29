from __future__ import annotations

import pytest

from whero.vatbrain import (
    AssistantMessagePhase,
    AudioPart,
    FilePart,
    FunctionCallItem,
    FunctionResultItem,
    FunctionToolType,
    ImagePart,
    ItemKind,
    MessageItem,
    ProviderItemSnapshot,
    ReasoningItem,
    Role,
    TextPart,
    VideoPart,
    provider_snapshot_for,
)


def test_message_item_accepts_string_parts() -> None:
    item = MessageItem.user("hello")

    assert item.role == Role.USER
    assert item.parts == (TextPart("hello"),)


def test_message_item_accepts_assistant_phase() -> None:
    item = MessageItem.assistant("working", assistant_phase="commentary")

    assert item.assistant_phase == AssistantMessagePhase.COMMENTARY

    with pytest.raises(ValueError):
        MessageItem(Role.USER, "hello", assistant_phase=AssistantMessagePhase.FINAL_ANSWER)


def test_provider_item_snapshot_attaches_to_item_field() -> None:
    snapshot = ProviderItemSnapshot(
        provider="openai",
        api_family="responses",
        item_type="message",
        payload={"type": "message", "role": "assistant", "content": []},
        captured_from="response",
    )
    item = MessageItem(Role.ASSISTANT, "hello", provider_snapshots=[snapshot])

    assert item.provider_snapshots == (snapshot,)
    assert provider_snapshot_for(item, provider="openai", api_family="responses") is snapshot
    assert provider_snapshot_for(item, provider="volcengine", api_family="responses") is None


def test_image_part_requires_exactly_one_source() -> None:
    with pytest.raises(ValueError):
        ImagePart()

    with pytest.raises(ValueError):
        ImagePart(url="https://example.test/a.png", data="abc")

    part = ImagePart(url="https://example.test/a.png", metadata={"role": "first_frame"})

    assert part.url == "https://example.test/a.png"
    assert part.metadata == {"role": "first_frame"}


@pytest.mark.parametrize("part_cls", [AudioPart, VideoPart, FilePart])
def test_media_and_file_parts_require_exactly_one_source(part_cls: type[object]) -> None:
    with pytest.raises(ValueError):
        part_cls()

    with pytest.raises(ValueError):
        part_cls(url="https://example.test/a", data="abc")

    part = part_cls(local_path="/tmp/example.bin")

    assert part.local_path == "/tmp/example.bin"


def test_file_part_accepts_provider_file_id() -> None:
    part = FilePart(file_id="file_1", provider="openai", mime_type="application/pdf")

    assert part.file_id == "file_1"
    assert part.provider == "openai"


def test_function_items_keep_protocol_fields() -> None:
    call = FunctionCallItem(name="lookup", arguments='{"q":"x"}', call_id="call_1")
    result = FunctionResultItem(call_id="call_1", output='{"ok":true}')

    assert call.name == "lookup"
    assert call.arguments == '{"q":"x"}'
    assert call.type == FunctionToolType.FUNCTION
    assert call.input is None
    assert result.call_id == "call_1"
    assert result.tool_type is None


def test_custom_function_call_item_keeps_raw_input() -> None:
    call = FunctionCallItem(
        name="run_code",
        arguments="print('hello')",
        call_id="call_1",
        type="custom",
    )
    result = FunctionResultItem(call_id="call_1", output="hello\n", tool_type="custom")

    assert call.type == FunctionToolType.CUSTOM
    assert call.input == "print('hello')"
    assert result.tool_type == FunctionToolType.CUSTOM


def test_reasoning_item_defaults_to_not_replayable() -> None:
    item = ReasoningItem(summary="short reasoning", provider="openai")

    assert item.kind == ItemKind.REASONING
    assert item.can_be_replayed is False

    with pytest.raises(ValueError):
        ReasoningItem()
