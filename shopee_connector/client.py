"""HTTP client Shopee Open Platform v2.

Aturan signing resmi (dok "Generate sign"):
- Shop-level API : sign = HMAC_SHA256(partner_key, partner_id + path + timestamp + access_token + shop_id)
- Merchant-level : ... + access_token + main_account_id
- Tanpa toko     : sign = HMAC_SHA256(partner_key, partner_id + path + timestamp)
  (dipakai untuk /api/v2/auth/token/get, /api/v2/auth/access_token/get, dsb.)

Common query params untuk SEMUA request: partner_id, timestamp, sign
(+ access_token & shop_id untuk shop-level).

Fitur client:
- retry + exponential backoff untuk HTTP 429/5xx (rate limit & gangguan server)
- refresh token proaktif (sebelum kedaluwarsa) dan reaktif (saat error token)
"""
import hashlib
import hmac
import logging
import random
import time
from typing import Any, Dict, Optional

import requests

from .config import Config
from .token_store import TokenStore

log = logging.getLogger("shopee_connector")

TOKEN_ERROR_KEYWORDS = (
    "invalid_acceess_token",   # typo asli dari Shopee — jangan dikoreksi
    "invalid_access_token",
    "invalid_token",
    "error_auth",
    "token_expired",
    "error_expire_token",
)


class ShopeeAPIError(RuntimeError):
    def __init__(self, error: str, message: str, request_id: str = "", status_code: int = 0):
        super().__init__(f"[{error}] {message} (request_id={request_id or '-'})")
        self.error, self.message, self.request_id, self.status_code = error, message, request_id, status_code

    def is_token_error(self) -> bool:
        text = f"{self.error} {self.message}".lower()
        return any(k in text for k in TOKEN_ERROR_KEYWORDS)


class ShopeeClient:
    def __init__(self, config: Config, token_store: Optional[TokenStore] = None,
                 session: Optional[requests.Session] = None,
                 max_retries: int = 5, timeout: int = 30):
        self.config = config
        self.token_store = token_store
        self.session = session or requests.Session()
        self.max_retries = max_retries
        self.timeout = timeout

    # ---------- signing ----------
    def _sign(self, path: str, timestamp: int, access_token: str = "", shop_id: Optional[int] = None) -> str:
        base = f"{self.config.partner_id}{path}{timestamp}{access_token}{shop_id or ''}"
        return hmac.new(self.config.partner_key.encode(), base.encode(), hashlib.sha256).hexdigest()

    def _signed_query(self, path: str, access_token: Optional[str] = None,
                      shop_id: Optional[int] = None, extra: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        ts = int(time.time())
        q: Dict[str, Any] = {
            "partner_id": self.config.partner_id,
            "timestamp": ts,
            "sign": self._sign(path, ts, access_token or "", shop_id),
        }
        if access_token:
            q["access_token"] = access_token
        if shop_id:
            q["shop_id"] = shop_id
        if extra:
            q.update(extra)
        return q

    # ---------- core request dengan retry ----------
    def request(self, method: str, path: str, *, params: Optional[Dict[str, Any]] = None,
                json_body: Optional[Dict[str, Any]] = None,
                access_token: Optional[str] = None, shop_id: Optional[int] = None,
                allow_token_retry: bool = True) -> Dict[str, Any]:
        url = self.config.base_url + path
        attempt = 0
        while True:
            query = self._signed_query(path, access_token, shop_id, params)
            try:
                resp = self.session.request(method, url, params=query, json=json_body, timeout=self.timeout)
            except requests.RequestException as e:
                self._backoff(attempt, f"network error: {e}")
                attempt += 1
                continue

            if resp.status_code in (429, 500, 502, 503, 504):
                self._backoff(attempt, f"HTTP {resp.status_code}")
                attempt += 1
                continue

            data = resp.json()
            err = data.get("error") or ""
            if not err:
                return data

            exc = ShopeeAPIError(err, data.get("message", ""), data.get("request_id", ""), resp.status_code)
            if exc.is_token_error() and shop_id and allow_token_retry and self.token_store:
                log.warning("Token error untuk shop %s -> refresh & coba ulang sekali", shop_id)
                new_token = self._refresh(shop_id)
                return self.request(method, path, params=params, json_body=json_body,
                                    access_token=new_token.access_token, shop_id=shop_id,
                                    allow_token_retry=False)
            if err.startswith("error_param_too_many") or "frequency" in err:  # rate limit versi Shopee
                self._backoff(attempt, f"rate limit: {err}")
                attempt += 1
                continue
            raise exc

    def _backoff(self, attempt: int, reason: str) -> None:
        if attempt >= self.max_retries:
            raise ShopeeAPIError("retry_exhausted", f"Gagal setelah {self.max_retries}x: {reason}")
        sleep = min(2 ** attempt, 30) + random.uniform(0, 0.5)
        log.info("Retry #%s dalam %.1fs (%s)", attempt + 1, sleep, reason)
        time.sleep(sleep)

    def _refresh(self, shop_id: int):
        from .auth import Token, refresh_access_token  # import lokal: hindari siklus
        assert self.token_store, "TokenStore diperlukan untuk refresh"
        token = refresh_access_token(self, shop_id)
        self.token_store.save(shop_id, token)
        return token

    # ---------- tingkat toko (butuh access_token) ----------
    def shop_call(self, shop_id: int, path: str, method: str = "GET", **query) -> Dict[str, Any]:
        if not self.token_store:
            raise RuntimeError("shop_call butuh TokenStore")
        token = self.token_store.load(shop_id)
        if token is None:
            raise RuntimeError(f"Toko {shop_id} belum diotorisasi. Jalankan scripts/authorize_shop.py")
        if token.is_expiring():
            log.info("Token shop %s hampir kedaluwarsa -> refresh proaktif", shop_id)
            token = self._refresh(shop_id)
        return self.request(method, path, params=query, access_token=token.access_token, shop_id=shop_id)

    # ---------- tingkat partner/app (tanpa token toko) ----------
    def partner_call(self, path: str, method: str = "GET", json_body: Optional[Dict[str, Any]] = None,
                     **query) -> Dict[str, Any]:
        return self.request(method, path, params=query or None, json_body=json_body)
