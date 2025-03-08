import tkinter as tk
from .components.navigation_bar import NavigationBar
from .utils.logger import Logger
from .core.event import EventBus
from .config import AppConfig
from .core.page_factory import PageFactory
from .components.status_bar import StatusBar
import logging


class APP(tk.Tk):
    def __init__(self):
        # 显式初始化current_page属性
        self.current_page = None  
        
        # 1. 初始化主窗口
        super().__init__()
        self.title("质谱数据分析工具 - designed by zc")
        self.iconbitmap("./front_end/icon.ico")
        self.geometry(AppConfig.WINDOW_SIZE)

        self.configure(bg=AppConfig.PRIMARY_BG)

        # 2. 创建布局容器
        self.left_frame = tk.Frame(self, bg=AppConfig.PRIMARY_BG)  # 左侧主内容区域
        self.right_frame = tk.Frame(self, width=AppConfig.LOG_TEXT_WIDTH)  # 右侧日志区域

        # 3. 初始化核心组件（先初始化事件总线）
        self.event_bus = EventBus()
        self.page_factory = PageFactory(self.left_frame, self.event_bus)

        # 4. 创建导航栏
        self.nav_bar = NavigationBar(self, self.page_factory)
        self.nav_bar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=(5, 10))

        # 5. 布局容器定位
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 5), pady=5)
        self.right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 10), pady=5)
        self.right_frame.config(width=AppConfig.LOG_TEXT_WIDTH)
        self.right_frame.pack_propagate(0)  # 禁止自动调整大小

        # 6. 初始化日志显示组件（移到事件总线之后）
        self.log_text = tk.Text(
            self.right_frame,
            bg=AppConfig.COLOR_PRIMARY,
            fg=AppConfig.COLOR_TEXT,
            font=(AppConfig.DEFAULT_FONT, 10),
            wrap=tk.CHAR
        )
        self.logger = Logger(self.event_bus, text_widget=self.log_text)

        # 7. 创建状态栏
        self.status_bar = StatusBar(self.left_frame, event_bus=self.event_bus)
        self.status_bar.config(
            relief=tk.GROOVE, 
            bd=2, 
            bg=AppConfig.STATUS_BG_COLOR
        )
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # 8. 配置日志文本框和滚动条
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar = tk.Scrollbar(self.right_frame, command=self.log_text.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.config(yscrollcommand=scrollbar.set)

        # 9. 显示初始页面
        initial_page = self.page_factory.get_page('BlankPage')
        self.show_page(initial_page)
        logging.info("应用初始化完成")

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