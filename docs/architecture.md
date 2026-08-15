# ServiceLoop AI v0.1 架构

ServiceLoop AI 是企业级 Agentic 客服运营中枢，围绕下面这条业务闭环构建：

```text
AI 客服 -> 人工客服 -> 数据沉淀 -> 运营 Agent -> 知识更新 -> AI 客服
```

平台包含三个使用端：

- 用户聊天端：`/customer`
- 人工客服工作台：`/workspace`
- 运营管理端：`/operations`

平台只设置三个业务 Agent：

- 客户服务 Agent
- 数据运营 Agent
- 知识运营 Agent

Agent 调用六个确定性服务：知识、订单、物流、工单、人工和数据服务。RAG
不是 Agent，而是知识服务内部的一项实现。v0.1 中，RAG 与 FastAPI 后端部署在
同一个进程，不单独拆成服务。

当前里程碑用于确定后端边界，并迁移唯一一套 RAG。客服数据模型、三个正式使用端
和真实知识内容将在后续里程碑中继续实现。
