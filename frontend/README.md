# SmartReview 前端

React 19、TypeScript、Vite、Ant Design 与 TanStack Query 构成的单页管理端。

## 本地开发

```powershell
corepack enable
pnpm install --frozen-lockfile
pnpm run dev
```

开发服务器默认访问 `http://127.0.0.1:5173`，并把 `/api` 转发到 `http://127.0.0.1:8000`。

## 验证

```powershell
pnpm run lint
pnpm run build
```

Docker 构建使用同一份 `pnpm-lock.yaml`，保证本地与部署环境依赖一致。
