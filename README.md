# MASS FINDING

一个用于处理质谱（MS）数据并给出可能化学分子式的软件工具。

## 功能概述
- 根据质谱模式（如ESI+、ESI-、EI+、EI-）和质谱峰（质荷比m/z），结合误差范围和电荷数，计算可能的分子量。
- 根据目标分子量和误差范围，搜索所有满足条件的化学式组合。
- 支持多种元素搜索范围（如`all`、`CHONSPCl`等），并考虑化合价规律和不饱和度。
- 将结果输出为CSV文件，包含可能的化学式、离子类型、不饱和度（DBR）和预测的质谱峰（m/z）。

## 安装与使用

### 安装依赖
本软件基于Python编写，需要Python环境支持。确保已安装Python 3.7或更高版本。

### 配置参数
在`main.py`中，可以通过修改以下配置参数来自定义分析：

- `MS_MODE`：质谱模式，可选`ESI+`、`ESI-`、`EI+`、`EI-`。
- `M2Z`：质谱峰的质荷比（m/z）。
- `ERROR_PERCENT`：误差范围（以百分比表示）。
- `CHARGE`：电荷数。
- `ELEMENTS`：元素搜索范围，可选`all`或指定元素组合（如`CHONSPCl`）。

### 运行程序
直接运行`main.py`文件即可启动分析。程序会根据配置参数计算可能的化学分子式，并将结果保存为CSV文件。

```bash
python main.py
```

## 输出结果
程序运行完成后，会在当前目录下生成一个以时间戳命名的CSV文件，例如`ms_data_1678901234.csv`。文件内容包含以下列：
- 配置参数（`ms_mode`、`m/z`、`error`、`z`、`ELEMENTS`）
- 化学式元素组成（`C`、`H`、`O`、`N`、`S`、`P`、`Si`、`B`、`Se`、`F`、`Cl`、`Br`、`I`）
- 离子类型（`ion`）
- 不饱和度（`dbr`）
- 预测的质谱峰（`p_mw`）

### 示例
假设配置参数如下：
```python
MS_MODE = 'ESI+'
M2Z = 100
ERROR_PERCENT = 0.1
CHARGE = 1
ELEMENTS = 'CHONSP'
```
运行程序后，可能会生成类似以下内容的CSV文件：
|C|H|O|N|S|P|Si|B|Se|F|Cl|Br|I|ion|dbr|p_mw|
|-|-|-|-|-|-|-|-|-|-|-|-|-|-|-|-|
|3|8|1|0|0|0|0|0|0|0|0|0|0|H+|1.0|100.08|
|2|6|2|0|0|0|0|0|0|0|0|0|0|H+|0.0|100.06|

## 注意事项
- 当`ELEMENTS`设置为`all`时，计算范围较大，可能导致运行时间较长，建议根据实际需求选择合适的元素范围。
- 程序的运行时间与质荷比、元素范围和误差范围有关，较大的质荷比和较宽的元素范围可能导致更长的运行时间。
- 生成的CSV文件名包含时间戳，避免文件名冲突。

## 贡献与反馈
欢迎提出改进建议或报告问题。可以通过以下方式与我们联系：  
- 提交[Issue](https://github.com/chenzhou96/2D_NMR_learning)
- 提交[Pull Request](https://github.com/chenzhou96/2D_NMR_learning/pulls)
- zhouchen96@126.com

##  版权声明
本软件由[Zhou Chen](https://github.com/chenzhou96)开发，遵循`GNU General Public License v3.0`。