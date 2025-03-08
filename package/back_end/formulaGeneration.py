import os
import time
import logging
import concurrent.futures
from concurrent.futures import ProcessPoolExecutor
from ..back_end.public import ExporterFactory
from pathlib import Path
from ..back_end.public import ConfigManager

# ---------------------------- 类定义 ----------------------------
class ChemicalFormula:
    def __init__(self, atomic_weights, element_categories):
        self.elements = {elem: 0 for elem in atomic_weights.keys()}
        self.atomic_weights = atomic_weights
        self.element_categories = element_categories

    def validate_valency(self) -> bool:
        valency_1 = sum(self.elements[e] for e in self.element_categories['valency_1'])
        valency_3 = sum(self.elements[e] for e in self.element_categories['valency_3'])
        valency_4 = sum(self.elements[e] for e in self.element_categories['valency_4'])

        self.dbr = (2 * valency_4 + 2 + valency_3 - valency_1) / 2
        if self.dbr < 0:
            return False

        self.even = ((self.dbr * 2) % 2) == 0
        return self.even

    def calculate_molecular_weight(self) -> float:
        self.predicted_mw = sum(
            self.atomic_weights[element] * count
            for element, count in self.elements.items()
        )
        return self.predicted_mw

# ---------------------------- 核心算法函数 ----------------------------
def parse_elements(elements: dict, atomic_weights: dict) -> list:
    processed = elements.copy()
    
    # 智能处理氢元素配置
    if 'H' not in processed:
        processed['H'] = -1  # 默认允许氢原子
    elif processed['H'] == 0:
        del processed['H']   # 完全禁用氢原子
        
    elements_order = []
    for elem, max_count in processed.items():
        if elem not in atomic_weights:
            logging.warning(f"元素 {elem} 不在原子量表中，已忽略。")
            continue
        if max_count == 0:
            continue
            
        # 将氢元素放在最后处理
        if elem == 'H':
            continue
            
        processed_max = float('inf') if max_count == -1 else max_count
        elements_order.append((elem, atomic_weights[elem], processed_max))
    
    # 按原子量降序排列（排除氢）
    elements_order.sort(key=lambda x: x[1], reverse=True)
    
    # 添加氢元素配置（如果允许）
    if 'H' in processed:
        h_max = float('inf') if processed['H'] == -1 else processed['H']
        elements_order.append(('H', atomic_weights['H'], h_max))
    
    return elements_order

def backtrack_search(target_mw: float, tolerance: float, elements: list, atomic_weights: dict, element_categories: dict) -> list:
    mw_min = target_mw - target_mw * tolerance
    mw_max = target_mw + target_mw * tolerance
    h_weight = atomic_weights['H']
    results = []
    
    # 从配置中获取氢元素的最大数量限制（默认无限制）
    h_max = next((elem[2] for elem in elements if elem[0] == 'H'), float('inf')) if any(e[0] == 'H' for e in elements) else float('inf')

    def dfs(index, remaining_mw, counts):
        if index == len(elements):
            # 计算氢原子数量（四舍五入）
            h_count = round(remaining_mw / h_weight)
            
            # 检查氢原子数量限制
            if h_count < 0 or h_count > h_max:
                return

            # 创建分子式对象
            formula = ChemicalFormula(atomic_weights, element_categories)
            
            # 设置其他元素数量
            for (elem, _, _), count in zip(elements, counts):
                formula.elements[elem] = count
                
            # 设置氢原子数量
            formula.elements['H'] = h_count

            # 验证化合价和分子量范围
            if formula.validate_valency():
                actual_mw = formula.calculate_molecular_weight()
                if mw_min < actual_mw < mw_max:
                    results.append(formula)
            return

        # 当前处理的元素信息
        current_elem, elem_weight, max_count = elements[index]
        
        # 计算当前元素的最大可能数量（考虑重量和用户限制）
        max_possible = min(
            int(remaining_mw / elem_weight),  # 根据剩余质量计算
            max_count  # 用户设置的最大数量
        )
        
        # 剪枝：无效范围
        if max_possible < 0:
            return
        
        # 反向遍历优化搜索效率
        for count in range(max_possible, -1, -1):
            new_remaining = remaining_mw - count * elem_weight
            used_mass = target_mw - new_remaining
            
            # 提前剪枝条件
            if used_mass > mw_max: 
                continue
            if used_mass + new_remaining < mw_min:
                continue
                
            dfs(index + 1, new_remaining, counts + [count])

    dfs(0, target_mw, [])
    return results

