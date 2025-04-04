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
            'bd': BaseConfig.BD_B,
            'relief': tk.FLAT,
        }

    # 导航栏
    class NavigationBar:
        frame = {
            **WidgetConfig.frame,
        }

        button = {
            **WidgetConfig.button,
            'width': 12,
            'height': 1,
            'font': (BaseConfig.FONT_STYLE, BaseConfig.FONT_SIZE, 'bold'),
        }

        active_button = {
            'bg': BaseConfig.PRIMARY_COLOR,
            'fg': BaseConfig.BACKGROUND,
            'bd': BaseConfig.BD_B,
            'relief': tk.SUNKEN,
            'width': 12,
            'height': 1,
            'font': (BaseConfig.FONT_STYLE, BaseConfig.FONT_SIZE, 'bold'),
        }

        padding = {
            'padx': BaseConfig.PADDING_A,
            'pady': BaseConfig.PADDING_A,
        }

    # 状态栏
    class StatusBar:
        frame = {
            'bg': BaseConfig.THIRD_COLOR,
        }

        text = {}

        padding = {
            'padx': BaseConfig.PADDING_A,
            'pady': BaseConfig.PADDING_A,
        }

        label = {
            'bg': BaseConfig.THIRD_COLOR,
            'fg': BaseConfig.TEXT_DARK,
            'font': (BaseConfig.FONT_STYLE, BaseConfig.FONT_SIZE_SMALL, 'bold')
        }

    # 主页面右侧的交互区域
    class InteractiveZone:
        frame = {
            'width': 200,
            **WidgetConfig.frame,
        }

        padding = {
            'padx': BaseConfig.PADDING_A,
            'pady': BaseConfig.PADDING_A,
        }

        # 分子式暂存区域
        class FormulaCacheZone:
            text= {}

        # 日志显示区域
        class LoggerZone:
            text = {
                'font': (BaseConfig.FONT_STYLE, BaseConfig.FONT_SIZE_SMALL)
            }

            LOG_FORMAT = '%(asctime)s [%(levelname)s]\n%(message)s'
            DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

    # 主页面左侧的功能区域
    class FunctionZone:
        frame = {
            **WidgetConfig.frame,
        }

        padding = {
            'padx': BaseConfig.PADDING_A,
            'pady': BaseConfig.PADDING_A,
        }

        # 分子式生成页面
        class FormulaGenerationPage:
            input_frame = {
                'width': 150,
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
                'background': BaseConfig.THIRD_COLOR,
                'foreground': BaseConfig.TEXT_DARK,
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
                'width': 300,
            }

            output_frame = {
                'relief': tk.GROOVE
            }

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

    class NavigationName:
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