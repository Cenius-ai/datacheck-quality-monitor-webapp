"""Dash shell wiring: three tabs, unique callback outputs, defensive rendering."""

from __future__ import annotations

import json
from collections import Counter

from datacheck.dash_app import state as app_state
from datacheck.dash_app.format import humanize_timestamp, kind_label, rule_parameters
from datacheck.dash_app.tabs import failures as failures_tab
from datacheck.dash_app.tabs import overview as overview_tab
from datacheck.dash_app.tabs import rules as rules_tab


def _walk(node, found=None):
    """Collect (component type, props) pairs from a Dash component tree."""
    found = [] if found is None else found
    if isinstance(node, (list, tuple)):
        for item in node:
            _walk(item, found)
        return found
    if hasattr(node, "to_plotly_json"):
        payload = node.to_plotly_json()
        found.append((payload.get("type"), payload.get("props", {})))
        _walk(payload.get("props", {}).get("children"), found)
    return found


def _resolved_layout(dash_module):
    """The layout the server actually renders.

    `app.layout` is a callable (it reads ?dataset=/?tab= per request), so the
    component tree has to be resolved with Dash's own accessor before it can be
    inspected.
    """
    return dash_module.app._layout_value()


def _layouts_payload_props(payload, target_id, found=None):
    """Every props dict in a serialised layout payload that carries `target_id`."""
    found = [] if found is None else found
    if isinstance(payload, dict):
        props = payload.get("props")
        if isinstance(props, dict) and props.get("id") == target_id:
            found.append(props)
        for value in payload.values():
            _layouts_payload_props(value, target_id, found)
    elif isinstance(payload, list):
        for item in payload:
            _layouts_payload_props(item, target_id, found)
    return found


def _dependency(dep):
    """(component_id, component_property) for a Dash dependency or a raw dict."""
    if isinstance(dep, dict):
        return dep.get("id"), dep.get("property")
    return getattr(dep, "component_id", None), getattr(dep, "component_property", None)


def _callback_specs(dash_module):
    """Every registered callback, whether or not the server has started yet."""
    from dash._callback import GLOBAL_CALLBACK_MAP

    return list(GLOBAL_CALLBACK_MAP.values()) + list(dash_module.app.callback_map.values())


def _output_property(spec):
    output = spec.get("output")
    if isinstance(output, str):
        return output
    component_id, component_property = _dependency(output)
    return f"{component_id}.{component_property}"


def _text(node, out=None):
    out = [] if out is None else out
    if isinstance(node, str):
        out.append(node)
    elif isinstance(node, (list, tuple)):
        for item in node:
            _text(item, out)
    elif node is not None and hasattr(node, "to_plotly_json"):
        _text(node.to_plotly_json().get("props", {}).get("children"), out)
    return out


def test_flask_cli_resolves_exactly_one_application(dash_module):
    """`flask run` boots this module: it must find exactly one Flask instance.

    A second module-level Flask binding (e.g. `flask_app = ...`) makes the CLI
    abort with "Detected multiple Flask applications in module 'app'", which
    breaks a clean-clone boot.
    """
    import dash as dash_pkg
    from flask import Flask
    from flask.cli import find_best_app

    flask_names = [
        name for name, value in vars(dash_module).items() if isinstance(value, Flask)
    ]
    assert flask_names == ["server"], f"unexpected Flask bindings: {flask_names}"
    assert find_best_app(dash_module) is dash_module.server
    assert isinstance(dash_module.app, dash_pkg.Dash)


def test_layout_contains_the_three_workspace_tabs(dash_module):
    components = _walk(_resolved_layout(dash_module))
    tabs = [props for kind, props in components if kind == "Tab"]
    assert [tab["value"] for tab in tabs] == ["overview", "rules", "failures"]
    assert [tab["label"] for tab in tabs] == ["Quality overview", "Rules", "Failures"]


def test_layout_exposes_every_id_the_callbacks_target(dash_module):
    component_ids = {
        props.get("id")
        for _kind, props in _walk(_resolved_layout(dash_module))
        if isinstance(props.get("id"), str)
    }
    required = {
        "url",
        "tabs",
        "dataset-picker",
        "dataset-store",
        "selected-run",
        "focused-rule",
        "refresh-tick",
        "run-validation",
        "run-context",
        "dataset-meta",
        "current-user",
        "overview-kpis",
        "score-trend",
        "runs-table",
        "rules-table",
        "rule-history",
        "create-rule-name",
        "create-rule-kind",
        "create-rule-column",
        "create-rule-submit",
        "failures-summary",
        "failure-rule-picker",
        "failures-table",
        "flash",
        "nav-overview",
        "nav-rules",
        "nav-failures",
    }
    missing = required - component_ids
    assert not missing, f"layout is missing {sorted(missing)}"


def test_each_callback_output_has_exactly_one_writer(dash_module):
    from dash._callback import GLOBAL_CALLBACK_MAP

    keys = set(GLOBAL_CALLBACK_MAP) | set(dash_module.app.callback_map)
    outputs = [
        output
        for key in keys
        for output in key.strip(".").split("...")
        if output and "@" not in output
    ]
    duplicates = [output for output, count in Counter(outputs).items() if count > 1]
    assert duplicates == [], f"duplicate callback outputs: {duplicates}"


