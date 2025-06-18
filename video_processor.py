#!/usr/bin/env python3
"""
Procesador de videos con anotaciones
"""

import cv2
import os
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
                tracked_objects = self.people_tracker.update_tracking_and_count(detections)
                last_tracked_objects = tracked_objects.copy()
                
                # Resto del código igual (anotaciones, mostrar frame, etc.)
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
                     # Obtener historial de movimiento
                     interpolated.append(detection)
                     break
             else:
                 # Si no hay tracking, usar detección original
                 interpolated.append(detection)
         
         return interpolated
        
    def _draw_annotations(self, frame, detections, tracked_objects):
        """Dibujar anotaciones en el frame"""
        # Obtener coordenadas de línea
        line_x1, line_y, line_x2, _ = self.people_tracker.get_line_coordinates()
        
        # Dibujar línea de conteo
        cv2.line(frame, (line_x1, line_y), (line_x2, line_y), (0, 255, 0), 3)
        cv2.putText(frame, "COUNTING LINE", (line_x1 + 10, line_y - 10), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
        
        # Dibujar detecciones
        for detection in detections:
            x1, y1, x2, y2, conf = detection
            
            # Bounding box
          #  cv2.rectangle(frame, (x1, y1), (x2, y2), (255, 0, 0), 2)
            
            # Confianza
            label = f"Person ({conf:.2f})"
       #     cv2.putText(frame, label, (x1, y1 - 10), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        
        # Dibujar objetos trackeados con IDs
        for object_id, centroid in tracked_objects.items():
            center_x, center_y = centroid
            
            # Centro con ID
            cv2.circle(frame, (center_x, center_y), 8, (0, 0, 255), -1)
            cv2.putText(frame, f"ID:{object_id}", (center_x + 10, center_y), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
            
            # Dibujar trayectoria si existe
            # Mostrar zona actual del objeto
            obj_status = self.people_tracker.get_object_history(object_id)
            if obj_status:
                zone_color = (0, 255, 255) if obj_status['last_zone'] == 'above' else (255, 255, 0)
                cv2.putText(frame, obj_status['last_zone'], (center_x - 20, center_y - 20), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, zone_color, 1)
        
        # Contadores con mejor estilo
        overlay = frame.copy()
        cv2.rectangle(overlay, (10, 10), (350, 120), (0, 0, 0), -1)
        cv2.addWeighted(overlay, 0.7, frame, 0.3, 0, frame)
        
        counts = self.people_tracker.get_counts()
        cv2.putText(frame, f"ENTRADAS: {counts['entries']}", (20, 40), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
        cv2.putText(frame, f"SALIDAS: {counts['exits']}", (20, 70), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
        cv2.putText(frame, f"OCUPACION: {counts['occupancy']}", (20, 100), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.8, (255, 0, 255), 2)
        
        # Info de tracking
        cv2.putText(frame, f"Tracked: {len(tracked_objects)}", (250, 40), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 1)
        
        return frame