import tkinter as tk
from tkinter import ttk, messagebox
import json
import logging
import os
from pathlib import Path
from .base_page import BasePage
from ...utils.widget_factory import WidgetFactory
from ...config.AppUI_config import AppUIConfig
from ...config.event_config import EventType, EventPriority
from ...config.base_config import BaseConfig
from ...config.path_config import PathManager
from ...core.thread_pool import ThreadPool
from ...service.formulaSearch import start_search


class FormulaSearchPage(BasePage):
    def __init__(self, parent, event_mgr):
        super().__init__(parent, event_mgr, title="Formula Search")
        self.event_mgr.publish(
            EventType.STATUS_UPDATE, 
            data={"status_text": "loading..."}
        )
        self._page_init()
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
        self._load_cached_formulas()
        self._update_formula_display(self.existing_formula_frame, self.existing_formula_list)
        self._update_formula_display(self.failed_formula_frame, self.failed_formula_list)
        self._setup_right_frame()
        self.event_mgr.subscribe(EventType.ADD_WAITING_FORMULA, self._on_add_formula, priority=EventPriority.NORMAL)

        self.event_mgr.publish(
            EventType.STATUS_UPDATE, 
            data={"status_text": "done"}
        )

    def _page_init(self):
        self.widget_factory = WidgetFactory()
        self.path_manager = PathManager()
        self.thread_pool = ThreadPool()
        self._structure_photo = None
        self._structure_image_path = None
        self._rdkit_checked = False
        self._rdkit_ready = False

        self.initialization_cache_path = self.path_manager.get_initialization_cache_path()
        self.existing_formula_file_path = self.path_manager.create_cache_file(self.initialization_cache_path, self.path_manager.existing_formula_filename)
        self.failed_formula_file_path = self.path_manager.create_cache_file(self.initialization_cache_path, self.path_manager.failed_formula_filename)

        self.existing_formula_list = self._read_formula_list(self.existing_formula_file_path)
        self.failed_formula_list = self._read_formula_list(self.failed_formula_file_path)
        self.waiting_formula_list = []
        self.success_formula_list = []
        self.text_areas = {}

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
            logging.warning("未检测到 rdkit，右侧将只显示文本信息，不显示结构式图片。")
        return self._rdkit_ready

    def _read_formula_list(self, path):
        try:
            with open(path, 'r', encoding='utf-8') as file:
                content = file.read().strip()
                if not content:
                    return []
                formula_list = json.loads(content)
                return formula_list
        except FileNotFoundError:
            logging.warning(f"文件 {path} 不存在")
            return []
        except json.JSONDecodeError:
            logging.warning(f"文件 {path} 内容为空或格式不正确，已重置为 []")
            return []
        
    def _write_formula_list(self, path, formula_list):
        try:
            with open(path, 'w', encoding='utf-8') as file:
                json.dump(formula_list, file)
        except Exception as e:
            logging.error(f"保存文件 {path} 失败: {e}")
            return False
        return True

    def _setup_left_frame(self):
        def setup_labelframe(frame, title, **kwargs):
            labelframe = self.widget_factory.create_labelframe(frame, text=title, **AppUIConfig.FunctionZone.FormulaSearchPage.labelframe, **kwargs)
            labelframe.pack_propagate(0)
            text_widget = self.widget_factory.create_scrollable_text(labelframe, **AppUIConfig.FunctionZone.FormulaSearchPage.text)
            text_widget["scrollbar"].pack(side=tk.RIGHT, fill=tk.Y)
            text_widget["text"].pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
            widget = text_widget['text']
            self._initialize_selectable_text_area(widget, title)
            return {
                'frame': labelframe,
                'text': widget,
                'title': title
            }

        self.left_frame.grid_columnconfigure(0, weight=1)
        self.left_frame.grid_columnconfigure(1, weight=1)
        self.left_frame.grid_rowconfigure(0, weight=1)
        self.left_frame.grid_rowconfigure(1, weight=1)

        self.existing_formula_frame = setup_labelframe(self.left_frame, "本地已有分子式")
        self.waiting_formula_frame = setup_labelframe(self.left_frame, "待搜索分子式")
        self.failed_formula_frame = setup_labelframe(self.left_frame, "搜索失败分子式", fg=BaseConfig.ERROR_COLOR)
        self.success_formula_frame = setup_labelframe(self.left_frame, "搜索成功分子式", fg=BaseConfig.SUCCESS_COLOR)

        self.existing_formula_frame['frame'].grid(row=0, column=0, sticky="nsew")
        self.waiting_formula_frame['frame'].grid(row=1, column=0, sticky="nsew")
        self.success_formula_frame['frame'].grid(row=0, column=1, sticky="nsew")
        self.failed_formula_frame['frame'].grid(row=1, column=1, sticky="nsew")

        btn_frame = self.widget_factory.create_frame(self.left_frame)
        btn_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=BaseConfig.PADDING_A)
        btn_frame.grid_columnconfigure(0, weight=1)

        self.search_button = self.widget_factory.create_rounded_button(
            btn_frame,
            text="开始搜索",
            command=self._run_search,
            width="120",
            height="34",
            hover_bg=BaseConfig.ACCENT_COLOR,
        )
        self.search_button.grid(row=0, column=0, sticky="ew")

    def _setup_right_frame(self, labelname='分子式信息'):
        self.info_label = self.widget_factory.create_label(self.right_frame, text=labelname, **AppUIConfig.FunctionZone.FormulaSearchPage.right_label)
        self.info_label.pack(side=tk.TOP, fill=tk.X)

        result_frame = self.widget_factory.create_labelframe(self.right_frame, text="分子式详情")
        result_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=BaseConfig.PADDING_A, pady=BaseConfig.PADDING_A)
        result_frame.grid_columnconfigure(0, weight=2, minsize=320)
        result_frame.grid_columnconfigure(1, weight=3, minsize=420)
        result_frame.grid_rowconfigure(1, weight=2)
        result_frame.grid_rowconfigure(2, weight=3)

        self.formula_info_label = self.widget_factory.create_label(
            result_frame,
            text="请选择本地已有或搜索成功分子式查看详情",
            anchor='w',
            justify='left'
        )
        self.formula_info_label.grid(
            row=0,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=BaseConfig.PADDING_A,
            pady=(BaseConfig.PADDING_A, 0)
        )

        compound_list_frame = self.widget_factory.create_labelframe(result_frame, text="化合物列表")
        compound_list_frame.grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="nsew",
            padx=BaseConfig.PADDING_A,
            pady=BaseConfig.PADDING_A
        )

        self.compound_listbox = tk.Listbox(compound_list_frame, exportselection=False)
        self.compound_listbox.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        compound_scroll = tk.Scrollbar(compound_list_frame, command=self.compound_listbox.yview)
        compound_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self.compound_listbox.config(yscrollcommand=compound_scroll.set)
        self.compound_listbox.bind('<<ListboxSelect>>', self._on_compound_select)

        result_text_frame = self.widget_factory.create_labelframe(result_frame, text="化合物信息")
        result_text_frame.grid(
            row=2,
            column=0,
            sticky="nsew",
            padx=(BaseConfig.PADDING_A, BaseConfig.PADDING_B),
            pady=(0, BaseConfig.PADDING_A)
        )

        result_widget = self.widget_factory.create_scrollable_text(result_text_frame, **AppUIConfig.FunctionZone.FormulaSearchPage.text)
        result_widget["scrollbar"].pack(side=tk.RIGHT, fill=tk.Y)
        result_widget["text"].pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.result_text = result_widget["text"]
        self.result_text.config(state=tk.DISABLED)

        preview_frame = self.widget_factory.create_labelframe(result_frame, text="结构式预览")
        preview_frame.grid(
            row=2,
            column=1,
            sticky="nsew",
            padx=(BaseConfig.PADDING_B, BaseConfig.PADDING_A),
            pady=(0, BaseConfig.PADDING_A)
        )
        preview_frame.grid_rowconfigure(0, weight=1)
        preview_frame.grid_columnconfigure(0, weight=1)

        self.structure_image_label = self.widget_factory.create_label(
            preview_frame,
            text="结构式预览区\n双击可用系统默认图片查看器打开",
            anchor='center',
            justify='center',
            bg="#ffffff",
            relief=tk.SOLID,
            bd=1,
            cursor='hand2',
        )
        self.structure_image_label.grid(row=0, column=0, sticky="nsew", padx=BaseConfig.PADDING_A, pady=BaseConfig.PADDING_A)
        self.structure_image_label.bind('<Double-1>', self._open_structure_image)

        self.current_formula_results = []

    def _update_formula_display(self, formula_type, formula_list):
        """根据列表内容更新文本框显示"""
        text_widget = formula_type["text"]
        text_widget.config(state=tk.NORMAL)
        text_widget.delete('1.0', tk.END)  # 清空原有内容
        for formula in formula_list:
            text_widget.insert(tk.END, f"{formula}\n")
        current_area = self.text_areas.get(formula_type['title'])
        if current_area:
            current_area['selected_indices'].clear()
            current_area['anchor'] = None
            text_widget.tag_remove("selected_line", "1.0", tk.END)
        text_widget.config(state=tk.DISABLED)

    def _on_add_formula(self, event):
        formulas = event.data
        if isinstance(formulas, str):
            formulas = [formulas]

        added = False
        for formula in formulas:
            if formula and formula not in self.waiting_formula_list and formula not in self.success_formula_list:
                self.waiting_formula_list.append(formula)
                logging.info(f"已添加待搜索分子式: {formula}")
                added = True

        if added:
            self._update_formula_display(self.waiting_formula_frame, self.waiting_formula_list)

    def _load_cached_formulas(self):
        try:
            cache_path = self.path_manager.get_formula_search_cache_path()
            if not cache_path.exists():
                return

            for file_path in cache_path.glob('*.json'):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        if isinstance(data, dict):
                            metadata = data.get('metadata', {})
                            formula_str = metadata.get('molecular_formula')
                            if formula_str and formula_str not in self.existing_formula_list:
                                self.existing_formula_list.append(formula_str)
                            results = data.get('results', [])
                        else:
                            results = data

                        if not isinstance(results, list):
                            continue

                        for item in results:
                            if not isinstance(item, dict):
                                continue

                            formula_dict = item.get('formula')
                            if isinstance(formula_dict, dict):
                                formula_str = self._formula_dict_to_string(formula_dict)
                                if formula_str and formula_str not in self.existing_formula_list:
                                    self.existing_formula_list.append(formula_str)
                            elif item.get('molecular_formula'):
                                formula_str = item.get('molecular_formula')
                                if formula_str and formula_str not in self.existing_formula_list:
                                    self.existing_formula_list.append(formula_str)
                except Exception:
                    continue

            self._write_formula_list(self.existing_formula_file_path, self.existing_formula_list)
        except Exception as e:
            logging.warning(f"加载缓存化学式失败: {e}")

    def _formula_dict_to_string(self, formula_dict):
        order = ['C', 'H', 'N', 'O', 'S', 'P', 'Si', 'F', 'Cl', 'Br', 'I', 'B', 'Se']
        parts = []
        for atom in order:
            if atom in formula_dict:
                count = formula_dict[atom]
                if isinstance(count, (int, float)) and count != 0:
                    if count == 1:
                        parts.append(atom)
                    else:
                        parts.append(f"{atom}{int(count)}")
        return ''.join(parts)

    def _initialize_selectable_text_area(self, widget, area_name):
        widget.tag_configure("selected_line", background="#d0e7ff")
        state = {
            'widget': widget,
            'area_name': area_name,
            'selected_indices': set(),
            'anchor': None,
            'menu': None
        }
        self.text_areas[area_name] = state

        widget.bind("<Button-1>", lambda e, s=state: self._on_text_click(e, s))
        widget.bind("<Shift-Button-1>", lambda e, s=state: self._on_text_shift_click(e, s))
        widget.bind("<B1-Motion>", lambda e, s=state: self._on_text_drag(e, s))
        widget.bind("<ButtonRelease-1>", lambda e, s=state: self._on_text_release(e, s))
        widget.bind("<Button-3>", lambda e, s=state: self._show_text_area_popup(e, s))
        widget.bind("<Double-1>", lambda e, s=state: self._on_text_double_click(e, s))

        menu = self.widget_factory.create_menu(widget, tearoff=0)
        if area_name == '待搜索分子式':
            menu.add_command(label="搜索选中分子式", command=lambda s=state: self._search_selected_from_waiting(s))
        else:
            menu.add_command(label="发送到待搜索分子式", command=lambda s=state: self._send_selected_to_search_from_area(s))
        if area_name in ('本地已有分子式', '搜索成功分子式'):
            menu.add_command(label="查看分子式信息", command=lambda s=state: self._show_formula_info_from_area(s))
        menu.add_separator()
        menu.add_command(label="删除", command=lambda s=state: self._delete_selected_formulas(s))
        state['menu'] = menu

    def _show_text_area_popup(self, event, state):
        line = self._get_text_line_at_event(event, state)
        if line is not None and line not in state['selected_indices']:
            state['anchor'] = line
            self._select_text_range(state, line, line)
        try:
            state['menu'].tk_popup(event.x_root, event.y_root)
        finally:
            state['menu'].grab_release()

    def _get_text_line_at_event(self, event, state):
        try:
            index = state['widget'].index(f"@{event.x},{event.y}")
            line = int(index.split('.')[0]) - 1
            list_name = self._list_name_by_area(state['area_name'])
            if list_name is None:
                return None
            target_list = getattr(self, list_name, [])
            if 0 <= line < len(target_list):
                return line
        except Exception:
            pass
        return None

    def _on_text_click(self, event, state):
        line = self._get_text_line_at_event(event, state)
        if line is not None:
            state['anchor'] = line
            self._select_text_range(state, line, line)
        return "break"

    def _on_text_shift_click(self, event, state):
        line = self._get_text_line_at_event(event, state)
        if line is not None:
            if state['anchor'] is None:
                state['anchor'] = line
            self._select_text_range(state, state['anchor'], line)
        return "break"

    def _on_text_drag(self, event, state):
        if state['anchor'] is None:
            return "break"
        line = self._get_text_line_at_event(event, state)
        if line is not None:
            self._select_text_range(state, state['anchor'], line)
        return "break"

    def _on_text_release(self, event, state):
        if state['anchor'] is None:
            return "break"
        line = self._get_text_line_at_event(event, state)
        if line is not None:
            self._select_text_range(state, state['anchor'], line)
        return "break"

    def _on_text_double_click(self, event, state):
        line = self._get_text_line_at_event(event, state)
        if line is None:
            return "break"
        state['anchor'] = line
        self._select_text_range(state, line, line)
        if state['area_name'] in ('本地已有分子式', '搜索成功分子式'):
            self._show_formula_info_from_area(state)
        return "break"

    def _select_text_range(self, state, start_line, end_line):
        widget = state['widget']
        widget.tag_remove("selected_line", "1.0", tk.END)
        state['selected_indices'] = set(range(min(start_line, end_line), max(start_line, end_line) + 1))
        for line in sorted(state['selected_indices']):
            widget.tag_add("selected_line", f"{line + 1}.0", f"{line + 1}.end")

    def _delete_selected_formulas(self, state):
        indices = sorted(state['selected_indices'], reverse=True)
        if not indices:
            return
        target_list_name = self._list_name_by_area(state['area_name'])
        if not target_list_name:
            return
        target_list = getattr(self, target_list_name)
        selected_formulas = [target_list[idx] for idx in sorted(state['selected_indices']) if 0 <= idx < len(target_list)]
        if not selected_formulas:
            return

        answer = messagebox.askyesno(
            "确认删除",
            f"是否删除选中的分子式？\n\n{chr(10).join(selected_formulas)}"
        )
        if not answer:
            return

        for idx in indices:
            if 0 <= idx < len(target_list):
                target_list.pop(idx)
        target_frame = self._frame_name_by_area(state['area_name'])
        if target_frame:
            self._update_formula_display(getattr(self, target_frame), target_list)
            if target_frame == 'existing_formula_frame':
                self._write_formula_list(self.existing_formula_file_path, self.existing_formula_list)
            elif target_frame == 'failed_formula_frame':
                self._write_formula_list(self.failed_formula_file_path, self.failed_formula_list)
        state['selected_indices'].clear()
        state['anchor'] = None

    def _send_selected_to_search_from_area(self, state):
        indices = sorted(state['selected_indices'])
        if not indices:
            return
        list_name = self._list_name_by_area(state['area_name'])
        if not list_name:
            return
        area_list = getattr(self, list_name)
        for idx in indices:
            formula = area_list[idx]
            if formula not in self.waiting_formula_list:
                self.waiting_formula_list.append(formula)
        self._update_formula_display(self.waiting_formula_frame, self.waiting_formula_list)
        state['selected_indices'].clear()
        state['anchor'] = None

    def _search_selected_from_waiting(self, state):
        indices = sorted(state['selected_indices'])
        if not indices:
            messagebox.showwarning("搜索失败", "请先选中待搜索分子式")
            return
        selected_formulas = [self.waiting_formula_list[idx] for idx in indices if 0 <= idx < len(self.waiting_formula_list)]
        if not selected_formulas:
            return
        self._run_search(selected_formulas)

    def _show_formula_info_from_area(self, state):
        indices = sorted(state['selected_indices'])
        if not indices:
            return
        list_name = self._list_name_by_area(state['area_name'])
        if not list_name:
            return
        formulas = getattr(self, list_name, [])
        first_idx = indices[0]
        if not (0 <= first_idx < len(formulas)):
            return
        self._show_formula_info(formulas[first_idx])

    def _list_name_by_area(self, area_name):
        mapping = {
            '本地已有分子式': 'existing_formula_list',
            '待搜索分子式': 'waiting_formula_list',
            '搜索成功分子式': 'success_formula_list',
            '搜索失败分子式': 'failed_formula_list'
        }
        return mapping.get(area_name)

    def _frame_name_by_area(self, area_name):
        mapping = {
            '本地已有分子式': 'existing_formula_frame',
            '待搜索分子式': 'waiting_formula_frame',
            '搜索成功分子式': 'success_formula_frame',
            '搜索失败分子式': 'failed_formula_frame'
        }
        return mapping.get(area_name)

    def _run_search(self, target_formulas=None):
        self.event_mgr.publish(
            EventType.STATUS_UPDATE, 
            data={"status_text": "running..."}
        )

        formula_list = list(target_formulas) if target_formulas is not None else list(self.waiting_formula_list)
        if not formula_list:
            logging.warning("当前没有待搜索的分子式")
            self.event_mgr.publish(EventType.STATUS_UPDATE, data={"status_text": "done"})
            return
        
        params = {
            "formula_list": formula_list,
            "web_name": "PubChem"
        }

        self.thread_pool.submit(self._run_search_background, params)

    def _cache_file_for_formula(self, formula):
        return self.path_manager.get_formula_search_cache_path() / f"formula_search_results_{formula}.json"

    def _load_cached_result_for_formula(self, formula):
        cache_file = self._cache_file_for_formula(formula)
        if not cache_file.exists():
            return None
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as ex:
            logging.warning(f"读取本地缓存失败({formula}): {ex}")
            return None

    def _remove_from_waiting_list(self, formulas):
        if not formulas:
            return
        remove_set = set(formulas)
        self.waiting_formula_list = [f for f in self.waiting_formula_list if f not in remove_set]

    def _run_search_background(self, params):
        try:
            formula_list = list(params["formula_list"])
            local_hit_results = {}
            need_search_formulas = []

            for formula in formula_list:
                cached_data = self._load_cached_result_for_formula(formula)
                if cached_data is not None:
                    local_hit_results[formula] = cached_data
                    logging.info(f"分子式 {formula} 已有本地缓存，跳过网络检索并直接使用本地数据")
                else:
                    need_search_formulas.append(formula)

            search_results = {"success": {}, "failed": []}
            if need_search_formulas:
                search_results = start_search(need_search_formulas, params["web_name"])

            merged_success = {}
            merged_success.update(local_hit_results)
            merged_success.update(search_results.get("success", {}))
            failed_formulas = list(search_results.get("failed", []))

            for formula in merged_success.keys():
                if formula not in self.success_formula_list:
                    self.success_formula_list.append(formula)
                if formula not in self.existing_formula_list:
                    self.existing_formula_list.append(formula)

            for formula in failed_formulas:
                if formula not in self.failed_formula_list:
                    self.failed_formula_list.append(formula)

            self._remove_from_waiting_list(formula_list)

            self._write_formula_list(self.existing_formula_file_path, self.existing_formula_list)
            self._write_formula_list(self.failed_formula_file_path, self.failed_formula_list)

            self.after(0, self._update_formula_display, self.waiting_formula_frame, self.waiting_formula_list)
            self.after(0, self._update_formula_display, self.success_formula_frame, self.success_formula_list)
            self.after(0, self._update_formula_display, self.existing_formula_frame, self.existing_formula_list)
            self.after(0, self._update_formula_display, self.failed_formula_frame, self.failed_formula_list)
            self.after(0, self._display_search_results, merged_success)
            self._log_search_results(local_hit_results, search_results)
        except Exception as e:
            logging.error(f"搜索失败: {e}")
            self.after(0, lambda: self.result_text.config(state=tk.NORMAL))
            self.after(0, lambda: self.result_text.insert(tk.END, f"搜索失败: {e}\n"))
            self.after(0, lambda: self.result_text.config(state=tk.DISABLED))
        finally:
            self.after(0, self.event_mgr.publish, EventType.STATUS_UPDATE, {"status_text": "done"})

    def _log_search_results(self, local_hit_results, search_results):
        for formula, data in local_hit_results.items():
            result_items = data.get("results", []) if isinstance(data, dict) else []
            logging.info(f"[本地命中] {formula}，本地记录数: {len(result_items)}")

        for formula, data in search_results.get("success", {}).items():
            result_items = data.get("results", []) if isinstance(data, dict) else []
            logging.info(f"[PubChem检索成功] {formula}，记录数: {len(result_items)}")

        for formula in search_results.get("failed", []):
            logging.warning(f"[PubChem检索失败] {formula}")

    def _render_structure_image(self, smiles, inchi=None):
        self._structure_photo = None
        self._structure_image_path = None
        if not self._ensure_rdkit_available():
            token = smiles or inchi or "N/A"
            self.structure_image_label.config(text=f"结构标识: {token}\n(未安装 rdkit，无法绘制结构式)", image='')
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
                self.structure_image_label.config(text="SMILES/InChI 无法解析，无法绘制结构式", image='')
                return
            image = Draw.MolToImage(mol, size=(360, 240))
            preview_dir = self.path_manager.get_structure_preview_cache_path()
            preview_name = f"structure_preview_{getattr(self, 'current_display_formula', 'unknown')}_{len(self.current_formula_results)}.png"
            preview_path = preview_dir / preview_name
            image.save(preview_path)
            self._structure_image_path = preview_path
            self._structure_photo = ImageTk.PhotoImage(image)
            self.structure_image_label.config(image=self._structure_photo, text='')
        except Exception as ex:
            self.structure_image_label.config(text=f"结构式绘制失败: {ex}", image='')

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
            if system == 'Darwin':
                subprocess.Popen(['open', str(self._structure_image_path)])
            else:
                subprocess.Popen(['xdg-open', str(self._structure_image_path)])
        except Exception as ex:
            messagebox.showerror("打开失败", f"无法打开结构式图片: {ex}")

    def _on_compound_select(self, _event=None):
        selected = self.compound_listbox.curselection()
        if not selected:
            return
        idx = selected[0]
        if idx < 0 or idx >= len(self.current_formula_results):
            return

        item = self.current_formula_results[idx]
        cid = item.get("cid") or "N/A"
        iupac_name = item.get("iupac_name") or "N/A"
        smiles = item.get("canonical_smiles") or item.get("isomeric_smiles") or ""
        mw = item.get("molecular_weight") or "N/A"
        mono = item.get("monoisotopic_mass") or "N/A"
        inchi = item.get("inchi") or "N/A"
        inchikey = item.get("inchikey") or "N/A"

        lines = [
            f"CID: {cid}",
            f"IUPAC Name: {iupac_name}",
            f"Molecular Weight: {mw}",
            f"Monoisotopic Mass: {mono}",
            f"SMILES: {smiles if smiles else 'N/A'}",
            f"InChI: {inchi}",
            f"InChIKey: {inchikey}",
        ]

        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete('1.0', tk.END)
        self.result_text.insert(tk.END, "\n".join(lines))
        self.result_text.config(state=tk.DISABLED)
        self._render_structure_image(smiles, inchi)

    def _show_formula_info(self, formula):
        self.current_display_formula = formula
        data = self._load_cached_result_for_formula(formula)
        if not isinstance(data, dict):
            self.formula_info_label.config(text=f"分子式: {formula}（无本地详情数据）")
            self.compound_listbox.delete(0, tk.END)
            self.current_formula_results = []
            self.result_text.config(state=tk.NORMAL)
            self.result_text.delete('1.0', tk.END)
            self.result_text.insert(tk.END, "无可展示的分子式信息")
            self.result_text.config(state=tk.DISABLED)
            self._structure_image_path = None
            self.structure_image_label.config(text="结构式预览区\n双击可用系统默认图片查看器打开", image='')
            return

        metadata = data.get("metadata", {})
        results = data.get("results", [])
        self.current_formula_results = results if isinstance(results, list) else []
        self.formula_info_label.config(text=f"分子式: {formula} | 记录数: {len(self.current_formula_results)}")

        self.compound_listbox.delete(0, tk.END)
        for idx, item in enumerate(self.current_formula_results, start=1):
            cid = item.get("cid") or "N/A"
            name = item.get("iupac_name") or "N/A"
            self.compound_listbox.insert(tk.END, f"{idx}. CID={cid} | {name}")

        if self.current_formula_results:
            self.compound_listbox.selection_set(0)
            self._on_compound_select()
        else:
            self.result_text.config(state=tk.NORMAL)
            self.result_text.delete('1.0', tk.END)
            self.result_text.insert(tk.END, f"分子式: {formula}\n未找到化合物记录")
            self.result_text.config(state=tk.DISABLED)
            self._structure_image_path = None
            self.structure_image_label.config(text="结构式预览区\n双击可用系统默认图片查看器打开", image='')

    def _display_search_results(self, merged_success):
        if not merged_success:
            self.formula_info_label.config(text="当前搜索没有成功结果，可在左侧选择本地已有分子式查看详情")
            return

        first_formula = next(iter(merged_success.keys()))
        self._show_formula_info(first_formula)