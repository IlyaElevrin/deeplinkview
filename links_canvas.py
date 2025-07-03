# links_canvas.py
import csv
import networkx as nx
import matplotlib.pyplot as plt
import numpy as np
from PyQt5.QtWidgets import QMessageBox
from PyQt5.QtCore import Qt, QPoint
from PyQt5.QtGui import QCursor
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.patches import Circle, FancyArrowPatch

class InteractiveLinksCanvas(FigureCanvas):
    def __init__(self, parent=None):
        plt.style.use('dark_background')
        self.fig, self.ax = plt.subplots(figsize=(10, 8))
        super().__init__(self.fig)
        self.setParent(parent)

        #links data
        self.links = {}  # {id: {'from': x, 'to': y}}
        self.link_positions = {}
        
        #visualization settings
        self.self_link_color = '#ff8888'
        self.link_color = '#8888ff'
        self.text_color = '#dddddd'
        self.highlight_color = '#ffff88'
        self.node_size = 0.15
        self.arrow_size = 15
        self.zoom_level = 1.0
        
        #interactive state
        self.selected_link = None
        self.hovered_link = None
        self.dragging = False
        self.pan_start = None
        self.pan_origin = None
        
        #artists
        self.link_artists = {}
        self.text_artists = {}
        
        self.ax.set_facecolor('#222222')
        self.fig.set_facecolor('#222222')
        self.ax.axis('off')
        
        #connect events
        self.mpl_connect('button_press_event', self.on_press)
        self.mpl_connect('button_release_event', self.on_release)
        self.mpl_connect('motion_notify_event', self.on_motion)
        self.mpl_connect('scroll_event', self.on_scroll)
        

    def load_links_from_csv(self, filename):
        self.links.clear()
        self.link_positions.clear()
        self.clear_artists()
        
        try:
            with open(filename, 'r', encoding='utf-8') as csvfile:
                reader = csv.reader(csvfile)
                next(reader, None)  #skip header if exists
                
                for row_id, row in enumerate(reader, start=1):
                    if len(row) < 2:  #need at least 2 columns (from, to)
                        continue
                    
                    #auto-generate link id starting from 1
                    link_id = row_id
                    
                    #try to parse from and to values
                    try:
                        from_val = int(row[0]) if row[0].strip() else None
                        to_val = int(row[1]) if row[1].strip() else None
                    except (ValueError, IndexError):
                        continue
                    
                    self.links[link_id] = {'from': from_val, 'to': to_val}
            
            if not self.links:
                raise ValueError("No valid links found in CSV file")
            
            self.apply_layout("spring")
            self.create_artists()
            self.update_artists()
            self.draw()
            return True
        
        except Exception as e:
            print(f"Error loading links: {e}")
            QMessageBox.warning(self.parent(), "Error",
                               f"Failed to load links: {e}\n"
                               "CSV should contain at least two columns with numeric values")
            return False

    def get_stats(self):
        self_links = sum(1 for link in self.links.values() 
                        if link['from'] == link['to'])
        return {'links': len(self.links), 'self_links': self_links}

    def clear_artists(self):
        """Clear all artists from the canvas"""
        for link_id in list(self.link_artists.keys()):
            artist = self.link_artists[link_id]
            if isinstance(artist, list):
                for a in artist:
                    a.remove()
            else:
                artist.remove()
        self.link_artists.clear()
        
        for artist in self.text_artists.values():
            artist.remove()
        self.text_artists.clear()
        
        self.ax.clear()
        self.ax.axis('off')

    def apply_layout(self, layout_type):
        """Apply the specified layout to the graph"""
        if not self.links:
            return
        
        # Create a graph where links are nodes and references are edges
        G = nx.DiGraph()
        G.add_nodes_from(self.links.keys())
        
        for link_id, link_data in self.links.items():
            if link_data['from'] in self.links:
                G.add_edge(link_data['from'], link_id)
            if link_data['to'] in self.links:
                G.add_edge(link_id, link_data['to'])
        
        # Calculate layout with try-except for fallback
        try:
            layouts = {
                "spring": nx.spring_layout(G, k=0.5, iterations=100),
                "circular": nx.circular_layout(G),
                "random": nx.random_layout(G),
                "kamada_kawai": nx.kamada_kawai_layout(G),
                "spectral": nx.spectral_layout(G)
            }
            self.link_positions = layouts.get(layout_type, nx.spring_layout(G))
        except Exception as e:
            print(f"Error applying {layout_type} layout: {e}")
            self.link_positions = nx.spring_layout(G)
        
        self.clear_artists()
        self.create_artists()
        self.reset_view()

    def create_artists(self):
        for link_id in self.links:
            self._create_link_artist(link_id)

    def _create_link_artist(self, link_id):
        """графический элемент связи"""
        link_data = self.links[link_id]
        from_id = link_data['from']
        to_id = link_data['to']
        pos = self.link_positions.get(link_id, (0, 0))
        
        #самозамкнутая связь
        if from_id == link_id and to_id == link_id:
            artist = self._draw_self_link(link_id, pos[0], pos[1])
        #обычная связь между элементами
        elif from_id is not None and to_id is not None:
            artist = self._draw_regular_link(link_id, from_id, to_id)
        #связь как узел
        else:
            artist = self._draw_link_as_node(link_id, pos[0], pos[1])
        
        self.link_artists[link_id] = artist

    def _draw_self_link(self, link_id, x, y):
        """символ бесконечности в самозамкнутой связи"""
        t = np.linspace(0, 2*np.pi, 100)
        a = self.node_size * 0.7
        x_loop = a * np.sin(t) / (1 + np.cos(t)**2)
        y_loop = a * np.sin(t) * np.cos(t) / (1 + np.cos(t)**2)
        x_loop += x
        y_loop += y
        
        #основная линия
        loop = self.ax.plot(x_loop, y_loop, color=self.self_link_color, 
                        lw=2, zorder=2, solid_capstyle='round')[0]
        
        #стрелка на петле
        arrow_idx = -20  #индекс точки для стрелки
        arrow = FancyArrowPatch(
            (x_loop[arrow_idx], y_loop[arrow_idx]),
            (x_loop[arrow_idx+1], y_loop[arrow_idx+1]),
            arrowstyle='->', color=self.self_link_color,
            mutation_scale=self.arrow_size*0.8, lw=2, zorder=3
        )
        self.ax.add_patch(arrow)
        
        # Возвращаем список художников
        return [loop, arrow]

    def _draw_regular_link(self, link_id, from_id, to_id):
        """соединения между всеми видами связи"""
        #получаем базовые позиции
        start_pos = self.link_positions.get(from_id, (0, 0))
        end_pos = self.link_positions.get(to_id, (0, 0))
        
        #корректируем начальную точку если рисуем ОТ стрелки
        if from_id in self.links and self.links[from_id]['from'] != self.links[from_id]['to']:
            src_from = self.link_positions.get(self.links[from_id]['from'], (0, 0))
            src_to = self.link_positions.get(self.links[from_id]['to'], (0, 0))
            start_pos = (
                (src_from[0] + src_to[0]) / 2,
                (src_from[1] + src_to[1]) / 2
            )
        
        #корректируем конечную точку если рисуем К стрелке
        if to_id in self.links and self.links[to_id]['from'] != self.links[to_id]['to']:
            tgt_from = self.link_positions.get(self.links[to_id]['from'], (0, 0))
            tgt_to = self.link_positions.get(self.links[to_id]['to'], (0, 0))
            end_pos = (
                (tgt_from[0] + tgt_to[0]) / 2,
                (tgt_from[1] + tgt_to[1]) / 2
            )
        
        #рисуем стрелку
        arrow = FancyArrowPatch(
            start_pos, end_pos,
            arrowstyle='->', color=self.link_color,
            mutation_scale=self.arrow_size, lw=2, zorder=1
        )
        self.ax.add_patch(arrow)
        return arrow

    def _get_nearest_point_on_line(self, point, line_start, line_end):
        """нахождение ближайшей точки на отрезке для заданной точки"""
        #вектор отрезка
        line_vec = np.array([line_end[0] - line_start[0], line_end[1] - line_start[1]])
        #вектор от начала отрезка до точки
        point_vec = np.array([point[0] - line_start[0], point[1] - line_start[1]])
        
        #длина отрезка
        line_len = np.linalg.norm(line_vec)
        if line_len == 0:
            return line_start
        
        #нормализованный вектор направления
        line_dir = line_vec / line_len
        
        #проекция point_vec на line_dir
        projection = np.dot(point_vec, line_dir)
        
        #ограничиваем проекцию в пределах отрезка
        projection = max(0, min(line_len, projection))
        
        #вычисляем ближайшую точку
        nearest_point = line_start + projection * line_dir
        
        #смещаем немного от краев для лучшего вида
        if projection < self.arrow_size * 0.5:
            nearest_point = line_start + self.arrow_size * 0.5 * line_dir
        elif projection > line_len - self.arrow_size * 0.5:
            nearest_point = line_end - self.arrow_size * 0.5 * line_dir
        
        return nearest_point

    def _draw_link_as_node(self, link_id, x, y):
        """связь как узел (просто круг)"""
        circle = Circle(
            (x, y), self.node_size/2,
            facecolor=self.link_color, edgecolor='white',
            linewidth=1, alpha=0.9, zorder=2
        )
        self.ax.add_patch(circle)
        return circle

    def _get_link_type(self, link_id):
        """определения типа связи"""
        if link_id not in self.links:
            return 'node'
        link = self.links[link_id]
        if link['from'] == link['to']:
            return 'loop'
        return 'arrow'

    def _get_node_edge_point(self, node_pos, target_pos, outward=True):
        """точка на краю круга"""
        dx = target_pos[0] - node_pos[0]
        dy = target_pos[1] - node_pos[1]
        dist = max(0.001, np.hypot(dx, dy))
        factor = 0.5 if outward else -0.5
        return (
            node_pos[0] + dx * self.node_size * factor / dist,
            node_pos[1] + dy * self.node_size * factor / dist
        )

    def _get_loop_connection_point(self, loop_pos, target_pos, outward=True):
        """точка соединения на петле (символ ∞)"""
        angle = np.arctan2(target_pos[1] - loop_pos[1], target_pos[0] - loop_pos[0])
        loop_size = self.node_size * 0.7
        factor = 0.7 if outward else -0.7
        return (
            loop_pos[0] + loop_size * np.cos(angle) * factor,
            loop_pos[1] + loop_size * np.sin(angle) * factor
        )

    def _get_arrow_connection_point(self, arrow_id, arrow_pos, target_pos, outward=True):
        """точка соединения на стрелке (обычной связи)"""
        #находим исходную стрелку
        arrow_data = self.links[arrow_id]
        from_pos = self.link_positions.get(arrow_data['from'], (0, 0))
        to_pos = self.link_positions.get(arrow_data['to'], (0, 0))
        
        #определяем направление исходной стрелки
        dx = to_pos[0] - from_pos[0]
        dy = to_pos[1] - from_pos[1]
        angle = np.arctan2(dy, dx)
        
        # перпендикулярное направление
        perp_angle = angle + np.pi/2
        
        # выбираем сторону соединения в зависимости от target_pos
        target_angle = np.arctan2(target_pos[1] - arrow_pos[1], target_pos[0] - arrow_pos[0])
        side = 1 if abs((target_angle - perp_angle) % (2*np.pi)) < np.pi/2 else -1
        
        # смещение от центра стрелки
        offset = self.node_size * 0.3
        return (
            arrow_pos[0] + offset * np.cos(perp_angle) * side,
            arrow_pos[1] + offset * np.sin(perp_angle) * side
        )

    def update_artists(self):
        """Update visual properties based on interaction state"""
        for link_id, artist in self.link_artists.items():
            color = self.self_link_color if self.links[link_id]['from'] == self.links[link_id]['to'] else self.link_color
            
            if link_id == self.hovered_link or link_id == self.selected_link:
                color = self.highlight_color
            
            # Handle both single artists and lists of artists (for self-links)
            if isinstance(artist, (list, tuple)):
                for a in artist:
                    if hasattr(a, 'set_color'):
                        a.set_color(color)
                    elif hasattr(a, 'set_facecolor'):  # for circles
                        a.set_facecolor(color)
            else:
                if hasattr(artist, 'set_color'):
                    artist.set_color(color)
                elif hasattr(artist, 'set_facecolor'):  #for circles
                    artist.set_facecolor(color)
        
        self.draw()

    def reset_view(self):
        """Reset view to fit all links"""
        if not self.link_positions:
            return
            
        all_x = [pos[0] for pos in self.link_positions.values()]
        all_y = [pos[1] for pos in self.link_positions.values()]
        
        if not all_x or not all_y:
            return
            
        x_min, x_max = min(all_x), max(all_x)
        y_min, y_max = min(all_y), max(all_y)
        
        x_padding = max(0.2, (x_max - x_min) * 0.2)
        y_padding = max(0.2, (y_max - y_min) * 0.2)
        
        self.ax.set_xlim(x_min - x_padding, x_max + x_padding)
        self.ax.set_ylim(y_min - y_padding, y_max + y_padding)
        self.zoom_level = 1.0
        self.draw()

    def set_zoom(self, zoom_level):
        """Set zoom level while maintaining center"""
        xlim, ylim = self.ax.get_xlim(), self.ax.get_ylim()
        center_x = (xlim[0] + xlim[1]) / 2
        center_y = (ylim[0] + ylim[1]) / 2
        
        width = (xlim[1] - xlim[0]) / zoom_level
        height = (ylim[1] - ylim[0]) / zoom_level
        
        self.ax.set_xlim(center_x - width/2, center_x + width/2)
        self.ax.set_ylim(center_y - height/2, center_y + height/2)
        self.zoom_level = zoom_level
        self.draw()

    
    def on_press(self, event):
        """Handle mouse press events"""
        if event.inaxes != self.ax:
            return

        if event.button == 1:  # Left mouse button
            # Find which link was clicked
            clicked_link = self._get_link_at_position((event.xdata, event.ydata))
        
            if clicked_link:
                self.selected_link = clicked_link
                self.dragging = True
                self.update_artists()
            else:
                # start panning
                self.pan_start = QPoint(event.x, event.y)
                self.pan_origin = (self.ax.get_xlim(), self.ax.get_ylim())
                self.setCursor(QCursor(Qt.ClosedHandCursor))

    def on_release(self, event):
        """Handle mouse release events"""
        if event.button == 1:  #left mouse button
            self.dragging = False
            self.selected_link = None
            self.pan_start = None
            self.pan_origin = None
            self.setCursor(QCursor(Qt.ArrowCursor))
            self.update_artists()

    def on_motion(self, event):
        """Handle mouse motion events"""
        if event.inaxes != self.ax:
            #handle hover off
            if self.hovered_link:
                self.hovered_link = None
                self.update_artists()
            return
    
        #handle panning
        if self.pan_start and event.button == 1:
            if event.xdata is None or event.ydata is None:
                return
            
            dx_pixels = event.x - self.pan_start.x()
            dy_pixels = event.y - self.pan_start.y()

            xlim_current, ylim_current = self.ax.get_xlim(), self.ax.get_ylim()
            fig_width, fig_height = self.fig.get_size_inches()
            dpi = self.fig.dpi
        
            if fig_width == 0 or fig_height == 0:
                return
            
            x_data_per_pixel = (xlim_current[1] - xlim_current[0]) / (fig_width * dpi)
            y_data_per_pixel = (ylim_current[1] - ylim_current[0]) / (fig_height * dpi)
        
            dx_data = dx_pixels * x_data_per_pixel
            dy_data = dy_pixels * y_data_per_pixel

            new_xlim = (self.pan_origin[0][0] - dx_data, self.pan_origin[0][1] - dx_data)
            new_ylim = (self.pan_origin[1][0] + dy_data, self.pan_origin[1][1] + dy_data)
        
            self.ax.set_xlim(new_xlim)
            self.ax.set_ylim(new_ylim)
            self.fig.canvas.draw_idle()
            return
    
        #handle hover
        hovered_link = self._get_link_at_position((event.xdata, event.ydata))
        if hovered_link != self.hovered_link:
            self.hovered_link = hovered_link
            self.update_artists()
    
        #handle dragging
        if self.dragging and self.selected_link and event.xdata is not None and event.ydata is not None:
            self.link_positions[self.selected_link] = (event.xdata, event.ydata)
            self._update_link_artist(self.selected_link)
            self.fig.canvas.draw_idle()

    def on_scroll(self, event):
        """Handle scroll events for zooming"""
        if event.inaxes != self.ax:
            return
        
        zoom_factor = 1.25 if event.button == 'up' else 0.8
        self.zoom_level *= zoom_factor
    
        xlim, ylim = self.ax.get_xlim(), self.ax.get_ylim()
        mouse_x = event.xdata if event.xdata else (xlim[0] + xlim[1]) / 2
        mouse_y = event.ydata if event.ydata else (ylim[0] + ylim[1]) / 2
    
        new_width = (xlim[1] - xlim[0]) / zoom_factor
        new_height = (ylim[1] - ylim[0]) / zoom_factor
    
        self.ax.set_xlim(mouse_x - new_width/2, mouse_x + new_width/2)
        self.ax.set_ylim(mouse_y - new_height/2, mouse_y + new_height/2)
        self.update_artists()

    def _get_link_at_position(self, pos):
        """Find which link is at given position (x,y)"""
        if not pos[0] or not pos[1]:
            return None
        
        x, y = pos
        xlim, ylim = self.ax.get_xlim(), self.ax.get_ylim()
    
        if (xlim[1] - xlim[0]) == 0 or (ylim[1] - ylim[0]) == 0:
            return None
        
        fig_width, fig_height = self.fig.get_size_inches()
        dpi = self.fig.dpi
        x_data_per_inch = (xlim[1] - xlim[0]) / fig_width
        y_data_per_inch = (ylim[1] - ylim[0]) / fig_height
        node_radius = 15.0 / dpi * ((x_data_per_inch + y_data_per_inch) / 2)
    
        for link_id, (lx, ly) in self.link_positions.items():
            if ((lx - x)**2 + (ly - y)**2) <= node_radius**2:
                return link_id
        return None

    def _update_link_artist(self, link_id):
        """Update visual representation of a single link"""
        if link_id not in self.link_artists:
            return
        
        #remove old artist(s)
        artist = self.link_artists[link_id]
        if isinstance(artist, list):
            for a in artist:
                a.remove()
        else:
            artist.remove()
        
        link_data = self.links[link_id]
        from_id = link_data['from']
        to_id = link_data['to']
        
        # create new artist at updated position
        if from_id == to_id == link_id:  # self-link (loop)
            loop, arrow = self._draw_self_link(link_id, *self.link_positions[link_id])
            self.link_artists[link_id] = [loop, arrow]
        elif from_id is not None and to_id is not None:  # regular link
            new_artist = self._draw_regular_link(link_id, from_id, to_id)
            self.link_artists[link_id] = new_artist
        else:  # link as node
            new_artist = self._draw_link_as_node(link_id, *self.link_positions[link_id])
            self.link_artists[link_id] = new_artist
        
        # update text position if exists
        if link_id in self.text_artists:
            self.text_artists[link_id].set_position(self.link_positions[link_id])

    def _get_connection_point(self, source_pos, target_id):
        """get the best connection point for a link to a target"""
        if target_id not in self.link_positions:
            return self.link_positions.get(target_id, (0, 0))
    
        target_pos = self.link_positions[target_id]

        #if target is a self-link, use special connection points
        if hasattr(self, 'connection_points') and self.links[target_id]['from'] == self.links[target_id]['to']:
            x1, y1 = source_pos
            angles = []
            for side, (x2, y2) in self.connection_points.items():
                angle = np.arctan2(y2 - y1, x2 - x1)
                angles.append((angle, (x2, y2)))
        
            #find the point with most direct angle
            angles.sort(key=lambda x: abs(x[0]))
            return angles[0][1]
    
        #regular node connection
        return target_pos
