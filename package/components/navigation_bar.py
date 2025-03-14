import tkinter as tk
from ..config import AppConfig, EVENT_TYPES
from ..core.event import Event
import logging

class NavigationBar(tk.Frame):
    def __init__(self, parent, page_factory, widget_factory):
        super().__init__(parent, **AppConfig.NavigationBar.frame)
        self.page_factory = page_factory
        self.widget_factory = widget_factory
        self.active_button = None  # 当前活动按钮跟踪
        self.buttons = {
            'FormulaGenerationPage': self._create_nav_button('分子式生成', 'FormulaGenerationPage'),
            'FormulaSearchPage': self._create_nav_button('分子式检索', 'FormulaSearchPage'),
            'Interface1Page': self._create_nav_button('预留接口1', 'Interface1Page'),
            'Interface2Page': self._create_nav_button('预留接口2', 'Interface2Page'),
            'Interface3Page': self._create_nav_button('预留接口3', 'Interface3Page'),
            'Interface4Page': self._create_nav_button('预留接口4', 'Interface4Page'),
            'Interface5Page': self._create_nav_button('预留接口5', 'Interface5Page'),
            'Interface6Page': self._create_nav_button('预留接口6', 'Interface6Page')
        }

        # 布局按钮
        for button in self.buttons.values():
            button.pack(side=tk.LEFT, padx=5, pady=5)

    def _create_nav_button(self, text, page_name):
        return self.widget_factory.create_button(
            self,
            text=text,
            command=lambda p=page_name: self._switch_page(p),
            **AppConfig.NavigationBar.button
        )

    def _switch_page(self, page_name):
        logging.info(f"切换到页面: {page_name}")
        if self.page_factory:
            page = self.page_factory.get_page(page_name)
            if page and page != self.winfo_toplevel().current_page:
                # 1. 发布事件
                self.winfo_toplevel().event_bus.publish(
                    Event(EVENT_TYPES['PAGE_SWITCH'], data={'new_page': page_name})
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