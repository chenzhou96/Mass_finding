from ..config.widget_config import WidgetConfig
import tkinter as tk

class WidgetFactory:
    def __init__(self):
        pass

    def create_frame(self, parent, **kwargs):
        """创建标准框架"""
        frame_style = WidgetConfig.frame.copy()
        frame_style.update(kwargs)
        return tk.Frame(parent, **frame_style)
    
    def create_labelframe(self, parent, text, **kwargs):
        """创建标准标签"""
        label_style = WidgetConfig.labelframe.copy()
        label_style.update(kwargs)
        return tk.LabelFrame(parent, text=text, **label_style)
    
    def create_canvas(self, parent, **kwargs):
        """创建标准画布"""
        canvas_style = WidgetConfig.canvas.copy()
        canvas_style.update(kwargs)
        return tk.Canvas(parent, **canvas_style)
    
    def create_toplevel(self, parent, **kwargs):
        """创建标准顶层窗口"""
        toplevel_style = WidgetConfig.toplevel.copy()
        toplevel_style.update(kwargs)
        return tk.Toplevel(parent, **toplevel_style)
    
    def create_paned_window(self, parent, **kwargs):
        """创建标准分割窗口"""
        paned_window_style = WidgetConfig.panedwindow.copy()
        paned_window_style.update(kwargs)
        return tk.PanedWindow(parent, **paned_window_style)
    
    def create_scrolled_window(self, parent, **kwargs):
        """创建带滚动条的框架"""
        scrolled_window_style = WidgetConfig.scrolledwindow.copy()
        scrolled_window_style.update(kwargs)
        return tk.Scrollbar(parent, **scrolled_window_style)

    def create_menu(self, parent, **kwargs):
        """创建标准菜单"""
        menu_style = WidgetConfig.menu.copy()
        menu_style.update(kwargs)
        return tk.Menu(parent, **menu_style)

    def create_button(self, parent, text, command=None, cooldown=0, **kwargs):
        """创建标准按钮（支持防抖功能）"""
        button_style = WidgetConfig.button.copy()
        button_style.update(kwargs)
        button = tk.Button(parent, text=text, command=command, **button_style)

        if cooldown is not None and command is not None:
            original_command = command
            duration = int(cooldown * 1000)  # 转换为毫秒

            def wrapped_command():
                if getattr(button, '_cooldown_active', False):
                    return
                button._cooldown_active = True
                original_command()
                button.after(duration, lambda: setattr(button, '_cooldown_active', False))

            button.config(command=wrapped_command)

        return button

    def create_entry(self, parent, **kwargs):
        """创建标准输入框"""
        entry_style = WidgetConfig.entry.copy()
        entry_style.update(kwargs)
        return tk.Entry(parent, **entry_style)
    
    def create_label(self, parent, text, **kwargs):
        """创建标准标签"""
        label_style = WidgetConfig.label.copy()
        label_style.update(kwargs)
        return tk.Label(parent, text=text, **label_style)

    def create_text(self, parent, **kwargs):
        """创建标准文本框"""
        text_style = WidgetConfig.text.copy()
        text_style.update(kwargs)
        return tk.Text(parent, **text_style)
    
    def create_checkbutton(self, parent, text, variable, command=None, **kwargs):
        """创建标准复选框"""
        checkbutton_style = WidgetConfig.checkbutton.copy()
        checkbutton_style.update(kwargs)
        return tk.Checkbutton(
            parent,
            text=text,
            variable=variable,
            command=command,
            **checkbutton_style
        )

    def create_scrollable_text(self, parent, **kwargs):
        """创建带滚动条的文本框"""
        text_style = WidgetConfig.text.copy()
        text_style.update(kwargs)
        text_widget = tk.Text(
            parent,
            wrap=tk.CHAR,
            **text_style
        )
        scrollbar = tk.Scrollbar(parent, command=text_widget.yview, **WidgetConfig.scrolledwindow)
        text_widget.config(yscrollcommand=scrollbar.set)
        return {
            "text": text_widget,
            "scrollbar": scrollbar
        }