def test_layout_first_paint_renders_seeded_content(dash_module):
    text = " ".join(_text(_resolved_layout(dash_module)))
    assert "Quality score" in text
    assert "Recent runs" in text
    assert "Billing transactions" in text
    assert "81.08" in text or "80" in text  # the regression dataset's latest score


def test_layout_restores_dataset_and_tab_from_the_query_string(auth_client, dataset_ids):
    """A refresh or a deep link renders the requested dataset/tab server-side."""
    target = dataset_ids["signup_cohort"]
    payload = auth_client.get(f"/app/_dash-layout?dataset={target}&tab=rules").get_json()
    picker = _layouts_payload_props(payload, "dataset-picker")[0]
    tabs = _layouts_payload_props(payload, "tabs")[0]
    assert picker["value"] == target
    assert tabs["value"] == "rules"
    assert _layouts_payload_props(payload, "dataset-store")[0]["data"] == target


def test_layout_tolerates_a_junk_query_string(auth_client, dataset_ids):
    payload = auth_client.get(
        "/app/_dash-layout?dataset=abc&tab=nope&run=999"
    ).get_json()
    assert _layouts_payload_props(payload, "dataset-picker")[0]["value"] == dataset_ids["billing_transactions"]
    assert _layouts_payload_props(payload, "tabs")[0]["value"] == "overview"

    unknown = auth_client.get("/app/_dash-layout?dataset=99999&tab=failures").get_json()
    assert _layouts_payload_props(unknown, "dataset-picker")[0]["value"] == dataset_ids["billing_transactions"]
    assert _layouts_payload_props(unknown, "tabs")[0]["value"] == "failures"


def test_the_selected_dataset_is_written_back_into_the_url(dash_module):
    """Picking a dataset must persist it in ?dataset= so a refresh restores it."""
    specs = _callback_specs(dash_module)
    writers = [spec for spec in specs if _output_property(spec) == "url.search"]
    assert writers, "nothing writes the dataset selection into the URL query string"
    inputs = [_dependency(dep) for dep in writers[0]["inputs"]]
    assert ("dataset-store", "data") in inputs
    # ...and the dataset picker stays a single-direction source (no cycle).
    reader_outputs = {
        _output_property(spec)
        for spec in specs
        if any(_dependency(dep)[0] == "url" for dep in spec["inputs"])
    }
    assert "url.search" not in reader_outputs


def test_index_html_declares_language_and_title(dash_module, auth_client):
    body = auth_client.get("/app/").get_data(as_text=True)
    assert '<html lang="en">' in body
    assert "<title>Datacheck Quality Monitor</title>" in body
    assert "loading" in body.lower()


def test_overview_helpers_handle_empty_data():
    assert _text(overview_tab.kpi_strip(None, None, 0))
    assert _text(overview_tab.runs_table([]))
    figure = overview_tab.trend_figure([], None)
    assert figure.layout.annotations[0].text == "No runs yet"
    assert _text(overview_tab.run_detail(None, None))


def test_rules_and_failures_helpers_handle_empty_data():
    assert _text(rules_tab.rule_table([], {}, None))
    assert _text(rules_tab.history_panel(None, []))
    assert _text(rules_tab.create_rule_form([], "dataset"))
    assert _text(failures_tab.failures_summary(None, [], 0))
    empty = failures_tab.failures_table([], None, None, [])
    assert "No run selected." in " ".join(_text(empty))
    no_failures = failures_tab.failures_table([], None, {"run_number": 3, "checked_rows": 5}, [])
    assert "No failures in this run" in " ".join(_text(no_failures))


def test_state_loaders_tolerate_unknown_and_missing_ids():
    assert app_state.load_overview(999_999, None).run is None
    assert app_state.load_rules(999_999, None).rules == []
    assert app_state.load_rules(None, None).dataset is not None
    assert app_state.load_failures(999_999, 999_999, 999_999).samples == []


def test_rule_parameters_are_human_readable():
    assert rule_parameters({"kind": "range", "params": {"min": 0, "max": 2500}}) == "0 – 2,500"
    assert rule_parameters({"kind": "range", "params": {"min": -250, "max": 5000}}) == "-250 – 5,000"
    assert rule_parameters({"kind": "unique", "params": {}}) == "no duplicates"
    assert rule_parameters({"kind": "null", "params": {}}) == "no nulls"
    assert kind_label("range") == "Range"


def test_humanized_timestamps_never_leak_raw_iso():
    assert humanize_timestamp(None) == "—"
    assert humanize_timestamp("not-a-date") == "—"
    rendered = humanize_timestamp("2026-03-01T02:15:00Z")
    assert "T" not in rendered
    assert "Z" not in rendered


def test_seeded_figures_serialise_for_the_browser(dash_module):
    dataset = app_state.resolve_dataset(None)
    data = app_state.load_overview(dataset["id"], None)
    figure = overview_tab.trend_figure(data.runs, data.run["id"])
    payload = json.loads(figure.to_json())
    assert len(payload["data"][0]["x"]) == 21
    assert payload["layout"]["yaxis"]["ticksuffix"] == "%"
