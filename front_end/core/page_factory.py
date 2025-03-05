from ..pages.formula_generation_page import FormulaGenerationPage
from ..pages.formula_search_page import FormulaSearchPage
from ..pages.blank_page import BlankPage

class PageFactory:
    def __init__(self, root, event_bus):
        if not hasattr(self, '_initialized'):  # 防止重复初始化
            self._initialized = True
            self.root = root
            self.event_bus = event_bus
            self.pages = {
                'BlankPage': BlankPage(root, event_bus),
                'FormulaGenerationPage': FormulaGenerationPage(root, event_bus),
                'FormulaSearchPage': FormulaSearchPage(root, event_bus),
                'Interface1Page': None,  # 需要实现
                'Interface2Page': None,  # 需要实现
                'Interface3Page': None,  # 需要实现
                'Interface4Page': None,  # 需要实现
                'Interface5Page': None,  # 需要实现
                'Interface6Page': None   # 需要实现
            }

    def get_page(self, page_name):
        return self.pages.get(page_name)