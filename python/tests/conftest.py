from __future__ import annotations

import base64
from collections.abc import Mapping
from dataclasses import dataclass
import json
import mimetypes
import os
from pathlib import Path
from typing import Any

import pytest


REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_COSTLY_CONFIG = REPO_ROOT / "creds.json"
DEFAULT_COSTLY_IMAGE_ASSET = REPO_ROOT / "asserts" / "haiou.jpg"
_TUPLE_CAPABILITY_KEYS = {
    "input_modalities",
    "output_modalities",
    "supported_reasoning_efforts",
}


@dataclass(frozen=True, slots=True)
class CostlyProviderConfig:
    provider: str
    enabled: bool
    api_key_env: str | None
    base_url: str | None
    features: Mapping[str, Any]
    raw: Mapping[str, Any]

    def model_capability_overrides(self) -> dict[str, dict[str, Any]]:
        overrides: dict[str, dict[str, Any]] = {}
        for feature_config in self.features.values():
            if not isinstance(feature_config, Mapping):
                continue
            for model_config in feature_config.get("models", ()) or ():
                if not isinstance(model_config, Mapping):
                    continue
                model_id = model_config.get("id")
                capabilities = model_config.get("capabilities", {})
                if isinstance(model_id, str) and isinstance(capabilities, Mapping):
                    overrides[model_id] = _normalize_capabilities(capabilities)
        return overrides


@dataclass(frozen=True, slots=True)
class CostlyModelCase:
    provider: str
    feature: str
    model_id: str
    profile: str
    enabled: bool
    capabilities: Mapping[str, Any]
    provider_config: CostlyProviderConfig

    @property
    def pytest_id(self) -> str:
        return f"{self.provider}:{self.feature}:{self.profile}:{self.model_id}"

    def supports(self, capability: str) -> bool:
        return self.capabilities.get(capability) is True

    def supports_modality(self, capability: str, modality: str) -> bool:
        values = self.capabilities.get(capability)
        if not isinstance(values, (list, tuple, set)):
            return False
        return modality in values

    def capability_int(self, capability: str) -> int | None:
        value = self.capabilities.get(capability)
        return value if isinstance(value, int) else None


@dataclass(frozen=True, slots=True)
class CostlyImageAsset:
    path: Path
    mime_type: str
    data: str


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--run-costly",
        action="store_true",
        default=False,
        help="Run costly tests that may call real provider APIs.",
    )
    parser.addoption(
        "--costly-config",
        default=str(DEFAULT_COSTLY_CONFIG),
        help="Path to the costly test creds.json file.",
    )
    parser.addoption(
        "--provider",
        action="append",
        default=[],
        help="Provider name to include in costly tests. Can be repeated.",
    )
    parser.addoption(
        "--feature",
        action="append",
        default=[],
        help="Feature name to include in costly tests. Can be repeated.",
    )
    parser.addoption(
        "--profile",
        action="append",
        default=[],
        help="Model profile to include in costly tests. Defaults to cheap.",
    )
    parser.addoption(
        "--all-costly-models",
        action="store_true",
        default=False,
        help="Run all enabled costly model cases instead of profile-filtered cases.",
    )
    parser.addoption(
        "--costly-image-asset",
        default=str(DEFAULT_COSTLY_IMAGE_ASSET),
        help="Image asset path used by costly multimodal smoke tests.",
    )


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers",
        "costly: tests that may call real provider APIs or create billable usage",
    )
    config.addinivalue_line("markers", "provider(name): provider targeted by a costly test")
    config.addinivalue_line("markers", "feature(name): provider feature family targeted by a costly test")


def pytest_collection_modifyitems(config: pytest.Config, items: list[pytest.Item]) -> None:
    if config.getoption("--run-costly"):
        return
    skip_costly = pytest.mark.skip(reason="costly tests require --run-costly or scripts/run-costly-tests")
    for item in items:
        if item.get_closest_marker("costly"):
            item.add_marker(skip_costly)


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "costly_model_case" not in metafunc.fixturenames:
        return
    if not metafunc.config.getoption("--run-costly"):
        metafunc.parametrize(
            "costly_model_case",
            [pytest.param(None, marks=pytest.mark.skip(reason="costly tests require --run-costly"))],
        )
        return

    cases = _selected_model_cases(
        metafunc.config,
        providers=_marker_values(metafunc, "provider"),
        features=_marker_values(metafunc, "feature"),
    )
    if not cases:
        metafunc.parametrize(
            "costly_model_case",
            [pytest.param(None, marks=pytest.mark.skip(reason="no costly model cases matched selection"))],
        )
        return
    metafunc.parametrize(
        "costly_model_case",
        [pytest.param(case, id=case.pytest_id) for case in cases],
    )


@pytest.fixture
def costly_provider_config(costly_model_case: CostlyModelCase) -> CostlyProviderConfig:
    return costly_model_case.provider_config


@pytest.fixture
def costly_client(costly_model_case: CostlyModelCase) -> Any:
    provider_config = costly_model_case.provider_config
    if not provider_config.api_key_env:
        pytest.skip(f"{costly_model_case.provider} has no api_key_env configured")
    api_key = os.environ.get(provider_config.api_key_env)
    if not api_key:
        pytest.skip(f"environment variable {provider_config.api_key_env} is not set")

    client_options: dict[str, Any] = {
        "api_key": api_key,
        "model_capability_overrides": provider_config.model_capability_overrides(),
    }
    if provider_config.base_url:
        client_options["base_url"] = provider_config.base_url
    for option_name in ("timeout", "max_retries"):
        if option_name in provider_config.raw:
            client_options[option_name] = provider_config.raw[option_name]
    extra_options = provider_config.raw.get("client_options", {})
    if isinstance(extra_options, Mapping):
        client_options.update(dict(extra_options))

    if costly_model_case.provider == "openai":
        pytest.importorskip("openai", reason="OpenAI costly tests require the openai package")
        from whero.vatbrain.providers.openai import OpenAIClient

        return OpenAIClient(**client_options)
    if costly_model_case.provider == "volcengine":
        pytest.importorskip(
            "volcenginesdkarkruntime",
            reason="Volcengine costly tests require python[volcengine]",
        )
        from whero.vatbrain.providers.volcengine import VolcengineClient

        return VolcengineClient(**client_options)
    pytest.skip(f"unsupported costly provider: {costly_model_case.provider}")


