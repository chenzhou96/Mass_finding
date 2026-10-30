# 2026-10-30 有限维护：统计选择与结构预览一致

基线工作分支 `improve/reagent-ranking-20261016`：`e611df172f83e8cf1f7bcff769c8b702f7cc7b2f`；master：`ebf9277830d6e3797f2fc0146b423b34510a7a1a`。已读取 README、科学/工作台契约、既往维护、最近提交和 PR #2；未发现 MODEL、ROADMAP、TODO 或新增未处理建议。开始时仅有 PR #2 一个开放 draft，无评论或开放问题；远端未新增提交，旧基线的 push/PR CI 均已结束。使用助手自有云端独立 checkout 和单写者锁，无用户电脑操作；不合并、不部署、不强推。

## 修改前复现

原生评分统计中先选择有达阈值候选的 CH4，再选择没有达阈值候选的 H2O，化合物列表变空，但结构图片及双击打开路径仍属于 CH4。选择没有可用统计的分子式还会因提前返回保留旧列表。这是既有选择状态错误，不是历史评分算法回归。

先新增 4 个实际选择处理器的合成回归；修改前全部失败，分别检出旧图片、打开路径或旧列表残留。合成化合物不代表实际结构鉴定或真实配方。

## 有限修复与界面审阅

- 每次切换分子式，先清空当前候选引用、列表、图片引用和打开路径，再显示当前候选；不对统计数据中的列表执行破坏性清空。
- 区分“无达到阈值的候选”“没有可用统计结果”“有候选但结构缺失/不可解析”。不拿上一条结构充当空状态，不隐藏已有的结构解析失败提示。
- 返回有候选的分子式会恢复其列表和首条预览；重复选择、延迟到达的空列表选择事件均不会重新显示旧结构。
- 不修改保存分数、排名、阈值、缓存、质量/离子模型或 PubChem 算法；参考库/未知物识别扩展保持暂停。启发分仍是未经真实样本标定的先验，不是鉴定概率。

实际读取 [Impeccable](https://github.com/pbakaus/impeccable) 的 context、critique、layout、harden 与 craft-floor 工作流；只读指南源版本 `5e745ace7e151feb2a93d360d0281fe39448b857`。context 命令实际运行，确认缺少 PRODUCT/DESIGN，但允许以现有实现为依据进行有限修复；未安装任何设计钩子或修改项目安全设置。另一名只读审阅者独立检查原生 Operate 界面的选择、分组和空状态：保留统计表→候选列表→结构预览的任务路径，不做视觉重设计。

同时按 [Vercel Web Interface Guidelines](https://github.com/vercel-labs/web-interface-guidelines/blob/main/command.md) 可迁移的空状态、内容处理和交互恢复要求检查本次行为；HTML/ARIA、浏览器覆盖层和 web-only detector 不适用于 Tk Python，不以空扫描冒称合规。布局源码未改变；本轮没有新的 Tk 实际像素/键盘/屏幕阅读器验收，不声称完成全应用 UI 审计。没有待用户决策的设计选项，故不发起设计访谈。

## 可复现检查

```sh
python -m unittest discover -s tests -p 'test_score_statistics_selection.py' -v
python -m unittest discover -s tests -p 'test_saved_ranking_snapshots.py' -v
python -m unittest discover -s tests -v
python -m compileall -q package workbench tests
node --check workbench/app.js
node --check tests/browser_workbench.cjs
git diff --check
```

- 基线全量 148 项：本地 145 通过，3 项因无 DISPLAY 报错，与上轮一致。
- 最终 6 个合成选择回归通过；标签替身保存累计配置，模拟实际 Tk，而非只检查最后一次 config 调用。覆盖空、缺失、恢复、重复、延迟事件、不可解析结构以及原列表未被修改。
- 另新增 1 个真实 Tk Treeview 事件/Listbox/Label/PhotoImage 回归，使用既有主线程 fixture 回收契约，交给有显示环境的 CI 执行；不是用合成替身冒称原生交互通过。
- 本地最终全量 155 项中 151 通过，4 个无 DISPLAY 错误（原有 3 个加新 Tk 回归）；没有跳过/删除测试。编译、两份 JS 语法和空白检查通过。
- 精确提交的远端 SHA/tree、Linux/Windows Tk、Windows EXE 构建和 sandbox-enabled Chrome 的实际终态，发布后记录于 PR #2 最新维护段落；本轮不把旧 CI 当作新提交验收。

## 验收边界

云端真实 Tk 控件合同不能替代用户 Windows/macOS 原生鼠标、实际像素、系统文件对话框、安装/签名或干净离线机器验收；本轮未操作这些环境。浏览器源码未改变，本地没有 Chrome；既有真实 Chrome 工作流由精确提交 CI 验证，不关闭沙箱。没有上传私人实验数据、改变安全设置或启动暂停的扩展。本轮只修复上述一个有限问题，检查发布后结束。
