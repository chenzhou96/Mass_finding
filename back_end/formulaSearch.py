import json
import time
import logging
import requests
from public import ExporterFactory
from enum import Enum

class Status(Enum):
    SUCCESS = 1
    NO_COMPOUNDS_FOUND = 2
    SEARCH_FAILED = 3

class FormulaSearch:
    def __init__(self):
        self.max_retries = 1
        self.retry_delay = 10  # 秒
        self.status = Status.SUCCESS

    def get_compounds(self, formula: str):
        # 尝试多次执行查询
        for attempt in range(self.max_retries):
            try:
                # 尝试获取匹配给定公式的化合物信息
                compounds = self._fetch_compounds(formula)
                # 如果没有找到匹配的化合物，设置状态并返回None
                if not compounds:
                    logging.warning(f"{formula} 未匹配到任何化合物")
                    self.status = Status.NO_COMPOUNDS_FOUND
                    return None
                # 如果成功获取化合物信息，记录成功信息并返回结果
                logging.info(f"成功获取匹配 {formula} 的化合物信息")
                self.status = Status.SUCCESS
                return compounds
            except requests.exceptions.RequestException as e:
                # 如果查询过程中出现HTTP错误，记录错误信息并尝试重试
                logging.warning(f"{formula} HTTP请求失败: {e}")
                logging.info(f"第 {attempt+1} 次重试...")
                time.sleep(self.retry_delay)
            except json.JSONDecodeError as e:
                # 如果解析JSON时出错，记录错误信息并尝试重试
                logging.warning(f"{formula} 搜索请求返回无效JSON: {e}")
                logging.warning(f"可能与短时间内重复搜索 {formula} 数据有关")
                logging.info(f"第 {attempt+1} 次重试...")
                time.sleep(self.retry_delay)

        # 如果超过最大重试次数仍未成功，设置状态并返回None
        logging.error(f"超过最大重试次数，{formula} 搜索失败")
        self.status = Status.SEARCH_FAILED
        return None

    def _fetch_compounds(self, formula: str):
        # 这个方法需要在子类中实现
        raise NotImplementedError("This method should be overridden by subclasses")

class FormulaSearch_PubChem(FormulaSearch):
    def _fetch_compounds(self, formula: str):
        # 尝试获取匹配给定公式的化合物信息
        import pubchempy as pcp
        return pcp.get_compounds(formula, 'formula')

class FormulaSearch_ChemSpider(FormulaSearch):
    def _fetch_compounds(self, formula: str):
        # 这里可以添加ChemSpider的查询逻辑
        raise NotImplementedError("ChemSpider search logic not implemented yet")

class SearchManager:
    def __init__(self, formula_search_instance: FormulaSearch, exporter_name: str):
        self.formula_search_instance = formula_search_instance
        self.exporter_name = exporter_name

    def search_formula_list(self, formula_list: list):
        # 输入参数为一个包含化学式的列表，列表每个元素都是string类型
        
        if not formula_list:
            logging.warning("未识别到任何化学式")
            return {}

        results = {}
        exporter = ExporterFactory.get_exporter(self.exporter_name)

        for formula in formula_list:
            try:
                # 尝试获取化学式对应的化合物
                logging.info(f"正在处理 {formula}")
                compounds = self.formula_search_instance.get_compounds(formula)
                # 根据状态进行处理
                if self.formula_search_instance.status == Status.SUCCESS:
                    results[formula] = exporter.export((formula, compounds))
            except Exception as e:
                # 如果发生异常，记录错误信息
                logging.error(f"处理化学式 {formula} 时发生未知错误: {e}", exc_info=True)

        # 如果没有找到任何化合物，抛出异常
        if not results:
            raise ValueError("选择的化学式都未找到任何化合物")

        return results

def start_search(formula_list: list, web_name: str) -> dict:
    # 将 web_name 转换为小写以便不区分大小写比较
    web_name_lower = web_name.lower()

    # 初始化 formula_search_instance 和 exporter_name
    formula_search_instance = None
    exporter_name = None

    # 检查 web_name 中是否包含 pubchem
    if 'pubchem' in web_name_lower:
        formula_search_instance = FormulaSearch_PubChem()
        exporter_name = 'json_formulaSearch_PubChem'
    # 检查 web_name 中是否包含 chemspider
    elif 'chemspider' in web_name_lower:
        formula_search_instance = FormulaSearch_ChemSpider()
        exporter_name = 'json_formulaSearch_ChemSpider'
    else:
        # 如果 web_name 不匹配任何已知的关键词，可以抛出异常或设置默认值
        raise ValueError(f"未知的 web_name: {web_name}")

    # 创建 CompoundSearchManager 实例
    compound_search_manager = SearchManager(formula_search_instance, exporter_name)
    # 搜索化学式列表
    results = compound_search_manager.search_formula_list(formula_list)

    return results

# 示例调用
if __name__ == "__main__":
    # 配置日志记录
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

    # 一些示例化学式
    formula_list = ["C6H12", "C6H8O", "C6H14O2"]

    # 示例 web_name
    web_name = "PubChem"

    # 调用 start_search 函数
    results = start_search(formula_list, web_name)
    print(results)