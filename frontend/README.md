# ServiceLoop Web

ServiceLoop 的客户聊天端和人工客服工作台，使用 React、TypeScript 和 Vite。前端与后端
目录完全分离，两个使用端复用同一套视觉语言和 API 基础设施。

## 启动

需要 Node.js 20.19+ 或 22.12+：

```bash
pnpm install
pnpm dev
```

浏览器打开：

- 客户聊天端：`http://127.0.0.1:5173/customer`
- 人工客服工作台：`http://127.0.0.1:5173/agent`

开发环境默认请求
`http://127.0.0.1:8000`，需要覆盖时新建 `frontend/.env.local`：

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

生产构建：

```bash
pnpm build
```

## 当前人工闭环

1. Customer Service Agent 判断需要转人工并创建 Handoff；
2. 人工客服工作台读取待接管队列和 Agent 上下文包；
3. 客服领取任务后，客户聊天端自动进入人工服务并允许双方继续回复；
4. 客服填写处理动作和最终回复，提交后创建 Human Resolution；
5. 会话与 Handoff 同时进入已解决状态。

当前使用固定演示客服身份 `agent-demo-001`，正式登录和权限不属于 v0.1 范围。
