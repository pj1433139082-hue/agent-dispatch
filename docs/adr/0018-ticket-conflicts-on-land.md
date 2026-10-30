# land 时票文件冲突：目标分支优先

票目录放在仓库内时，两条分支都会改同一张票文件，land 的 merge 会出 add/add 或 modify/modify 冲突。票是流水线文档，不是这条 run 的交付物，所以 **land 合并冲突只涉及 tickets_dir 下的文件时，自动 `git checkout --ours`（目标分支版本）并提交**；只要冲突里出现非票文件，就原样失败，不替人做决定。

**Considered Options**：把票目录移出仓库（改动大、破坏现有约定）被否；`git merge -X ours` 全局策略被否（会吞掉代码冲突）。

**Consequences**：票文件永远以目标分支为准；run 分支里的票副本只用于执行，不回写。
