from datetime import date
from unittest.mock import Mock

from py_src.domain.value_objects.item_fee import ItemFee
from py_src.infrastructure.api.finances_repository import FinancesRepository


def _events_page(events: list[dict], next_token: str | None = None) -> Mock:
    response = Mock()
    response.status_code = 200
    payload = {"FinancialEvents": {"ShipmentEventList": events}}
    if next_token:
        payload["NextToken"] = next_token
    response.json.return_value = {"payload": payload}
    return response


class TestFinancesRepository:
    def test_flattens_item_fees(self) -> None:
        auth = Mock()
        auth._session.get.return_value = _events_page([
            {
                "AmazonOrderId": "249-1",
                "ShipmentItemList": [
                    {
                        "SellerSKU": "SKU-A",
                        "ItemFeeList": [
                            {"FeeType": "Commission",
                             "FeeAmount": {"CurrencyAmount": -100.0}},
                            {"FeeType": "FBAPerUnitFulfillmentFee",
                             "FeeAmount": {"CurrencyAmount": -300.0}},
                        ],
                    }
                ],
            }
        ])
        repository = FinancesRepository(authenticator=auth, pause_seconds=0)

        fees = repository.get_item_fees("2026-09-01T00:00:00Z", "2026-09-02T00:00:00Z")

        assert fees == [
            ItemFee(order_id="249-1", seller_sku="SKU-A", fee_amount=400.0),
        ]

    def test_fees_are_positive_even_though_the_api_returns_negatives(self) -> None:
        auth = Mock()
        auth._session.get.return_value = _events_page([
            {
                "AmazonOrderId": "249-2",
                "ShipmentItemList": [
                    {"SellerSKU": "SKU-B",
                     "ItemFeeList": [{"FeeType": "Commission",
                                      "FeeAmount": {"CurrencyAmount": -55.5}}]},
                ],
            }
        ])
        repository = FinancesRepository(authenticator=auth, pause_seconds=0)

        assert repository.get_item_fees("a", "b")[0].fee_amount == 55.5

    def test_follows_next_token(self) -> None:
        auth = Mock()
        auth._session.get.side_effect = [
            _events_page([
                {"AmazonOrderId": "249-1", "ShipmentItemList": [
                    {"SellerSKU": "SKU-A", "ItemFeeList": [
                        {"FeeType": "Commission", "FeeAmount": {"CurrencyAmount": -10.0}}]}]}
            ], next_token="TOKEN"),
            _events_page([
                {"AmazonOrderId": "249-2", "ShipmentItemList": [
                    {"SellerSKU": "SKU-B", "ItemFeeList": [
                        {"FeeType": "Commission", "FeeAmount": {"CurrencyAmount": -20.0}}]}]}
            ]),
        ]
        repository = FinancesRepository(authenticator=auth, pause_seconds=0)

        fees = repository.get_item_fees("a", "b")

        assert [fee.order_id for fee in fees] == ["249-1", "249-2"]

    def test_event_without_fees_is_skipped(self) -> None:
        auth = Mock()
        auth._session.get.return_value = _events_page([
            {"AmazonOrderId": "249-3", "ShipmentItemList": [
                {"SellerSKU": "SKU-C", "ItemFeeList": []}]}
        ])
        repository = FinancesRepository(authenticator=auth, pause_seconds=0)

        assert repository.get_item_fees("a", "b") == []
