# 技术架构 V1.0

## 总体形态

本地优先 Web 应用。Windows 桌面快捷方式启动仅监听 `127.0.0.1` 的后端服务，并打开本地 Dashboard。前端静态资源、后端、SQLite 数据库、原始证据和用户笔记均可随安装包部署。

## 组件

- 前端：React、TypeScript、Vite、Apache ECharts。
- 后端：Python、FastAPI、SQLAlchemy、Pydantic。
- 数据库：SQLite；模式变化使用 Alembic 管理。
- 采集：每个机构一个适配器，统一输出原始证据和候选观测值。
- 调度：应用内调度器加 Windows 任务计划程序。
- 通知：应用内状态为主，Windows 通知为辅。
- 测试：公式、解析器、数据库、API 和浏览器端到端测试。

## 数据流水线

1. Source Registry：登记来源机构、数据集、入口、频率和获取策略。
2. Raw Artifact：保存网页、PDF、Excel、CSV 或接口响应及 SHA-256。
3. Parser：从原始资料生成候选观测值。
4. Validator：检查字段、单位、统计期、重复值、异常和口径版本。
5. Observation：审核通过后写入带版本的规范数据。
6. Metric Engine：计算同比、环比、剪刀差和趋势。
7. Signal Engine：根据可配置规则生成参考信号与解释。
8. Presentation：通过 API 向 Dashboard 提供数据。

## 关键边界

- 页面不直接抓取官网。
- 采集器不直接覆盖正式观测值。
- 自动计算不修改官方原始数据。
- 信号与原始事实分表保存。
- 用户笔记引用具体的数据版本，保证复盘时能还原当时信息。

