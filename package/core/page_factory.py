from ..pages.formula_generation_page import FormulaGenerationPage
from ..pages.formula_search_page import FormulaSearchPage
from ..pages.blank_page import BlankPage
from ..pages.interface_page import InterfacePage
import logging

class PageFactory:
    def __init__(self, root, event_bus):
        if not hasattr(self, '_initialized'):  # 防止重复初始化
            self._initialized = True
            self.root = root
            self.event_bus = event_bus
            self.page_classes = {
                'BlankPage': BlankPage,
                'FormulaGenerationPage': FormulaGenerationPage,
                'FormulaSearchPage': FormulaSearchPage,
                'Interface1Page': InterfacePage,  # 需要实现
                'Interface2Page': InterfacePage,  # 需要实现
                'Interface3Page': InterfacePage,  # 需要实现
                'Interface4Page': InterfacePage,  # 需要实现
                'Interface5Page': InterfacePage,  # 需要实现
                'Interface6Page': InterfacePage   # 需要实现
            }

    def get_page(self, page_name):
        page_class = self.page_classes.get(page_name)
        if not page_class:
            logging.error(f"未找到页面类: {page_name}")
            return self.get_page('BlankPage')  # 回退到默认页面
        
        # 按需创建实例（避免提前初始化所有页面）
        return page_class(self.root, self.event_bus)