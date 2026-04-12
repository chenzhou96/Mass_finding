from .base_config import BaseConfig
import tkinter as tk

class WidgetConfig:
    frame = {
        'bg': BaseConfig.BACKGROUND,
        'bd': 0,
        'relief': tk.FLAT,
        'padx': BaseConfig.PADDING_B,
        'pady': BaseConfig.PADDING_B,
    }

    labelframe = {
        'bg': '#ffffff',
        'bd': 0,
        'fg': BaseConfig.TEXT_DARK,
        'relief': tk.FLAT,
        'labelanchor': 'nw',
        'font': (BaseConfig.FONT_STYLE, BaseConfig.FONT_SIZE, 'bold'),
        'padx': BaseConfig.PADDING_B,
        'pady': BaseConfig.PADDING_B,
        'highlightthickness': 0,
    }

    toplevel = {
        'bg': BaseConfig.BACKGROUND,
        'bd': 0,
        'relief': tk.FLAT,
    }

    panedwindow = {
        'bg': BaseConfig.BACKGROUND,
        'bd': 0,
        'relief': tk.FLAT,
    }

    canvas = {
        'bg': BaseConfig.BACKGROUND,
        'bd': 0,
        'relief': tk.FLAT,
    }

    scrolledwindow = {
        'bg': BaseConfig.BACKGROUND,
        'bd': 0,
        'troughcolor': BaseConfig.SECONDARY_COLOR,
        'highlightthickness': 0,
        'width': 0,
    }

    menu = {
        'tearoff': 0,
        'bg': '#ffffff',
        'fg': BaseConfig.TEXT_DARK,
        'activebackground': BaseConfig.ACCENT_COLOR,
        'activeforeground': BaseConfig.TEXT_DARK,
    }

    button = {
        'bg': BaseConfig.PRIMARY_COLOR,
        'fg': '#ffffff',
        'bd': 0,
        'relief': tk.FLAT,
        'activebackground': BaseConfig.SECONDARY_COLOR,
        'activeforeground': '#ffffff',
        'font': (BaseConfig.FONT_STYLE, BaseConfig.FONT_SIZE),
        'padx': BaseConfig.PADDING_B,
        'pady': BaseConfig.PADDING_B,
        'highlightthickness': 0,
        'highlightbackground': BaseConfig.BACKGROUND,
        'cursor': 'hand2',
    }

    entry = {
        'bg': '#ffffff',
        'fg': BaseConfig.TEXT_DARK,
        'bd': 0,
        'relief': tk.FLAT,
        'insertbackground': BaseConfig.TEXT_DARK,
        'font': (BaseConfig.FONT_STYLE, BaseConfig.FONT_SIZE),
        'highlightthickness': 1,
        'highlightbackground': BaseConfig.SECONDARY_COLOR,
        'highlightcolor': BaseConfig.TEXT_DARK,
        'insertwidth': 2,
        'justify': 'left',
    }

    label = {
        'bg': BaseConfig.BACKGROUND,
        'fg': BaseConfig.TEXT_DARK,
        'font': (BaseConfig.FONT_STYLE, BaseConfig.FONT_SIZE, 'bold'),
        'padx': BaseConfig.PADDING_A,
        'pady': BaseConfig.PADDING_A,
    }

    text = {
        'bg': '#ffffff',
        'fg': BaseConfig.TEXT_DARK,
        'bd': 0,
        'relief': tk.FLAT,
        'font': (BaseConfig.FONT_STYLE, BaseConfig.FONT_SIZE),
        'highlightthickness': 1,
        'highlightbackground': BaseConfig.SECONDARY_COLOR,
        'highlightcolor': BaseConfig.PRIMARY_COLOR,
        'insertbackground': BaseConfig.TEXT_DARK,
    }

    checkbutton = {
        'bg': BaseConfig.BACKGROUND,
        'fg': BaseConfig.TEXT_DARK,
        'bd': 0,
        'relief': tk.FLAT,
        'font': (BaseConfig.FONT_STYLE, BaseConfig.FONT_SIZE),
        'padx': BaseConfig.PADDING_A,
        'pady': BaseConfig.PADDING_A,
    }

