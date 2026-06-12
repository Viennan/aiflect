# TEST.md

This file describes the project-level testing workflow. Keep language-specific
details in the corresponding implementation area when the workflow grows.

## Unit Tests

Unit tests should not incur costs, such as paid APIs or cloud services, unless
the user explicitly asks for those tests to be built or run.

Run Python tests from the Python project directory with the project-root virtual
environment:

```bash
cd python
../.venv/bin/python -m pytest
```

When adding tests, prefer local fakes, fixtures, and static asserts over live
provider calls. Tests that require credentials, network access, or billable
provider usage must be clearly separated from the default unit test suite.

## Costly Tests

Costly tests are tests that may call real provider APIs, use credentials, touch
network services, or create billable usage. They must never run as part of the
default unit test command.

Costly tests must be isolated by pytest markers:

- `costly`: marks a test as non-default and potentially billable.
- `provider(name)`: identifies the provider, such as `openai`, `volcengine`,
  `anthropic`, or `deepseek`.
- `feature(name)`: identifies the API family, such as `generation`,
  `embedding`, `files`, `image_generation`, or `video_generation`.

The default test workflow must exclude costly tests. The costly-test runner
script runs them only after explicit user confirmation:

```bash
scripts/run-costly-tests --provider volcengine --feature generation --profile cheap
```

Non-interactive usage must require an explicit consent flag, such as `--yes`.
The runner must print the provider, features, selected profiles, and selected
model IDs before asking for confirmation.

To diagnose whether an OpenAI or OpenAI-compatible route supports chained
Responses API context through `previous_response_id`, use:

```bash
scripts/verify-openai-previous-response-id --model gpt-5.5 --yes
```

The diagnostic reads only the `openai` provider entry from `creds.json`, resolves
`api_key_env` from the current environment, creates one stored response, and then
sends a second request with `previous_response_id`. It must not print or persist
raw API keys. Like costly tests, it may create billable usage and requires
interactive confirmation unless `--yes` is passed.

The current costly smoke-test framework covers text generation, text embedding,
image-to-text generation, image embedding, and cached multi-turn generation
model cases from `creds.json`. Cached multi-turn generation covers both
OpenAI full-context cache-enabled requests, response-id style cache reuse for
Volcengine adapters, and automatic prompt caching for the Anthropic adapter.
Volcengine Session cache costly tests require the model matrix to declare
`supports_session_cache=true`; otherwise they are skipped because the cache
service may require account/model activation outside adapter control.
Response-id style costly tests assert that the second turn used
`previous_response_id` successfully and did not pass only because the adapter
refreshed with full context. Image-input tests use raw inline data from
`asserts`; they do not upload assertion assets through provider File APIs.
Provider optional dependencies must be installed before running the matching
costly tests, for example:

Generation costly tests may skip provider 5xx or temporary-unavailable failures
because they indicate live provider capacity/service availability rather than a
stable adapter contract. Provider 4xx capability, parameter, or mapping failures
should still fail.

```bash
.venv/bin/python -m pip install -e "python[volcengine,test]"
.venv/bin/python -m pip install -e "python[anthropic,test]"
.venv/bin/python -m pip install -e "python[deepseek,test]"
```

### Costly Credentials

Costly test credentials are described by a project-root `creds.json` file. This
file is ignored by Git and must not be committed. `TEST.md` documents the
expected schema and may include non-secret provider endpoints, environment
variable names, model IDs, and model capabilities. Neither `TEST.md` nor
`creds.json` may contain raw API keys, access tokens, secret keys, refresh
tokens, or session credentials.

Provider API keys must be provided indirectly through environment variables:

- `api_key_env` names the environment variable that contains the provider API
  key.
- `base_url` is not a secret and may be written directly in `creds.json`.
- `base_url` may be omitted when the provider adapter or SDK default should be
  used.

The costly-test runner must read `creds.json`, resolve `api_key_env` from the
current process environment, and pass the resolved API key only to the pytest
child process. It must not write secrets back to `creds.json`, `TEST.md`, shell
startup files, or system-level environment configuration. Environment changes
must be scoped to the single test process by default, or to the current shell
session only when the user explicitly uses a session-scoped helper.

### Costly Model Matrix

Each provider contains feature-specific model lists. Each feature may define
multiple models to support historical models, cost tiers, regional variants, or
provider-specific quality tiers.

Model entries use:

- `id`: concrete provider model ID.
- `profile`: cost or compatibility tier, such as `cheap`, `standard`,
  `premium`, `legacy`, or `experimental`.
- `enabled`: whether the runner may select the model.
- `capabilities`: model capability overrides for both test selection and
  `vatbrain` client construction.

`capabilities` keys should match `ModelCapability` field names where possible,
for example `supports_streaming`, `supports_tools`,
`supports_parallel_tool_calls`, `supports_structured_output`,
`supports_reasoning_config`,
`supports_text_embedding`, `supports_multimodal_embedding`,
`input_modalities`, `output_modalities`, and `output_dimensions`.

