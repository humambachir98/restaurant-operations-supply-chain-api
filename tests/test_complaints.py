import pytest


def _item(client, name="Sesame Buns", quantity=0, pack_size=30):
    resp = client.post(
        "/inventory/", json={"name": name, "unit": "pcs", "quantity": quantity, "pack_size": pack_size}
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _order(client, item, packs, receive=True):
    order = client.post("/purchase-orders/", json={"items": [{"item_id": item["id"], "packs": packs}]}).json()
    if receive:
        assert client.post(f"/purchase-orders/{order['id']}/receive").status_code == 200
    return order


def _complain(client, order, item, difference, notes="Squished buns due to bad pallets"):
    return client.post(
        "/complaints/",
        json={"order_id": order["id"], "item_id": item["id"], "quantity_difference": difference, "notes": notes},
    )


def _stock(client, item):
    return client.get(f"/inventory/{item['id']}").json()["quantity"]


@pytest.fixture
def delivered(client):
    """Buns: 4 packs of 30 delivered, so stock is 120."""
    buns = _item(client)
    order = _order(client, buns, 4)
    assert _stock(client, buns) == 120
    return order, buns


def test_complaint_changes_stock_only_when_approved(client, delivered):
    order, buns = delivered
    resp = _complain(client, order, buns, -30)
    assert resp.status_code == 201, resp.text
    complaint = resp.json()
    assert complaint | {"id": None, "created_at": None} == {
        "id": None, "created_at": None, "order_id": order["id"], "item_id": buns["id"],
        "item_name": "Sesame Buns", "unit": "pcs", "quantity_difference": -30,
        "notes": "Squished buns due to bad pallets", "status": "pending", "resolved_at": None,
    }
    assert _stock(client, buns) == 120

    approved = client.post(f"/complaints/{complaint['id']}/approve")
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert approved.json()["resolved_at"] is not None
    assert _stock(client, buns) == 90


def test_extra_goods_increase_stock(client, delivered):
    order, buns = delivered
    complaint = _complain(client, order, buns, 6, notes="Supplier sent 6 extra buns").json()
    client.post(f"/complaints/{complaint['id']}/approve")
    assert _stock(client, buns) == 126


def test_complaint_can_be_decided_only_once(client, delivered):
    order, buns = delivered
    complaint = _complain(client, order, buns, -30).json()
    assert client.post(f"/complaints/{complaint['id']}/approve").status_code == 200

    again = client.post(f"/complaints/{complaint['id']}/approve")
    assert again.status_code == 400
    assert "already been approved" in again.json()["detail"]
    assert client.post(f"/complaints/{complaint['id']}/reject").status_code == 400
    assert _stock(client, buns) == 90  # applied once


def test_rejecting_leaves_stock_alone(client, delivered):
    order, buns = delivered
    complaint = _complain(client, order, buns, -30).json()
    rejected = client.post(f"/complaints/{complaint['id']}/reject")
    assert rejected.json()["status"] == "rejected"
    assert _stock(client, buns) == 120
    assert client.post(f"/complaints/{complaint['id']}/approve").status_code == 400


def test_complaint_validation(client, delivered):
    order, buns = delivered
    fries = _item(client, "Fries", pack_size=15)
    pending = _order(client, buns, 1, receive=False)

    assert _complain(client, pending, buns, -5).status_code == 400  # not delivered yet
    assert _complain(client, order, fries, -5).status_code == 400  # not on this order
    assert _complain(client, {"id": 999}, buns, -5).status_code == 400
    assert _complain(client, order, buns, 0).status_code == 422
    assert _complain(client, order, buns, -5, notes="").status_code == 422

    too_much = _complain(client, order, buns, -121)
    assert too_much.status_code == 400
    assert "120 pcs" in too_much.json()["detail"]
    assert _complain(client, order, buns, -120).status_code == 201  # the whole delivery is fine


def test_list_complaints_by_status(client, delivered):
    order, buns = delivered
    first = _complain(client, order, buns, -10).json()
    second = _complain(client, order, buns, -5).json()
    client.post(f"/complaints/{first['id']}/approve")

    assert [c["id"] for c in client.get("/complaints/?status=pending").json()] == [second["id"]]
    assert [c["id"] for c in client.get("/complaints/?status=approved").json()] == [first["id"]]
    assert [c["id"] for c in client.get("/complaints/").json()] == [second["id"], first["id"]]  # newest first


def test_unknown_complaint_404(client):
    assert client.post("/complaints/999/approve").status_code == 404
    assert client.get("/complaints/999").status_code == 404


def test_item_with_complaints_cannot_be_deleted(client, delivered):
    order, buns = delivered
    _complain(client, order, buns, -5)
    assert client.delete(f"/inventory/{buns['id']}").status_code == 409
