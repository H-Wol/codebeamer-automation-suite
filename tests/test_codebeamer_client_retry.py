from __future__ import annotations

import unittest

from src.codebeamer_client import CodebeamerClient


class _RateLimitError(Exception):
    def __init__(self, status_code: int = 429, message: str = "Too Many Requests") -> None:
        self.response = type("Response", (), {"status_code": status_code})()
        super().__init__(message)


class RetryingClient(CodebeamerClient):
    def __init__(self, responses, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._responses = list(responses)
        self.calls = 0

    def _post(self, path: str, json_body: dict | None = None, params: dict | None = None):
        del path, json_body, params
        self.calls += 1
        response = self._responses.pop(0)
        if isinstance(response, Exception):
            raise response
        return response


class CodebeamerClientRetryTest(unittest.TestCase):
    def test_create_item_retries_with_configured_delay_multiples(self) -> None:
        slept: list[float] = []
        client = RetryingClient(
            [_RateLimitError(), _RateLimitError(), {"id": 123}],
            base_url="https://example.com/cb",
            username="user",
            password="pass",
            rate_limit_retry_delay_seconds=2.0,
            rate_limit_max_retries=3,
            sleep_fn=slept.append,
        )

        result = client.create_item(1, {"name": "REQ-1"})

        self.assertEqual(result["id"], 123)
        self.assertEqual(client.calls, 3)
        self.assertEqual(slept, [2.0, 4.0])

    def test_create_item_raises_after_max_retries(self) -> None:
        slept: list[float] = []
        client = RetryingClient(
            [_RateLimitError(), _RateLimitError(), _RateLimitError()],
            base_url="https://example.com/cb",
            username="user",
            password="pass",
            rate_limit_retry_delay_seconds=1.5,
            rate_limit_max_retries=2,
            sleep_fn=slept.append,
        )

        with self.assertRaises(_RateLimitError):
            client.create_item(1, {"name": "REQ-1"})

        self.assertEqual(client.calls, 3)
        self.assertEqual(slept, [1.5, 3.0])


if __name__ == "__main__":
    unittest.main()
