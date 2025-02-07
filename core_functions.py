import time
import csv
import re
import os
import winreg  # 用于获取Windows桌面路径
from tkinter import messagebox
import tkinter as tk

# ---------------------------- 常量定义 ----------------------------
ATOMIC_WEIGHTS = {
    'H': 1.007825, 'C': 12.000000, 'N': 14.003074, 'O': 15.994915,
    'F': 18.998403, 'Si': 27.976927, 'P': 30.973762, 'B': 11.009305,
    'S': 31.972071, 'Cl': 34.968853, 'Br': 78.918338, 'Se': 79.916521,
    'I': 126.904473,
}

ION_WEIGHTS = {
    'e+': 0.0000, 'e-': 0.0000,
    'Na+': 22.989769, 'K+': 38.963707, 'H3O+': 19.01839, 'NH4+': 18.034374,
    'H+': 1.007825, 'H-': -1.007825, 'Cl-': 34.968853, 'HCOO-': 44.997655,
    'CH3COO-': 59.013305,
}

ADDUCTS = {
    'ESI+': {
        'H+': ION_WEIGHTS['H+'],
        'H3O+': ION_WEIGHTS['H3O+'],
        'NH4+': ION_WEIGHTS['NH4+'],
        'Na+': ION_WEIGHTS['Na+'],
        'K+': ION_WEIGHTS['K+']
    },
    'ESI-': {
        'H-': ION_WEIGHTS['H-'],
        'Cl-': ION_WEIGHTS['Cl-'],
        'HCOO-': ION_WEIGHTS['HCOO-'],
        'CH3COO-': ION_WEIGHTS['CH3COO-'],
    },
    'EI+': {
        'e+': ION_WEIGHTS['e+'],
    },
    'EI-': {
        'e-': ION_WEIGHTS['e-'],
    },
}

# ---------------------------- 类定义 ----------------------------
class ChemicalFormula:
    """存储和验证化学分子式的类"""

    def __init__(self):
        self.elements = {
            'H': 0, 'F': 0, 'Cl': 0, 'Br': 0, 'I': 0,
            'B': 0, 'N': 0, 'P': 0,
            'C': 0, 'Si': 0,
            'O': 0, 'S': 0, 'Se': 0,
        }
        self.valency_1 = 0   # 单价元素总原子数
        self.valency_3 = 0   # 三价元素总原子数
        self.valency_4 = 0   # 四价元素总原子数
        self.dbr = 0.0       # 不饱和度
        self.even = False    # 不饱和度是否为整数
        self.predicted_mw = 0.0  # 预测分子量

    def validate_valency(self) -> bool:
        """
        验证分子式的化合价规则
        返回: bool - 是否通过验证
        """
        # 计算各价态元素总数
        self.valency_1 = sum(self.elements[e] for e in ['H', 'F', 'Cl', 'Br', 'I'])
        self.valency_3 = sum(self.elements[e] for e in ['B', 'N', 'P'])
        self.valency_4 = sum(self.elements[e] for e in ['C', 'Si'])

        # 计算不饱和度
        self.dbr = (2 * self.valency_4 + 2 + self.valency_3 - self.valency_1) / 2
        if self.dbr < 0:
            return False

        # 检查不饱和度是否为整数
        self.even = ((self.dbr * 2) % 2) == 0
        return self.even

    def calculate_molecular_weight(self) -> float:
        """计算预测分子量"""
        self.predicted_mw = sum(
            ATOMIC_WEIGHTS[element] * count
            for element, count in self.elements.items()
        )
        return self.predicted_mw


# ---------------------------- 核心算法函数 ----------------------------
def get_desktop_path() -> str:
    """
    获取Windows桌面路径
    返回: str - 桌面绝对路径
    """
    try:
        # 通过注册表获取准确路径
        with winreg.OpenKey(
            winreg.HKEY_CURRENT_USER,
            r'Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders'
        ) as key:
            desktop_path, _ = winreg.QueryValueEx(key, 'Desktop')
            return os.path.expandvars(desktop_path)
    except Exception:
        # 回退到环境变量获取
        return os.path.join(os.environ['USERPROFILE'], 'Desktop')


