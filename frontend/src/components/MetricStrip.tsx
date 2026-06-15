import type { LucideIcon } from "lucide-react";

type Metric = {
  label: string;
  value: string;
  icon: LucideIcon;
  tone: string;
};

type MetricStripProps = {
  metrics: Metric[];
};

export function MetricStrip({ metrics }: MetricStripProps) {
  return (
    <section className="metric-strip" aria-label="审查指标">
      {metrics.map((metric) => {
        const Icon = metric.icon;
        return (
          <article className={`metric-card tone-${metric.tone}`} key={metric.label}>
            <Icon size={20} />
            <div>
              <span>{metric.label}</span>
              <strong>{metric.value}</strong>
            </div>
          </article>
        );
      })}
    </section>
  );
}
