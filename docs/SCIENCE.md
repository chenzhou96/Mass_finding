# 科学计算与数据契约（v2）

## 质量、单位与离子

`m2z` 是观测质荷比，单位 Th（Da/e）；`molecular_weight` 是候选中性单同位素质量，单位 Da。字段名为兼容原有 JSON 保留，并不表示平均分子量。PubChem 的 MolecularWeight 字段通常为平均分子量，详情中单独显示，不混入候选匹配计算。

质量表采用 NIST 同位素质量：H1/C12/N14/O16/F19/Si28/P31/B11/S32/Cl35/Br79/Se80/I127。来源为 [NIST Atomic Weights and Isotopic Compositions](https://physics.nist.gov/cgi-bin/Compositions/stand_alone.pl)（如 [H](https://physics.nist.gov/cgi-bin/Compositions/stand_alone.pl?ele=H)）。表内不是天然丰度加权平均值；不提供自定义同位素标记或完整同位素分布拟合。

离子质量采用固定版本 [CODATA 2018 常数表](https://physics.nist.gov/cuu/Constants/ArchiveASCII/allascii_2018.txt)：质子 `p = 1.007276466621 Da`，电子 `e = 0.000548579909065 Da`。这是有追溯的 2018 数值，不宣称是最新 CODATA 版本。表版本随每次新结果导出。

| 模式 / 加合标签 | 单电荷质量偏移 δ | 解释 |
| --- | --- | --- |
| ESI+ H+ | p | [M+H]+ |
| ESI+ Na+ / K+ | 中性 Na23 / K39 − e | [M+Na]+ / [M+K]+ |
| ESI+ NH4+ | N14 + 3×H1 + p | [M+NH4]+ |
| ESI+ H3O+ | O16 + 2×H1 + p | [M+H3O]+ |
| ESI− H− | −p | [M−H]−（去质子化，并非加入氢负离子） |
| ESI− Cl− / HCOO− / CH3COO− | 对应中性元素质量和 + e | 阴离子加合 |
| EI+ e+ | −e | [M]+，移去一个电子 |
| EI− e− | +e | [M]−，增加一个电子 |

`M = |z| × (observed_mz − δ)`，`predicted_mz = M / |z| + δ`。当 |z| > 1 时只允许 H+ / H−，明确表示逐个质子化/去质子化。其它加合物只支持 |z|=1；没有假设每个电荷都自动增加一个 Na/NH4。混合加合、二聚体、碎片损失、不明电荷态及任意带电元素式不属于此模型。

原子质量相加是常规质量模型，不显式修正每种化学结合能，也不包含仪器校准、峰挑选误差、同位素包络或 MS/MS 信息。导出很多小数位是保留数值追溯，不能解释为测量精度或结构置信度。

## 误差与枚举

```
tolerance_Th = max(observed_mz × error_pct / 100, error_da)
tolerance_Da = |z| × tolerance_Th
error_Th = predicted_mz − observed_mz
error_ppm = error_Th / observed_mz × 1e6
```

`error_pct=0.0005` 是 5 ppm。兼容字段 `error_da` 的输入含义是 m/z 窗口（Th），不是中性质量窗口。两窗口取较大值、闭区间包含端点；均为零时仍可用于精确合成真值。枚举和最终求和采用 `math.fsum`/16 个 ULP 的数值端点保护，解决重排求和及整数裁剪造成的端点漏式；不会人为增加一个固定 Da 容差。

元素上限 `0` 或缺项表示不选；`-1` 为不限，但由质量预算得到有限上界。H 与其它元素具有相同的显式约束，H=0 不会隐式恢复不限。为兼容 v1 Tk 导出，旧文件未记录 H 时，入口会以旧约定恢复 H 不限并标记为历史结果；引擎 v2 契约始终以缺 H=0 解释。

DFS 按质量递减枚举非 H 元素，最后由窗口求出 H 整数范围。每次搜索最多 2,000,000 DFS 节点；每个模型及所有模型合计最多 25,000 候选。超限和取消是明确错误/取消状态，不能作为“无匹配”或完整候选集。输入边界见 README；所有数值拒绝 NaN/Infinity/布尔值，电荷与元素计数拒绝小数或非法负数。

DBE 筛选：`(2×(C+Si) + 2 + (N+P+B) − (H+F+Cl+Br+I))/2`；默认要求非负整数。该假设适用于选定典型价态的中性闭壳层候选，并非完整化学价态验证。高价 P/S、SF6 等无机结构及部分自由基可被误排；开关关闭后质量合格候选仍显示原 DBE（可以为负/半整数），不增加结构可存在的保证。

## PubChem 完整性与排序

数据来源是 [PubChem PUG REST](https://pubchem.ncbi.nlm.nih.gov/docs/pug-rest) 及可选 PubChemPy 备用路径。属性和同义词分别追踪已成功 CID、缺口及失败批次；合法空同义词数组与拉取失败不同。缺 CID、非法 CID 或不在请求范围的响应拒收，不以数组位置猜身份。备用路径补拉失败也保留 partial；不允许部分结果时严格返回失败。

部分成功保留已得到属性和同义词，后续重试只补缺口。JSON 元数据含 status、batch_summary、failed_batches；缓存离线重排不得把 partial 改写为完整成功。单个记录的 `properties_complete` / `synonyms_complete` 区分属性与同义词缺口，旧缓存未记完整性时保持已有信息并依据明确缺口补拉。

排序是记录字段质量、同义词/关键词及规则化离子化指标的组合。启发分没有通过真实鉴定样本校准成概率，不是实验丰度、真实引用次数或结构鉴定置信度。完整响应仅说明本次请求响应无已知缺口；不能保证数据库包含所有匹配同分异构体。严格筛选排除同位素与多共价单元记录，原始缓存仍保留以支持复核。

## 保存和迁移

新生成 JSON 与 CSV 保存完整输入、离子模型、引擎/质量表版本、窗口规则和未预先舍入的质量与误差。JSON 保留原 `input_params/results/calculated_properties` 结构；CSV 兼容原列并追加离子模型和偏差。显示精度设置不改导出。历史文件保留当时结果；打开不自动把旧质量表的数值伪装为 v2 重算结果。

独立真值测试不通过待测函数产生期望质量；使用硬编码来源常数、已知乙醇/SF6 与独立笛卡尔枚举，并覆盖所有加合类型、不同电荷、包含端点与非法值。详见 `tests/test_scientific_engine.py` 和验证记录。