@pytest.fixture(scope="session")
def costly_image_asset(pytestconfig: pytest.Config) -> CostlyImageAsset:
    path = Path(str(pytestconfig.getoption("--costly-image-asset")))
    if not path.is_absolute():
        path = REPO_ROOT / path
    if not path.exists():
        pytest.skip(f"costly image asset not found: {path}")
    mime_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    if not mime_type.startswith("image/"):
        pytest.skip(f"costly image asset is not an image: {path}")
    return CostlyImageAsset(
        path=path,
        mime_type=mime_type,
        data=base64.b64encode(path.read_bytes()).decode("ascii"),
    )


def _selected_model_cases(
    config: pytest.Config,
    *,
    providers: tuple[str, ...] = (),
    features: tuple[str, ...] = (),
) -> list[CostlyModelCase]:
    data = _load_costly_config(config)
    cli_providers = tuple(config.getoption("--provider") or ())
    cli_features = tuple(config.getoption("--feature") or ())
    selected_providers = _combined_filter(providers, cli_providers)
    selected_features = _combined_filter(features, cli_features)
    selected_profiles = _selected_profiles(config)

    cases: list[CostlyModelCase] = []
    for provider, provider_raw in sorted((data.get("providers") or {}).items()):
        if selected_providers is not None and provider not in selected_providers:
            continue
        if not isinstance(provider_raw, Mapping) or not provider_raw.get("enabled", False):
            continue
        feature_map = provider_raw.get("features", {})
        if not isinstance(feature_map, Mapping):
            continue
        provider_config = CostlyProviderConfig(
            provider=provider,
            enabled=bool(provider_raw.get("enabled", False)),
            api_key_env=_optional_str(provider_raw.get("api_key_env")),
            base_url=_optional_str(provider_raw.get("base_url")),
            features=feature_map,
            raw=provider_raw,
        )
        for feature, feature_raw in sorted(feature_map.items()):
            if selected_features is not None and feature not in selected_features:
                continue
            if not isinstance(feature_raw, Mapping):
                continue
            for model_raw in feature_raw.get("models", ()) or ():
                if not isinstance(model_raw, Mapping):
                    continue
                model_id = model_raw.get("id")
                if not isinstance(model_id, str) or not model_id:
                    continue
                enabled = bool(model_raw.get("enabled", False))
                profile = str(model_raw.get("profile") or "default")
                if not enabled:
                    continue
                if selected_profiles is not None and profile not in selected_profiles:
                    continue
                capabilities = model_raw.get("capabilities", {})
                if not isinstance(capabilities, Mapping):
                    capabilities = {}
                cases.append(
                    CostlyModelCase(
                        provider=provider,
                        feature=feature,
                        model_id=model_id,
                        profile=profile,
                        enabled=enabled,
                        capabilities=_normalize_capabilities(capabilities),
                        provider_config=provider_config,
                    )
                )
    return cases


def _load_costly_config(config: pytest.Config) -> dict[str, Any]:
    path = Path(str(config.getoption("--costly-config")))
    if not path.is_absolute():
        path = REPO_ROOT / path
    if not path.exists():
        raise pytest.UsageError(f"costly config file not found: {path}")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise pytest.UsageError(f"invalid costly config JSON: {path}") from exc
    if not isinstance(data, dict):
        raise pytest.UsageError("costly config root must be a JSON object")
    _reject_inline_secrets(data)
    return data


def _reject_inline_secrets(value: Any, *, path: str = "$") -> None:
    if isinstance(value, Mapping):
        for key, item in value.items():
            key_text = str(key)
            lowered = key_text.lower()
            if lowered in {"api_key", "apikey", "secret", "token", "access_token"}:
                raise pytest.UsageError(f"costly config must use environment variables instead of {path}.{key_text}")
            _reject_inline_secrets(item, path=f"{path}.{key_text}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_inline_secrets(item, path=f"{path}[{index}]")


def _marker_values(metafunc: pytest.Metafunc, marker_name: str) -> tuple[str, ...]:
    values: list[str] = []
    for marker in metafunc.definition.iter_markers(marker_name):
        if marker.args:
            values.append(str(marker.args[0]))
    return tuple(values)


def _combined_filter(left: tuple[str, ...], right: tuple[str, ...]) -> set[str] | None:
    left_set = set(left)
    right_set = set(right)
    if left_set and right_set:
        return left_set & right_set
    if left_set:
        return left_set
    if right_set:
        return right_set
    return None


def _selected_profiles(config: pytest.Config) -> set[str] | None:
    if config.getoption("--all-costly-models"):
        return None
    profiles = config.getoption("--profile") or ()
    return set(str(profile) for profile in profiles) if profiles else {"cheap"}


def _normalize_capabilities(capabilities: Mapping[str, Any]) -> dict[str, Any]:
    normalized = dict(capabilities)
    for key in _TUPLE_CAPABILITY_KEYS:
        value = normalized.get(key)
        if isinstance(value, list):
            normalized[key] = tuple(value)
    return normalized


def _optional_str(value: Any) -> str | None:
    return value if isinstance(value, str) and value else None
