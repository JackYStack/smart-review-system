import json

from app.services.expert_review import safe_json_dict, stable_issue_key


def test_stable_issue_key_uses_source_id_but_namespaces_it_by_step() -> None:
    first = stable_issue_key("content", {"issue_id": "RULE-001"})
    assert first == stable_issue_key("content", {"issue_id": "RULE-001"})
    assert first != stable_issue_key("dify_workflow", {"issue_id": "RULE-001"})


def test_stable_issue_key_is_order_independent() -> None:
    first = {
        "message": "立杆间距超限",
        "evidence": "原文摘录",
        "anchor": {"title_path": ["计算书"], "heading_para_index": 12},
    }
    second = json.loads(json.dumps(first, ensure_ascii=False, sort_keys=True))
    assert stable_issue_key("rules_and_formulas", first) == stable_issue_key(
        "rules_and_formulas", second
    )


def test_malformed_json_is_never_exposed_as_dict() -> None:
    assert safe_json_dict("not-json") == {}
    assert safe_json_dict("[]") == {}
