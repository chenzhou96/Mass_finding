import tkinter as tk
from tkinter import ttk, messagebox
import json
import logging
import os
import csv
from datetime import datetime
from pathlib import Path

from .base_page import BasePage
from ...utils.widget_factory import WidgetFactory
from ...config.AppUI_config import AppUIConfig
from ...config.event_config import EventType, EventPriority
from ...config.base_config import BaseConfig
from ...config.path_config import PathManager
from ...service.formula_search_service import rerank_cached_compounds


class ScoreStatisticsPage(BasePage):
    def __init__(self, parent, event_mgr):
        super().__init__(parent, event_mgr, title="Score Statistics")
        self.event_mgr.publish(EventType.STATUS_UPDATE, data={"status_text": "loading..."})
        self._page_init()
        self._setup_left_panel()
        self._setup_right_panel()
        self._subscribe_events()
        self.event_mgr.publish(EventType.STATUS_UPDATE, data={"status_text": "done"})

    def _page_init(self):
        self.widget_factory = WidgetFactory()
        self.path_manager = PathManager()

        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=5)
        self.grid_rowconfigure(0, weight=1)

        self.formula_list = []          # 接收到的分子式列表
        self.statistics_data = {}       # {formula: {total, above, pct, top_score, compounds}}
        self.current_threshold = 80.0
        self._structure_photo = None
        self._structure_image_path = None
        self._rdkit_checked = False
        self._rdkit_ready = False
        self._current_compounds = []    # 当前选中分子式的高于阈值化合物列表

    # ---------- left panel ----------

    def _setup_left_panel(self):
        self.left_frame = self.widget_factory.create_frame(self)
        self.left_frame.grid(row=0, column=0, sticky="nsew")

        ctrl = self.widget_factory.create_labelframe(self.left_frame, text="控制区")
        ctrl.pack(fill=tk.X, padx=BaseConfig.PADDING_A, pady=(BaseConfig.PADDING_A, 0))

        row_frame = self.widget_factory.create_frame(ctrl)
        row_frame.pack(fill=tk.X, padx=BaseConfig.PADDING_A, pady=BaseConfig.PADDING_A)

        self.widget_factory.create_label(row_frame, text="评分阈值:").pack(side=tk.LEFT)
        self.threshold_var = tk.DoubleVar(value=80.0)
        self.threshold_spinbox = tk.Spinbox(
            row_frame, textvariable=self.threshold_var,
            from_=0, to=100, increment=1, width=5,
        )
        self.threshold_spinbox.pack(side=tk.LEFT, padx=(4, 8))

        self.stat_btn = self.widget_factory.create_rounded_button(
            row_frame, text="统计", command=self._run_statistics,
            width=6, height=28, hover_bg=BaseConfig.ACCENT_COLOR,
        )
        self.stat_btn.pack(side=tk.LEFT)

        # 分子式来源清单
        list_frame = self.widget_factory.create_labelframe(self.left_frame, text="待统计分子式")
        list_frame.pack(fill=tk.BOTH, expand=True, padx=BaseConfig.PADDING_A, pady=BaseConfig.PADDING_A)

        self.formula_listbox = tk.Listbox(list_frame, exportselection=False)
        self.formula_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(BaseConfig.PADDING_A, 0), pady=BaseConfig.PADDING_A)
        list_scroll = tk.Scrollbar(list_frame, command=self.formula_listbox.yview)
        list_scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, BaseConfig.PADDING_A), pady=BaseConfig.PADDING_A)
        self.formula_listbox.config(yscrollcommand=list_scroll.set)

        # 摘要
        self.summary_var = tk.StringVar(value="共 0 个分子式 / 0 个化合物 / 0 个高于阈值")
        self.summary_label = self.widget_factory.create_label(
            self.left_frame, "", textvariable=self.summary_var,
            anchor="w", fg=BaseConfig.PRIMARY_COLOR,
        )
        self.summary_label.pack(fill=tk.X, padx=BaseConfig.PADDING_A, pady=(0, BaseConfig.PADDING_A))

        # 统计表格
        table_frame = self.widget_factory.create_labelframe(self.left_frame, text="统计结果")
        table_frame.pack(fill=tk.BOTH, expand=True, padx=BaseConfig.PADDING_A, pady=(0, BaseConfig.PADDING_A))

        columns = ("formula", "total", "above", "pct", "top_score")
        self.tree = ttk.Treeview(table_frame, columns=columns, show="headings", selectmode="browse")
        self.tree.heading("formula", text="分子式")
        self.tree.heading("total", text="总数")
        self.tree.heading("above", text="高于阈值")
        self.tree.heading("pct", text="占比")
        self.tree.heading("top_score", text="最高分")
        self.tree.column("formula", width=100, anchor="center")
        self.tree.column("total", width=50, anchor="center")
        self.tree.column("above", width=60, anchor="center")
        self.tree.column("pct", width=55, anchor="center")
        self.tree.column("top_score", width=60, anchor="center")
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(BaseConfig.PADDING_A, 0), pady=BaseConfig.PADDING_A)
        tree_scroll = tk.Scrollbar(table_frame, command=self.tree.yview)
        tree_scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, BaseConfig.PADDING_A), pady=BaseConfig.PADDING_A)
        self.tree.config(yscrollcommand=tree_scroll.set)
        self.tree.bind("<<TreeviewSelect>>", self._on_table_row_select)

        # 导出按钮
        self.export_btn = self.widget_factory.create_rounded_button(
            self.left_frame, text="导出 CSV", command=self._export_csv,
            width=10, height=30, hover_bg=BaseConfig.ACCENT_COLOR,
        )
        self.export_btn.pack(pady=(0, BaseConfig.PADDING_A))

    # ---------- right panel ----------

    def _setup_right_panel(self):
        self.right_frame = self.widget_factory.create_frame(self)
        self.right_frame.grid(row=0, column=1, sticky="nsew")
        self.right_frame.grid_rowconfigure(0, weight=1)
        self.right_frame.grid_rowconfigure(1, weight=1)
        self.right_frame.grid_columnconfigure(0, weight=1)

        # 上部：化合物明细
        compound_frame = self.widget_factory.create_labelframe(self.right_frame, text="高于阈值的化合物")
        compound_frame.grid(row=0, column=0, sticky="nsew", padx=BaseConfig.PADDING_A, pady=(BaseConfig.PADDING_A, BaseConfig.PADDING_B))

        self.compound_listbox = tk.Listbox(compound_frame, exportselection=False)
        self.compound_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True, padx=(BaseConfig.PADDING_A, 0), pady=BaseConfig.PADDING_A)
        comp_scroll = tk.Scrollbar(compound_frame, command=self.compound_listbox.yview)
        comp_scroll.pack(side=tk.RIGHT, fill=tk.Y, padx=(0, BaseConfig.PADDING_A), pady=BaseConfig.PADDING_A)
        self.compound_listbox.config(yscrollcommand=comp_scroll.set)
        self.compound_listbox.bind("<<ListboxSelect>>", self._on_compound_select)

        # 下部：结构式预览
        preview_frame = self.widget_factory.create_labelframe(self.right_frame, text="结构式预览")
        preview_frame.grid(row=1, column=0, sticky="nsew", padx=BaseConfig.PADDING_A, pady=(BaseConfig.PADDING_B, BaseConfig.PADDING_A))
        preview_frame.grid_rowconfigure(0, weight=1)
        preview_frame.grid_columnconfigure(0, weight=1)

        self.structure_label = self.widget_factory.create_label(
            preview_frame,
            text="结构式预览区\n双击可用系统默认图片查看器打开\n\n请先在统计表中选中分子式",
            anchor="center", justify="center",
            bg="#ffffff", relief=tk.SOLID, bd=1, cursor="hand2",
        )
        self.structure_label.grid(row=0, column=0, sticky="nsew", padx=BaseConfig.PADDING_A, pady=BaseConfig.PADDING_A)
        self.structure_label.bind("<Double-1>", self._open_structure_image)

    # ---------- events ----------

    def _subscribe_events(self):
        self.event_mgr.subscribe(EventType.SCORE_STATISTICS, self._on_receive_formulas, priority=EventPriority.NORMAL)

    def _on_receive_formulas(self, event):
        formulas = event.data.get("formulas", []) if isinstance(event.data, dict) else []
        if not formulas:
            return
        added = 0
        existing = set(self.formula_list)
        for f in formulas:
            if f and f not in existing:
                self.formula_list.append(f)
                existing.add(f)
                added += 1
        if added:
            self._refresh_formula_listbox()
            self._run_statistics()

    # ---------- statistics ----------

    def _run_statistics(self):
        try:
            self.current_threshold = float(self.threshold_spinbox.get())
        except (ValueError, TypeError):
            self.current_threshold = 80.0
        self.statistics_data.clear()
        self._current_compounds.clear()
        self.compound_listbox.delete(0, tk.END)
        self._clear_structure()

        for formula in self.formula_list:
            compounds = self._load_compounds(formula)
            if compounds is None:
                continue
            total = len(compounds)
            above = [c for c in compounds if c.get("final_score", 0) >= self.current_threshold]
            above_count = len(above)
            pct = round(above_count / total * 100, 1) if total > 0 else 0.0
            top_score = max((c.get("final_score", 0) for c in compounds), default=0)
            self.statistics_data[formula] = {"total": total, "above": above_count, "pct": pct, "top_score": top_score, "compounds": above}

        self._refresh_tree()
        self._update_summary()

    def _load_compounds(self, formula):
        cache_file = self.path_manager.get_formula_search_cache_path() / f"formula_search_results_{formula}.json"
        if not cache_file.exists():
            logging.warning(f"分子式缓存不存在: {formula}")
            return None
        try:
            with open(cache_file, "r", encoding="utf-8") as f:
                payload = json.load(f)
            if isinstance(payload, dict):
                raw = payload.get("results", [])
                return rerank_cached_compounds(raw, ion_mode="both", strict_filter=True)
            return []
        except Exception as ex:
            logging.warning(f"读取缓存失败({formula}): {ex}")
            return None

    def _refresh_formula_listbox(self):
        self.formula_listbox.delete(0, tk.END)
        for f in self.formula_list:
            self.formula_listbox.insert(tk.END, f)

    def _refresh_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)
        for formula, stats in self.statistics_data.items():
            self.tree.insert("", tk.END, values=(
                formula, stats["total"], stats["above"],
                f"{stats['pct']}%", f"{stats['top_score']:.2f}",
            ))

    def _update_summary(self):
        total_formulas = len(self.formula_list)
        total_compounds = sum(d["total"] for d in self.statistics_data.values())
        total_above = sum(d["above"] for d in self.statistics_data.values())
        self.summary_var.set(f"共 {total_formulas} 个分子式 / {total_compounds} 个化合物 / {total_above} 个高于阈值")

    # ---------- table row selection ----------

    def _on_table_row_select(self, _event=None):
        selection = self.tree.selection()
        if not selection:
            return
        values = self.tree.item(selection[0], "values")
        if not values:
            return
        formula = values[0]
        self._show_compounds_for_formula(formula)

    def _show_compounds_for_formula(self, formula):
        data = self.statistics_data.get(formula)
        if not data:
            return
        compounds = data.get("compounds", [])
        self._current_compounds = compounds
        self.compound_listbox.delete(0, tk.END)
        for i, c in enumerate(compounds):
            cid = c.get("cid", "?")
            name = (c.get("title") or c.get("iupac_name") or "N/A")
            score = c.get("final_score", 0)
            self.compound_listbox.insert(tk.END, f"CID:{cid} | {score:.2f} | {name}")

        if compounds:
            self.compound_listbox.selection_set(0)
            self._render_compound_structure(compounds[0])

    def _on_compound_select(self, _event=None):
        selected = self.compound_listbox.curselection()
        if not selected or not self._current_compounds:
            return
        idx = selected[0]
        if 0 <= idx < len(self._current_compounds):
            self._render_compound_structure(self._current_compounds[idx])

    # ---------- structure image ----------

    def _ensure_rdkit_available(self):
        if self._rdkit_checked:
            return self._rdkit_ready
        self._rdkit_checked = True
        try:
            from rdkit import Chem  # noqa: F401
            from rdkit.Chem import Draw  # noqa: F401
            self._rdkit_ready = True
        except Exception:
            self._rdkit_ready = False
            logging.warning("未检测到 rdkit，结构式预览不可用")
        return self._rdkit_ready

    def _render_compound_structure(self, compound):
        smiles = compound.get("canonical_smiles") or compound.get("isomeric_smiles")
        inchi = compound.get("inchi")
        self._render_structure_image(smiles, inchi)

    def _render_structure_image(self, smiles, inchi=None):
        self._structure_photo = None
        self._structure_image_path = None
        if not self._ensure_rdkit_available():
            token = smiles or inchi or "N/A"
            self.structure_label.config(
                text=f"结构标识: {token}\n(缺少 rdkit，无法绘制)",
                image="",
            )
            return
        try:
            from rdkit import Chem
            from rdkit.Chem import Draw
            from PIL import ImageTk

            mol = None
            if smiles:
                mol = Chem.MolFromSmiles(smiles)
            if mol is None and inchi:
                try:
                    mol = Chem.MolFromInchi(inchi)
                except Exception:
                    mol = None
            if mol is None:
                self.structure_label.config(text="SMILES/InChI 无法解析", image="")
                return
            image = Draw.MolToImage(mol, size=(360, 240))
            preview_dir = self.path_manager.get_structure_preview_cache_path()
            preview_name = f"structure_preview_stats_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            preview_path = preview_dir / preview_name
            image.save(preview_path)
            self._structure_image_path = preview_path
            self._structure_photo = ImageTk.PhotoImage(image)
            self.structure_label.config(image=self._structure_photo, text="")
        except Exception as ex:
            self.structure_label.config(text=f"结构式绘制失败: {ex}", image="")

    def _clear_structure(self):
        self._structure_photo = None
        self._structure_image_path = None
        self.structure_label.config(
            image="",
            text="结构式预览区\n双击可用系统默认图片查看器打开\n\n请先在统计表中选中分子式",
        )

    def _open_structure_image(self, _event=None):
        if not self._structure_image_path or not Path(self._structure_image_path).exists():
            messagebox.showwarning("打开失败", "当前没有可打开的结构式图片")
            return
        try:
            os.startfile(str(self._structure_image_path))
        except AttributeError:
            import subprocess
            import platform
            system = platform.system()
            if system == "Darwin":
                subprocess.Popen(["open", str(self._structure_image_path)])
            else:
                subprocess.Popen(["xdg-open", str(self._structure_image_path)])
        except Exception as ex:
            messagebox.showerror("打开失败", f"无法打开结构式图片: {ex}")

    # ---------- export ----------

    def _export_csv(self):
        if not self.statistics_data:
            messagebox.showwarning("导出失败", "暂无统计数据，请先执行统计")
            return
        desktop = self.path_manager.desktop_path
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        file_path = desktop / f"score_statistics_{timestamp}.csv"
        try:
            with open(file_path, "w", newline="", encoding="utf-8-sig") as f:
                writer = csv.writer(f)
                writer.writerow(["分子式", "化合物总数", "高于阈值", "占比(%)", "最高分"])
                for formula, stats in self.statistics_data.items():
                    writer.writerow([formula, stats["total"], stats["above"], stats["pct"], f"{stats['top_score']:.2f}"])
            logging.info(f"统计结果已导出: {file_path}")
            messagebox.showinfo("导出完成", f"已导出到桌面:\n{file_path.name}")
        except Exception as ex:
            logging.error(f"导出 CSV 失败: {ex}")
            messagebox.showerror("导出失败", str(ex))
