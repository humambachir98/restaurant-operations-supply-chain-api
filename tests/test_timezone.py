from datetime import datetime

from app.utils.time import LOCAL_TZ


def _employee(client):
    return client.post("/employees/", json={"name": "Ana", "role": "crew"}).json()


def _shift(client, employee_id, start, end):
    return client.post("/shifts/", json={"employee_id": employee_id, "start_time": start, "end_time": end})


def test_naive_shift_times_are_berlin_local(client):
    emp = _employee(client)
    summer = _shift(client, emp["id"], "2026-10-07T09:00:00", "2026-10-07T17:00:00").json()
    assert summer["start_time"] == "2026-10-07T09:00:00+02:00"  # CEST

    winter = _shift(client, emp["id"], "2026-12-01T09:00:00", "2026-12-01T17:00:00").json()
    assert winter["start_time"] == "2026-12-01T09:00:00+01:00"  # CET


def test_utc_shift_times_are_converted_to_berlin(client):
    emp = _employee(client)
    shift = _shift(client, emp["id"], "2026-10-07T07:00:00Z", "2026-10-07T15:00:00Z").json()
    assert shift["start_time"] == "2026-10-07T09:00:00+02:00"
    assert shift["end_time"] == "2026-10-07T17:00:00+02:00"
    # Reading it back from the database gives the same Berlin time.
    assert client.get(f"/shifts/{shift['id']}").json()["start_time"] == "2026-10-07T09:00:00+02:00"


def test_shift_spanning_dst_change_keeps_real_duration(client):
    # Night of 24->25 Oct 2026 clocks go back 03:00 -> 02:00: 22:00 to 06:00 is 9 real hours.
    emp = _employee(client)
    shift = _shift(client, emp["id"], "2026-10-24T22:00:00", "2026-10-25T06:00:00").json()
    start = datetime.fromisoformat(shift["start_time"])
    end = datetime.fromisoformat(shift["end_time"])
    assert (end - start).total_seconds() == 9 * 3600


def test_shift_update_compares_mixed_naive_and_aware_times(client):
    emp = _employee(client)
    shift = _shift(client, emp["id"], "2026-10-07T09:00:00", "2026-10-07T17:00:00").json()
    # New end of 06:00 UTC = 08:00 Berlin, before the 09:00 start -> rejected.
    bad = client.patch(f"/shifts/{shift['id']}", json={"end_time": "2026-10-07T06:00:00Z"})
    assert bad.status_code == 422
    ok = client.patch(f"/shifts/{shift['id']}", json={"end_time": "2026-10-07T16:00:00Z"})
    assert ok.status_code == 200
    assert ok.json()["end_time"] == "2026-10-07T18:00:00+02:00"


def test_local_tz_is_berlin():
    assert str(LOCAL_TZ) == "Europe/Berlin"
