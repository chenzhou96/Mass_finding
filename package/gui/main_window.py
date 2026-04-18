import tkinter as tk
from tkinter import messagebox
import logging
from .components.navigation_bar import NavigationBar
from ..utils.logger import Logger, EventLogHandler
from ..core.event import EventManager
from ..config.AppUI_config import AppUIConfig
from ..config.event_config import EventType, EventPriority
from ..core.page_factory import PageFactory
from .components.status_bar import StatusBar
from ..config.base_config import BaseConfig
from ..utils.widget_factory import WidgetFactory
import platform
from PIL import Image, ImageTk
from ..config.path_config import PathManager
from ..service.cache_index_service import sync_formula_index_cache

class APP(tk.Tk):
    def __init__(self):
        self._mid_ratio = (3, 1)
        self._right_ratio = (1, 1)
        self.path_manager = PathManager()
        self._sync_formula_indexes_on_startup()
        self._init_window()
        self._init_components()
        self._setup_layout()
        self._init_event_handlers()
        self._setup_initial_page()

        # 发布初始化完成日志
        logging.info("应用初始化完成")
        self.event_mgr.publish(
            EventType.STATUS_UPDATE, 
            data={"status_text": "done"}
        )

    def _sync_formula_indexes_on_startup(self):
        try:
            sync_formula_index_cache(self.path_manager)
        except Exception as ex:
            logging.warning(f"启动阶段同步 formula 索引失败: {ex}")

    def _init_window(self):
        super().__init__()
        self.current_status_text = "done"
        self.title(AppUIConfig.MainWindow.TITLE)
        self.geometry(AppUIConfig.MainWindow.WINDOW_SIZE)
        self.configure(bg=AppUIConfig.MainWindow.BG_COLOR)
        self.protocol("WM_DELETE_WINDOW", self._on_close_request)
        self._set_icon()

    def _set_icon(self):
        system = platform.system()
        try:
            if system == "Windows" and self.path_manager.ico_path.exists():
                self.iconbitmap(str(self.path_manager.ico_path))
            elif system == "Darwin" and self.path_manager.icns_path.exists():
                image = Image.open(self.path_manager.icns_path)
                icon = ImageTk.PhotoImage(image)
                self.iconphoto(True, icon)
            else:
                logging.warning("未找到可用图标资源，已跳过窗口图标设置")
        except Exception as ex:
            logging.warning(f"设置窗口图标失败: {ex}")

    def _init_components(self):
        """优化后的组件初始化"""
        self.current_page = None
        self.formula_bus = []
        # 1. 初始化事件总线
        self.event_mgr = EventManager(root=self)
        # 2. 初始化日志器（依赖 event_mgr 的 bus）
        self.logger = Logger(event_bus=self.event_mgr.bus)
        self.widget_factory = WidgetFactory()
        # 3. 初始化页面工厂（需要 event_mgr）
        self.page_factory = PageFactory(
            root=self,  # 顶层容器（主窗口）
            event_mgr=self.event_mgr
        )
        # 4. 创建布局容器
        self._create_layout_containers()
        # 5. 初始化导航栏，状态栏，元素区域
        self._create_navigation_bar()
        self._create_status_bar()
        self._init_formula_bus()
        # 6. 初始化日志器
        self._init_logger()

    def _create_layout_containers(self):
        self.nav_frame = self.widget_factory.create_frame(
            self,
            **AppUIConfig.NavigationBar.frame
        )
        self.mid_frame = self.widget_factory.create_frame(
            self,
            **AppUIConfig.MainWindow.frame
        )
        self.status_frame = self.widget_factory.create_frame(
            self,
            **AppUIConfig.StatusBar.frame
        )
        self.main_paned = self.widget_factory.create_paned_window(
            self.mid_frame,
            orient=tk.HORIZONTAL,
            sashrelief=tk.FLAT,
            showhandle=False,
            opaqueresize=True,
        )
        self.left_frame = self.widget_factory.create_frame(
            self.main_paned,
            **AppUIConfig.FunctionZone.frame
        )
        self.right_frame = self.widget_factory.create_frame(
            self.main_paned,
            **AppUIConfig.InteractiveZone.frame
        )
        self.right_paned = self.widget_factory.create_paned_window(
            self.right_frame,
            orient=tk.VERTICAL,
            sashrelief=tk.FLAT,
            showhandle=False,
            opaqueresize=True,
        )
        self.upper_frame = self.widget_factory.create_labelframe(
            self.right_paned,
            text='分子式 bus',
            **AppUIConfig.InteractiveZone.frame
        )
        self.lower_frame = self.widget_factory.create_labelframe(
            self.right_paned,
            text='操作日志',
            **AppUIConfig.InteractiveZone.frame
        )
        self.page_factory.set_root(self.left_frame)

    def _create_navigation_bar(self):
        self.nav_bar = NavigationBar(
            self,
            self.nav_frame,
            self.page_factory,
            self.widget_factory
        )

    def _create_status_bar(self):
        self.status_bar = StatusBar(
            self.status_frame,
            widget_factory=self.widget_factory,
            event_mgr=self.event_mgr
        )

    def _init_formula_bus(self):
        # 上部信息区组件（分子式显示）
        self.upper_info = self.widget_factory.create_scrollable_text(self.upper_frame)
        self.upper_info["scrollbar"].pack(side=tk.RIGHT, fill=tk.Y)
        self.upper_info["text"].pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self.upper_info["text"].tag_configure("selected_line", background="#d0e7ff")
        self.selected_bus_indices = set()
        self.selection_anchor = None

        self.upper_info["text"].bind("<Button-1>", self._on_formula_bus_click)
        self.upper_info["text"].bind("<Shift-Button-1>", self._on_formula_bus_shift_click)
        self.upper_info["text"].bind("<B1-Motion>", self._on_formula_bus_drag)
        self.upper_info["text"].bind("<ButtonRelease-1>", self._on_formula_bus_release)

        self.popup_menu = self.widget_factory.create_menu(self.upper_info["text"], tearoff=0)
        self.popup_menu.add_command(label="发送到待搜索分子式", command=self._send_selected_to_search)
        self.popup_menu.add_separator()
        self.popup_menu.add_command(label="删除", command=self._delete_selected_text)
        self.upper_info["text"].bind("<Button-3>", self._show_popup)
    
    def _show_popup(self, event):
        try:
            self._ensure_right_click_selection(event)
            self.popup_menu.tk_popup(event.x_root, event.y_root)
        finally:
            self.popup_menu.grab_release()

    def _ensure_right_click_selection(self, event):
        line = self._text_line_at_event(event)
        if line is None:
            return
        if line not in self.selected_bus_indices:
            self.selection_anchor = line
            self._select_range(line, line)

    def _text_line_at_event(self, event):
        text_widget = self.upper_info["text"]
        try:
            index = text_widget.index(f"@{event.x},{event.y}")
            line = int(index.split('.')[0]) - 1
            if line < 0 or line >= len(self.formula_bus):
                return None
            return line
        except Exception:
            return None

    def _select_range(self, start_line, end_line):
        text_widget = self.upper_info["text"]
        text_widget.tag_remove("selected_line", "1.0", tk.END)
        start = min(start_line, end_line)
        end = max(start_line, end_line)
        self.selected_bus_indices = set(range(start, end + 1))
        for line in self.selected_bus_indices:
            text_widget.tag_add(
                "selected_line",
                f"{line + 1}.0",
                f"{line + 1}.end"
            )

    def _on_formula_bus_click(self, event):
        line = self._text_line_at_event(event)
        if line is not None:
            self.selection_anchor = line
            self._select_range(line, line)
        return "break"

    def _on_formula_bus_shift_click(self, event):
        line = self._text_line_at_event(event)
        if line is not None:
            if self.selection_anchor is None:
                self.selection_anchor = line
            self._select_range(self.selection_anchor, line)
        return "break"

    def _on_formula_bus_drag(self, event):
        if self.selection_anchor is None:
            self.selection_anchor = self._text_line_at_event(event)
            if self.selection_anchor is None:
                return "break"
        target_line = self._text_line_at_event(event)
        if target_line is not None:
            self._select_range(self.selection_anchor, target_line)
        return "break"

    def _on_formula_bus_release(self, event):
        if self.selection_anchor is None:
            return
        target_line = self._text_line_at_event(event)
        if target_line is not None:
            self._select_range(self.selection_anchor, target_line)
        return "break"

    def _update_formula_display(self):
        """根据列表内容更新文本框显示"""
        text_widget = self.upper_info["text"]
        text_widget.config(state=tk.NORMAL)
        text_widget.delete('1.0', tk.END)  # 清空原有内容
        for formula in self.formula_bus:
            text_widget.insert(tk.END, f"{formula}\n")
        self.selected_bus_indices = set()
        self.selection_anchor = None
        text_widget.tag_remove("selected_line", "1.0", tk.END)
        text_widget.config(state=tk.DISABLED)

    def _on_add_formula(self, event):
        formulas = event.data
        if isinstance(formulas, str):
            formulas = [formulas]

        added = []
        for formula_str in formulas:
            if formula_str and formula_str not in self.formula_bus:
                self.formula_bus.append(formula_str)
                added.append(formula_str)

        if added:
            logging.info(f"添加 {', '.join(added)} 到分子式bus")
            self._update_formula_display()  # 列表更新后刷新显示
        else:
            logging.warning(f"添加失败，分子式已存在或无效：{formulas}")

    def _delete_selected_text(self):
        if not self.selected_bus_indices:
            messagebox.showwarning("删除失败", "请先选中要删除的分子式")
            return

        selected_formulas = [self.formula_bus[i] for i in sorted(self.selected_bus_indices)]
        answer = messagebox.askyesno(
            "确认删除",
            f"是否删除选中的分子式？\n\n{chr(10).join(selected_formulas)}"
        )
        if not answer:
            return

        for index in sorted(self.selected_bus_indices, reverse=True):
            del self.formula_bus[index]

        self.selected_bus_indices = set()
        self.selection_anchor = None
        self._update_formula_display()
        logging.info(f"删除以下分子：\n{chr(10).join(selected_formulas)}")

    def _send_selected_to_search(self):
        if not self.selected_bus_indices:
            messagebox.showwarning("发送失败", "请先选中要发送的分子式")
            return

        selected_indices = sorted(self.selected_bus_indices)
        selected_formulas = [self.formula_bus[i] for i in selected_indices]
        self.event_mgr.publish(EventType.ADD_WAITING_FORMULA, data=selected_formulas, priority=EventPriority.NORMAL)

        for index in sorted(selected_indices, reverse=True):
            del self.formula_bus[index]

        self.selected_bus_indices = set()
        self.selection_anchor = None
        self._update_formula_display()

        logging.info(f"发送到待搜索分子式：{', '.join(selected_formulas)}")
        messagebox.showinfo("发送成功", f"已发送 {len(selected_formulas)} 个分子式到待搜索队列")

    def _init_logger(self):
        """配置日志 UI 组件"""
        scrollable_text = self.widget_factory.create_scrollable_text(
            self.lower_frame,
            **AppUIConfig.InteractiveZone.LoggerZone.text
        )
        self.log_text = scrollable_text["text"]
        # 将日志文本框关联到已存在的 Logger 实例
        self.logger.set_text_widget(self.log_text)
        event_handler = EventLogHandler(self.event_mgr)
        logging.getLogger().addHandler(event_handler)

        scrollable_text["scrollbar"].pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

    def _setup_layout(self):
        self.nav_frame.pack(
            side=tk.TOP,
            fill=tk.X,
            padx=BaseConfig.PADDING_C,
            pady=(BaseConfig.PADDING_B, 0)
        )
        self.status_frame.pack(
            side=tk.BOTTOM,
            fill=tk.X,
            padx=BaseConfig.PADDING_C,
            pady=(0, BaseConfig.PADDING_B)
        )
        # 先为状态栏预留高度，避免被中间可伸缩区域挤压
        self.status_frame.configure(height=28)
        self.status_frame.pack_propagate(False)
        self.mid_frame.pack(
            side=tk.TOP,
            fill=tk.BOTH,
            expand=True,
            padx=BaseConfig.PADDING_C,
            pady=BaseConfig.PADDING_B,
        )
        # 导航栏布局
        self.nav_bar.pack(
            side=tk.TOP,
            fill=tk.X,
        )
        # 状态栏布局
        self.status_bar.pack(
            side=tk.LEFT,
            fill=tk.BOTH,
            expand=True,
        )
        self.main_paned.pack(fill=tk.BOTH, expand=True, pady=BaseConfig.PADDING_A)
        self.main_paned.add(self.left_frame, minsize=420, stretch="always")
        self.main_paned.add(self.right_frame, minsize=240, stretch="always")

        self.right_paned.pack(fill=tk.BOTH, expand=True)
        self.right_paned.add(self.upper_frame, minsize=120, stretch="always")
        self.right_paned.add(self.lower_frame, minsize=120, stretch="always")

        self.mid_frame.bind("<Configure>", self._on_mid_frame_resize)
        self.right_frame.bind("<Configure>", self._on_right_frame_resize)
        self.main_paned.bind("<ButtonRelease-1>", self._on_main_paned_release)
        self.right_paned.bind("<ButtonRelease-1>", self._on_right_paned_release)

        # 首次渲染后立即应用比例，避免初始等分导致右侧过宽
        self.after_idle(self._apply_mid_ratio)
        self.after_idle(self._apply_right_ratio)
        # 二次校准，兼容不同设备上的延迟几何计算
        self.after(100, self._apply_mid_ratio)
        self.after(100, self._apply_right_ratio)

    def _on_mid_frame_resize(self, _event=None):
        self.after_idle(self._apply_mid_ratio)

    def _on_right_frame_resize(self, _event=None):
        self.after_idle(self._apply_right_ratio)

    def _on_main_paned_release(self, _event=None):
        self.after_idle(self._apply_mid_ratio)

    def _on_right_paned_release(self, _event=None):
        self.after_idle(self._apply_right_ratio)

    def _apply_mid_ratio(self):
        try:
            total_width = self.main_paned.winfo_width()
            left_ratio, right_ratio = self._mid_ratio
            total_ratio = left_ratio + right_ratio
            if total_width <= 1 or total_ratio <= 0:
                return
            sash_x = int(total_width * left_ratio / total_ratio)
            self.main_paned.sash_place(0, sash_x, 0)
        except (tk.TclError, AttributeError):
            return

    def _apply_right_ratio(self):
        try:
            total_height = self.right_paned.winfo_height()
            upper_ratio, lower_ratio = self._right_ratio
            total_ratio = upper_ratio + lower_ratio
            if total_height <= 1 or total_ratio <= 0:
                return
            sash_y = int(total_height * upper_ratio / total_ratio)
            self.right_paned.sash_place(0, 0, sash_y)
        except (tk.TclError, AttributeError):
            return

    def _init_event_handlers(self):
        self.event_mgr.subscribe(
            EventType.ADD_FORMULA,
            self._on_add_formula,
            priority=EventPriority.NORMAL
        )
        self.event_mgr.subscribe(
            EventType.STATUS_UPDATE,
            self._on_status_update,
            priority=EventPriority.NORMAL
        )

    def _on_status_update(self, event):
        data = event.data if isinstance(event.data, dict) else {}
        self.current_status_text = data.get("status_text", "") or ""

    def _on_close_request(self):
        status_text = str(getattr(self, "current_status_text", "")).strip().lower()
        is_running = status_text.startswith("running")
        if is_running:
            should_close = messagebox.askyesno(
                "确认退出",
                "当前任务仍在运行中，直接关闭可能中断处理。\n\n确认仍要退出吗？"
            )
            if not should_close:
                return
        self.destroy()

    def _setup_initial_page(self):
        initial_page = self.page_factory.get_page('Blank_Page')
        self.show_page(initial_page)

    def show_page(self, page):
        if page is None or page == self.current_page:
            return

        page.update_idletasks()
        if self.current_page:
            self.current_page.pack_forget()
        page.pack(
            fill=tk.BOTH,
            expand=True,
            **AppUIConfig.FunctionZone.padding
        )
        self.current_page = page
        self.update_idletasks()

if __name__ == '__main__':
    app = APP()
    app.mainloop()