class BaseConfig:
    # 版本号
    VERSION = '3.0.0'

    # 窗口设置
    WINDOW_SIZE = '1440x880'

    # 字体设置
    FONT_STYLE = '微软雅黑'
    FONT_SIZE = 10
    FONT_SIZE_SMALL = 9

    # 黑白银灰高级配色方案
    PRIMARY_COLOR = "#302302"   # 碳黑（品牌主色）
    SECONDARY_COLOR = "#B0B0B0" # 银灰（辅助色）
    THIRD_COLOR = "#F4F4F4"     # 轻银灰（卡片背景）
    BACKGROUND = "#FFFFFF"      # 纯白（主背景）
    TEXT_DARK = "#141414"       # 近黑（标题文字）
    TEXT_LIGHT = "#6B6B6B"      # 中灰（次要文字）
    ACCENT_COLOR = "#E8E8E8"    # 亮银（强调背景）
    WARNING_COLOR = "#AD7D0C"   # 橙色（警告提示）
    ERROR_COLOR = "#EF476F"     # 珊瑚红（错误提示）
    SUCCESS_COLOR = "#2EC4B6"   # 翡翠绿（成功提示）

    # 布局设置
    PADDING_A = 2
    PADDING_B = 4
    PADDING_C = 6

    # 边框设置
    BD_A = 0
    BD_B = 1
    BD_C = 2

    # 按钮设置
    BUTTON_WIDTH_A = 3
    BUTTON_WIDTH_B = 6
    BUTTON_WIDTH_C = 9
    BUTTON_HEIGHT_A = 1
    BUTTON_HEIGHT_B = 2

    # PubChem 检索策略（服务层）
    PUBCHEM_MAX_RETRIES = 3
    PUBCHEM_RETRY_BASE_DELAY_SEC = 2
    PUBCHEM_HTTP_TIMEOUT_SEC = 30
    PUBCHEM_POLL_INTERVAL_SEC = 2
    PUBCHEM_POLL_MAX_ATTEMPTS = 6
    PUBCHEM_PREFER_FASTFORMULA = True