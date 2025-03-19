import tkinter as tk
from tkinter import ttk, filedialog
from .base_page import BasePage
from ...core.thread_pool import ThreadPool
from ...service.formulaGeneration import start_analysis
from ...utils.data_validator import DataValidator
from ...utils.widget_factory import WidgetFactory
from ...config.AppUI_config import AppUIConfig
from ...config.event_config import EventType, EventPriority
from ...config.path_config import PathManager
import logging
import json
import tkinter.font as tkFont
import re

class FormulaGenerationPage(BasePage):

    def __init__(self, parent, event_mgr):
        super().__init__(parent, event_mgr, title="Formula Generation")
        self.widget_factory = WidgetFactory()
        self.left_frame = self.widget_factory.create_frame(self, **AppUIConfig.FunctionZone.FormulaGenerationPage.input_frame)
        self.right_frame = self.widget_factory.create_frame(self, **AppUIConfig.FunctionZone.FormulaGenerationPage.output_frame)

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
        with open(PathManager().chem_element_config_path, "r", encoding="utf-8") as f:
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
        if hasattr(self, 'adduct_frame'):
            if self.adduct_frame:
                self.adduct_frame.destroy()
            self.adduct_frame = None
        
        # 创建新框架
        self.adduct_frame = self.widget_factory.create_labelframe(self.left_frame, text="加合物模型")
        self.adduct_frame.grid(row=1, column=0, sticky="ew")
        
        # 启动网格布局
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
        
        # m/z值输入框
        m2z_frame = create_input_frame(self.left_frame, "m/z值", 2)
        self.m2z = tk.DoubleVar(value=100)
        entry = self.widget_factory.create_entry(m2z_frame, textvariable=self.m2z, **AppUIConfig.FunctionZone.FormulaGenerationPage.input_entry)
        entry.pack(**AppUIConfig.FunctionZone.FormulaGenerationPage.padding)
        
        # 误差范围输入框
        error_frame = create_input_frame(self.left_frame, "误差范围 (%)", 3)
        self.error_pct = tk.DoubleVar(value=0.1)
        entry = self.widget_factory.create_entry(error_frame, textvariable=self.error_pct, **AppUIConfig.FunctionZone.FormulaGenerationPage.input_entry)
        entry.pack(**AppUIConfig.FunctionZone.FormulaGenerationPage.padding)
        
        # 电荷数输入框
        charge_frame = create_input_frame(self.left_frame, "电荷数", 4)
        self.charge = tk.IntVar(value=1)
        entry = self.widget_factory.create_entry(charge_frame, textvariable=self.charge, **AppUIConfig.FunctionZone.FormulaGenerationPage.input_entry)
        entry.pack(**AppUIConfig.FunctionZone.FormulaGenerationPage.padding)

        # 元素配置区优化
        elements = ["C", "N", "O", "S", "P", "Si", "F", "Cl", "Br", "I", "B", "Se"]
        self.element_vars = {
            e: tk.StringVar(value="-1" if e in {"C", "N", "O"} else "0") 
            for e in elements
        }

        self.elements_frame = create_input_frame(self.left_frame, "元素配置(不超过)", 5)
        self.elements_frame.grid_propagate(True)
        self.elements_frame.columnconfigure(0, weight=0)  # 标签列固定
        self.elements_frame.columnconfigure(1, weight=1)  # 输入列扩展
        self.elements_frame.columnconfigure(2, weight=0)  # 标签列固定
        self.elements_frame.columnconfigure(3, weight=1)  # 输入列扩展

        for i, elem in enumerate(elements):
            row, col_in_row = divmod(i, 2)
            
            # 计算实际列位置：每组元素占两列（标签+输入框）
            label_col = col_in_row * 2
            entry_col = label_col + 1

            element_label = self.widget_factory.create_label(self.elements_frame, text=f"{elem}:", **AppUIConfig.FunctionZone.FormulaGenerationPage.element_label)
            element_label.grid(row=row, column=label_col, **AppUIConfig.FunctionZone.FormulaGenerationPage.padding,)
            
            entry = self.widget_factory.create_entry(self.elements_frame, textvariable=self.element_vars[elem], **AppUIConfig.FunctionZone.FormulaGenerationPage.element_entry)
            entry.grid(row=row, column=entry_col, **AppUIConfig.FunctionZone.FormulaGenerationPage.padding)

    def _setup_right_frame(self):
        # 创建筛选栏容器
        filter_frame = self.widget_factory.create_labelframe(self.right_frame, text="筛选栏")
        filter_frame.pack(side=tk.TOP, fill=tk.X)

        # 创建表格容器
        table_frame = self.widget_factory.create_labelframe(self.right_frame, text="可能分子式")
        table_frame.pack(side=tk.BOTTOM, fill=tk.BOTH, expand=True)

        # 筛选栏设置
        first_row = ["M/Z", "DBR", "C", "H", "N", "O", "S", "P"]
        second_row = ["Adduct", "Si", "F", "Cl", "Br", "I", "B", "Se"]
        columns = first_row + second_row + ['Mol Weight']

        self.filters = {}
        for row_idx, row_columns in enumerate([first_row, second_row]):
            for col_idx, col_name in enumerate(row_columns):
                # 创建Labelframe容器
                labelframe = self.widget_factory.create_labelframe(
                    filter_frame, 
                    text=col_name,
                )
                labelframe.grid(row=row_idx, column=col_idx, sticky="w")
                
                var = tk.StringVar()
                if col_name in ["M/Z", "Adduct"]:
                    width = 12
                else:
                    width = 8
                entry = self.widget_factory.create_entry(
                    labelframe, 
                    textvariable=var, 
                    width=width,
                )
                entry.pack(fill=tk.X, **AppUIConfig.FunctionZone.FormulaGenerationPage.padding)
                
                self.filters[col_name] = var

        # 确保列权重均匀分布
        max_cols = max(len(first_row), len(second_row))
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

        # 绑定筛选事件
        for var in self.filters.values():
            var.trace_add("write", self._apply_filters)

        self.table.bind("<Double-1>", self._on_table_double_click)

    def _update_hidden_columns(self):
        visible_cols = ["M/Z", "Adduct", "Mol Weight", "DBR"]
        for col in self.table["columns"]:
            if col in visible_cols:
                continue
            all_zero = True
            for item in self.data:
                value = item.get(col, "")
                if value not in ("0", "0.0", ""):
                    try:
                        if float(value) != 0:
                            all_zero = False
                            break
                    except (ValueError, TypeError):
                        all_zero = False
                        break
            if not all_zero:
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
                logging.info(f"- 电荷数: {data['input_params']['charge']}")
                logging.info(f"- 元素配置: {element_config_str}")
                
            except json.JSONDecodeError as je:
                logging.error(f"JSON解析失败: {str(je)}")
            except (KeyError, ValueError, TypeError) as e:
                logging.error(f"文件内容异常: {str(e)}")
            except Exception as e:
                logging.error(f"文件读取失败: {str(e)}")

    def _setup_buttons(self):
        btn_frame = self.widget_factory.create_frame(self.left_frame)
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

        btn_refresh = self.widget_factory.create_button(
            btn_frame, 
            text="刷新页面", 
            command=self._refresh_page
        )
        btn_refresh.grid(row=2, column=0, sticky=tk.EW)

    def _refresh_page(self):
        # 1. 重置输入参数
        self.ms_mode.set("ESI+")
        self.m2z.set(100)
        self.error_pct.set(0.1)
        self.charge.set(1)
        
        # 2. 重置元素配置
        for elem in self.element_vars:
            self.element_vars[elem].set("-1" if elem in {"C", "N", "O"} else "0")
        
        # 3. 重置加合物选项
        self.adduct_vars = {}
        self._on_ms_mode_change()  # 触发模式变化以重建加合物选项
        
        # 4. 清空表格数据
        self.data = []
        self.table.delete(*self.table.get_children())
        
        # 5. 清除筛选条件
        for var in self.filters.values():
            var.set("")
        
        # 6. 重置隐藏列
        self._update_hidden_columns()

        logging.debug("页面已刷新")

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
            self.after(0, self.auto_resize_columns)
            self.after(0, self._update_hidden_columns)
        except Exception as e:
            logging.error(f"分析失败: {e}")
            self.after(0, lambda e=e: logging.error(f"分析失败: {e}"))

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
            for col in self.filters:
                filter_val = self.filters[col].get().strip()
                if not filter_val:  # 无输入时跳过
                    continue
                    
                if col == "Adduct":  # 保留原有模糊匹配逻辑
                    cell_val = item.get(col, "")
                    if filter_val.lower() not in cell_val.lower():
                        valid = False
                        break
                else:
                    # 解析数值条件
                    parts = re.findall(r'\d+\.?\d*', filter_val)  # 提取所有数字
                    if not parts:
                        continue  # 无效输入时跳过
                    
                    numbers = [float(p) for p in parts[:2]]  # 只取前两个数值
                    if not numbers:
                        continue
                    
                    # 获取数据单元格数值
                    cell_val_str = item.get(col, "")
                    try:
                        cell_num = float(cell_val_str)
                    except (ValueError, TypeError):
                        valid = False  # 数据非数值类型视为不匹配
                        break

                    if len(numbers) == 1:
                        # 单值匹配
                        target = numbers[0]
                        if cell_num != target:
                            valid = False
                            break
                    else:
                        # 范围匹配（自动排序）
                        lower = min(numbers[0], numbers[1])
                        upper = max(numbers[0], numbers[1])
                        if not (lower <= cell_num <= upper):
                            valid = False
                            break

            if valid:
                # 按列顺序插入数据
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

        # 提取元素生成化学式
        elements_order = ['C', 'H', 'N', 'O', 'S', 'P', 'Si', 'F', 'Cl', 'Br', 'I', 'B', 'Se']
        formula = []
        for elem in elements_order:
            count = data.get(elem, '0')
            if count != 0:
                if count == 1:
                    formula.append(f'{elem}')
                else:
                    formula.append(f"{elem}{count}")
        formula_str = ''.join(formula)

        # 发送事件
        self.event_mgr.publish(EventType.ADD_FORMULA, data=formula_str, priority=EventPriority.NORMAL)
        logging.info(f"添加 {formula_str} 为感兴趣的分子式")