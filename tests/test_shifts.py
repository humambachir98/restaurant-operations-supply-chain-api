import pytest


def _employee(client, name="Ana", role="crew"):
    resp = client.post("/employees/", json={"name": name, "role": role})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _shift(client, employee_id, start, end):
    return client.post("/shifts/", json={"employee_id": employee_id, "start_time": start, "end_time": end})


# --- Roles ---


def test_roles_are_restricted(client):
    assert _employee(client, role="shift_manager")["role"] == "shift_manager"
    assert client.post("/employees/", json={"name": "Ben", "role": "cook"}).status_code == 422
    assert client.post("/employees/", json={"name": "Ben"}).status_code == 422  # role is required

    emp = _employee(client, "Ben")
    assert client.patch(f"/employees/{emp['id']}", json={"role": "manager"}).status_code == 422
    promoted = client.patch(f"/employees/{emp['id']}", json={"role": "shift_manager"})
    assert promoted.json()["role"] == "shift_manager"


# --- Duration (max 10 h, German Working Hours Act) ---


@pytest.mark.parametrize(
    ("start", "end", "expected_status"),
    [
        ("2026-10-07T08:00:00", "2026-10-07T18:00:00", 201),  # exactly 10 h
        ("2026-10-07T08:00:00", "2026-10-07T18:01:00", 422),  # 10 h 1 min
        ("2026-10-07T09:00:00", "2026-10-07T09:00:00", 422),  # zero length
        ("2026-10-07T17:00:00", "2026-10-07T09:00:00", 422),  # end before start
        # Night of 24->25 Oct 2026 clocks go back: 22:00-08:00 is 10 h on the wall clock but 11 h worked.
        ("2026-10-24T22:00:00", "2026-10-25T08:00:00", 422),
        # Night of 27->28 Mar 2027 clocks go forward: 22:00-09:00 looks like 11 h but is 10 h worked.
        ("2027-03-27T22:00:00", "2027-03-28T09:00:00", 201),
        # 06:00Z-16:00Z = 08:00-18:00 Berlin: offsets are honoured.
        ("2026-10-07T06:00:00Z", "2026-10-07T16:00:00Z", 201),
        ("2026-10-07T08:00:00", "2026-10-07T16:30:00Z", 422),  # 08:00 -> 18:30 Berlin
    ],
)
def test_shift_duration_limits(client, start, end, expected_status):
    emp = _employee(client)
    resp = _shift(client, emp["id"], start, end)
    assert resp.status_code == expected_status, resp.text


def test_update_enforces_duration_limit(client):
    emp = _employee(client)
    shift = _shift(client, emp["id"], "2026-10-07T09:00:00", "2026-10-07T17:00:00").json()
    resp = client.patch(f"/shifts/{shift['id']}", json={"end_time": "2026-10-07T19:30:00"})
    assert resp.status_code == 422
    assert "10:00:00" in resp.text
    resp = client.patch(f"/shifts/{shift['id']}", json={"start_time": "2026-10-07T07:00:00"})
    assert resp.status_code == 200  # 07:00-17:00 is exactly 10 h


# --- Overlap prevention ---


@pytest.mark.parametrize(
    ("start", "end"),
    [
        ("2026-10-07T12:00:00", "2026-10-07T20:00:00"),  # starts during the existing shift
        ("2026-10-07T06:00:00", "2026-10-07T10:00:00"),  # ends during it
        ("2026-10-07T10:00:00", "2026-10-07T12:00:00"),  # inside it
        ("2026-10-07T08:00:00", "2026-10-07T18:00:00"),  # covers it
        ("2026-10-07T09:00:00", "2026-10-07T17:00:00"),  # identical
        ("2026-10-07T14:00:00Z", "2026-10-07T18:00:00Z"),  # 16:00-20:00 Berlin
    ],
)
def test_overlapping_shift_is_rejected(client, start, end):
    emp = _employee(client)
    existing = _shift(client, emp["id"], "2026-10-07T09:00:00", "2026-10-07T17:00:00").json()

    resp = _shift(client, emp["id"], start, end)
    assert resp.status_code == 400
    assert f"id {existing['id']}" in resp.json()["detail"]
    assert len(client.get(f"/shifts/?employee_id={emp['id']}").json()) == 1


def test_non_overlapping_shifts_are_allowed(client):
    ana, ben = _employee(client, "Ana"), _employee(client, "Ben")
    assert _shift(client, ana["id"], "2026-10-07T09:00:00", "2026-10-07T17:00:00").status_code == 201
    # Back-to-back: ends exactly when the next one starts.
    assert _shift(client, ana["id"], "2026-10-07T17:00:00", "2026-10-07T21:00:00").status_code == 201
    assert _shift(client, ana["id"], "2026-10-07T05:00:00", "2026-10-07T09:00:00").status_code == 201
    # The same hours for a different employee.
    assert _shift(client, ben["id"], "2026-10-07T09:00:00", "2026-10-07T17:00:00").status_code == 201


def test_update_checks_overlap_but_ignores_itself(client):
    emp = _employee(client)
    morning = _shift(client, emp["id"], "2026-10-07T08:00:00", "2026-10-07T10:00:00").json()
    evening = _shift(client, emp["id"], "2026-10-07T16:00:00", "2026-10-07T22:00:00").json()

    # Moving within its own old slot is fine.
    resp = client.patch(f"/shifts/{morning['id']}", json={"end_time": "2026-10-07T12:00:00"})
    assert resp.status_code == 200, resp.text
    # Stretching into the evening shift is not.
    resp = client.patch(f"/shifts/{morning['id']}", json={"end_time": "2026-10-07T16:30:00"})
    assert resp.status_code == 400
    assert f"id {evening['id']}" in resp.json()["detail"]
    assert client.get(f"/shifts/{morning['id']}").json()["end_time"] == "2026-10-07T12:00:00+02:00"


def test_reassigning_a_shift_checks_the_new_employees_schedule(client):
    ana, ben = _employee(client, "Ana"), _employee(client, "Ben")
    _shift(client, ana["id"], "2026-10-07T09:00:00", "2026-10-07T17:00:00")
    bens = _shift(client, ben["id"], "2026-10-07T12:00:00", "2026-10-07T18:00:00").json()

    assert client.patch(f"/shifts/{bens['id']}", json={"employee_id": ana["id"]}).status_code == 400
    assert client.get(f"/shifts/{bens['id']}").json()["employee_id"] == ben["id"]