# ---------------------------- 入口函数 ----------------------------
def start_analysis(input_data: dict) -> dict:
    try:
        script_dir = Path(__file__).resolve().parent
        config_path = script_dir.joinpath('config.json')

        # 加载配置
        config_manager = ConfigManager(config_path)


        ms_mode = input_data["ms_mode"]
        m2z = float(input_data["m2z"])
        error = float(input_data["error_pct"]) / 100
        charge = int(input_data["charge"])
        elements = input_data["elements"]

        # 分离不限和有限的元素
        unlimited_elements = [elem for elem, count in elements.items() if count == -1]
        limited_elements = [f"{elem}<={count}个" for elem, count in elements.items() if count > 0]

        # 构建元素配置字符串
        element_config_parts = []
        if unlimited_elements:
            element_config_parts.append(f"{', '.join(unlimited_elements)}不限个数")
        if limited_elements:
            element_config_parts.append(', '.join(limited_elements))

        element_config_str = '; '.join(element_config_parts)

        start_time = time.time()
        ion_weights = config_manager.config['ion_weights']
        adducts = config_manager.config['adducts']

        # 获取用户指定的离子类型（默认为空）
        selected_adducts = input_data.get("adduct_model", [])
        if not selected_adducts:
            logging.warning("未选择任何离子类型。")
            return

        molecular_weights = {}
        for adduct, ion in adducts[ms_mode].items():
            if adduct in selected_adducts:  # 只处理选中的离子类型
                molecular_weights[adduct] = (m2z - ion_weights[ion]) * charge

        results = {
            "input_params": {
                **input_data,
                "adduct_model": selected_adducts  # 记录实际使用的离子类型
            },
            "formulas": {}
        }

        logging.info(f"开始分析, 参数如下...")
        logging.info(f"质谱模式: {ms_mode}")
        logging.info(f"加合离子: {', '.join(selected_adducts)}")
        logging.info(f"m/z: {m2z}")
        logging.info(f"误差范围: ±{error * 100:.4f}%")
        logging.info(f"电荷数: {charge}")
        logging.info(f"元素配置: {element_config_str}")

        p_elements = parse_elements(elements, config_manager.config['atomic_weights'])

        # 使用 ProcessPoolExecutor 并发执行 backtrack_search
        max_workers = max(1, os.cpu_count() // 2)  # 根据实际情况调整最大工作进程数
        with ProcessPoolExecutor(max_workers=max_workers) as executor:
            futures = {}
            for adduct, base_mw in molecular_weights.items():
                if base_mw > 0:
                    future = executor.submit(backtrack_search, base_mw, error, p_elements, config_manager.config['atomic_weights'], config_manager.config['element_categories'])
                    futures[future] = adduct

            for future in concurrent.futures.as_completed(futures):
                adduct = futures[future]
                try:
                    formulas = future.result()
                    if formulas:
                        results["formulas"][adduct] = [  # 按离子类型分组
                            {
                                **formula.__dict__,
                                "mz": (formula.predicted_mw + charge * config_manager.config['ion_weights'][config_manager.config['adducts'][ms_mode][adduct]]) / charge
                            }
                            for formula in formulas
                        ]
                except Exception as e:
                    logging.error(f"backtrack_search for adduct {adduct} failed: {e}")

        # 直接处理结果
        if results["formulas"]:
            csv_exporter = ExporterFactory.get_exporter('csv_formulaGeneration')
            json_exporter = ExporterFactory.get_exporter('json_formulaGeneration')

            try:
                csv_exporter.export(results)
                data_to_save = json_exporter.export(results)
                logging.info(f"分析完成！耗时 {time.time() - start_time:.2f}秒")
                return data_to_save
            except Exception as e:
                logging.error(f"结果导出失败: {e}")
        else:
            logging.warning("未找到符合条件的分子式")

    except Exception as e:
        logging.error(f"分析失败: {e}", exc_info=True)

# ---------------------------- 测试代码 ----------------------------
if __name__ == '__main__':

    # 配置日志记录
    logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

    # 测试实例 1
    input_data_1 = {
        "ms_mode": "ESI+",
        "adduct_model": ["H+", "Na+"],
        "m2z": 100.0,
        "error_pct": 0.1,
        "charge": 1,
        "elements": {
            "C": -1,
            "H": -1,
            "O": -1,
            "N": -1
        }
    }

    # 测试实例 2
    input_data_2 = {
        "ms_mode": "ESI-",
        "adduct_model": ["H-"],
        "m2z": 50.0,
        "error_pct": 0.1,
        "charge": 3,
        "elements": {
            "C": -1,
            "H": -1,
            "O": 2,
            "N": 1
        }
    }

    # 测试实例 3
    input_data_3 = {
        "ms_mode": "EI+",
        "adduct_model": ["e+"],
        "m2z": 200.0,
        "error_pct": 0.05,
        "charge": 1,
        "elements": {
            "C": -1,
            "O": -1,
            "S": 2,
            "P": 1
        }
    }

    # 测试实例 4
    input_data_4 = {
        "ms_mode": "ESI+",
        "adduct_model": ["H3O+"],
        "m2z": 120.0,
        "error_pct": 0.15,
        "charge": 2,
        "elements": {
            "C": -1,
            "H": -1,
            "N": 1
        }
    }

    # 测试实例 5
    input_data_5 = {
        "ms_mode": "ESI+",
        "adduct_model": ["H+", "Na+", "K+", "NH4+", "H3O+"],
        "m2z": 100.0,
        "error_pct": 0.1,
        "charge": 1,
        "elements": {
            "C": -1,
            "H": -1,
            "O": -1,
            "N": -1,
            "S": -1,
            "P": -1,
            "Si": -1,
            "B": -1,
            "Se": -1,
            "F": -1,
            "Cl": -1,
            "Br": -1,
            "I": -1
        }
    }

    # 运行测试实例
    from time import sleep
    logging.info(f"开始测试... from {__file__}")
    logging.info("测试实例 1:")
    start_analysis(input_data_1)
    sleep(1)
    logging.info("测试实例 2:")
    start_analysis(input_data_2)
    sleep(1)
    logging.info("测试实例 3:")
    start_analysis(input_data_3)
    sleep(1)
    logging.info("测试实例 4:")
    start_analysis(input_data_4)
    sleep(1)
    logging.info("测试实例 5:")
    start_analysis(input_data_5)