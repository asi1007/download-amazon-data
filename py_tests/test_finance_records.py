from unittest.mock import Mock

import pytest

from py_src.domain.value_objects.finance_record import FinanceRecord
from py_src.infrastructure.api.finances_repository import FinancesRepository
from py_src.infrastructure.api.sp_api_authenticator import SpApiAuthenticator


def _page(shipments: list[dict] | None = None, refunds: list[dict] | None = None,
          next_token: str | None = None) -> Mock:
    response = Mock()
    events = {}
    if shipments is not None:
        events["ShipmentEventList"] = shipments
    if refunds is not None:
        events["RefundEventList"] = refunds
    payload = {"FinancialEvents": events}
    if next_token:
        payload["NextToken"] = next_token
    response.json.return_value = {"payload": payload}
    return response


def _amount(value: float) -> dict:
    return {"CurrencyCode": "JPY", "CurrencyAmount": value}


SHIPMENT = {
    "AmazonOrderId": "503-1",
    "ShipmentItemList": [
        {
            "SellerSKU": "ZW-R3RT-17SM",
            "QuantityShipped": 2,
            "ItemChargeList": [
                {"ChargeType": "Principal", "ChargeAmount": _amount(724.0)},
                {"ChargeType": "Tax", "ChargeAmount": _amount(72.0)},
            ],
            "ItemFeeList": [
                {"FeeType": "Commission", "FeeAmount": _amount(-72.0)},
                {"FeeType": "FBAPerUnitFulfillmentFee", "FeeAmount": _amount(-500.0)},
            ],
        }
    ],
}

# 実物の形。QuantityShipped は返金でも正の値で入る
REFUND = {
    "AmazonOrderId": "503-2",
    "ShipmentItemAdjustmentList": [
        {
            "SellerSKU": "BW-5Z8A-WYZV",
            "QuantityShipped": 1,
            "ItemChargeAdjustmentList": [
                {"ChargeType": "Principal", "ChargeAmount": _amount(-434.0)},
                {"ChargeType": "Tax", "ChargeAmount": _amount(-43.0)},
            ],
            "ItemFeeAdjustmentList": [
                {"FeeType": "Commission", "FeeAmount": _amount(33.0)},
                {"FeeType": "RefundCommission", "FeeAmount": _amount(-3.0)},
            ],
        }
    ],
}


class TestGetFinanceRecords:
    def test_shipment_becomes_a_positive_quantity_and_positive_fee(self) -> None:
        auth = Mock(spec=SpApiAuthenticator)
        auth.request.return_value = _page(shipments=[SHIPMENT])

        records = FinancesRepository(authenticator=auth).get_finance_records("a", "b")

        assert records == [
            FinanceRecord(order_id="503-1", seller_sku="ZW-R3RT-17SM", quantity=2,
                          fba_fee_amount=500.0, referral_fee_amount=72.0,
                          refunded_sales=0.0)
        ]

    def test_refund_reverses_quantity_and_nets_the_fee_adjustments(self) -> None:
        # Commission +33 は払った手数料の戻し、RefundCommission -3 は新たに取られる
        # 手数料。差し引き 30 が戻る = 手数料は -30
        auth = Mock(spec=SpApiAuthenticator)
        auth.request.return_value = _page(refunds=[REFUND])

        records = FinancesRepository(authenticator=auth).get_finance_records("a", "b")

        assert records == [
            FinanceRecord(order_id="503-2", seller_sku="BW-5Z8A-WYZV", quantity=-1,
                          fba_fee_amount=0.0, referral_fee_amount=-30.0,
                          refunded_sales=434.0)
        ]

    def test_collects_both_lists_from_the_same_page(self) -> None:
        auth = Mock(spec=SpApiAuthenticator)
        auth.request.return_value = _page(shipments=[SHIPMENT], refunds=[REFUND])

        records = FinancesRepository(authenticator=auth).get_finance_records("a", "b")

        assert [r.order_id for r in records] == ["503-1", "503-2"]

    def test_follows_next_token_with_the_token_alone(self) -> None:
        auth = Mock(spec=SpApiAuthenticator)
        auth.request.side_effect = [_page(shipments=[], next_token="TOKEN"), _page(shipments=[])]

        FinancesRepository(authenticator=auth).get_finance_records(
            "2026-08-20T00:00:00Z", "2026-08-28T00:00:00Z"
        )

        second_url = auth.request.call_args_list[1][0][1]
        assert "NextToken=TOKEN" in second_url
        assert "PostedAfter" not in second_url

    def test_malformed_entries_are_skipped_rather_than_killing_the_fetch(self) -> None:
        auth = Mock(spec=SpApiAuthenticator)
        auth.request.return_value = _page(shipments=[
            {"ShipmentItemList": [{"SellerSKU": "X", "QuantityShipped": 1}]},
            {"AmazonOrderId": "503-3", "ShipmentItemList": [{"QuantityShipped": 1}]},
            SHIPMENT,
        ])

        records = FinancesRepository(authenticator=auth).get_finance_records("a", "b")

        assert [r.order_id for r in records] == ["503-1"]


class TestFeeSplit:
    def test_fba_and_referral_fees_are_counted_separately(self) -> None:
        # FBA手数料は価格に連動しないのでシートの列と直接比べられる。販売手数料は
        # 価格に比例するため、セール中に下がっても「列が古い」とは限らない
        auth = Mock(spec=SpApiAuthenticator)
        auth.request.return_value = _page(shipments=[{
            "AmazonOrderId": "503-9",
            "ShipmentItemList": [{
                "SellerSKU": "YB-C1TA-NLOP",
                "QuantityShipped": 1,
                "ItemFeeList": [
                    {"FeeType": "FBAPerUnitFulfillmentFee", "FeeAmount": _amount(-252.0)},
                    {"FeeType": "Commission", "FeeAmount": _amount(-37.0)},
                    {"FeeType": "ShippingChargeback", "FeeAmount": _amount(-7.0)},
                ],
            }],
        }])

        record = FinancesRepository(authenticator=auth).get_finance_records("a", "b")[0]

        assert record.fba_fee_amount == 252.0
        assert record.referral_fee_amount == 44.0
        assert record.fee_amount == 296.0
