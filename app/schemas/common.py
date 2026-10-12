from collections import Counter
from collections.abc import Iterable
from datetime import datetime
from typing import Annotated, Protocol

from pydantic import AfterValidator

from app.utils.time import to_local

# A datetime normalized to the restaurant's time zone. Naive input is taken as local time;
# input with an offset (e.g. "Z") is converted.
ZonedDateTime = Annotated[datetime, AfterValidator(to_local)]


class _HasItemId(Protocol):
    item_id: int


def ensure_unique_item_ids(lines: Iterable[_HasItemId]) -> None:
    ensure_unique((line.item_id for line in lines), "item_id")


def ensure_unique(ids: Iterable[int], field: str) -> None:
    counts = Counter(ids)
    duplicates = sorted(value for value, n in counts.items() if n > 1)
    if duplicates:
        raise ValueError(f"Each item may appear only once; duplicated {field}(s): {duplicates}")
