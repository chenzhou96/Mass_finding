class AppConfig:
    WINDOW_SIZE = "1280x800"
    LOG_FORMAT = '%(asctime)s - [%(levelname)s] %(message)s'
    DATE_FORMAT = '%Y-%m-%d %H:%M:%S'
    BUTTON_STYLE = {
        'width': 15,
        'height': 1,
        'bd': 0,
        'bg': 'lightgray',
        'font': ('Helvetica', 12, 'bold')
    }

EVENT_TYPES = {
    'PAGE_SWITCH': 'page_switch',
    'LOG_MESSAGE': 'log_message',
}