from datetime import datetime

import pytest

from app.routers import dashboard, transfers, waste
from app.services import stock
from app.utils.time import LOCAL_TZ, now_local


def _item(client, name, quantity=100.0, unit="pcs", **extra):
    resp = client.post("/inventory/", json={"name": name, "unit": unit, "quantity": quantity, **extra})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _stock(client, item):
    return client.get(f"/inventory/{item['id']}").json()["quantity"]


def _menu_item(client, name, *ingredients):
    """ingredients: (item, quantity_needed)."""
    resp = client.post(
        "/menu-items/",
        json={"name": name, "ingredients": [{"item_id": i["id"], "quantity_needed": q} for i, q in ingredients]},
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


@pytest.fixture
def burgers(client):
    patty = _item(client, "Whopper Patties", 50)
    sesame = _item(client, "Sesame Buns", 40)
    regular = _item(client, "Regular Buns", 40)
    hamburger_patty = _item(client, "Hamburger Patties", 60)
    cheese = _item(client, "Cheese Slices", 200)
    whopper = _menu_item(client, "Whopper", (patty, 1), (sesame, 1))
    cheeseburger = _menu_item(client, "Cheeseburger", (hamburger_patty, 1), (regular, 1), (cheese, 1))
    return {
        "patty": patty, "sesame": sesame, "regular": regular, "hamburger_patty": hamburger_patty,
        "cheese": cheese, "whopper": whopper, "cheeseburger": cheeseburger,
    }


def _at(*args):
    return datetime(*args, tzinfo=LOCAL_TZ)


# --- Packaging ---


def test_item_packaging_is_optional_and_editable(client):
    patty = _item(client, "Whopper Patties", units_per_carton=48, units_per_subpackage=12)
    assert (patty["units_per_carton"], patty["units_per_subpackage"]) == (48, 12)
    fries = _item(client, "French Fries", unit="kg")
    assert (fries["units_per_carton"], fries["units_per_subpackage"]) == (None, None)

    resp = client.patch(f"/inventory/{fries['id']}", json={"units_per_carton": 6})
    assert resp.json()["units_per_carton"] == 6
    assert client.patch(f"/inventory/{fries['id']}", json={"units_per_carton": 0}).status_code == 422


# --- Menu items (bill of materials) ---


def test_menu_items_list_recipes(client, burgers):
    menu = client.get("/menu-items/").json()
    assert [m["name"] for m in menu] == ["Cheeseburger", "Whopper"]
    whopper = next(m for m in menu if m["name"] == "Whopper")
    assert whopper["ingredients"] == [
        {"item_id": burgers["patty"]["id"], "item_name": "Whopper Patties", "unit": "pcs", "quantity_needed": 1},
        {"item_id": burgers["sesame"]["id"], "item_name": "Sesame Buns", "unit": "pcs", "quantity_needed": 1},
    ]


@pytest.mark.parametrize(
    ("name", "ingredients", "expected"),
    [
        ("Whopper", "patty", 409),  # name taken
        ("Royal", [], 422),
        ("Royal", [{"item_id": 999, "quantity_needed": 1}], 400),
        ("Royal", "duplicate", 422),
        ("Royal", [{"item_id": 1, "quantity_needed": 0}], 422),
    ],
)
def test_invalid_menu_item(client, burgers, name, ingredients, expected):
    patty = {"item_id": burgers["patty"]["id"], "quantity_needed": 1}
    if isinstance(ingredients, str):
        ingredients = {"patty": [patty], "duplicate": [patty, patty]}[ingredients]
    resp = client.post("/menu-items/", json={"name": name, "ingredients": ingredients})
    assert resp.status_code == expected, resp.text
    assert len(client.get("/menu-items/").json()) == 2


# --- Waste: deconstructing menu items ---


def test_wasted_menu_items_deduct_their_ingredients(client, burgers):
    resp = client.post("/waste/", json={"items": [
        {"menu_item_id": burgers["whopper"]["id"], "quantity": 3, "reason": "Dropped"},
        {"menu_item_id": burgers["cheeseburger"]["id"], "quantity": 2},
        {"item_id": burgers["patty"]["id"], "quantity": 4, "reason": "Expired"},  # raw waste of the same item
    ]})
    assert resp.status_code == 201, resp.text
    entries = resp.json()

    assert sorted((e["item_name"], e["quantity"], e["reason"]) for e in entries) == [
        ("Cheese Slices", 2, "(From wasted Cheeseburger)"),
        ("Hamburger Patties", 2, "(From wasted Cheeseburger)"),
        ("Regular Buns", 2, "(From wasted Cheeseburger)"),
        ("Sesame Buns", 3, "Dropped (From wasted Whopper)"),
        ("Whopper Patties", 3, "Dropped (From wasted Whopper)"),
        ("Whopper Patties", 4, "Expired"),
    ]
    assert len({e["batch_id"] for e in entries}) == 1
    b = burgers
    assert [_stock(client, b[k]) for k in ("patty", "sesame", "hamburger_patty", "regular", "cheese")] == [
        50 - 3 - 4, 40 - 3, 60 - 2, 40 - 2, 200 - 2,
    ]


def test_menu_item_quantity_scales_recipe(client):
    lettuce = _item(client, "Lettuce", 5, unit="kg")
    salad = _menu_item(client, "Garden Salad", (lettuce, 0.15))
    entry = client.post("/waste/", json={"items": [{"menu_item_id": salad["id"], "quantity": 4}]}).json()[0]
    assert entry["quantity"] == pytest.approx(0.6)
    assert _stock(client, lettuce) == pytest.approx(4.4)


def test_long_reason_is_trimmed_to_fit_the_note(client, burgers):
    resp = client.post("/waste/", json={"items": [
        {"menu_item_id": burgers["whopper"]["id"], "quantity": 1, "reason": "x" * 500},
    ]})
    assert resp.status_code == 201, resp.text
    reason = resp.json()[0]["reason"]
    assert len(reason) == 500 and reason.endswith(" (From wasted Whopper)")


@pytest.mark.parametrize(
    "line",
    [
        {"quantity": 1},  # neither id
        {"item_id": "patty", "menu_item_id": "whopper", "quantity": 1},  # both ids
        {"menu_item_id": 999, "quantity": 1},  # unknown menu item
        {"menu_item_id": "whopper", "quantity": 0},
        "duplicate menu item",
    ],
)
def test_invalid_menu_waste_changes_nothing(client, burgers, line):
    whopper_line = {"menu_item_id": burgers["whopper"]["id"], "quantity": 1}
    if line == "duplicate menu item":
        lines = [whopper_line, whopper_line]
    else:
        ids = {"patty": burgers["patty"]["id"], "whopper": burgers["whopper"]["id"]}
        lines = [whopper_line, {k: ids.get(v, v) if isinstance(v, str) else v for k, v in line.items()}]

    resp = client.post("/waste/", json={"items": lines})
    assert resp.status_code in (400, 422), resp.text
    assert (_stock(client, burgers["patty"]), _stock(client, burgers["sesame"])) == (50, 40)
    assert client.get("/waste/").json() == []


def test_menu_waste_is_all_or_nothing(client, burgers, monkeypatch):
    calls = 0

    def adjust(db, item_id, delta):
        nonlocal calls
        calls += 1
        if calls == 2:  # fail on the second ingredient of the Whopper
            raise RuntimeError("simulated failure mid-batch")
        stock.adjust_stock(db, item_id, delta)

    monkeypatch.setattr(waste, "adjust_stock", adjust)
    with pytest.raises(RuntimeError):
        client.post("/waste/", json={"items": [{"menu_item_id": burgers["whopper"]["id"], "quantity": 2}]})
    monkeypatch.undo()

    assert (_stock(client, burgers["patty"]), _stock(client, burgers["sesame"])) == (50, 40)
    assert client.get("/waste/").json() == []


# --- Dashboard: "today" is the Berlin calendar day ---


def test_dashboard_waste_today_resets_at_berlin_midnight(client, monkeypatch):
    buns = _item(client, "Sesame Buns")
    monkeypatch.setattr(waste, "now_local", lambda: _at(2026, 10, 12, 23, 59, 59))
    client.post("/waste/", json={"items": [{"item_id": buns["id"], "quantity": 2}]})

    monkeypatch.setattr(dashboard, "now_local", lambda: _at(2026, 10, 12, 23, 59, 59, 999999))
    assert client.get("/dashboard/summary").json()["waste_today"]["entries"] == 1

    monkeypatch.setattr(dashboard, "now_local", lambda: _at(2026, 10, 13, 0, 0, 0))
    today = client.get("/dashboard/summary").json()["waste_today"]
    assert today == {"date": "2026-10-13", "entries": 0, "items": []}


def test_dashboard_today_spans_25_hours_on_dst_change(client, monkeypatch):
    buns = _item(client, "Sesame Buns")
    # 2026-10-25: clocks go back at 03:00, so 23:30 local is 22:30 UTC.
    monkeypatch.setattr(waste, "now_local", lambda: _at(2026, 10, 25, 23, 30))
    client.post("/waste/", json={"items": [{"item_id": buns["id"], "quantity": 1}]})
    monkeypatch.setattr(waste, "now_local", lambda: _at(2026, 10, 25, 0, 15))
    client.post("/waste/", json={"items": [{"item_id": buns["id"], "quantity": 1}]})

    monkeypatch.setattr(dashboard, "now_local", lambda: _at(2026, 10, 25, 12, 0))
    assert client.get("/dashboard/summary").json()["waste_today"]["entries"] == 2


# --- Archive ---


def _waste_at(client, monkeypatch, when, *lines):
    monkeypatch.setattr(waste, "now_local", lambda: when)
    resp = client.post("/waste/", json={"items": [{"item_id": i["id"], "quantity": q} for i, q in lines]})
    assert resp.status_code == 201, resp.text
    return resp.json()


def test_waste_archive_groups_batches_by_berlin_month(client, monkeypatch):
    buns = _item(client, "Sesame Buns")
    fries = _item(client, "French Fries", unit="kg")
    september = _waste_at(client, monkeypatch, _at(2026, 9, 30, 23, 30), (buns, 1))  # 21:30 UTC
    first = _waste_at(client, monkeypatch, _at(2026, 10, 1, 0, 30), (buns, 2), (fries, 1.5))  # Sep 30 in UTC
    second = _waste_at(client, monkeypatch, _at(2026, 10, 12, 22, 0), (fries, 3))

    october = client.get("/archive/waste?year=2026&month=10").json()
    assert [b["batch_id"] for b in october] == [second[0]["batch_id"], first[0]["batch_id"]]  # newest first
    assert [(line["item_name"], line["quantity"]) for line in october[1]["lines"]] == [
        ("Sesame Buns", 2), ("French Fries", 1.5),
    ]
    assert october[1]["created_at"] == "2026-10-01T00:30:00+02:00"

    sept = client.get("/archive/waste?year=2026&month=9").json()
    assert [b["batch_id"] for b in sept] == [september[0]["batch_id"]]
    assert client.get("/archive/waste?year=2026&month=8").json() == []


def test_archive_defaults_to_current_month(client):
    buns = _item(client, "Sesame Buns")
    booked = client.post("/waste/", json={"items": [{"item_id": buns["id"], "quantity": 1}]}).json()
    assert [b["batch_id"] for b in client.get("/archive/waste").json()] == [booked[0]["batch_id"]]


@pytest.mark.parametrize("query", ["year=2026", "month=10", "year=2026&month=13", "year=1999&month=1"])
def test_archive_month_validation(client, query):
    assert client.get(f"/archive/waste?{query}").status_code == 422


def test_transfer_archive_groups_lists(client, monkeypatch):
    buns = _item(client, "Sesame Buns")
    patties = _item(client, "Whopper Patties")
    monkeypatch.setattr(transfers, "now_local", lambda: _at(2026, 10, 5, 10, 0))
    first = client.post("/transfers/", json={"target_store_name": "Potsdam", "items": [
        {"item_id": buns["id"], "quantity": 10, "direction": "out"},
        {"item_id": patties["id"], "quantity": 5, "direction": "in"},
    ]}).json()
    second = client.post("/transfers/", json={"target_store_name": "Spandau", "items": [
        {"item_id": buns["id"], "quantity": 4, "direction": "in"},
    ]}).json()

    archive = client.get("/archive/transfers?year=2026&month=10").json()
    # Same timestamp: still two lists, told apart by batch id.
    assert {(b["batch_id"], b["target_store_name"], len(b["lines"])) for b in archive} == {
        (first[0]["batch_id"], "Potsdam", 2), (second[0]["batch_id"], "Spandau", 1),
    }
    assert [line["stock_change"] for line in next(b for b in archive if b["target_store_name"] == "Potsdam")["lines"]] == [-10, 5]


def test_audit_archive_shows_previous_and_new_quantities(client):
    buns = _item(client, "Sesame Buns", 40, is_daily_tracked=True)
    audit = client.post("/inventory/audit", json={
        "audit_type": "daily", "counts": [{"item_id": buns["id"], "counted_quantity": 37}],
    }).json()
    month = now_local()

    archive = client.get(f"/archive/audits?year={month.year}&month={month.month}").json()
    assert [(b["batch_id"], b["audit_type"]) for b in archive] == [(audit["id"], "daily")]
    assert archive[0]["lines"] == [{
        "item_id": buns["id"], "item_name": "Sesame Buns", "unit": "pcs",
        "expected_quantity": 40, "counted_quantity": 37, "variance": -3,
    }]
    assert client.get(f"/archive/audits?year={month.year}&month={month.month}&audit_type=weekly").json() == []
