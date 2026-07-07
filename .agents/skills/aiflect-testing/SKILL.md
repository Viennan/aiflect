---
name: aiflect-testing
description: Use when adding, changing, running, or diagnosing aiflect tests, including Python unit tests, pytest markers, costly provider smoke tests, creds.json, model matrices, asserts assets, File API cleanup, scripts/run-costly-tests, and scripts/verify-openai-previous-response-id.
---

# Aiflect Testing

## Default Unit Tests

Unit tests must not incur costs such as paid APIs or cloud services unless the
user explicitly asks for those tests to be built or run.

Run Python tests from the Python project directory with the project-root virtual
environment:

```bash
cd python
../.venv/bin/python -m pytest
```

When adding tests, prefer local fakes, fixtures, and static assertions over live
provider calls. Tests that require credentials, network access, or billable
provider usage must be clearly separated from the default unit test suite.

New requirements should have default unit-test coverage whenever the current
design makes that possible. Do not change the product or code design merely to
make a unit test easier to write; if the current design makes meaningful unit
coverage impractical, report the limitation and wait for user direction.

## Coverage and Assertion Standards

- Non-cost default unit tests must maintain at least 80% code coverage for the
  Python implementation.
- Prefer measuring coverage for `whero.aiflect` from the default unit-test
  suite, excluding costly tests.
- When pytest coverage tooling is available, use an explicit fail-under check
  such as:

```bash
cd python
../.venv/bin/python -m pytest --cov=whero.aiflect --cov-fail-under=80
```

- If the current tooling cannot measure coverage, report that as a test
  infrastructure gap instead of treating coverage as satisfied.
- Tests must assert objective behavior with deterministic pass/fail criteria.
  A test that only runs code, prints logs, or relies on manual inspection is not
  sufficient.
- As the system grows, refactor and extend test code when needed so coverage
  and assertion quality remain understandable and maintainable.

## Pytest Layout and Markers

- Place default unit tests under `python/tests/unit`.
- Place costly provider tests under `python/tests/costly`.
- Keep costly tests out of the default test command.

Use these markers for costly tests:

- `costly`: marks a test as non-default and potentially billable.
- `provider(name)`: identifies the provider, such as `openai`, `volcengine`,
  `anthropic`, or `deepseek`.
- `feature(name)`: identifies the API family, such as `generation`,
  `embedding`, `files`, `image_generation`, or `video_generation`.

## Costly Tests

Costly tests may call real provider APIs, use credentials, touch network
services, or create billable usage. Never run them as part of the default unit
test command.

Run costly tests only after explicit user confirmation:

```bash
scripts/run-costly-tests --provider volcengine --feature generation --profile cheap
```

Non-interactive usage must require an explicit consent flag, such as `--yes`.
The runner must print the provider, features, selected profiles, and selected
model IDs before asking for confirmation.

Provider optional dependencies must be installed before running matching costly
tests:

```bash
.venv/bin/python -m pip install -e "python[volcengine,test]"
.venv/bin/python -m pip install -e "python[anthropic,test]"
.venv/bin/python -m pip install -e "python[deepseek,test]"
```

Generation costly tests may skip provider 5xx or temporary-unavailable failures
because they indicate live provider capacity or service availability rather than
a stable adapter contract. Provider 4xx capability, parameter, or mapping
failures should still fail.

## Current Costly Coverage

The costly smoke-test framework covers text generation, text embedding,
image-to-text generation, image embedding, and cached multi-turn generation
model cases from `creds.json`.

Cached multi-turn generation covers:

- OpenAI full-context cache-enabled requests.
- Response-id style cache reuse for Volcengine adapters.
- Automatic prompt caching for the Anthropic adapter.

Volcengine Session cache costly tests require the model matrix to declare
`supports_session_cache=true`; otherwise they are skipped because the cache
service may require account or model activation outside adapter control.

Response-id style costly tests assert that the second turn used
`previous_response_id` successfully and did not pass only because the adapter
refreshed with full context. Image-input tests use raw inline data from
`asserts`; they do not upload assertion assets through provider File APIs.

## Previous Response Diagnostic

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

## Credentials and Model Matrix

Costly test credentials are described by a project-root `creds.json` file. This
file is ignored by Git and must not be committed.

- Never write raw API keys, access tokens, secret keys, refresh tokens, or
  session credentials to `creds.json`, documentation, shell startup files, or
  system-level environment configuration.
- Provider API keys must be provided indirectly through environment variables.
- `api_key_env` names the environment variable that contains the provider API
  key.
- `base_url` is not a secret and may be written directly in `creds.json`.
- `base_url` may be omitted when the provider adapter or SDK default should be
  used.
- The costly-test runner must read `creds.json`, resolve `api_key_env` from the
  current process environment, and pass the resolved API key only to the pytest
  child process.
- Environment changes must be scoped to the single test process by default, or
  to the current shell session only when the user explicitly uses a
  session-scoped helper.

When creating or updating `creds.json` examples, provider model matrices, or
capability schema details, read `references/creds-json.md`.

## Costly Asset Rules

Costly tests that need image, video, audio, or other assertion assets must use
files from `asserts` according to `asserts/INDEX.md`.

When a costly test uses an asset as request input, provide the asset as raw
request data, such as bytes, base64 data, data URLs, or direct inline payloads
supported by the provider adapter. Do not upload an assertion asset through a
provider File API just to use it in a generation, embedding, image, video, or
multimodal request.

Use the smallest asset that exercises the target behavior. Large assets, such as
videos, should be reserved for feature tests that specifically require that
modality.

## File API Cleanup

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
