"""Synthetic selection-state regressions; no identity or score calibration."""
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from package.gui.pages.score_statistics_page import ScoreStatisticsPage


class ScoreStatisticsSelectionTests(unittest.TestCase):
    def setUp(self):
        self.page = ScoreStatisticsPage.__new__(ScoreStatisticsPage)
        self.first = {"cid": 1, "title": "Synthetic A", "final_score": 90}
        self.second = {"cid": 2, "title": "Synthetic B", "final_score": 91}
        self.page.statistics_data = {
            "CH4": {"compounds": [self.first]},
            "H2O": {"compounds": []},
            "NH3": {"compounds": [self.second]},
        }
        self.page._current_compounds = []
        self.page._structure_photo = None
        self.page._structure_image_path = None
        self.page.compound_listbox = Mock()
        self.page.structure_label = Mock()
        self.label_options = {}
        self.page.structure_label.config.side_effect = self.label_options.update
        self.page._render_compound_structure = Mock(side_effect=self.render)

    def render(self, compound):
        self.page._structure_photo = "photo-" + str(compound["cid"])
        self.page._structure_image_path = Path("synthetic-" + str(compound["cid"]) + ".png")
        self.page.structure_label.config(image=self.page._structure_photo, text="")

    def assert_cleared(self):
        self.assertEqual(self.page._current_compounds, [])
        self.assertIsNone(self.page._structure_photo)
        self.assertIsNone(self.page._structure_image_path)
        self.assertEqual(self.label_options["image"], "")
        self.assertTrue(self.label_options["text"])

    def test_selecting_empty_formula_clears_prior_preview_and_open_target(self):
        self.page._show_compounds_for_formula("CH4")
        self.page._show_compounds_for_formula("H2O")
        self.assert_cleared()
        self.assertIn("阈值", self.label_options["text"])
        with patch("package.gui.pages.score_statistics_page.messagebox.showwarning") as warning, \
             patch.object(Path, "exists", return_value=True), \
             patch("os.startfile", create=True) as windows_open, \
             patch("subprocess.Popen") as open_image:
            self.page._open_structure_image()
        warning.assert_called_once()
        windows_open.assert_not_called()
        open_image.assert_not_called()

    def test_selecting_unavailable_formula_clears_prior_compound_list_and_preview(self):
        self.page._show_compounds_for_formula("CH4")
        self.page.compound_listbox.reset_mock()
        self.page._show_compounds_for_formula("MISSING")
        self.assert_cleared()
        self.page.compound_listbox.delete.assert_called_once()
        self.assertIn("统计", self.label_options["text"])

    def test_unavailable_selection_recovers_and_queued_compound_event_is_harmless(self):
        self.page._show_compounds_for_formula("CH4")
        self.page._show_compounds_for_formula("MISSING")
        self.page.compound_listbox.curselection.return_value = (0,)
        self.page._render_compound_structure.reset_mock()
        self.page._on_compound_select()
        self.page._render_compound_structure.assert_not_called()
        self.assert_cleared()
        self.page._show_compounds_for_formula("NH3")
        self.page._render_compound_structure.assert_called_once_with(self.second)
        self.assertEqual(self.page._current_compounds, [self.second])
        self.assertEqual(self.page.statistics_data["CH4"]["compounds"], [self.first])

    def test_populated_formula_without_structure_retains_its_unavailable_preview(self):
        self.page._show_compounds_for_formula("CH4")
        self.page._render_compound_structure.side_effect = lambda _compound: self.page.structure_label.config(
            image="", text="SMILES/InChI 无法解析")
        self.page._show_compounds_for_formula("NH3")
        self.assertEqual(self.page._current_compounds, [self.second])
        self.assertIsNone(self.page._structure_image_path)
        self.assertEqual(self.label_options, {"image": "", "text": "SMILES/InChI 无法解析"})

    def test_repeated_empty_selection_and_return_to_populated_formula_are_consistent(self):
        for formula in ("CH4", "H2O", "H2O", "NH3", "H2O", "CH4"):
            self.page._show_compounds_for_formula(formula)
            expected = self.page.statistics_data[formula]["compounds"]
            self.assertEqual(self.page._current_compounds, expected)
            if expected:
                self.assertEqual(self.page._structure_image_path, Path("synthetic-" + str(expected[0]["cid"]) + ".png"))
                self.page.compound_listbox.selection_set.assert_called_with(0)
            else:
                self.assert_cleared()

    def test_tree_selection_uses_same_empty_state_contract(self):
        selected = ["first"]
        self.page.tree = SimpleNamespace(selection=lambda: selected,
            item=lambda item, _option: ("CH4" if item == "first" else "H2O",))
        self.page._on_table_row_select()
        selected[:] = ["empty"]
        self.page._on_table_row_select()
        self.assert_cleared()


if __name__ == "__main__":
    unittest.main()
