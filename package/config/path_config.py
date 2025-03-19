from pathlib import Path
import platform
import os
import logging

# 自动定位项目根目录（假设根目录包含run.py和.git）
def _find_project_root() -> Path:
    current_path = Path(__file__).resolve()
    while current_path != current_path.parent:
        if (current_path / 'run.py').exists() and (current_path / '.git').exists():
            return current_path
        current_path = current_path.parent
    raise RuntimeError("无法定位项目根目录")

def _get_desktop_path() -> Path:
    system = platform.system()
    if system == "Windows":
        try:
            import winreg
            with winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r'Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders'
            ) as key:
                desktop_path, _ = winreg.QueryValueEx(key, 'Desktop')
                expanded_path = os.path.expandvars(desktop_path)
                return Path(expanded_path)
        except (OSError, Exception) as e:
            logging.warning(f"访问注册表失败！\n报错信息: {e}")
            # 回退到环境变量获取
            user_profile = os.environ.get('USERPROFILE', None)
            if user_profile:
                fallback_path = os.path.join(user_profile, 'Desktop')
                logging.info(f"回退到获取环境变量 USERPROFILE: {fallback_path}")
                return Path(fallback_path)
            else:
                logging.error("USERPROFILE 环境变量未设置，无法获取桌面路径")
                raise EnvironmentError("USERPROFILE environment variable is not set.")
    elif system in ["Darwin", "Linux"]:
        # 对于 macOS 和 Linux，尝试从 HOME 环境变量构建路径
        home = os.environ.get('HOME', None)
        if home:
            return Path(os.path.join(home, 'Desktop'))
        else:
            logging.error("HOME 环境变量未设置，无法获取桌面路径")
            raise EnvironmentError("HOME environment variable is not set.")
    else:
        raise NotImplementedError(f"Unsupported operating system: {system}")
    
def _get_cache_path(parent_path: Path, folder_name: str) -> Path:

    folder_path = parent_path / folder_name

    try:
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
            logging.info(f"没有缓存文件夹: {folder_name}\n已经创建: {str(folder_path)}")
        return folder_path
    except OSError as e:
        logging.error(f"创建文件夹 {folder_name} 失败\n错误信息: {e}")
        raise EnvironmentError(f"Failed to create mass_finding_cache folder: {e}")

class PathManager:
    def __init__(self):
        self.root_dir = _find_project_root()
        self.config_dir = self.root_dir / "package" / "config"
        self.resource = self.root_dir / "package" / "resources"
        self.chem_element_config_path = self.config_dir / "chem_element_config.json"
        self.icns_path = self.resource / "icon.icns"
        self.ico_path = self.resource / "icon.ico"

        self.desktop_path = _get_desktop_path()

    def get_mass_finding_cache_path(self) -> Path:
        self.mass_finding_cache_path = _get_cache_path(self.desktop_path, 'mass_finding_cache')
        return self.mass_finding_cache_path

    def get_formula_generation_cache_path(self) -> Path:
        self.formula_generation_cache_path = _get_cache_path(self.mass_finding_cache_path, 'formula_generation_cache')
        return self.formula_generation_cache_path
    
    def get_formula_search_cache_path(self) -> Path:
        self.formula_search_cache_path = _get_cache_path(self.mass_finding_cache_path, 'formula_search_cache')
        return self.formula_search_cache_path
    
    def get_initialization_cache_path(self) -> Path:
        self.initialization_cache_path = _get_cache_path(self.mass_finding_cache_path, 'initialization_cache')
        return self.initialization_cache_path
    
    def get_logger_cache_path(self) -> Path:
        self.logger_cache_path = _get_cache_path(self.mass_finding_cache_path, 'logger_cache')
        return self.logger_cache_path