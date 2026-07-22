"""Notifier Telegram Bot API (gratis, tanpa dependency khusus).

Butuh di Settings: tg_token (dari @BotFather) + tg_chat_id (chat Anda / grup).
baca panduan singkat cara buat bot di halaman Settings aplikasi.
"""
import logging
from typing import Optional

import requests

from . import db

log = logging.getLogger("autopilot.notify")


def kirim(c, pesan: str, parse_html: bool = True) -> bool:
    """Kirim pesan Telegram. Return True bila terkirim."""
    token = db.get_setting(c, "tg_token", "")
    chat_id = db.get_setting(c, "tg_chat_id", "")
    if not token or not chat_id:
        log.info("Telegram belum diset — pesan hanya dicatat: %s", pesan[:80])
        return False
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{token}/sendMessage",
            json={"chat_id": chat_id, "text": pesan,
                  **({"parse_mode": "HTML"} if parse_html else {})},
            timeout=15,
        )
        ok = r.ok and (r.json().get("ok") is True)
        if not ok:
            log.warning("Telegram gagal: %s", r.text[:200])
        return ok
    except requests.RequestException as e:
        log.warning("Telegram error: %s", e)
        return False


def kirim_aksi(nama_rule: str, nama_toko: str, nama_kampanye: str,
               aksi: str, nilai_metrik: str, mode_: str) -> str:
    return (f"🤖 <b>Autopilot</b> [{mode_.upper()}]\n"
            f"Aturan: <b>{nama_rule}</b>\n"
            f"Toko: {nama_toko} · Kampanye: {nama_kampanye}\n"
            f"Aksi: <b>{aksi}</b>\n"
            f"Kondisi: {nilai_metrik}")
