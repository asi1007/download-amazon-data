from __future__ import annotations
import time
from functools import wraps
from typing import Callable, TypeVar

import requests

MAX_ATTEMPTS = 3
RETRY_WAIT_SECONDS = 30

T = TypeVar("T")


def retry_on_connection_error(operation: Callable[..., T]) -> Callable[..., T]:
    @wraps(operation)
    def wrapper(*args: object, **kwargs: object) -> T:
        for attempt in range(MAX_ATTEMPTS):
            try:
                return operation(*args, **kwargs)
            except requests.exceptions.RequestException as error:
                if attempt == MAX_ATTEMPTS - 1:
                    raise
                print(f"{operation.__name__} が通信エラーで失敗、{RETRY_WAIT_SECONDS}秒後に再試行します: {error}")
                time.sleep(RETRY_WAIT_SECONDS)
        raise RuntimeError("unreachable")

    return wrapper
