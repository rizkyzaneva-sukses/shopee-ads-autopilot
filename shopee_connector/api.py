"""Wrapper endpoint Shopee v2 — tipis dan mudah diperluas.

Konvensi: semua fungsi mengembalikan dict respons utuh ("response" Shopee),
mentah apa adanya — simpan dulu raw payload, normalisasi belakangan (normalize.py).

Endpoint yang belum 100% pasti nama parameternya diberi **extra passthrough
+ komentar; cocokkan dengan halaman dokumentasi modul terkait saat implementasi.
"""
from typing import Any, Dict, Iterable, List, Optional

from .client import ShopeeClient

# ============================================================ ORDER
ORDER_LIST = "/api/v2/order/get_order_list"
ORDER_DETAIL = "/api/v2/order/get_order_detail"

# Field opsional resmi agar detail order lengkap (dipakai saat get_order_detail)
ORDER_DETAIL_FIELDS = (
    "buyer_user_id,buyer_username,estimated_shipping_fee,recipient_address,"
    "actual_shipping_fee,goods_to_declare,note,note_update_time,item_list,"
    "pay_time,dropshipper,dropshipper_phone,split_up,buyer_cancel_reason,"
    "cancel_by,cancel_reason,actual_shipping_fee_confirmed,buyer_cpf_id,"
    "fulfillment_flag,pickup_done_time,package_list,shipping_carrier,"
    "payment_method,total_amount,invoice_data"
)


def get_order_list(client: ShopeeClient, shop_id: int, time_from: int, time_to: int,
                   time_range_field: str = "update_time",
                   page_size: int = 100, cursor: str = "",
                   order_status: Optional[str] = None) -> Dict[str, Any]:
    """Daftar pesanan dalam rentang waktu. Inkremental: pakai update_time.
    NOTE: rentang maksimum 15 hari per call."""
    params: Dict[str, Any] = {
        "time_range_field": time_range_field,
        "time_from": time_from,
        "time_to": time_to,
        "page_size": page_size,
        "cursor": cursor,
        "response_optional_fields": "order_status",
    }
    if order_status:
        params["order_status"] = order_status
    return client.shop_call(shop_id, ORDER_LIST, **params)


def get_order_detail(client: ShopeeClient, shop_id: int, order_sn_list: Iterable[str],
                     batch_size: int = 45) -> List[Dict[str, Any]]:
    """Detail banyak pesanan sekaligus (maks 50/call; default aman 45).
    Mengembalikan list order detail ter-gabung dari semua batch."""
    sns = list(order_sn_list)
    out: List[Dict[str, Any]] = []
    for i in range(0, len(sns), batch_size):
        batch = sns[i:i + batch_size]
        data = client.shop_call(
            shop_id, ORDER_DETAIL,
            order_sn_list=",".join(batch),
            response_optional_fields=ORDER_DETAIL_FIELDS,
        )
        out.extend((data.get("response") or {}).get("order_list") or [])
    return out


def list_order_sn(client: ShopeeClient, shop_id: int, time_from: int, time_to: int,
                  time_range_field: str = "update_time",
                  order_status: Optional[str] = None) -> List[Dict[str, Any]]:
    """Helper: kumpulkan semua order_sn (auto-pagination via cursor+more)."""
    orders: List[Dict[str, Any]] = []
    cursor = ""
    while True:
        data = get_order_list(client, shop_id, time_from, time_to,
                              time_range_field=time_range_field, cursor=cursor,
                              order_status=order_status)
        r = data.get("response") or {}
        orders.extend(r.get("order_list") or [])
        if r.get("more"):
            cursor = r.get("next_cursor", "")
        else:
            return orders


# ============================================================ SHOP
def get_shop_info(client: ShopeeClient, shop_id: int) -> Dict[str, Any]:
    return client.shop_call(shop_id, "/api/v2/shop/get_shop_info")


# ============================================================ PAYMENT (inti keuangan)
ESCROW_LIST = "/api/v2/payment/get_escrow_list"
ESCROW_DETAIL = "/api/v2/payment/get_escrow_detail"
ESCROW_DETAIL_BATCH = "/api/v2/payment/get_escrow_detail_batch"


def get_escrow_detail(client: ShopeeClient, shop_id: int, order_sn: str) -> Dict[str, Any]:
    """Rincian penghasilan + SEMUA potongan untuk 1 pesanan (hanya yg selesai)."""
    return client.shop_call(shop_id, ESCROW_DETAIL, order_sn=order_sn)


