import { Download, FileText } from "lucide-react";

export function ReportView() {
  return (
    <section className="tool-panel">
      <div className="panel-title">
        <FileText size={20} />
        <h1>报告导出</h1>
      </div>
      <div className="report-list">
        {["审查报告_v0.1.pdf", "问题清单_v0.1.xlsx", "专家复核记录.md"].map((fileName) => (
          <article className="report-item" key={fileName}>
            <span>{fileName}</span>
            <button className="icon-button" title="下载" type="button">
              <Download size={18} />
            </button>
          </article>
        ))}
      </div>
    </section>
  );
}
