from datetime import date, timedelta

import pytest

from app.routers import transfers, waste
from app.services import stock
from app.utils.time import elapsed, local_day_bounds, now_local


def _item(client, name="Sesame Buns", quantity=100.0, unit="pcs", reorder_level=0, daily=False):
    resp = client.post(
        "/inventory/",
        json={
            "name": name, "unit": unit, "quantity": quantity,
            "reorder_level": reorder_level, "is_daily_tracked": daily,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _stock(client, item):
    return client.get(f"/inventory/{item['id']}").json()["quantity"]


def _book_waste(client, *lines):
    """lines: (item, quantity) or (item, quantity, reason)."""
    items = [
        {"item_id": line[0]["id"], "quantity": line[1], **({"reason": line[2]} if len(line) > 2 else {})}
        for line in lines
    ]
    return client.post("/waste/", json={"items": items})


def _transfer(client, *lines, store="Berlin Alexanderplatz"):
    """lines: (item, quantity, direction)."""
    items = [{"item_id": item["id"], "quantity": qty, "direction": direction} for item, qty, direction in lines]
    return client.post("/transfers/", json={"target_store_name": store, "items": items})


def _fail_on_second_adjustment(monkeypatch, module):
    """Make the second stock update of a batch fail, after the first one has run."""
    calls = 0

    def adjust(db, item_id, delta):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise RuntimeError("simulated failure mid-batch")
        stock.adjust_stock(db, item_id, delta)

    monkeypatch.setattr(module, "adjust_stock", adjust)


# --- Waste (batch) ---


def test_waste_batch_deducts_every_line(client):
    fries = _item(client, "French Fries", quantity=20, unit="kg")
    buns = _item(client)
    lettuce = _item(client, "Lettuce", quantity=5, unit="kg")

    resp = _book_waste(client, (fries, 2.5, "Held past 7 minutes"), (buns, 12))
    assert resp.status_code == 201, resp.text
    entries = resp.json()
    assert [e | {"id": None, "created_at": None} for e in entries] == [
        {"id": None, "created_at": None, "item_id": fries["id"], "item_name": "French Fries", "unit": "kg",
         "quantity": 2.5, "reason": "Held past 7 minutes"},
        {"id": None, "created_at": None, "item_id": buns["id"], "item_name": "Sesame Buns", "unit": "pcs",
         "quantity": 12, "reason": None},
    ]
    assert entries[0]["created_at"] == entries[1]["created_at"]  # one booking, one timestamp
    assert (_stock(client, fries), _stock(client, buns), _stock(client, lettuce)) == (17.5, 88, 5)


def test_waste_has_no_audit_type(client):
    buns = _item(client)
    entry = _book_waste(client, (buns, 1)).json()[0]
    assert "audit_type" not in entry


def test_blank_reason_is_stored_as_none(client):
    buns = _item(client)
    assert _book_waste(client, (buns, 1, "   ")).json()[0]["reason"] is None


def test_waste_can_take_stock_negative(client):
    buns = _item(client, quantity=2)
    assert _book_waste(client, (buns, 5)).status_code == 201
    assert _stock(client, buns) == -3  # the next count corrects it


@pytest.mark.parametrize(
    "lines",
    [
        [],  # empty booking
        [{"quantity": 1}],  # no item
        "zero",
        "negative",
        "duplicate",
        "unknown item",
        "reason too long",
    ],
)
def test_invalid_waste_batch_changes_nothing(client, lines):
    buns = _item(client)
    fries = _item(client, "French Fries", quantity=20, unit="kg")
    good = {"item_id": fries["id"], "quantity": 1}
    bad = {
        "zero": {"item_id": buns["id"], "quantity": 0},
        "negative": {"item_id": buns["id"], "quantity": -1},
        "duplicate": {"item_id": fries["id"], "quantity": 2},
        "unknown item": {"item_id": 999, "quantity": 1},
        "reason too long": {"item_id": buns["id"], "quantity": 1, "reason": "x" * 501},
    }
    payload = lines if isinstance(lines, list) else [good, bad[lines]]

    resp = client.post("/waste/", json={"items": payload})
    assert resp.status_code in (400, 422), resp.text
    assert (_stock(client, buns), _stock(client, fries)) == (100, 20)
    assert client.get("/waste/").json() == []


def test_waste_batch_is_all_or_nothing(client, monkeypatch):
    buns = _item(client)
    fries = _item(client, "French Fries", quantity=20, unit="kg")
    _fail_on_second_adjustment(monkeypatch, waste)

    with pytest.raises(RuntimeError):
        _book_waste(client, (buns, 10), (fries, 2))
    monkeypatch.undo()

    assert (_stock(client, buns), _stock(client, fries)) == (100, 20)  # first line rolled back too
    assert client.get("/waste/").json() == []


def test_waste_list_filters_by_berlin_day(client):
    buns = _item(client)
    fries = _item(client, "French Fries", quantity=20, unit="kg")
    first = _book_waste(client, (buns, 1)).json()
    second = _book_waste(client, (fries, 2)).json()
    today = now_local().date()

    assert [w["id"] for w in client.get(f"/waste/?on={today}").json()] == [second[0]["id"], first[0]["id"]]
    assert client.get(f"/waste/?on={today - timedelta(days=1)}").json() == []
    assert len(client.get("/waste/?limit=1").json()) == 1


def test_local_day_bounds_follow_dst():
    start, end = local_day_bounds(date(2026, 10, 25))  # clocks go back: a 25-hour day
    assert (start.isoformat(), end.isoformat()) == ("2026-10-25T00:00:00+02:00", "2026-10-26T00:00:00+01:00")
    assert elapsed(start, end) == timedelta(hours=25)


# --- Transfers (batch) ---


def test_transfer_list_moves_stock_both_ways(client):
    buns = _item(client)
    patties = _item(client, "Patties", quantity=50)

    resp = _transfer(client, (buns, 30, "out"), (patties, 12, "in"), store="  Berlin Alexanderplatz ")
    assert resp.status_code == 201, resp.text
    lines = resp.json()
    assert [line | {"id": None, "created_at": None} for line in lines] == [
        {"id": None, "created_at": None, "item_id": buns["id"], "item_name": "Sesame Buns", "unit": "pcs",
         "quantity": 30, "direction": "out", "stock_change": -30, "target_store_name": "Berlin Alexanderplatz"},
        {"id": None, "created_at": None, "item_id": patties["id"], "item_name": "Patties", "unit": "pcs",
         "quantity": 12, "direction": "in", "stock_change": 12, "target_store_name": "Berlin Alexanderplatz"},
    ]
    assert (_stock(client, buns), _stock(client, patties)) == (70, 62)

    assert [t["direction"] for t in client.get("/transfers/").json()] == ["in", "out"]  # newest (highest id) first
    assert [t["item_id"] for t in client.get("/transfers/?direction=out").json()] == [buns["id"]]


@pytest.mark.parametrize(
    ("store", "line_overrides"),
    [
        ("Potsdam", {"direction": "incoming"}),  # values are 'in' / 'out'
        ("Potsdam", {"quantity": 0}),
        ("Potsdam", {"item_id": 999}),
        ("Potsdam", "duplicate"),
        ("   ", {}),  # store applies to the whole batch and is required
    ],
)
def test_invalid_transfer_list_changes_nothing(client, store, line_overrides):
    buns = _item(client)
    patties = _item(client, "Patties", quantity=50)
    first = {"item_id": buns["id"], "quantity": 5, "direction": "out"}
    second = (
        {"item_id": buns["id"], "quantity": 3, "direction": "in"}
        if line_overrides == "duplicate"
        else {"item_id": patties["id"], "quantity": 5, "direction": "out", **line_overrides}
    )
    resp = client.post("/transfers/", json={"target_store_name": store, "items": [first, second]})
    assert resp.status_code in (400, 422), resp.text
    assert (_stock(client, buns), _stock(client, patties)) == (100, 50)
    assert client.get("/transfers/").json() == []


def test_empty_transfer_list_is_rejected(client):
    assert client.post("/transfers/", json={"target_store_name": "Potsdam", "items": []}).status_code == 422


def test_transfer_list_is_all_or_nothing(client, monkeypatch):
    buns = _item(client)
    patties = _item(client, "Patties", quantity=50)
    _fail_on_second_adjustment(monkeypatch, transfers)

    with pytest.raises(RuntimeError):
        _transfer(client, (buns, 30, "out"), (patties, 12, "in"))
    monkeypatch.undo()

    assert (_stock(client, buns), _stock(client, patties)) == (100, 50)
    assert client.get("/transfers/").json() == []


def test_item_with_movements_cannot_be_deleted(client):
    buns = _item(client)
    _book_waste(client, (buns, 1))
    resp = client.delete(f"/inventory/{buns['id']}")
    assert resp.status_code == 409
    assert "waste" in resp.json()["detail"]


# --- Dashboard summary ---


def test_dashboard_summary(client):
    fries = _item(client, "French Fries", quantity=-2, unit="kg", reorder_level=30)  # negative
    patties = _item(client, "Patties", quantity=50, reorder_level=120)  # low
    _item(client, "Lettuce", quantity=20, unit="kg", reorder_level=6)  # ok
    _item(client, "Napkins", quantity=0)  # reorder level 0: unmanaged, counts as ok

    _book_waste(client, (fries, 1.5), (patties, 4))
    _book_waste(client, (fries, 0.5))
    for i in range(7):
        _transfer(client, (patties, i + 1, "out" if i % 2 else "in"))

    resp = client.get("/dashboard/summary")
    assert resp.status_code == 200, resp.text
    summary = resp.json()

    # Stock after the movements: fries -4 (negative), patties 50 - 4 + 16 - 12 = 50 (low).
    assert summary["stock_health"] == {"total_items": 4, "ok": 2, "low": 1, "negative": 1}
    waste_today = summary["waste_today"]
    assert waste_today["date"] == now_local().date().isoformat()
    assert waste_today["entries"] == 3
    assert [(w["item_name"], w["quantity"], w["entries"]) for w in waste_today["items"]] == [
        ("Patties", 4, 1),
        ("French Fries", 2, 2),
    ]
    assert [t["quantity"] for t in summary["recent_transfers"]] == [7, 6, 5, 4, 3]  # newest 5
    assert summary["pending_deliveries"] == 0
    assert summary["pending_complaints"] == 0


def test_dashboard_summary_counts_open_work(client):
    buns = _item(client)
    client.post("/purchase-orders/", json={"items": [{"item_id": buns["id"], "packs": 2}]})
    summary = client.get("/dashboard/summary").json()
    assert summary["pending_deliveries"] == 1
    assert summary["waste_today"] == {"date": now_local().date().isoformat(), "entries": 0, "items": []}


def test_dashboard_summary_empty(client):
    assert client.get("/dashboard/summary").json()["stock_health"] == {"total_items": 0, "ok": 0, "low": 0, "negative": 0}
