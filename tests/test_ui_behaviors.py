import json
import logging
import os
import sys
import threading
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

    def set(self, value):
        self._value = value


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


class _FakeWidget:
    def __init__(self):
        self.packed = False
        self.configured = {}

    def pack(self, *args, **kwargs):
        self.packed = True

    def pack_forget(self, *args, **kwargs):
        self.packed = False

    def configure(self, **kwargs):
        self.configured.update(kwargs)


class _FakeTextWidget:
    def __init__(self):
        self.main_thread_id = threading.get_ident()
        self.messages = []
        self.configured = {}

    def tag_configure(self, *args, **kwargs):
        return None

    def config(self, **kwargs):
        self.configured.update(kwargs)

    def insert(self, *args, **kwargs):
        if len(args) >= 2:
            self.messages.append(args[1])

    def see(self, *args, **kwargs):
        return None

    def after(self, delay, callback=None, *args):
        if threading.get_ident() != self.main_thread_id:
            raise RuntimeError("after called off main thread")
        return None

    def winfo_exists(self):
        return True


class UiBehaviorTests(unittest.TestCase):
    def test_open_json_file_uses_formula_generation_cache_as_default_folder(self):
        expected_dir = Path("E:/Python/Mass_finding/mass_finding_cache/formula_generation_cache")
        page = FormulaGenerationPage.__new__(FormulaGenerationPage)
        page.event_mgr = DummyEventManager()

        with patch("package.gui.pages.formula_generation_page.PathManager") as path_manager_mock, \
             patch("package.gui.pages.formula_generation_page.filedialog.askopenfilename", return_value="") as ask_mock:
            path_manager_mock.return_value.get_formula_generation_cache_path.return_value = expected_dir

            FormulaGenerationPage._open_json_file(page)

        ask_mock.assert_called_once()
        self.assertEqual(ask_mock.call_args.kwargs.get("initialdir"), str(expected_dir))
        self.assertEqual(page.event_mgr.status_updates[-1], "done")

    def test_open_json_file_temporarily_switches_cwd_to_cache_dir(self):
        expected_dir = Path("E:/Python/Mass_finding/mass_finding_cache/formula_generation_cache")
        page = FormulaGenerationPage.__new__(FormulaGenerationPage)
        page.event_mgr = DummyEventManager()
        original_cwd = os.getcwd()

        def fake_dialog(**kwargs):
            self.assertEqual(Path.cwd(), expected_dir)
            return ""

        with patch("package.gui.pages.formula_generation_page.PathManager") as path_manager_mock, \
             patch("package.gui.pages.formula_generation_page.filedialog.askopenfilename", side_effect=fake_dialog):
            path_manager_mock.return_value.get_formula_generation_cache_path.return_value = expected_dir
            FormulaGenerationPage._open_json_file(page)

        self.assertEqual(Path.cwd(), Path(original_cwd))

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

    def test_event_bus_publish_does_not_deadlock_when_log_listener_fails(self):
        from package.config.event_config import EventPriority, EventType
        from package.core.event import Event, EventBus
        from package.utils.logger import EventLogHandler

        class DummyEventManagerForLogging:
            def __init__(self):
                self.bus = EventBus()

            def publish(self, event_type, data=None, priority=EventPriority.NORMAL):
                priority_value = priority.value if hasattr(priority, "value") else priority
                self.bus.publish(Event(event_type.value, data, priority_value))

        event_mgr = DummyEventManagerForLogging()

        def broken_listener(_event):
            raise RuntimeError("boom")

        event_mgr.bus.subscribe(EventType.LOG_MESSAGE.value, broken_listener)

        root_logger = logging.getLogger()
        old_handlers = list(root_logger.handlers)
        old_level = root_logger.level
        root_logger.handlers = [EventLogHandler(event_mgr)]
        root_logger.setLevel(logging.INFO)

        finished = threading.Event()

        def emit_log():
            logging.info("probe message")
            finished.set()

        try:
            worker = threading.Thread(target=emit_log, daemon=True)
            worker.start()
            worker.join(timeout=1.0)
            self.assertTrue(finished.is_set(), "logging event handling deadlocked")
        finally:
            root_logger.handlers = old_handlers
            root_logger.setLevel(old_level)

    def test_logger_log_to_ui_is_safe_from_worker_thread(self):
        from package.core.event import EventBus
        from package.utils.logger import Logger

        logger = Logger(event_bus=EventBus())
        logger.set_text_widget(_FakeTextWidget())

        payload = SimpleNamespace(data={"level": "INFO", "message": "worker-thread log"})
        failures = []

        def call_log_to_ui():
            try:
                logger.log_to_ui(payload)
            except Exception as ex:
                failures.append(ex)

        worker = threading.Thread(target=call_log_to_ui, daemon=True)
        worker.start()
        worker.join(timeout=1.0)

        self.assertFalse(failures, f"log_to_ui should not raise from worker thread: {failures}")

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

    def test_no_compounds_failure_shows_popup_and_is_not_retained(self):
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
            page.waiting_formula_list = ["C5HNO"]
            page.success_formula_list = []
            page.existing_formula_list = []
            page.failed_formula_list = []
            page.raw_data_formula_list = []
            page.partial_formula_map = {}
            page.failed_reason_map = {}
            page.existing_formula_file_path = existing_file
            page.failed_formula_file_path = failed_file
            page.partial_formula_file_path = partial_file
            page.raw_data_formula_file_path = raw_file
            page._remove_from_waiting_list = FormulaSearchPage._remove_from_waiting_list.__get__(page, FormulaSearchPage)
            page._write_formula_list = FormulaSearchPage._write_formula_list.__get__(page, FormulaSearchPage)
            page._write_partial_formula_map = FormulaSearchPage._write_partial_formula_map.__get__(page, FormulaSearchPage)
            page._refresh_formula_displays = lambda: None
            page._display_failed_summary = lambda *args, **kwargs: None

            class FakePathManager:
                def has_pubchem_raw_cache(self_inner, formula):
                    return False

            page.path_manager = FakePathManager()

            page._pending_no_compounds_formulas = []
            page.winfo_toplevel = lambda: "MAIN_WINDOW"

            with patch("package.gui.pages.formula_search_page.messagebox.showinfo") as info_mock:
                FormulaSearchPage._apply_search_progress_update(page, {
                    "formula": "C5HNO",
                    "status": "failed",
                    "detail": {
                        "category": "no_compounds",
                        "message": "no_compounds:final_empty_result",
                    },
                })
                FormulaSearchPage._flush_pending_no_compounds_notices(page)

            self.assertEqual(page.waiting_formula_list, [])
            self.assertEqual(page.failed_formula_list, [])
            self.assertNotIn("C5HNO", page.failed_reason_map)
            self.assertEqual(json.loads(failed_file.read_text(encoding="utf-8")), [])
            info_mock.assert_called_once_with(
                "未找到匹配结果",
                "分子式 C5HNO 在 PubChem 中没有匹配化合物，已自动从列表中移除。",
                parent="MAIN_WINDOW",
            )

    def test_flush_no_compounds_notice_uses_parent_window(self):
        page = FormulaSearchPage.__new__(FormulaSearchPage)
        page._pending_no_compounds_formulas = ["C5HNO"]
        page.winfo_toplevel = lambda: "MAIN_WINDOW"

        with patch("package.gui.pages.formula_search_page.messagebox.showinfo") as info_mock:
            FormulaSearchPage._flush_pending_no_compounds_notices(page)

        info_mock.assert_called_once_with(
            "未找到匹配结果",
            "分子式 C5HNO 在 PubChem 中没有匹配化合物，已自动从列表中移除。",
            parent="MAIN_WINDOW",
        )
        self.assertEqual(page._pending_no_compounds_formulas, [])

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

    def test_dbr_filter_uses_integer_spinbox_like_elements(self):
        page = FormulaGenerationPage.__new__(FormulaGenerationPage)
        page.filter_fields_order = ["Adduct", "M/Z", "DBR", "C"]
        page.element_filter_fields = {"C", "H", "N", "O", "S", "P", "Si", "F", "Cl", "Br", "I", "B", "Se"}
        page.filter_field_meta = FormulaGenerationPage._build_filter_field_meta(page)
        page._get_current_adduct_filter_options = lambda: []
        page._on_filter_operator_change = lambda row: None

        row = {
            "field_var": DummyVar("DBR"),
            "operator_var": DummyVar(""),
            "operator_combo": _FakeWidget(),
            "value_entry": _FakeWidget(),
            "value_spin": _FakeWidget(),
            "value_combo": _FakeWidget(),
            "second_value_label": _FakeWidget(),
            "second_value_entry": _FakeWidget(),
            "second_value_spin": _FakeWidget(),
        }

        FormulaGenerationPage._refresh_row_field_behavior(page, row)

        self.assertTrue(row["value_spin"].packed)
        self.assertFalse(row["value_entry"].packed)

    def test_compound_info_displays_cas_between_cid_and_title(self):
        page = FormulaSearchPage.__new__(FormulaSearchPage)
        page.current_formula_results = [{
            "cid": 702,
            "title": "Ethanol",
            "iupac_name": "ethanol",
            "synonyms": ["64-17-5", "ethyl alcohol"],
        }]

        class FakeListbox:
            def curselection(self):
                return (0,)

        class FakeText:
            def __init__(self):
                self.content = ""

            def config(self, **kwargs):
                return None

            def delete(self, *args, **kwargs):
                self.content = ""

            def insert(self, _index, text):
                self.content += text

        page.compound_listbox = FakeListbox()
        page.result_text = FakeText()
        page._render_structure_image = lambda *args, **kwargs: None

        FormulaSearchPage._on_compound_select(page)

        self.assertIn("CID: 702\nCAS: 64-17-5\nTitle: Ethanol", page.result_text.content)

    def test_failed_summary_logs_instead_of_overwriting_compound_info_panel(self):
        page = FormulaSearchPage.__new__(FormulaSearchPage)

        class FakeText:
            def __init__(self):
                self.actions = []

            def config(self, **kwargs):
                self.actions.append(("config", kwargs))

            def insert(self, *args, **kwargs):
                self.actions.append(("insert", args, kwargs))

        page.result_text = FakeText()

        with patch("package.gui.pages.formula_search_page.logging.info") as info_mock, \
             patch("package.gui.pages.formula_search_page.logging.warning") as warning_mock:
            FormulaSearchPage._display_failed_summary(
                page,
                ["C10H15N"],
                {"C10H15N": {"category": "timeout", "message": "timeout:test"}},
                {"timeout": 1, "no_compounds": 0, "poll_limit": 0, "other": 0},
                ["C8H11N"],
            )

        self.assertEqual(page.result_text.actions, [])
        self.assertTrue(info_mock.called or warning_mock.called)

    def test_remedy_search_moves_failed_formulas_to_waiting_immediately(self):
        page = FormulaSearchPage.__new__(FormulaSearchPage)
        page.failed_formula_list = ["C10H15N", "C8H11N"]
        page.waiting_formula_list = []
        page.partial_formula_map = {"C7H7NO": {"missing_count": 2}}
        page.failed_reason_map = {"C10H15N": {"category": "timeout"}, "C8H11N": {"category": "other"}}
        page.failed_formula_file_path = Path("failed_formula.json")
        page._write_formula_list = lambda *args, **kwargs: True

        updates = []
        page._update_formula_display = lambda frame, values: updates.append((frame["title"], list(values)))
        page.failed_formula_frame = {"title": "搜索失败分子式"}
        page.waiting_formula_frame = {"title": "待搜索分子式"}

        captured = {}
        page._run_search = lambda target_formulas=None, raw_only=False: captured.update({
            "target_formulas": list(target_formulas or []),
            "raw_only": raw_only,
        })

        FormulaSearchPage._run_remedy_search(page)

        self.assertEqual(page.failed_formula_list, [])
        self.assertEqual(page.waiting_formula_list, ["C10H15N", "C8H11N", "C7H7NO"])
        self.assertNotIn("C10H15N", page.failed_reason_map)
        self.assertNotIn("C8H11N", page.failed_reason_map)
        self.assertEqual(captured["target_formulas"], ["C10H15N", "C8H11N", "C7H7NO"])
        self.assertIn(("搜索失败分子式", []), updates)
        self.assertIn(("待搜索分子式", ["C10H15N", "C8H11N", "C7H7NO"]), updates)


if __name__ == "__main__":
    unittest.main()
