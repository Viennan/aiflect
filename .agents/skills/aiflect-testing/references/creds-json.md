# `creds.json` Reference

Read this reference when creating, reviewing, or updating the project-root
`creds.json` file, costly-test model matrices, or capability examples.

## Model Matrix Rules

Each provider contains feature-specific model lists. Each feature may define
multiple models to support historical models, cost tiers, regional variants, or
provider-specific quality tiers.

Model entries use:

- `id`: concrete provider model ID.
- `profile`: cost or compatibility tier, such as `cheap`, `standard`,
  `premium`, `legacy`, or `experimental`.
- `enabled`: whether the runner may select the model.
- `capabilities`: model capability overrides for both test selection and
  `aiflect` client construction.

`capabilities` keys should match `ModelCapability` field names where possible,
for example `supports_streaming`, `supports_tools`,
`supports_parallel_tool_calls`, `supports_structured_output`,
`supports_reasoning_config`, `supports_text_embedding`,
`supports_multimodal_embedding`, `input_modalities`, `output_modalities`, and
`output_dimensions`.

Costly tests must not assume a model supports a capability merely because the
provider supports it. A costly test should skip a model when the required
capability is absent, false, or unknown. If a capability is declared true and the
provider call fails because that capability is not actually supported, the test
should fail so the model matrix can be corrected.

The runner should default to enabled low-cost models, such as `profile=cheap`,
unless the user explicitly selects a different profile or asks to run all
enabled models.

## Current Shape

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
