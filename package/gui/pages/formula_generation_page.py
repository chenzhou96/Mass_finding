import os
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from .base_page import BasePage
from ...core.thread_pool import ThreadPool
from ...service.formulaGeneration import start_analysis
from ...utils.data_validator import DataValidator
from ...utils.widget_factory import WidgetFactory
from ...config.AppUI_config import AppUIConfig
from ...config.base_config import BaseConfig
from ...config.event_config import EventType, EventPriority
from ...config.path_config import PathManager
import logging
import json
import tkinter.font as tkFont
from pathlib import Path
import re
from functools import partial

class FormulaGenerationPage(BasePage):

    def __init__(self, parent, event_mgr):
        super().__init__(parent, event_mgr, title="Formula Generation")
        self._layout_ratio = (2, 5)
        self.event_mgr.publish(
            EventType.STATUS_UPDATE, 
            data={"status_text": "loading..."}
        )
        self.widget_factory = WidgetFactory()
        self.left_frame = self.widget_factory.create_frame(self, **AppUIConfig.FunctionZone.FormulaGenerationPage.input_frame)
        self.right_frame = self.widget_factory.create_frame(self, **AppUIConfig.FunctionZone.FormulaGenerationPage.output_frame)

        self.adducts_config = None

        # 初始化加合物框架
        self.adduct_frame = None
        self.adduct_vars = {}  # 重置为字典存储当前选中的加合物

        # 使用网格布局
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=5)
        self.grid_rowconfigure(0, weight=1)

        self.left_frame.grid(row=0, column=0, sticky="nsew")
        self.right_frame.grid(row=0, column=1, sticky="nsew")
        self.bind("<Configure>", self._on_page_resize)

        self._setup_left_scrollable_container()

        # 初始化所有控件
        self._setup_left_frame()
        self._setup_right_frame()
        self._setup_buttons()

        # 数据存储
        self.data = []

        # 线程池实例
        self.thread_pool = ThreadPool()

        # 初始化加合物选项
        self._on_ms_mode_change()

        self.event_mgr.publish(
            EventType.STATUS_UPDATE, 
            data={"status_text": "done"}
        )

    def _setup_left_scrollable_container(self):
        self.left_frame.grid_rowconfigure(0, weight=1)
        self.left_frame.grid_columnconfigure(0, weight=1)

        self.left_canvas = self.widget_factory.create_canvas(self.left_frame, highlightthickness=0)
        self.left_scrollbar = tk.Scrollbar(self.left_frame, orient=tk.VERTICAL, command=self.left_canvas.yview)
        self.left_canvas.configure(yscrollcommand=self.left_scrollbar.set)

        self.left_canvas.grid(row=0, column=0, sticky="nsew")
        self.left_scrollbar.grid(row=0, column=1, sticky="ns")

        self.left_content_frame = self.widget_factory.create_frame(self.left_canvas)
        self.left_canvas_window = self.left_canvas.create_window((0, 0), window=self.left_content_frame, anchor="nw")

        self.left_content_frame.bind("<Configure>", self._on_left_content_configure)
        self.left_canvas.bind("<Configure>", self._on_left_canvas_configure)
        self.left_canvas.bind("<MouseWheel>", self._on_left_mousewheel)

    def _on_left_content_configure(self, _event):
        self.left_canvas.configure(scrollregion=self.left_canvas.bbox("all"))

    def _on_left_canvas_configure(self, event):
        self.left_canvas.itemconfigure(self.left_canvas_window, width=event.width)

    def _on_left_mousewheel(self, event):
        self.left_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")

    def _on_page_resize(self, event):
        left_ratio, right_ratio = self._layout_ratio
        total_ratio = left_ratio + right_ratio
        if event.width <= 1 or total_ratio <= 0:
            return

        left_width = max(0, int(event.width * left_ratio / total_ratio))
        right_width = max(0, event.width - left_width)
        self.grid_columnconfigure(0, minsize=left_width)
        self.grid_columnconfigure(1, minsize=right_width)

    def _get_adduct_config(self):
        if not self.adducts_config:
            with open(PathManager().chem_element_config_path, "r", encoding="utf-8") as f:
                config_data = json.load(f)
                self.adducts_config = config_data["adducts"]
        return {
            mode: list(adducts.values()) 
            for mode, adducts in self.adducts_config.items()
        }

    def _on_ms_mode_change(self, *args):
        current_mode = self.ms_mode.get()
        adduct_config = self._get_adduct_config()
        max_adduct_rows = 1
        for adduct_modes in adduct_config.values():
            max_adduct_rows = max(max_adduct_rows, len(adduct_modes) + 1)  # 1行用于标题

        adducts = adduct_config.get(current_mode, [])
        
        # 销毁旧框架
        if hasattr(self, 'adduct_frame'):
            if self.adduct_frame:
                self.adduct_frame.destroy()
            self.adduct_frame = None
        
        # 创建新框架
        self.adduct_frame = self.widget_factory.create_labelframe(self.left_content_frame, text="加合物模型")
        self.adduct_frame.grid(row=1, column=0, sticky="ew")
        
        # 启动网格布局
        self.adduct_frame.grid_propagate(True)
        self.adduct_frame.columnconfigure(0, weight=1)
        self.adduct_frame.columnconfigure(1, weight=1)
        
        # 重置变量
        self.adduct_vars = {}
        
        # 添加选项，使用两列布局来节省垂直空间
        cols = 2
        for idx, adduct in enumerate(adducts):
            row = idx // cols
            col = idx % cols
            var = tk.BooleanVar()
            cb = self.widget_factory.create_checkbutton(
                self.adduct_frame, 
                text=adduct, 
                variable=var,
            )
            cb.grid(row=row, column=col, sticky="w", padx=BaseConfig.PADDING_A, pady=BaseConfig.PADDING_A)
            self.adduct_vars[adduct] = var

        self._refresh_adduct_filter_options()

    def _setup_left_frame(self):

        # 创建样式
        style = ttk.Style()
        style.configure("TMenubutton", **AppUIConfig.FunctionZone.FormulaGenerationPage.option_menu)

        # 初始化网格布局
        self.left_content_frame.columnconfigure(0, weight=1)

        def create_input_frame(parent, text, row):
            frame = self.widget_factory.create_labelframe(parent, text=text)
            frame.grid(row=row, column=0, sticky="ew")
            return frame

        def create_grid_input_frame(parent, text, row, col):
            frame = self.widget_factory.create_labelframe(parent, text=text)
            frame.grid(row=row, column=col, sticky="ew", padx=BaseConfig.PADDING_A, pady=BaseConfig.PADDING_A)
            return frame

        # 质谱模式框架
        ms_mode_frame = create_input_frame(self.left_content_frame, "质谱模式", 0)
        self.ms_mode = tk.StringVar(value="ESI+")
        self.ms_mode.trace_add("write", self._on_ms_mode_change)
        
        # 质谱模式选择框
        option_menu = ttk.OptionMenu(
            ms_mode_frame, 
            self.ms_mode, 
            "ESI+", 
            *["ESI+", "ESI-", "EI+", "EI-"],
            style="TMenubutton"
        )
        option_menu.pack(side=tk.LEFT, **AppUIConfig.FunctionZone.FormulaGenerationPage.padding)
        
        # 参数输入区（2x2布局）
        params_frame = create_input_frame(self.left_content_frame, "参数输入", 2)
        params_frame.columnconfigure(0, weight=1)
        params_frame.columnconfigure(1, weight=1)

        # 第一行：m/z值、电荷数
        m2z_frame = create_grid_input_frame(params_frame, "m/z值", 0, 0)
        self.m2z = tk.DoubleVar(value=100)
        entry = self.widget_factory.create_entry(m2z_frame, textvariable=self.m2z, **AppUIConfig.FunctionZone.FormulaGenerationPage.input_entry)
        entry.pack(**AppUIConfig.FunctionZone.FormulaGenerationPage.padding)

        charge_frame = create_grid_input_frame(params_frame, "电荷数", 0, 1)
        self.charge = tk.IntVar(value=1)
        entry = self.widget_factory.create_entry(charge_frame, textvariable=self.charge, **AppUIConfig.FunctionZone.FormulaGenerationPage.input_entry)
        entry.pack(**AppUIConfig.FunctionZone.FormulaGenerationPage.padding)

        # 第二行：误差范围（%）、误差范围（Da）
        error_frame = create_grid_input_frame(params_frame, "误差范围 (%)", 1, 0)
        self.error_pct = tk.DoubleVar(value=0.1)
        entry = self.widget_factory.create_entry(error_frame, textvariable=self.error_pct, **AppUIConfig.FunctionZone.FormulaGenerationPage.input_entry)
        entry.pack(**AppUIConfig.FunctionZone.FormulaGenerationPage.padding)

        error_da_frame = create_grid_input_frame(params_frame, "误差范围 (Da)", 1, 1)
        self.error_da = tk.DoubleVar(value=0.0)
        entry = self.widget_factory.create_entry(error_da_frame, textvariable=self.error_da, **AppUIConfig.FunctionZone.FormulaGenerationPage.input_entry)
        entry.pack(**AppUIConfig.FunctionZone.FormulaGenerationPage.padding)

        # 元素配置区优化
        elements = ["C", "N", "O", "S", "P", "Si", "F", "Cl", "Br", "I", "B", "Se"]
        self.element_vars = {
            e: tk.StringVar(value="不限" if e in {"C", "N", "O"} else "0") 
            for e in elements
        }

        self.elements_frame = create_input_frame(self.left_content_frame, "元素配置(不超过)", 3)
        self.elements_frame.grid_propagate(True)
        self.elements_frame.columnconfigure(0, weight=0)
        self.elements_frame.columnconfigure(1, weight=1)
        self.elements_frame.columnconfigure(2, weight=0)
        self.elements_frame.columnconfigure(3, weight=1)

        element_options = ["不限"] + [str(i) for i in range(0, 13)]
        for i, elem in enumerate(elements):
            row, col_in_row = divmod(i, 2)
            label_col = col_in_row * 2
            entry_col = label_col + 1

            element_label = self.widget_factory.create_label(
                self.elements_frame,
                text=f"{elem}:",
                **AppUIConfig.FunctionZone.FormulaGenerationPage.element_label
            )
            element_label.grid(row=row, column=label_col, **AppUIConfig.FunctionZone.FormulaGenerationPage.padding)
            
            combo = ttk.Combobox(
                self.elements_frame,
                textvariable=self.element_vars[elem],
                values=element_options,
                state='readonly',
                width=8,
                font=(BaseConfig.FONT_STYLE, BaseConfig.FONT_SIZE)
            )
            combo.grid(row=row, column=entry_col, **AppUIConfig.FunctionZone.FormulaGenerationPage.padding)

    def _setup_right_frame(self):
        # 创建筛选栏容器
        filter_frame = self.widget_factory.create_labelframe(self.right_frame, text="筛选栏")
        filter_frame.pack(side=tk.TOP, fill=tk.X)

        # 创建表格容器
        table_frame = self.widget_factory.create_labelframe(self.right_frame, text="可能分子式")
        table_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

        self.filter_fields_order = [
            "Adduct", "M/Z", "DBR", "C", "H", "N", "O", "S", "P", "Si", "F", "Cl", "Br", "I", "B", "Se", "Mol Weight"
        ]
        self.element_filter_fields = {"C", "H", "N", "O", "S", "P", "Si", "F", "Cl", "Br", "I", "B", "Se"}
        self.integer_filter_fields = set(self.element_filter_fields) | {"DBR"}
        self.filter_field_meta = self._build_filter_field_meta()
        self.filter_condition_rows = []
        self.active_filter_row = None
        self._is_refreshing_filter_options = False
        self._is_clearing_filter_rows = False
        self._suspend_dirty_tracking = False
        self.applied_conditions = []
        self.applied_conditions_signature = []
        self.is_filter_dirty = False
        self._current_table_context = {"row_id": "", "column_name": "", "cell_value": ""}
        self._table_selection_anchor = None

        # 筛选行视觉样式（局部样式，不影响其他页面）
        self.filter_row_even_bg = "#fafafa"
        self.filter_row_odd_bg = "#f3f3f3"
        self.filter_row_hover_bg = "#f0f7ff"
        self.filter_row_active_bg = "#e6f2ff"
        self.filter_row_border_color = BaseConfig.SECONDARY_COLOR

        filter_toolbar = self.widget_factory.create_frame(filter_frame, padx=0, pady=0)
        filter_toolbar.pack(side=tk.TOP, fill=tk.X, padx=BaseConfig.PADDING_A, pady=BaseConfig.PADDING_A)

        self.add_filter_button = ttk.Button(filter_toolbar, text="+ 添加条件", command=self._add_filter_condition_row)
        self.add_filter_button.pack(side=tk.LEFT, padx=(0, BaseConfig.PADDING_A))

        self.apply_filter_button = ttk.Button(filter_toolbar, text="应用筛选", command=self._apply_filters)
        self.apply_filter_button.pack(side=tk.LEFT, padx=(0, BaseConfig.PADDING_A))

        self.clear_filter_button = ttk.Button(filter_toolbar, text="清空条件", command=self._clear_filter_conditions)
        self.clear_filter_button.pack(side=tk.LEFT, padx=(0, BaseConfig.PADDING_A))

        self.filter_dirty_label = self.widget_factory.create_label(
            filter_toolbar,
            text="",
            bg=BaseConfig.BACKGROUND,
            fg="#f39c12",
            font=(BaseConfig.FONT_STYLE, max(8, BaseConfig.FONT_SIZE - 1)),
        )
        self.filter_dirty_label.pack(side=tk.LEFT)

        self.filter_feedback_label = self.widget_factory.create_label(
            filter_frame,
            text="",
            bg=BaseConfig.BACKGROUND,
            fg="#e74c3c",
            anchor="w",
            justify=tk.LEFT,
            font=(BaseConfig.FONT_STYLE, max(8, BaseConfig.FONT_SIZE - 1)),
        )
        self.filter_feedback_label.pack(side=tk.TOP, fill=tk.X, padx=BaseConfig.PADDING_A, pady=(0, BaseConfig.PADDING_A))

        self.filter_condition_container = self.widget_factory.create_frame(filter_frame, padx=0, pady=0)
        self.filter_condition_container.pack(side=tk.TOP, fill=tk.X, padx=BaseConfig.PADDING_A, pady=(0, BaseConfig.PADDING_A))

        self._add_filter_condition_row()

        columns = list(self.filter_fields_order)

        # 表格部分
        vsb = tk.Scrollbar(table_frame, orient=tk.VERTICAL)
        hsb = tk.Scrollbar(table_frame, orient=tk.HORIZONTAL)
        self.table = ttk.Treeview(
            table_frame,
            columns=columns,
            displaycolumns=['M/Z', 'Adduct', 'Mol Weight', 'DBR'],
            show="headings",
            selectmode="extended",
            xscrollcommand=hsb.set,
            yscrollcommand=vsb.set
        )
        vsb.config(command=self.table.yview)
        hsb.config(command=self.table.xview)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.table.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.empty_result_label = self.widget_factory.create_label(
            table_frame,
            text="",
            bg=BaseConfig.BACKGROUND,
            fg=BaseConfig.TEXT_LIGHT,
            justify=tk.CENTER,
            font=(BaseConfig.FONT_STYLE, BaseConfig.FONT_SIZE),
        )

        for col in columns:
            self.table.heading(col, text=col)
            self.table.column(col, minwidth=50, anchor=tk.CENTER, stretch=False)

        self.table_popup_menu = self.widget_factory.create_menu(self.table, tearoff=0)
        self.table_popup_menu.add_command(label="按当前列添加筛选", command=self._add_filter_from_table_context)
        self.table_popup_menu.add_separator()
        self.table_popup_menu.add_command(label="发送选中项到分子式 bus", command=self._send_selected_row_to_bus)
        self.table_popup_menu.add_separator()
        self.table_popup_menu.add_command(label="删除", command=self._delete_selected_row)
        self.table.bind("<ButtonPress-1>", self._on_table_left_press, add="+")
        self.table.bind("<B1-Motion>", self._on_table_drag_select, add="+")
        self.table.bind("<Button-3>", self._on_table_right_click)

        self.table.bind("<Double-1>", self._on_table_double_click)
        self.table.bind("<Delete>", self._on_delete_shortcut)

        self.result_stats_label = self.widget_factory.create_label(
            self.right_frame,
            text="总数: 0 | 命中: 0 | 筛除: 0",
            bg=BaseConfig.BACKGROUND,
            fg=BaseConfig.TEXT_LIGHT,
            anchor="w",
            justify=tk.LEFT,
            font=(BaseConfig.FONT_STYLE, max(8, BaseConfig.FONT_SIZE - 1)),
        )
        self.result_stats_label.pack(side=tk.BOTTOM, fill=tk.X, padx=BaseConfig.PADDING_A, pady=(BaseConfig.PADDING_A, 0))

        self.applied_summary_label = self.widget_factory.create_label(
            self.right_frame,
            text="已应用条件: 无",
            bg=BaseConfig.BACKGROUND,
            fg=BaseConfig.TEXT_LIGHT,
            anchor="w",
            justify=tk.LEFT,
            font=(BaseConfig.FONT_STYLE, max(8, BaseConfig.FONT_SIZE - 1)),
        )
        self.applied_summary_label.pack(side=tk.BOTTOM, fill=tk.X, padx=BaseConfig.PADDING_A, pady=(0, BaseConfig.PADDING_A))

        self.bind("<Return>", self._on_apply_shortcut)
        self.bind("<Control-d>", self._on_duplicate_shortcut)
        self.bind("<Delete>", self._on_delete_shortcut)

        self._update_filter_dirty_state()
        self._update_result_summary(total=0, matched=0)
        self._refresh_adduct_filter_options()

    def _build_filter_field_meta(self):
        numeric_fields = [
            "M/Z", "DBR", "C", "H", "N", "O", "S", "P", "Si", "F", "Cl", "Br", "I", "B", "Se", "Mol Weight"
        ]
        meta = {
            "Adduct": {
                "type": "text",
                "operators": ["等于", "包含"],
            }
        }
        for field in numeric_fields:
            meta[field] = {
                "type": "number",
                "operators": [">", ">=", "=", "<=", "<", "区间"],
            }
        return meta

    def _add_filter_condition_row(self, preset=None):
        row_frame = self.widget_factory.create_frame(
            self.filter_condition_container,
            bg=self.filter_row_even_bg,
            padx=1,
            pady=1,
            bd=1,
            relief=tk.FLAT,
            highlightthickness=1,
            highlightbackground=self.filter_row_border_color,
        )
        row_frame.pack(side=tk.TOP, fill=tk.X, pady=1)

        index_var = tk.StringVar(value="")
        field_var = tk.StringVar(value="")
        operator_var = tk.StringVar(value="")
        value_var = tk.StringVar(value="")
        second_value_var = tk.StringVar(value="")
        error_var = tk.StringVar(value="")

        index_label = self.widget_factory.create_label(
            row_frame,
            text="",
            textvariable=index_var,
            bg=self.filter_row_even_bg,
            fg=BaseConfig.TEXT_LIGHT,
            width=2,
            anchor="center",
            font=(BaseConfig.FONT_STYLE, max(8, BaseConfig.FONT_SIZE - 2)),
        )
        index_label.pack(side=tk.LEFT, padx=(0, 1))

        field_combo = ttk.Combobox(
            row_frame,
            textvariable=field_var,
            values=[],
            state="readonly",
            width=8,
            font=(BaseConfig.FONT_STYLE, BaseConfig.FONT_SIZE)
        )
        field_combo.pack(side=tk.LEFT, padx=(0, 1))

        operator_combo = ttk.Combobox(
            row_frame,
            textvariable=operator_var,
            values=[],
            state="readonly",
            width=4,
            font=(BaseConfig.FONT_STYLE, BaseConfig.FONT_SIZE)
        )
        operator_combo.pack(side=tk.LEFT, padx=(0, 1))

        value_container = self.widget_factory.create_frame(row_frame, bg=self.filter_row_even_bg, padx=0, pady=0)
        value_container.pack(side=tk.LEFT, fill=tk.X, expand=True, padx=(0, 1))

        value_entry = self.widget_factory.create_entry(
            value_container,
            textvariable=value_var,
            width=10,
        )
        value_spin = ttk.Spinbox(
            value_container,
            textvariable=value_var,
            from_=0,
            to=999,
            increment=1,
            width=8,
            font=(BaseConfig.FONT_STYLE, BaseConfig.FONT_SIZE)
        )
        value_combo = ttk.Combobox(
            value_container,
            textvariable=value_var,
            values=[],
            state="readonly",
            width=10,
            font=(BaseConfig.FONT_STYLE, BaseConfig.FONT_SIZE)
        )
        second_value_label = self.widget_factory.create_label(
            value_container,
            text="~",
            bg=self.filter_row_even_bg,
            fg=BaseConfig.TEXT_LIGHT,
            font=(BaseConfig.FONT_STYLE, BaseConfig.FONT_SIZE)
        )
        second_value_entry = self.widget_factory.create_entry(
            value_container,
            textvariable=second_value_var,
            width=10,
        )
        second_value_spin = ttk.Spinbox(
            value_container,
            textvariable=second_value_var,
            from_=0,
            to=999,
            increment=1,
            width=8,
            font=(BaseConfig.FONT_STYLE, BaseConfig.FONT_SIZE)
        )

        delete_button = ttk.Button(row_frame, text="X", width=2, command=lambda: self._remove_filter_condition_row(row_data))
        delete_button.pack(side=tk.LEFT, padx=(0, 1))

        error_label = self.widget_factory.create_label(
            row_frame,
            text="",
            textvariable=error_var,
            bg=self.filter_row_even_bg,
            fg="#e74c3c",
            anchor="w",
            justify=tk.LEFT,
            width=10,
            font=(BaseConfig.FONT_STYLE, max(8, BaseConfig.FONT_SIZE - 2)),
        )
        error_label.pack(side=tk.LEFT, padx=(2, 0))

        row_data = {
            "frame": row_frame,
            "is_hover": False,
            "base_bg": self.filter_row_even_bg,
            "index_var": index_var,
            "index_label": index_label,
            "field_var": field_var,
            "operator_var": operator_var,
            "value_var": value_var,
            "second_value_var": second_value_var,
            "error_var": error_var,
            "error_label": error_label,
            "field_combo": field_combo,
            "operator_combo": operator_combo,
            "value_container": value_container,
            "value_entry": value_entry,
            "value_spin": value_spin,
            "value_combo": value_combo,
            "second_value_label": second_value_label,
            "second_value_entry": second_value_entry,
            "second_value_spin": second_value_spin,
            "delete_button": delete_button,
        }
        self.filter_condition_rows.append(row_data)

        field_combo.bind("<<ComboboxSelected>>", lambda _event, row=row_data: self._on_filter_field_change(row))
        operator_combo.bind("<<ComboboxSelected>>", lambda _event, row=row_data: self._on_filter_operator_change(row))

        for widget in [field_combo, operator_combo, value_entry, value_spin, value_combo, second_value_entry, second_value_spin, delete_button]:
            widget.bind("<FocusIn>", lambda _event, row=row_data: self._set_active_filter_row(row))
            widget.bind("<Enter>", lambda _event, row=row_data: self._set_row_hover_state(row, True))
            widget.bind("<Leave>", lambda _event, row=row_data: self._set_row_hover_state(row, False))

        row_frame.bind("<Enter>", lambda _event, row=row_data: self._set_row_hover_state(row, True))
        row_frame.bind("<Leave>", lambda _event, row=row_data: self._set_row_hover_state(row, False))

        value_entry.bind("<KeyRelease>", lambda _event, row=row_data: self._on_row_input_changed(row))
        second_value_entry.bind("<KeyRelease>", lambda _event, row=row_data: self._on_row_input_changed(row))
        value_spin.bind("<KeyRelease>", lambda _event, row=row_data: self._on_row_input_changed(row))
        second_value_spin.bind("<KeyRelease>", lambda _event, row=row_data: self._on_row_input_changed(row))
        value_combo.bind("<<ComboboxSelected>>", lambda _event, row=row_data: self._on_row_input_changed(row))

        self._refresh_filter_field_options()
        self._refresh_row_indices()
        self._refresh_row_field_behavior(row_data)

        if preset:
            self._apply_row_preset(row_data, preset)
            self._refresh_filter_field_options()
        self._on_row_input_changed(row_data)
        self._set_active_filter_row(row_data)
        if not self._is_clearing_filter_rows:
            self._mark_filter_dirty()

    def _remove_filter_condition_row(self, row_data):
        if row_data not in self.filter_condition_rows:
            return
        row_data["frame"].destroy()
        self.filter_condition_rows.remove(row_data)
        if not self.filter_condition_rows:
            self._is_clearing_filter_rows = True
            self._add_filter_condition_row()
            self._is_clearing_filter_rows = False
            self._refresh_row_indices()
            self._mark_filter_dirty()
            return
        if self.active_filter_row is row_data:
            self.active_filter_row = None
        self._refresh_row_indices()
        self._refresh_filter_field_options()
        self._mark_filter_dirty()

    def _refresh_row_indices(self):
        for idx, row in enumerate(self.filter_condition_rows, start=1):
            row["index_var"].set(f"{idx}.")
        self._refresh_filter_row_styles()

    def _refresh_filter_row_styles(self):
        for idx, row in enumerate(self.filter_condition_rows):
            row["base_bg"] = self.filter_row_even_bg if idx % 2 == 0 else self.filter_row_odd_bg
            self._apply_filter_row_style(row)

    def _apply_filter_row_style(self, row_data):
        bg = row_data.get("base_bg", self.filter_row_even_bg)
        if self.active_filter_row is row_data:
            bg = self.filter_row_active_bg
        elif row_data.get("is_hover", False):
            bg = self.filter_row_hover_bg

        row_data["frame"].configure(bg=bg, highlightbackground=self.filter_row_border_color)
        row_data["index_label"].configure(bg=bg)
        row_data["value_container"].configure(bg=bg)
        row_data["second_value_label"].configure(bg=bg)
        row_data["error_label"].configure(bg=bg)

    def _set_row_hover_state(self, row_data, is_hover):
        if not is_hover:
            pointer_widget = self.winfo_containing(self.winfo_pointerx(), self.winfo_pointery())
            if pointer_widget and self._is_widget_inside_row(pointer_widget, row_data["frame"]):
                return
        row_data["is_hover"] = is_hover
        self._apply_filter_row_style(row_data)

    def _is_widget_inside_row(self, widget, row_frame):
        current = widget
        while current is not None:
            if current == row_frame:
                return True
            current = current.master
        return False

    def _refresh_filter_field_options(self):
        all_fields = list(self.filter_fields_order)
        self._is_refreshing_filter_options = True
        try:
            for row in self.filter_condition_rows:
                current_field = row["field_var"].get().strip()
                selected_fields = {
                    r["field_var"].get().strip()
                    for r in self.filter_condition_rows
                    if r is not row and r["field_var"].get().strip()
                }
                available_fields = [field for field in all_fields if field == current_field or field not in selected_fields]
                row["field_combo"].configure(values=available_fields)
                if current_field not in available_fields:
                    row["field_var"].set(available_fields[0] if available_fields else "")
                    current_field = row["field_var"].get().strip()
                self._refresh_row_field_behavior(row)
        finally:
            self._is_refreshing_filter_options = False

        selected_count = len({row["field_var"].get().strip() for row in self.filter_condition_rows if row["field_var"].get().strip()})
        if selected_count >= len(all_fields):
            self.add_filter_button.config(state=tk.DISABLED)
        else:
            self.add_filter_button.config(state=tk.NORMAL)

    def _on_filter_field_change(self, row_data):
        self._refresh_row_field_behavior(row_data)
        if not self._is_refreshing_filter_options:
            self._refresh_filter_field_options()
        self._on_row_input_changed(row_data)

    def _refresh_row_field_behavior(self, row_data):
        field_name = row_data["field_var"].get().strip()
        if not field_name and self.filter_fields_order:
            row_data["field_var"].set(self.filter_fields_order[0])
            field_name = self.filter_fields_order[0]

        field_meta = self.filter_field_meta.get(field_name)
        if not field_meta:
            return

        operators = field_meta.get("operators", [])
        row_data["operator_combo"].configure(values=operators)
        if row_data["operator_var"].get().strip() not in operators:
            row_data["operator_var"].set(operators[0] if operators else "")

        row_data["value_entry"].pack_forget()
        row_data["value_spin"].pack_forget()
        row_data["value_combo"].pack_forget()
        row_data["second_value_label"].pack_forget()
        row_data["second_value_entry"].pack_forget()
        row_data["second_value_spin"].pack_forget()

        integer_fields = getattr(self, "integer_filter_fields", set(getattr(self, "element_filter_fields", set())) | {"DBR"})

        if field_name == "Adduct":
            row_data["value_combo"].configure(values=self._get_current_adduct_filter_options())
            row_data["value_combo"].pack(side=tk.LEFT, fill=tk.X, expand=True)
        elif field_name in integer_fields:
            row_data["value_spin"].pack(side=tk.LEFT, fill=tk.X, expand=True)
        else:
            row_data["value_entry"].pack(side=tk.LEFT, fill=tk.X, expand=True)

        self._on_filter_operator_change(row_data)

    def _on_filter_operator_change(self, row_data):
        operator = row_data["operator_var"].get().strip()
        field_name = row_data["field_var"].get().strip()
        integer_fields = getattr(self, "integer_filter_fields", set(getattr(self, "element_filter_fields", set())) | {"DBR"})
        if operator == "区间":
            row_data["second_value_label"].pack(side=tk.LEFT, padx=(6, 6))
            if field_name in integer_fields:
                row_data["second_value_spin"].pack(side=tk.LEFT, fill=tk.X, expand=True)
            else:
                row_data["second_value_entry"].pack(side=tk.LEFT, fill=tk.X, expand=True)
        else:
            row_data["second_value_label"].pack_forget()
            row_data["second_value_entry"].pack_forget()
            row_data["second_value_spin"].pack_forget()
            row_data["second_value_var"].set("")
        self._on_row_input_changed(row_data)

    def _refresh_adduct_filter_options(self):
        options = self._get_current_adduct_filter_options()
        for row in getattr(self, "filter_condition_rows", []):
            if row["field_var"].get().strip() != "Adduct":
                continue
            row["value_combo"].configure(values=options)
            current_val = row["value_var"].get().strip()
            if current_val and current_val not in options:
                row["value_var"].set("")

    def _set_active_filter_row(self, row_data):
        self.active_filter_row = row_data
        self._refresh_filter_row_styles()

    def _apply_row_preset(self, row_data, preset):
        self._suspend_dirty_tracking = True
        try:
            row_data["field_var"].set(preset.get("field", row_data["field_var"].get()))
            self._refresh_row_field_behavior(row_data)
            row_data["operator_var"].set(preset.get("operator", row_data["operator_var"].get()))
            self._on_filter_operator_change(row_data)
            row_data["value_var"].set(preset.get("value", ""))
            row_data["second_value_var"].set(preset.get("second_value", ""))
        finally:
            self._suspend_dirty_tracking = False
        self._on_row_input_changed(row_data)

    def _on_row_input_changed(self, row_data):
        self._validate_row_input(row_data)
        self._mark_filter_dirty()

    def _validate_row_input(self, row_data):
        field_name = row_data["field_var"].get().strip()
        operator = row_data["operator_var"].get().strip()
        value = row_data["value_var"].get().strip()
        second_value = row_data["second_value_var"].get().strip()
        row_data["error_var"].set("")

        if not field_name or not operator:
            return True

        field_meta = self.filter_field_meta.get(field_name, {})
        if operator == "区间":
            if (value and not second_value) or (second_value and not value):
                row_data["error_var"].set("区间需填写上下限")
                return False

        if field_meta.get("type") == "number":
            parser = int if field_name in getattr(self, "integer_filter_fields", set()) else float
            value_error = "请输入有效整数" if parser is int else "请输入有效数值"
            upper_error = "区间上限需为整数" if parser is int else "区间上限需为数值"

            if value:
                try:
                    parser(value)
                except ValueError:
                    row_data["error_var"].set(value_error)
                    return False
            if operator == "区间" and second_value:
                try:
                    parser(second_value)
                except ValueError:
                    row_data["error_var"].set(upper_error)
                    return False
            if operator == "区间" and value and second_value and parser(value) > parser(second_value):
                row_data["error_var"].set("下限不能大于上限")
                return False

        return True

    def _serialize_draft_conditions(self):
        serialized = []
        for row in self.filter_condition_rows:
            field_name = row["field_var"].get().strip()
            operator = row["operator_var"].get().strip()
            value = row["value_var"].get().strip()
            second_value = row["second_value_var"].get().strip()
            if not field_name or not operator:
                continue
            if not value and not second_value:
                continue
            serialized.append((field_name, operator, value, second_value))
        return serialized

    def _mark_filter_dirty(self):
        if self._suspend_dirty_tracking:
            return
        self.is_filter_dirty = self._serialize_draft_conditions() != self.applied_conditions_signature
        self._update_filter_dirty_state()

    def _update_filter_dirty_state(self):
        if not hasattr(self, "filter_dirty_label"):
            return
        if self.is_filter_dirty:
            self.filter_dirty_label.configure(text="有未应用更改")
        else:
            self.filter_dirty_label.configure(text="")

    def _update_result_summary(self, total, matched):
        removed = max(total - matched, 0)
        self.result_stats_label.configure(text=f"总数: {total} | 命中: {matched} | 筛除: {removed}")
        summary_text = self._format_conditions_summary(self.applied_conditions)
        self.applied_summary_label.configure(text=f"已应用条件: {summary_text}")

    def _format_conditions_summary(self, conditions):
        if not conditions:
            return "无"
        parts = []
        for cond in conditions:
            if cond["operator"] == "区间":
                parts.append(f"{cond['field']}:[{cond['value']},{cond['second_value']}]")
            else:
                parts.append(f"{cond['field']} {cond['operator']} {cond['value']}")
        return " AND ".join(parts)

    def _show_empty_result_guidance(self, show):
        if not show:
            self.empty_result_label.place_forget()
            return
        self.empty_result_label.configure(
            text="当前条件下无匹配项\n建议：放宽数值条件、删除部分约束，或点击“清空条件”重试"
        )
        self.empty_result_label.place(relx=0.5, rely=0.5, anchor="center")

    def _on_apply_shortcut(self, _event=None):
        if self.winfo_exists():
            self._apply_filters()
        return "break"

    def _on_duplicate_shortcut(self, _event=None):
        if not self.active_filter_row:
            return "break"
        preset = {
            "field": self.active_filter_row["field_var"].get().strip(),
            "operator": self.active_filter_row["operator_var"].get().strip(),
            "value": self.active_filter_row["value_var"].get().strip(),
            "second_value": self.active_filter_row["second_value_var"].get().strip(),
        }
        if not preset["field"]:
            return "break"
        self._add_filter_condition_row(preset=preset)
        return "break"

    def _on_delete_shortcut(self, _event=None):
        focus_widget = self.focus_get()
        if self.active_filter_row and focus_widget and self._is_widget_in_filter_row(focus_widget):
            if len(self.filter_condition_rows) > 1:
                self._remove_filter_condition_row(self.active_filter_row)
            return "break"
        if self.table.focus_get() == self.table:
            self._delete_selected_row()
            return "break"
        return None

    def _is_widget_in_filter_row(self, widget):
        parent = widget
        while parent:
            if parent == self.filter_condition_container:
                return True
            parent = parent.master
        return False

    def _set_filter_action_state(self, applying):
        state = tk.DISABLED if applying else tk.NORMAL
        self.apply_filter_button.configure(state=state)
        self.clear_filter_button.configure(state=state)
        self.add_filter_button.configure(state=state if applying else tk.NORMAL)
        self.filter_feedback_label.configure(text="筛选中，请稍候..." if applying else "")
        if not applying:
            self._refresh_filter_field_options()

    def _filter_data_chunked(self, source_data, conditions, chunk_size=500):
        matched_rows = []
        for idx in range(0, len(source_data), chunk_size):
            chunk = source_data[idx: idx + chunk_size]
            for item in chunk:
                if all(self._item_match_condition(item, condition) for condition in conditions):
                    matched_rows.append(item)
            if idx + chunk_size < len(source_data):
                self.update_idletasks()
        return matched_rows

    def _render_rows_chunked(self, rows, start_idx=0, chunk_size=300):
        end_idx = min(start_idx + chunk_size, len(rows))
        for item in rows[start_idx:end_idx]:
            values = [item[col] for col in self.table["columns"]]
            self.table.insert("", "end", values=values, tags=(json.dumps(item),))
        if end_idx < len(rows):
            self.after(1, partial(self._render_rows_chunked, rows, end_idx, chunk_size))
        else:
            self._show_empty_result_guidance(len(rows) == 0)
            self._set_filter_action_state(False)

    def _get_current_adduct_filter_options(self):
        mode_adducts = self._get_adduct_config().get(self.ms_mode.get(), [])
        data_adducts = [
            str(item.get("Adduct", "")).strip()
            for item in getattr(self, 'data', [])
            if str(item.get("Adduct", "")).strip()
        ]
        return list(dict.fromkeys(mode_adducts + data_adducts))

    def _update_hidden_columns(self):
        visible_cols = ["M/Z", "Adduct", "Mol Weight", "DBR"]
        for col in self.table["columns"]:
            if col in visible_cols:
                continue
            if any(str(item.get(col, 0)) not in ("0", "0.0", "") for item in self.data):
                visible_cols.append(col)
        self.table["displaycolumns"] = visible_cols

    def auto_resize_columns(self):
        """更新列宽计算逻辑以适应新格式"""
        for col in self.table["columns"]:
            current_width = self.table.column(col, "width")
            if current_width <= 0:
                continue
            
            font = tkFont.Font()
            title_width = font.measure(col) + 20  # 标题宽度
            
            # 计算内容最大宽度（已格式化为4位小数）
            content_width = max(
                font.measure(str(item.get(col, ""))) 
                for item in self.data
            ) if self.data else 0
            
            new_width = max(title_width, content_width)
            self.table.column(col, width=new_width, minwidth=new_width, stretch=False)

    def _open_json_file(self):
        self.event_mgr.publish(
            EventType.STATUS_UPDATE, 
            data={"status_text": "loading..."}
        )

        initial_dir = PathManager().get_formula_generation_cache_path()
        initial_dir = Path(initial_dir).expanduser().resolve()
        initial_dir.mkdir(parents=True, exist_ok=True)

        original_cwd = Path.cwd()
        try:
            try:
                os.chdir(initial_dir)
            except OSError as ex:
                logging.warning(f"切换导入目录失败，将仅使用默认目录参数: {ex}")

            file_path = filedialog.askopenfilename(
                title="选择JSON文件",
                initialdir=str(initial_dir),
                filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")]
            )
        finally:
            try:
                os.chdir(original_cwd)
            except OSError as ex:
                logging.warning(f"恢复工作目录失败: {ex}")
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                
                required_keys = ["metadata", "input_params", "results"]
                if not all(key in data for key in required_keys):
                    raise ValueError("JSON文件缺少必要结构: {}".format(
                        ", ".join([k for k in required_keys if k not in data])
                    ))
                
                if not isinstance(data["results"], list):
                    raise TypeError("results字段必须为数组类型")
                
                self.data = self._map_data(data["results"])
                self._refresh_adduct_filter_options()
                self._apply_filters()
                self.auto_resize_columns()
                self._update_hidden_columns()

                # 分离不限和有限的元素
                elements = data["input_params"]["elements"]
                unlimited_elements = [elem for elem, count in elements.items() if count == -1]
                limited_elements = [f"{elem}<={count}个" for elem, count in elements.items() if count > 0]

                # 构建元素配置字符串
                element_config_parts = []
                if unlimited_elements:
                    element_config_parts.append(f"{', '.join(unlimited_elements)}不限个数")
                if limited_elements:
                    element_config_parts.append(', '.join(limited_elements))

                element_config_str = '; '.join(element_config_parts)

                logging.info("文件导入成功，参数如下:")
                logging.info(f"- 质谱模式: {data['input_params']['ms_mode']}")
                logging.info(f"- 加合离子: {', '.join(data['input_params']['adduct_model'])}")
                logging.info(f"- m/z: {data['input_params']['m2z']}")
                logging.info(f"- 误差范围: ±{data['input_params']['error_pct']}%")
                logging.info(f"- 误差范围: ±{data['input_params'].get('error_da', 0)} Da")
                logging.info(f"- 电荷数: {data['input_params']['charge']}")
                logging.info(f"- 元素配置: {element_config_str}")
                
            except json.JSONDecodeError as je:
                logging.error(f"JSON解析失败: {str(je)}")
            except (KeyError, ValueError, TypeError) as e:
                logging.error(f"文件内容异常: {str(e)}")
            except Exception as e:
                logging.error(f"文件读取失败: {str(e)}")
        
        self.event_mgr.publish(
            EventType.STATUS_UPDATE, 
            data={"status_text": "done"}
        )

    def _setup_buttons(self):
        btn_frame = self.widget_factory.create_frame(self.left_content_frame)
        btn_frame.grid(row=4, column=0, sticky="ew", pady=(BaseConfig.PADDING_B, 0))
        for idx in range(2):
            btn_frame.grid_columnconfigure(idx, weight=1, uniform="formula_generation_actions")

        common_button_kwargs = {
            "cooldown": 3,
            "width": 10,
            "height": 34,
            "hover_bg": BaseConfig.ACCENT_COLOR,
        }

        btn_run = self.widget_factory.create_rounded_button(
            btn_frame,
            text="开始分析",
            command=self._run_analysis,
            **common_button_kwargs,
        )
        btn_run.grid(row=0, column=0, sticky="ew", padx=(0, BaseConfig.PADDING_A), pady=(0, BaseConfig.PADDING_A))

        btn_open = self.widget_factory.create_rounded_button(
            btn_frame,
            text="导入文件",
            command=self._open_json_file,
            **common_button_kwargs,
        )
        btn_open.grid(row=0, column=1, sticky="ew", padx=(BaseConfig.PADDING_A, 0), pady=(0, BaseConfig.PADDING_A))

        btn_refresh = self.widget_factory.create_rounded_button(
            btn_frame,
            text="刷新页面",
            command=self._refresh_page,
            **common_button_kwargs,
        )
        btn_refresh.grid(row=1, column=0, sticky="ew", padx=(0, BaseConfig.PADDING_A), pady=(BaseConfig.PADDING_A, 0))

        btn_placeholder = self.widget_factory.create_rounded_button(
            btn_frame,
            text="",
            command=lambda: None,
            cooldown=0,
            width=10,
            height=34,
            hover_bg=BaseConfig.PRIMARY_COLOR,
        )
        btn_placeholder.config(state=tk.DISABLED)
        btn_placeholder.grid(row=1, column=1, sticky="ew", padx=(BaseConfig.PADDING_A, 0), pady=(BaseConfig.PADDING_A, 0))

    def _refresh_page(self):
        self.event_mgr.publish(
            EventType.STATUS_UPDATE, 
            data={"status_text": "loading..."}
        )

        # 1. 重置输入参数
        self.ms_mode.set("ESI+")
        self.m2z.set(100)
        self.error_pct.set(0.1)
        self.error_da.set(0.0)
        self.charge.set(1)
        
        # 2. 重置元素配置
        for elem in self.element_vars:
            self.element_vars[elem].set("不限" if elem in {"C", "N", "O"} else "0")
        
        # 3. 重置加合物选项
        self.adduct_vars = {}
        self._on_ms_mode_change()  # 触发模式变化以重建加合物选项
        
        # 4. 清空表格数据
        self.data = []
        self._refresh_adduct_filter_options()
        self.table.delete(*self.table.get_children())
        
        # 5. 清除筛选条件
        self._clear_filter_conditions(reapply=False)
        
        # 6. 重置隐藏列
        self._update_hidden_columns()

        logging.debug("页面已刷新")

        self.event_mgr.publish(
            EventType.STATUS_UPDATE, 
            data={"status_text": "done"}
        )

    def _run_analysis(self):
        params = {
            "ms_mode": self.ms_mode.get(),
            "adduct_model": [k for k, v in self.adduct_vars.items() if v.get()],
            "m2z": self.m2z.get(),
            "error_pct": self.error_pct.get(),
            "error_da": self.error_da.get(),
            "charge": self.charge.get(),
            "elements": {k: v.get() for k, v in self.element_vars.items()}
        }

        validator = DataValidator()
        if not validator.validate(params):
            logging.error("参数输入有误，请检查")
            self.event_mgr.publish(
                EventType.STATUS_UPDATE,
                data={"status_text": "done"}
            )
            return

        elements = params["elements"]
        for k, v in elements.items():
            if v == "不限":
                params['elements'][k] = -1
            else:
                params['elements'][k] = int(v)

        logging.debug(f"参数: {params}")
        self.event_mgr.publish(
            EventType.STATUS_UPDATE,
            data={"status_text": "running..."}
        )

        try:
            self.thread_pool.submit(self._run_analysis_background, params)
        except Exception as ex:
            logging.error(f"提交分析任务失败: {ex}")
            self.event_mgr.publish(
                EventType.STATUS_UPDATE,
                data={"status_text": "done"}
            )

    def _run_analysis_background(self, params):
        try:
            result = start_analysis(params)
            self.data = self._map_data(result["results"])
            self.after(0, self._refresh_adduct_filter_options)
            self.after(0, self._apply_filters)
            self.after(0, self.auto_resize_columns)
            self.after(0, self._update_hidden_columns)
        except Exception as e:
            logging.error(f"分析失败: {e}")
        finally:
            self.after(0, self.event_mgr.publish, EventType.STATUS_UPDATE, {"status_text": "done"})

    def _map_data(self, raw_data):
        mapped = []
        for item in raw_data:
            formula_data = item.get("formula", item.get("elements", {})) or {}
            row = {
                "M/Z": self._format_float(item["calculated_properties"].get("predicted_mz", "")),
                "Adduct": item["adduct_type"],
                "Mol Weight": self._format_float(item["calculated_properties"].get("molecular_weight", "")),
                "DBR": item["calculated_properties"].get("dbr", ""),
                "C": self._normalize_element_count(formula_data.get("C", 0)),
                "H": self._normalize_element_count(formula_data.get("H", 0)),
                "N": self._normalize_element_count(formula_data.get("N", 0)),
                "O": self._normalize_element_count(formula_data.get("O", 0)),
                "S": self._normalize_element_count(formula_data.get("S", 0)),
                "P": self._normalize_element_count(formula_data.get("P", 0)),
                "Si": self._normalize_element_count(formula_data.get("Si", 0)),
                "F": self._normalize_element_count(formula_data.get("F", 0)),
                "Cl": self._normalize_element_count(formula_data.get("Cl", 0)),
                "Br": self._normalize_element_count(formula_data.get("Br", 0)),
                "I": self._normalize_element_count(formula_data.get("I", 0)),
                "B": self._normalize_element_count(formula_data.get("B", 0)),
                "Se": self._normalize_element_count(formula_data.get("Se", 0)),
            }
            mapped.append(row)
        return mapped

    def _normalize_element_count(self, value):
        if value in ("", None):
            return 0
        try:
            return int(float(value))
        except (ValueError, TypeError):
            return 0

    def _format_float(self, value):
        """统一浮点数格式化方法"""
        try:
            return f"{float(value):.4f}"  # 强制保留4位小数（自动四舍五入）
        except (ValueError, TypeError):
            return str(value)  # 非数值类型直接转字符串
    
    def _apply_filters(self, *args):
        self.filter_feedback_label.configure(text="")
        conditions = self._collect_filter_conditions()
        if conditions is None:
            return

        self._set_filter_action_state(True)
        self.table.delete(*self.table.get_children())
        filtered_rows = self._filter_data_chunked(self.data, conditions)
        self.applied_conditions = conditions
        self.applied_conditions_signature = self._serialize_draft_conditions()
        self.is_filter_dirty = False
        self._update_filter_dirty_state()
        self._update_result_summary(total=len(self.data), matched=len(filtered_rows))
        self._render_rows_chunked(filtered_rows)

    def _collect_filter_conditions(self):
        conditions = []
        invalid_rows = []
        for row in self.filter_condition_rows:
            field_name = row["field_var"].get().strip()
            operator = row["operator_var"].get().strip()
            value = row["value_var"].get().strip()
            second_value = row["second_value_var"].get().strip()

            if not field_name or not operator:
                continue

            if operator == "区间":
                if not value and not second_value:
                    continue
                if not value or not second_value:
                    row["error_var"].set("区间需填写上下限")
                    invalid_rows.append(field_name)
                    continue
            elif not value:
                continue

            field_meta = self.filter_field_meta.get(field_name, {})
            if field_meta.get("type") == "number":
                try:
                    parsed_value = float(value)
                except ValueError:
                    row["error_var"].set("请输入有效数值")
                    invalid_rows.append(field_name)
                    continue

                parsed_second_value = None
                if operator == "区间":
                    try:
                        parsed_second_value = float(second_value)
                    except ValueError:
                        row["error_var"].set("区间上限需为数值")
                        invalid_rows.append(field_name)
                        continue
                    if parsed_value > parsed_second_value:
                        row["error_var"].set("下限不能大于上限")
                        invalid_rows.append(field_name)
                        continue

                conditions.append({
                    "field": field_name,
                    "type": "number",
                    "operator": operator,
                    "value": parsed_value,
                    "second_value": parsed_second_value,
                })
            else:
                conditions.append({
                    "field": field_name,
                    "type": "text",
                    "operator": operator,
                    "value": value,
                })

                if invalid_rows:
                    self.filter_feedback_label.configure(text=f"存在 {len(invalid_rows)} 条非法条件，请先修正后再应用")
                    return None
        return conditions

    def _item_match_condition(self, item, condition):
        field_name = condition["field"]
        cell_value = item.get(field_name, "")

        if condition["type"] == "text":
            cell_text = str(cell_value).strip().lower()
            target_text = str(condition["value"]).strip().lower()
            if condition["operator"] == "等于":
                return cell_text == target_text
            return target_text in cell_text

        try:
            cell_number = float(cell_value)
        except (ValueError, TypeError):
            return False

        operator = condition["operator"]
        target = condition["value"]
        if operator == ">":
            return cell_number > target
        if operator == ">=":
            return cell_number >= target
        if operator == "=":
            return cell_number == target
        if operator == "<=":
            return cell_number <= target
        if operator == "<":
            return cell_number < target
        if operator == "区间":
            return target <= cell_number <= condition["second_value"]
        return True

    def _clear_filter_conditions(self, reapply=True):
        self._is_clearing_filter_rows = True
        for row in self.filter_condition_rows:
            row["frame"].destroy()
        self.filter_condition_rows = []
        self._add_filter_condition_row()
        self._is_clearing_filter_rows = False
        self.filter_feedback_label.configure(text="")
        self._mark_filter_dirty()
        if reapply:
            self._apply_filters()

    def _add_filter_from_table_context(self):
        column_name = self._current_table_context.get("column_name", "")
        cell_value = self._current_table_context.get("cell_value", "")
        if not column_name or column_name not in self.filter_fields_order:
            messagebox.showinfo("提示", "请在表格中选中有效单元格后再执行此操作")
            return

        preset = {
            "field": column_name,
            "operator": "=" if self.filter_field_meta.get(column_name, {}).get("type") == "number" else "等于",
            "value": cell_value,
            "second_value": "",
        }
        self._add_filter_condition_row(preset=preset)
        self.filter_feedback_label.configure(text=f"已从表格添加草稿条件: {column_name} {preset['operator']} {cell_value}")

    def _on_table_left_press(self, event):
        row_id = self.table.identify_row(event.y)
        self._table_selection_anchor = row_id or None

    def _on_table_drag_select(self, event):
        if not self._table_selection_anchor:
            return

        target_row = self.table.identify_row(event.y)
        if not target_row:
            return "break"

        children = self.table.get_children()
        try:
            start_idx = children.index(self._table_selection_anchor)
            end_idx = children.index(target_row)
        except ValueError:
            return "break"

        selected_rows = children[min(start_idx, end_idx):max(start_idx, end_idx) + 1]
        self.table.selection_set(selected_rows)
        self.table.focus(target_row)
        return "break"

    def _on_table_double_click(self, event):
        item = self.table.selection()
        if not item:
            return
        item = item[0]
        tags = self.table.item(item, 'tags')
        if not tags:
            return
        try:
            data = json.loads(tags[0])
        except Exception as e:
            logging.error(f"无法解析数据项: {e}")
            return

        formula_str = self._formula_from_row_data(data)

        # 发送事件
        self.event_mgr.publish(EventType.ADD_FORMULA, data=formula_str, priority=EventPriority.NORMAL)

    def _on_table_right_click(self, event):
        row_id = self.table.identify_row(event.y)
        column_token = self.table.identify_column(event.x)
        column_name = ""
        cell_value = ""
        if column_token and column_token.startswith("#"):
            try:
                column_index = int(column_token[1:]) - 1
                if 0 <= column_index < len(self.table["columns"]):
                    column_name = self.table["columns"][column_index]
            except ValueError:
                column_name = ""

        if row_id:
            current_selection = set(self.table.selection())
            if row_id not in current_selection:
                self.table.selection_set(row_id)
            self.table.focus(row_id)
            if column_name:
                values = self.table.item(row_id, "values")
                try:
                    cell_value = str(values[self.table["columns"].index(column_name)])
                except Exception:
                    cell_value = ""

        self._current_table_context = {
            "row_id": row_id,
            "column_name": column_name,
            "cell_value": cell_value,
        }

        context_label = "按当前列添加筛选"
        if column_name:
            context_label = f"按当前列添加筛选 ({column_name})"
        self.table_popup_menu.entryconfigure(0, label=context_label)

        if column_name and column_name in self.filter_fields_order:
            self.table_popup_menu.entryconfigure(0, state=tk.NORMAL)
        else:
            self.table_popup_menu.entryconfigure(0, state=tk.DISABLED)

        if row_id:
            try:
                self.table_popup_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.table_popup_menu.grab_release()
        elif column_name:
            try:
                self.table_popup_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.table_popup_menu.grab_release()
        return "break"

    def _send_selected_row_to_bus(self):
        selected_items = self.table.selection()
        if not selected_items:
            messagebox.showwarning("发送失败", "请先选中要发送的分子式")
            return

        formulas_to_send = []
        for row_id in selected_items:
            tags = self.table.item(row_id, 'tags')
            if not tags:
                continue
            try:
                data = json.loads(tags[0])
            except Exception as e:
                logging.error(f"无法解析数据项: {e}")
                continue

            formula_str = self._formula_from_row_data(data)
            if formula_str and formula_str not in formulas_to_send:
                formulas_to_send.append(formula_str)

        if not formulas_to_send:
            messagebox.showwarning("发送失败", "未能从选中项中解析出有效分子式")
            return

        payload = formulas_to_send if len(formulas_to_send) > 1 else formulas_to_send[0]
        self.event_mgr.publish(EventType.ADD_FORMULA, data=payload, priority=EventPriority.NORMAL)
        logging.info(f"已发送 {len(formulas_to_send)} 个分子式到分子式 bus: {', '.join(formulas_to_send)}")
        messagebox.showinfo("发送成功", f"已发送 {len(formulas_to_send)} 个分子式到分子式 bus")

    def _delete_selected_row(self):
        selected_row_ids = self.table.selection()
        if not selected_row_ids:
            messagebox.showwarning("删除失败", "请先选中要删除的行")
            return

        selected_formulas = []
        selected_tags = []
        for row_id in selected_row_ids:
            tags = self.table.item(row_id, 'tags')
            if not tags:
                continue
            selected_tags.append(tags[0])
            try:
                data = json.loads(tags[0])
                formula_str = self._formula_from_row_data(data)
                if formula_str:
                    selected_formulas.append(formula_str)
            except Exception as e:
                logging.error(f"无法解析数据项: {e}")

        preview_text = chr(10).join(selected_formulas[:10]) if selected_formulas else ""
        if len(selected_formulas) > 10:
            preview_text += f"{chr(10)}... 共 {len(selected_formulas)} 个"

        if not messagebox.askyesno("确认删除", f"是否删除选中的分子式？{chr(10)}{preview_text}"):
            return

        if selected_tags:
            remaining_data = []
            pending_tags = list(selected_tags)
            for data_item in self.data:
                encoded = json.dumps(data_item, ensure_ascii=False)
                if encoded in pending_tags:
                    pending_tags.remove(encoded)
                    continue
                remaining_data.append(data_item)
            self.data = remaining_data

        for row_id in selected_row_ids:
            self.table.delete(row_id)
        self._apply_filters()
        logging.info(f"删除分子式 {len(selected_row_ids)} 条")

    def _formula_from_row_data(self, data):
        elements_order = ['C', 'H', 'N', 'O', 'S', 'P', 'Si', 'F', 'Cl', 'Br', 'I', 'B', 'Se']
        formula = []
        for elem in elements_order:
            raw_count = data.get(elem, 0)
            if raw_count in ("", None):
                count = 0
            else:
                try:
                    count = int(float(raw_count))
                except (ValueError, TypeError):
                    count = 0

            if count > 0:
                if count == 1:
                    formula.append(f'{elem}')
                else:
                    formula.append(f"{elem}{count}")
        return ''.join(formula)
