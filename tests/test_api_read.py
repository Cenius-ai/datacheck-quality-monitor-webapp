"""Read API contract: datasets, runs, rule results, history and failures."""

from __future__ import annotations

from datacheck import repositories as repo


def test_dataset_list_shape(auth_client):
    payload = auth_client.get("/api/datasets").get_json()
    datasets = payload["datasets"]
    assert len(datasets) == 3
    first = datasets[0]
    assert first["slug"] == "billing_transactions"
    assert first["row_count"] == 500
    assert first["latest_run"]["quality_score"] > 0
    for dataset in datasets:
        for key in ("id", "name", "description", "rule_count", "latest_run"):
            assert key in dataset


def test_runs_are_returned_newest_first(auth_client, dataset_ids):
    dataset_id = dataset_ids["billing_transactions"]
    payload = auth_client.get(f"/api/datasets/{dataset_id}/runs").get_json()
    runs = payload["runs"]
    assert len(runs) == 21
    numbers = [run["run_number"] for run in runs]
    assert numbers == sorted(numbers, reverse=True)
    for key in ("started_at", "quality_score", "total_rules", "failed_rules", "trigger"):
        assert key in runs[0]


def test_rule_results_cover_every_rule(auth_client, dataset_ids):
    dataset_id = dataset_ids["billing_transactions"]
    run = repo.latest_run(dataset_id)
    payload = auth_client.get(f"/api/runs/{run['id']}/rule-results").get_json()
    rules = repo.list_rules(dataset_id)
    assert len(payload["results"]) == len(rules)
    assert {row["rule_id"] for row in payload["results"]} == {rule["id"] for rule in rules}
    for row in payload["results"]:
        assert row["checked_count"] == 500


def test_rule_history_returns_21_results_oldest_first(auth_client, dataset_ids):
    rule = repo.list_rules(dataset_ids["orders_ledger"])[0]
    payload = auth_client.get(f"/api/rules/{rule['id']}/history").get_json()
    history = payload["history"]
    assert len(history) == 21
    numbers = [row["run_number"] for row in history]
    assert numbers == sorted(numbers)


def test_failures_endpoint_returns_capped_samples(auth_client, dataset_ids):
    run = repo.latest_run(dataset_ids["billing_transactions"])
    results = repo.results_for_run(run["id"])
    failing = next(row for row in results if not row["passed"])
    payload = auth_client.get(
        f"/api/runs/{run['id']}/failures?rule_id={failing['rule_id']}"
    ).get_json()
    assert payload["checked_rows"] == 500
    assert payload["failing_rows"] > 0
    assert 1 <= len(payload["failures"]) <= 20
    sample = payload["failures"][0]
    for key in ("row_index", "column_name", "value_text", "reason"):
        assert key in sample


def test_rules_list_includes_the_result_for_the_selected_run(auth_client, dataset_ids):
    dataset_id = dataset_ids["orders_ledger"]
    runs = auth_client.get(f"/api/datasets/{dataset_id}/runs").get_json()["runs"]
    clean_run = next(run for run in runs if run["failed_rules"] == 0)
    payload = auth_client.get(
        f"/api/datasets/{dataset_id}/rules?run_id={clean_run['id']}"
    ).get_json()
    assert all(rule["result"]["passed"] for rule in payload["rules"])


def test_unknown_ids_return_404_json(auth_client):
    for path in (
        "/api/datasets/99999/runs",
        "/api/datasets/99999/rules",
        "/api/runs/99999/rule-results",
        "/api/runs/99999/failures",
        "/api/rules/99999/history",
    ):
        response = auth_client.get(path)
        assert response.status_code == 404, path
        assert response.get_json()["error"]["code"] == "not_found"


def test_rule_from_another_dataset_is_not_reachable_through_a_wrong_dataset(auth_client, dataset_ids):
    orders_rule = repo.list_rules(dataset_ids["orders_ledger"])[0]
    response = auth_client.get(
        f"/api/datasets/{dataset_ids['signup_cohort']}/rules?run_id={orders_rule['id']}"
    )
    assert response.status_code == 404
