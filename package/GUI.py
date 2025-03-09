import tkinter as tk
from .components.navigation_bar import NavigationBar
from .utils.logger import Logger
from .core.event import EventBus
from .config import AppConfig
from .core.page_factory import PageFactory
from .components.status_bar import StatusBar
from .utils.widget_factory import WidgetFactory
import logging
import platform
from PIL import Image, ImageTk

class APP(tk.Tk):
    def __init__(self):
        # 显式初始化current_page属性
        self.current_page = None  
        
        # 1. 初始化主窗口
        super().__init__()
        self.title(AppConfig.MainWindow.TITLE)
        self.geometry(AppConfig.MainWindow.WINDOW_SIZE)

        # 系统类型检测
        system = platform.system()

        # 动态设置图标
        if system == "Windows":
            self.iconbitmap(AppConfig.MainWindow.ICO)
        elif system == "Darwin":  # macOS
            # 需要通过PhotoImage加载ICNS
            image = Image.open(AppConfig.MainWindow.ICNS)
            icon = ImageTk.PhotoImage(image)
            self.iconphoto(True, icon)  # macOS推荐使用iconphoto
        else:
            # 其他系统保留默认图标
            pass

        self.configure(bg=AppConfig.MainWindow.BG_COLOR)

        # 2. 创建布局容器
        self.left_frame = tk.Frame(self, **AppConfig.PageWindow.FRAME)  # 左侧主内容区域
        self.right_frame = tk.Frame(self, **AppConfig.LogWindow.FRAME)  # 右侧日志区域

        # 3. 初始化核心组件（先初始化事件总线）
        self.event_bus = EventBus()
        self.page_factory = PageFactory(self.left_frame, self.event_bus)
        self.widget_factory = WidgetFactory()  # 创建 WidgetFactory 实例

        # 4. 创建导航栏
        self.nav_bar = NavigationBar(self, self.page_factory, self.widget_factory)
        self.nav_bar.pack(side=tk.TOP, fill=tk.X, padx=5, pady=(5, 10))

        # 5. 布局容器定位
        self.right_frame.pack(side=tk.RIGHT, fill=tk.Y, padx=(5, 10), pady=5)
        self.right_frame.pack_propagate(0)  # 禁止自动调整大小
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(10, 5), pady=5)

        # 6. 初始化日志显示组件（移到事件总线之后）
        scrollable_text = self.widget_factory.create_scrollable_text(self.right_frame)
        self.log_text = scrollable_text["text"]
        self.logger = Logger(self.event_bus, text_widget=self.log_text)
        scrollable_text["scrollbar"].pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 7. 创建状态栏
        self.status_bar = StatusBar(self.left_frame, event_bus=self.event_bus)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # 8. 显示初始页面
        initial_page = self.page_factory.get_page('BlankPage')
        self.show_page(initial_page)
        logging.info("应用初始化完成")

    # 在show_page方法中添加容错处理
    def show_page(self, page):
        if page is None or page == self.current_page:
            return
        
        page.update_idletasks()  # 强制更新布局

        # 隐藏旧页面（若存在）
        if self.current_page:
            self.current_page.pack_forget()  # 仅隐藏不销毁
        
        # 显示新页面
        page.pack(fill=tk.BOTH, expand=True)

        # 显示新页面（固定在left_frame内）
        page.pack(fill=tk.BOTH, expand=True, 
                padx=AppConfig.Padding.X,  # 统一间距配置
                pady=AppConfig.Padding.Y)

        self.current_page = page  # 更新当前页面状态

        # 强制刷新界面
        self.update_idletasks()

if __name__ == '__main__':
    app = APP()
    app.mainloop()