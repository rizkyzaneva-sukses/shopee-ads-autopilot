"""OAuth shop-level Shopee v2.

Alur:
1. Seller membuka URL dari `build_authorization_url()` dan menyetujui.
2. Shopee redirect ke redirect_url Anda dengan ?code=...&shop_id=...
3. Tukar code -> token via `get_access_token()` (berlaku ±4 jam).
4. Sebelum/sesudah kedaluwarsa -> `refresh_access_token()` (sudah otomatis di client).
"""
import time
from typing import Optional
from urllib.parse import quote

from .client import ShopeeClient
from .config import Config
from .token_store import Token

AUTH_PARTNER_PATH = "/api/v2/shop/auth_partner"
TOKEN_GET_PATH = "/api/v2/auth/token/get"
REFRESH_TOKEN_PATH = "/api/v2/auth/access_token/get"

DEFAULT_EXPIRE_IN = 14400  # 4 jam


def build_authorization_url(config: Config) -> str:
    """URL yang dibuka pemilik toko untuk mengotorisasi app."""
    ts = int(time.time())
    base = f"{config.partner_id}{AUTH_PARTNER_PATH}{ts}"
    import hashlib
    import hmac
    sign = hmac.new(config.partner_key.encode(), base.encode(), hashlib.sha256).hexdigest()
    redirect = quote(config.redirect_url, safe="")
    return (
        f"{config.base_url}{AUTH_PARTNER_PATH}"
        f"?partner_id={config.partner_id}&redirect={redirect}&timestamp={ts}&sign={sign}"
    )


def get_access_token(client: ShopeeClient, code: str, shop_id: Optional[int] = None,
                     main_account_id: Optional[int] = None) -> Token:
    """Tukar `code` dari redirect OAuth menjadi access+refresh token."""
    body = {"code": code, "partner_id": client.config.partner_id}
    if shop_id:
        body["shop_id"] = int(shop_id)
    elif main_account_id:
        body["main_account_id"] = int(main_account_id)
    else:
        raise ValueError("Isi shop_id atau main_account_id")

    data = client.partner_call(TOKEN_GET_PATH, method="POST", json_body=body)
    # Shopee API v2 token endpoint dapat mengembalikan kunci di root atau di dalam 'response'
    r = data.get("response") if (isinstance(data.get("response"), dict) and "access_token" in data.get("response")) else data

    if "access_token" not in r:
        err_code = data.get("error") or "token_error"
        err_msg = data.get("message") or f"Respon Shopee API tidak berisi access_token. Respon lengkap: {data}"
        req_id = data.get("request_id") or ""
        raise RuntimeError(f"[{err_code}] {err_msg} (request_id={req_id})")

    shop_id_found = shop_id
    if not shop_id_found and r.get("shop_id_list"):
        shop_id_found = r["shop_id_list"][0]

    token = Token(
        access_token=r["access_token"],
        refresh_token=r["refresh_token"],
        expire_in=int(r.get("expire_in", DEFAULT_EXPIRE_IN)),
        obtained_at=int(time.time()),
        shop_id=shop_id_found,
    )
    return token




def refresh_access_token(client: ShopeeClient, shop_id: int) -> Token:
    """Refresh token yang akan/habis masa berlakunya. Dipanggil otomatis oleh ShopeeClient."""
    assert client.token_store, "TokenStore diperlukan"
    existing = client.token_store.load(shop_id)
    if existing is None:
        raise RuntimeError(f"Tidak ada token tersimpan untuk shop {shop_id}")

    body = {
        "refresh_token": existing.refresh_token,
        "partner_id": client.config.partner_id,
        "shop_id": shop_id,
    }
    data = client.partner_call(REFRESH_TOKEN_PATH, method="POST", json_body=body)
    r = data.get("response") if (isinstance(data.get("response"), dict) and "access_token" in data.get("response")) else data
    if "access_token" not in r:
        err_code = data.get("error") or "refresh_error"
        err_msg = data.get("message") or f"Respon refresh token Shopee API tidak berisi access_token: {data}"
        raise RuntimeError(f"[{err_code}] {err_msg}")

    return Token(
        access_token=r["access_token"],
        refresh_token=r.get("refresh_token") or existing.refresh_token,
        expire_in=int(r.get("expire_in", DEFAULT_EXPIRE_IN)),
        obtained_at=int(time.time()),
        shop_id=shop_id,
    )

