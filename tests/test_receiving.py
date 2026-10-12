from datetime import UTC, date, datetime, time

import pytest

from app.config import settings
from app.routers import purchase_orders
from app.scheduler import AUTO_RECEIVE_JOB_ID, create_scheduler
from app.services import receiving
from app.services.receiving import catch_up_date
from app.utils.time import LOCAL_TZ


def _berlin(*args):
    return datetime(*args, tzinfo=LOCAL_TZ)


@pytest.fixture
def clock(monkeypatch):
    """Set the Berlin clock for order creation, the trigger and the received_at stamp."""
    def set_now(now):
        monkeypatch.setattr(purchase_orders, "now_local", lambda: now)
        monkeypatch.setattr(receiving, "now_local", lambda: now)
    return set_now


def _item(client, name, quantity=0):
    resp = client.post("/inventory/", json={"name": name, "unit": "pcs", "quantity": quantity})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _order(client, item, packs):
    resp = client.post("/purchase-orders/", json={"items": [{"item_id": item["id"], "packs": packs}]})
    assert resp.status_code == 201, resp.text
    return resp.json()


def _stock(client, item):
    return client.get(f"/inventory/{item['id']}").json()["quantity"]


def _trigger(client):
    resp = client.post("/purchase-orders/trigger-auto-receive")
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_trigger_receives_orders_due_today_only(client, clock):
    buns = _item(client, "Buns", quantity=-5)
    clock(_berlin(2026, 10, 5, 10))  # Monday morning -> Tuesday delivery
    tuesday = _order(client, buns, 10)
    clock(_berlin(2026, 10, 7, 10))  # Wednesday morning -> Thursday delivery
    thursday = _order(client, buns, 20)
    assert (tuesday["expected_delivery_date"], thursday["expected_delivery_date"]) == ("2026-10-06", "2026-10-08")

    clock(_berlin(2026, 10, 6, 6, 0))
    assert _trigger(client) == {"as_of": "2026-10-06", "received_order_ids": [tuesday["id"]]}
    assert _stock(client, buns) == 5  # -5 + 10

    received = client.get(f"/purchase-orders/{tuesday['id']}").json()
    assert received["status"] == "received"
    assert datetime.fromisoformat(received["received_at"]) == _berlin(2026, 10, 6, 6, 0)
    assert client.get(f"/purchase-orders/{thursday['id']}").json()["status"] == "pending"


def test_trigger_is_idempotent(client, clock):
    buns = _item(client, "Buns")
    clock(_berlin(2026, 10, 5, 10))
    order = _order(client, buns, 10)

    clock(_berlin(2026, 10, 6, 6, 0))
    assert _trigger(client)["received_order_ids"] == [order["id"]]
    assert _trigger(client)["received_order_ids"] == []
    assert _stock(client, buns) == 10
    # The manual receive endpoint agrees it's done.
    assert client.post(f"/purchase-orders/{order['id']}/receive").status_code == 400


def test_trigger_catches_up_on_missed_deliveries(client, clock):
    buns = _item(client, "Buns")
    clock(_berlin(2026, 10, 5, 10))
    missed = _order(client, buns, 10)  # due Tuesday, but nothing ran that day
    clock(_berlin(2026, 10, 7, 10))
    today = _order(client, buns, 20)  # due Thursday

    clock(_berlin(2026, 10, 8, 6, 0))
    assert _trigger(client)["received_order_ids"] == [missed["id"], today["id"]]
    assert _stock(client, buns) == 30


def test_one_failing_order_does_not_block_the_others(client, clock, monkeypatch):
    buns = _item(client, "Buns")
    clock(_berlin(2026, 10, 5, 10))
    broken = _order(client, buns, 10)
    fine = _order(client, buns, 20)

    original = receiving.mark_received

    def mark_received(db, order):
        if order.id == broken["id"]:
            original(db, order)  # partially applied, then fails: must be rolled back
            raise RuntimeError("simulated failure")
        return original(db, order)

    monkeypatch.setattr(receiving, "mark_received", mark_received)
    clock(_berlin(2026, 10, 6, 6, 0))
    assert _trigger(client)["received_order_ids"] == [fine["id"]]
    assert _stock(client, buns) == 20
    assert client.get(f"/purchase-orders/{broken['id']}").json()["status"] == "pending"


@pytest.mark.parametrize(
    ("now", "expected"),
    [
        (_berlin(2026, 10, 8, 5, 59), date(2026, 10, 7)),  # before 06:00: today's delivery isn't due yet
        (_berlin(2026, 10, 8, 6, 0), date(2026, 10, 8)),
        (_berlin(2026, 10, 8, 23, 0), date(2026, 10, 8)),
        (datetime(2026, 10, 8, 4, 30, tzinfo=UTC), date(2026, 10, 8)),  # = 06:30 Berlin
    ],
)
def test_catch_up_date(now, expected):
    assert catch_up_date(now, time(6, 0)) == expected


def test_scheduler_runs_daily_at_six_berlin_time_across_dst():
    scheduler = create_scheduler()  # not started
    job = scheduler.get_job(AUTO_RECEIVE_JOB_ID)
    assert job is not None
    assert settings.auto_receive_time == time(6, 0)

    trigger = job.trigger
    # Clocks go back on 25 Oct 2026: the next run is still 06:00 local, now at UTC+1.
    after = _berlin(2026, 10, 24, 7, 0)
    next_run = trigger.get_next_fire_time(None, after)
    assert next_run.replace(tzinfo=None) == datetime(2026, 10, 25, 6, 0)
    assert next_run.utcoffset().total_seconds() == 3600
