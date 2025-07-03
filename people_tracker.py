#!/usr/bin/env python3
"""
Sistema de tracking y conteo de personas
ACTUALIZADO: Con soporte para líneas angulares (RAM eficiente)
"""

import time
import math
import numpy as np
from sort_tracker import SortTracker
from person_filter import PersonFilter



class PeopleTracker:
    def __init__(self, config):
        """Inicializar tracker de personas"""
        self.config = config
        self.tracker = SortTracker(
            max_disappeared=config["tracking"]["max_disappeared"],
            max_distance=config["tracking"]["max_distance"]
        )
        self.reset_counters()
        self.person_filter = PersonFilter(config)
        # Configurar línea según tipo
        if config["counting"].get("line_type") == "angular":
            self.setup_angular_line()
        else:
            self.setup_horizontal_line()  # Compatibilidad legacy
        
    def reset_counters(self):
        """Reiniciar contadores"""
        self.entry_count = 0
        self.exit_count = 0
        self.tracked_objects_status = {}  # {object_id: {'last_zone': zone, 'counted': False}}
        print("🔄 Contadores reiniciados")
        
    def setup_angular_line(self):
        """Configurar línea angular con matemáticas RAM eficientes"""
        counting_config = self.config["counting"]
        
        # Obtener parámetros de línea CON CONVERSIÓN EXPLÍCITA A NÚMEROS
        self.line_center_x = int(counting_config["line_center_x"])
        self.line_center_y = int(counting_config["line_center_y"])
        self.line_angle = float(counting_config["line_angle"])
        self.line_length = int(counting_config["line_length"])
        self.line_buffer = int(counting_config["line_buffer"])
        self.entry_inverted = bool(counting_config.get("entry_inverted", False))
        
        # OPTIMIZACIÓN RAM: Pre-calcular coeficientes de línea (solo una vez)
        # Ecuación de línea: ax + by + c = 0
        angle_rad = math.radians(self.line_angle)
        
        # Vector normal a la línea (perpendicular)
        self.line_a = math.sin(angle_rad)
        self.line_b = -math.cos(angle_rad)
        self.line_c = -(self.line_a * self.line_center_x + self.line_b * self.line_center_y)
        
        # Pre-calcular puntos de inicio y fin de línea para visualización
        half_length = self.line_length / 2
        dx = math.cos(angle_rad) * half_length
        dy = math.sin(angle_rad) * half_length
        
        self.line_start_x = int(self.line_center_x - dx)
        self.line_start_y = int(self.line_center_y - dy)
        self.line_end_x = int(self.line_center_x + dx)
        self.line_end_y = int(self.line_center_y + dy)
        
        # Verificar rotación
        rotation = self.config.get("image", {}).get("rotation", 0)
        
        print(f"📐 Línea angular configurada:")
        print(f"   Centro: ({self.line_center_x}, {self.line_center_y})")
        print(f"   Ángulo: {self.line_angle}°")
        print(f"   Longitud: {self.line_length}px")
        print(f"   Buffer: ±{self.line_buffer}px")
        print(f"   Entrada invertida: {self.entry_inverted}")
        print(f"   Rotación de imagen: {rotation}°")
        print(f"   Puntos: ({self.line_start_x},{self.line_start_y}) -> ({self.line_end_x},{self.line_end_y})")
        
        if rotation != 0:
            print(f"🔄 Conversión de coordenadas activada para rotación {rotation}°")
        
    def setup_horizontal_line(self):
        """Configurar línea horizontal (legacy)"""
        roi = self.config["roi"]
        line_pos = float(self.config["counting"]["line_position"])  # CONVERSIÓN EXPLÍCITA
        
        self.line_y = int(roi["y1"] + (roi["y2"] - roi["y1"]) * line_pos)
        self.line_x1 = int(roi["x1"])
        self.line_x2 = int(roi["x2"])
        
        # Zona muerta alrededor de la línea
        self.line_buffer = int(self.config["counting"].get("line_buffer", 
                                                     self.config["counting"].get("direction_threshold", 20)))
        self.line_y_upper = self.line_y - self.line_buffer
        self.line_y_lower = self.line_y + self.line_buffer
        self.entry_inverted = False
        
        print(f"📏 Línea horizontal (legacy) configurada en Y={self.line_y} con buffer ±{self.line_buffer}px")
    
    def _get_object_zone_angular(self, center_x, center_y):
        """
        Determinar zona de objeto usando línea angular (RAM eficiente)
        
        Returns: "side_A", "side_B", o "buffer"
        """
        # CORRECCIÓN: Convertir coordenadas ROI a coordenadas absolutas del frame
        # CONSIDERANDO LA ROTACIÓN DE IMAGEN
        roi = self.config["roi"]
        
        # Si hay rotación, ajustar coordenadas del ROI rotado a ROI original
        rotation = self.config.get("image", {}).get("rotation", 0)
        
        if rotation == 180:
            # Con rotación 180°, las coordenadas se invierten dentro del ROI
            roi_width = roi["x2"] - roi["x1"]
            roi_height = roi["y2"] - roi["y1"]
            
            # Invertir coordenadas dentro del ROI
            corrected_x = roi_width - center_x
            corrected_y = roi_height - center_y
            
            # Convertir a coordenadas absolutas
            absolute_x = corrected_x + roi["x1"]
            absolute_y = corrected_y + roi["y1"]
            
        elif rotation == 90:
            # Con rotación 90°, x e y se intercambian
            roi_width = roi["x2"] - roi["x1"]
            roi_height = roi["y2"] - roi["y1"]
            
            corrected_x = center_y
            corrected_y = roi_width - center_x
            
            absolute_x = corrected_x + roi["x1"]
            absolute_y = corrected_y + roi["y1"]
            
        elif rotation == 270:
            # Con rotación 270°, x e y se intercambian e invierten
            roi_width = roi["x2"] - roi["x1"]
            roi_height = roi["y2"] - roi["y1"]
            
            corrected_x = roi_height - center_y
            corrected_y = center_x
            
            absolute_x = corrected_x + roi["x1"]
            absolute_y = corrected_y + roi["y1"]
            
        else:
            # Sin rotación, conversión directa
            absolute_x = center_x + roi["x1"]
            absolute_y = center_y + roi["y1"]
        
        # OPTIMIZACIÓN: Solo una operación matemática por objeto
        distance = self.line_a * absolute_x + self.line_b * absolute_y + self.line_c
        
        if distance > self.line_buffer:
            return "side_A"
        elif distance < -self.line_buffer:
            return "side_B"
        else:
            return "buffer"
    
    def _get_object_zone_horizontal(self, center_x, center_y):
        """Determinar zona de objeto usando línea horizontal (legacy)"""
        # Coordenadas relativas al ROI
        roi = self.config["roi"]
        center_y_roi = center_y  # Ya está en coordenadas ROI
        line_y_roi = self.line_y - roi["y1"]
        
        if center_y_roi < line_y_roi - self.line_buffer:
            return "above"
        elif center_y_roi > line_y_roi + self.line_buffer:
            return "below"
        else:
            return "buffer"
            
    def update_tracking_and_count(self, detections, current_frame=None):

        """Actualizar tracking con lógica de zona (angular o horizontal)"""
        rects = [(x1, y1, x2, y2) for x1, y1, x2, y2, conf in detections]
        objects = self.tracker.update(rects)
        
        # Usar método según configuración
        is_angular = self.config["counting"].get("line_type") == "angular"
        
        for object_id, centroid in objects.items():
            center_x, center_y = centroid
            
            # Determinar zona actual
            if is_angular:
                current_zone = self._get_object_zone_angular(center_x, center_y)
            else:
                current_zone = self._get_object_zone_horizontal(center_x, center_y)
            
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
                    
                    # Lógica para línea angular
                    if is_angular:
                        entry_detected = (last_zone == "side_A" and current_zone == "side_B")
                        exit_detected = (last_zone == "side_B" and current_zone == "side_A")
                        
                        # Aplicar inversión si está configurada
                        if self.entry_inverted:
                            entry_detected, exit_detected = exit_detected, entry_detected
                            
                    # Lógica para línea horizontal (legacy)
                    else:
                        entry_detected = (last_zone == "above" and current_zone == "below")
                        exit_detected = (last_zone == "below" and current_zone == "above")
                    
                    
                    # DESPUÉS:
                        if entry_detected:
                           if current_frame is not None:
                               is_staff, confidence = self.person_filter.is_store_staff(current_frame, center_x, center_y)
                               if not is_staff:
                                   self.entry_count += 1
                                   print(f"🟢 ENTRADA! ID: {object_id}, Total: {self.entry_count}")
                               else:
                                   print(f"👔 PERSONAL DETECTADO - No contado (ID: {object_id}, conf: {confidence:.2f})")
                           else:
                               # Fallback si no hay frame disponible
                               self.entry_count += 1
                               print(f"🟢 ENTRADA! ID: {object_id}, Total: {self.entry_count}")
                
                        elif exit_detected:
                               if current_frame is not None:
                                   is_staff, confidence = self.person_filter.is_store_staff(current_frame, center_x, center_y)
                                   if not is_staff:
                                       self.exit_count += 1
                                       print(f"🔴 SALIDA! ID: {object_id}, Total: {self.exit_count}")
                                   else:
                                       print(f"👔 PERSONAL DETECTADO - No contado (ID: {object_id}, conf: {confidence:.2f})")
                               else:
                                   # Fallback si no hay frame disponible
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
        
    def get_line_coordinates_for_roi(self):
        """Obtener coordenadas de la línea para dibujar en ROI (considerando rotación)"""
        roi = self.config["roi"]
        
        if self.config["counting"].get("line_type") == "angular":
            # Convertir coordenadas absolutas a relativas del ROI
            start_x_roi = self.line_start_x - roi["x1"]
            start_y_roi = self.line_start_y - roi["y1"]
            end_x_roi = self.line_end_x - roi["x1"]
            end_y_roi = self.line_end_y - roi["y1"]
            
            # CORRECCIÓN: Si hay rotación, ajustar coordenadas para el ROI rotado
            rotation = self.config.get("image", {}).get("rotation", 0)
            
            if rotation == 180:
                # Con rotación 180°, invertir coordenadas dentro del ROI
                roi_width = roi["x2"] - roi["x1"]
                roi_height = roi["y2"] - roi["y1"]
                
                start_x_roi = roi_width - start_x_roi
                start_y_roi = roi_height - start_y_roi
                end_x_roi = roi_width - end_x_roi
                end_y_roi = roi_height - end_y_roi
                
            elif rotation == 90:
                # Con rotación 90°, intercambiar y rotar coordenadas
                roi_width = roi["x2"] - roi["x1"]
                
                new_start_x = start_y_roi
                new_start_y = roi_width - start_x_roi
                new_end_x = end_y_roi
                new_end_y = roi_width - end_x_roi
                
                start_x_roi, start_y_roi = new_start_x, new_start_y
                end_x_roi, end_y_roi = new_end_x, new_end_y
                
            elif rotation == 270:
                # Con rotación 270°, intercambiar y rotar coordenadas
                roi_height = roi["y2"] - roi["y1"]
                
                new_start_x = roi_height - start_y_roi
                new_start_y = start_x_roi
                new_end_x = roi_height - end_y_roi
                new_end_y = end_x_roi
                
                start_x_roi, start_y_roi = new_start_x, new_start_y
                end_x_roi, end_y_roi = new_end_x, new_end_y
            
            return start_x_roi, start_y_roi, end_x_roi, end_y_roi
        else:
            # Línea horizontal legacy
            line_y_roi = self.line_y - roi["y1"]
            return 0, line_y_roi, roi["x2"] - roi["x1"], line_y_roi
    
    def get_buffer_coordinates_for_roi(self):
        """Obtener coordenadas de la zona buffer para visualización en ROI"""
        roi = self.config["roi"]
        
        if self.config["counting"].get("line_type") == "angular":
            # Para línea angular, calcular rectángulo buffer perpendicular
            # (Implementación simplificada - rectángulo alrededor de línea)
            start_x_roi = max(0, self.line_start_x - roi["x1"] - self.line_buffer)
            start_y_roi = max(0, self.line_start_y - roi["y1"] - self.line_buffer)
            end_x_roi = min(roi["x2"] - roi["x1"], self.line_end_x - roi["x1"] + self.line_buffer)
            end_y_roi = min(roi["y2"] - roi["y1"], self.line_end_y - roi["y1"] + self.line_buffer)
            
            return start_x_roi, start_y_roi, end_x_roi, end_y_roi
        else:
            # Buffer horizontal legacy
            line_y_upper_roi = self.line_y_upper - roi["y1"]
            line_y_lower_roi = self.line_y_lower - roi["y1"]
            return 0, line_y_upper_roi, roi["x2"] - roi["x1"], line_y_lower_roi
    
    def get_line_info(self):
        """Obtener información de la línea configurada"""
        if self.config["counting"].get("line_type") == "angular":
            return {
                "type": "angular",
                "center": (self.line_center_x, self.line_center_y),
                "angle": self.line_angle,
                "length": self.line_length,
                "buffer": self.line_buffer,
                "inverted": self.entry_inverted,
                "start": (self.line_start_x, self.line_start_y),
                "end": (self.line_end_x, self.line_end_y)
            }
        else:
            return {
                "type": "horizontal",
                "y": self.line_y,
                "x1": self.line_x1,
                "x2": self.line_x2,
                "buffer": self.line_buffer
            }
        
    def get_object_history(self, object_id):
        """Obtener historial de objeto específico"""
        return self.tracked_objects_status.get(object_id, None)
        
    def get_active_objects_count(self):
        """Obtener número de objetos activamente trackeados"""
        return len(self.tracked_objects_status)
    
    def get_distance_to_line(self, x, y):
        """Obtener distancia de un punto a la línea (útil para debugging)"""
        if self.config["counting"].get("line_type") == "angular":
            return abs(self.line_a * x + self.line_b * y + self.line_c)
        else:
            roi = self.config["roi"]
            return abs(y - (self.line_y - roi["y1"]))
            
    def invert_entry_direction(self):
        """Alternar dirección de entrada (útil para calibración)"""
        if self.config["counting"].get("line_type") == "angular":
            self.entry_inverted = not self.entry_inverted
            self.config["counting"]["entry_inverted"] = self.entry_inverted
            print(f"🔄 Dirección entrada {'INVERTIDA' if self.entry_inverted else 'NORMAL'}")
            return True
        return False