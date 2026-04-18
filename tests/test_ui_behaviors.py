import json
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from package.gui.main_window import APP
from package.gui.pages.formula_generation_page import FormulaGenerationPage
from package.gui.pages.formula_search_page import FormulaSearchPage
from package.utils.widget_factory import WidgetFactory


class DummyVar:
    def __init__(self, value):
        self._value = value

    def get(self):
        return self._value


class DummyEventManager:
    def __init__(self):
        self.status_updates = []

    def publish(self, event_type, data=None, priority=None):
        if isinstance(data, dict) and "status_text" in data:
            self.status_updates.append(data["status_text"])


class DummyThreadPool:
    def __init__(self):
        self.calls = []

    def submit(self, func, *args, **kwargs):
        self.calls.append((func, args, kwargs))


class UiBehaviorTests(unittest.TestCase):
    def test_invalid_analysis_input_resets_status_to_done(self):
        dummy_page = SimpleNamespace(
            event_mgr=DummyEventManager(),
            ms_mode=DummyVar("ESI+"),
            adduct_vars={"[M+H]+": DummyVar(True)},
            m2z=DummyVar(100),
            error_pct=DummyVar(0.1),
            error_da=DummyVar(0.0),
            charge=DummyVar(1),
            element_vars={"C": DummyVar("bad")},
            thread_pool=DummyThreadPool(),
        )

        with patch("package.gui.pages.formula_generation_page.DataValidator.validate", return_value=False):
            FormulaGenerationPage._run_analysis(dummy_page)

        self.assertEqual(dummy_page.thread_pool.calls, [])
        self.assertEqual(dummy_page.event_mgr.status_updates[-1], "done")

    def test_close_request_prompts_when_status_is_running(self):
        app = APP.__new__(APP)
        app.current_status_text = "running..."
        destroyed = {"called": False}
        app.destroy = lambda: destroyed.__setitem__("called", True)

        with patch("package.gui.main_window.messagebox.askyesno", return_value=False) as ask_mock:
            APP._on_close_request(app)

        ask_mock.assert_called_once()
        self.assertFalse(destroyed["called"])

    def test_close_request_closes_immediately_when_not_running(self):
        app = APP.__new__(APP)
        app.current_status_text = "done"
        destroyed = {"called": False}
        app.destroy = lambda: destroyed.__setitem__("called", True)

        with patch("package.gui.main_window.messagebox.askyesno") as ask_mock:
            APP._on_close_request(app)

        ask_mock.assert_not_called()
        self.assertTrue(destroyed["called"])

    def test_rounded_button_numeric_height_uses_pixels(self):
        root = None
        try:
            import tkinter as tk
            root = tk.Tk()
            root.withdraw()
            factory = WidgetFactory()
            button = factory.create_rounded_button(root, text="测试", width=10, height=34)
            self.assertEqual(int(button.cget("height")), 34)
        finally:
            if root is not None:
                root.destroy()

    def test_delete_existing_formula_removes_search_cache_and_syncs_existing_file(self):
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            search_cache_dir = temp_root / "formula_search_cache"
            search_cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file = search_cache_dir / "formula_search_results_C6H13NO4.json"
            cache_file.write_text('{"results": []}', encoding="utf-8")

            existing_file = temp_root / "existing_formula.json"
            existing_file.write_text(json.dumps(["C6H13NO4"], ensure_ascii=False), encoding="utf-8")
            failed_file = temp_root / "failed_formula.json"
            failed_file.write_text("[]", encoding="utf-8")
            partial_file = temp_root / "partial_formula.json"
            partial_file.write_text("{}", encoding="utf-8")
            raw_file = temp_root / "raw_data_formula.json"
            raw_file.write_text("[]", encoding="utf-8")

            page = FormulaSearchPage.__new__(FormulaSearchPage)
            page.existing_formula_list = ["C6H13NO4"]
            page.success_formula_list = ["C6H13NO4"]
            page.waiting_formula_list = []
            page.raw_data_formula_list = []
            page.failed_formula_list = []
            page.partial_formula_map = {"C6H13NO4": {"missing_count": 1}}
            page.failed_reason_map = {}
            page.existing_formula_file_path = existing_file
            page.failed_formula_file_path = failed_file
            page.partial_formula_file_path = partial_file
            page.raw_data_formula_file_path = raw_file
            page.existing_formula_frame = {"title": "本地已有分子式"}
            page.success_formula_frame = {"title": "搜索成功分子式"}
            page.failed_formula_frame = {"title": "搜索失败分子式"}
            page.waiting_formula_frame = {"title": "待搜索分子式"}
            page._update_formula_display = lambda *args, **kwargs: None
            page._list_name_by_area = FormulaSearchPage._list_name_by_area.__get__(page, FormulaSearchPage)
            page._frame_name_by_area = FormulaSearchPage._frame_name_by_area.__get__(page, FormulaSearchPage)
            page._get_formula_from_state_index = FormulaSearchPage._get_formula_from_state_index.__get__(page, FormulaSearchPage)
            page._write_formula_list = FormulaSearchPage._write_formula_list.__get__(page, FormulaSearchPage)
            page._write_partial_formula_map = FormulaSearchPage._write_partial_formula_map.__get__(page, FormulaSearchPage)

            class FakePathManager:
                def get_formula_search_cache_path(self_inner):
                    return search_cache_dir

                def get_pubchem_raw_cache_path(self_inner):
                    raw_cache_dir = temp_root / "pubchem_raw_cache"
                    raw_cache_dir.mkdir(parents=True, exist_ok=True)
                    return raw_cache_dir

                def get_initialization_cache_path(self_inner):
                    return temp_root

                existing_formula_filename = "existing_formula.json"
                raw_data_formula_filename = "raw_data_formula.json"

                def create_cache_file(self_inner, parent_path, file_name):
                    return parent_path / file_name

            page.path_manager = FakePathManager()

            state = {
                "area_name": "本地已有分子式",
                "selected_indices": {0},
                "anchor": 0,
                "display_to_formula": ["C6H13NO4"],
            }

            with patch("package.gui.pages.formula_search_page.messagebox.askyesno", return_value=True):
                FormulaSearchPage._delete_selected_formulas(page, state)

            self.assertFalse(cache_file.exists())
            self.assertEqual(page.existing_formula_list, [])
            self.assertEqual(page.success_formula_list, [])
            self.assertEqual(json.loads(existing_file.read_text(encoding="utf-8")), [])

    def test_delete_success_formula_removes_search_cache_and_syncs_existing_file(self):
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            search_cache_dir = temp_root / "formula_search_cache"
            search_cache_dir.mkdir(parents=True, exist_ok=True)
            cache_file = search_cache_dir / "formula_search_results_C8H14O6S.json"
            cache_file.write_text('{"results": []}', encoding="utf-8")

            existing_file = temp_root / "existing_formula.json"
            existing_file.write_text(json.dumps(["C8H14O6S"], ensure_ascii=False), encoding="utf-8")
            failed_file = temp_root / "failed_formula.json"
            failed_file.write_text("[]", encoding="utf-8")
            partial_file = temp_root / "partial_formula.json"
            partial_file.write_text("{}", encoding="utf-8")
            raw_file = temp_root / "raw_data_formula.json"
            raw_file.write_text("[]", encoding="utf-8")

            page = FormulaSearchPage.__new__(FormulaSearchPage)
            page.existing_formula_list = ["C8H14O6S"]
            page.success_formula_list = ["C8H14O6S"]
            page.waiting_formula_list = []
            page.raw_data_formula_list = []
            page.failed_formula_list = []
            page.partial_formula_map = {}
            page.failed_reason_map = {}
            page.existing_formula_file_path = existing_file
            page.failed_formula_file_path = failed_file
            page.partial_formula_file_path = partial_file
            page.raw_data_formula_file_path = raw_file
            page.existing_formula_frame = {"title": "本地已有分子式"}
            page.success_formula_frame = {"title": "搜索成功分子式"}
            page.failed_formula_frame = {"title": "搜索失败分子式"}
            page.waiting_formula_frame = {"title": "待搜索分子式"}
            page._update_formula_display = lambda *args, **kwargs: None

            class FakePathManager:
                def get_formula_search_cache_path(self_inner):
                    return search_cache_dir

                def get_pubchem_raw_cache_path(self_inner):
                    raw_cache_dir = temp_root / "pubchem_raw_cache"
                    raw_cache_dir.mkdir(parents=True, exist_ok=True)
                    return raw_cache_dir

                def get_initialization_cache_path(self_inner):
                    return temp_root

                existing_formula_filename = "existing_formula.json"
                raw_data_formula_filename = "raw_data_formula.json"

                def create_cache_file(self_inner, parent_path, file_name):
                    return parent_path / file_name

            page.path_manager = FakePathManager()

            state = {
                "area_name": "搜索成功分子式",
                "selected_indices": {0},
                "anchor": 0,
                "display_to_formula": ["C8H14O6S"],
            }

            with patch("package.gui.pages.formula_search_page.messagebox.askyesno", return_value=True):
                FormulaSearchPage._delete_selected_formulas(page, state)

            self.assertFalse(cache_file.exists())
            self.assertEqual(page.success_formula_list, [])
            self.assertEqual(page.existing_formula_list, [])
            self.assertEqual(json.loads(existing_file.read_text(encoding="utf-8")), [])

    def test_progress_update_keeps_right_detail_panel_unchanged(self):
        with TemporaryDirectory() as temp_dir:
            temp_root = Path(temp_dir)
            existing_file = temp_root / "existing_formula.json"
            existing_file.write_text("[]", encoding="utf-8")
            failed_file = temp_root / "failed_formula.json"
            failed_file.write_text("[]", encoding="utf-8")
            partial_file = temp_root / "partial_formula.json"
            partial_file.write_text("{}", encoding="utf-8")
            raw_file = temp_root / "raw_data_formula.json"
            raw_file.write_text("[]", encoding="utf-8")

            page = FormulaSearchPage.__new__(FormulaSearchPage)
            page.waiting_formula_list = ["C10H15N"]
            page.success_formula_list = []
            page.existing_formula_list = []
            page.failed_formula_list = []
            page.raw_data_formula_list = []
            page.partial_formula_map = {}
            page.failed_reason_map = {}
            page.current_display_formula = "MANUAL_SELECTION"
            page.existing_formula_file_path = existing_file
            page.failed_formula_file_path = failed_file
            page.partial_formula_file_path = partial_file
            page.raw_data_formula_file_path = raw_file
            page.existing_formula_frame = {"title": "本地已有分子式"}
            page.success_formula_frame = {"title": "搜索成功分子式"}
            page.failed_formula_frame = {"title": "搜索失败分子式"}
            page.waiting_formula_frame = {"title": "待搜索分子式"}
            page._remove_from_waiting_list = FormulaSearchPage._remove_from_waiting_list.__get__(page, FormulaSearchPage)
            page._refresh_formula_displays = lambda: None

            display_calls = []
            page._display_search_results = lambda *args, **kwargs: display_calls.append(args)
            page._display_failed_summary = lambda *args, **kwargs: None

            class FakePathManager:
                def has_pubchem_raw_cache(self_inner, formula):
                    return False

            page.path_manager = FakePathManager()

            FormulaSearchPage._apply_search_progress_update(page, {
                "formula": "C10H15N",
                "status": "success",
                "data": {"results": [{"cid": 1}]},
                "detail": {},
            })

            self.assertEqual(display_calls, [])
            self.assertEqual(page.waiting_formula_list, [])
            self.assertIn("C10H15N", page.success_formula_list)
            self.assertIn("C10H15N", page.existing_formula_list)

    def test_single_click_existing_or_success_formula_shows_formula_info(self):
        page = FormulaSearchPage.__new__(FormulaSearchPage)
        calls = []
        page._get_text_line_at_event = lambda event, state: 0
        page._select_text_range = lambda state, start, end: calls.append(("select", start, end))
        page._show_formula_info_from_area = lambda state: calls.append(("show", state["area_name"]))

        existing_state = {
            "area_name": "本地已有分子式",
            "selected_indices": set(),
            "anchor": None,
        }
        success_state = {
            "area_name": "搜索成功分子式",
            "selected_indices": set(),
            "anchor": None,
        }
        waiting_state = {
            "area_name": "待搜索分子式",
            "selected_indices": set(),
            "anchor": None,
        }

        self.assertEqual(FormulaSearchPage._on_text_click(page, object(), existing_state), "break")
        self.assertIn(("show", "本地已有分子式"), calls)

        calls.clear()
        self.assertEqual(FormulaSearchPage._on_text_click(page, object(), success_state), "break")
        self.assertIn(("show", "搜索成功分子式"), calls)

        calls.clear()
        self.assertEqual(FormulaSearchPage._on_text_click(page, object(), waiting_state), "break")
        self.assertNotIn(("show", "待搜索分子式"), calls)


if __name__ == "__main__":
    unittest.main()
