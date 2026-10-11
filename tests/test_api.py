def test_health(client):
    assert client.get("/health").json() == {"status": "ok"}


def test_employee_and_shift_flow(client):
    emp = client.post("/employees/", json={"name": "Ana", "role": "crew"}).json()
    resp = client.post(
        "/shifts/",
        json={
            "employee_id": emp["id"],
            "start_time": "2026-10-07T09:00:00",
            "end_time": "2026-10-07T17:00:00",
        },
    )
    assert resp.status_code == 201
    shifts = client.get(f"/shifts/?employee_id={emp['id']}").json()
    assert [s["id"] for s in shifts] == [resp.json()["id"]]


def test_shift_rejects_end_before_start(client):
    emp = client.post("/employees/", json={"name": "Ben", "role": "crew"}).json()
    resp = client.post(
        "/shifts/",
        json={
            "employee_id": emp["id"],
            "start_time": "2026-10-07T17:00:00",
            "end_time": "2026-10-07T09:00:00",
        },
    )
    assert resp.status_code == 422


def test_low_stock_filter(client):
    client.post("/inventory/", json={"name": "Flour", "unit": "kg", "quantity": 2, "reorder_level": 5})
    client.post("/inventory/", json={"name": "Rice", "unit": "kg", "quantity": 20, "reorder_level": 5})
    low = client.get("/inventory/?low_stock=true").json()
    assert [i["name"] for i in low] == ["Flour"]
