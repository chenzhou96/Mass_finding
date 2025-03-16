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

    panedWindow = {
        'bg': BaseConfig.BACKGROUND,
        'bd': BaseConfig.BD_B,
        'relief': tk.FLAT,
    }

    canvas = {
        'bg': BaseConfig.BACKGROUND,
        'bd': BaseConfig.BD_B,
        'relief': tk.FLAT,
    }

    scrolledWindow = {
        'bg': BaseConfig.BACKGROUND,
        'bd': BaseConfig.BD_B,
        'relief': tk.SUNKEN,
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
    }

    entry = {
        'bg': BaseConfig.BACKGROUND,
        'fg': BaseConfig.TEXT_DARK,
        'bd': BaseConfig.BD_B,
        'relief': tk.SUNKEN,
        'insertbackground': BaseConfig.TEXT_DARK,
        'font': (BaseConfig.FONT_STYLE, BaseConfig.FONT_SIZE),
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

