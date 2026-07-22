"""Konfigurasi konektor — dibaca dari environment variable."""
import os
from dataclasses import dataclass

BASE_URL_PROD = "https://partner.shopeemobile.com"
BASE_URL_SANDBOX = "https://partner.test-stable.shopee.cn"


@dataclass(frozen=True)
class Config:
    partner_id: int
    partner_key: str
    base_url: str = BASE_URL_PROD
    redirect_url: str = ""
    token_dir: str = "./tokens"
    raw_dir: str = "./raw_payload"
    sync_state_dir: str = "./sync_state"

    @classmethod
    def from_env(cls) -> "Config":
        partner_id = os.environ.get("SHOPEE_PARTNER_ID", "").strip()
        partner_key = os.environ.get("SHOPEE_PARTNER_KEY", "").strip()
        if not partner_id or not partner_key:
            raise RuntimeError(
                "SHOPEE_PARTNER_ID dan SHOPEE_PARTNER_KEY belum di-set. "
                "Salin .env.example -> .env, isi, lalu: set -a; source .env; set +a"
            )
        return cls(
            partner_id=int(partner_id),
            partner_key=partner_key,
            base_url=os.environ.get("SHOPEE_BASE_URL", BASE_URL_PROD).rstrip("/"),
            redirect_url=os.environ.get("SHOPEE_REDIRECT_URL", ""),
            token_dir=os.environ.get("SHOPEE_TOKEN_DIR", "./tokens"),
            raw_dir=os.environ.get("SHOPEE_RAW_DIR", "./raw_payload"),
            sync_state_dir=os.environ.get("SHOPEE_SYNC_STATE_DIR", "./sync_state"),
        )
