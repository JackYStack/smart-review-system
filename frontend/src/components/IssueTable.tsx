type Issue = {
  id: string;
  title: string;
  severity: "A" | "B" | "C";
  module: string;
  status: string;
};

const issues: Issue[] = [
  {
    id: "ISS-001",
    title: "未明确落地式脚手架搭设高度",
    severity: "B",
    module: "参数性",
    status: "待复核"
  },
  {
    id: "ISS-002",
    title: "专项方案审批链缺少编制单位签章",
    severity: "A",
    module: "程序性",
    status: "红线"
  },
  {
    id: "ISS-003",
    title: "连墙件布置参数缺少页码证据",
    severity: "C",
    module: "证据链",
    status: "补证据"
  }
];

export function IssueTable() {
  return (
    <div className="table-wrap">
      <table>
        <thead>
          <tr>
            <th>编号</th>
            <th>问题</th>
            <th>等级</th>
            <th>模块</th>
            <th>状态</th>
          </tr>
        </thead>
        <tbody>
          {issues.map((issue) => (
            <tr key={issue.id}>
              <td>{issue.id}</td>
              <td>{issue.title}</td>
              <td>
                <span className={`severity severity-${issue.severity}`}>{issue.severity}</span>
              </td>
              <td>{issue.module}</td>
              <td>{issue.status}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
