import pytest
from py_src.domain.value_objects.sales_info import SalesInfo


class TestSalesInfo:
    def test_creation(self) -> None:
        info = SalesInfo(unit_count=5, total_sales_amount=15000.0, order_count=3)
        assert info.unit_count == 5
        assert info.total_sales_amount == 15000.0
        assert info.order_count == 3

    def test_immutable(self) -> None:
        info = SalesInfo(unit_count=5, total_sales_amount=15000.0, order_count=3)
        with pytest.raises(AttributeError):
            info.unit_count = 10

    def test_default_values(self) -> None:
        info = SalesInfo()
        assert info.unit_count == 0
        assert info.total_sales_amount == 0.0
        assert info.order_count == 0
