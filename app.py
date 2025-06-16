import sys
import csv
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QLabel, QComboBox, QPushButton,
                             QFileDialog, QMessageBox, QSlider)
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QFont, QCursor
import networkx as nx
import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.patches import Circle, FancyArrowPatch
from matplotlib.lines import Line2D


class InteractiveGraph(FigureCanvas):
    def __init__(self, parent=None):
        plt.style.use('dark_background')
        self.fig, self.ax = plt.subplots(figsize=(10, 8))
        super().__init__(self.fig)
        self.setParent(parent)

        self.graph = nx.DiGraph()
        self.pos = {}
        self.selected_node = None
        self.dragging = False
        self.hovered_node = None
        self.node_labels = {}
        self.zoom_level = 1.0 # this will now be a relative zoom level (1.0 is default)
        self.pan_start = None
        self.pan_origin = None

        # store Matplotlib artists for efficient updates
        self.node_artists = {} # {node: circle_patch}
        self.edge_artists = {} # {edge: arrow_patch}
        self.text_artists = {} # {node: text_artist}
        self.info_text_artist = None
        self.hover_text_artist = None

        self.mpl_connect('button_press_event', self.on_press)
        self.mpl_connect('button_release_event', self.on_release)
        self.mpl_connect('motion_notify_event', self.on_motion)
        self.mpl_connect('scroll_event', self.on_scroll)

        self.ax.set_facecolor('black')
        self.fig.set_facecolor('black')
        self.ax.axis('off') # ensure axes are off initially
        self.draw_idle()

    def load_graph_from_csv(self, filename):
        self.graph.clear()
        self.pos = {}
        self.node_labels = {}
        # clear existing artists when loading a new graph
        self.clear_artists()

        try:
            with open(filename, 'r', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile) #csv.reader (fuck DictReader)
                header = next(reader, None)
                
                if not header or len(header) < 2:
                    raise ValueError("CSV file must have at least two columns.")
                
                for row in reader:
                    if len(row) < 2:
                        continue

                    node_a = row[0].strip()
                    node_b = row[1].strip()
                    
                    if not node_a or not node_b:
                        continue

                    self.graph.add_edge(node_a, node_b)
                    self.node_labels[node_a] = node_a
                    self.node_labels[node_b] = node_b

            if not self.graph.nodes:
                raise ValueError("No valid edges found in the CSV file.")

            self.apply_layout("spring")
            self.auto_scale()
            self.create_artists() # create artists for the first time
            self.update_artists() # update their positions and properties
            self.draw() # initial draw
            return True
        except Exception as e:
            print(f"Error loading graph: {e}")
            QMessageBox.warning(self.parent(), "Error",
                                  f"Failed to load graph: {e}\n"
                                  "Please check:\n"
                                  "1. File is valid CSV format with at least two columns.\n"
                                  "2. File encoding is UTF-8.")
            return False

    def clear_artists(self):
        # remove all existing artists from the axis
        self.ax.clear()
        self.node_artists.clear()
        self.edge_artists.clear()
        self.text_artists.clear()
        self.info_text_artist = None
        self.hover_text_artist = None
        self.ax.axis('off') # re-ensure axes are off after clearing

    def apply_layout(self, layout_type):
        if not self.graph.nodes:
            return
        
        if layout_type == "spring":
            self.pos = nx.spring_layout(self.graph, k=0.5, iterations=100)
        elif layout_type == "circular":
            self.pos = nx.circular_layout(self.graph)
        elif layout_type == "random":
            self.pos = nx.random_layout(self.graph)
        elif layout_type == "kamada_kawai":
            self.pos = nx.kamada_kawai_layout(self.graph)
        elif layout_type == "spectral":
            self.pos = nx.spectral_layout(self.graph)
        
        self.clear_artists() # clear old artists as positions are new
        self.auto_scale() # set new default view limits
        self.create_artists() # create new artists for the new layout
        self.update_artists()
        self.draw()


    def auto_scale(self):
        if not self.pos:
            return

        all_x = [pos[0] for pos in self.pos.values()]
        all_y = [pos[1] for pos in self.pos.values()]

        if not all_x or not all_y: # handle case of graph with no nodes
            return

        x_min, x_max = min(all_x), max(all_x)
        y_min, y_max = min(all_y), max(all_y)

        #ensure there's a range for padding, even with single node or line graph
        x_range = x_max - x_min
        y_range = y_max - y_min

        x_padding = max(0.2, x_range * 0.3) if x_range > 0 else 0.5
        y_padding = max(0.2, y_range * 0.3) if y_range > 0 else 0.5

        self.ax.set_xlim(x_min - x_padding, x_max + x_padding)
        self.ax.set_ylim(y_min - y_padding, y_max + y_padding)
        self.zoom_level = 1.0 #reset internal zoom level on auto-scale
        self.ax.axis('off') #ensure axes are off after setting limits
        self.update_artists() #update positions based on new limits
        self.draw() #redraw the canvas

    def create_artists(self):
        """Creates Matplotlib artists for nodes, edges, and labels."""
        #ensure axis is off before creating artists
        self.ax.axis('off')

        #edges
        for edge in self.graph.edges():
            arrow = FancyArrowPatch((0,0), (0,0), #dummy coordinates, will be updated
                                    arrowstyle='-|>',
                                    mutation_scale=15,
                                    color='white',
                                    alpha=0.8,
                                    zorder=1)
            self.ax.add_patch(arrow)
            self.edge_artists[edge] = arrow

        #nodes
        for node in self.graph.nodes():
            circle = Circle((0,0), 1, # dummy coordinates and radius
                           facecolor='#888888', edgecolor='white',
                           linewidth=1, alpha=0.9, zorder=2)
            self.ax.add_patch(circle)
            self.node_artists[node] = circle

            text = self.ax.text(0, 0, self.node_labels[node],
                              ha='center', va='center',
                              fontsize=10, color='black',
                              fontweight='bold', zorder=3)
            self.text_artists[node] = text

        #info text
        self.info_text_artist = self.ax.text(0.01, 0.99, "",
                                    transform=self.ax.transAxes,
                                    ha='left', va='top', fontsize=10, color='white',
                                    bbox=dict(facecolor='black', alpha=0.7, edgecolor='white'))
        
        self.hover_text_artist = self.ax.text(0.01, 0.95, "",
                                    transform=self.ax.transAxes,
                                    ha='left', va='top', fontsize=10, color='white',
                                    bbox=dict(facecolor='black', alpha=0.7, edgecolor='white'))

    def update_artists(self, changed_node=None):
        """
        Updates positions and properties of existing Matplotlib artists.
        If changed_node is specified, only that node and its incident edges are updated.
        """
        if not self.graph.nodes:
            self.ax.text(0.5, 0.5, "No graph loaded",
                        ha='center', va='center', fontsize=12, color='white')
            #ensure the axis is off even with no graph
            self.ax.axis('off')
            self.draw()
            return
            
        #determine node size based on current view limits for consistent visual size
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()
        
        #ensure that the view is valid before calculating node_radius
        if (xlim[1] - xlim[0]) == 0 or (ylim[1] - ylim[0]) == 0:
            #fallback for degenerate view, use a default radius or return
            node_radius_in_data_units = 0.05 # A reasonable default for many layouts
        else:
            fig_width_inches, fig_height_inches = self.fig.get_size_inches()
            dpi = self.fig.dpi
            
            #convert 15 pixels to inches, then to data units
            #ratio of data units per inch (x-axis)
            data_units_per_inch_x = (xlim[1] - xlim[0]) / fig_width_inches
            data_units_per_inch_y = (ylim[1] - ylim[0]) / fig_height_inches
            
            #use average for radius, or pick one axis
            node_radius_in_data_units = 15.0 / dpi * ((data_units_per_inch_x + data_units_per_inch_y) / 2)


        nodes_to_update = [changed_node] if changed_node else self.graph.nodes()
        edges_to_update = set()

        if changed_node:
            edges_to_update.update(self.graph.in_edges(changed_node))
            edges_to_update.update(self.graph.out_edges(changed_node))
        else:
            edges_to_update.update(self.graph.edges())


        #update edges
        for edge in edges_to_update:
            if edge in self.edge_artists:
                x1, y1 = self.pos.get(edge[0], (0,0)) #use .get with default to handle missing nodes gracefully
                x2, y2 = self.pos.get(edge[1], (0,0))
                self.edge_artists[edge].set_positions((x1, y1), (x2, y2))
                
        #update nodes and texts
        for node in nodes_to_update:
            if node in self.node_artists:
                x, y = self.pos.get(node, (0,0)) #use .get with default
                self.node_artists[node].set_center((x, y))
                self.node_artists[node].set_radius(node_radius_in_data_units) #update radius

                color = '#888888'
                if node == self.selected_node:
                    color = '#aaaaaa'
                elif node == self.hovered_node:
                    color = '#cccccc'
                self.node_artists[node].set_facecolor(color)

                self.text_artists[node].set_position((x, y))
                self.text_artists[node].set_text(self.node_labels.get(node, str(node))) #use .get for labels


        #update info text
        if self.info_text_artist:
            info_text = f"Nodes: {len(self.graph.nodes)} | Edges: {len(self.graph.edges)}"
            self.info_text_artist.set_text(info_text)

        #update hover text
        if self.hover_text_artist:
            if self.hovered_node:
                self.hover_text_artist.set_text(f"Hovered: {self.hovered_node}")
                self.hover_text_artist.set_visible(True)
            else:
                self.hover_text_artist.set_visible(False) #hide if no node hovered

        self.ax.axis('off') #always ensure axes are off after updates
        self.fig.canvas.draw_idle() #use draw_idle for efficiency

    def get_node_at_position(self, pos):
        if not pos[0] or not pos[1]:
            return None

        x, y = pos
        
        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()
        
        if (xlim[1] - xlim[0]) == 0 or (ylim[1] - ylim[0]) == 0:
            return None

        fig_width_inches, fig_height_inches = self.fig.get_size_inches()
        dpi = self.fig.dpi
        data_units_per_inch_x = (xlim[1] - xlim[0]) / fig_width_inches
        data_units_per_inch_y = (ylim[1] - ylim[0]) / fig_height_inches
        node_radius_in_data_units = 15.0 / dpi * ((data_units_per_inch_x + data_units_per_inch_y) / 2)


        for node, (nx_pos, ny_pos) in self.pos.items():
            if ((nx_pos - x)**2 + (ny_pos - y)**2) <= node_radius_in_data_units**2:
                return node
        return None

    def on_press(self, event):
        if event.inaxes != self.ax:
            return

        if event.button == 1:
            node = self.get_node_at_position((event.xdata, event.ydata))
            if node:
                self.selected_node = node
                self.dragging = True
                self.update_artists()
                self.fig.canvas.draw_idle()
            else:
                
                self.pan_start = QPoint(event.x, event.y)
                self.pan_origin = (self.ax.get_xlim(), self.ax.get_ylim())
                self.setCursor(QCursor(Qt.ClosedHandCursor))

    def on_release(self, event):
        if event.button == 1:
            self.dragging = False
            self.selected_node = None
            self.pan_start = None
            self.pan_origin = None
            self.setCursor(QCursor(Qt.ArrowCursor))
            self.update_artists() #reset selected node color
            self.fig.canvas.draw_idle()

    def on_motion(self, event):
        if event.inaxes != self.ax:
            if self.hovered_node:
                self.hovered_node = None
                self.update_artists()
                self.fig.canvas.draw_idle()
            return

        #pan
        if self.pan_start and event.button == 1:
            if event.xdata is None or event.ydata is None: return #ensure valid data coordinates

            #convert pixel motion to data units
            dx_pixels = event.x - self.pan_start.x()
            dy_pixels = event.y - self.pan_start.y() #Y-axis inverted for PyQt vs Matplotlib

            #get current axis limits
            xlim_current = self.ax.get_xlim()
            ylim_current = self.ax.get_ylim()

            #calculate data units per pixel
            fig_width_inches, fig_height_inches = self.fig.get_size_inches()
            dpi = self.fig.dpi

            #check for non-zero dimensions to prevent division by zero
            if fig_width_inches == 0 or fig_height_inches == 0: return

            x_data_per_pixel = (xlim_current[1] - xlim_current[0]) / (fig_width_inches * dpi)
            y_data_per_pixel = (ylim_current[1] - ylim_current[0]) / (fig_height_inches * dpi)

            #calculate movement in data units
            dx_data = dx_pixels * x_data_per_pixel
            dy_data = dy_pixels * y_data_per_pixel

            #apply pan relative to original pan origin
            new_xlim = (self.pan_origin[0][0] - dx_data, self.pan_origin[0][1] - dx_data)
            new_ylim = (self.pan_origin[1][0] + dy_data, self.pan_origin[1][1] + dy_data) #plus for y-axis due to inversion

            self.ax.set_xlim(new_xlim)
            self.ax.set_ylim(new_ylim)
            self.fig.canvas.draw_idle() #use draw_idle for pan
            return

        #update hovered node
        node = self.get_node_at_position((event.xdata, event.ydata))
        if node != self.hovered_node:
            self.hovered_node = node
            self.update_artists()
            self.fig.canvas.draw_idle()

        #drag node
        if self.dragging and self.selected_node and event.xdata is not None and event.ydata is not None:
            self.pos[self.selected_node] = (event.xdata, event.ydata)
            self.update_artists(changed_node=self.selected_node) #only update the dragged node and its edges
            self.fig.canvas.draw_idle() #use draw_idle for continuous dragging


    def on_scroll(self, event):
        if event.inaxes != self.ax:
            return

        zoom_factor_scroll = 1.25 if event.button == 'up' else 0.8 #more aggressive zoom for scroll
        self.zoom_level *= zoom_factor_scroll #update the overall zoom level

        xlim = self.ax.get_xlim()
        ylim = self.ax.get_ylim()

        mouse_x = event.xdata if event.xdata else (xlim[0] + xlim[1]) / 2
        mouse_y = event.ydata if event.ydata else (ylim[0] + ylim[1]) / 2

        new_width = (xlim[1] - xlim[0]) / zoom_factor_scroll
        new_height = (ylim[1] - ylim[0]) / zoom_factor_scroll

        #apply zoom while keeping mouse pointer at the same data coordinate
        self.ax.set_xlim(mouse_x - new_width/2, mouse_x + new_width/2)
        self.ax.set_ylim(mouse_y - new_height/2, mouse_y + new_height/2)
        self.update_artists() #update radii based on new limits
        self.fig.canvas.draw_idle()


