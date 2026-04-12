import tkinter as tk
from tkinter import ttk, messagebox
import json
import logging
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
        self.event_mgr.subscribe(EventType.ADD_FORMULA, self._on_add_formula, priority=EventPriority.NORMAL)

        self.event_mgr.publish(
            EventType.STATUS_UPDATE, 
            data={"status_text": "done"}
        )

    def _page_init(self):
        self.widget_factory = WidgetFactory()
        self.path_manager = PathManager()
        self.thread_pool = ThreadPool()

        self.initialization_cache_path = self.path_manager.get_initialization_cache_path()
        self.existing_formula_file_path = self.path_manager.create_cache_file(self.initialization_cache_path, self.path_manager.existing_formula_filename)
        self.failed_formula_file_path = self.path_manager.create_cache_file(self.initialization_cache_path, self.path_manager.failed_formula_filename)

        self.existing_formula_list = self._read_formula_list(self.existing_formula_file_path)
        self.failed_formula_list = self._read_formula_list(self.failed_formula_file_path)
        self.waiting_formula_list = []
        self.success_formula_list = []
        self.text_areas = {}

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

        self.search_button = self.widget_factory.create_button(
            btn_frame,
            text="搜索选中分子式",
            command=self._run_search
        )
        self.search_button.grid(row=0, column=0, sticky="ew")

    def _setup_right_frame(self, labelname='分子可能结构式'):
        self.info_label = self.widget_factory.create_label(self.right_frame, text=labelname, **AppUIConfig.FunctionZone.FormulaSearchPage.right_label)
        self.info_label.pack(side=tk.TOP, fill=tk.X)

        result_frame = self.widget_factory.create_labelframe(self.right_frame, text="PubChem 检索结果")
        result_frame.pack(side=tk.TOP, fill=tk.BOTH, expand=True, padx=BaseConfig.PADDING_A, pady=BaseConfig.PADDING_A)

        result_widget = self.widget_factory.create_scrollable_text(result_frame, **AppUIConfig.FunctionZone.FormulaSearchPage.text)
        result_widget["scrollbar"].pack(side=tk.RIGHT, fill=tk.Y)
        result_widget["text"].pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.result_text = result_widget["text"]
        self.result_text.config(state=tk.DISABLED)

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

        menu = self.widget_factory.create_menu(widget, tearoff=0)
        menu.add_command(label="发送到待搜索分子式", command=lambda s=state: self._send_selected_to_search_from_area(s))
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

    def _run_search(self):
        self.event_mgr.publish(
            EventType.STATUS_UPDATE, 
            data={"status_text": "running..."}
        )

        formula_list = self.waiting_formula_list
        if not formula_list:
            logging.warning("当前没有待搜索的分子式")
            self.event_mgr.publish(EventType.STATUS_UPDATE, data={"status_text": "done"})
            return
        
        params = {
            "formula_list": formula_list,
            "web_name": "PubChem"
        }

        self.thread_pool.submit(self._run_search_background, params)

    def _run_search_background(self, params):
        try:
            results = start_search(params["formula_list"], params["web_name"])
            total = params["formula_list"]

            self.waiting_formula_list = []
            self.success_formula_list = list(results.get("success", {}).keys())

            unique_success = [formula for formula in self.success_formula_list if formula not in self.existing_formula_list]
            self.existing_formula_list.extend(unique_success)
            for formula in results.get("failed", []):
                if formula not in self.failed_formula_list:
                    self.failed_formula_list.append(formula)

            self._write_formula_list(self.existing_formula_file_path, self.existing_formula_list)
            self._write_formula_list(self.failed_formula_file_path, self.failed_formula_list)

            self.after(0, self._update_formula_display, self.waiting_formula_frame, self.waiting_formula_list)
            self.after(0, self._update_formula_display, self.success_formula_frame, self.success_formula_list)
            self.after(0, self._update_formula_display, self.existing_formula_frame, self.existing_formula_list)
            self.after(0, self._update_formula_display, self.failed_formula_frame, self.failed_formula_list)
            self.after(0, self._display_search_results, results)
        except Exception as e:
            logging.error(f"搜索失败: {e}")
            self.after(0, lambda: self.result_text.config(state=tk.NORMAL))
            self.after(0, lambda: self.result_text.insert(tk.END, f"搜索失败: {e}\n"))
            self.after(0, lambda: self.result_text.config(state=tk.DISABLED))
        finally:
            self.after(0, self.event_mgr.publish, EventType.STATUS_UPDATE, {"status_text": "done"})

    def _display_search_results(self, results):
        self.result_text.config(state=tk.NORMAL)
        self.result_text.delete('1.0', tk.END)
        if not results:
            self.result_text.insert(tk.END, "未检索到结果。\n")
        for formula, data in results.items():
            self.result_text.insert(tk.END, f"化学式: {formula}\n")
            if isinstance(data, dict):
                result_items = data.get("results", [])
                self.result_text.insert(tk.END, f"  查询到 {len(result_items)} 条记录\n")
                for idx, item in enumerate(result_items, start=1):
                    iupac_name = item.get("iupac_name") or "N/A"
                    cid = item.get("cid") or "N/A"
                    smiles = item.get("canonical_smiles") or item.get("isomeric_smiles") or "N/A"
                    self.result_text.insert(tk.END, f"    {idx}. CID={cid}, Name={iupac_name}, SMILES={smiles}\n")
            else:
                self.result_text.insert(tk.END, f"  无效结果格式: {type(data)}\n")
            self.result_text.insert(tk.END, "\n")
        self.result_text.config(state=tk.DISABLED)