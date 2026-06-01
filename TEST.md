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

Coming soon.
