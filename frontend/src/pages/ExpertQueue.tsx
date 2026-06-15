import { CheckCircle2, UserCheck } from "lucide-react";

const items = ["程序性红线复核", "公式验算边界值复核", "整改建议文本复核"];

export function ExpertQueue() {
  return (
    <section className="tool-panel">
      <div className="panel-title">
        <UserCheck size={20} />
        <h1>专家复核</h1>
      </div>
      <div className="queue-list">
        {items.map((item, index) => (
          <article className="queue-item" key={item}>
            <CheckCircle2 size={18} />
            <div>
              <strong>{item}</strong>
              <span>REV-{String(index + 1).padStart(3, "0")}</span>
            </div>
            <button className="ghost-button" type="button">
              领取
            </button>
          </article>
        ))}
      </div>
    </section>
  );
}
