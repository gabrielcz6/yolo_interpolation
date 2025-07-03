#!/usr/bin/env python3
"""
Procesador de videos con anotaciones
ACTUALIZADO: Con soporte para visualización de líneas angulares
"""

import cv2
import os
import math
import numpy as np


class VideoProcessor:
    def __init__(self, config, detection_engine, people_tracker):
        """Inicializar procesador de video"""
        self.config = config
        self.detection_engine = detection_engine
        self.people_tracker = people_tracker
    
    def _remove_from_watchdog_log(self, video_path):
        """Eliminar entrada del log del watchdog cuando se procesa un archivo"""
        try:
            filename = os.path.basename(video_path)
            watchdog_log = os.path.join(self.config["paths"]["videos_dir"], "watchdog_log.txt")
            
            if not os.path.exists(watchdog_log):
                return
            
            # Leer líneas actuales
            with open(watchdog_log, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            # Filtrar líneas (eliminar la que contenga este filename)
            filtered_lines = [line for line in lines if not line.startswith(filename + "|")]
            
            # Reescribir archivo
            with open(watchdog_log, "w", encoding="utf-8") as f:
                f.writelines(filtered_lines)
                
            print(f"📝 Entrada eliminada del log watchdog: {filename}")
            
        except Exception as e:
            print(f"⚠️ Error eliminando del log: {e}")

    def process_video(self, video_path):
        """Procesar un video específico"""
        print(f"📹 Procesando: {video_path}")
        
        cap = cv2.VideoCapture(video_path)
        if not cap.isOpened():
            print(f"❌ Error: No se pudo abrir {video_path}")
            print(f"🗑️ Eliminando archivo corrupto...")
            try:
                os.remove(video_path)
                print(f"🗑️ Video original eliminado: {video_path}")
                # Eliminar entrada del log del watchdog
                self._remove_from_watchdog_log(video_path)
            except Exception as e:
                print(f"⚠️ Error eliminando video: {e}")
            return True
        
        # Ajustar dimensiones para ROI
        roi_width, roi_height = self.detection_engine.get_roi_dimensions()
        fps = int(cap.get(cv2.CAP_PROP_FPS)) or 30
        
        frame_count = 0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        
        print(f"📊 Total frames: {total_frames}")
        
        try:
            frame_counter = 0
            last_detections = []
            last_tracked_objects = {}
            
            while True:
                ret, frame = cap.read()
                if not ret:
                    break
                    
                frame_count += 1
                frame_counter += 1
                
                # Recortar ROI
                cropped_frame = self.detection_engine.crop_frame(frame)
                
                # Decidir si ejecutar detección o interpolar
                should_detect = (frame_counter % self.config["detection"]["frame_skip"] == 0) or not self.config["detection"]["interpolation"]
                
                if should_detect:
                    # Ejecutar YOLO completo
                    detections = self.detection_engine.detect_people(cropped_frame)
                    last_detections = detections
                else:
                    # Usar interpolación
                    detections = self._interpolate_detections(last_detections, last_tracked_objects)
                
                # Actualizar tracking y contadores
                tracked_objects = self.people_tracker.update_tracking_and_count(detections, cropped_frame)
                last_tracked_objects = tracked_objects.copy()
                
                # Crear frame anotado
                annotated_frame = self._draw_annotations(cropped_frame.copy(), detections, tracked_objects)
              
                # Mostrar frame en tiempo real
                cv2.imshow('People Counter', annotated_frame)
                if cv2.waitKey(1) & 0xFF == ord('q'):
                    print("🛑 Interrupción por usuario")
                    break
                
                # Mostrar progreso cada 50 frames
                if frame_count % 50 == 0:
                    progress = (frame_count / total_frames) * 100 if total_frames > 0 else 0
                    counts = self.people_tracker.get_counts()
                    print(f"⏳ Progreso: {frame_count}/{total_frames} ({progress:.1f}%) - "
                          f"Entradas: {counts['entries']}, Salidas: {counts['exits']}")
                    
        except Exception as e:
            print(f"❌ Error procesando video: {e}")
            return False
            
        finally:
            cap.release()
            cv2.destroyAllWindows()
        
        counts = self.people_tracker.get_counts()
        print(f"📈 Resumen: {counts['entries']} entradas, {counts['exits']} salidas, "
              f"{counts['occupancy']} ocupación final")
        
        # Eliminar video original
        try:
            os.remove(video_path)
            print(f"🗑️ Video original eliminado: {video_path}")
        except Exception as e:
            print(f"⚠️ Error eliminando video: {e}")
            
        return True
    
    def _interpolate_detections(self, last_detections, last_tracked_objects):
        """Interpolar detecciones basadas en movimiento previo"""
        if not last_detections or not last_tracked_objects:
            return last_detections
         
        interpolated = []
        frame_skip = self.config["detection"]["frame_skip"]
         
        for detection in last_detections:
            x1, y1, x2, y2, conf = detection
            center_x = (x1 + x2) // 2
            center_y = (y1 + y2) // 2
             
            # Buscar objeto correspondiente en tracking
            for obj_id, tracked_center in last_tracked_objects.items():
                tracked_x, tracked_y = tracked_center
                 
                # Si está cerca, usar movimiento para interpolar
                if abs(center_x - tracked_x) < 50 and abs(center_y - tracked_y) < 50:
                    interpolated.append(detection)
                    break
            else:
                # Si no hay tracking, usar detección original
                interpolated.append(detection)
         
        return interpolated
        
    def _draw_annotations(self, frame, detections, tracked_objects):
        """Dibujar anotaciones en el frame (ACTUALIZADO para líneas angulares)"""
        
        # Obtener información de la línea configurada
        line_info = self.people_tracker.get_line_info()
        
        if line_info["type"] == "angular":
            self._draw_angular_line_annotations(frame, line_info)
        else:
            self._draw_horizontal_line_annotations(frame, line_info)
        
        # Dibujar detecciones (opcional - comentado para menor carga visual)
        # self._draw_detections(frame, detections)
        
        # Dibujar objetos trackeados con IDs
        self._draw_tracked_objects(frame, tracked_objects)
        
        # Dibujar contadores e información (CORREGIDO: pasar tracked_objects)
        self._draw_counters_and_info(frame, line_info, tracked_objects)
         
        return frame
    
    def _draw_angular_line_annotations(self, frame, line_info):
        """Dibujar anotaciones para línea angular"""
        # Obtener coordenadas para ROI
        start_x, start_y, end_x, end_y = self.people_tracker.get_line_coordinates_for_roi()
        
        # Asegurar que las coordenadas estén dentro del frame
        h, w = frame.shape[:2]
        start_x = max(0, min(w-1, start_x))
        start_y = max(0, min(h-1, start_y))
        end_x = max(0, min(w-1, end_x))
        end_y = max(0, min(h-1, end_y))
        
        # Dibujar línea principal (más gruesa)
        cv2.line(frame, (int(start_x), int(start_y)), (int(end_x), int(end_y)), (0, 255, 0), 4)
        
        # Dibujar indicador de dirección (flecha)
        self._draw_direction_arrow(frame, start_x, start_y, end_x, end_y, line_info["inverted"])
        
        # Dibujar zona buffer (líneas paralelas más tenues)
        self._draw_angular_buffer_zone(frame, start_x, start_y, end_x, end_y, line_info["buffer"])
        
        # Etiqueta de la línea
        mid_x = int((start_x + end_x) / 2)
        mid_y = int((start_y + end_y) / 2)
        cv2.putText(frame, f"COUNTING LINE ({line_info['angle']}°)", 
                   (mid_x - 80, mid_y - 15), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
    
    def _draw_direction_arrow(self, frame, start_x, start_y, end_x, end_y, inverted):
        """Dibujar flecha indicando dirección de entrada"""
        # Calcular punto medio y vector de dirección
        mid_x = (start_x + end_x) / 2
        mid_y = (start_y + end_y) / 2
        
        # Vector de la línea
        line_dx = end_x - start_x
        line_dy = end_y - start_y
        line_length = math.sqrt(line_dx**2 + line_dy**2)
        
        if line_length == 0:
            return
            
        # Vector perpendicular (normal) - dirección de entrada
        normal_dx = -line_dy / line_length
        normal_dy = line_dx / line_length
        
        # Invertir si está configurado
        if inverted:
            normal_dx = -normal_dx
            normal_dy = -normal_dy
        
        # Dibujar flecha
        arrow_length = 30
        arrow_end_x = int(mid_x + normal_dx * arrow_length)
        arrow_end_y = int(mid_y + normal_dy * arrow_length)
        
        # Flecha principal
        cv2.arrowedLine(frame, (int(mid_x), int(mid_y)), (arrow_end_x, arrow_end_y), 
                       (0, 255, 255), 3, tipLength=0.3)
        
        # Etiqueta "ENTRADA"
        cv2.putText(frame, "ENTRADA", (arrow_end_x + 10, arrow_end_y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 2)
    
    def _draw_angular_buffer_zone(self, frame, start_x, start_y, end_x, end_y, buffer_distance):
        """Dibujar zona buffer alrededor de línea angular"""
        # Calcular vector perpendicular para el buffer
        line_dx = end_x - start_x
        line_dy = end_y - start_y
        line_length = math.sqrt(line_dx**2 + line_dy**2)
        
        if line_length == 0:
            return
            
        # Vector perpendicular normalizado
        perp_dx = -line_dy / line_length
        perp_dy = line_dx / line_length
        
        # Líneas buffer paralelas
        buffer_offset = buffer_distance
        
        # Buffer superior
        start_x_buf1 = int(start_x + perp_dx * buffer_offset)
        start_y_buf1 = int(start_y + perp_dy * buffer_offset)
        end_x_buf1 = int(end_x + perp_dx * buffer_offset)
        end_y_buf1 = int(end_y + perp_dy * buffer_offset)
        
        # Buffer inferior
        start_x_buf2 = int(start_x - perp_dx * buffer_offset)
        start_y_buf2 = int(start_y - perp_dy * buffer_offset)
        end_x_buf2 = int(end_x - perp_dx * buffer_offset)
        end_y_buf2 = int(end_y - perp_dy * buffer_offset)
        
        # Dibujar líneas buffer (más tenues)
        cv2.line(frame, (start_x_buf1, start_y_buf1), (end_x_buf1, end_y_buf1), (255, 255, 0), 1)
        cv2.line(frame, (start_x_buf2, start_y_buf2), (end_x_buf2, end_y_buf2), (255, 255, 0), 1)
    
    def _draw_horizontal_line_annotations(self, frame, line_info):
        """Dibujar anotaciones para línea horizontal (legacy)"""
        # Obtener coordenadas para ROI
        start_x, start_y, end_x, end_y = self.people_tracker.get_line_coordinates_for_roi()
        
        # Dibujar línea principal
        cv2.line(frame, (start_x, start_y), (end_x, end_y), (0, 255, 0), 3)
        
        # Dibujar zona buffer
        buffer_x1, buffer_y1, buffer_x2, buffer_y2 = self.people_tracker.get_buffer_coordinates_for_roi()
        cv2.line(frame, (buffer_x1, buffer_y1), (buffer_x2, buffer_y1), (255, 255, 0), 1)
        cv2.line(frame, (buffer_x1, buffer_y2), (buffer_x2, buffer_y2), (255, 255, 0), 1)
        
        # Etiqueta
        cv2.putText(frame, "COUNTING LINE", (start_x + 10, start_y - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
    
    def _draw_detections(self, frame, detections):
        """Dibujar detecciones (opcional)"""
        for detection in detections:
            x1, y1, x2, y2, conf = detection
            cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
            label = f"Person ({conf:.2f})"
            cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
    
    def _draw_tracked_objects(self, frame, tracked_objects):
        """Dibujar objetos trackeados con información de zona"""
        for object_id, centroid in tracked_objects.items():
            center_x, center_y = centroid
            
            # Centro con ID
            cv2.circle(frame, (center_x, center_y), 8, (0, 0, 255), -1)
            cv2.putText(frame, f"ID:{object_id}", (center_x + 10, center_y), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            
            # Mostrar zona actual del objeto
            obj_status = self.people_tracker.get_object_history(object_id)
            if obj_status:
                zone = obj_status['last_zone']
                
                # Colores según zona
                if zone in ['above', 'side_A']:
                    zone_color = (0, 255, 255)  # Amarillo
                    zone_text = "A" if zone == "side_A" else "↑"
                elif zone in ['below', 'side_B']:
                    zone_color = (255, 255, 0)  # Cian  
                    zone_text = "B" if zone == "side_B" else "↓"
                else:  # buffer
                    zone_color = (128, 128, 128)  # Gris
                    zone_text = "●"
                     
                cv2.putText(frame, zone_text, (center_x - 20, center_y - 20), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, zone_color, 2)
    
    def _draw_counters_and_info(self, frame, line_info, tracked_objects):
        """Dibujar contadores e información del sistema"""
        # Fondo semitransparente para contadores
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (380, 150), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        
        # Contadores principales
        counts = self.people_tracker.get_counts()
        cv2.putText(frame, f"ENTRADAS: {counts['entries']}", (20, 40), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.putText(frame, f"SALIDAS: {counts['exits']}", (20, 70), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        cv2.putText(frame, f"OCUPACION: {counts['occupancy']}", (20, 100), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 255), 2)
        
        # Información de la línea
        if line_info["type"] == "angular":
            info_text = f"Linea: {line_info['angle']:.0f}° | Buffer: {line_info['buffer']}px"
            direction_text = f"Entrada: {'Invertida' if line_info['inverted'] else 'Normal'}"
        else:
            info_text = f"Linea: Horizontal | Buffer: {line_info['buffer']}px"
            direction_text = "Entrada: Abajo->Arriba"
            
        cv2.putText(frame, info_text, (20, 125), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        cv2.putText(frame, direction_text, (20, 145), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        
        # Info de tracking (CORREGIDO: usar tracked_objects pasado como parámetro)
        active_objects_count = len(tracked_objects)
        cv2.putText(frame, f"Objetos: {active_objects_count}", (290, 40), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        # Instrucciones
        cv2.putText(frame, "Q=Salir", (290, 125), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (200, 200, 200), 1)