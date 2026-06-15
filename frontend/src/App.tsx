import {
  AlertTriangle,
  ClipboardCheck,
  FileText,
  Gauge,
  Search,
  ShieldCheck,
  UploadCloud,
  UsersRound
} from "lucide-react";
import { useMemo, useState } from "react";

import { MetricStrip } from "./components/MetricStrip";
import { StatusRail } from "./components/StatusRail";
import { ExpertQueue } from "./pages/ExpertQueue";
import { ReportView } from "./pages/ReportView";
import { ReviewWorkbench } from "./pages/ReviewWorkbench";
import { Upload } from "./pages/Upload";

type ViewKey = "upload" | "workbench" | "expert" | "report";

const views = [
  { key: "upload", label: "方案上传", icon: UploadCloud },
  { key: "workbench", label: "审查工作台", icon: ClipboardCheck },
  { key: "expert", label: "专家复核", icon: UsersRound },
  { key: "report", label: "报告导出", icon: FileText }
] as const;

export default function App() {
  const [activeView, setActiveView] = useState<ViewKey>("upload");

  const metrics = useMemo(
    () => [
      { label: "待解析", value: "3", icon: Search, tone: "blue" },
      { label: "红线问题", value: "2", icon: AlertTriangle, tone: "red" },
      { label: "复核中", value: "5", icon: UsersRound, tone: "amber" },
      { label: "证据完整率", value: "100%", icon: ShieldCheck, tone: "green" }
    ],
    []
  );

  return (
    <main className="app-shell">
      <aside className="sidebar" aria-label="主导航">
        <div className="brand">
          <Gauge size={24} />
          <div>
            <strong>智审系统</strong>
            <span>v0.1</span>
          </div>
        </div>
        <nav className="nav-list">
          {views.map((view) => {
            const Icon = view.icon;
            return (
              <button
                className={activeView === view.key ? "nav-item active" : "nav-item"}
                key={view.key}
                onClick={() => setActiveView(view.key)}
                title={view.label}
                type="button"
              >
                <Icon size={18} />
                <span>{view.label}</span>
              </button>
            );
          })}
        </nav>
        <StatusRail />
      </aside>

      <section className="workspace">
        <MetricStrip metrics={metrics} />
        {activeView === "upload" && <Upload />}
        {activeView === "workbench" && <ReviewWorkbench />}
        {activeView === "expert" && <ExpertQueue />}
        {activeView === "report" && <ReportView />}
      </section>
    </main>
  );
}
