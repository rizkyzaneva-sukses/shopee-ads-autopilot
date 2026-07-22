"""Penyimpanan access/refresh token per toko.

Versi file-JSON untuk pengembangan. UNTUK PRODUKSI: ganti implementasi
TokenStore dengan tabel DB terenkripsi (api_credentials) — lihat db/schema.sql.
"""
import json
import os
import time
from abc import ABC, abstractmethod
from dataclasses import asdict, dataclass
from typing import Optional


@dataclass
class Token:
    access_token: str
    refresh_token: str
    expire_in: int          # detik; Shopee umumnya 14400 (4 jam)
    obtained_at: int        # unix timestamp saat token diterbitkan
    shop_id: Optional[int] = None

    @property
    def expires_at(self) -> int:
        return self.obtained_at + self.expire_in

    def is_expiring(self, skew_seconds: int = 300) -> bool:
        """True jika token kedaluwarsa dalam `skew_seconds` (default 5 menit)."""
        return time.time() >= (self.expires_at - skew_seconds)


class TokenStore(ABC):
    @abstractmethod
    def save(self, shop_id: int, token: Token) -> None: ...

    @abstractmethod
    def load(self, shop_id: int) -> Optional[Token]: ...


class JsonFileTokenStore(TokenStore):
    def __init__(self, directory: str):
        self.directory = directory
        os.makedirs(self.directory, exist_ok=True)
        # token adalah rahasia setara password — pastikan folder ini tidak ikut ter-commit
        gitignore = os.path.join(self.directory, ".gitignore")
        if not os.path.exists(gitignore):
            with open(gitignore, "w") as f:
                f.write("*\n!.gitignore\n")

    def _path(self, shop_id: int) -> str:
        return os.path.join(self.directory, f"shop_{shop_id}.json")

    def save(self, shop_id: int, token: Token) -> None:
        token.shop_id = shop_id
        with open(self._path(shop_id), "w") as f:
            json.dump(asdict(token), f, indent=2)

    def load(self, shop_id: int) -> Optional[Token]:
        path = self._path(shop_id)
        if not os.path.exists(path):
            return None
        with open(path) as f:
            return Token(**json.load(f))