Costly tests must not assume a model supports a capability merely because the
provider supports it. A costly test should skip a model when the required
capability is absent, false, or unknown. If a capability is declared true and
the provider call fails because that capability is not actually supported, the
test should fail so the model matrix can be corrected.

The runner should default to enabled low-cost models, such as `profile=cheap`,
unless the user explicitly selects a different profile or asks to run all
enabled models.

### Costly Asset Rules

Costly tests that need image, video, audio, or other assertion assets must use
files from `asserts` according to `asserts/INDEX.md`.

When a costly test uses an asset as request input, it must provide the asset as
raw request data, such as bytes, base64 data, data URLs, or direct inline
payloads supported by the provider adapter. Costly tests must not upload an
assertion asset through a provider File API just to use it in a generation,
embedding, image, video, or multimodal request.

Use the smallest asset that exercises the target behavior. Large assets, such
as videos, should be reserved for feature tests that specifically require that
modality.

### File API Cleanup

Tests for provider File APIs are the only costly tests that may upload files.
They must be marked with `feature("files")` and must clean up every uploaded
remote file before the test finishes.

File API tests must:

- Track every remote file ID returned by upload/create calls.
- Delete each uploaded file in a cleanup step that runs even if assertions fail.
- Prefer fixture finalizers or `try` / `finally` cleanup around the provider
  call sequence.
- Fail or report a clear cleanup error if a remote file cannot be deleted.
- Avoid using File API uploads as setup for unrelated feature tests.

### Current `creds.json` Shape

```json
{
  "version": 1,
  "providers": {
    "openai": {
      "enabled": true,
      "api_key_env": "OPENAI_API_KEY",
      "base_url": "https://api.aicodemirror.com/api/codex/backend-api/codex/v1",
      "features": {
        "generation": {
          "models": [
            {
              "id": "gpt-5.5",
              "profile": "premium",
              "enabled": true,
              "capabilities": {
                "supports_streaming": true,
                "supports_tools": true,
                "supports_parallel_tool_calls": true,
                "supports_structured_output": true,
                "input_modalities": ["text", "image"],
                "output_modalities": ["text"]
              }
            }
          ]
        }
      }
    },
    "anthropic": {
      "enabled": true,
      "api_key_env": "ANTHROPIC_API_KEY",
      "features": {
        "generation": {
          "models": [
            {
              "id": "claude-model-id",
              "profile": "cheap",
              "enabled": true,
              "capabilities": {
                "supports_streaming": true,
                "supports_structured_output": true,
                "input_modalities": ["text", "image"],
                "output_modalities": ["text"]
              }
            }
          ]
        }
      }
    },
    "deepseek": {
      "enabled": true,
      "api_key_env": "DEEPSEEK_API_KEY",
      "base_url": "https://api.deepseek.com/anthropic",
      "features": {
        "generation": {
          "models": [
            {
              "id": "deepseek-chat",
              "profile": "cheap",
              "enabled": true,
              "capabilities": {
                "supports_streaming": true,
                "supports_tools": true,
                "supports_reasoning_config": false,
                "supports_structured_output": false,
                "input_modalities": ["text"],
                "output_modalities": ["text"]
              }
            },
            {
              "id": "deepseek-reasoner",
              "profile": "standard",
              "enabled": true,
              "capabilities": {
                "supports_streaming": true,
                "supports_tools": true,
                "supports_reasoning_config": true,
                "supported_reasoning_efforts": ["high", "max"],
                "supports_structured_output": false,
                "input_modalities": ["text"],
                "output_modalities": ["text"]
              }
            }
          ]
        }
      }
    },
    "volcengine": {
      "enabled": true,
      "api_key_env": "ARK_API_KEY",
      "base_url": "https://ark.cn-beijing.volces.com/api/v3",
      "features": {
        "generation": {
          "models": [
            {
              "id": "doubao-seed-2-0-mini-260428",
              "profile": "cheap",
              "enabled": true,
              "capabilities": {
                "supports_streaming": true,
                "supports_tools": true,
                "supports_structured_output": true,
                "supports_reasoning_config": true,
                "input_modalities": ["text", "image", "video", "file"],
                "output_modalities": ["text"]
              }
            },
            {
              "id": "doubao-seed-2-0-pro-260215",
              "profile": "premium",
              "enabled": true,
              "capabilities": {
                "supports_streaming": true,
                "supports_tools": true,
                "supports_structured_output": true,
                "supports_reasoning_config": true,
                "input_modalities": ["text", "image", "video", "file"],
                "output_modalities": ["text"]
              }
            }
          ]
        },
        "embedding": {
            "models": [
                {
                    "id": "doubao-embedding-vision-251215",
                    "profile": "premium",
                    "enabled": true,
                    "capabilities": {
                        "supports_text_embedding": true,
                        "supports_multimodal_embedding": true,
                        "supports_sparse_embedding": true,
                        "input_modalities": ["text", "image"],
                        "output_dimensions": 2048
                    }
                }
            ]
        }
      }
    }
  }
}
```
