from __future__ import annotations
from collections import defaultdict
from datetime import date

from sales_data.domain.value_objects.actual_profit_cell import ActualProfitCell
from py_src.domain.value_objects.fee_gap import FeeGap
from py_src.domain.value_objects.finance_record import FinanceRecord
from sales_data.domain.value_objects.sales_info import SalesInfo
from py_src.domain.value_objects.settled_fees import (
    SettledFees,
    actual_gross_profit,
    is_fully_settled,
)
from sales_data.domain.value_objects.unit_costs import UnitCosts, estimate_gross_profit

SettledByDateAsin = dict[tuple[date, str], SettledFees]


def aggregate_settled(
    records: list[FinanceRecord],
    purchase_dates: dict[str, date],
    sku_to_asin: dict[str, str],
) -> tuple[SettledByDateAsin, int]:
    # 実測は出荷日、シートの列は注文日。注文IDで注文日へ引き直してから足す。
    # 窓の外で注文された分は書き換える列が無いので落とす
    settled: SettledByDateAsin = {}
    unknown_sku_count = 0
    for record in records:
        asin = sku_to_asin.get(record.seller_sku)
        if asin is None:
            unknown_sku_count += 1
            continue
        order_date = purchase_dates.get(record.order_id)
        if order_date is None:
            continue
        key = (order_date, asin)
        current = settled.get(key, SettledFees())
        settled[key] = SettledFees(
            quantity=current.quantity + record.quantity,
            fba_fee_amount=current.fba_fee_amount + record.fba_fee_amount,
            referral_fee_amount=current.referral_fee_amount + record.referral_fee_amount,
            refunded_sales=current.refunded_sales + record.refunded_sales,
        )
    return settled, unknown_sku_count


def build_profit_cells(
    sales_by_asin: dict[str, dict[date, SalesInfo]],
    settled: SettledByDateAsin,
    costs: dict[str, UnitCosts],
) -> dict[date, list[ActualProfitCell]]:
    cells: dict[date, list[ActualProfitCell]] = defaultdict(list)
    for asin, by_date in sales_by_asin.items():
        unit_costs = costs.get(asin, UnitCosts())
        for target_date, sales in by_date.items():
            measured = settled.get((target_date, asin), SettledFees())
            profit = actual_gross_profit(sales, measured, unit_costs)
            estimate = estimate_gross_profit(sales, unit_costs)
            if profit is None or estimate is None:
                continue
            cells[target_date].append(
                ActualProfitCell(
                    asin=asin,
                    profit=profit,
                    estimate=estimate,
                    # 売れた日に実測が1件も無いのを「確定」と塗ってはいけない。
                    # 取得できていないだけかもしれず、黄色のまま残すほうが正直。
                    # 売れていない日は確定させるものが無いので白でよい
                    fully_settled=is_fully_settled(sales, measured)
                    and (sales.unit_count == 0 or measured.quantity > 0),
                )
            )
    return dict(cells)


def build_fee_gaps(
    settled: SettledByDateAsin, costs: dict[str, UnitCosts]
) -> list[FeeGap]:
    totals: dict[str, SettledFees] = {}
    for (_, asin), measured in settled.items():
        current = totals.get(asin, SettledFees())
        totals[asin] = SettledFees(
            quantity=current.quantity + measured.quantity,
            fba_fee_amount=current.fba_fee_amount + measured.fba_fee_amount,
            referral_fee_amount=current.referral_fee_amount + measured.referral_fee_amount,
        )
    gaps = [
        FeeGap(
            asin=asin,
            quantity=measured.quantity,
            estimated_referral_fee=costs[asin].selling_fee,
            actual_referral_fee=measured.referral_fee_amount / measured.quantity,
            estimated_fba_fee=costs[asin].fba_fee,
            actual_fba_fee=measured.fba_fee_amount / measured.quantity,
        )
        for asin, measured in totals.items()
        if measured.quantity > 0
        and asin in costs
        and costs[asin].selling_fee is not None
        and costs[asin].fba_fee is not None
    ]
    return sorted(gaps, key=lambda gap: -abs(gap.difference))
