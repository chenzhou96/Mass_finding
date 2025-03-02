from formulaGeneration import start_analysis
from public import ConfigManager
from pathlib import Path
import logging

# 配置日志记录
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

# 测试案例
if __name__ == "__main__":
    script_dir = Path(__file__).resolve().parent
    config_path = script_dir.joinpath('config.json')

    # 加载配置
    config_manager = ConfigManager(config_path)
    
    input_data = {
        "ms_mode": "ESI+",
        "m2z": 100.0,
        "error_pct": 0.1,
        "charge": 1,
        "elements": ["C", "H", "O", "N", "S", "P", "Si", "B", "Se", "F", "Cl", "Br", "I"]
    }

    start_analysis(input_data, config_manager)