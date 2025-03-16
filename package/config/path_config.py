from pathlib import Path

# 自动定位项目根目录（假设根目录包含run.py和.git）
def find_project_root():
    current_path = Path(__file__).resolve()
    while current_path != current_path.parent:
        if (current_path / 'run.py').exists() and (current_path / '.git').exists():
            return current_path
        current_path = current_path.parent
    raise RuntimeError("无法定位项目根目录")

ROOT_DIR = find_project_root()
CONFIG_DIR = ROOT_DIR / "package" / "config"
RESOURCE = ROOT_DIR / "package" / "resources"

CHEM_ELEMENTS_CONFIG_PATH = CONFIG_DIR / "chem_element_config.json"
ICNS_PATH =  RESOURCE / "icon.icns"
IC0_PATH =  RESOURCE / "icon.ico"