def get_escrow_detail_batch(client: ShopeeClient, shop_id: int,
                            order_sn_list: Iterable[str], batch_size: int = 45) -> List[Dict[str, Any]]:
    """Versi batch — cara paling efisien menarik escrow banyak pesanan."""
    sns = list(order_sn_list)
    out: List[Dict[str, Any]] = []
    for i in range(0, len(sns), batch_size):
        batch = sns[i:i + batch_size]
        data = client.shop_call(shop_id, ESCROW_DETAIL_BATCH, order_sn_list=",".join(batch))
        out.extend((data.get("response") or {}).get("escrow_list") or [])
    return out


def get_escrow_list(client: ShopeeClient, shop_id: int, time_from: int, time_to: int,
                    cursor: str = "", page_size: int = 100, **extra) -> Dict[str, Any]:
    """Daftar escrow yang cair pada rentang waktu (untuk rekonsiliasi berkala).
    Sesuaikan nama param rentang waktu dengan dok Payment > get_escrow_list."""
    params = {"release_time_from": time_from, "release_time_to": time_to,
              "cursor": cursor, "page_size": page_size, **extra}
    return client.shop_call(shop_id, ESCROW_LIST, **params)


def get_wallet_transaction_list(client: ShopeeClient, shop_id: int, **extra) -> Dict[str, Any]:
    """Transaksi dompet seller (uang masuk/keluar) -> rekonsiliasi payout."""
    return client.shop_call(shop_id, "/api/v2/payment/get_wallet_transaction_list", **extra)


def get_payout_info(client: ShopeeClient, shop_id: int, **extra) -> Dict[str, Any]:
    return client.shop_call(shop_id, "/api/v2/payment/get_payout_info", **extra)


def get_payout_detail(client: ShopeeClient, shop_id: int, **extra) -> Dict[str, Any]:
    return client.shop_call(shop_id, "/api/v2/payment/get_payout_detail", **extra)


def get_billing_transaction_info(client: ShopeeClient, shop_id: int, **extra) -> Dict[str, Any]:
    return client.shop_call(shop_id, "/api/v2/payment/get_billing_transaction_info", **extra)


def generate_income_statement(client: ShopeeClient, shop_id: int, time_from: int, time_to: int) -> Dict[str, Any]:
    return client.shop_call(shop_id, "/api/v2/payment/generate_income_statement",
                            time_from=time_from, time_to=time_to)


def get_income_statement(client: ShopeeClient, shop_id: int, statement_id: Any, **extra) -> Dict[str, Any]:
    return client.shop_call(shop_id, "/api/v2/payment/get_income_statement",
                            statement_id=statement_id, **extra)


# ============================================================ PRODUCT (mapping SKU)
def get_item_list(client: ShopeeClient, shop_id: int, offset: int = 0, page_size: int = 100,
                  item_status: str = "NORMAL") -> Dict[str, Any]:
    return client.shop_call(shop_id, "/api/v2/product/get_item_list",
                            offset=offset, page_size=page_size, item_status=item_status)


def get_item_base_info(client: ShopeeClient, shop_id: int, item_id_list: Iterable[int]) -> Dict[str, Any]:
    return client.shop_call(shop_id, "/api/v2/product/get_item_base_info",
                            item_id_list=",".join(str(i) for i in item_id_list))


def get_model_list(client: ShopeeClient, shop_id: int, item_id: int) -> Dict[str, Any]:
    return client.shop_call(shop_id, "/api/v2/product/get_model_list", item_id=item_id)


# ============================================================ RETURNS
def get_return_list(client: ShopeeClient, shop_id: int, page_no: int = 1,
                    page_size: int = 50, **filters) -> Dict[str, Any]:
    return client.shop_call(shop_id, "/api/v2/returns/get_return_list",
                            page_no=page_no, page_size=page_size, **filters)


def get_return_detail(client: ShopeeClient, shop_id: int, return_sn: str) -> Dict[str, Any]:
    return client.shop_call(shop_id, "/api/v2/returns/get_return_detail", return_sn=return_sn)


# ============================================================ PUSH (real-time & reliabilitas)
def get_app_push_config(client: ShopeeClient) -> Dict[str, Any]:
    return client.partner_call("/api/v2/push/get_app_push_config")


def set_app_push_config(client: ShopeeClient, callback_url: str, **extra) -> Dict[str, Any]:
    return client.partner_call("/api/v2/push/set_app_push_config", method="POST",
                               json_body={"callback_url": callback_url, **extra})


