# ServiceLoop AI v0.1 架构

ServiceLoop AI 是企业级 Agentic 客服运营中枢，围绕下面这条业务闭环构建：

```text
AI 客服 -> 人工客服 -> 数据沉淀 -> 运营 Agent -> 知识更新 -> AI 客服
```

平台包含三个使用端：

- 用户聊天端：`/customer`
- 人工客服工作台：`/agent`
- 运营管理端：`/operations`

平台只设置三个业务 Agent：

- 客户服务 Agent
- 数据运营 Agent
- 知识运营 Agent

Agent 调用六个确定性服务：知识、订单、物流、工单、人工和数据服务。RAG
不是 Agent，而是知识服务内部的一项实现。v0.1 中，RAG 与 FastAPI 后端部署在
同一个进程，不单独拆成服务。

当前里程碑已经确定后端边界、迁移唯一一套 RAG，并使用 MySQL 8 与 SQLAlchemy 2
建立客服数据中台。第一版使用简单建表入口和自动提交／异常回滚事务，
不引入数据库锁和复杂迁移配置。客户服务 Agent 已通过 LangGraph ToolNode 调用五个业务
Tool，并使用条件边跑通直接回答与转人工分支。显式人工请求、工具异常和低质量检索使用
工作流路由；其中显式人工请求和工具失败由代码守住，条款咨询与实际退款操作由 Agent
区分。知识为空或低分时允许 Query Rewrite 节点受控改写并只重试一次，
第二次仍不达标时进入 Evidence Decision 节点，结合问题意图、检索片段和 ReRank 分数选择
回答、追问或转人工。所有接管都会执行 Knowledge Gap 判定，只有知识类原因进入运营待补充
列表。

订单、物流和工单 Tool 在生产依赖中读取或写入 MySQL；内存数据只作为单元测试的依赖注入
替身。客户评价、失败 Tool Call 与异常 Handoff 由数据运营 Agent 通过 LangGraph 条件工作流
去重为 Bad Case，再按知识、工具、体验和流程形成 Improvement Task。知识／体验类任务可以
回流为 Knowledge Gap，继续经过知识运营 Agent、人工确认、版本发布和运行时索引切换，形成：

```text
运行信号 -> Bad Case -> Improvement Task -> Knowledge Gap -> Draft -> Published Knowledge
```

三个正式使用端、两条运营 Agent 链路和 MySQL 数据仓储均已可运行。正式身份系统、真实企业
业务系统接入和生产监控保留为上线工程，不为简历演示引入额外基础设施。
