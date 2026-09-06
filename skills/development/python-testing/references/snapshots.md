# Snapshot Tests

Use the snapshot library already configured by the repository. A snapshot is a load-bearing assertion only when the captured structure demonstrates behavior worth protecting.

- Prefer snapshots for complex objects, message sequences, API responses, and nested mappings.
- Keep the snapshot beside its case when parametrizing heterogeneous behavior.
- Replace timestamps, generated IDs, and other volatile values with the library's typed or pattern matchers.
- Add explicit assertions for critical facts that a broad snapshot makes hard to review.
- Do not snapshot fields unrelated to the behavior under test.
- Review every snapshot update as a code change; never accept updates solely to make the suite green.

Adapt the API to the repository's existing snapshot library:

```python
from inline_snapshot import snapshot


def test_build_payload_uses_public_shape() -> None:
    assert build_payload("Ada") == snapshot(
        {"user": {"name": "Ada"}, "enabled": True}
    )
```

Finish when the snapshot contains only meaningful stable structure and every volatile value is intentionally matched.
