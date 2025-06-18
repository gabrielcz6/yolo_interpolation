#!/usr/bin/env python3
"""
Sistema de tracking y conteo de personas
"""

import time
import numpy as np
from sort_tracker import SortTracker


class PeopleTracker:
    def __init__(self, config):
        """Inicializar tracker de personas"""
        self.config = config
        self.tracker = SortTracker(
            max_disappeared=config["tracking"]["max_disappeared"],
            max_distance=config["tracking"]["max_distance"]
        )
        self.reset_counters()
        self.setup_tracking_line()
        
    def reset_counters(self):
        """Reiniciar contadores"""
        self.entry_count = 0
        self.exit_count = 0
        self.tracked_objects_status = {}  # {object_id: {'last_zone': zone, 'counted': False}}

        print("🔄 Contadores reiniciados")
        
    def setup_tracking_line(self):
        """Configurar línea de conteo con zona muerta"""
        roi = self.config["roi"]
        line_pos = self.config["counting"]["line_position"]
        
        self.line_y = int(roi["y1"] + (roi["y2"] - roi["y1"]) * line_pos)
        self.line_x1 = roi["x1"]
        self.line_x2 = roi["x2"]
        
        # Zona muerta alrededor de la línea
        self.line_buffer = self.config["counting"].get("line_buffer", 10)
        self.line_y_upper = self.line_y - self.line_buffer
        self.line_y_lower = self.line_y + self.line_buffer
        
        print(f"📏 Línea de conteo configurada en Y={self.line_y} con buffer ±{self.line_buffer}px")
        
    def update_tracking_and_count(self, detections):
        """Actualizar tracking con lógica de zona mejorada (con zona muerta)"""
        rects = [(x1, y1, x2, y2) for x1, y1, x2, y2, conf in detections]
        objects = self.tracker.update(rects)
        
        # Coordenadas relativas al ROI
        line_y_relative = self.line_y - self.config["roi"]["y1"]
        line_y_upper_relative = self.line_y_upper - self.config["roi"]["y1"]
        line_y_lower_relative = self.line_y_lower - self.config["roi"]["y1"]
        
        for object_id, centroid in objects.items():
            center_x, center_y = centroid
            
            # Determinar zona actual con zona muerta
            if center_y < line_y_upper_relative:
                current_zone = "above"
            elif center_y > line_y_lower_relative:
                current_zone = "below"
            else:
                current_zone = "buffer"  # Zona muerta
            
            if object_id not in self.tracked_objects_status:
                # Nuevo objeto - inicializar sin contar si está en buffer
                self.tracked_objects_status[object_id] = {
                    'last_zone': current_zone,
                    'last_counting_zone': current_zone if current_zone != "buffer" else None
                }
            else:
                obj_status = self.tracked_objects_status[object_id]
                last_zone = obj_status.get('last_counting_zone')
                
                # Solo contar si sale de la zona buffer hacia una zona válida
                if current_zone != "buffer" and last_zone is not None and current_zone != last_zone:
                    if last_zone == "above" and current_zone == "below":
                        self.entry_count += 1
                        print(f"🟢 ENTRADA! ID: {object_id}, Total: {self.entry_count}")
                    elif last_zone == "below" and current_zone == "above":
                        self.exit_count += 1
                        print(f"🔴 SALIDA! ID: {object_id}, Total: {self.exit_count}")
                
                # Actualizar estado
                obj_status['last_zone'] = current_zone
                if current_zone != "buffer":
                    obj_status['last_counting_zone'] = current_zone
        
        # Limpiar objetos inactivos
        active_ids = set(objects.keys())
        inactive_ids = set(self.tracked_objects_status.keys()) - active_ids
        for inactive_id in inactive_ids:
            del self.tracked_objects_status[inactive_id]
        
        return objects
        
    def get_counts(self):
        """Obtener conteos actuales"""
        return {
            'entries': self.entry_count,
            'exits': self.exit_count,
            'occupancy': self.entry_count - self.exit_count
        }
        
    def get_line_coordinates(self):
        """Obtener coordenadas de la línea de conteo para ROI"""
        roi = self.config["roi"]
        line_y_roi = self.line_y - roi["y1"]
        line_x1_roi = 0
        line_x2_roi = roi["x2"] - roi["x1"]
        
        return line_x1_roi, line_y_roi, line_x2_roi, line_y_roi
    
    def get_buffer_coordinates(self):
        """Obtener coordenadas de la zona buffer para visualización"""
        roi = self.config["roi"]
        line_y_upper_roi = self.line_y_upper - roi["y1"]
        line_y_lower_roi = self.line_y_lower - roi["y1"]
        line_x1_roi = 0
        line_x2_roi = roi["x2"] - roi["x1"]
        
        return line_x1_roi, line_y_upper_roi, line_x2_roi, line_y_lower_roi
        
    def get_object_history(self, object_id):
        return self.tracked_objects_status.get(object_id, None)
        
    def get_active_objects_count(self):
        return len(self.tracked_objects_status)