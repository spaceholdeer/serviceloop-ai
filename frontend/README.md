# ServiceLoop Customer

ServiceLoop 的客户聊天端，使用 React、TypeScript 和 Vite。前端与后端目录完全分离，
当前只实现 `/customer`，后续的人工工作台和运营后台继续复用同一设计系统。

## 启动

需要 Node.js 20.19+ 或 22.12+：

```bash
pnpm install
pnpm dev
```

浏览器打开 `http://127.0.0.1:5173/customer`。开发环境默认请求
`http://127.0.0.1:8000`，需要覆盖时新建 `frontend/.env.local`：

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

生产构建：

```bash
pnpm build
```
