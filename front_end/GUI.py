import tkinter as tk
from .components.navigation_bar import NavigationBar
from .pages.formula_generation_page import FormulaGenerationPage
from .pages.formula_search_page import FormulaSearchPage
from .pages.blank_page import BlankPage
from .utils.logger import Logger
from .core.event import EventBus
from .config import AppConfig
from .core.page_factory import PageFactory


class APP(tk.Tk):
    def __init__(self):
        super().__init__()
        self.root = self
        self.title("质谱数据分析工具 - designed by zc")
        self.iconbitmap("./front_end/icon.ico")
        self.geometry(AppConfig.WINDOW_SIZE)

        self.current_page = None  # 当前页面状态跟踪

        # 初始化事件总线
        self.event_bus = EventBus()

        # 初始化日志记录器
        self.logger = Logger(self.event_bus)

        # 初始化页面工厂
        self.page_factory = PageFactory(self, self.event_bus)

        # 初始化导航栏
        self.nav_bar = NavigationBar(self, self.page_factory)
        self.nav_bar.pack(side=tk.TOP, fill=tk.X)

        # 初始化页面
        initial_page = self.page_factory.get_page('BlankPage')
        self.show_page(initial_page)

    # 在show_page方法中添加容错处理
    def show_page(self, page):
        if page is None or page == self.current_page:
            return
        
        page.update_idletasks()  # 强制更新布局

        # 隐藏旧页面（如果存在）
        if self.current_page is not None and self.current_page.winfo_ismapped():
            self.current_page.pack_forget()
        
        # 显示新页面
        page.pack(fill=tk.BOTH, expand=True)
        self.current_page = page  # 更新当前页面状态

        # 强制刷新界面
        self.update_idletasks()


if __name__ == '__main__':
    app = APP()
    app.mainloop()