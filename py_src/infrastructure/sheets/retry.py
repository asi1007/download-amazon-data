from __future__ import annotations
import time
from functools import wraps
from typing import Callable, TypeVar

import requests
from gspread.exceptions import APIError

MAX_ATTEMPTS = 3
INITIAL_WAIT_SECONDS = 30
BACKOFF_FACTOR = 2
RETRIABLE_STATUS_CODES = frozenset({429, 500, 502, 503, 504})

T = TypeVar("T")


def _is_transient(error: Exception) -> bool:
    if isinstance(error, APIError):
        return error.code in RETRIABLE_STATUS_CODES
    return True


def _wait_seconds_before(attempt: int) -> int:
    return INITIAL_WAIT_SECONDS * BACKOFF_FACTOR**attempt


def retry_on_transient_error(operation: Callable[..., T]) -> Callable[..., T]:
    @wraps(operation)
    def wrapper(*args: object, **kwargs: object) -> T:
        for attempt in range(MAX_ATTEMPTS):
            try:
                return operation(*args, **kwargs)
            except (requests.exceptions.RequestException, APIError) as error:
                if attempt == MAX_ATTEMPTS - 1 or not _is_transient(error):
                    raise
                wait_seconds = _wait_seconds_before(attempt)
                print(f"{operation.__name__} が一時的なエラーで失敗、{wait_seconds}秒後に再試行します: {error}")
                time.sleep(wait_seconds)
        raise RuntimeError("unreachable")

    return wrapper
