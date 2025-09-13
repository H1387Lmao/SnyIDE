import os
from PySide6.QtWidgets import QWidget, QTreeView, QVBoxLayout, QFileSystemModel
from PySide6.QtCore import QSortFilterProxyModel, QDir

class ProjectPathFilterProxy(QSortFilterProxyModel):
    def __init__(self, project_path, source_model):
        super().__init__()
        self.project_path = os.path.abspath(project_path)
        self._parent = os.path.dirname(project_path)
        self.source_model = source_model

    def filterAcceptsRow(self, source_row, source_parent):
        index = self.source_model.index(source_row, 0, source_parent)
        file_path = os.path.abspath(self.source_model.filePath(index))
        if file_path.startswith(self._parent):
                if file_path == self._parent:
                        return True
                if file_path.startswith(self.project_path):
                        return True
        return False

class FileExplorerTree(QTreeView):
    def __init__(self, project_path):
        super().__init__()
        project_path = os.path.abspath(os.path.expanduser(project_path))
        parent = os.path.dirname(project_path)
        if not os.path.isdir(project_path):
            raise ValueError(f"'{project_path}' is not a valid directory.")

        self.fs_model = QFileSystemModel()
        self.fs_model.setFilter(QDir.NoDotAndDotDot | QDir.AllDirs | QDir.Files)
        self.fs_model.setRootPath(project_path)

        self.proxy_model = ProjectPathFilterProxy(project_path, self.fs_model)
        self.proxy_model.setSourceModel(self.fs_model)

        self.setModel(self.proxy_model)

        source_index = self.fs_model.index(parent)
        proxy_root_index = self.proxy_model.mapFromSource(source_index)
        self.expand(self.proxy_model.mapFromSource(self.fs_model.index(project_path)))
        self.setRootIndex(proxy_root_index)

        for col in range(1, self.fs_model.columnCount()):
            self.hideColumn(col)
        self.header().hide()

if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = FileExplorerTree(".")
    window.setWindowTitle("Project Explorer")
    window.resize(600, 400)
    window.show()
    sys.exit(app.exec())

