# Recorded Interactions

Use the recorder already configured by the repository. Recordings protect user-visible compatibility with a real service, but stale matching can hide request drift.

## Workflow

1. Record or rewrite the interaction with the repository's documented command and authorized credentials.
2. Run the same test in playback mode without credentials or network access.
3. Review the recording diff for secrets, unstable data, accidental requests, and realistic responses.
4. Keep every load-bearing returned fact in the test assertion, not only in the recording.
5. If the test asserts an outbound field, include that field in cassette matching so a changed live request cannot replay a stale response.

Adapt marker and matcher syntax to the repository's recorder:

```python
import pytest


@pytest.mark.vcr(additional_matchers=["json_body"])
def test_create_user_sends_and_returns_name(api_client: ApiClient) -> None:
    user = api_client.create_user({"name": "Ada"})
    assert user.name == "Ada"
```

Here `json_body` is a repository-defined matcher for the request field protected by the test. Add a narrower matcher when only one field matters; do not weaken all recordings globally.

Ordinary playback must not require live credentials or unrestricted network access. Finish when playback is deterministic, matcher-sensitive to asserted outbound data, and the reviewed recording contains no secrets.
