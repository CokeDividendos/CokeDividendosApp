import time
import requests
from typing import Any
from src.config import get_settings

class RapidYHClient:
    def __init__(self):
        s = get_settings()
        self.host = s.rapidapi_host
        self.key = s.rapidapi_key

    def _headers(self) -> dict[str, str]:
        return {
            "X-RapidAPI-Key": self.key,
            "X-RapidAPI-Host": self.host,
        }

    def get(self, path: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        url = f"https://{self.host}/{path.lstrip('/')}"
        backoffs = [0.5, 1.0, 2.0]
        last_err = None

        for attempt in range(len(backoffs) + 1):
            try:
                r = requests.get(url, headers=self._headers(), params=params, timeout=20)
                if r.status_code == 429:
                    # rate limit
                    if attempt < len(backoffs):
                        time.sleep(backoffs[attempt])
                        continue
                    r.raise_for_status()
                r.raise_for_status()
                return r.json()
            except Exception as e:
                last_err = e
                if attempt < len(backoffs):
                    time.sleep(backoffs[attempt])
                    continue
                raise last_err

