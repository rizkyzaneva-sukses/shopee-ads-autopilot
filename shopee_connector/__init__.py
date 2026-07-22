"""Konektor internal Shopee Open Platform v2.

Subpaket kecil tapi lengkap untuk fondasi sistem analitik keuangan internal:
- signing HMAC-SHA256 sesuai aturan v2
- OAuth shop-level (auth URL, get_access_token, refresh otomatis)
- HTTP client dengan retry/backoff untuk rate limit
- Wrapper endpoint: Order, Payment (escrow/wallet/payout/income), Product,
  Returns, Push, Ads, AMS
- Normalisasi escrow -> baris fee siap-insert DB
- Orkestrator sinkronisasi inkremental dengan penyimpanan raw payload

Dibangun berdasarkan daftar modul resmi Shopee Open Platform v2.
"""

__version__ = "0.1.0"
