# graph_canvas.py

import csv
import networkx as nx
import matplotlib.pyplot as plt
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QCursor
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.patches import Circle, FancyArrowPatch


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
        self.zoom_level = 1.0
        self.pan_start = None
        self.pan_origin = None

        self.node_artists = {}
        self.edge_artists = {}
        self.text_artists = {}
        self.info_text_artist = None
        self.hover_text_artist = None

        self.mpl_connect('button_press_event', self.on_press)
        self.mpl_connect('button_release_event', self.on_release)
        self.mpl_connect('motion_notify_event', self.on_motion)
        self.mpl_connect('scroll_event', self.on_scroll)

        self.ax.set_facecolor('black')
        self.fig.set_facecolor('black')
        self.ax.axis('off')
        self.draw_idle()

    def load_graph_from_csv(self, filename):
        self.graph.clear()
        self.pos = {}
        self.node_labels = {}
        self.clear_artists()

        try:
            with open(filename, 'r', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
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
            self.create_artists()
            self.update_artists()
            self.draw()
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
        self.ax.clear()
        self.node_artists.clear()
        self.edge_artists.clear()
        self.text_artists.clear()
        self.info_text_artist = None
        self.hover_text_artist = None
        self.ax.axis('off')

    def apply_layout(self, layout_type):
        if not self.graph.nodes:
            return
        
        layouts = {
            "spring": nx.spring_layout(self.graph, k=0.5, iterations=100),
            "circular": nx.circular_layout(self.graph),
            "random": nx.random_layout(self.graph),
            "kamada_kawai": nx.kamada_kawai_layout(self.graph),
            "spectral": nx.spectral_layout(self.graph)
        }
        self.pos = layouts.get(layout_type, nx.spring_layout(self.graph))
        
        self.clear_artists()
        self.auto_scale()
        self.create_artists()
        self.update_artists()
        self.draw()

    def auto_scale(self):
        if not self.pos:
            return

        all_x = [pos[0] for pos in self.pos.values()]
        all_y = [pos[1] for pos in self.pos.values()]

        if not all_x or not all_y:
            return

        x_min, x_max = min(all_x), max(all_x)
        y_min, y_max = min(all_y), max(all_y)
        
        x_range = x_max - x_min
        y_range = y_max - y_min

        x_padding = max(0.2, x_range * 0.3) if x_range > 0 else 0.5
        y_padding = max(0.2, y_range * 0.3) if y_range > 0 else 0.5

        self.ax.set_xlim(x_min - x_padding, x_max + x_padding)
        self.ax.set_ylim(y_min - y_padding, y_max + y_padding)
        self.zoom_level = 1.0
        self.ax.axis('off')
        self.update_artists()
        self.draw()

    def create_artists(self):
        """Создаём графические элементы без текстовых меток"""
        for link_id in self.links:
            self._create_link_artist(link_id)

    def update_artists(self, changed_node=None):
        if not self.graph.nodes:
            self.ax.text(0.5, 0.5, "No graph loaded", ha='center', va='center', fontsize=12, color='white')
            self.ax.axis('off')
            self.draw()
            return

        xlim, ylim = self.ax.get_xlim(), self.ax.get_ylim()
        if (xlim[1] - xlim[0]) == 0 or (ylim[1] - ylim[0]) == 0:
            node_radius_in_data_units = 0.05
        else:
            fig_width_inches, fig_height_inches = self.fig.get_size_inches()
            dpi = self.fig.dpi
            data_units_per_inch_x = (xlim[1] - xlim[0]) / fig_width_inches
            data_units_per_inch_y = (ylim[1] - ylim[0]) / fig_height_inches
            node_radius_in_data_units = 15.0 / dpi * ((data_units_per_inch_x + data_units_per_inch_y) / 2)

        nodes_to_update = [changed_node] if changed_node else list(self.graph.nodes())
        edges_to_update = set()

        if changed_node:
            edges_to_update.update(self.graph.in_edges(changed_node))
            edges_to_update.update(self.graph.out_edges(changed_node))
        else:
            edges_to_update.update(self.graph.edges())

        for edge in edges_to_update:
            if edge in self.edge_artists:
                x1, y1 = self.pos.get(edge[0], (0,0))
                x2, y2 = self.pos.get(edge[1], (0,0))
                self.edge_artists[edge].set_positions((x1, y1), (x2, y2))
                
        for node in nodes_to_update:
            if node in self.node_artists:
                x, y = self.pos.get(node, (0,0))
                self.node_artists[node].set_center((x, y))
                self.node_artists[node].set_radius(node_radius_in_data_units)

                color = '#888888'
                if node == self.selected_node: color = '#aaaaaa'
                elif node == self.hovered_node: color = '#cccccc'
                self.node_artists[node].set_facecolor(color)

                self.text_artists[node].set_position((x, y))
                self.text_artists[node].set_text(self.node_labels.get(node, str(node)))

        if self.info_text_artist:
            self.info_text_artist.set_text(f"Nodes: {len(self.graph.nodes)} | Edges: {len(self.graph.edges)}")

        if self.hover_text_artist:
            if self.hovered_node:
                self.hover_text_artist.set_text(f"Hovered: {self.hovered_node}")
                self.hover_text_artist.set_visible(True)
            else:
                self.hover_text_artist.set_visible(False)

        self.ax.axis('off')
        self.fig.canvas.draw_idle()

    def get_node_at_position(self, pos):
        if not pos[0] or not pos[1]: return None
        x, y = pos
        xlim, ylim = self.ax.get_xlim(), self.ax.get_ylim()
        if (xlim[1] - xlim[0]) == 0 or (ylim[1] - ylim[0]) == 0: return None

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
        if event.inaxes != self.ax: return
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
            self.update_artists()
            self.fig.canvas.draw_idle()

    def on_motion(self, event):
        if event.inaxes != self.ax:
            if self.hovered_node:
                self.hovered_node = None
                self.update_artists()
                self.fig.canvas.draw_idle()
            return

        if self.pan_start and event.button == 1:
            if event.xdata is None or event.ydata is None: return
            dx_pixels, dy_pixels = event.x - self.pan_start.x(), event.y - self.pan_start.y()
            xlim_current, ylim_current = self.ax.get_xlim(), self.ax.get_ylim()
            fig_width_inches, fig_height_inches = self.fig.get_size_inches()
            dpi = self.fig.dpi
            if fig_width_inches == 0 or fig_height_inches == 0: return
            x_data_per_pixel = (xlim_current[1] - xlim_current[0]) / (fig_width_inches * dpi)
            y_data_per_pixel = (ylim_current[1] - ylim_current[0]) / (fig_height_inches * dpi)
            dx_data, dy_data = dx_pixels * x_data_per_pixel, dy_pixels * y_data_per_pixel
            new_xlim = (self.pan_origin[0][0] - dx_data, self.pan_origin[0][1] - dx_data)
            new_ylim = (self.pan_origin[1][0] + dy_data, self.pan_origin[1][1] + dy_data)
            self.ax.set_xlim(new_xlim)
            self.ax.set_ylim(new_ylim)
            self.fig.canvas.draw_idle()
            return

        node = self.get_node_at_position((event.xdata, event.ydata))
        if node != self.hovered_node:
            self.hovered_node = node
            self.update_artists()
            self.fig.canvas.draw_idle()

        if self.dragging and self.selected_node and event.xdata is not None and event.ydata is not None:
            self.pos[self.selected_node] = (event.xdata, event.ydata)
            self.update_artists(changed_node=self.selected_node)
            self.fig.canvas.draw_idle()

    def on_scroll(self, event):
        if event.inaxes != self.ax: return
        zoom_factor_scroll = 1.25 if event.button == 'up' else 0.8
        self.zoom_level *= zoom_factor_scroll
        xlim, ylim = self.ax.get_xlim(), self.ax.get_ylim()
        mouse_x = event.xdata if event.xdata else (xlim[0] + xlim[1]) / 2
        mouse_y = event.ydata if event.ydata else (ylim[0] + ylim[1]) / 2
        new_width = (xlim[1] - xlim[0]) / zoom_factor_scroll
        new_height = (ylim[1] - ylim[0]) / zoom_factor_scroll
        self.ax.set_xlim(mouse_x - new_width/2, mouse_x + new_width/2)
        self.ax.set_ylim(mouse_y - new_height/2, mouse_y + new_height/2)
        self.update_artists()
        self.fig.canvas.draw_idle()