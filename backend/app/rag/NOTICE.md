# RAG 来源说明

本模块的部分代码和设计改编自
[`spaceholdeer/redevops-rag`](https://github.com/spaceholdeer/redevops-rag)。
该仓库说明它基于
[`redevops-io/redevops-rag`](https://github.com/redevops-io/redevops-rag)。

迁移后的模块继续附带 AGPL-3.0-or-later 许可证，文件位于
`backend/app/rag/LICENSE`。ServiceLoop 的主要修改包括：移除 metadata 硬约束和
独立答案生成层，增加预构建 BM25 倒排索引、内存 Dense 精确索引、原子索引快照、
动态知识版本和本地测试页面。
