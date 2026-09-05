"""Test Dify Workflow connectivity without printing the API key."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import httpx

_BACKEND = Path(__file__).resolve().parent.parent
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.config import get_settings
from app.services.dify_workflow_client import DifyWorkflowClient


def main() -> int:
    parser = argparse.ArgumentParser(description="Test the configured Dify Workflow application.")
    parser.add_argument("--file", type=Path, help="Optional DOCX/PDF to run through the workflow")
    args = parser.parse_args()
    settings = get_settings()
    base_url = settings.dify_workflow_base_url.rstrip("/")
    api_key = settings.dify_workflow_api_key
    if not base_url or not api_key:
        print("ERROR: DIFY_WORKFLOW_BASE_URL or DIFY_WORKFLOW_API_KEY is not configured")
        return 2

    if args.file is None:
        try:
            response = httpx.get(
                f"{base_url}/info",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=20,
            )
            print(f"HTTP {response.status_code}")
            if response.is_success:
                body = response.json()
                print(f"Connected application: {body.get('name') or '(unnamed)'}")
                return 0
            print("Dify responded, but authentication or the endpoint configuration failed.")
            return 1
        except httpx.RequestError as exc:
            print(f"NETWORK ERROR: {type(exc).__name__}: {exc}")
            return 1

    file_path = args.file.resolve()
    if not file_path.is_file():
        print(f"ERROR: file not found: {file_path}")
        return 2
    client = DifyWorkflowClient(
        base_url,
        api_key,
        settings.dify_workflow_timeout_seconds,
    )
    result = client.run_review(
        file_name=file_path.name,
        file_content=file_path.read_bytes(),
        project_name=file_path.stem,
        project_region="",
        risk_type="危大工程",
        review_focus="执行接口联调测试",
        user="smart-review-connection-test",
    )
    print("Workflow succeeded")
    print(f"status={result.status}")
    print(f"workflow_run_id={result.workflow_run_id}")
    print(f"report_length={len(result.report)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
