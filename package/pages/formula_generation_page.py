import tkinter as tk
from tkinter import ttk, filedialog
from .base_page import BasePage
from ..core.event import EventBus, Event
from ..core.thread_pool import ThreadPool
from ..back_end.formulaGeneration import start_analysis
from ..utils.data_validator import DataValidator
from ..utils.widget_factory import WidgetFactory
from ..config import AppConfig
import logging
import json
from pathlib import Path
import tkinter.font as tkFont

class FormulaGenerationPage(BasePage):

    def __init__(self, parent, event_bus):
        super().__init__(parent, event_bus, title="Formula Generation")
        self.widget_factory = WidgetFactory()
        self.left_frame = self.widget_factory.create_frame(self, **AppConfig.FunctionZone.FormulaGenerationPage.input_frame)
        self.right_frame = self.widget_factory.create_frame(self, **AppConfig.FunctionZone.FormulaGenerationPage.output_frame)

        # 初始化加合物框架
        self.adduct_frame = None
        self.adduct_vars = {}  # 重置为字典存储当前选中的加合物

        # 使用网格布局，左侧占1份，右侧占3份
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

    def _get_adduct_config(self):
        config_path = Path(__file__).parent.parent / "back_end/config.json"
        with open(config_path, "r", encoding="utf-8") as f:
            config_data = json.load(f)
            adducts_config = config_data["adducts"]
        return {
            mode: list(adducts.values()) 
            for mode, adducts in adducts_config.items()
        }

    def _on_ms_mode_change(self, *args):
        current_mode = self.ms_mode.get()
        adduct_config = self._get_adduct_config()
        max_adduct_rows = 1
        for adduct_modes in adduct_config.values():
            max_adduct_rows = max(max_adduct_rows, len(adduct_modes) + 1)  # 1行用于标题

        adducts = adduct_config.get(current_mode, [])
        
        # 销毁旧框架
        if hasattr(self, 'adduct_frame') and self.adduct_frame:
            self.adduct_frame.destroy()
            self.adduct_frame = None
        
        # 创建新框架
        self.adduct_frame = self.widget_factory.create_labelframe(self.left_frame, text="加合物模型")
        self.adduct_frame.grid(row=1, column=0, sticky="ew")
        
        # 禁用自动调整
        self.adduct_frame.grid_propagate(True)
        
        # 预配置列和行
        self.adduct_frame.grid_columnconfigure(0, weight=1)  # 列配置
        
        # 重置变量
        self.adduct_vars = {}
        
        # 添加选项
        for idx, adduct in enumerate(adducts):
            var = tk.BooleanVar()
            cb = self.widget_factory.create_checkbutton(
                self.adduct_frame, 
                text=adduct, 
                variable=var,
            )
            cb.grid(row=idx, column=0, sticky="w")
            
            self.adduct_vars[adduct] = var

    def _setup_left_frame(self):
        # 初始化网格布局并禁用自动调整
        self.left_frame.columnconfigure(0, weight=1)
        self.left_frame.grid_propagate(False)  # 禁止子组件影响框架尺寸
        
        # 质谱模式框架
        ms_mode_frame = self.widget_factory.create_labelframe(self.left_frame, text="质谱模式")
        ms_mode_frame.grid(row=0, column=0, sticky="ew")
        self.ms_mode = tk.StringVar(value="ESI+")
        self.ms_mode.trace_add("write", self._on_ms_mode_change)
        
        # 限制OptionMenu宽度
        option_menu = ttk.OptionMenu(
            ms_mode_frame, 
            self.ms_mode, 
            "ESI+", 
            *["ESI+", "ESI-", "EI+", "EI-"]
        )
        option_menu.pack(side=tk.LEFT, **AppConfig.FunctionZone.FormulaGenerationPage.padding)
        
        # m/z值输入框
        m2z_frame = self.widget_factory.create_labelframe(self.left_frame, text="m/z值")
        m2z_frame.grid(row=2, column=0, sticky="w")
        self.m2z = tk.DoubleVar(value=100)
        entry = self.widget_factory.create_entry(m2z_frame, textvariable=self.m2z, **AppConfig.FunctionZone.FormulaGenerationPage.input_entry)
        entry.pack(**AppConfig.FunctionZone.FormulaGenerationPage.padding)
        
        # 误差范围输入框
        error_frame = self.widget_factory.create_labelframe(self.left_frame, text="误差范围 (%)")
        error_frame.grid(row=3, column=0, sticky="w")
        self.error_pct = tk.DoubleVar(value=0.1)
        entry = self.widget_factory.create_entry(error_frame, textvariable=self.error_pct, **AppConfig.FunctionZone.FormulaGenerationPage.input_entry)
        entry.pack(**AppConfig.FunctionZone.FormulaGenerationPage.padding)
        
        # 电荷数输入框
        charge_frame = self.widget_factory.create_labelframe(self.left_frame, text="电荷数")
        charge_frame.grid(row=4, column=0, sticky="w")
        self.charge = tk.IntVar(value=1)
        entry = self.widget_factory.create_entry(charge_frame, textvariable=self.charge, **AppConfig.FunctionZone.FormulaGenerationPage.input_entry)
        entry.pack(**AppConfig.FunctionZone.FormulaGenerationPage.padding)

        # 元素配置区优化
        elements = ["C", "N", "O", "S", "P", "Si", "F", "Cl", "Br", "I", "B", "Se"]
        self.element_vars = {
            e: tk.StringVar(value="-1" if e in {"C", "N", "O"} else "0") 
            for e in elements
        }

        elements_frame = self.widget_factory.create_labelframe(self.left_frame, text="元素配置(不超过)")
        elements_frame.grid(row=5, column=0, sticky="nsew")
        elements_frame.grid_propagate(True)  # 允许内容调整
        elements_frame.columnconfigure(0, weight=0)  # 标签列固定
        elements_frame.columnconfigure(1, weight=1)  # 输入列扩展
        elements_frame.columnconfigure(2, weight=0)  # 标签列固定
        elements_frame.columnconfigure(3, weight=1)  # 输入列扩展

        for i, elem in enumerate(elements):
            row = i // 2        # 每行显示2个元素
            col_in_row = i % 2  # 当前元素在行中的位置（0或1）
            
            # 计算实际列位置：每组元素占两列（标签+输入框）
            label_col = col_in_row * 2
            entry_col = label_col + 1

            element_label = self.widget_factory.create_label(elements_frame, text=f"{elem}:", **AppConfig.FunctionZone.FormulaGenerationPage.element_label)
            element_label.grid(row=row, column=label_col, **AppConfig.FunctionZone.FormulaGenerationPage.padding,)
            
            entry = self.widget_factory.create_entry(elements_frame, textvariable=self.element_vars[elem], **AppConfig.FunctionZone.FormulaGenerationPage.element_entry)
            entry.grid(row=row, column=entry_col, **AppConfig.FunctionZone.FormulaGenerationPage.padding)

    def _setup_right_frame(self):
        # 创建外层容器
        scrollable_container = self.widget_factory.create_scrolled_window(self.right_frame)
        scrollable_container.pack(fill=tk.BOTH, expand=True)

        # 创建水平滚动条
        hsb = ttk.Scrollbar(scrollable_container, orient=tk.HORIZONTAL)
        hsb.pack(side=tk.BOTTOM, fill=tk.X)

        # 使用Canvas实现水平滚动
        canvas = tk.Canvas(scrollable_container, xscrollcommand=hsb.set)
        canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        hsb.config(command=canvas.xview)

        # 内部容器用于放置筛选栏和表格
        inner_frame = ttk.Frame(canvas)
        canvas.create_window((0,0), window=inner_frame, anchor=tk.NW)

        # 更新Canvas滚动区域
        def on_configure(event):
            canvas.configure(scrollregion=canvas.bbox('all'))
        inner_frame.bind('<Configure>', on_configure)

        # 筛选栏设置
        filter_frame = ttk.Frame(inner_frame)
        filter_frame.pack(fill=tk.X, pady=AppConfig.Padding.Y)

        self.filters = {}
        columns = [
            "M/Z", "Adduct", "Mol Weight", "DBR",
            "C", "H", "N", "O", "S", "P",
            "Si", "F", "Cl", "Br", "I", "B", "Se",
        ]

        # 配置筛选栏列数
        filter_frame.columnconfigure(tuple(range(len(columns))), weight=1)

        # 创建筛选标题和输入框
        for col_idx, col_name in enumerate(columns):
            ttk.Label(filter_frame, text=col_name).grid(
                row=0, column=col_idx, 
                padx=AppConfig.Padding.X, 
                sticky="ew",
                ipadx=2
            )
            var = tk.StringVar()
            entry = ttk.Entry(filter_frame, textvariable=var, width=5)
            entry.grid(
                row=1, column=col_idx, 
                padx=AppConfig.Padding.X, 
                sticky="ew",
                ipadx=2
            )
            self.filters[col_name] = var

        # 表格容器框架
        table_container = ttk.Frame(inner_frame)
        table_container.pack(fill=tk.BOTH, expand=True, pady=AppConfig.Padding.Y)

        # 垂直滚动条
        vsb = ttk.Scrollbar(table_container, orient=tk.VERTICAL)

        # 创建Treeview并关联垂直滚动
        self.table = ttk.Treeview(
            table_container,
            columns=columns,
            show="headings",
            selectmode="browse",
            yscrollcommand=vsb.set,
        )
        vsb.config(command=self.table.yview)
        vsb.pack(side=tk.RIGHT, fill=tk.Y)

        self.table.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # 设置表格列属性
        for col in columns:
            self.table.heading(col, text=col)
            self.table.column(col, 
                width=0, 
                minwidth=50, 
                anchor=tk.CENTER, 
                stretch=True
            )

        # 绑定筛选事件
        for var in self.filters.values():
            var.trace_add("write", self._apply_filters)

        # 自动调整列宽
        self.after(100, self.auto_resize_columns)

    def auto_resize_columns(self):
        for col in self.table["columns"]:
            col_title_width = tkFont.Font().measure(col)  # 列标题宽度
            if self.data:
                data_widths = [tkFont.Font().measure(str(item[col])) for item in self.data]
                max_width = max(col_title_width, *data_widths)
            else:
                max_width = col_title_width  # 如果数据为空，只使用列标题宽度
            self.table.column(col, width=max_width + 20)  # 预留边距

    def _open_json_file(self):
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
                self._apply_filters()
                
            except json.JSONDecodeError as je:
                logging.error(f"JSON解析失败: {str(je)}")
            except (KeyError, ValueError, TypeError) as e:
                logging.error(f"文件内容异常: {str(e)}")
            except Exception as e:
                logging.error(f"文件读取失败: {str(e)}")

    def _setup_buttons(self):
        btn_frame = self.widget_factory.create_frame(self.left_frame)
        # btn_frame = ttk.Frame(self.left_frame)
        btn_frame.grid(row=6, column=0, sticky="ew")
        
        btn_frame.grid_columnconfigure(0, weight=1)  # 设置列权重为1，使按钮居中
        
        btn_run = self.widget_factory.create_button(
            btn_frame, 
            text="开始分析", 
            command=self._run_analysis
        )
        btn_run.grid(row=0, column=0, sticky=tk.EW)
        
        btn_open = self.widget_factory.create_button(
            btn_frame, 
            text="导入文件", 
            command=self._open_json_file
        )
        btn_open.grid(row=1, column=0, sticky=tk.EW)

    def _run_analysis(self):
        params = {
            "ms_mode": self.ms_mode.get(),
            "adduct_model": [k for k, v in self.adduct_vars.items() if v.get()],
            "m2z": self.m2z.get(),
            "error_pct": self.error_pct.get(),
            "charge": self.charge.get(),
            "elements": {k: v.get() for k, v in self.element_vars.items()}
        }

        validator = DataValidator()
        if not validator.validate(params):
            logging.error("参数输入有误，请检查")
            return
        
        elements = params["elements"]
        for k, v in elements.items():
            params['elements'][k] = int(v)

        logging.debug(f"参数: {params}")

        self.thread_pool.submit(self._run_analysis_background, params)

    def _run_analysis_background(self, params):
        try:
            result = start_analysis(params)
            self.data = self._map_data(result["results"])
            self.after(0, self._apply_filters)
        except Exception as e:
            logging.error(f"分析失败: {e}")
            self.after(0, lambda e=e: logging.error(f"分析失败: {e}"))

    def _map_data(self, raw_data):
        mapped = []
        for item in raw_data:
            row = {
                "M/Z": item["calculated_properties"].get("predicted_mz", ""),
                "Adduct": item["adduct_type"],
                "Mol Weight": item["calculated_properties"].get("molecular_weight", ""),
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

    def _apply_filters(self, *args):
        self.table.delete(*self.table.get_children())
        for item in self.data:
            valid = True
            for col in self.filters:
                filter_val = self.filters[col].get().strip()
                if filter_val:
                    cell_val = item.get(col, "")
                    if str(cell_val) != filter_val:
                        valid = False
                        break
            if valid:
                self.table.insert("", "end", values=list(item.values()))

    def on_window_resize(self, event):
        # 动态调整元素配置区高度
        elements_frame = self.left_frame.winfo_children()[5]
        elements_frame.config(height=int(event.height * 0.3))  # 占总高度30%
        
        # 触发表格列宽重计算
        self.after(100, self.auto_resize_columns)