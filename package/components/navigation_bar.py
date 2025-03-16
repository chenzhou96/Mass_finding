import tkinter as tk
from ..config import AppConfig
from ..core.event import Event
from ..utils.logger import Logger

class NavigationBar(tk.Frame):
    def __init__(self, parent, page_factory, widget_factory):
        super().__init__(parent, **AppConfig.NavigationBar.frame)
        self.page_factory = page_factory
        self.widget_factory = widget_factory
        self.active_button = None  # 当前活动按钮跟踪
        self.buttons = {}
        self.event_bus = self.winfo_toplevel().event_bus
        self.logger = Logger(event_bus=self.event_bus, text_widget=None)

        # 生成已定义的页面按钮
        for page_key in ['page1', 'page2']:  # 可扩展其他页面
            page_config = getattr(AppConfig.NavigationName, page_key)
            self.buttons[page_config['english']] = self._create_nav_button(
                page_config['chinese'], 
                page_config['english']
            )
        
        # 生成预留接口按钮（根据配置或固定数量）
        interface_count = 6
        for i in range(1, interface_count + 1):
            name = f"Interface{i}Page"
            text = f"预留接口{i}"
            self.buttons[name] = self._create_nav_button(text, name)

        # 布局按钮
        for button in self.buttons.values():
            button.pack(side=tk.LEFT, padx=5, pady=5)

    def _create_nav_button(self, text, page_name):
        return self.widget_factory.create_button(
            self,
            text=text,
            command=lambda p=page_name, pc=text: self._switch_page(p, pc),
            **AppConfig.NavigationBar.button
        )

    def _switch_page(self, page_name, page_name_chinese):
        if self.page_factory:
            page = self.page_factory.get_page(page_name)
            if page and page != self.winfo_toplevel().current_page:
                # 1. 发布事件
                self.winfo_toplevel().event_bus.publish(
                    Event(AppConfig.EventName.page_switch, data={'new_page': page_name})
                )
                
                # 2. 重置按钮样式
                for btn in self.buttons.values():
                    if btn.cget('state') == tk.NORMAL:
                        btn.config(**AppConfig.NavigationBar.button)
                
                # 3. 设置当前按钮样式
                new_button = self.buttons[page_name]
                new_button.config(**AppConfig.NavigationBar.active_button)
                self.active_button = new_button
                
                # 4. 切换页面，调用顶层窗口的show_page
                self.winfo_toplevel().show_page(page)
                
        self.logger.info(f"切换到页面: {page_name_chinese}")