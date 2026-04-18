import multiprocessing

from package.gui.main_window import APP


def main():
    multiprocessing.freeze_support()
    app = APP()
    app.mainloop()


if __name__ == "__main__":
    main()