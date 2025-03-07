import tkinter as tk

class AppConfig:
    WINDOW_SIZE = "1280x800"
    LOG_FORMAT = '%(asctime)s - [%(levelname)s] %(message)s'
    DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

    # 中性灰配色方案
    COLOR_PRIMARY = '#E3E3E3'    # 浅灰白（主背景）
    COLOR_ACTIVE = '#696969'     # 深石板灰（激活状态）
    COLOR_DISABLED = '#F5F5F5'   # 淡灰色（禁用状态）
    COLOR_TEXT = '#404040'       # 深灰色文字
    
    BUTTON_STYLE = {
        'width': 12,
        'height': 1,
        'bd': 0,
        'bg': COLOR_PRIMARY,
        'fg': COLOR_TEXT,
        'font': ('微软雅黑', 12, 'bold'),
        'relief': tk.FLAT,        # 扁平化设计
        'borderwidth': 1,
        'padx': 8,
        'pady': 4,
        'activebackground': '#B0B0B0'  # 中灰色激活背景
    }
    
    ACTIVE_BUTTON_STYLE = {
        'bg': COLOR_ACTIVE,
        'fg': '#FFFFFF',          # 白色文字提高对比度
        'relief': tk.SUNKEN,
        'borderwidth': 1
    }
    
    DISABLED_BUTTON_STYLE = {
        'bg': COLOR_DISABLED,
        'fg': '#F3F3F3',
        'relief': tk.FLAT
    }

EVENT_TYPES = {
    'PAGE_SWITCH': 'page_switch',
    'LOG_MESSAGE': 'log_message',
}