import pytest
from alembic import command
from sqlalchemy import create_engine, text

from app.database.migrations import alembic_config


def _employee(client, name="Ana", role="crew", **extra):
    resp = client.post("/employees/", json={"name": name, "role": role, **extra})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _shift(client, employee, start, end, **extra):
    return client.post(
        "/shifts/", json={"employee_id": employee["id"], "start_time": start, "end_time": end, **extra}
    )


def _time_off(client, employee, day, status="Urlaub"):
    return client.post("/time-off/", json={"employee_id": employee["id"], "date": day, "status": status})


def _week(client, start_date):
    resp = client.get("/schedule/weekly", params={"start_date": start_date})
    assert resp.status_code == 200, resp.text
    return resp.json()


# --- Role worked ---


def test_role_worked_defaults_to_the_employee_role_and_can_be_overridden(client):
    manager = _employee(client, "Sabine", "shift_manager")
    as_manager = _shift(client, manager, "2026-10-13T08:00:00", "2026-10-13T16:00:00").json()
    assert as_manager["role_worked"] == "shift_manager"

    as_crew = _shift(client, manager, "2026-10-14T08:00:00", "2026-10-14T16:00:00", role_worked="crew").json()
    assert as_crew["role_worked"] == "crew"

    reset = client.patch(f"/shifts/{as_crew['id']}", json={"role_worked": None})
    assert reset.json()["role_worked"] == "shift_manager"
    assert client.patch(f"/shifts/{as_crew['id']}", json={"role_worked": "boss"}).status_code == 422


# --- Time-off CRUD and conflicts ---


def test_time_off_crud(client):
    ana = _employee(client)
    resp = _time_off(client, ana, "2026-10-13", "Krank")
    assert resp.status_code == 201, resp.text
    entry = resp.json()
    assert entry == {"id": entry["id"], "employee_id": ana["id"], "date": "2026-10-13", "status": "Krank"}

    assert client.get(f"/time-off/{entry['id']}").json() == entry
    assert client.patch(f"/time-off/{entry['id']}", json={"status": "Frei"}).json()["status"] == "Frei"
    assert client.get("/time-off/", params={"start_date": "2026-10-14"}).json() == []
    assert [t["id"] for t in client.get("/time-off/", params={"employee_id": ana["id"]}).json()] == [entry["id"]]

    assert client.delete(f"/time-off/{entry['id']}").status_code == 204
    assert client.get(f"/time-off/{entry['id']}").status_code == 404


@pytest.mark.parametrize(
    "body",
    [
        {"date": "2026-10-13", "status": "Holiday"},  # not one of Urlaub / Krank / Frei
        {"date": "not-a-date", "status": "Urlaub"},
        {"status": "Urlaub"},
    ],
)
def test_time_off_validation(client, body):
    ana = _employee(client)
    assert client.post("/time-off/", json={"employee_id": ana["id"], **body}).status_code == 422


def test_time_off_needs_a_known_employee_and_one_status_per_day(client):
    ana = _employee(client)
    assert client.post("/time-off/", json={"employee_id": 999, "date": "2026-10-13", "status": "Frei"}).status_code == 400
    assert _time_off(client, ana, "2026-10-13").status_code == 201
    second = _time_off(client, ana, "2026-10-13", "Krank")
    assert second.status_code == 400
    assert "already marked 'Urlaub'" in second.json()["detail"]


def test_no_shift_on_a_day_off_and_no_day_off_on_a_shift_day(client):
    ana = _employee(client)
    assert _time_off(client, ana, "2026-10-13").status_code == 201
    resp = _shift(client, ana, "2026-10-13T08:00:00", "2026-10-13T16:00:00")
    assert resp.status_code == 400
    assert "marked 'Urlaub' on 2026-10-13" in resp.json()["detail"]

    shift = _shift(client, ana, "2026-10-14T08:00:00", "2026-10-14T16:00:00").json()
    assert _time_off(client, ana, "2026-10-14", "Krank").status_code == 400
    # Moving the shift onto the day off is rejected too.
    assert client.patch(f"/shifts/{shift['id']}", json={
        "start_time": "2026-10-13T08:00:00", "end_time": "2026-10-13T16:00:00",
    }).status_code == 400
    # So is moving the day off onto the shift.
    off = client.get("/time-off/").json()[0]
    assert client.patch(f"/time-off/{off['id']}", json={"date": "2026-10-14"}).status_code == 400


def test_night_shift_belongs_to_the_day_it_starts(client):
    ana = _employee(client)
    assert _shift(client, ana, "2026-10-13T22:00:00", "2026-10-14T06:00:00").status_code == 201
    assert _time_off(client, ana, "2026-10-14", "Frei").status_code == 201  # the next day is still free
    assert _time_off(client, ana, "2026-10-13", "Frei").status_code == 400


