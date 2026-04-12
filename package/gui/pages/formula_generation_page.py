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
import re

class FormulaGenerationPage(BasePage):

    def __init__(self, parent, event_mgr):
        super().__init__(parent, event_mgr, title="Formula Generation")
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
        self.grid_columnconfigure(0, weight=0)
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self.left_frame.grid(row=0, column=0, sticky="nsw")
        self.left_frame.grid_propagate(False)  # 禁用自动调整
        self.right_frame.grid(row=0, column=1, sticky="nsew")

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

        # 绑定窗口调整事件
        self.bind("<Configure>", self.on_window_resize)

        self.event_mgr.publish(
            EventType.STATUS_UPDATE, 
            data={"status_text": "done"}
        )

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
        self.adduct_frame = self.widget_factory.create_labelframe(self.left_frame, text="加合物模型")
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

        # 初始化网格布局并禁用自动调整
        self.left_frame.columnconfigure(0, weight=1)
        self.left_frame.grid_propagate(False)  # 禁止子组件影响框架尺寸

        def create_input_frame(parent, text, row):
            frame = self.widget_factory.create_labelframe(parent, text=text)
            frame.grid(row=row, column=0, sticky="ew")
            return frame

        def create_grid_input_frame(parent, text, row, col):
            frame = self.widget_factory.create_labelframe(parent, text=text)
            frame.grid(row=row, column=col, sticky="ew", padx=BaseConfig.PADDING_A, pady=BaseConfig.PADDING_A)
            return frame

        # 质谱模式框架
        ms_mode_frame = create_input_frame(self.left_frame, "质谱模式", 0)
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
        params_frame = create_input_frame(self.left_frame, "参数输入", 2)
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

        self.elements_frame = create_input_frame(self.left_frame, "元素配置(不超过)", 3)
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

        # 筛选栏设置
        filter_rows = [
            ["Adduct", "M/Z", "DBR", "C"],
            ["H", "N", "O", "S"],
            ["P", "Si", "F", "Cl"],
            ["Br", "I", "B", "Se"],
        ]
        columns = [col for row in filter_rows for col in row] + ['Mol Weight']

        self.filters = {}
        for row_idx, row_columns in enumerate(filter_rows):
            for col_idx, col_name in enumerate(row_columns):
                labelframe = self.widget_factory.create_labelframe(
                    filter_frame,
                    text=col_name,
                )
                labelframe.grid(row=row_idx, column=col_idx, sticky="nsew", padx=BaseConfig.PADDING_A, pady=BaseConfig.PADDING_A)

                if col_name == "Adduct":
                    var = tk.StringVar()
                    entry = ttk.Combobox(
                        labelframe,
                        textvariable=var,
                        values=[],
                        state='readonly',
                        width=12,
                        font=(BaseConfig.FONT_STYLE, BaseConfig.FONT_SIZE)
                    )
                    entry.pack(fill=tk.X, **AppUIConfig.FunctionZone.FormulaGenerationPage.padding)
                    var.trace_add("write", self._apply_filters)
                    self.adduct_filter_var = var
                    self.adduct_filter_combo = entry
                    self.filters[col_name] = {'type': 'text', 'var': var}
                else:
                    min_var = tk.StringVar()
                    max_var = tk.StringVar()
                    range_frame = tk.Frame(labelframe, bg=BaseConfig.BACKGROUND)
                    range_frame.pack(fill=tk.X, **AppUIConfig.FunctionZone.FormulaGenerationPage.padding)

                    min_spin = ttk.Spinbox(
                        range_frame,
                        textvariable=min_var,
                        from_=0,
                        to=999,
                        width=5,
                        font=(BaseConfig.FONT_STYLE, BaseConfig.FONT_SIZE)
                    )
                    min_spin.pack(side=tk.LEFT, fill=tk.X, expand=True)
                    tk.Label(range_frame, text="~", bg=BaseConfig.BACKGROUND, fg=BaseConfig.TEXT_LIGHT, font=(BaseConfig.FONT_STYLE, BaseConfig.FONT_SIZE)).pack(side=tk.LEFT, padx=(4, 4))
                    max_spin = ttk.Spinbox(
                        range_frame,
                        textvariable=max_var,
                        from_=0,
                        to=999,
                        width=5,
                        font=(BaseConfig.FONT_STYLE, BaseConfig.FONT_SIZE)
                    )
                    max_spin.pack(side=tk.LEFT, fill=tk.X, expand=True)
                    min_var.trace_add("write", self._apply_filters)
                    max_var.trace_add("write", self._apply_filters)
                    self.filters[col_name] = {
                        'type': 'range',
                        'min': min_var,
                        'max': max_var,
                    }

        # 确保列权重均匀分布
        max_cols = max(len(row) for row in filter_rows)
        for col in range(max_cols):
            filter_frame.grid_columnconfigure(col, weight=1)

        # 表格部分
        vsb = tk.Scrollbar(table_frame, orient=tk.VERTICAL)
        hsb = tk.Scrollbar(table_frame, orient=tk.HORIZONTAL)
        self.table = ttk.Treeview(
            table_frame,
            columns=columns,
            displaycolumns=['M/Z', 'Adduct', 'Mol Weight', 'DBR'],
            show="headings",
            selectmode="browse",
            xscrollcommand=hsb.set,
            yscrollcommand=vsb.set
        )
        vsb.config(command=self.table.yview)
        hsb.config(command=self.table.xview)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)
        self.table.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        for col in columns:
            self.table.heading(col, text=col)
            self.table.column(col, minwidth=50, anchor=tk.CENTER, stretch=False)

        self.table_popup_menu = self.widget_factory.create_menu(self.table, tearoff=0)
        self.table_popup_menu.add_command(label="发送到分子式 bus", command=self._send_selected_row_to_bus)
        self.table_popup_menu.add_separator()
        self.table_popup_menu.add_command(label="删除", command=self._delete_selected_row)
        self.table.bind("<Button-3>", self._on_table_right_click)

        self.table.bind("<Double-1>", self._on_table_double_click)
        self._refresh_adduct_filter_options()

    def _refresh_adduct_filter_options(self):
        if not hasattr(self, 'adduct_filter_combo') or not hasattr(self, 'adduct_filter_var'):
            return

        mode_adducts = self._get_adduct_config().get(self.ms_mode.get(), [])
        data_adducts = [
            str(item.get("Adduct", "")).strip()
            for item in getattr(self, 'data', [])
            if str(item.get("Adduct", "")).strip()
        ]
        options = list(dict.fromkeys(mode_adducts + data_adducts))

        self.adduct_filter_combo.configure(values=options)
        current_val = self.adduct_filter_var.get().strip()
        if current_val and current_val not in options:
            self.adduct_filter_var.set("")

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

        file_path = filedialog.askopenfilename(
            title="选择JSON文件",
            filetypes=[("JSON文件", "*.json"), ("所有文件", "*.*")]
        )
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
        btn_frame = self.widget_factory.create_frame(self.left_frame)
        btn_frame.grid(row=4, column=0, sticky="ew", pady=(BaseConfig.PADDING_B, 0))
        for idx in range(2):
            btn_frame.grid_columnconfigure(idx, weight=1)
        for idx in range(2):
            btn_frame.grid_rowconfigure(idx, weight=1)

        btn_run = self.widget_factory.create_rounded_button(
            btn_frame,
            text="开始分析",
            command=self._run_analysis,
            cooldown=3,
            width="92",
            height="34",
            hover_bg=BaseConfig.ACCENT_COLOR,
        )
        btn_run.grid(row=0, column=0, sticky="ew", padx=(0, BaseConfig.PADDING_A), pady=(0, BaseConfig.PADDING_A))

        btn_open = self.widget_factory.create_rounded_button(
            btn_frame,
            text="导入文件",
            command=self._open_json_file,
            cooldown=3,
            width="92",
            height="34",
            hover_bg=BaseConfig.ACCENT_COLOR,
        )
        btn_open.grid(row=0, column=1, sticky="ew", padx=(BaseConfig.PADDING_A, 0), pady=(0, BaseConfig.PADDING_A))

        btn_refresh = self.widget_factory.create_rounded_button(
            btn_frame,
            text="刷新页面",
            command=self._refresh_page,
            cooldown=3,
            width="92",
            height="34",
            hover_bg=BaseConfig.ACCENT_COLOR,
        )
        btn_refresh.grid(row=1, column=0, sticky="ew", padx=(0, BaseConfig.PADDING_A), pady=(BaseConfig.PADDING_A, 0))

        btn_placeholder = self.widget_factory.create_rounded_button(
            btn_frame,
            text="",
            command=lambda: None,
            cooldown=0,
            width="92",
            height="34",
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
        for filter_control in self.filters.values():
            if isinstance(filter_control, dict) and filter_control.get('type') == 'range':
                filter_control['min'].set("")
                filter_control['max'].set("")
            elif isinstance(filter_control, dict) and filter_control.get('type') == 'text':
                filter_control['var'].set("")
            else:
                try:
                    filter_control.set("")
                except Exception:
                    pass
        
        # 6. 重置隐藏列
        self._update_hidden_columns()

        logging.debug("页面已刷新")

        self.event_mgr.publish(
            EventType.STATUS_UPDATE, 
            data={"status_text": "done"}
        )

    def _run_analysis(self):
        self.event_mgr.publish(
            EventType.STATUS_UPDATE, 
            data={"status_text": "running..."}
        )

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
            return
        
        elements = params["elements"]
        for k, v in elements.items():
            if v == "不限":
                params['elements'][k] = -1
            else:
                params['elements'][k] = int(v)

        logging.debug(f"参数: {params}")

        self.thread_pool.submit(self._run_analysis_background, params)

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
            row = {
                "M/Z": self._format_float(item["calculated_properties"].get("predicted_mz", "")),
                "Adduct": item["adduct_type"],
                "Mol Weight": self._format_float(item["calculated_properties"].get("molecular_weight", "")),
                "DBR": item["calculated_properties"].get("dbr", ""),
                "C": item["formula"].get("C", ""),
                "H": item["formula"].get("H", ""),
                "N": item["formula"].get("N", ""),
                "O": item["formula"].get("O", ""),
                "S": item["formula"].get("S", ""),
                "P": item["formula"].get("P", ""),
                "Si": item["formula"].get("Si", ""),
                "F": item["formula"].get("F", ""),
                "Cl": item["formula"].get("Cl", ""),
                "Br": item["formula"].get("Br", ""),
                "I": item["formula"].get("I", ""),
                "B": item["formula"].get("B", ""),
                "Se": item["formula"].get("Se", ""),  
            }
            mapped.append(row)
        return mapped

    def _format_float(self, value):
        """统一浮点数格式化方法"""
        try:
            return f"{float(value):.4f}"  # 强制保留4位小数（自动四舍五入）
        except (ValueError, TypeError):
            return str(value)  # 非数值类型直接转字符串
    
    def _apply_filters(self, *args):
        self.table.delete(*self.table.get_children())
        for item in self.data:
            valid = True
            for col, filter_control in self.filters.items():
                if isinstance(filter_control, dict):
                    if filter_control['type'] == 'text':
                        filter_val = filter_control['var'].get().strip()
                        if not filter_val:
                            continue
                        cell_val = item.get(col, "")
                        if filter_val.lower() not in cell_val.lower():
                            valid = False
                            break
                    elif filter_control['type'] == 'range':
                        min_val = filter_control['min'].get().strip()
                        max_val = filter_control['max'].get().strip()
                        if not min_val and not max_val:
                            continue
                        try:
                            cell_val_str = item.get(col, "")
                            cell_num = float(cell_val_str)
                        except (ValueError, TypeError):
                            valid = False
                            break
                        if min_val:
                            try:
                                if cell_num < float(min_val):
                                    valid = False
                                    break
                            except ValueError:
                                pass
                        if max_val:
                            try:
                                if cell_num > float(max_val):
                                    valid = False
                                    break
                            except ValueError:
                                pass
                else:
                    filter_val = filter_control.get().strip()
                    if not filter_val:
                        continue
                    if col == "Adduct":
                        if filter_val.lower() not in item.get(col, "").lower():
                            valid = False
                            break

            if valid:
                values = [item[col] for col in self.table["columns"]]
                self.table.insert("", "end", values=values, tags=(json.dumps(item),))

    def on_window_resize(self, event):
        # 动态调整元素配置区高度
        if hasattr(self, 'elements_frame'):
            self.elements_frame.config(
                height=int(event.height * 0.3)
            )

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
        if row_id:
            self.table.selection_set(row_id)
            try:
                self.table_popup_menu.tk_popup(event.x_root, event.y_root)
            finally:
                self.table_popup_menu.grab_release()
        return "break"

    def _send_selected_row_to_bus(self):
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
        self.event_mgr.publish(EventType.ADD_FORMULA, data=formula_str, priority=EventPriority.NORMAL)
        logging.info(f"已发送 {formula_str} 到分子式 bus")

    def _delete_selected_row(self):
        item = self.table.selection()
        if not item:
            messagebox.showwarning("删除失败", "请先选中要删除的行")
            return

        row_id = item[0]
        tags = self.table.item(row_id, 'tags')
        formula_str = None
        if tags:
            try:
                data = json.loads(tags[0])
                formula_str = self._formula_from_row_data(data)
            except Exception as e:
                logging.error(f"无法解析数据项: {e}")

        if not messagebox.askyesno("确认删除", f"是否删除选中的分子式？{chr(10)}{formula_str if formula_str else ''}"):
            return

        if tags:
            try:
                data = json.loads(tags[0])
                filtered_data = [item for item in self.data if json.dumps(item, ensure_ascii=False) != tags[0]]
                self.data = filtered_data
            except Exception:
                pass

        self.table.delete(row_id)
        self._apply_filters()
        logging.info(f"删除分子式: {formula_str}")

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
