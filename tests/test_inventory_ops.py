from datetime import date, datetime

import pytest

from app.routers import purchase_orders
from app.utils.delivery import DELIVERY_WEEKDAYS, get_next_delivery_date
from app.utils.time import LOCAL_TZ


def _item(client, name, quantity=0.0, daily=False, pack_size=1.0):
    resp = client.post(
        "/inventory/",
        json={"name": name, "unit": "pcs", "quantity": quantity, "is_daily_tracked": daily, "pack_size": pack_size},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# --- Negative stock ---


def test_negative_stock_allowed_on_create_and_update(client):
    item = _item(client, "Buns", quantity=-4)
    assert item["quantity"] == -4

    resp = client.patch(f"/inventory/{item['id']}", json={"quantity": -12.5})
    assert resp.status_code == 200
    assert resp.json()["quantity"] == -12.5


# --- Daily items & audits ---


def test_daily_items_returns_only_key_items(client):
    _item(client, "Patties", daily=True)
    _item(client, "Napkins")
    _item(client, "Fries", daily=True)
    names = [i["name"] for i in client.get("/inventory/daily-items").json()]
    assert names == ["Fries", "Patties"]


def test_audit_sets_quantities_and_logs_variance(client):
    patties = _item(client, "Patties", quantity=100, daily=True)
    buns = _item(client, "Buns", quantity=-5, daily=True)  # negative after mis-rings
    untouched = _item(client, "Napkins", quantity=50)

    resp = client.post(
        "/inventory/audit",
        json={
            "audit_type": "daily",
            "counts": [
                {"item_id": patties["id"], "counted_quantity": 92},
                {"item_id": buns["id"], "counted_quantity": 10},
            ],
        },
    )
    assert resp.status_code == 201, resp.text
    audit = resp.json()
    assert audit["audit_type"] == "daily"
    lines = {line["item_id"]: line for line in audit["lines"]}
    assert lines[patties["id"]] == {
        "item_id": patties["id"], "expected_quantity": 100, "counted_quantity": 92, "variance": -8,
    }
    assert lines[buns["id"]]["variance"] == 15

    assert client.get(f"/inventory/{patties['id']}").json()["quantity"] == 92
    assert client.get(f"/inventory/{buns['id']}").json()["quantity"] == 10
    assert client.get(f"/inventory/{untouched['id']}").json()["quantity"] == 50

    history = client.get("/inventory/audits?audit_type=daily").json()
    assert [a["id"] for a in history] == [audit["id"]]
    assert client.get("/inventory/audits?audit_type=weekly").json() == []


@pytest.mark.parametrize(
    "body",
    [
        {"audit_type": "monthly", "counts": [{"item_id": 1, "counted_quantity": 1}]},
        {"audit_type": "weekly", "counts": []},
        {"audit_type": "weekly", "counts": [{"item_id": 1, "counted_quantity": -1}]},
        {"audit_type": "weekly", "counts": [{"item_id": 1, "counted_quantity": 1}, {"item_id": 1, "counted_quantity": 2}]},
    ],
    ids=["bad-type", "empty", "negative-count", "duplicate-item"],
)
def test_audit_validation(client, body):
    _item(client, "Patties")
    assert client.post("/inventory/audit", json=body).status_code == 422


def test_audit_with_unknown_item_changes_nothing(client):
    item = _item(client, "Patties", quantity=10)
    resp = client.post(
        "/inventory/audit",
        json={
            "audit_type": "weekly",
            "counts": [
                {"item_id": item["id"], "counted_quantity": 3},
                {"item_id": 999, "counted_quantity": 1},
            ],
        },
    )
    assert resp.status_code == 400
    assert client.get(f"/inventory/{item['id']}").json()["quantity"] == 10
    assert client.get("/inventory/audits").json() == []


def test_daily_audit_rejects_non_daily_items(client):
    patties = _item(client, "Patties", quantity=10, daily=True)
    napkins = _item(client, "Napkins", quantity=50)
    resp = client.post(
        "/inventory/audit",
        json={
            "audit_type": "daily",
            "counts": [
                {"item_id": patties["id"], "counted_quantity": 8},
                {"item_id": napkins["id"], "counted_quantity": 40},
            ],
        },
    )
    assert resp.status_code == 400
    assert str(napkins["id"]) in resp.json()["detail"]
    # Nothing applied, not even the valid line.
    assert client.get(f"/inventory/{patties['id']}").json()["quantity"] == 10
    assert client.get("/inventory/audits").json() == []

    # The same counts are fine in a weekly audit.
    weekly = client.post(
        "/inventory/audit",
        json={"audit_type": "weekly", "counts": [{"item_id": napkins["id"], "counted_quantity": 40}]},
    )
    assert weekly.status_code == 201


def test_item_referenced_by_audit_cannot_be_deleted(client):
    item = _item(client, "Patties", quantity=10)
    client.post("/inventory/audit", json={"audit_type": "weekly", "counts": [{"item_id": item["id"], "counted_quantity": 9}]})
    assert client.delete(f"/inventory/{item['id']}").status_code == 409


# --- Purchase orders ---


def _order(client, lines):
    return client.post("/purchase-orders/", json={"items": lines})


def test_create_order_is_pending_with_next_delivery_date(client):
    patties = _item(client, "Patties")
    resp = _order(client, [{"item_id": patties["id"], "packs": 40}])
    assert resp.status_code == 201, resp.text
    order = resp.json()

    assert order["status"] == "pending"
    assert order["received_at"] is None
    created = datetime.fromisoformat(order["created_at"])
    assert created.utcoffset() == LOCAL_TZ.utcoffset(created.replace(tzinfo=None))
    expected = date.fromisoformat(order["expected_delivery_date"])
    assert expected == get_next_delivery_date(created)
    assert expected.weekday() in DELIVERY_WEEKDAYS


@pytest.mark.parametrize(
    ("ordered_at", "expected_delivery"),
    [
        (datetime(2026, 10, 5, 13, 59, tzinfo=LOCAL_TZ), date(2026, 10, 6)),  # Mon before cutoff -> Tue
        (datetime(2026, 10, 5, 15, 0, tzinfo=LOCAL_TZ), date(2026, 10, 8)),   # Mon after cutoff -> Thu
    ],
)
def test_create_order_uses_berlin_clock_and_cutoff(client, monkeypatch, ordered_at, expected_delivery):
    monkeypatch.setattr(purchase_orders, "now_local", lambda: ordered_at)
    patties = _item(client, "Patties")
    order = _order(client, [{"item_id": patties["id"], "packs": 1}]).json()
    assert order["expected_delivery_date"] == expected_delivery.isoformat()
    assert datetime.fromisoformat(order["created_at"]) == ordered_at


def test_create_order_validation(client):
    patties = _item(client, "Patties")
    assert _order(client, []).status_code == 422
    assert _order(client, [{"item_id": patties["id"], "packs": 0}]).status_code == 422
    assert _order(client, [{"item_id": patties["id"], "packs": 1.5}]).status_code == 422  # whole packs only
    assert _order(client, [{"item_id": patties["id"], "packs": 1}, {"item_id": patties["id"], "packs": 2}]).status_code == 422
    assert _order(client, [{"item_id": 999, "packs": 1}]).status_code == 400


def test_receive_adds_stock_once(client):
    patties = _item(client, "Patties", quantity=-3)  # negative stock is topped up correctly
    fries = _item(client, "Fries", quantity=10, pack_size=2.5)
    order = _order(
        client,
        [{"item_id": patties["id"], "packs": 40}, {"item_id": fries["id"], "packs": 5}],  # 5 x 2.5 = 12.5
    ).json()

    resp = client.post(f"/purchase-orders/{order['id']}/receive")
    assert resp.status_code == 200, resp.text
    assert resp.json()["status"] == "received"
    assert resp.json()["received_at"] is not None
    assert client.get(f"/inventory/{patties['id']}").json()["quantity"] == 37
    assert client.get(f"/inventory/{fries['id']}").json()["quantity"] == 22.5

    again = client.post(f"/purchase-orders/{order['id']}/receive")
    assert again.status_code == 400
    assert client.get(f"/inventory/{patties['id']}").json()["quantity"] == 37

    assert [o["id"] for o in client.get("/purchase-orders/?status=received").json()] == [order["id"]]
    assert client.get("/purchase-orders/?status=pending").json() == []


def test_order_snapshots_pack_size(client):
    fries = _item(client, "Fries", pack_size=15)
    order = _order(client, [{"item_id": fries["id"], "packs": 3}]).json()
    assert order["items"][0] | {"id": None} == {
        "id": None, "item_id": fries["id"], "item_name": "Fries", "unit": "pcs",
        "packs": 3, "pack_size": 15, "quantity": 45,
    }

    # Changing the item's pack size later doesn't change what this order delivers.
    client.patch(f"/inventory/{fries['id']}", json={"pack_size": 10})
    client.post(f"/purchase-orders/{order['id']}/receive")
    assert client.get(f"/inventory/{fries['id']}").json()["quantity"] == 45


def test_pack_size_must_be_positive(client):
    assert client.post("/inventory/", json={"name": "X", "unit": "kg", "pack_size": 0}).status_code == 422
    item = _item(client, "Fries")
    assert item["pack_size"] == 1.0  # default
    assert client.patch(f"/inventory/{item['id']}", json={"pack_size": -5}).status_code == 422


def test_receive_unknown_order_404(client):
    assert client.post("/purchase-orders/999/receive").status_code == 404


def test_receive_rolls_back_if_a_stock_update_fails(client, monkeypatch):
    from sqlalchemy.orm import Session

    patties = _item(client, "Patties", quantity=5)
    fries = _item(client, "Fries", quantity=5)
    order = _order(
        client,
        [{"item_id": patties["id"], "packs": 10}, {"item_id": fries["id"], "packs": 10}],
    ).json()

    original_execute = Session.execute
    stock_updates = 0

    def failing_execute(self, statement, *args, **kwargs):
        nonlocal stock_updates
        if getattr(statement, "table", None) is not None and statement.table.name == "inventory_items":
            stock_updates += 1
            if stock_updates == 2:
                raise RuntimeError("simulated failure mid-delivery")
        return original_execute(self, statement, *args, **kwargs)

    monkeypatch.setattr(Session, "execute", failing_execute)
    with pytest.raises(RuntimeError):
        client.post(f"/purchase-orders/{order['id']}/receive")
    monkeypatch.undo()

    assert client.get(f"/purchase-orders/{order['id']}").json()["status"] == "pending"
    assert client.get(f"/inventory/{patties['id']}").json()["quantity"] == 5
    assert client.get(f"/inventory/{fries['id']}").json()["quantity"] == 5
