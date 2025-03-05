import tkinter as tk

class AppConfig:
    WINDOW_SIZE = "1280x800"
    LOG_FORMAT = '%(asctime)s - [%(levelname)s] %(message)s'
    DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

    COLOR_PRIMARY = '#B0E0E6'    #  PowderBlue 更醒目的基础色
    COLOR_ACTIVE = '#0047AB'     #  CobaltBlue 高对比度激活色
    COLOR_DISABLED = '#A9A9A9'   #  DarkGray 禁用状态灰色
    COLOR_TEXT = '#2F4F4F'       #  DarkSlateGray 深色文字
    
    BUTTON_STYLE = {
        'width': 15,
        'height': 1,
        'bd': 0,
        'bg': COLOR_PRIMARY,
        'fg': COLOR_TEXT,  # 文字颜色
        'font': ('Helvetica', 12, 'bold'),
        'relief': tk.RAISED,
        'borderwidth': 2,
        'padx': 8,
        'pady': 4,
        'activebackground': COLOR_ACTIVE  # 按下状态背景
    }
    
    ACTIVE_BUTTON_STYLE = {
        'bg': COLOR_ACTIVE,
        'fg': '#008000',
        'relief': tk.SUNKEN
    }
    
    DISABLED_BUTTON_STYLE = {
        'bg': COLOR_DISABLED,
        'fg': 'white',
        'relief': tk.FLAT
    }

EVENT_TYPES = {
    'PAGE_SWITCH': 'page_switch',
    'LOG_MESSAGE': 'log_message',
}