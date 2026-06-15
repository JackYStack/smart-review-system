const steps = ["上传", "解析", "审查", "复核", "报告"];

export function StatusRail() {
  return (
    <div className="status-rail" aria-label="审查流程">
      {steps.map((step, index) => (
        <div className="status-step" key={step}>
          <span>{index + 1}</span>
          <p>{step}</p>
        </div>
      ))}
    </div>
  );
}