def test_deleting_an_employee_removes_their_time_off(client):
    ana = _employee(client)
    entry = _time_off(client, ana, "2026-10-13").json()
    assert client.delete(f"/employees/{ana['id']}").status_code == 204
    assert client.get(f"/time-off/{entry['id']}").status_code == 404


# --- Weekly roster ---


def test_weekly_schedule_matrix(client):
    crew_b = _employee(client, "Ben")
    manager = _employee(client, "Sabine", "shift_manager")
    crew_a = _employee(client, "aylin")
    _employee(client, "Gone", is_active=False)  # inactive, nothing scheduled: not listed

    morning = _shift(client, crew_a, "2026-10-13T08:00:00", "2026-10-13T16:00:00").json()
    night = _shift(client, manager, "2026-10-18T22:00:00", "2026-10-19T06:00:00").json()  # Sunday night
    _shift(client, crew_a, "2026-10-19T08:00:00", "2026-10-19T16:00:00")  # next week
    sick = _time_off(client, crew_b, "2026-10-15", "Krank").json()

    week = _week(client, "2026-10-15")  # a Thursday: the week runs Monday 12th to Sunday 18th
    assert (week["start_date"], week["end_date"]) == ("2026-10-12", "2026-10-18")
    assert week["days"] == [f"2026-10-{d}" for d in range(12, 19)]

    # Schichtführer first, then Mitarbeiter by name.
    assert [row["employee"]["name"] for row in week["rows"]] == ["Sabine", "aylin", "Ben"]
    rows = {row["employee"]["name"]: row["days"] for row in week["rows"]}
    assert all(len(days) == 7 for days in rows.values())

    tuesday = rows["aylin"][1]
    assert tuesday["date"] == "2026-10-13"
    assert [s["id"] for s in tuesday["shifts"]] == [morning["id"]]
    assert tuesday["shifts"][0]["start_time"] == "2026-10-13T08:00:00+02:00"
    assert tuesday["time_off"] is None
    assert sum(len(day["shifts"]) for day in rows["aylin"]) == 1  # Monday 19th is next week

    assert rows["Ben"][3]["time_off"] == sick
    assert [s["id"] for s in rows["Sabine"][6]["shifts"]] == [night["id"]]


def test_weekly_schedule_lists_inactive_employees_with_entries(client):
    gone = _employee(client, "Gone", is_active=False)
    _time_off(client, gone, "2026-10-13", "Urlaub")
    assert [row["employee"]["name"] for row in _week(client, "2026-10-12")["rows"]] == ["Gone"]
    assert _week(client, "2026-10-19")["rows"] == []


def test_weekly_schedule_across_the_dst_change(client):
    # Clocks go back on Sunday 25 Oct 2026: the 25-hour day still ends at midnight Berlin time.
    ana = _employee(client)
    late = _shift(client, ana, "2026-10-25T23:30:00", "2026-10-26T07:30:00").json()  # 23:30 CET on Sunday
    week = _week(client, "2026-10-25")
    assert week["start_date"] == "2026-10-19"
    assert [s["id"] for s in week["rows"][0]["days"][6]["shifts"]] == [late["id"]]
    assert all(day["shifts"] == [] for day in _week(client, "2026-10-26")["rows"][0]["days"])


def test_weekly_schedule_needs_a_valid_start_date(client):
    assert client.get("/schedule/weekly").status_code == 422
    assert client.get("/schedule/weekly", params={"start_date": "2026-13-01"}).status_code == 422


# --- Migration ---


def test_role_worked_migration_backfills_existing_shifts(tmp_path):
    url = f"sqlite:///{(tmp_path / 'roster.db').as_posix()}"
    config = alembic_config(url)
    command.upgrade(config, "2152315bd420")  # before time-off / role_worked

    engine = create_engine(url)
    with engine.begin() as conn:
        conn.execute(text(
            "INSERT INTO employees (id, name, role, is_active) VALUES (1, 'A', 'shift_manager', 1), (2, 'B', 'crew', 1)"
        ))
        conn.execute(text(
            "INSERT INTO shifts (id, employee_id, start_time, end_time) VALUES "
            "(1, 1, '2026-10-13 06:00:00', '2026-10-13 14:00:00'), (2, 2, '2026-10-13 06:00:00', '2026-10-13 14:00:00')"
        ))

    command.upgrade(config, "head")
    with engine.connect() as conn:
        assert conn.execute(text("SELECT role_worked FROM shifts ORDER BY id")).scalars().all() == [
            "shift_manager", "crew",
        ]
    engine.dispose()
