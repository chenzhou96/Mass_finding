import tkinter as tk
import logging
from .components.navigation_bar import NavigationBar
from ..utils.logger import Logger, EventLogHandler
from ..core.event import EventManager
from ..config.AppUI_config import AppUIConfig
from ..config.event_config import EventType, EventPriority
from ..core.page_factory import PageFactory
from .components.status_bar import StatusBar
from ..utils.widget_factory import WidgetFactory
import platform
from PIL import Image, ImageTk
from ..config.path_config import PathManager

class APP(tk.Tk):
    def __init__(self):
        self.current_page = None
        self.path_manager = PathManager()
        self._init_window()
        self._init_components()
        self._setup_layout()
        self._init_event_handlers()
        self._setup_initial_page()

        # 发布初始化完成日志
        logging.info("应用初始化完成")
        self.event_mgr.publish(
            EventType.STATUS_UPDATE, 
            data={"status_text": "done"}
        )

    def _init_window(self):
        super().__init__()
        self.title(AppUIConfig.MainWindow.TITLE)
        self.geometry(AppUIConfig.MainWindow.WINDOW_SIZE)
        self.configure(bg=AppUIConfig.MainWindow.BG_COLOR)
        self._set_icon()

    def _set_icon(self):
        system = platform.system()
        if system == "Windows":
            self.iconbitmap(self.path_manager.ico_path)
        elif system == "Darwin":
            image = Image.open(self.path_manager.icns_path)
            icon = ImageTk.PhotoImage(image)
            self.iconphoto(True, icon)

    def _init_components(self):
        """优化后的组件初始化"""
        # 1. 初始化事件总线
        self.event_mgr = EventManager()
        # 2. 初始化日志器（依赖 event_mgr 的 bus）
        self.logger = Logger(event_bus=self.event_mgr.bus)
        self.widget_factory = WidgetFactory()
        # 3. 初始化页面工厂（需要 event_mgr）
        self.page_factory = PageFactory(
            root=self,  # 顶层容器（主窗口）
            event_mgr=self.event_mgr
        )
        # 4. 创建布局容器
        self._create_layout_containers()
        # 5. 初始化导航栏，状态栏，元素区域
        self._create_navigation_bar()
        self._create_status_bar()
        self._init_formula_bus()
        # 6. 初始化日志器
        self._init_logger()

    def _create_layout_containers(self):
        self.nav_frame = self.widget_factory.create_frame(
            self,
            **AppUIConfig.NavigationBar.frame
        )
        self.mid_frame = self.widget_factory.create_frame(
            self,
            **AppUIConfig.MainWindow.frame
        )
        self.status_frame = self.widget_factory.create_frame(
            self,
            **AppUIConfig.StatusBar.frame
        )
        self.left_frame = self.widget_factory.create_frame(
            self.mid_frame,
            **AppUIConfig.FunctionZone.frame
        )
        self.right_frame = self.widget_factory.create_frame(
            self.mid_frame,
            **AppUIConfig.InteractiveZone.frame
        )
        self.upper_frame = self.widget_factory.create_labelframe(
            self.right_frame,
            text='分子式 bus',
            **AppUIConfig.InteractiveZone.frame
        )
        self.lower_frame = self.widget_factory.create_labelframe(
            self.right_frame,
            text='操作日志',
            **AppUIConfig.InteractiveZone.frame
        )
        self.page_factory.set_root(self.left_frame)

    def _create_navigation_bar(self):
        self.nav_bar = NavigationBar(
            self,
            self.nav_frame,
            self.page_factory,
            self.widget_factory
        )

    def _create_status_bar(self):
        self.status_bar = StatusBar(
            self.status_frame,
            widget_factory=self.widget_factory,
            event_mgr=self.event_mgr
        )

    def _init_formula_bus(self):
        # 上部信息区组件（分子式显示）
        self.upper_info = self.widget_factory.create_scrollable_text(self.upper_frame)
        self.upper_info["scrollbar"].pack(side=tk.RIGHT, fill=tk.Y)
        self.upper_info["text"].pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def _init_logger(self):
        """配置日志 UI 组件"""
        scrollable_text = self.widget_factory.create_scrollable_text(
            self.lower_frame,
            **AppUIConfig.InteractiveZone.LoggerZone.text
        )
        self.log_text = scrollable_text["text"]
        # 将日志文本框关联到已存在的 Logger 实例
        self.logger.text_widget = self.log_text
        event_handler = EventLogHandler(self.event_mgr)
        logging.getLogger().addHandler(event_handler)

        scrollable_text["scrollbar"].pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def _setup_layout(self):
        self.nav_frame.pack(
            side=tk.TOP,
            fill=tk.X,
            **AppUIConfig.NavigationBar.padding
        )
        self.mid_frame.pack(
            side=tk.TOP,
            fill=tk.BOTH,
            expand=True,
        )
        self.status_frame.pack(
            side=tk.BOTTOM,
            fill=tk.X,
            **AppUIConfig.StatusBar.padding
        )
        # 导航栏布局
        self.nav_bar.pack(
            side=tk.TOP,
            fill=tk.X,
        )
        # 状态栏布局
        self.status_bar.pack(
            side=tk.BOTTOM,
            fill=tk.X,
        )
        # 右侧主容器
        self.right_frame.pack(
            side=tk.RIGHT,
            fill=tk.Y,
            **AppUIConfig.InteractiveZone.padding
        )
        self.right_frame.pack_propagate(0)
        # 右侧上下容器
        self.upper_frame.pack(
            side=tk.TOP,
            fill=tk.BOTH,
            expand=True
        )
        self.upper_frame.pack_propagate(0)
        self.lower_frame.pack(
            side=tk.BOTTOM,
            fill=tk.BOTH,
            expand=True
        )
        self.lower_frame.pack_propagate(0)
        # 左侧主容器
        self.left_frame.pack(
            side=tk.LEFT,
            fill=tk.BOTH,
            expand=True,
            **AppUIConfig.FunctionZone.padding
        )

    def _init_event_handlers(self):
        self.event_mgr.subscribe(
            EventType.ADD_FORMULA,
            self._on_add_formula,
            priority=EventPriority.NORMAL
        )

    def _setup_initial_page(self):
        initial_page = self.page_factory.get_page('Blank_Page')
        self.show_page(initial_page)

    def show_page(self, page):
        if page is None or page == self.current_page:
            return

        page.update_idletasks()
        if self.current_page:
            self.current_page.pack_forget()
        page.pack(
            fill=tk.BOTH,
            expand=True,
            **AppUIConfig.FunctionZone.padding
        )
        self.current_page = page
        self.update_idletasks()

    def _on_add_formula(self, event):
        formula_str = event.data
        text_widget = self.upper_info["text"]
        text_widget.config(state=tk.NORMAL)
        text_widget.insert(tk.END, f"{formula_str}\n")
        text_widget.see(tk.END)
        text_widget.config(state=tk.DISABLED)

if __name__ == '__main__':
    app = APP()
    app.mainloop()