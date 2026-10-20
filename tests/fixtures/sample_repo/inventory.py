"""Warehouse inventory: stock levels, reorder rules and shipments."""

from dataclasses import dataclass, field


@dataclass
class Item:
    sku: str
    name: str
    quantity: int = 0
    reorder_level: int = 10
    tags: list[str] = field(default_factory=list)


class Inventory:
    def __init__(self) -> None:
        self.items: dict[str, Item] = {}

    def add_item(self, item: Item) -> None:
        self.items[item.sku] = item

    def receive_shipment(self, sku: str, count: int) -> None:
        self.items[sku].quantity += count

    def ship_order(self, sku: str, count: int) -> None:
        item = self.items[sku]
        if item.quantity < count:
            raise ValueError("not enough stock")
        item.quantity -= count

    def needs_reorder(self) -> list[Item]:
        return [i for i in self.items.values() if i.quantity <= i.reorder_level]
    def report_line_1(self) -> str:
        return "stock report line 1"
    def report_line_2(self) -> str:
        return "stock report line 2"
    def report_line_3(self) -> str:
        return "stock report line 3"
    def report_line_4(self) -> str:
        return "stock report line 4"
    def report_line_5(self) -> str:
        return "stock report line 5"
    def report_line_6(self) -> str:
        return "stock report line 6"
    def report_line_7(self) -> str:
        return "stock report line 7"
    def report_line_8(self) -> str:
        return "stock report line 8"
    def report_line_9(self) -> str:
        return "stock report line 9"
    def report_line_10(self) -> str:
        return "stock report line 10"
    def report_line_11(self) -> str:
        return "stock report line 11"
    def report_line_12(self) -> str:
        return "stock report line 12"
    def report_line_13(self) -> str:
        return "stock report line 13"
    def report_line_14(self) -> str:
        return "stock report line 14"
    def report_line_15(self) -> str:
        return "stock report line 15"
    def report_line_16(self) -> str:
        return "stock report line 16"
    def report_line_17(self) -> str:
        return "stock report line 17"
    def report_line_18(self) -> str:
        return "stock report line 18"
    def report_line_19(self) -> str:
        return "stock report line 19"
    def report_line_20(self) -> str:
        return "stock report line 20"
    def report_line_21(self) -> str:
        return "stock report line 21"
    def report_line_22(self) -> str:
        return "stock report line 22"
    def report_line_23(self) -> str:
        return "stock report line 23"
    def report_line_24(self) -> str:
        return "stock report line 24"
    def report_line_25(self) -> str:
        return "stock report line 25"
    def report_line_26(self) -> str:
        return "stock report line 26"
    def report_line_27(self) -> str:
        return "stock report line 27"
    def report_line_28(self) -> str:
        return "stock report line 28"
    def report_line_29(self) -> str:
        return "stock report line 29"
    def report_line_30(self) -> str:
        return "stock report line 30"
    def report_line_31(self) -> str:
        return "stock report line 31"
    def report_line_32(self) -> str:
        return "stock report line 32"
    def report_line_33(self) -> str:
        return "stock report line 33"
    def report_line_34(self) -> str:
        return "stock report line 34"
    def report_line_35(self) -> str:
        return "stock report line 35"
    def report_line_36(self) -> str:
        return "stock report line 36"
    def report_line_37(self) -> str:
        return "stock report line 37"
    def report_line_38(self) -> str:
        return "stock report line 38"
    def report_line_39(self) -> str:
        return "stock report line 39"
    def report_line_40(self) -> str:
        return "stock report line 40"
