import tkinter as tk
from ..config import AppConfig


class NavigationBar(tk.Frame):
    def __init__(self, parent, page_factory):
        super().__init__(parent)
        self.page_factory = page_factory
        self.active_button = None  # 当前活动按钮跟踪
        self.buttons = {
            'FormulaGenerationPage': self._create_nav_button('分子式生成', 'FormulaGenerationPage'),
            'FormulaSearchPage': self._create_nav_button('分子式检索', 'FormulaSearchPage'),
            'Interface1Page': self._create_nav_button('预留接口1', 'Interface1Page', is_disabled=True),
            'Interface2Page': self._create_nav_button('预留接口2', 'Interface2Page', is_disabled=True),
            'Interface3Page': self._create_nav_button('预留接口3', 'Interface3Page', is_disabled=True),
            'Interface4Page': self._create_nav_button('预留接口4', 'Interface4Page', is_disabled=True),
            'Interface5Page': self._create_nav_button('预留接口5', 'Interface5Page', is_disabled=True),
            'Interface6Page': self._create_nav_button('预留接口6', 'Interface6Page', is_disabled=True)
        }

        # 布局按钮
        for button in self.buttons.values():
            button.pack(side=tk.LEFT, padx=5, pady=5)

    def _create_nav_button(self, text, page_name, is_disabled=False):
        button_style = AppConfig.BUTTON_STYLE.copy()

        if is_disabled:
            button_style.update(AppConfig.DISABLED_BUTTON_STYLE)
            button_style['state'] = tk.DISABLED

        return tk.Button(
            self,
            text=text,
            **button_style,
            command=lambda p=page_name: self._switch_page(p) if not is_disabled else None
        )

    def _switch_page(self, page_name):
        if self.page_factory:
            page = self.page_factory.get_page(page_name)
            if page and page != self.master.current_page:
                # 重置所有非禁用按钮到基础样式
                for btn in self.buttons.values():
                    if btn.cget('state') != tk.DISABLED:  # 跳过禁用按钮
                        btn.config(**AppConfig.BUTTON_STYLE)
                        
                # 设置当前活动按钮样式
                new_button = self.buttons[page_name]
                new_button.config(**AppConfig.ACTIVE_BUTTON_STYLE)
                self.active_button = new_button
                    
                self.master.show_page(page)