def parse_elements(input_str: str) -> list:
    """
    解析元素输入字符串
    参数:
        input_str (str): 用户输入的元素字符串
    返回:
        list: 包含(元素符号, 原子量)的列表，按原子量降序排列
    """
    element_order = [
        ('I', 126.904473), ('Br', 78.918338), ('Se', 79.916521),
        ('S', 31.972071), ('Cl', 34.968853), ('P', 30.973762),
        ('Si', 27.976927), ('F', 18.998403), ('O', 15.994915),
        ('N', 14.003074), ('C', 12.000000), ('B', 11.009305)
    ]

    if input_str.lower() == 'all':
        return element_order

    # 清洗输入并分割元素符号
    cleaned = re.sub(r'[^a-zA-Z]', '', input_str)
    elements = re.findall(r'[A-Z]?[a-z]+|[A-Z]', cleaned)
    
    return [item for item in element_order if item[0] in elements]


def backtrack_search(target_mw: float, tolerance: float, elements: list) -> list:
    """
    回溯算法搜索可能的分子式组合
    参数:
        target_mw (float): 目标分子量
        tolerance (float): 允许的误差范围
        elements (list): 可用的元素列表
    返回:
        list: 符合条件的ChemicalFormula对象列表
    """
    mw_min = target_mw - target_mw * tolerance
    mw_max = target_mw + target_mw * tolerance
    h_weight = ATOMIC_WEIGHTS['H']
    results = []

    def dfs(index, remaining_mw, counts):
        """深度优先搜索递归函数"""
        if index == len(elements):
            # 计算氢原子数量
            h_count = round(remaining_mw / h_weight)
            formula = ChemicalFormula()
            
            # 设置各元素数量
            for (elem, _), count in zip(elements, counts):
                formula.elements[elem] = count
            formula.elements['H'] = h_count

            # 验证并计算分子量
            if formula.validate_valency():
                mw = formula.calculate_molecular_weight()
                if mw_min < mw < mw_max:
                    results.append(formula)
            return

        current_elem, elem_weight = elements[index]
        max_count = int(remaining_mw / elem_weight)

        # 剪枝优化：从大到小尝试原子数量
        for count in range(max_count, -1, -1):
            new_remaining = remaining_mw - count * elem_weight
            current_total = target_mw - new_remaining
            
            # 提前终止条件
            if current_total > mw_max:
                continue  # 当前总和已超过上限
            if current_total + new_remaining < mw_min:
                continue  # 剩余部分无法达到下限
            
            dfs(index + 1, new_remaining, counts + [count])

    dfs(0, target_mw, [])
    return results


def validate_inputs(ms_mode: str, m2z: str, error_pct: str, charge: str, elements: str):
    """验证用户输入参数有效性"""
    errors = []
    
    if ms_mode not in ADDUCTS:
        errors.append("质谱模式必须是 ESI+/ESI-/EI+/EI-")
    if not m2z.replace('.', '', 1).isdigit() or float(m2z) <= 0:
        errors.append("质荷比必须为正数")
    if not error_pct.replace('.', '', 1).isdigit() or not 0 < float(error_pct) < 100:
        errors.append("误差百分比必须在0-100之间")
    if not charge.isdigit() or int(charge) <= 0:
        errors.append("电荷数必须为正整数")
    if not elements.strip():
        errors.append("元素范围不能为空")
    
    if errors:
        raise ValueError("\n".join(errors))

