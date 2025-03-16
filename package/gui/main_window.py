import tkinter as tk
from tkinter import ttk
from .components.navigation_bar import NavigationBar
from ..utils.logger import Logger
from ..core.event import EventBus
from ..config.config_temp import AppConfig
from ..core.page_factory import PageFactory
from .components.status_bar import StatusBar
from ..utils.widget_factory import WidgetFactory
import platform
from PIL import Image, ImageTk
from ..config.path_config import IC0_PATH, ICNS_PATH

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
            self.iconbitmap(IC0_PATH)
        elif system == "Darwin":  # macOS
            # 需要通过PhotoImage加载ICNS
            image = Image.open(ICNS_PATH)
            icon = ImageTk.PhotoImage(image)
            self.iconphoto(True, icon)  # macOS推荐使用iconphoto
        else:
            # 其他系统保留默认图标
            pass

        self.configure(bg=AppConfig.MainWindow.BG_COLOR)

        # 创建全局样式对象
        style = ttk.Style()

        # 1. 设置基础组件的默认背景颜色
        style.configure(
            'TFrame',          # 作用于所有组件
            background=AppConfig.MainWindow.BG_COLOR,  # 主背景色
        )

        # 2. 初始化核心组件
        self.widget_factory = WidgetFactory()  # 创建 WidgetFactory 实例
        self.event_bus = EventBus(logger=None)
        self.event_bus.subscribe(AppConfig.EventName.add_formula, self._on_add_formula, priority=AppConfig.EventPriority.normal)

        # 3. 创建布局容器
        self.left_frame = self.widget_factory.create_frame(self, **AppConfig.FunctionZone.frame)
        self.right_frame = self.widget_factory.create_frame(self, **AppConfig.InteractiveZone.frame)
        self.upper_frame = self.widget_factory.create_labelframe(self.right_frame, text='分子式 bus', **AppConfig.FunctionZone.frame)
        self.lower_frame = self.widget_factory.create_labelframe(self.right_frame, text='操作日志', **AppConfig.FunctionZone.frame)
        self.page_factory = PageFactory(self.left_frame, self.event_bus)

        # 4. 创建导航栏
        self.nav_bar = NavigationBar(self, self.page_factory, self.widget_factory)
        self.nav_bar.pack(side=tk.TOP, fill=tk.X, **AppConfig.NavigationBar.padding)

        # 5. 布局容器定位
        self.right_frame.pack(side=tk.RIGHT, fill=tk.Y, **AppConfig.InteractiveZone.padding)
        self.right_frame.pack_propagate(0)  # 禁止自动调整大小
        self.upper_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True)
        self.lower_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)
        self.left_frame.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, **AppConfig.FunctionZone.padding)

        # 6.1 在upper_frame中添加占位组件（根据需求替换）
        self.upper_info = self.widget_factory.create_scrollable_text(self.upper_frame)
        self.upper_info["scrollbar"].pack(side=tk.RIGHT, fill=tk.Y)
        self.upper_info["text"].pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 6.2 初始化日志显示组件
        scrollable_text = self.widget_factory.create_scrollable_text(self.lower_frame, **AppConfig.InteractiveZone.LoggerZone.text)
        self.log_text = scrollable_text["text"]
        self.logger = Logger(self.event_bus, text_widget=self.log_text)
        self.event_bus.logger = self.logger
        scrollable_text["scrollbar"].pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 7. 创建状态栏
        self.status_bar = StatusBar(self.left_frame, widget_factory=self.widget_factory, event_bus=self.event_bus)
        self.status_bar.pack(side=tk.BOTTOM, fill=tk.X)

        # 8. 显示初始页面
        initial_page = self.page_factory.get_page('BlankPage')
        self.show_page(initial_page)
        self.logger.info("应用初始化完成")

    # 在show_page方法中添加容错处理
    def show_page(self, page):
        if page is None or page == self.current_page:
            return
        
        page.update_idletasks()  # 强制更新布局

        # 隐藏旧页面（若存在）
        if self.current_page:
            self.current_page.pack_forget()  # 仅隐藏不销毁
        
        # 显示新页面
        page.pack(fill=tk.BOTH, expand=True, **AppConfig.FunctionZone.padding)

        self.current_page = page  # 更新当前页面状态

        # 强制刷新界面
        self.update_idletasks()

    def _on_add_formula(self, event):
        formula_str = event.data
        text_widget = self.upper_info["text"]
        text_widget.config(state=tk.NORMAL)
        text_widget.insert(tk.END, formula_str + "\n")
        text_widget.see(tk.END)
        text_widget.config(state=tk.DISABLED)

if __name__ == '__main__':
    app = APP()
    app.mainloop()