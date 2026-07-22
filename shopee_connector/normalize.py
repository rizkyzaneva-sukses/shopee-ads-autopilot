"""Normalisasi raw payload Shopee -> baris siap-insert ke skema internal (db/schema.sql).

Prinsip: field yang belum dikenali TETAP disimpan (catch-all), jadi saat Shopee
menambah jenis biaya baru, datanya tidak hilang.
"""
from typing import Any, Dict, List

# field escrow order_income -> (jenis_fee internal, label)
# = biaya/potongan; + = tambahan pendapatan ke seller
ESCROW_FEE_MAP = {
    "commission_fee":            ("biaya_komisi", "Biaya Komisi/Kategori"),
    "service_fee":               ("biaya_layanan", "Biaya Layanan (Program)"),
    "seller_transaction_fee":    ("biaya_transaksi", "Biaya Transaksi"),
    "ams_commission_fee":        ("komisi_ams", "Komisi AMS/Afiliasi"),
    "shipping_fee":              ("biaya_ongkir", "Biaya Pengiriman"),
    "reverse_shipping_fee":      ("biaya_ongkir_retur", "Biaya Kirim Balik (Retur)"),
    "escrow_tax":                ("pajak_escrow", "Pajak"),
    "drc_adjustable_refund":     ("penyesuaian", "Penyesuaian DRC"),
    "seller_return_refund":      ("penyesuaian", "Refund ke Buyer"),
    "voucher_from_seller":       ("voucher_seller", "Voucher Ditanggung Seller"),
    "seller_discount":           ("diskon_seller", "Diskon Ditanggung Seller"),
    "seller_loss_compensation":  ("kompensasi", "Kompensasi dari Shopee (+)"),
}

# field ringkasan pendapatan di escrow
ESCROW_TOTAL_FIELDS = ("escrow_amount", "buyer_total_amount", "original_price",
                       "escrow_amount_after_adjustment")


def escrow_to_fee_rows(order_sn: str, escrow_raw: Dict[str, Any]) -> Dict[str, Any]:
    """Ubah respons get_escrow_detail -> {order_sn, totals..., fees:[...]}"""
    response = escrow_raw.get("response") or escrow_raw  # terima raw utuh atau inner
    income = response.get("order_income") or response

    fees: List[Dict[str, Any]] = []
    known = set(ESCROW_FEE_MAP) | set(ESCROW_TOTAL_FIELDS)

    for field, (jenis, label) in ESCROW_FEE_MAP.items():
        val = income.get(field)
        if isinstance(val, (int, float)) and val:
            fees.append({"order_sn": order_sn, "jenis_fee": jenis,
                         "label": label, "jumlah": val, "field_asal": field})

    # catch-all: biaya baru yang belum dipetakan
    for field, val in income.items():
        if field in known:
            continue
        if isinstance(val, (int, float)) and val and any(
            k in field for k in ("fee", "tax", "commission", "charge", "refund", "adjust")
        ):
            fees.append({"order_sn": order_sn, "jenis_fee": "lainnya",
                         "label": field, "jumlah": val, "field_asal": field})

    totals = {f: income.get(f) for f in ESCROW_TOTAL_FIELDS if f in income}
    return {"order_sn": order_sn, "totals": totals, "fees": fees}


def order_to_summary(order_detail: Dict[str, Any]) -> Dict[str, Any]:
    """Ringkasan order untuk tabel `orders`."""
    return {
        "order_sn": order_detail.get("order_sn"),
        "order_status": order_detail.get("order_status"),
        "create_time": order_detail.get("create_time"),
        "update_time": order_detail.get("update_time"),
        "pay_time": order_detail.get("pay_time"),
        "total_amount": order_detail.get("total_amount"),
        "currency": order_detail.get("currency"),
        "estimated_shipping_fee": order_detail.get("estimated_shipping_fee"),
        "actual_shipping_fee": order_detail.get("actual_shipping_fee"),
        "payment_method": order_detail.get("payment_method"),
        "n_items": len(order_detail.get("item_list") or []),
    }
