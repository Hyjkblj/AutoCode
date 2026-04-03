# 分支隔离修复与 PR 任务更新（2026-04-03）

## 1. 目标
- 修复当前多 worktree/多分支中的串线与脏工作区问题。
- 在不丢失现场的前提下恢复“按 Agent 白名单路径开发”的纪律。
- 给出从当前状态继续推进 M3/M4/M5 的 PR 清单与合并顺序。

## 2. 当前检查结论（基线：2026-04-03）
- `origin/master` 已合并：`#1 #2 #3 #4 #5 #7 #8 #9`。
- 仍未合入 `origin/master` 的有效开发分支：`feat/a4-mobile-visual-app`（ahead=1）。
- 本地 `master` 落后 `origin/master`，后续比对统一以 `origin/master` 为准。
- 脏工作区（需要处理）：
  - `D:/Develop/Project/AutoCode-a1`：2 个测试文件修改（白名单内，可保留）。
  - `D:/Develop/Project/AutoCode-a4`：`?? .gradle-local/`（构建产物）。
  - `D:/Develop/Project/AutoCode-agent2`：`?? control-plane-spring/build/`（构建产物）。
  - `D:/Develop/Project/AutoCode-agent3-m2`：大量 `mobile-app/**` 改动（与 Agent-3 白名单冲突，属于串线风险）。

## 3. 修复动作（先修复再继续开发）

### P0：先保护现场（防止误删）
- 在 `agent3-m2` 先做保护性暂存：
  - `git -C D:/Develop/Project/AutoCode-agent3-m2 stash push -u -m "temp: accidental mobile-app edits on agent3-m2 2026-04-03"`
- 如需追溯误改来源，可从该 stash 拉救援分支：
  - `git -C D:/Develop/Project/AutoCode-agent3-m2 stash branch chore/rescue-mobile-app-accidental-20260403`

### P0：恢复 Agent-3 工作区白名单边界
- `agent3-m2` 只允许 `pc-agent-java/**`（及必要 `pom.xml` 约束项）。
- 将 `mobile-app/**` 的变更全部移出该分支（通过上面的 stash/rescue 方式保留，不在本分支提交）。

### P1：清理构建产物与临时目录
- `AutoCode-a4` 清理 `.gradle-local/`。
- `AutoCode-agent2` 清理 `control-plane-spring/build/`。
- 持续要求：提交前 `git status --short` 必须干净，且不提交构建目录。

### P1：处理 `AutoCode-a1` 当前两处测试改动
- 二选一：
  - 若为计划内 M3/M4 准备改动：单独提交到对应新分支。
  - 若为临时调试：还原，确保 worktree 干净。

## 4. PR 任务规划更新（2026-04-03）

## 4.1 已完成（可归档）
- M1：Agent-2 / Agent-1 / Agent-3 已完成并合入。
- M2：Agent-2 / Agent-1 / Agent-3 已完成并合入。
- M5：PR-1、PR-2 已合入。

## 4.2 进行中
- M5：`feat/a4-mobile-visual-app`（PR-3）
  - 当前状态：ahead=1（待合入）。
  - 范围：`mobile-app/**`。
  - 备注：提交内容与 Agent-4 白名单一致。

## 4.3 待创建/续做 PR（更新后）
1. `fix/a1-m3-runtime-metadata-authz`
- 负责人：Agent-1
- 目标：控制面对 runtime metadata 的校验/透传与权限语义（非成员 404）。
- 白名单：`control-plane-spring/src/main/**`、`control-plane-spring/src/test/**`
- 验收：`mvn -pl shared-protocol,control-plane-spring -am test`

2. `fix/a3-m3-minimal-run-health-reporting`
- 负责人：Agent-3
- 目标：本地 run/health 最小闭环上报，与协议对齐。
- 白名单：`pc-agent-java/src/main/**`、`pc-agent-java/src/test/**`、`pc-agent-java/pom.xml`
- 验收：`mvn -pl shared-protocol,pc-agent-java -am test`

3. `fix/a2-m4-deploy-plan-result-payloads`
- 负责人：Agent-2
- 目标：部署请求/部署结果 payload（v1 兼容）与校验样例。
- 白名单：`shared-protocol/**`（按原文档约束）
- 验收：`mvn -pl shared-protocol test`

4. `fix/a1-m4-deploy-authz-audit-state`
- 负责人：Agent-1
- 目标：部署权限/审计/状态机推进，非成员不可探测。
- 白名单：`control-plane-spring/src/main/**`、`control-plane-spring/src/test/**`
- 验收：`mvn -pl shared-protocol,control-plane-spring -am test`

5. `fix/a3-m4-deploy-gate-execution-reporting`
- 负责人：Agent-3
- 目标：部署执行与审批门禁联动，上报部署结果。
- 白名单：`pc-agent-java/src/main/**`、`pc-agent-java/src/test/**`、`pc-agent-java/pom.xml`
- 验收：`mvn -pl shared-protocol,pc-agent-java -am test`

## 5. 合并顺序（更新）
1. 先完成“工作区修复动作”（第 3 节），确保无串线与无构建垃圾。
2. 合并 M5 PR-3：`feat/a4-mobile-visual-app`。
3. 合并 M3 剩余：`a1` -> `a3`。
4. 合并 M4：`a2` -> `a1` -> `a3`。
5. 每次合并后执行对应模块回归，最后执行总门禁。

## 6. 总门禁（保持不变）
- `git status --short` 干净。
- `mvn -B -q -pl shared-protocol,control-plane-spring,pc-agent-java -am test`
- 移动端模块内执行构建/测试并完成一次端到端手动流程。
