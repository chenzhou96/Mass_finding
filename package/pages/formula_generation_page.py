import tkinter as tk
from tkinter import ttk
from .base_page import BasePage
from ..core.event import EventBus, Event
from ..core.thread_pool import ThreadPool
from ..back_end.formulaGeneration import start_analysis
from ..utils.data_validator import DataValidator
from ..config import AppConfig
import logging

class FormulaGenerationPage(BasePage):

    ADDUCT_CONFIG = {
        "ESI+": ["H+", "H3O+", "NH4+", "Na+", "K+"],
        "ESI-": ["H-", "Cl-", "HCOO-", "CH3COO-"],
        "EI+": ["e+"],
        "EI-": ["e-"]
    }
    MAX_ADDUCT_ROWS = 6  # 定义最大行数

    def __init__(self, parent, event_bus):
        super().__init__(parent, event_bus, title="Formula Generation")
        self.left_frame = tk.Frame(self, bg="white", padx=AppConfig.Padding.X, pady=AppConfig.Padding.Y)
        self.right_frame = tk.Frame(self, bg="white", padx=AppConfig.Padding.X, pady=AppConfig.Padding.Y)

        # 初始化加合物框架
        self.adduct_frame = None
        self.adduct_vars = {}  # 重置为字典存储当前选中的加合物

        # 使用网格布局，左侧占1份，右侧占3份
        self.grid_columnconfigure(0, weight=1)
        self.grid_columnconfigure(1, weight=3)
        self.grid_rowconfigure(0, weight=1)

        self.left_frame.grid(row=0, column=0, sticky="nsew")
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

    def _on_ms_mode_change(self, *args):
        current_mode = self.ms_mode.get()
        adducts = self.ADDUCT_CONFIG.get(current_mode, [])
        
        # 销毁旧框架
        if hasattr(self, 'adduct_frame') and self.adduct_frame:
            self.adduct_frame.destroy()
            self.adduct_frame = None
        
        # 创建新框架并固定高度
        self.adduct_frame = ttk.LabelFrame(self.left_frame, text="加合物模型")
        self.adduct_frame.configure(
            height=self.MAX_ADDUCT_ROWS * 25,  # 5行×25px=125px
            takefocus=False
        )
        self.adduct_frame.grid(row=1, column=0, sticky="ew", pady=AppConfig.Padding.Y)
        
        # 禁用自动调整
        self.adduct_frame.grid_propagate(False)
        
        # 预配置列和行
        self.adduct_frame.grid_columnconfigure(0, weight=1, minsize=150)  # 列配置
        for row in range(self.MAX_ADDUCT_ROWS):
            self.adduct_frame.grid_rowconfigure(row, minsize=25)  # 每行25px
        
        # 重置变量
        self.adduct_vars = {}
        
        # 添加选项
        for idx, adduct in enumerate(adducts):
            var = tk.BooleanVar()
            cb = ttk.Checkbutton(
                self.adduct_frame, 
                text=adduct, 
                variable=var,
                width=12  # 保持足够宽度
            )
            cb.grid(row=idx, column=0, sticky=tk.W + tk.E, padx=AppConfig.Padding.X, pady=0)  # 移除pady
            
            self.adduct_vars[adduct] = var
        
        # 隐藏多余行（使用同宽度占位符）
        for idx in range(len(adducts), self.MAX_ADDUCT_ROWS):
            placeholder = ttk.Label(
                self.adduct_frame, 
                text=" ", 
                width=12
            )
            placeholder.grid(row=idx, column=0, sticky="ew", pady=0)  # 移除pady

    def _setup_left_frame(self):
        # 初始化网格布局
        self.left_frame.columnconfigure(0, weight=1)
        
        # 质谱模式
        ms_mode_frame = ttk.LabelFrame(self.left_frame, text="质谱模式")
        ms_mode_frame.grid(row=0, column=0, sticky="ew", pady=AppConfig.Padding.Y)
        self.ms_mode = tk.StringVar(value="ESI+")
        self.ms_mode.trace_add("write", self._on_ms_mode_change)
        
        ttk.OptionMenu(
            ms_mode_frame, 
            self.ms_mode, 
            "ESI+", 
            *["ESI+", "ESI-", "EI+", "EI-"]
        ).pack(padx=AppConfig.Padding.X, pady=AppConfig.Padding.Y)

        # 预留加合物框架的位置（第二行）
        self.adduct_frame = None  # 初始化为空

        # 其他控件按行放置
        m2z_frame = ttk.LabelFrame(self.left_frame, text="m/z值")
        m2z_frame.grid(row=2, column=0, sticky="ew", pady=AppConfig.Padding.Y)
        self.m2z = tk.DoubleVar()
        ttk.Entry(m2z_frame, textvariable=self.m2z).pack(padx=AppConfig.Padding.X, pady=AppConfig.Padding.Y)

        # 误差范围
        error_frame = ttk.LabelFrame(self.left_frame, text="误差范围 (%)")
        error_frame.grid(row=3, column=0, sticky="ew", pady=AppConfig.Padding.Y)
        self.error_pct = tk.DoubleVar(value=0.1)
        ttk.Entry(error_frame, textvariable=self.error_pct).pack(padx=AppConfig.Padding.X, pady=AppConfig.Padding.Y)

        # 电荷数
        charge_frame = ttk.LabelFrame(self.left_frame, text="电荷数")
        charge_frame.grid(row=4, column=0, sticky="ew", pady=AppConfig.Padding.Y)
        self.charge = tk.IntVar(value=1)
        ttk.Entry(charge_frame, textvariable=self.charge).pack(padx=AppConfig.Padding.X, pady=AppConfig.Padding.Y)

        # 在元素配置部分修改为：
        elements = ["C", "N", "O", "S", "P", "Si", "F", "Cl", "Br", "I", "B", "Se"]  # 移除H
        self.element_vars = {
            e: tk.StringVar(value="-1" if e in {"C", "N", "O"} else "0") 
            for e in elements
        }

        # 使用两列布局
        elements_frame = ttk.LabelFrame(self.left_frame, text="元素配置(不超过)")
        elements_frame.grid(row=5, column=0, sticky="nsew", pady=AppConfig.Padding.Y)
        elements_frame.columnconfigure(0, weight=1)
        elements_frame.columnconfigure(1, weight=1)
        elements_frame.columnconfigure(2, weight=1)
        elements_frame.columnconfigure(3, weight=1)

        for i, elem in enumerate(elements):
            row = i // 2        # 计算行号（每两元素占一行）
            col = (i % 2) * 2   # 列号（0或2列）
            
            # 创建标签和输入框
            ttk.Label(elements_frame, text=f"{elem}:").grid(
                row=row, column=col, sticky=tk.W, padx=(AppConfig.Padding.X,0), pady=AppConfig.Padding.Y
            )
            entry = ttk.Entry(elements_frame, textvariable=self.element_vars[elem], width=3)
            entry.grid(row=row, column=col+1, sticky=tk.W, padx=(0,AppConfig.Padding.X), pady=AppConfig.Padding.Y)

        # 限制元素配置区高度
        elements_frame.configure(height=180)  # 根据实际行数调整高度
        elements_frame.grid_propagate(False)  # 禁止自动调整大小

        # 父容器的行配置
        self.left_frame.grid_rowconfigure(5, weight=0)  # 防止该行自动扩展

    def _setup_right_frame(self):
        # 筛选栏
        filter_frame = ttk.Frame(self.right_frame)
        filter_frame.pack(fill=tk.X, pady=AppConfig.Padding.Y)

        self.filters = {}
        columns = [
            "H", "C", "N", "O", "F", "Si", "P", "B", "S", 
            "Cl", "Br", "Se", "I", "Adduct", "DBR", "M/Z", "Mol Weight"
        ]
        for col in columns:
            var = tk.StringVar()
            ttk.Entry(filter_frame, textvariable=var, width=5).pack(side=tk.LEFT, padx=AppConfig.Padding.X)
            self.filters[col] = var

        # 表格
        self.table = ttk.Treeview(
            self.right_frame,
            columns=columns,
            show="headings",
            selectmode="browse"
        )
        for col in columns:
            self.table.heading(col, text=col)
            self.table.column(col, width=60, anchor=tk.CENTER)
        self.table.pack(fill=tk.BOTH, expand=True, pady=AppConfig.Padding.Y)

        # 绑定筛选事件
        for var in self.filters.values():
            var.trace_add("write", self._apply_filters)

    def _setup_buttons(self):
        btn_frame = ttk.Frame(self.left_frame)
        btn_frame.grid(row=6, column=0, sticky="ew", pady=AppConfig.Padding.Y)

        ttk.Button(
            btn_frame, 
            text="开始分析", 
            command=self._run_analysis
        ).pack(padx=AppConfig.Padding.X, pady=AppConfig.Padding.Y)

    def _run_analysis(self):
        # 收集参数
        params = {
            "ms_mode": self.ms_mode.get(),
            "adduct_model": [k for k, v in self.adduct_vars.items() if v.get()],
            "m2z": self.m2z.get(),
            "error_pct": self.error_pct.get(),
            "charge": self.charge.get(),
            "elements": {k: v.get() for k, v in self.element_vars.items()}
        }

        # 验证参数
        validator = DataValidator()
        if not validator.validate(params):
            logging.error("错误", "参数输入有误，请检查")
            return

        # 调用后端分析（多线程）
        self.thread_pool.submit(self._run_analysis_background, params)

    def _run_analysis_background(self, params):
        try:
            result = start_analysis(params)
            self.data = self._map_data(result["results"])
            self.after(0, self._apply_filters)
        except Exception as e:
            logging.error(f"分析失败: {e}")
            self.after(0, lambda: logging.error("错误", f"分析失败: {e}"))

    def _map_data(self, raw_data):
        mapped = []
        for item in raw_data:
            row = {
                "H": item["formula"].get("H", ""),
                "C": item["formula"].get("C", ""),
                "N": item["formula"].get("N", ""),
                "O": item["formula"].get("O", ""),
                "F": item["formula"].get("F", ""),
                "Si": item["formula"].get("Si", ""),
                "P": item["formula"].get("P", ""),
                "B": item["formula"].get("B", ""),
                "S": item["formula"].get("S", ""),
                "Cl": item["formula"].get("Cl", ""),
                "Br": item["formula"].get("Br", ""),
                "Se": item["formula"].get("Se", ""),
                "I": item["formula"].get("I", ""),
                "Adduct": item["adduct_type"],
                "DBR": item["calculated_properties"].get("dbr", ""),
                "M/Z": item["calculated_properties"].get("predicted_mz", ""),
                "Mol Weight": item["calculated_properties"].get("molecular_weight", "")
            }
            mapped.append(row)
        return mapped

    def _apply_filters(self, *args):
        # 清空表格
        self.table.delete(*self.table.get_children())

        # 过滤数据
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