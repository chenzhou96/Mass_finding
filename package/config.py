import tkinter as tk

class BaseConfig:
    # 版本号
    VERSINO = '3.0'

    # 窗口设置
    WINDOW_SIZE = '1280x800'

    # 字体设置
    FONT_STYLE = '微软雅黑'
    FONT_SIZE = 10

    # 极简风配色方案
    PRIMARY_COLOR = "#457B9D"   # 北欧蓝（品牌主色）
    SECONDARY_COLOR = "#C7C7CC" # 精钢灰（辅助色）
    # BACKGROUND = "#FBFBFC"      # 云母白（主背景）
    BACKGROUND = "red"
    TEXT_DARK = "#2D3436"       # 宇宙灰（标题文字）
    TEXT_LIGHT = "#666666"      # 石墨灰（次要文字）
    ACCENT_COLOR = "#D7E7F5"    # 湖泊蓝（状态提示）
    WARNING_COLOR = "#FFD166"   # 香蕉黄（警告提示）
    ERROR_COLOR = "#EF476F"     # 珊瑚红（错误提示）
    SUCCESS_COLOR = "#2EC4B6"   # 翡翠绿（成功提示）

    # 布局设置
    PADDING_A = 2
    PADDING_B = 4
    PADDING_C = 8

    # 边框设置
    BD_A = 0
    BD_B = 1
    BD_C = 2

    # 按钮设置
    BUTTON_WIDTH_A = 3
    BUTTON_WIDTH_B = 6
    BUTTON_WIDTH_C = 12
    BUTTON_HEIGHT_A = 1
    BUTTON_HEIGHT_B = 2
    
class BaseElement:
    frame = {
        'bg': BaseConfig.BACKGROUND,
        'bd': BaseConfig.BD_A,
        'relief': tk.FLAT,
        'padx': BaseConfig.PADDING_A,
        'pady': BaseConfig.PADDING_A,
    }

    labelframe = {
        'bg': BaseConfig.BACKGROUND,
        'bd': BaseConfig.BD_B,
        'fg': BaseConfig.TEXT_DARK,
        'relief': tk.GROOVE,
        'padx': BaseConfig.PADDING_A,
        'pady': BaseConfig.PADDING_A,
    }

    toplevel = {
        'bg': BaseConfig.BACKGROUND,
        'bd': BaseConfig.BD_A,
        'relief': tk.FLAT,
    }

    panedWindow = {
        'bg': BaseConfig.BACKGROUND,
        'bd': BaseConfig.BD_A,
        'relief': tk.FLAT,
    }

    scrolledWindow = {
        'bg': BaseConfig.BACKGROUND,
        'bd': BaseConfig.BD_B,
        'relief': tk.SUNKEN,
    }

    button = {
        'bg': BaseConfig.BACKGROUND,
        'fg': BaseConfig.TEXT_DARK,
        'bd': BaseConfig.BD_B,
        'relief': tk.FLAT,
        'activebackground': BaseConfig.SECONDARY_COLOR,
        'activeforeground': BaseConfig.PRIMARY_COLOR,
        'font': (BaseConfig.FONT_STYLE, BaseConfig.FONT_SIZE),
        'padx': BaseConfig.PADDING_A,
        'pady': BaseConfig.PADDING_A,
    }

    entry = {
        'bg': BaseConfig.BACKGROUND,
        'fg': BaseConfig.TEXT_DARK,
        'bd': BaseConfig.BD_B,
        'relief': tk.SOLID,
        'insertbackground': BaseConfig.TEXT_DARK,
        'font': (BaseConfig.FONT_STYLE, BaseConfig.FONT_SIZE),
    }

    label = {
        'bg': BaseConfig.BACKGROUND,
        'fg': BaseConfig.TEXT_DARK,
        'font': (BaseConfig.FONT_STYLE, BaseConfig.FONT_SIZE),
    }

    text = {
        'bg': BaseConfig.BACKGROUND,
        'fg': BaseConfig.TEXT_DARK,
        'bd': BaseConfig.BD_A,
        'relief': tk.SUNKEN,
        'font': (BaseConfig.FONT_STYLE, BaseConfig.FONT_SIZE),
    }

    checkbutton = {
        'padx': BaseConfig.PADDING_A,
        'pady': BaseConfig.PADDING_A,
    }


class AppConfig:

    # 主窗口    
    class MainWindow:
        TITLE = f"质谱数据分析工具 V{BaseConfig.VERSINO} - designed by zc"
        ICO = "./package/icon.ico"
        ICNS = "./package/icon.icns"
        WINDOW_SIZE = BaseConfig.WINDOW_SIZE
        BG_COLOR = BaseConfig.BACKGROUND

    # 导航栏
    class NavigationBar:
        frame = {}

        button = {
            **BaseElement.button,
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
        frame = {}

        text = {}

    # 主页面右侧的交互区域
    class InteractiveZone:
        frame = {
            'width': 200,
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
                'fg': BaseConfig.TEXT_LIGHT,
            }

            LOG_FORMAT = '%(asctime)s - [%(levelname)s] %(message)s'
            DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

    # 主页面左侧的功能区域
    class FunctionZone:
        frame = {}

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

            element_label = {
                'width': 2,
                'anchor': 'e',
            }

            element_entry = {
                'width': 5,
                'justify': 'left',
            }

            output_frame = {}

    class Padding:
        X = BaseConfig.PADDING_A
        Y = BaseConfig.PADDING_A


EVENT_TYPES = {
    'PAGE_SWITCH': 'page_switch',
    'LOG_MESSAGE': 'log_message',
}