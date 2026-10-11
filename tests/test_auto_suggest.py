from datetime import date

import pytest

from app.utils.delivery import DELIVERY_WEEKDAYS
from app.utils.restock import packs_to_order


def _item(client, name, quantity, reorder_level, unit="pcs", pack_size=1.0):
    resp = client.post(
        "/inventory/",
        json={
            "name": name, "unit": unit, "quantity": quantity,
            "reorder_level": reorder_level, "pack_size": pack_size,
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _setup_stock(client):
    return {
        "below": _item(client, "Patties", 50, 120, pack_size=48),     # 2*120 - 50 = 190 -> 4 boxes (192)
        "equal": _item(client, "Buns", 80, 80),                       # 2*80 - 80 = 80 -> 80 x 1
        "negative": _item(client, "Fries", -4.5, 30, "kg", pack_size=15),  # 2*30 + 4.5 = 64.5 -> 5 boxes (75 kg)
        "above": _item(client, "Lettuce", 20, 6, "kg"),
        "unmanaged": _item(client, "Napkins", 0, 0),         # reorder level 0: never flagged
    }


def test_low_stock_endpoint(client):
    _setup_stock(client)
    names = [i["name"] for i in client.get("/inventory/low-stock").json()]
    assert names == ["Buns", "Fries", "Patties"]
    # The list filter uses the same rule.
    assert [i["name"] for i in client.get("/inventory/?low_stock=true").json()] == names


def test_auto_suggest_uses_restock_formula(client):
    items = _setup_stock(client)
    resp = client.post("/purchase-orders/auto-suggest")
    assert resp.status_code == 200, resp.text
    draft = resp.json()

    lines = {line["name"]: line for line in draft["items"]}
    assert set(lines) == {"Buns", "Fries", "Patties"}
    assert lines["Patties"] == {
        "item_id": items["below"]["id"],
        "packs": 4,
        "name": "Patties",
        "unit": "pcs",
        "pack_size": 48,
        "quantity": 192,
        "needed": 190,
        "current_quantity": 50,
        "reorder_level": 120,
        "on_order": 0,
    }
    assert (lines["Buns"]["packs"], lines["Buns"]["quantity"]) == (80, 80)
    assert (lines["Fries"]["packs"], lines["Fries"]["quantity"], lines["Fries"]["needed"]) == (5, 75, 64.5)
    assert date.fromisoformat(draft["expected_delivery_date"]).weekday() in DELIVERY_WEEKDAYS


def test_auto_suggest_saves_nothing(client):
    _setup_stock(client)
    client.post("/purchase-orders/auto-suggest")
    assert client.get("/purchase-orders/").json() == []


def test_suggestion_can_be_submitted_as_is(client):
    _setup_stock(client)
    draft = client.post("/purchase-orders/auto-suggest").json()

    resp = client.post("/purchase-orders/", json={"items": draft["items"]})
    assert resp.status_code == 201, resp.text
    order = resp.json()
    assert order["status"] == "pending"
    assert sorted((i["packs"], i["quantity"]) for i in order["items"]) == [(4, 192), (5, 75), (80, 80)]


def test_pending_orders_reduce_suggestion(client):
    items = _setup_stock(client)
    client.post("/purchase-orders/", json={"items": [{"item_id": items["below"]["id"], "packs": 2}]})  # 96
    client.post("/purchase-orders/", json={"items": [{"item_id": items["equal"]["id"], "packs": 80}]})

    lines = {line["name"]: line for line in client.post("/purchase-orders/auto-suggest").json()["items"]}
    assert lines["Patties"]["on_order"] == 96  # pending orders count in stock units
    assert lines["Patties"]["needed"] == 94  # 190 - 96 already on order
    assert lines["Patties"]["packs"] == 2  # 94 / 48 rounded up
    assert "Buns" not in lines  # fully covered by the pending order
    assert lines["Fries"]["packs"] == 5


def test_received_orders_dont_count_as_on_order(client):
    items = _setup_stock(client)
    order = client.post("/purchase-orders/", json={"items": [{"item_id": items["above"]["id"], "packs": 5}]}).json()
    client.post(f"/purchase-orders/{order['id']}/receive")

    lines = client.post("/purchase-orders/auto-suggest").json()["items"]
    assert all(line["on_order"] == 0 for line in lines)


def test_auto_suggest_with_nothing_low(client):
    _item(client, "Lettuce", 20, 6, "kg")
    draft = client.post("/purchase-orders/auto-suggest").json()
    assert draft["items"] == []


@pytest.mark.parametrize(
    ("needed", "pack_size", "packs"),
    [
        (64.5, 15, 5),    # rounds up to whole boxes
        (60, 15, 4),      # exact multiple: no extra box
        (0.1, 15, 1),     # any shortfall needs a box
        (0, 15, 0),
        (-3, 15, 0),      # over-stocked
        (0.3, 0.1, 3),    # float noise (0.3 / 0.1 = 2.9999999999999996) doesn't change the result
        (3.0000000001, 1.5, 2),  # ...nor add a whole extra box
        (190, 1, 190),
    ],
)
def test_packs_to_order(needed, pack_size, packs):
    assert packs_to_order(needed, pack_size) == packs
