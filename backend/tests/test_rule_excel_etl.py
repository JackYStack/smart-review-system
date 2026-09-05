from pathlib import Path

from openpyxl import Workbook

from app.services.rule_excel_etl import parse_rule_workbook


def _save_workbook(path: Path, *, source_text: str = "条款测试原文") -> None:
    workbook = Workbook()
    rules = workbook.active
    rules.title = "规则"
    rules.append(
        [
            "规则编号",
            "版本",
            "规则名称",
            "规则类型",
            "严重等级",
            "规则配置",
            "规范编号",
            "规范名称",
            "规范版本",
            "条款号",
            "条款原文",
        ]
    )
    rules.append(
        [
            "SCAFFOLD-F-001",
            1,
            "承载力验算",
            "formula",
            "error",
            "{}",
            "TEST-001",
            "测试规范",
            "2026",
            "5.1.1",
            source_text,
        ]
    )
    formulas = workbook.create_sheet("公式")
    formulas.append(
        [
            "规则编号",
            "规则版本",
            "公式编号",
            "版本",
            "公式名称",
            "表达式",
            "变量映射",
            "结果单位",
            "比较符",
            "阈值",
        ]
    )
    formulas.append(
        [
            "SCAFFOLD-F-001",
            1,
            "CAPACITY",
            1,
            "承载力",
            "load / area",
            '{"load":{"parameter":"load","unit":"N"},"area":{"parameter":"area","unit":"m2"}}',
            "Pa",
            "<=",
            1000,
        ]
    )
    workbook.save(path)


def test_rule_workbook_preview_is_valid(tmp_path: Path) -> None:
    path = tmp_path / "rules.xlsx"
    _save_workbook(path)
    plan = parse_rule_workbook(path, scheme_type_id=3)
    assert plan.valid
    assert len(plan.rules) == 1
    assert len(plan.formulas) == 1
    assert plan.public_report()["formula_count"] == 1


def test_rule_without_traceable_clause_is_rejected(tmp_path: Path) -> None:
    path = tmp_path / "rules.xlsx"
    _save_workbook(path, source_text="")
    plan = parse_rule_workbook(path, scheme_type_id=3)
    assert not plan.valid
    assert any("条款" in error.message for error in plan.errors)
