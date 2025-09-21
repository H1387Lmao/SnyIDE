import os
import shutil
from PySide6.QtWidgets import QWidget, QTreeView, QVBoxLayout, QFileSystemModel, QFileIconProvider, QMenu, QInputDialog, QMessageBox, QAbstractItemView
from PySide6.QtCore import QSortFilterProxyModel, QDir, Qt, QPoint
from PySide6.QtGui import QIcon, QAction

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

class CustomIconProvider(QFileIconProvider):
    def __init__(self, base_dir):
        super().__init__()
        self.folder_icon = QIcon(os.path.join(base_dir, 'icons', 'folder.svg'))
        self.default_file_icon = QIcon(os.path.join(base_dir, 'icons', 'general_file.svg'))
        self.ext_icons = {
            'py': QIcon(os.path.join(base_dir, 'icons', 'extension_py.svg')),
            'txt': QIcon(os.path.join(base_dir, 'icons', 'general_file.svg'))
        }

    def icon(self, info):  # info is QFileInfo
        try:
            if info.isDir():
                return self.folder_icon
            ext = info.suffix().lower()
            return self.ext_icons.get(ext, self.default_file_icon)
        except Exception:
            return self.default_file_icon

class FileExplorerTree(QTreeView):
    def __init__(self, project_path):
        super().__init__()
        project_path = os.path.abspath(os.path.expanduser(project_path))
        if not os.path.isdir(project_path):
            raise ValueError(f"'{project_path}' is not a valid directory.")

        self.fs_model = QFileSystemModel()
        self.fs_model.setFilter(QDir.NoDotAndDotDot | QDir.AllDirs | QDir.Files)
        self.fs_model.setRootPath(project_path)
        self.fs_model.setReadOnly(False)
        # Custom icons
        base_dir = os.path.dirname(__file__)
        self.fs_model.setIconProvider(CustomIconProvider(base_dir))

        self.proxy_model = ProjectPathFilterProxy(project_path, self.fs_model)
        self.proxy_model.setSourceModel(self.fs_model)

        self.setModel(self.proxy_model)
        self._apply_root(project_path)

        self.setRootIsDecorated(True)
        for col in range(1, self.fs_model.columnCount()):
            self.hideColumn(col)
        self.header().hide()

        # UX: do not expand/collapse on double-click (use caret instead)
        self.setExpandsOnDoubleClick(False)
        # Do not start rename on double-click
        self.setEditTriggers(QAbstractItemView.NoEditTriggers)

        # Enable drag & drop move
        self.setSelectionMode(QAbstractItemView.SingleSelection)
        self.setDragEnabled(True)
        self.setAcceptDrops(True)
        self.setDropIndicatorShown(True)
        self.setDefaultDropAction(Qt.MoveAction)
        self.setDragDropMode(QAbstractItemView.DragDrop)

        # Context menu
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)
        self._context_target_dir = None

    def _apply_root(self, project_path):
        project_path = os.path.abspath(project_path)
        parent = os.path.dirname(project_path)
        source_parent_index = self.fs_model.index(parent)
        proxy_root_index = self.proxy_model.mapFromSource(source_parent_index)
        self.setRootIndex(proxy_root_index)
        # Expand the project root
        self.expand(self.proxy_model.mapFromSource(self.fs_model.index(project_path)))

    def set_project_path(self, project_path):
        project_path = os.path.abspath(os.path.expanduser(project_path))
        if not os.path.isdir(project_path):
            return
        self.fs_model.setRootPath(project_path)
        self.proxy_model.project_path = project_path
        self.proxy_model._parent = os.path.dirname(project_path)
        self._apply_root(project_path)

    # ---------- Context menu actions ----------
    def _selected_source_index(self):
        idx = self.currentIndex()
        if not idx.isValid():
            return None
        return self.proxy_model.mapToSource(idx)

    def _index_dir_path(self, source_index):
        if source_index is None:
            return self.fs_model.rootPath()
        path = self.fs_model.filePath(source_index)
        return path if os.path.isdir(path) else os.path.dirname(path)

    def _show_context_menu(self, pos: QPoint):
        index = self.indexAt(pos)
        # Determine target dir for New File/Folder
        if index.isValid():
            src_index = self.proxy_model.mapToSource(index)
            self._context_target_dir = self._index_dir_path(src_index)
        else:
            # Right-clicked empty space: use root
            self._context_target_dir = self.fs_model.rootPath()

        menu = QMenu(self)
        act_new_file = QAction("New File", self)
        act_new_folder = QAction("New Folder", self)
        act_rename = QAction("Rename", self)
        act_delete = QAction("Delete", self)
        act_new_file.triggered.connect(self._action_new_file)
        act_new_folder.triggered.connect(self._action_new_folder)
        act_rename.triggered.connect(self._action_rename)
        act_delete.triggered.connect(self._action_delete)
        menu.addAction(act_new_file)
        menu.addAction(act_new_folder)
        if index.isValid():
            menu.addSeparator()
            menu.addAction(act_rename)
            menu.addAction(act_delete)
        menu.exec(self.viewport().mapToGlobal(pos))

    def _action_new_file(self):
        # Prefer context-target dir if set by the last right-click
        dir_path = self._context_target_dir or self._index_dir_path(self._selected_source_index())
        name, ok = QInputDialog.getText(self, "New File", "File name:")
        if not ok or not name.strip():
            return
        target = os.path.join(dir_path, name.strip())
        if os.path.exists(target):
            QMessageBox.warning(self, "New File", "A file or folder with that name already exists.")
            return
        try:
            open(target, 'w', encoding='utf-8').close()
        except Exception as e:
            QMessageBox.critical(self, "New File", f"Failed to create file:\n{e}")

    def _action_new_folder(self):
        dir_path = self._context_target_dir or self._index_dir_path(self._selected_source_index())
        name, ok = QInputDialog.getText(self, "New Folder", "Folder name:")
        if not ok or not name.strip():
            return
        target = os.path.join(dir_path, name.strip())
        if os.path.exists(target):
            QMessageBox.warning(self, "New Folder", "A file or folder with that name already exists.")
            return
        try:
            os.makedirs(target, exist_ok=False)
        except Exception as e:
            QMessageBox.critical(self, "New Folder", f"Failed to create folder:\n{e}")

    def _action_rename(self):
        src_index = self._selected_source_index()
        if not src_index or not src_index.isValid():
            return
        proxy_index = self.proxy_model.mapFromSource(src_index)
        self.edit(proxy_index)

    def _action_delete(self):
        src_index = self._selected_source_index()
        if not src_index or not src_index.isValid():
            return
        path = self.fs_model.filePath(src_index)
        name = os.path.basename(path)
        if QMessageBox.question(self, "Delete", f"Are you sure you want to delete '\n{name}\n'? This cannot be undone.") != QMessageBox.Yes:
            return
        try:
            if os.path.isdir(path):
                shutil.rmtree(path)
            else:
                os.remove(path)
        except Exception as e:
            QMessageBox.critical(self, "Delete", f"Failed to delete:\n{e}")

if __name__ == "__main__":
    import sys
    from PySide6.QtWidgets import QApplication

    app = QApplication(sys.argv)
    window = FileExplorerTree(".")
    window.setWindowTitle("Project Explorer")
    window.resize(600, 400)
    window.show()
    sys.exit(app.exec())

