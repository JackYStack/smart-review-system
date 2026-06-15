import { ClipboardCheck, GitMerge, ShieldAlert } from "lucide-react";

import { IssueTable } from "../components/IssueTable";

export function ReviewWorkbench() {
  return (
    <section className="workbench-layout">
      <div className="tool-panel main-panel">
        <div className="panel-title">
          <ClipboardCheck size={20} />
          <h1>审查工作台</h1>
        </div>
        <IssueTable />
      </div>
      <aside className="side-stack">
        <div className="tool-panel">
          <div className="panel-title compact">
            <ShieldAlert size={18} />
            <h2>红线队列</h2>
          </div>
          <strong className="large-count">2</strong>
        </div>
        <div className="tool-panel">
          <div className="panel-title compact">
            <GitMerge size={18} />
            <h2>证据链</h2>
          </div>
          <div className="evidence-meter">
            <span style={{ width: "86%" }} />
          </div>
          <p className="muted">86% 已绑定条文与页码</p>
        </div>
      </aside>
    </section>
  );
}
