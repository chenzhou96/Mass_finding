import json
import unittest
from concurrent.futures import Future
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from package.gui.pages.formula_generation_page import FormulaGenerationPage
from package.gui.pages.formula_search_page import FormulaSearchPage
from package.gui.pages.score_statistics_page import ScoreStatisticsPage


class Var:
    def __init__(self, value): self.value = value
    def get(self): return self.value
    def set(self, value): self.value = value


class Widget:
    def __init__(self): self.options = {}
    def configure(self, **kw): self.options.update(kw)


class Events:
    def __init__(self): self.status = []
    def publish(self, _event, data=None): self.status.append(data["status_text"])


class DesktopContractTests(unittest.TestCase):
    def page(self):
        page = FormulaGenerationPage.__new__(FormulaGenerationPage)
        page.event_mgr = Events()
        page.filter_feedback_label = Widget()
        page.data = [{"previous": True}]
        return page

    def test_analysis_double_click_is_ignored_while_running(self):
        page = self.page()
        page._analysis_running = True
        FormulaGenerationPage._run_analysis(page)
        self.assertEqual(page.event_mgr.status, [])

    def test_search_double_click_and_cache_clear_are_ignored_while_running(self):
        page = FormulaSearchPage.__new__(FormulaSearchPage)
        page._search_running = True
        FormulaSearchPage._run_search(page)
        FormulaSearchPage._clear_all_cache(page)
        FormulaSearchPage._run_remedy_search(page)

    def test_typing_invalid_numeric_tk_input_recovers(self):
        import tkinter as tk
        page = self.page()
        page.ms_mode = Var("ESI+")
        page.adduct_vars = {}
        page.m2z = SimpleNamespace(get=lambda: (_ for _ in ()).throw(tk.TclError("expected floating-point number")))
        with patch("package.gui.pages.formula_generation_page.messagebox.showerror") as error:
            FormulaGenerationPage._run_analysis(page)
        error.assert_called_once()
        self.assertEqual(page.event_mgr.status[-1], "done")
        self.assertEqual(page.data, [{"previous": True}])

    def test_service_error_is_not_rendered_as_empty_success(self):
        page = self.page()
        with patch("package.gui.pages.formula_generation_page.start_analysis", return_value={"status": "error", "error": "invalid charge"}):
            with self.assertRaisesRegex(ValueError, "invalid charge"):
                page._run_analysis_background({})

    def test_failed_future_unlocks_actions_and_keeps_previous_result(self):
        page = self.page()
        page._analysis_future = Future()
        page._analysis_future.set_exception(ValueError("algorithm limit"))
        page.run_button = Widget()
        page.open_button = Widget()
        page.refresh_button = Widget()
        page._analysis_running = True
        with patch("package.gui.pages.formula_generation_page.messagebox.showerror"):
            page._poll_analysis_future()
        self.assertFalse(page._analysis_running)
        self.assertEqual(page.run_button.options["state"], "normal")
        self.assertEqual(page.data, [{"previous": True}])
        self.assertEqual(page.event_mgr.status[-1], "done")

    def test_changing_inputs_marks_previous_result_stale(self):
        page = self.page()
        page._on_analysis_input_changed()
        self.assertTrue(page._results_stale)
        self.assertEqual(page._input_revision, 1)
        self.assertIn("输入已更改", page.filter_feedback_label.options["text"])
        with patch("package.gui.pages.formula_generation_page.messagebox.showwarning") as warning:
            page._send_selected_row_to_bus()
        warning.assert_called_once()

    def test_filter_rejects_invalid_nonfinite_and_reversed_ranges(self):
        for first, second, operator in [("bad", "", "="), ("nan", "", "="), ("inf", "", "="), ("0", "inf", "区间"), ("2", "1", "区间")]:
            with self.subTest(first=first, second=second):
                page = self.page()
                page.filter_field_meta = {"M/Z": {"type": "number"}}
                page.filter_condition_rows = [{"field_var": Var("M/Z"), "operator_var": Var(operator), "value_var": Var(first), "second_value_var": Var(second), "error_var": Var("")}]
                self.assertIsNone(page._collect_filter_conditions())
                self.assertIn("非法", page.filter_feedback_label.options["text"])

    def test_mass_display_preserves_more_than_four_decimals(self):
        page = self.page()
        self.assertEqual(float(page._format_float(123.123456789)), 123.123456789)
        for value in (float("nan"), float("inf"), "bad"):
            with self.assertRaises(ValueError): page._format_float(value)

    def test_import_rejects_malformed_result_without_mutating_previous_data(self):
        with TemporaryDirectory() as temp:
            source = Path(temp)/"malformed.json"
            source.write_text(json.dumps({"metadata": {}, "input_params": {"elements": {}}, "results": [{}]}))
            page = self.page()
            with patch("package.gui.pages.formula_generation_page.PathManager") as manager, patch("package.gui.pages.formula_generation_page.filedialog.askopenfilename", return_value=str(source)), patch("package.gui.pages.formula_generation_page.DataValidator.validate", return_value=True), patch("package.gui.pages.formula_generation_page.messagebox.showerror") as error:
                manager.return_value.get_formula_generation_cache_path.return_value = Path(temp)
                page._open_json_file()
            error.assert_called_once()
            self.assertEqual(page.data, [{"previous": True}])
            self.assertEqual(page.event_mgr.status[-1], "done")

    def test_import_h_semantics_distinguish_v2_and_legacy_and_preserve_raw_input(self):
        for metadata, expected in [({"engine_version":"2.0.0"},"0"),({},"不限")]:
            with self.subTest(metadata=metadata), TemporaryDirectory() as temp:
                source=Path(temp)/"saved.json"
                payload={"metadata":metadata,"input_params":{"m2z":40,"error_pct":0,"error_da":0,"charge":1,"ms_mode":"ESI+","adduct_model":["H+"],"elements":{"C":3}},"results":[]}
                source.write_text(json.dumps(payload))
                page=self.page()
                for key in ("ms_mode","m2z","charge","error_pct","error_da","dbe_filter"):setattr(page,key,Var(None))
                page.element_vars={"C":Var("0"),"H":Var("12")};page.adduct_vars={"H+":Var(False)}
                page._refresh_adduct_filter_options=lambda:None;page._apply_filters=lambda:None;page.auto_resize_columns=lambda:None;page._update_hidden_columns=lambda:None
                with patch("package.gui.pages.formula_generation_page.PathManager") as manager, patch("package.gui.pages.formula_generation_page.filedialog.askopenfilename",return_value=str(source)), patch("package.gui.pages.formula_generation_page.messagebox.showerror") as error:
                    manager.return_value.get_formula_generation_cache_path.return_value=Path(temp)
                    page._open_json_file()
                error.assert_not_called()
                self.assertEqual(page.element_vars["H"].get(),expected)
                self.assertNotIn("H",page._raw_result["input_params"]["elements"])

    def test_search_worker_queues_callbacks_without_calling_tk(self):
        import queue
        import threading
        page = FormulaSearchPage.__new__(FormulaSearchPage)
        page._ui_callbacks = queue.Queue()
        page._ui_thread_id = threading.get_ident()
        page.after = lambda *args: self.fail("worker must not call Tk.after")
        callback = lambda value: value
        worker = threading.Thread(target=page._queue_ui, args=(0, callback, "payload"))
        worker.start()
        worker.join(timeout=1)
        self.assertEqual(page._ui_callbacks.get_nowait(), (0, callback, ("payload",)))

    def test_successful_future_preserves_snapshot_and_flags_changed_input(self):
        page = self.page()
        result = {"results": [], "input_params": {"m2z": 100}}
        page._analysis_future = Future()
        page._analysis_future.set_result(result)
        page._input_revision = 2
        page._submitted_revision = 1
        page._refresh_adduct_filter_options = lambda: None
        page._apply_filters = lambda: None
        page.auto_resize_columns = lambda: None
        page._update_hidden_columns = lambda: None
        page._poll_analysis_future()
        self.assertIs(page._raw_result, result)
        self.assertTrue(page._results_stale)
        self.assertFalse(page._analysis_running)
        self.assertEqual(page.data, [])

    def test_pending_future_does_not_replace_previous_result(self):
        page = self.page()
        page._analysis_future = Future()
        scheduled = []
        page.after = lambda delay, callback: scheduled.append(delay)
        page._poll_analysis_future()
        self.assertEqual(scheduled, [75])
        self.assertEqual(page.data, [{"previous": True}])

    def test_candidate_rows_require_valid_mass_and_formula(self):
        page = self.page()
        valid = {"formula": {"C": 2, "H": 6, "O": 1}, "adduct_type": "[M+H]+", "calculated_properties": {"predicted_mz": 47.049141265, "molecular_weight": 46.041864812, "dbr": 0}}
        self.assertEqual(page._map_data([valid])[0]["H"], 6)
        for key, value in [("predicted_mz", None), ("molecular_weight", -1), ("dbr", float("inf"))]:
            malformed = dict(valid, calculated_properties=dict(valid["calculated_properties"], **{key: value}))
            with self.assertRaises(ValueError): page._map_data([malformed])

    def test_statistics_rejects_invalid_threshold_without_changing_results(self):
        for value in ("bad", "nan", "inf", "-1", "101"):
            page = ScoreStatisticsPage.__new__(ScoreStatisticsPage)
            page.threshold_spinbox = Var(value)
            page.current_threshold = 80.0
            page.statistics_data = {"previous": True}
            with patch("package.gui.pages.score_statistics_page.messagebox.showerror") as error:
                page._run_statistics()
            error.assert_called_once()
            self.assertEqual(page.current_threshold, 80.0)
            self.assertEqual(page.statistics_data, {"previous": True})

    def test_statistics_export_cancel_has_no_write_or_success_notice(self):
        page = ScoreStatisticsPage.__new__(ScoreStatisticsPage)
        page.statistics_data = {"C2H6O": {}}
        page.path_manager = SimpleNamespace(desktop_path=Path("/tmp"))
        with patch("package.gui.pages.score_statistics_page.filedialog.asksaveasfilename", return_value=""), patch("package.gui.pages.score_statistics_page.messagebox.showinfo") as notice:
            page._export_csv()
        notice.assert_not_called()

    def test_cancellation_waits_for_worker_exit_and_preserves_previous_result(self):
        import threading
        page = self.page()
        page._analysis_running = True
        page._analysis_cancel_event = threading.Event()
        page.cancel_button = Widget()
        page._analysis_future = Future()
        page._cancel_analysis()
        self.assertTrue(page._analysis_cancel_event.is_set())
        self.assertTrue(page._analysis_running)
        self.assertEqual(page.cancel_button.options["state"], "disabled")
        page._analysis_future.set_exception(ValueError("分析已取消"))
        with patch("package.gui.pages.formula_generation_page.messagebox.showerror") as error:
            page._poll_analysis_future()
        error.assert_not_called()
        self.assertFalse(page._analysis_running)
        self.assertEqual(page.data, [{"previous": True}])
        self.assertEqual(page.cancel_button.options["state"], "disabled")

    def test_statistics_export_failure_preserves_existing_file(self):
        with TemporaryDirectory() as temp:
            target = Path(temp)/"statistics.csv"
            target.write_text("previous export", encoding="utf-8")
            page = ScoreStatisticsPage.__new__(ScoreStatisticsPage)
            page.statistics_data = {"C2H6O": {"total": 1, "above": 1, "pct": 100.0, "top_score": 85.123456}}
            page.current_threshold = 80.0
            page.path_manager = SimpleNamespace(desktop_path=Path(temp))
            with patch("package.gui.pages.score_statistics_page.filedialog.asksaveasfilename", return_value=str(target)), patch("package.gui.pages.score_statistics_page.csv.writer") as writer, patch("package.gui.pages.score_statistics_page.messagebox.showerror") as error:
                writer.return_value.writerow.side_effect = OSError("simulated write failure")
                page._export_csv()
            error.assert_called_once()
            self.assertEqual(target.read_text(), "previous export")
            self.assertEqual(list(Path(temp).glob(".mass-finding-*.tmp")), [])

    def test_import_rejects_fractional_or_negative_atom_counts(self):
        page = self.page()
        for value in (0.5, -1, float("nan"), True):
            with self.assertRaises(ValueError): page._normalize_element_count(value)


if __name__ == "__main__": unittest.main()
