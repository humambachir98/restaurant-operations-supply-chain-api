import math


def suggested_order_quantity(quantity: float, reorder_level: float, on_order: float = 0) -> float:
    """How much to order to restock an item to twice its reorder level, in stock units.

    Baseline is `reorder_level * 2 - quantity`, minus anything already on order that hasn't
    arrived yet. Negative stock (mis-rings, unrecorded waste) raises the suggestion accordingly.
    Rounded to 3 decimals to hide float noise; may be <= 0 when nothing is needed.
    """
    return round(reorder_level * 2 - quantity - on_order, 3)


def packs_to_order(needed: float, pack_size: float) -> int:
    """Whole packs covering `needed` units, rounded up. E.g. 64.5 kg in 15 kg boxes -> 5 boxes.

    0 when nothing is needed. The division is rounded first so float noise (e.g. 30.0000001 / 15)
    doesn't add a whole extra pack.
    """
    if needed <= 0:
        return 0
    return math.ceil(round(needed / pack_size, 6))
