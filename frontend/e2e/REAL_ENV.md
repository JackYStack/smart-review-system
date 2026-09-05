# Compose 真实环境 E2E

演示模式测试不依赖后端，执行 `pnpm test:e2e` 即可。真实登录测试需要先启动完整 Compose 环境，并准备一个可登录账号。

PowerShell 示例：

```powershell
$env:E2E_BASE_URL = 'http://127.0.0.1'
$env:E2E_USERNAME = 'admin'
$env:E2E_PASSWORD = '<测试账号密码>'
pnpm test:e2e:real
```

若测试 HTTPS 环境使用的是内部自签名证书，可额外设置：

```powershell
$env:E2E_IGNORE_HTTPS_ERRORS = 'true'
```

真实配置不会自动启动或停止 Compose，也不会创建、修改或删除业务数据；当前只验证登录和进入系统。需要扩展真实文件提交测试时，应使用独立测试项目、独立方案类型和可清理的测试存储桶。
