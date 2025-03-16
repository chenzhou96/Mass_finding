import tkinter as tk
from ...config.AppUI_config import AppUIConfig
from ...core.event import EventType, EventPriority
from ...utils.logger import Logger

class NavigationBar(tk.Frame):
    def __init__(self, parent, page_factory, widget_factory):
        super().__init__(parent, **AppUIConfig.NavigationBar.frame)
        self.page_factory = page_factory
        self.widget_factory = widget_factory
        self.event_mgr = parent.event_mgr  # 从父级（APP）获取 event_mgr
        self.logger = parent.logger       # 从父级（APP）获取 logger

        self.active_button = None
        self.buttons = {}

        # 生成已定义的页面按钮（假设页面配置已更新）
        for page_key in ['page1', 'page2']:  # 根据实际配置调整
            page_config = getattr(AppUIConfig.NavigationName, page_key)
            self.buttons[page_config['english']] = self._create_nav_button(
                page_config['chinese'], 
                page_config['english']
            )
        
        # 生成预留接口按钮
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
            **AppUIConfig.NavigationBar.button
        )

    def _switch_page(self, page_name, page_name_chinese):
        if self.page_factory:
            page = self.page_factory.get_page(page_name)
            if page and page != self.winfo_toplevel().current_page:
                # 1. 发布事件（使用优化后的事件类型）
                self.event_mgr.publish(
                    EventType.PAGE_SWITCH,
                    data={'new_page': page_name}
                )
                
                # 2. 重置按钮样式
                for btn in self.buttons.values():
                    if btn.cget('state') == tk.NORMAL:
                        btn.config(**AppUIConfig.NavigationBar.button)
                
                # 3. 设置当前按钮样式
                new_button = self.buttons.get(page_name, None)
                if new_button:
                    new_button.config(**AppUIConfig.NavigationBar.active_button)
                    self.active_button = new_button
                
                # 4. 切换页面
                self.winfo_toplevel().show_page(page)
                
        # 使用优化后的 Logger 记录日志
        self.logger.info(f"切换到页面: {page_name_chinese}")
