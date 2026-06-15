import { FileUp } from "lucide-react";
import { useState } from "react";

const scenarios = [
  { value: "scaffold_landed", label: "落地式钢管脚手架" },
  { value: "scaffold_cantilever", label: "悬挑式脚手架" },
  { value: "deep_foundation", label: "深基坑工程" },
  { value: "high_formwork", label: "高支模" }
];

export function Upload() {
  const [scenario, setScenario] = useState(scenarios[0].value);

  return (
    <section className="panel-grid">
      <div className="tool-panel upload-panel">
        <div className="panel-title">
          <FileUp size={20} />
          <h1>方案上传</h1>
        </div>
        <label className="field">
          <span>工程类型</span>
          <select value={scenario} onChange={(event) => setScenario(event.target.value)}>
            {scenarios.map((item) => (
              <option key={item.value} value={item.value}>
                {item.label}
              </option>
            ))}
          </select>
        </label>
        <label className="drop-zone">
          <FileUp size={34} />
          <span>选择 DOCX / PDF 文件</span>
          <input accept=".docx,.pdf" type="file" />
        </label>
        <div className="action-row">
          <button className="primary-button" type="button">
            提交解析
          </button>
          <button className="ghost-button" type="button">
            保存草稿
          </button>
        </div>
      </div>
      <div className="tool-panel checklist-panel">
        <div className="panel-title">
          <h2>资料检查</h2>
        </div>
        <ul className="checklist">
          <li data-state="done">文件编号已生成</li>
          <li data-state="done">脱敏状态已标记</li>
          <li data-state="pending">解析质量待评估</li>
          <li data-state="pending">专家复核待分派</li>
        </ul>
      </div>
    </section>
  );
}
