import tkinter as tk
from .base_page import BasePage
from ...utils.widget_factory import WidgetFactory
from ...config.AppUI_config import AppUIConfig
from ...config.event_config import EventType


class FormulaSearchPage(BasePage):
    def __init__(self, parent, event_mgr):
        super().__init__(parent, event_mgr, title="Formula Search")
        self.event_mgr.publish(
            EventType.STATUS_UPDATE, 
            data={"status_text": "loading..."}
        )
        self.widget_factory = WidgetFactory()
        self.left_frame = self.widget_factory.create_frame(self, **AppUIConfig.FunctionZone.FormulaSearchPage.input_frame)
        self.right_frame = self.widget_factory.create_frame(self, **AppUIConfig.FunctionZone.FormulaSearchPage.output_frame)

        self._setup_left_frame()
        self._setup_right_frame()

        self.event_mgr.publish(
            EventType.STATUS_UPDATE, 
            data={"status_text": "loading..."}
        )

    def _setup_left_frame(self):
        pass

    def _setup_right_frame(self):
        pass
