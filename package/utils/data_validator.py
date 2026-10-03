"""Desktop string adapter to the shared scientific contract."""
import logging
from ..service.formula_generation_service import validate_input


class DataValidator:
    def validate(self, params):
        try:
            normalized = dict(params)
            normalized['elements'] = {e: -1 if n == '不限' else int(n) if isinstance(n, str) else n
                                      for e, n in params['elements'].items()}
            validate_input(normalized)
            return True
        except (ValueError, TypeError, KeyError) as exc:
            logging.error('参数输入错误: %s', exc)
            return False
