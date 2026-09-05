from app.models.integration_settings import IntegrationSettings
from app.services.configuration_audit import (
    apply_integration_snapshot,
    changed_fields,
    integration_snapshot,
)


def test_integration_snapshot_diff_and_restore() -> None:
    row = IntegrationSettings(
        dify_workflow_enabled=True,
        dify_workflow_base_url="http://old/v1",
        dify_workflow_output_variable="report",
    )
    before = integration_snapshot(row)
    row.dify_workflow_base_url = "http://new/v1"
    after = integration_snapshot(row)
    assert changed_fields(before, after) == ["dify_workflow_base_url"]
    apply_integration_snapshot(row, before)
    assert row.dify_workflow_base_url == "http://old/v1"

