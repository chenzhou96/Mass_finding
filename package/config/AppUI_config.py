import tkinter as tk
from .base_config import BaseConfig
from .widget_config import WidgetConfig

class AppUIConfig:

    # 主窗口    
    class MainWindow:
        TITLE = f"质谱数据分析工具 V{BaseConfig.VERSION} - designed by zc"
        ICO = "./package/icon.ico"
        ICNS = "./package/icon.icns"
        WINDOW_SIZE = BaseConfig.WINDOW_SIZE
        BG_COLOR = BaseConfig.BACKGROUND

        frame = {
            'bg': BaseConfig.BACKGROUND,
            'bd': 0,
            'relief': tk.FLAT,
        }

    # 导航栏
    class NavigationBar:
        frame = {
            **WidgetConfig.frame,
            'bg': BaseConfig.BACKGROUND,
        }

        button = {
            **WidgetConfig.button,
            'width': 14,
            'height': 1,
            'font': (BaseConfig.FONT_STYLE, BaseConfig.FONT_SIZE, 'bold'),
            'bg': BaseConfig.PRIMARY_COLOR,
            'fg': '#ffffff',
            'activebackground': BaseConfig.SECONDARY_COLOR,
            'activeforeground': '#ffffff',
        }

        active_button = {
            'bg': BaseConfig.SECONDARY_COLOR,
            'fg': '#202020',
            'bd': 0,
            'relief': tk.FLAT,
            'width': 14,
            'height': 1,
            'font': (BaseConfig.FONT_STYLE, BaseConfig.FONT_SIZE, 'bold'),
        }

        padding = {
            'padx': BaseConfig.PADDING_B,
            'pady': BaseConfig.PADDING_B,
        }
        
        class PageName:
            page0 = {
                'chinese': '空白页',
                'english': 'Blank_Page',
            }
            page1 = {
                'chinese': '分子式生成',
                'english': 'Formula_Generation_Page',
            }
            page2 = {
                'chinese': '分子式检索',
                'english': 'Formula_Search_Page',
            }
            page_undefined = {
                'chinese': '预留接口',
                'english': 'Interface',
            }

    # 状态栏
    class StatusBar:
        frame = {
            'bg': BaseConfig.BACKGROUND,
            'bd': 0,
            'relief': tk.FLAT,
            'highlightthickness': 0,
            'highlightbackground': BaseConfig.BACKGROUND,
        }

        text = {}

        padding = {
            'padx': BaseConfig.PADDING_B,
            'pady': BaseConfig.PADDING_B,
        }

        label = {
            'bg': BaseConfig.BACKGROUND,
            'fg': BaseConfig.TEXT_DARK,
            'font': (BaseConfig.FONT_STYLE, BaseConfig.FONT_SIZE_SMALL, 'bold')
        }

    # 主页面右侧的交互区域
    class InteractiveZone:
        frame = {
            **WidgetConfig.frame,
        }

        padding = {
            'padx': BaseConfig.PADDING_B,
            'pady': BaseConfig.PADDING_B,
        }

        # 分子式暂存区域
        class FormulaCacheZone:
            text= {}

        # 日志显示区域
        class LoggerZone:
            text = {
                'font': (BaseConfig.FONT_STYLE, BaseConfig.FONT_SIZE_SMALL)
            }

            TAG_STYLES = {
                'DEBUG': {
                    'foreground': BaseConfig.TEXT_LIGHT,
                },
                'INFO': {
                    'foreground': BaseConfig.TEXT_DARK,
                },
                'WARNING': {
                    'foreground': BaseConfig.WARNING_COLOR,
                },
                'ERROR': {
                    'foreground': BaseConfig.ERROR_COLOR,
                },
                'CRITICAL': {
                    'foreground': BaseConfig.ERROR_COLOR,
                },
                'DEFAULT': {
                    'foreground': BaseConfig.TEXT_DARK,
                },
            }

            LOG_FORMAT = '%(asctime)s [%(levelname)s]\n%(message)s'
            DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

    # 主页面左侧的功能区域
    class FunctionZone:
        frame = {
            **WidgetConfig.frame,
        }

        padding = {
            'padx': BaseConfig.PADDING_B,
            'pady': BaseConfig.PADDING_B,
        }

        # 分子式生成页面
        class FormulaGenerationPage:
            input_frame = {
            }

            input_entry = {
                'width': 150,
            }

            padding = {
                'padx': BaseConfig.PADDING_A,
                'pady': BaseConfig.PADDING_A,
            }

            canvas = {
                'width': 150,
            }

            option_menu = {
                'background': '#ffffff',
                'foreground': BaseConfig.TEXT_DARK,
                'activebackground': BaseConfig.ACCENT_COLOR,
            }

            element_label = {
                'width': 2,
                'anchor': 'e',
                'bg': BaseConfig.BACKGROUND,
            }

            element_entry = {
                'width': 5,
                'justify': 'left',
            }

            output_frame = {}

        # 分子式搜索页面
        class FormulaSearchPage:
            input_frame = {
            }

            output_frame = {}

            padding = {
                'padx': BaseConfig.PADDING_A,
                'pady': BaseConfig.PADDING_A,
            }

            labelframe = {
            }

            text = {
            }

            right_label = {
                'anchor': 'w',
                'bg': BaseConfig.BACKGROUND,
                'fg': BaseConfig.TEXT_DARK,
            }