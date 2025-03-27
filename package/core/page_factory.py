import logging
from ..gui.pages.formula_generation_page import FormulaGenerationPage
from ..gui.pages.formula_search_page import FormulaSearchPage
from ..gui.pages.blank_page import BlankPage
from ..gui.pages.interface_page import InterfacePage

class PageFactory:
    def __init__(self, root, event_mgr=None):
        if not hasattr(self, '_initialized'):  # 防止重复初始化
            self._initialized = True
            self.root = root
            self.event_mgr = event_mgr
            self.page_classes = {
                'Blank_Page': BlankPage,
                'Formula_Generation_Page': FormulaGenerationPage,
                'Formula_Search_Page': FormulaSearchPage,
                'Interface_1_Page': InterfacePage,  # 需要实现
                'Interface_2_Page': InterfacePage,  # 需要实现
                'Interface_3_Page': InterfacePage,  # 需要实现
                'Interface_4_Page': InterfacePage,  # 需要实现
                'Interface_5_Page': InterfacePage,  # 需要实现
                'Interface_6_Page': InterfacePage   # 需要实现
            }

            self._instances = {}

    def set_root(self, root):
        self.root = root

    def get_page(self, page_name):
        page_class = self.page_classes.get(page_name)
        if not page_class:
            logging.error(f"未找到页面类: {page_name}")
            return self.get_page('Blank_Page')  # 回退到默认页面
        
        # 检查是否已存在实例，存在则直接返回
        if page_name in self._instances:
            return self._instances[page_name]
        
        # 不存在则创建新实例并缓存
        instance = page_class(self.root, self.event_mgr)
        self._instances[page_name] = instance
        return instance