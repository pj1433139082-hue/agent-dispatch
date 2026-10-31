# 调用方式：dispatch 技能保持 model-invoked

上游把重技能（wayfinder / triage / grilling）设成 user-invoked：描述不常驻，省上下文，但只能人手敲名字。我们**不照搬**这条：dispatch 的八个技能是命令式工具，价值在于"该派单时自动出现"；改成 user-invoked 会让人先记住名字再调用，和"路由"目标冲突。代价是描述常驻，可以靠把描述写短来控制。

**Considered Options**：全部改 user-invoked（省上下文，失去自动触发）；只把 wayfinder/triage 改 user-invoked（它们不是我们维护的，会被 skillshare 覆盖）。

**Consequences**：dispatch 技能继续自动触发；重技能由 dispatch-flow 的 A0/外部输入两条路由显式点名，避免"模型不知道它存在"。
