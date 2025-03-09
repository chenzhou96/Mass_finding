import logging

class DataValidator:
    def __init__(self):
        # 定义 ms_mode 的可选值
        self.valid_ms_modes = {"ESI+", "ESI-", "EI+", "EI-"}
        # 定义元素的可选值
        self.valid_elements = {"C", "N", "O", "S", "P", "Si", "F", "Cl", "Br", "I", "B", "Se"}

    def validate(self, params):
        # 验证 ms_mode 是否在有效选项中
        if "ms_mode" not in params or params["ms_mode"] not in self.valid_ms_modes:
            logging.error("参数 ms_mode 无效")
            return False

        # 验证 adduct_model 是否为列表且不为空
        if "adduct_model" not in params or not isinstance(params["adduct_model"], list) or not params["adduct_model"]:
            logging.error("参数 adduct_model 无效或为空")
            return False

        # 验证 m2z 是否为正数且小于等于3000
        if "m2z" not in params or not isinstance(params["m2z"], (int, float)) or params["m2z"] <= 0 or params["m2z"] > 3000:
            logging.error("参数 m2z 无效或不在50-3000之间")
            return False

        # 验证 error_pct 是否为正数
        if "error_pct" not in params or not isinstance(params["error_pct"], (int, float)) or params["error_pct"] <= 0:
            logging.error("参数 error_pct 无效")
            return False

        # 验证 charge 是否为正整数
        if "charge" not in params or not isinstance(params["charge"], int) or params["charge"] <= 0:
            logging.error("参数 charge 无效")
            return False

        # 验证 elements 是否为字典且包含有效的元素键
        if "elements" not in params or not isinstance(params["elements"], dict):
            logging.error("参数 elements 无效")
            return False

        for element, count in params["elements"].items():
            if element not in self.valid_elements:
                logging.error(f"元素 {element} 无效")
                return False
            if not isinstance(count, str):
                logging.error(f"元素 {element} 的计数无效（非字符串）")
                return False
            try:
                int(count)  # 允许负数，验证是否为整数
            except ValueError:
                logging.error(f"元素 {element} 的计数无效（非整数）")
                return False

        return True