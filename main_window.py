# main_window.py
from PyQt5.QtWidgets import (QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QLabel, QComboBox, QPushButton, QFileDialog, QSlider)
from PyQt5.QtCore import Qt
from links_canvas import InteractiveLinksCanvas

class LinksViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Interactive Links Viewer")
        self.setGeometry(100, 100, 1000, 800)

        self.setStyleSheet("""
            QMainWindow { background-color: #222222; }
            QLabel, QPushButton, QSlider { color: #dddddd; }
            QPushButton { background-color: #444444; border: 1px solid #666666; padding: 5px; }
            QPushButton:hover { background-color: #555555; }
            QComboBox { background-color: #333333; border: 1px solid #666666; padding: 2px; color: #dddddd; }
            QComboBox::drop-down { border: 0px; }
            QComboBox QAbstractItemView { background-color: #333333; color: #dddddd; selection-background-color: #555555; }
            QSlider::groove:horizontal { background: #444444; height: 8px; }
            QSlider::handle:horizontal { background: #888888; width: 12px; margin: -4px 0; }
        """)

        self.init_ui()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        control_panel = QWidget()
        control_layout = QHBoxLayout(control_panel)

        self.file_label = QLabel("No file selected")
        self.file_label.setMinimumWidth(200)
        control_layout.addWidget(self.file_label)

        browse_btn = QPushButton("Open Links CSV")
        browse_btn.clicked.connect(self.browse_file)
        control_layout.addWidget(browse_btn)

        control_layout.addWidget(QLabel("Layout:"))
        self.layout_combo = QComboBox()
        self.layout_combo.addItems(["spring", "circular", "random", "kamada_kawai", "spectral"])
        control_layout.addWidget(self.layout_combo)

        apply_layout_btn = QPushButton("Apply Layout")
        apply_layout_btn.clicked.connect(self.apply_layout)
        control_layout.addWidget(apply_layout_btn)

        control_layout.addWidget(QLabel("Zoom:"))
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(10, 200)
        self.zoom_slider.setValue(100)
        self.zoom_slider.valueChanged.connect(self.adjust_zoom)
        control_layout.addWidget(self.zoom_slider)

        reset_zoom_btn = QPushButton("Reset View")
        reset_zoom_btn.clicked.connect(self.reset_view)
        control_layout.addWidget(reset_zoom_btn)

        layout.addWidget(control_panel)

        self.links_canvas = InteractiveLinksCanvas(self)
        layout.addWidget(self.links_canvas)

        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")

    def browse_file(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Open Links CSV File", "", 
            "CSV Files (*.csv)", options=options)
        
        if file_name:
            self.file_label.setText(file_name.split('/')[-1])
            if self.links_canvas.load_links_from_csv(file_name):
                stats = self.links_canvas.get_stats()
                self.status_bar.showMessage(
                    f"Loaded {stats['links']} links ({stats['self_links']} self-links)")
            else:
                self.status_bar.showMessage("Failed to load links")

    def apply_layout(self):
        layout_type = self.layout_combo.currentText()
        self.links_canvas.apply_layout(layout_type)
        self.status_bar.showMessage(f"Applied {layout_type} layout")
        self.zoom_slider.setValue(100)

    def adjust_zoom(self, value):
        self.links_canvas.set_zoom(value / 100.0)

    def reset_view(self):
        self.links_canvas.reset_view()
        self.zoom_slider.setValue(100)