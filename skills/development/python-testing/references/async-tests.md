# Async Tests

Use the async plugin, backend, and marker already configured by the repository; do not add `pytest-asyncio` or AnyIO merely to copy an example.

- Await the public operation rather than testing its coroutine implementation.
- Use async fixtures or async context managers for resources that require asynchronous setup and teardown.
- Exercise both streaming and non-streaming paths when they are distinct public behaviors.
- Use `AsyncMock` or async-aware fakes only at genuine isolation boundaries, and assert contract-relevant interactions.
- Keep event-loop and backend parametrization only when the project actually supports multiple backends.

Example for a repository that already uses AnyIO:

```python
import pytest


@pytest.mark.anyio
async def test_client_returns_public_result(client: Client) -> None:
    result = await client.fetch("item-1")
    assert result.id == "item-1"
```

For a repository using `pytest-asyncio`, preserve the same test body and use its configured marker instead. Finish when the async lifecycle is exercised without leaking tasks or replacing the behavior under test with mocks.