class GraphViewer(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Interactive Graph Viewer (Dark Theme)")
        self.setGeometry(100, 100, 1000, 800)

        self.setStyleSheet("""
            QMainWindow {
                background-color: #222222;
            }
            QLabel, QPushButton, QSlider {
                color: #dddddd;
            }
            QPushButton {
                background-color: #444444;
                border: 1px solid #666666;
                padding: 5px;
            }
            QPushButton:hover {
                background-color: #555555;
            }
            QComboBox {
                background-color: #333333;
                border: 1px solid #666666;
                padding: 2px;
                color: #dddddd; /* Text color for QComboBox */
            }
            QComboBox::drop-down {
                border: 0px; /* Remove the dropdown arrow border */
            }
            QComboBox::down-arrow {
                image: url(data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAABAAAAAQCAYAAAAf8/9hAAAAGXRFWHRTb2Z0d2FyZQBBZG9iZSBJbWFnZVJlYWR5ccllPAAAAyRpVFh0WE1MOmNvbS5hZG9iZS54bXAAAAAAADw/eHBhY2tldCBiZWdpbj0i77u/IiBpZD0iV0FNWmRlZmcxMjAyMCI+IDx4OnhtcG1ldGEgeG1sbnM6eD0iYWRvYmU6bnM6bWV0YS8iIHg6eG1wdGs9IkFkb2JlIFhNUCBDb3JlIDUuNi1jMTQ1IDc5LjE2MzY4NywgMjAxOC8wOC8xMy0xNjowOToyMiAgICAgICAgIj4gPHJkZjpSREYgeG1sbnM6cmRmPSJodHRwOi8vd3d3LnczLm9yZy8xOTk5LzAyLzIyLXJkZi1zeW50YXgtbnMjIj4gPHJkZjpEZXNjcmlwdGlvbiByZGY6YWJvdXQ9IiIgxmlnsOnhtcE1NPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvbW0vIiB4bWxuczpzdFJlZj0iaHR0cDovL25zLmFkb2JlLmNvbS94YXAvMS4wL3NUeXBlL1Jlc291cmNlUmVmIyIgeG1sbnM6eG1wPSJodHRwOi8vbnMuYWRvYmUuY29tL3hhcC8xLjAvIj4gPHhtcE1NOkRvY3VtZW50SUQ+eG1wLmRpZDozOEQ5NThCRkY0Q0IxMUVBQUQ3NUI4MDk5MDdEMjZFNTwvL3htcE1NOkRvY3VtZW50SUQ+IDx4bXBNTTpJbnN0YW5jZUlEPnhtcC5paWQ6MzhEOTU4QkU0NENCMTFFQUFENzVCODA5OTA3RDI2RTU8L2xldm1uOmNvb3JkaW5hdGU+IDx4bXBNTTpPcmlnaW5hbERvY3VtZW50SUQ+eG1wLmRpZDozOEQ5NThCRUY0Q0IxMUVBQUQ3NUI4MDk5MDdEMjZFNTwvL3htcE1NOk9yaWdpbmFsRDoKPC9yZGY6UmRGPjAsIC8+8Fh+UaAAAAXUlEQVR42mL8//8/AzWAiYFggJqB+kYGYoYxIMtBGAW0jFjGQBYyA8NogWAG4P9/fwxigFgCyAFY+g0SjAwgywdiWjQOIFWcAUlDAmSGkI0DNgAAAgwAWX8x000jJ/cAAAAASUVORK5CYII=); /* Example: a darker arrow icon */
            }
            QComboBox QAbstractItemView {
                background-color: #333333; /* Background for the dropdown list */
                color: #dddddd; /* Text color for items in the dropdown list */
                selection-background-color: #555555;
            }
            QSlider::groove:horizontal {
                background: #444444;
                height: 8px;
            }
            QSlider::handle:horizontal {
                background: #888888;
                width: 12px;
                margin: -4px 0;
            }
        """)

        self.init_ui()

    def init_ui(self):
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        layout = QVBoxLayout(main_widget)

        #control panel
        control_panel = QWidget()
        control_layout = QHBoxLayout(control_panel)

        self.file_label = QLabel("No file selected")
        self.file_label.setMinimumWidth(200)
        control_layout.addWidget(self.file_label)

        browse_btn = QPushButton("Open CSV")
        browse_btn.clicked.connect(self.browse_file)
        control_layout.addWidget(browse_btn)

        control_layout.addWidget(QLabel("Layout:"))
        self.layout_combo = QComboBox()
        self.layout_combo.addItems(["spring", "circular", "random", "kamada_kawai", "spectral"])
        #set a light gray color for the text within the QComboBox itself for dark theme consistency
        self.layout_combo.setStyleSheet("QComboBox { color: #dddddd; }")

        control_layout.addWidget(self.layout_combo)

        apply_layout_btn = QPushButton("Apply Layout")
        apply_layout_btn.clicked.connect(self.apply_layout)
        control_layout.addWidget(apply_layout_btn)

        control_layout.addWidget(QLabel("Zoom:"))
        self.zoom_slider = QSlider(Qt.Horizontal)
        self.zoom_slider.setRange(10, 200) # 10 (zoomed out) to 200 (zoomed in)
        self.zoom_slider.setValue(100) # Default zoom
        self.zoom_slider.valueChanged.connect(self.adjust_zoom)
        control_layout.addWidget(self.zoom_slider)

        reset_zoom_btn = QPushButton("Reset View")
        reset_zoom_btn.clicked.connect(self.reset_view)
        control_layout.addWidget(reset_zoom_btn)

        layout.addWidget(control_panel)

        self.graph_canvas = InteractiveGraph(self)
        layout.addWidget(self.graph_canvas)

        self.status_bar = self.statusBar()
        self.status_bar.showMessage("Ready")

    def browse_file(self):
        options = QFileDialog.Options()
        file_name, _ = QFileDialog.getOpenFileName(
            self, "Open CSV File", "", "CSV Files (*.csv)", options=options)

        if file_name:
            self.file_label.setText(file_name.split('/')[-1])
            if self.graph_canvas.load_graph_from_csv(file_name):
                self.status_bar.showMessage(
                    f"Loaded {len(self.graph_canvas.graph.nodes)} nodes and {len(self.graph_canvas.graph.edges)} edges")
            else:
                self.status_bar.showMessage("Failed to load graph")
                #error message is now handled in InteractiveGraph.load_graph_from_csv

    def apply_layout(self):
        layout_type = self.layout_combo.currentText()
        self.graph_canvas.apply_layout(layout_type)
        self.status_bar.showMessage(f"Applied {layout_type} layout")
        self.zoom_slider.setValue(100) #reset zoom slider after layout change

    def adjust_zoom(self, value):
        #calculate the new zoom factor based on slider value
        new_zoom_level = value / 100.0

        #get current center of the plot
        xlim = self.graph_canvas.ax.get_xlim()
        ylim = self.graph_canvas.ax.get_ylim()
        current_center_x = (xlim[0] + xlim[1]) / 2
        current_center_y = (ylim[0] + ylim[1]) / 2

        #get the "original" extent of the graph as determined by auto_scale
        if not self.graph_canvas.graph.nodes:
            return

        all_x = [pos[0] for pos in self.graph_canvas.pos.values()]
        all_y = [pos[1] for pos in self.graph_canvas.pos.values()]

        if not all_x or not all_y: #handle empty graph case
            return

        x_min, x_max = min(all_x), max(all_x)
        y_min, y_max = min(all_y), max(all_y)

        x_range = x_max - x_min
        y_range = y_max - y_min

        x_padding = max(0.2, x_range * 0.3) if x_range > 0 else 0.5
        y_padding = max(0.2, y_range * 0.3) if y_range > 0 else 0.5

        base_xlim = (x_min - x_padding, x_max + x_padding)
        base_ylim = (y_min - y_padding, y_max + y_padding)

        base_width = base_xlim[1] - base_xlim[0]
        base_height = base_ylim[1] - base_ylim[0]

        #calculate new width and height based on the new zoom level
        zoomed_width = base_width / new_zoom_level
        zoomed_height = base_height / new_zoom_level

        #set new limits, centered around the current center of the view
        self.graph_canvas.ax.set_xlim(current_center_x - zoomed_width / 2, current_center_x + zoomed_width / 2)
        self.graph_canvas.ax.set_ylim(current_center_y - zoomed_height / 2, current_center_y + zoomed_height / 2)

        self.graph_canvas.zoom_level = new_zoom_level

        self.graph_canvas.update_artists()
        self.graph_canvas.fig.canvas.draw_idle()


    def reset_view(self):
        self.graph_canvas.auto_scale()
        self.zoom_slider.setValue(100) #reset slider after auto_scale


def main():
    app = QApplication(sys.argv)
    app.setStyle('Fusion')

    font = QFont()
    font.setFamily("Arial")
    font.setPointSize(10)
    app.setFont(font)

    viewer = GraphViewer()
    viewer.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()