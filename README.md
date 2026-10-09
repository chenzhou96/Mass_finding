# Mass Finding

面向实验室同事的质谱候选分析工具：由实测 **m/z → 中性单同位素质量 → 候选分子式 → PubChem 公开记录**。分子式匹配与启发排序用于初筛，不能替代结构鉴定、谱图或标准品复核。

v2 修正了质子/电子质量、显式 H 上限、闭区间浮点端点与 PubChem 部分响应；保留原生 Tk 流程，并增加共用服务的本机浏览器工作台。

## 启动

在仓库根目录运行，建议 Python 3.12（支持 Python 3.11+）。

```sh
python -m workbench.server
```

打开 **http://127.0.0.1:8866**。浏览器入口的离线候选生成和 PubChem REST 路径仅使用 Python 标准库；无需 Node、前端构建或安装全局工具。服务固定绑定 `127.0.0.1`，没有公开服务或部署步骤。关闭终端任务可停止服务；自定义端口：`python -m workbench.server --port 8867`。

保留的原生入口：

```sh
python -m venv .venv
# macOS/Linux: source .venv/bin/activate
# Windows PowerShell: .venv\Scripts\python.exe 可直接调用，不必修改执行策略
python -m pip install -r requirements.txt
python run.py
```

原生入口需要 Tk 和 Pillow；RDKit 用于结构图、PubChemPy 提供检索备用路径，PyInstaller 用于 Windows 打包。缺 RDKit 时保留文字详情并明确标记结构预览不可用。

## 使用流程

1. 输入 m/z（Th）、离子模式、电荷绝对值与加合物，设置 `%` 和绝对 `Th` 窗口。两个窗口取较大值。
2. 设置元素计数上限：`0` 不选择，`-1` 不限（仍受质量预算约束）。浏览器常见 CHNO 同屏；扩展元素可展开并局部滚动。H 是显式元素，H=0 不会生成含氢分子式。
3. 生成并查看预测 m/z、带符号 ppm 偏差、中性单同位素质量（Da）及 DBE。浏览器按绝对偏差排序、分页并支持局部表格滚动。
4. 选中候选加入 PubChem 队列，或直接输入一个简单中性分子式。缺失字段、部分响应和网络失败均明确标记；失败项保留以便重试。
5. 导出 JSON / CSV 保存完整输入、离子模型、质量表/引擎版本和原始浮点精度。显示小数位只影响表格，不改变导出值。

修改参数会标记此前候选陈旧并禁用发送/导出。重复点击不会并发启动同类任务。枚举可取消；PubChem 取消会抑制回填，已进行的网络请求可能持续至超时。原生仍支持候选筛选、分子式 bus、结构详情、评分统计与缓存重建。

JSON 打开先验证整个文件；取消或失败保留当前输入与结果。历史文件的原始结果不自动重算，浏览器明确提示历史质量表；旧 Tk 文件未声明 H 的隐含不限约定保留，v2 文件缺 H 按零处理。浏览器仅自动保存参数草稿至本机 localStorage，不保存结果。

## 科学约定

- 使用代表性常见同位素的原子质量，不是平均分子量。加合离子与 EI 模型包含电子质量修正，H+/H− 使用明确版本的质子质量。
- `M = |z| × (m/z − 每电荷质量偏移)`。多电荷仅支持 `[M+zH]z+` / `[M−zH]z−`；钠、铵、卤素、EI 等模型只允许单电荷。拒绝含义不明的混合加合/二聚体解释。
- DBE 筛选是可关闭的闭壳层价态启发式；自由基、部分高价 P/S 与无机化合物可能被排除。关闭筛选也不证明候选结构可存在。
- 输入边界：m/z `(0, 3000]` Th，中性质量 `(0, 5000]` Da，电荷 1–10，误差 0–1% / 0–10 Th，元素上限 0–1000 或 -1。允许双零窗口用于精确合成基准。
- 搜索节点和候选有明确上限，超限报错，不把截断列表当完整枚举结果。PubChem 完整响应只指请求数据完整，不保证数据库覆盖所有结构。
- PubChem 启发分包含记录质量、同义词/关键词与离子化指标；**不是鉴定概率**。同义词失败也保持 partial，补拉只重试缺口，不丢失成功记录。

公式、常数来源与精度适用范围见 [科学契约](docs/SCIENCE.md)；界面、API 与取消语义见 [工作台说明](docs/WORKBENCH.md)。

## 测试

```sh
python -m unittest discover -s tests -v
python -m compileall -q package workbench tests
```

真实浏览器测试使用锁定的项目依赖和已安装 Google Chrome，保持浏览器沙箱启用。先启动本机服务，再在另一终端运行：

```sh
npm ci
npm run test:browser
```

测试证据输出至被 Git 忽略的 `test-results/`；`WORKBENCH_EVIDENCE` 可指定输出目录。浏览器 PubChem 部分/失败场景使用明确标记的合成响应；枚举、下载、恢复与视口使用真实 Chrome 和本机服务。测试边界与本次验收结果见 [验证记录](docs/VALIDATION.md)。

## Windows 打包

在安装完整项目依赖的 **Windows 环境** 执行：

```powershell
python -m PyInstaller --noconfirm --clean mass_finding.spec
```

输出 `dist/MassFinding.exe`，为保留 Tk 流程的单文件程序。浏览器入口由源码运行，不被偷偷打包为另一套应用。Windows 冻结程序缓存位于 `%LOCALAPPDATA%/MassFinding/mass_finding_cache`；源码运行缓存位于仓库的 `mass_finding_cache/`。这些运行文件、日志、依赖及打包产物不纳入源码提交。

CI 会在 Linux/Windows 执行科学、服务与桌面合同测试，并尝试 Windows 构建。CI 构建、窗口构造和 macOS 通过均不能替代目标机器原生交互、安装和分发验收。

## 项目结构

| 路径 | 用途 |
| --- | --- |
| `package/service` | 两个入口共用的候选生成、PubChem、完整性与缓存服务 |
| `package/config/chem_element_config.json` | 有版本和来源的同位素/离子质量表 |
| `package/gui` | 保留的 Tk 页面、导航、任务状态和详情 |
| `workbench` | 标准库 loopback HTTP 适配与静态浏览器界面 |
| `tests` | 独立科学真值、PubChem 合成故障、桌面/API/浏览器回归 |
| `docs` | 科学约定、使用与验证边界 |

PubChem 联网仅发送所查询的分子式；弱网、限流或接口变化可能影响可用性。缓存保留部分结果及缺口以便重试，离线重建流程仍可使用已有原始数据。
