from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from app.database import SessionLocal
from app.services.rule_excel_etl import apply_rule_import, parse_rule_workbook


def main() -> int:
    parser = argparse.ArgumentParser(description="预览或导入危大工程规则Excel")
    parser.add_argument("file", type=Path)
    parser.add_argument("--scheme-type-id", type=int, required=True)
    parser.add_argument("--apply", action="store_true", help="通过校验后执行事务导入")
    parser.add_argument("--replace-existing", action="store_true")
    parser.add_argument("--actor-id", type=int)
    parser.add_argument("--report", type=Path, help="可选JSON校验报告输出路径")
    args = parser.parse_args()

    plan = parse_rule_workbook(args.file, scheme_type_id=args.scheme_type_id)
    report = plan.public_report()
    exit_code = 0 if plan.valid else 2
    if args.apply and plan.valid:
        with SessionLocal() as db:
            try:
                report["apply_result"] = apply_rule_import(
                    db,
                    plan,
                    actor_id=args.actor_id,
                    replace_existing=args.replace_existing,
                )
                db.commit()
                report["applied"] = True
            except Exception as exc:
                db.rollback()
                report["applied"] = False
                report["apply_error"] = str(exc)
                exit_code = 3
    else:
        report["applied"] = False

    text = json.dumps(report, ensure_ascii=False, indent=2)
    print(text)
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(text + "\n", encoding="utf-8")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
