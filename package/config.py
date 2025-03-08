import tkinter as tk


DEFUALT_FONT = '微软雅黑'

class AppConfig:
    
    class MainWindow:
        TITLE = "质谱数据分析工具 V3.0 - designed by zc"
        ICON = "./package/icon.ico"
        WINDOW_SIZE = "1280x800"
        BG_COLOR = "#FFFFFF"

    class BaseElement:
        BUTTON = {
            'width': 6,
            'height': 1,
            'bd': 0,
            'bg': '#E3E3E3',
            'fg': '#404040',
            'font': (DEFUALT_FONT, 8),
            'relief': tk.FLAT,
            'borderwidth': 1,
        }

        TEXT = {    
            'bg': '#E3E3E3',
            'fg': '#404040',
            'font': (DEFUALT_FONT, 8),    
        }

    class LogWindow:
        FRAME = {
            'width': 200,
        }

        TEXT = {
            'bg': "#FAFAFA",
            'fg': '#000000',
            'font': (DEFUALT_FONT, 8),
        }

        LOG_FORMAT = '%(asctime)s - [%(levelname)s] %(message)s'
        DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

    class NavigationBar:
        FRAME = {
            'bg': '#E3E3E3',
            'relief': tk.RAISED,
            'bd': 2
        }

        BUTTON = {
            'width': 12,
            'height': 1,
            'bd': 0,
            'bg': '#E3E3E3',
            'fg': '#404040',
            'font': (DEFUALT_FONT, 10, 'bold'),
            'relief': tk.FLAT,
            'borderwidth': 1,
            'padx': 8,
            'pady': 4,
            'activebackground': '#B0B0B0'
        }

        ACTIVE_BUTTON = {
            'bg': '#696969',
            'fg': '#FFFFFF',
            'relief': tk.SUNKEN,
            'borderwidth': 1
        }
        
        DISABLED_BUTTON = {
            'bg': '#F5F5F5',
            'fg': '#F3F3F3',
            'relief': tk.FLAT
        }

    class StatusBar:
        FRAME = {
            'bg': "#EEEEEE",
            'bd': 2,
            'relief': tk.GROOVE
        }

        TEXT = {
            'bg': '#EEEEEE',
            'fg': '#00008B',
            'font': (DEFUALT_FONT, 8),
        }

    class PageWindow:
        FRAME = {
            'bg': "#FFFFFF"
        }

        BUTTON = {
            'width': 6,
            'height': 1,
            'bd': 0,
            'bg': '#E3E3E3',
            'fg': '#404040',
            'font': (DEFUALT_FONT, 8),
            'relief': tk.FLAT,
            'borderwidth': 1,
        }

        DISABLED_BUTTON = {
            'bg': '#F5F5F5',
            'fg': '#F3F3F3',
            'relief': tk.FLAT
        }

        TEXT = {
            'bg': '#E3E3E3',
            'fg': '#404040',
            'font': (DEFUALT_FONT, 8),
        }

    class Padding:
        X = 2
        Y = 2

EVENT_TYPES = {
    'PAGE_SWITCH': 'page_switch',
    'LOG_MESSAGE': 'log_message',
}