def start_analysis(input_data, output_widget):
    try:
        # 解析输入数据
        ms_mode = input_data["ms_mode"]
        m2z = input_data["m2z"]
        error_pct = input_data["error_pct"]
        charge = input_data["charge"]
        elements = input_data["elements"]

        # 验证输入
        validate_inputs(ms_mode, m2z, error_pct, charge, elements)

        # 转换数据类型
        m2z = float(m2z)
        error = float(error_pct) / 100
        charge = int(charge)

        output_widget.delete(1.0, tk.END)  # 清空输出框
        output_widget.insert(tk.END, "开始分析...\n")

        # 执行核心计算
        start_time = time.time()
        results = {}
        molecular_weights = calculate_molecular_weights(ms_mode, m2z, charge)

        for adduct, base_mw in molecular_weights.items():
            formulas = backtrack_search(base_mw, error, parse_elements(elements))
            if formulas:
                results[adduct] = formulas

        # 生成结果文件
        if results:
            save_to_csv(results, input_data, charge)
            output_widget.insert(tk.END,
                f"分析完成！耗时 {time.time() - start_time:.2f}秒\n"
                f"结果已保存到桌面: {csv_path}\n"
            )
        else:
            output_widget.insert(tk.END, "未找到符合条件的分子式\n")

    except Exception as e:
        messagebox.showerror("错误", str(e))

# def start_analysis(entries, output_widget):
#     """分析按钮点击事件处理"""
#     try:
#         # 获取并验证输入参数
#         params = {
#             'ms_mode': entries['entry_0'].get().strip(),
#             'm2z': entries['entry_1'].get(),
#             'error_pct': entries['entry_2'].get(),
#             'charge': entries['entry_3'].get(),
#             'elements': entries['entry_4'].get().strip()
#         }
#         validate_inputs(**params)

#         # 转换数据类型
#         m2z = float(params['m2z'])
#         error = float(params['error_pct']) / 100
#         charge = int(params['charge'])
        
#         output_widget.delete(1.0, tk.END)  # 清空输出框
#         output_widget.insert(tk.END, "开始分析...\n")
#         output_widget.update_idletasks()  # 立即更新界面

#         # 执行核心计算
#         start_time = time.time()
#         results = {}
#         molecular_weights = calculate_molecular_weights(params['ms_mode'], m2z, charge)
        
#         for adduct, base_mw in molecular_weights.items():
#             formulas = backtrack_search(base_mw, error, parse_elements(params['elements']))
#             if formulas:
#                 results[adduct] = formulas

#         # 生成结果文件
#         if results:
#             save_to_csv(results, params, charge)
#             output_widget.insert(tk.END, 
#                 f"分析完成！耗时 {time.time()-start_time:.2f}秒\n"
#                 f"结果已保存到桌面: {csv_path}\n"
#             )
#         else:
#             output_widget.insert(tk.END, "未找到符合条件的分子式\n")

#     except Exception as e:
#         messagebox.showerror("错误", str(e))


def calculate_molecular_weights(ms_mode: str, m2z: float, charge: int) -> dict:
    """计算不同加合方式对应的分子量"""
    return {
        adduct: m2z * charge - ion * charge
        for adduct, ion in ADDUCTS[ms_mode].items()
    }


def save_to_csv(results: dict, params: dict, charge: int):
    """将结果保存到CSV文件"""
    desktop = get_desktop_path()
    timestamp = int(time.time())
    global csv_path
    csv_path = os.path.join(desktop, f'mass_data_{timestamp}.csv')

    with open(csv_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            f"ms_mode: {params['ms_mode']}", f"m/z: {params['m2z']}",
            f"error: {params['error_pct']}%", f"charge: {params['charge']}",
            f"elements: {params['elements']}"
        ])
        writer.writerow([
            'C', 'H', 'O', 'N', 'S', 'P', 'Si', 'B', 'Se',
            'F', 'Cl', 'Br', 'I', 'ion', 'dbr', 'p_m/z'
        ])

        for adduct, formulas in results.items():
            for formula in formulas:
                mz = (formula.predicted_mw + charge * ADDUCTS[params['ms_mode']][adduct]) / charge
                writer.writerow([
                    formula.elements['C'], formula.elements['H'],
                    formula.elements['O'], formula.elements['N'],
                    formula.elements['S'], formula.elements['P'],
                    formula.elements['Si'], formula.elements['B'],
                    formula.elements['Se'], formula.elements['F'],
                    formula.elements['Cl'], formula.elements['Br'],
                    formula.elements['I'], adduct,
                    f"{formula.dbr:.1f}", f"{mz:.4f}"
                ])