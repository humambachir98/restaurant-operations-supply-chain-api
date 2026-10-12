from datetime import date, timedelta

import pytest

from app.routers import transfers, waste
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


def _waste(client, item, quantity, reason="Dropped tray", **extra):
    return client.post("/waste/", json={"item_id": item["id"], "quantity": quantity, "reason": reason, **extra})


def _transfer(client, item, quantity, direction, store="Berlin Alexanderplatz"):
    return client.post(
        "/transfers/",
        json={"item_id": item["id"], "quantity": quantity, "direction": direction, "target_store_name": store},
    )


# --- Waste ---


def test_waste_deducts_stock_immediately(client):
    fries = _item(client, "French Fries", quantity=20, unit="kg")
    resp = _waste(client, fries, 2.5, reason="Held past 7 minutes")
    assert resp.status_code == 201, resp.text
    entry = resp.json()
    assert entry | {"id": None, "created_at": None} == {
        "id": None, "created_at": None, "item_id": fries["id"], "item_name": "French Fries", "unit": "kg",
        "quantity": 2.5, "audit_type": "daily", "reason": "Held past 7 minutes",
    }
    assert _stock(client, fries) == 17.5


@pytest.mark.parametrize("audit_type", ["daily", "weekly", "monthly"])
def test_waste_accepts_every_reporting_period(client, audit_type):
    buns = _item(client)
    resp = _waste(client, buns, 3, audit_type=audit_type)
    assert resp.status_code == 201, resp.text
    assert resp.json()["audit_type"] == audit_type
    assert [w["id"] for w in client.get(f"/waste/?audit_type={audit_type}").json()] == [resp.json()["id"]]


def test_waste_can_take_stock_negative(client):
    buns = _item(client, quantity=2)
    assert _waste(client, buns, 5).status_code == 201
    assert _stock(client, buns) == -3  # the next count corrects it


def test_waste_validation(client):
    buns = _item(client)
    assert _waste(client, buns, 0).status_code == 422
    assert _waste(client, buns, -1).status_code == 422
    assert _waste(client, buns, 1, reason="   ").status_code == 422
    assert _waste(client, buns, 1, audit_type="yearly").status_code == 422
    assert _waste(client, {"id": 999}, 1).status_code == 400
    assert _stock(client, buns) == 100
    assert client.get("/waste/").json() == []


def _failing_adjust(*args):
    raise RuntimeError("simulated failure")


def test_waste_is_atomic(client, monkeypatch):
    buns = _item(client)
    monkeypatch.setattr(waste, "adjust_stock", _failing_adjust)
    with pytest.raises(RuntimeError):
        _waste(client, buns, 5)
    monkeypatch.undo()

    assert client.get("/waste/").json() == []  # no log without the stock change
    assert _stock(client, buns) == 100


def test_waste_list_filters_by_berlin_day(client):
    buns = _item(client)
    first = _waste(client, buns, 1).json()
    second = _waste(client, buns, 2).json()
    today = now_local().date()

    assert [w["id"] for w in client.get(f"/waste/?on={today}").json()] == [second["id"], first["id"]]
    assert client.get(f"/waste/?on={today - timedelta(days=1)}").json() == []
    assert len(client.get("/waste/?limit=1").json()) == 1


def test_local_day_bounds_follow_dst():
    start, end = local_day_bounds(date(2026, 10, 25))  # clocks go back: a 25-hour day
    assert (start.isoformat(), end.isoformat()) == ("2026-10-25T00:00:00+02:00", "2026-10-26T00:00:00+01:00")
    assert elapsed(start, end) == timedelta(hours=25)


# --- Transfers ---


def test_transfers_move_stock_both_ways(client):
    buns = _item(client)

    out = _transfer(client, buns, 30, "out", store="  Berlin Alexanderplatz ")
    assert out.status_code == 201, out.text
    assert out.json() | {"id": None, "created_at": None} == {
        "id": None, "created_at": None, "item_id": buns["id"], "item_name": "Sesame Buns", "unit": "pcs",
        "quantity": 30, "direction": "out", "stock_change": -30, "target_store_name": "Berlin Alexanderplatz",
    }
    assert _stock(client, buns) == 70

    back = _transfer(client, buns, 12, "in", store="Potsdam Hbf")
    assert back.json()["stock_change"] == 12
    assert _stock(client, buns) == 82

    assert [t["direction"] for t in client.get("/transfers/").json()] == ["in", "out"]  # newest first
    assert [t["id"] for t in client.get("/transfers/?direction=out").json()] == [out.json()["id"]]


def test_transfer_validation(client):
    buns = _item(client)
    assert _transfer(client, buns, 5, "incoming").status_code == 422  # values are 'in' / 'out'
    assert _transfer(client, buns, 0, "in").status_code == 422
    assert _transfer(client, buns, 5, "in", store=" ").status_code == 422
    assert _transfer(client, {"id": 999}, 5, "in").status_code == 400
    assert _stock(client, buns) == 100


def test_transfer_is_atomic(client, monkeypatch):
    buns = _item(client)
    monkeypatch.setattr(transfers, "adjust_stock", _failing_adjust)
    with pytest.raises(RuntimeError):
        _transfer(client, buns, 5, "out")
    monkeypatch.undo()
    assert client.get("/transfers/").json() == []
    assert _stock(client, buns) == 100


def test_item_with_movements_cannot_be_deleted(client):
    buns = _item(client)
    _waste(client, buns, 1)
    resp = client.delete(f"/inventory/{buns['id']}")
    assert resp.status_code == 409
    assert "waste" in resp.json()["detail"]


# --- Dashboard summary ---


def test_dashboard_summary(client):
    fries = _item(client, "French Fries", quantity=-2, unit="kg", reorder_level=30)  # negative
    patties = _item(client, "Patties", quantity=50, reorder_level=120)  # low
    _item(client, "Lettuce", quantity=20, unit="kg", reorder_level=6)  # ok
    _item(client, "Napkins", quantity=0)  # reorder level 0: unmanaged, counts as ok

    _waste(client, fries, 1.5)
    _waste(client, fries, 0.5)
    _waste(client, patties, 4)
    for i in range(7):
        _transfer(client, patties, i + 1, "out" if i % 2 else "in")

    resp = client.get("/dashboard/summary")
    assert resp.status_code == 200, resp.text
    summary = resp.json()

    # Stock after the movements: fries -4 (negative), patties 50 - 4 + 4 = 50 (low).
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
