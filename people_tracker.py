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
        self.tracked_objects_status = {}  # {object_id: {'last_y': y, 'zone': 'above'/'below', 'counted': False}}

        print("🔄 Contadores reiniciados")
        
    def setup_tracking_line(self):
        """Configurar línea de conteo"""
        roi = self.config["roi"]
        line_pos = self.config["counting"]["line_position"]
        
        self.line_y = int(roi["y1"] + (roi["y2"] - roi["y1"]) * line_pos)
        self.line_x1 = roi["x1"]
        self.line_x2 = roi["x2"]
        
        print(f"📏 Línea de conteo configurada en Y={self.line_y}")
        
    def update_tracking_and_count(self, detections):
        """Actualizar tracking con lógica de zona simple"""
        rects = [(x1, y1, x2, y2) for x1, y1, x2, y2, conf in detections]
        objects = self.tracker.update(rects)
        
        line_y_relative = self.line_y - self.config["roi"]["y1"]
        
        for object_id, centroid in objects.items():
            center_x, center_y = centroid
            
            # Determinar zona actual
            current_zone = "above" if center_y < line_y_relative else "below"
            
            if object_id not in self.tracked_objects_status:
                # Nuevo objeto
                self.tracked_objects_status[object_id] = {
                    'last_zone': current_zone,
                    'counted_in_zone': True  # Para evitar contar inmediatamente
                }
            else:
                obj_status = self.tracked_objects_status[object_id]
                last_zone = obj_status['last_zone']
                
                # Detectar cambio de zona
                if current_zone != last_zone:
                    if last_zone == "above" and current_zone == "below":
                        self.entry_count += 1
                        print(f"🟢 ENTRADA! ID: {object_id}, Total: {self.entry_count}")
                    elif last_zone == "below" and current_zone == "above":
                        self.exit_count += 1
                        print(f"🔴 SALIDA! ID: {object_id}, Total: {self.exit_count}")
                    
                    # Actualizar estado
                    obj_status['last_zone'] = current_zone
                    obj_status['counted_in_zone'] = True
        
        # Limpiar objetos inactivos
        active_ids = set(objects.keys())
        inactive_ids = set(self.tracked_objects_status.keys()) - active_ids
        for inactive_id in inactive_ids:
            del self.tracked_objects_status[inactive_id]
        
        return objects
  #  
  #def _check_line_crossing(self, positions):
  #    """Verificar si hay cruce de línea"""
  #    line_y_relative = self.line_y - self.config["roi"]["y1"]  # Ajustar a coordenadas ROI
  #    
  #    for i in range(len(positions) - 1):
  #        y1, y2 = positions[i], positions[i + 1]
  #        # Verificar si la línea fue cruzada
  #        if (y1 < line_y_relative < y2) or (y2 < line_y_relative < y1):
  #            return True
  #    return False
  #    
  #def _get_direction(self, positions):
  #    """Determinar dirección del movimiento"""
  #    if len(positions) < 3:
  #        return None
  #        
  #    # Usar primer y último tercio para determinar dirección
  #    start_segment = positions[:len(positions)//3]
  #    end_segment = positions[-len(positions)//3:]
  #    
  #    start_avg = np.mean(start_segment)
  #    end_avg = np.mean(end_segment)
  #    
  #    threshold = self.config["counting"]["direction_threshold"]
  #    
  #    if end_avg - start_avg > threshold:
  #        return "entry"  # Movimiento hacia abajo
  #    elif start_avg - end_avg > threshold:
  #        return "exit"   # Movimiento hacia arriba
  #    else:
  #        return None     # Movimiento insuficiente
  #        
  #def _cleanup_old_objects(self, active_objects, current_time):
  #    """Limpiar objetos antiguos del historial"""
  #    active_ids = set(active_objects.keys())
  #    to_remove = []
  #    
  #    for obj_id in self.tracked_objects_history:
  #        if obj_id not in active_ids:
  #            # Verificar si ha pasado suficiente tiempo
  #            if current_time - self.tracked_objects_history[obj_id]['timestamps'][-1] > 3:
  #                to_remove.append(obj_id)
  #                
  #    for obj_id in to_remove:
  #        del self.tracked_objects_history[obj_id]
  #   
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
        
    def get_object_history(self, object_id):
        return self.tracked_objects_status.get(object_id, None)
        
    def get_active_objects_count(self):
        return len(self.tracked_objects_status)
