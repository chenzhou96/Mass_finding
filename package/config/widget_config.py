from .base_config import BaseConfig
import tkinter as tk

class WidgetConfig:
    frame = {
        'bg': BaseConfig.BACKGROUND,
        'bd': BaseConfig.BD_B,
        'relief': tk.FLAT,
        'padx': BaseConfig.PADDING_A,
        'pady': BaseConfig.PADDING_A,
    }

    labelframe = {
        'bg': BaseConfig.BACKGROUND,
        'bd': BaseConfig.BD_B,
        'fg': BaseConfig.TEXT_DARK,
        'relief': tk.FLAT,
        'font': (BaseConfig.FONT_STYLE, BaseConfig.FONT_SIZE, 'bold'),
        'padx': BaseConfig.PADDING_A,
        'pady': BaseConfig.PADDING_A,
    }

    toplevel = {
        'bg': BaseConfig.BACKGROUND,
        'bd': BaseConfig.BD_B,
        'relief': tk.FLAT,
    }

    panedwindow = {
        'bg': BaseConfig.BACKGROUND,
        'bd': BaseConfig.BD_B,
        'relief': tk.FLAT,
    }

    canvas = {
        'bg': BaseConfig.BACKGROUND,
        'bd': BaseConfig.BD_B,
        'relief': tk.FLAT,
    }

    scrolledwindow = {
        'bg': BaseConfig.BACKGROUND,
        'bd': BaseConfig.BD_A,
        'relief': tk.SUNKEN,
        'troughcolor': BaseConfig.BACKGROUND,
        'highlightthickness': 0,
        'width': 0,
    }

    button = {
        'bg': BaseConfig.BACKGROUND,
        'fg': BaseConfig.TEXT_DARK,
        'bd': BaseConfig.BD_B,
        'relief': tk.RIDGE,
        'activebackground': BaseConfig.SECONDARY_COLOR,
        'activeforeground': BaseConfig.PRIMARY_COLOR,
        'font': (BaseConfig.FONT_STYLE, BaseConfig.FONT_SIZE),
        'padx': BaseConfig.PADDING_A,
        'pady': BaseConfig.PADDING_A,
        'highlightthickness': 0,
        'highlightbackground': BaseConfig.BACKGROUND,
    }

    entry = {
        'bg': BaseConfig.BACKGROUND,
        'fg': BaseConfig.TEXT_DARK,
        'bd': BaseConfig.BD_B,
        'relief': tk.SUNKEN,
        'insertbackground': BaseConfig.TEXT_DARK,
        'font': (BaseConfig.FONT_STYLE, BaseConfig.FONT_SIZE),
        'highlightthickness': 0.5,
        'highlightbackground': BaseConfig.SECONDARY_COLOR,
    }

    label = {
        'bg': BaseConfig.BACKGROUND,
        'fg': BaseConfig.TEXT_DARK,
        'font': (BaseConfig.FONT_STYLE, BaseConfig.FONT_SIZE),
        'padx': BaseConfig.PADDING_A,
        'pady': BaseConfig.PADDING_A,
    }

    text = {
        'bg': BaseConfig.BACKGROUND,
        'fg': BaseConfig.TEXT_DARK,
        'bd': BaseConfig.BD_A,
        'relief': tk.SUNKEN,
        'font': (BaseConfig.FONT_STYLE, BaseConfig.FONT_SIZE),
        'highlightthickness': 0.5,
        'highlightbackground': BaseConfig.SECONDARY_COLOR,
    }

    checkbutton = {
        'bg': BaseConfig.BACKGROUND,
        'fg': BaseConfig.TEXT_DARK,
        'bd': BaseConfig.BD_A,
        'relief': tk.FLAT,
        'font': (BaseConfig.FONT_STYLE, BaseConfig.FONT_SIZE),
        'padx': BaseConfig.PADDING_A,
        'pady': BaseConfig.PADDING_A,
    }

