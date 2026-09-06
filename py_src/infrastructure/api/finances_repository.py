from __future__ import annotations
from urllib.parse import urlencode

from py_src.domain.value_objects.finance_record import FinanceRecord
from py_src.infrastructure.api.sp_api_authenticator import SpApiAuthenticator, SP_API_BASE

PRINCIPAL_CHARGE_TYPE = "Principal"
# FBA手数料は価格に連動しない（シートの FBA手数料 列と直接比べられる）。
# 販売手数料は価格に比例するため、セール中は下がるのが当然で「列が古い」とは
# 限らない。原因を切り分けるには分けて数える必要がある
FBA_FEE_TYPE_PREFIX = "FBA"


class FinancesRepository:
    def __init__(self, authenticator: SpApiAuthenticator) -> None:
        self._auth = authenticator

    def get_finance_records(self, posted_after: str, posted_before: str) -> list[FinanceRecord]:
        self._auth.authenticate()
        records: list[FinanceRecord] = []
        url = self._events_url(posted_after, posted_before)
        while True:
            payload = self._auth.request("GET", url).json().get("payload", {})
            events = payload.get("FinancialEvents", {})
            records.extend(self._shipment_records(events.get("ShipmentEventList", [])))
            records.extend(self._refund_records(events.get("RefundEventList", [])))
            next_token = payload.get("NextToken")
            if not next_token:
                return records
            url = self._next_page_url(next_token)

    @staticmethod
    def _events_url(posted_after: str, posted_before: str) -> str:
        return (
            f"{SP_API_BASE}/finances/v0/financialEvents"
            f"?PostedAfter={posted_after}"
            f"&PostedBefore={posted_before}"
        )

    @staticmethod
    def _next_page_url(next_token: str) -> str:
        # NextToken は PostedAfter/PostedBefore と排他。併記すると2ページ目だけが
        # 本番で落ちる。tools/check_finances_api.py で実物を確認した形に揃える
        return f"{SP_API_BASE}/finances/v0/financialEvents?{urlencode({'NextToken': next_token})}"

    @classmethod
    def _shipment_records(cls, events: list[dict]) -> list[FinanceRecord]:
        return cls._records_from(events, "ShipmentItemList", "ItemFeeList", None)

    @classmethod
    def _refund_records(cls, events: list[dict]) -> list[FinanceRecord]:
        # 返金でも QuantityShipped は正の値で入るため、こちらで符号を反転する。
        # 手数料は「払った分の戻し(正)」と「返金手数料(負)」が混在し、合計が
        # 戻ってくる額になる。出荷イベントと同じ -Σ で符号が揃う
        return cls._records_from(
            events,
            "ShipmentItemAdjustmentList",
            "ItemFeeAdjustmentList",
            "ItemChargeAdjustmentList",
        )

    @staticmethod
    def _records_from(
        events: list[dict], item_key: str, fee_key: str, refund_charge_key: str | None
    ) -> list[FinanceRecord]:
        # 1件でも形の違うイベントが混ざると14日分の取得が丸ごと死ぬので .get() で通す
        records: list[FinanceRecord] = []
        for event in events:
            order_id = event.get("AmazonOrderId")
            if not order_id:
                continue
            for item in event.get(item_key, []):
                seller_sku = item.get("SellerSKU")
                if not seller_sku:
                    continue
                quantity = item.get("QuantityShipped", 0)
                fba_fee, referral_fee = _split_fees(item.get(fee_key, []))
                refunded_sales = 0.0
                if refund_charge_key is not None:
                    quantity = -quantity
                    refunded_sales = -sum(
                        charge.get("ChargeAmount", {}).get("CurrencyAmount", 0)
                        for charge in item.get(refund_charge_key, [])
                        if charge.get("ChargeType") == PRINCIPAL_CHARGE_TYPE
                    )
                records.append(
                    FinanceRecord(
                        order_id=order_id,
                        seller_sku=seller_sku,
                        quantity=quantity,
                        fba_fee_amount=fba_fee,
                        referral_fee_amount=referral_fee,
                        refunded_sales=refunded_sales,
                    )
                )
        return records


def _split_fees(fees: list[dict]) -> tuple[float, float]:
    fba = referral = 0.0
    for fee in fees:
        amount = -fee.get("FeeAmount", {}).get("CurrencyAmount", 0)
        if str(fee.get("FeeType", "")).startswith(FBA_FEE_TYPE_PREFIX):
            fba += amount
        else:
            referral += amount
    return fba, referral
