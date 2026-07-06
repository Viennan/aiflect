from __future__ import annotations

import pytest

from whero.aiflect import (
    ClientConfig,
    SecretString,
    reveal_secret_values,
    secretize_client_options,
)


def test_secret_string_redacts_repr_and_reveals_explicitly() -> None:
    secret = SecretString("super-secret")

    assert repr(secret) == "SecretString('********')"
    assert str(secret) == "********"
    assert secret.reveal() == "super-secret"

    with pytest.raises(ValueError):
        SecretString("")


def test_client_config_wraps_api_key_only() -> None:
    config = ClientConfig(
        api_key="api-key",
        provider_options={"region": "cn-beijing", "default_headers": {"x-trace-id": "trace"}},
    )

    assert config.api_key == SecretString("api-key")
    assert config.provider_options == {
        "region": "cn-beijing",
        "default_headers": {"x-trace-id": "trace"},
    }


def test_secretize_and_reveal_client_options() -> None:
    options = secretize_client_options(
        {
            "api_key": "api-key",
            "nested": {"api_key": SecretString("nested-secret")},
            "timeout": 10.0,
        }
    )

    assert options["api_key"] == SecretString("api-key")
    assert reveal_secret_values(options) == {
        "api_key": "api-key",
        "nested": {"api_key": "nested-secret"},
        "timeout": 10.0,
    }
