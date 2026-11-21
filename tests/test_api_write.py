"""Write API contract: run validation now, create rule, enable/disable rule."""

from __future__ import annotations

from datacheck import repositories as repo


def test_run_validation_now_appends_a_run_and_becomes_latest(auth_client, dataset_ids):
    dataset_id = dataset_ids["orders_ledger"]
    before = repo.latest_run(dataset_id)

    response = auth_client.post(f"/api/datasets/{dataset_id}/runs")
    assert response.status_code == 201
    created = response.get_json()["run"]
    assert created["run_number"] == before["run_number"] + 1
    assert created["trigger"] == "manual"
    assert created["total_rules"] >= 4
    assert len(response.get_json()["results"]) == created["total_rules"]

    latest = repo.latest_run(dataset_id)
    assert latest["id"] == created["id"]


def test_run_validation_on_unknown_dataset_is_404(auth_client):
    assert auth_client.post("/api/datasets/99999/runs").status_code == 404


def test_create_rule_and_evaluate_it_on_the_next_run(auth_client, dataset_ids):
    dataset_id = dataset_ids["signup_cohort"]
    payload = {
        "dataset_id": dataset_id,
        "name": "Plan is present",
        "kind": "null",
        "column_name": "plan",
        "params": {},
    }
    response = auth_client.post("/api/rules", json=payload)
    assert response.status_code == 201, response.get_json()
    rule = response.get_json()["rule"]
    assert rule["name"] == "Plan is present"
    assert rule["enabled"] is True

    run = auth_client.post(f"/api/datasets/{dataset_id}/runs").get_json()["run"]
    results = {row["rule_id"]: row for row in repo.results_for_run(run["id"])}
    assert rule["id"] in results


def test_create_range_rule_with_inverted_bounds_is_rejected(auth_client, dataset_ids):
    before = len(repo.list_rules(dataset_ids["orders_ledger"]))
    response = auth_client.post(
        "/api/rules",
        json={
            "dataset_id": dataset_ids["orders_ledger"],
            "name": "Inverted bounds",
            "kind": "range",
            "column_name": "order_total",
            "params": {"min": 900, "max": 100},
        },
    )
    assert response.status_code == 422
    fields = response.get_json()["error"]["fields"]
    assert "min" in fields
    assert "less than the maximum" in fields["min"]
    assert len(repo.list_rules(dataset_ids["orders_ledger"])) == before


def test_create_rule_with_unknown_kind_or_column_is_rejected(auth_client, dataset_ids):
    bad_kind = auth_client.post(
        "/api/rules",
        json={
            "dataset_id": dataset_ids["orders_ledger"],
            "name": "Nonsense kind",
            "kind": "regex",
            "column_name": "order_total",
        },
    )
    assert bad_kind.status_code == 422
    assert "kind" in bad_kind.get_json()["error"]["fields"]

    bad_column = auth_client.post(
        "/api/rules",
        json={
            "dataset_id": dataset_ids["orders_ledger"],
            "name": "Ghost column",
            "kind": "null",
            "column_name": "does_not_exist",
        },
    )
    assert bad_column.status_code == 422
    assert "column_name" in bad_column.get_json()["error"]["fields"]


def test_create_rule_for_unknown_dataset_is_404(auth_client):
    response = auth_client.post(
        "/api/rules",
        json={"dataset_id": 99999, "name": "Nowhere", "kind": "null", "column_name": "x"},
    )
    assert response.status_code == 404


def test_duplicate_rule_name_is_rejected(auth_client, dataset_ids):
    dataset_id = dataset_ids["orders_ledger"]
    existing = repo.list_rules(dataset_id)[0]
    response = auth_client.post(
        "/api/rules",
        json={
            "dataset_id": dataset_id,
            "name": existing["name"],
            "kind": "null",
            "column_name": "status",
        },
    )
    assert response.status_code == 422
    assert "name" in response.get_json()["error"]["fields"]


def test_patch_rule_toggles_enabled_state(auth_client, dataset_ids):
    rule = repo.list_rules(dataset_ids["signup_cohort"])[0]
    response = auth_client.patch(f"/api/rules/{rule['id']}", json={"enabled": False})
    assert response.status_code == 200
    assert response.get_json()["rule"]["enabled"] is False
    assert repo.get_rule(rule["id"])["enabled"] is False

    restored = auth_client.patch(f"/api/rules/{rule['id']}", json={"enabled": True})
    assert restored.status_code == 200
    assert repo.get_rule(rule["id"])["enabled"] is True


def test_patch_unknown_rule_is_404_and_bad_payload_is_422(auth_client, dataset_ids):
    rule = repo.list_rules(dataset_ids["signup_cohort"])[0]
    assert auth_client.patch("/api/rules/99999", json={"enabled": True}).status_code == 404

    bad_value = auth_client.patch(f"/api/rules/{rule['id']}", json={"enabled": "sometimes"})
    assert bad_value.status_code == 422

    missing_flag = auth_client.patch(f"/api/rules/{rule['id']}", json={})
    assert missing_flag.status_code == 422


def test_patch_rule_with_mismatched_dataset_is_404(auth_client, dataset_ids):
    rule = repo.list_rules(dataset_ids["signup_cohort"])[0]
    response = auth_client.patch(
        f"/api/rules/{rule['id']}",
        json={"enabled": True, "dataset_id": dataset_ids["orders_ledger"]},
    )
    assert response.status_code == 404


def test_write_endpoints_reject_cross_origin_requests(auth_client, dataset_ids):
    response = auth_client.post(
        f"/api/datasets/{dataset_ids['orders_ledger']}/runs",
        headers={"Origin": "https://evil.example"},
    )
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "cross_origin"


def test_anonymous_writes_are_rejected(client, dataset_ids):
    response = client.post(f"/api/datasets/{dataset_ids['orders_ledger']}/runs")
    assert response.status_code == 401
