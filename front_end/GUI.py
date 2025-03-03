import tkinter as tk
from .components.navigation_bar import NavigationBar
from .pages.formula_generation_page import FormulaGenerationPage
from .pages.formula_search_page import FormulaSearchPage
from .utils.logger import Logger
from .core.event import EventBus
from .config import AppConfig


class APP(tk.Tk):
    def __init__(self):
        super().__init__()
        self.root = self
        self.title("质谱数据分析工具 - designed by zc")
        self.iconbitmap("./front_end/icon.ico")

        # 初始化事件总线
        self.event_bus = EventBus()

        # 初始化日志记录器
        self.logger = Logger(self.event_bus)

        # 初始化导航栏
        self.nav_bar = NavigationBar(self, page_factory=None)  # 假设 page_factory 将在其他地方定义
        self.nav_bar.pack(side=tk.TOP, fill=tk.X)

        # 初始化页面
        self.formula_gen_page = FormulaGenerationPage(self, self.event_bus)
        self.formula_search_page = FormulaSearchPage(self, self.event_bus)

        # 显示初始页面
        self.show_page(self.formula_gen_page)

    def show_page(self, page):
        page.pack(fill=tk.BOTH, expand=True)


if __name__ == '__main__':
    app = APP()
    app.mainloop()