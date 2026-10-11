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


def test_cors_allows_vite_dev_server(client):
    for origin in ("http://localhost:5173", "http://127.0.0.1:5173"):
        resp = client.options(
            "/inventory/daily-items",
            headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
        )
        assert resp.headers["access-control-allow-origin"] == origin

    resp = client.get("/health", headers={"Origin": "http://evil.example"})
    assert "access-control-allow-origin" not in resp.headers
