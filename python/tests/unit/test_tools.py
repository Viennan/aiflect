from __future__ import annotations

import pytest

from whero.aiflect import (
    FunctionToolSpec,
    FunctionToolType,
    ToolExecutionOwner,
    ToolSpec,
)


def test_tool_spec_is_function_tool_compatible_alias() -> None:
    tool = ToolSpec(name="lookup", parameters_schema={"type": "object"})

    assert isinstance(tool, FunctionToolSpec)
    assert tool.type == "function"
    assert tool.type == FunctionToolType.FUNCTION
    assert tool.execution_owner == ToolExecutionOwner.USER


def test_tool_spec_accepts_custom_tool_type() -> None:
    tool = ToolSpec(name="run_code", type="custom")

    assert tool.name == "run_code"
    assert tool.type == FunctionToolType.CUSTOM
    assert tool.execution_owner == ToolExecutionOwner.USER
    assert tool.parameters_schema == {}


def test_function_tool_requires_name() -> None:
    with pytest.raises(ValueError, match="name is required"):
        FunctionToolSpec(name="")