def get_lost_push_message(client: ShopeeClient, **extra) -> Dict[str, Any]:
    """Tarik event push yang terlewat (mekanisme anti-hilang)."""
    return client.partner_call("/api/v2/push/get_lost_push_message", method="POST", json_body=extra)


def confirm_consumed_lost_push_message(client: ShopeeClient, **extra) -> Dict[str, Any]:
    return client.partner_call("/api/v2/push/confirm_consumed_lost_push_message",
                               method="POST", json_body=extra)


def get_shopee_ip_ranges(client: ShopeeClient) -> Dict[str, Any]:
    """Whitelist sumber webhook di sisi Anda."""
    return client.partner_call("/api/v2/public/get_shopee_ip_ranges")


# ============================================================ ADS (ROAS)
def get_ads_total_balance(client: ShopeeClient, shop_id: int) -> Dict[str, Any]:
    return client.shop_call(shop_id, "/api/v2/ads/get_total_balance")


def get_all_cpc_ads_daily_performance(client: ShopeeClient, shop_id: int,
                                      start_date: str, end_date: str, **extra) -> Dict[str, Any]:
    """Performa harian seluruh CPC ads (format tanggal: YYYY-MM-DD)."""
    return client.shop_call(shop_id, "/api/v2/ads/get_all_cpc_ads_daily_performance",
                            start_date=start_date, end_date=end_date, **extra)


def get_all_cpc_ads_hourly_performance(client: ShopeeClient, shop_id: int,
                                       date: str, **extra) -> Dict[str, Any]:
    return client.shop_call(shop_id, "/api/v2/ads/get_all_cpc_ads_hourly_performance",
                            date=date, **extra)


def get_product_campaign_daily_performance(client: ShopeeClient, shop_id: int,
                                           start_date: str, end_date: str, **extra) -> Dict[str, Any]:
    return client.shop_call(shop_id, "/api/v2/ads/get_product_campaign_daily_performance",
                            start_date=start_date, end_date=end_date, **extra)


def get_product_level_campaign_id_list(client: ShopeeClient, shop_id: int, **extra) -> Dict[str, Any]:
    return client.shop_call(shop_id, "/api/v2/ads/get_product_level_campaign_id_list", **extra)


# ============================================================ AMS (afiliasi, modul 127)
def get_open_campaign_added_product(client: ShopeeClient, shop_id: int,
                                    cursor: str = "", page_size: int = 100) -> Dict[str, Any]:
    return client.shop_call(shop_id, "/api/v2/ams/get_open_campaign_added_product",
                            cursor=cursor, page_size=page_size)


def get_open_campaign_performance(client: ShopeeClient, shop_id: int, **extra) -> Dict[str, Any]:
    return client.shop_call(shop_id, "/api/v2/ams/get_open_campaign_performance", **extra)


def get_shop_performance(client: ShopeeClient, shop_id: int, **extra) -> Dict[str, Any]:
    return client.shop_call(shop_id, "/api/v2/ams/get_shop_performance", **extra)


def get_product_performance(client: ShopeeClient, shop_id: int, **extra) -> Dict[str, Any]:
    return client.shop_call(shop_id, "/api/v2/ams/get_product_performance", **extra)


def get_affiliate_performance(client: ShopeeClient, shop_id: int, **extra) -> Dict[str, Any]:
    return client.shop_call(shop_id, "/api/v2/ams/get_affiliate_performance", **extra)


def get_ams_conversion_report(client: ShopeeClient, shop_id: int, **extra) -> Dict[str, Any]:
    """Laporan konversi afiliasi (revenue per konversi) -> dasar analytics afiliasi."""
    return client.shop_call(shop_id, "/api/v2/ams/get_conversion_report", **extra)


def batch_edit_products_open_campaign_setting(client: ShopeeClient, shop_id: int,
                                              settings: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Ubah komisi banyak produk sekaligus — inti logic 'margin -> komisi otomatis'.

    `settings`: list item sesuai dok AMS, mis. [{"item_id": 123, "commission_rate": 5.0}].
    Verifikasi nama field body persisnya di dok modul AMS sebelum dipakai.
    """
    if not client.token_store:
        raise RuntimeError("Butuh TokenStore")
    token = client.token_store.load(shop_id)
    return client.request(
        "POST", "/api/v2/ams/batch_edit_products_open_campaign_setting",
        json_body={"settings": settings},          # TODO: sesuaikan schema body dgn dok AMS
        access_token=token.access_token, shop_id=shop_id,
    )
