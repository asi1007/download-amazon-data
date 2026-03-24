from py_src.domain.value_objects.realtime_sales_result import RealtimeSalesResult


class TestRealtimeSalesResult:
    def test_initial_values(self) -> None:
        result = RealtimeSalesResult(asin="B00EXAMPLE")

        assert result.unit_count == 0
        assert result.total_amount == 0.0

    def test_add_sale(self) -> None:
        result = RealtimeSalesResult(asin="B00EXAMPLE")
        result.add_sale(quantity=2, unit_price=1500.0)

        assert result.unit_count == 2
        assert result.total_amount == 3000.0

    def test_add_sale_accumulates(self) -> None:
        result = RealtimeSalesResult(asin="B00EXAMPLE")
        result.add_sale(quantity=2, unit_price=1500.0)
        result.add_sale(quantity=1, unit_price=1500.0)

        assert result.unit_count == 3
        assert result.total_amount == 4500.0
