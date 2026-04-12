from ..config.widget_config import WidgetConfig
from ..config.base_config import BaseConfig
import tkinter as tk

class RoundedButton(tk.Canvas):
    def __init__(self, parent, text, command=None, width=120, height=34, radius=18, bg=BaseConfig.PRIMARY_COLOR, fg='#ffffff', hover_bg=BaseConfig.SECONDARY_COLOR, font=None, cursor='hand2', **kwargs):
        bg_parent = parent.cget('bg') if hasattr(parent, 'cget') else BaseConfig.BACKGROUND
        super().__init__(parent, width=width, height=height, highlightthickness=0, bd=0, relief=tk.FLAT, bg=bg_parent, cursor=cursor, **kwargs)
        self._command = command
        self._bg = bg
        self._fg = fg
        self._hover_bg = hover_bg
        self._radius = radius
        self._font = font or (BaseConfig.FONT_STYLE, BaseConfig.FONT_SIZE)
        self._state = tk.NORMAL
        self._draw_button(text)
        self.bind('<ButtonRelease-1>', self._on_click)
        self.bind('<Enter>', lambda e: self._update_fill(self._hover_bg))
        self.bind('<Leave>', lambda e: self._update_fill(self._bg))

    def _draw_button(self, text):
        self._text = text
        self.delete('all')
        width = int(self['width'])
        height = int(self['height'])
        self._rect = self._create_rounded_rect(2, 2, width - 2, height - 2, self._radius, fill=self._bg, outline='')
        self._text_id = self.create_text(width / 2, height / 2, text=self._text, fill=self._fg, font=self._font)

    def _create_rounded_rect(self, x1, y1, x2, y2, r, **kwargs):
        points = [
            x1 + r, y1,
            x2 - r, y1,
            x2, y1,
            x2, y1 + r,
            x2, y2 - r,
            x2, y2,
            x2 - r, y2,
            x1 + r, y2,
            x1, y2,
            x1, y2 - r,
            x1, y1 + r,
            x1, y1,
        ]
        return self.create_polygon(points, smooth=True, **kwargs)

    def _update_fill(self, color):
        self.itemconfig(self._rect, fill=color)

    def _on_click(self, event):
        if self._state != tk.NORMAL:
            return
        if callable(self._command):
            self._command()

    def config(self, **kwargs):
        if 'bg' in kwargs:
            self._bg = kwargs.pop('bg')
            self._update_fill(self._bg)
        if 'fg' in kwargs:
            self._fg = kwargs.pop('fg')
            self.itemconfig(self._text_id, fill=self._fg)
        if 'font' in kwargs:
            self._font = kwargs.pop('font')
            self.itemconfig(self._text_id, font=self._font)
        if 'width' in kwargs:
            width = kwargs.pop('width')
            width_px = int(width) * 10 if isinstance(width, int) else int(width)
            super().config(width=width_px)
            self._draw_button(self._text)
        if 'height' in kwargs:
            height = kwargs.pop('height')
            height_px = int(height) * 28 if isinstance(height, int) else int(height)
            super().config(height=height_px)
            self._draw_button(self._text)
        if 'state' in kwargs:
            self._state = kwargs.pop('state')
        if 'command' in kwargs:
            self._command = kwargs.pop('command')

        # 忽略 tk.Button 特有的无效参数
        for invalid in ['activebackground', 'activeforeground', 'relief', 'bd', 'borderwidth', 'padx', 'pady', 'cursor', 'highlightthickness', 'highlightbackground']:
            kwargs.pop(invalid, None)

        super().config(**kwargs)

    def cget(self, key):
        if key == 'state':
            return self._state
        if key == 'bg':
            return self._bg
        return super().cget(key)

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
        hover_bg = kwargs.pop('hover_bg', BaseConfig.SECONDARY_COLOR)
        button_style.update(kwargs)
        button = tk.Button(parent, text=text, command=command, **button_style)

        normal_bg = button_style.get('bg', BaseConfig.PRIMARY_COLOR)
        button.bind('<Enter>', lambda e: button.config(bg=hover_bg))
        button.bind('<Leave>', lambda e: button.config(bg=normal_bg))

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

    def create_rounded_button(self, parent, text, command=None, cooldown=0, **kwargs):
        """创建圆角按钮"""
        button_style = WidgetConfig.button.copy()
        hover_bg = kwargs.pop('hover_bg', BaseConfig.SECONDARY_COLOR)
        button_style.update(kwargs)

        width = button_style.pop('width', 14)
        height = button_style.pop('height', 1)
        width_px = int(width) * 10 if isinstance(width, int) else int(width)
        height_px = int(height) * 28 if isinstance(height, int) else int(height)

        button_command = command
        if cooldown is not None and command is not None:
            original_command = command
            duration = int(cooldown * 1000)
            def wrapped_command():
                if getattr(button_command, '_cooldown_active', False):
                    return
                setattr(button_command, '_cooldown_active', True)
                original_command()
                parent.after(duration, lambda: setattr(button_command, '_cooldown_active', False))
            button_command = wrapped_command

        rounded_button = RoundedButton(
            parent,
            text=text,
            command=button_command,
            width=width_px,
            height=height_px,
            bg=button_style.get('bg', BaseConfig.PRIMARY_COLOR),
            fg=button_style.get('fg', '#ffffff'),
            hover_bg=hover_bg,
            font=button_style.get('font'),
        )
        return rounded_button

    def create_entry(self, parent, **kwargs):
        """创建标准输入框"""
        entry_style = WidgetConfig.entry.copy()
        entry_style.update(kwargs)
        entry_style.pop('padx', None)
        entry_style.pop('pady', None)
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