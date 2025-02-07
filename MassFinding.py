import tkinter as tk
from tkinter import scrolledtext
import core_functions  # 导入核心功能模块

if __name__ == '__main__':
    # ---------------------------- GUI布局 ----------------------------
    root = tk.Tk()
    root.title("质谱数据分析工具 v2.0 designed by zc")

    # 输入区域
    input_frame = tk.Frame(root, padx=10, pady=10)
    input_frame.pack()

    # 质谱模式单选框
    ms_mode_var = tk.StringVar(value="ESI+")  # 默认值
    tk.Label(input_frame, text="质谱模式：").grid(row=0, column=0, sticky='w')
    modes = ["ESI+", "ESI-", "EI+", "EI-"]
    for i, mode in enumerate(modes):
        tk.Radiobutton(input_frame, text=mode, variable=ms_mode_var, value=mode).grid(row=0, column=i + 1)

    # 其他输入框
    labels = [
        ("质荷比 (m/z)：", 1),
        ("误差范围 (%)：", 2),
        ("电荷数：", 3),
    ]

    entries = {}
    for text, row in labels:
        tk.Label(input_frame, text=text).grid(row=row, column=0, sticky='w')
        entry = tk.Entry(input_frame, width=30)
        entry.grid(row=row, column=1, columnspan=4)
        entries[f"entry_{row}"] = entry

    # 元素范围复选框
    tk.Label(input_frame, text="元素范围：").grid(row=4, column=0, sticky='w')

    # 分组显示复选框
    element_vars = {
        "all": tk.BooleanVar(value=False),
        "C": tk.BooleanVar(value=False), "H": tk.BooleanVar(value=False), "O": tk.BooleanVar(value=False),
        "N": tk.BooleanVar(value=False), "S": tk.BooleanVar(value=False), "P": tk.BooleanVar(value=False),
        "F": tk.BooleanVar(value=False), "Cl": tk.BooleanVar(value=False), "Br": tk.BooleanVar(value=False),
        "I": tk.BooleanVar(value=False), "Si": tk.BooleanVar(value=False), "B": tk.BooleanVar(value=False),
        "Se": tk.BooleanVar(value=False)
    }

    # 第一组：'all'
    tk.Checkbutton(input_frame, text="all", variable=element_vars["all"]).grid(row=5, column=1)

    # 第二组：'C', 'H', 'O', 'N', 'S', 'P'
    for i, elem in enumerate(["C", "H", "O", "N", "S", "P"]):
        tk.Checkbutton(input_frame, text=elem, variable=element_vars[elem]).grid(row=6, column=i + 1)

    # 第三组：'F', 'Cl', 'Br', 'I'
    for i, elem in enumerate(["F", "Cl", "Br", "I"]):
        tk.Checkbutton(input_frame, text=elem, variable=element_vars[elem]).grid(row=7, column=i + 1)

    # 第四组：'Si', 'B', 'Se'
    for i, elem in enumerate(["Si", "B", "Se"]):
        tk.Checkbutton(input_frame, text=elem, variable=element_vars[elem]).grid(row=8, column=i + 1)

    # 操作按钮
    btn_frame = tk.Frame(root, pady=5)
    btn_frame.pack()

    def start_analysis():
        # 获取质谱模式
        ms_mode = ms_mode_var.get()

        # 获取元素范围
        elements = []
        if element_vars["all"].get():
            elements = ["all"]
        else:
            for elem, var in element_vars.items():
                if var.get():
                    elements.append(elem)
        elements_str = ",".join(elements)

        # 获取其他输入
        m2z = entries["entry_1"].get()
        error_pct = entries["entry_2"].get()
        charge = entries["entry_3"].get()

        # 将所有输入封装为字典
        input_data = {
            "ms_mode": ms_mode,
            "m2z": m2z,
            "error_pct": error_pct,
            "charge": charge,
            "elements": elements_str
        }

        # 调用核心功能模块进行分析
        core_functions.start_analysis(input_data, output_text)

    tk.Button(btn_frame, text="开始分析", command=start_analysis).pack(side=tk.LEFT, padx=5)

    # 输出区域
    output_text = scrolledtext.ScrolledText(root, width=70, height=15, wrap=tk.WORD)
    output_text.pack(padx=10, pady=(0, 10))

    root.mainloop()