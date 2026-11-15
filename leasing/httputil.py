"""Shared HTTP session with retries and a browser-like user agent."""

from __future__ import annotations

import time
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
)

DEFAULT_TIMEOUT = 40


def session() -> requests.Session:
    s = requests.Session()
    s.headers.update(
        {
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/json,application/xhtml+xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "he-IL,he;q=0.9,en-US;q=0.8,en;q=0.7",
        }
    )
    retry = Retry(
        total=4,
        connect=4,
        read=4,
        backoff_factor=1.2,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET", "POST"),
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry)
    s.mount("https://", adapter)
    s.mount("http://", adapter)
    return s


def get(s: requests.Session, url: str, **kw: Any) -> requests.Response:
    kw.setdefault("timeout", DEFAULT_TIMEOUT)
    return s.get(url, **kw)


def post(s: requests.Session, url: str, **kw: Any) -> requests.Response:
    kw.setdefault("timeout", DEFAULT_TIMEOUT)
    return s.post(url, **kw)


def polite_sleep(seconds: float = 0.25) -> None:
    time.sleep(seconds)
