"""Warehouse stock kept in memory."""

import functools
from dataclasses import dataclass

MAX_ITEMS = 1000


@dataclass
class Item:
    """One stock keeping unit."""

    sku: str
    quantity: int = 0


def log_call(fn):
    """Decorator that records each call."""

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        return fn(*args, **kwargs)

    return wrapper


class Inventory:
    """Items by sku."""

    def __init__(self) -> None:
        self.items: dict[str, Item] = {}

    @log_call
    def add(self, item: Item) -> None:
        """Add an item to the inventory, or raise when the inventory is full."""
        if len(self.items) >= MAX_ITEMS:
            raise ValueError("inventory full")
        self.items[item.sku] = item

    def remove(self, sku: str) -> Item:
        """Take a stock unit out by sku."""
        return self.items.pop(sku)

    def count(self) -> int:
        return len(self.items)


def restock(inventory: Inventory, sku: str, amount: int) -> None:
    """Raise the quantity of one sku after a delivery."""
    inventory.items[sku].quantity += amount
