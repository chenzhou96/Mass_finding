import json
import logging
from pathlib import Path
from typing import Any


def read_json_file(path: Path, default: Any = None) -> Any:
    try:
        if not path.exists():
            return default
        content = path.read_text(encoding='utf-8').strip()
        if not content:
            return default
        return json.loads(content)
    except json.JSONDecodeError:
        logging.warning(f"JSON文件解析失败: {path}")
        return default
    except Exception as e:
        logging.error(f"读取 JSON 文件失败: {path}, {e}")
        return default


def write_json_file(path: Path, data: Any) -> bool:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=4), encoding='utf-8')
        return True
    except Exception as e:
        logging.error(f"写入 JSON 文件失败: {path}, {e}")
        return False
