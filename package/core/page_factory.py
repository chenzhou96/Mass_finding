from ..gui.pages.formula_generation_page import FormulaGenerationPage
from ..gui.pages.formula_search_page import FormulaSearchPage
from ..gui.pages.blank_page import BlankPage
from ..gui.pages.interface_page import InterfacePage

class PageFactory:
    def __init__(self, root, event_mgr=None, logger=None):
        if not hasattr(self, '_initialized'):  # 防止重复初始化
            self._initialized = True
            self.root = root
            self.event_mgr = event_mgr
            self.logger = logger
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

            self._instances = {}

    def get_page(self, page_name):
        page_class = self.page_classes.get(page_name)
        if not page_class:
            self.logger.error(f"未找到页面类: {page_name}")
            return self.get_page('BlankPage')  # 回退到默认页面
        
        # 检查是否已存在实例，存在则直接返回
        if page_name in self._instances:
            return self._instances[page_name]
        
        # 不存在则创建新实例并缓存
        instance = page_class(self.root, self.event_mgr, self.logger)
        self._instances[page_name] = instance
        return instance