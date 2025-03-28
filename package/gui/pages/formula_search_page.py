import tkinter as tk
from .base_page import BasePage
from ...utils.widget_factory import WidgetFactory
from ...config.AppUI_config import AppUIConfig
from ...config.event_config import EventType
from ...config.base_config import BaseConfig


class FormulaSearchPage(BasePage):
    def __init__(self, parent, event_mgr):
        super().__init__(parent, event_mgr, title="Formula Search")
        self.event_mgr.publish(
            EventType.STATUS_UPDATE, 
            data={"status_text": "loading..."}
        )
        self._page_init()
        self.widget_factory = WidgetFactory()
        self.left_frame = self.widget_factory.create_frame(self, **AppUIConfig.FunctionZone.FormulaSearchPage.input_frame)
        self.right_frame = self.widget_factory.create_frame(self, **AppUIConfig.FunctionZone.FormulaSearchPage.output_frame)

        # 使用网格布局
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.left_frame.grid(row=0, column=0, sticky="nsw")
        self.left_frame.grid_propagate(False)  # 禁用自动调整
        self.right_frame.grid(row=0, column=1, sticky="nsew")

        self._setup_left_frame()
        self._setup_right_frame()

        self.event_mgr.publish(
            EventType.STATUS_UPDATE, 
            data={"status_text": "done"}
        )

    def _setup_left_frame(self):
        def setup_labelframe(frame, text, **kwargs):
            labelframe = self.widget_factory.create_labelframe(frame, text=text, **AppUIConfig.FunctionZone.FormulaSearchPage.labelframe, **kwargs)
            labelframe.pack_propagate(0)
            text_widget = self.widget_factory.create_scrollable_text(labelframe, **AppUIConfig.FunctionZone.FormulaSearchPage.text)
            text_widget["scrollbar"].pack(side=tk.RIGHT, fill=tk.Y)
            text_widget["text"].pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            return labelframe

        self.left_frame.grid_columnconfigure(0, weight=1)
        self.left_frame.grid_columnconfigure(1, weight=1)
        self.left_frame.grid_rowconfigure(0, weight=1)
        self.left_frame.grid_rowconfigure(1, weight=1)

        self.existing_formula = setup_labelframe(self.left_frame, "本地已有分子式")
        self.waiting_formula = setup_labelframe(self.left_frame, "待搜索分子式")
        self.failed_formula = setup_labelframe(self.left_frame, "搜索失败分子式", fg=BaseConfig.ERROR_COLOR)
        self.success_formula = setup_labelframe(self.left_frame, "搜索成功分子式", fg=BaseConfig.SUCCESS_COLOR)

        self.existing_formula.grid(row=0, column=0, sticky="nsew")
        self.waiting_formula.grid(row=1, column=0, sticky="nsew")
        self.success_formula.grid(row=0, column=1, sticky="nsew")
        self.failed_formula.grid(row=1, column=1, sticky="nsew")

    def _setup_right_frame(self, labelname='分子可能结构式'):
        self.info_label = self.widget_factory.create_label(self.right_frame, text=labelname, **AppUIConfig.FunctionZone.FormulaSearchPage.right_label)
        self.info_label.pack(side=tk.TOP, fill=tk.X)

    def _read_formula_list(self, type):
        pass

    def _page_init(self):
        pass
