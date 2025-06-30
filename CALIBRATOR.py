#!/usr/bin/env python3
"""
Calibrador de ROI y Línea Angular - UNA SOLA PANTALLA
Soporte para definir ROI y línea angular sin cambiar de modo
"""

import cv2
import json
import math

class ROICalibrator:
    def __init__(self, config_file="config.json"):
        """Inicializar calibrador"""
        self.config_file = config_file
        self.config = self.load_config()
        
        # Variables para ROI
        self.drawing_roi = False
        self.roi_ix, self.roi_iy = -1, -1
        self.roi_points = None
        
        # Variables para línea angular
        self.line_center = None
        self.current_mouse_pos = None
        self.line_angle = 0
        self.line_length = 300
        self.entry_inverted = False
        self.line_buffer = 20
        
        self.current_frame = None
        
    def load_config(self):
        """Cargar configuración actual"""
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"❌ No se encontró {self.config_file}")
            return None
            
    def resize_frame(self, frame):
        """Redimensionar frame según configuración FFmpeg"""
        target_resolution = self.config["ffmpeg"]["resolution"]
        target_width, target_height = map(int, target_resolution.split('x'))
        
        original_height, original_width = frame.shape[:2]
        resized_frame = cv2.resize(frame, (target_width, target_height))
        return resized_frame, original_width, original_height
        
    def mouse_callback(self, event, x, y, flags, param):
        """Callback del mouse SIMPLIFICADO"""
        self.current_mouse_pos = (x, y)
        
        # Click simple = ROI o centro de línea
        if event == cv2.EVENT_LBUTTONDOWN:
            if self.roi_points and self.is_point_in_roi(x, y):
                # Si hay ROI y click dentro = centro de línea
                self.line_center = (x, y)
                print(f"📐 Centro de línea: ({x}, {y})")
            else:
                # Si no hay ROI o click fuera = empezar ROI
                self.drawing_roi = True
                self.roi_ix, self.roi_iy = x, y
                print(f"🖱️ Inicio ROI: ({x}, {y})")
                
        elif event == cv2.EVENT_MOUSEMOVE and self.drawing_roi:
            # Dibujando ROI
            pass  # Se maneja en draw_all_annotations
            
        elif event == cv2.EVENT_LBUTTONUP and self.drawing_roi:
            # Finalizar ROI
            self.drawing_roi = False
            x1, y1 = min(self.roi_ix, x), min(self.roi_iy, y)
            x2, y2 = max(self.roi_ix, x), max(self.roi_iy, y)
            self.roi_points = (x1, y1, x2, y2)
            print(f"🖱️ ROI completo: ({x1}, {y1}) -> ({x2}, {y2})")
            
            # AUTO-CENTRAR línea cuando se define ROI
            self.auto_center_line_to_roi()
            
        elif event == cv2.EVENT_MOUSEWHEEL and self.line_center:
            # Scroll = ajustar longitud (solo si hay línea)
            if flags > 0:  # Scroll up
                self.line_length = min(800, self.line_length + 20)
            else:  # Scroll down
                self.line_length = max(100, self.line_length - 20)
            print(f"📏 Longitud: {self.line_length}px")
    
    def handle_roi_mouse(self, event, x, y, flags, param):
        """Manejar eventos de mouse para ROI"""
        if event == cv2.EVENT_LBUTTONDOWN:
            self.drawing_roi = True
            self.roi_ix, self.roi_iy = x, y
            print(f"🖱️ Inicio ROI: ({x}, {y})")
            
        elif event == cv2.EVENT_MOUSEMOVE:
            if self.drawing_roi and self.current_frame is not None:
                # Mostrar preview del ROI en tiempo real
                pass  # Se maneja en el bucle principal
                
        elif event == cv2.EVENT_LBUTTONUP:
            self.drawing_roi = False
            x1, y1 = min(self.roi_ix, x), min(self.roi_iy, y)
            x2, y2 = max(self.roi_ix, x), max(self.roi_iy, y)
            self.roi_points = (x1, y1, x2, y2)
            print(f"🖱️ ROI completo: ({x1}, {y1}) -> ({x2}, {y2})")
            
            # AUTO-CENTRAR línea cuando se define ROI
            self.auto_center_line_to_roi()
    
    def handle_line_mouse(self, event, x, y, flags, param):
        """Manejar eventos de mouse para línea angular (CTRL + Click)"""
        if event == cv2.EVENT_LBUTTONDOWN:
            # Verificar que el click esté dentro del ROI
            if self.roi_points and self.is_point_in_roi(x, y):
                self.line_center = (x, y)
                self.defining_line = True
                print(f"📐 Centro de línea: ({x}, {y})")
            elif not self.roi_points:
                print("❌ Primero define un ROI")
            else:
                print("❌ Click dentro del ROI para definir línea")
                
        elif event == cv2.EVENT_MOUSEMOVE and self.defining_line and self.line_center:
            # Calcular ángulo en tiempo real (CTRL + Move)
            center_x, center_y = self.line_center
            dx = x - center_x
            dy = y - center_y
            
            # Calcular ángulo (0-360 grados)
            angle_rad = math.atan2(dy, dx)
            angle_deg = math.degrees(angle_rad)
            if angle_deg < 0:
                angle_deg += 360
                
            self.line_angle = angle_deg
            
        elif event == cv2.EVENT_LBUTTONUP:
            self.defining_line = False
            if self.line_center:
                print(f"📐 Línea definida: Centro{self.line_center}, Ángulo:{self.line_angle:.1f}°")
            
        elif event == cv2.EVENT_MOUSEWHEEL and self.line_center:
            # Ajustar longitud con scroll wheel (solo si hay línea)
            if flags > 0:  # Scroll up
                self.line_length = min(800, self.line_length + 20)
            else:  # Scroll down
                self.line_length = max(100, self.line_length - 20)
            print(f"📏 Longitud de línea: {self.line_length}px")
    
    def is_point_in_roi(self, x, y):
        """Verificar si un punto está dentro del ROI"""
        if not self.roi_points:
            return False
        x1, y1, x2, y2 = self.roi_points
        return x1 <= x <= x2 and y1 <= y <= y2
    
    def auto_center_line_to_roi(self):
        """AUTO-CENTRAR línea al centro del ROI"""
        if not self.roi_points:
            return False
            
        x1, y1, x2, y2 = self.roi_points
        center_x = (x1 + x2) // 2
        center_y = (y1 + y2) // 2
        
        old_center = self.line_center
        self.line_center = (center_x, center_y)
        
        if old_center:
            print(f"🔄 Línea recentrada: {old_center} → {self.line_center}")
        else:
            print(f"🎯 Línea centrada automáticamente: {self.line_center}")
            
        return True
    
    def calculate_line_endpoints(self):
        """Calcular puntos de inicio y fin de la línea"""
        if not self.line_center:
            return None, None
            
        center_x, center_y = self.line_center
        angle_rad = math.radians(self.line_angle)
        half_length = self.line_length / 2
        
        start_x = int(center_x - math.cos(angle_rad) * half_length)
        start_y = int(center_y - math.sin(angle_rad) * half_length)
        end_x = int(center_x + math.cos(angle_rad) * half_length)
        end_y = int(center_y + math.sin(angle_rad) * half_length)
        
        return (start_x, start_y), (end_x, end_y)
    
    def draw_all_annotations(self, frame):
        """Dibujar todas las anotaciones en un solo frame"""
        display_frame = frame.copy()
        h, w = display_frame.shape[:2]
        
        # 1. Información general
        cv2.putText(display_frame, f"CALIBRADOR ROI + LINEA | Frame: {w}x{h}", 
                   (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
        
        # 2. Dibujar ROI (existente o en proceso)
        if self.drawing_roi and self.current_mouse_pos:
            # ROI en proceso
            cv2.rectangle(display_frame, (self.roi_ix, self.roi_iy), self.current_mouse_pos, (0, 255, 0), 2)
            cv2.putText(display_frame, "Dibujando ROI...", (10, 60), 
                       cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        elif self.roi_points:
            # ROI definido
            x1, y1, x2, y2 = self.roi_points
            cv2.rectangle(display_frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
            
            roi_w, roi_h = x2 - x1, y2 - y1
            cv2.putText(display_frame, f"ROI: ({x1},{y1})->({x2},{y2}) | {roi_w}x{roi_h}", 
                       (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        # 3. Dibujar línea angular (si existe)
        if self.line_center and self.roi_points:
            start_point, end_point = self.calculate_line_endpoints()
            
            if start_point and end_point:
                # Línea principal
                cv2.line(display_frame, start_point, end_point, (0, 255, 255), 4)
                
                # Centro de línea
                cv2.circle(display_frame, self.line_center, 8, (255, 0, 0), -1)
                
                # Zona buffer
                self.draw_buffer_zone(display_frame, start_point, end_point)
                
                # Flecha de dirección
                self.draw_direction_arrow(display_frame, start_point, end_point)
                
                # Info de línea
                cv2.putText(display_frame, f"Linea: Centro{self.line_center} | Angulo:{self.line_angle:.1f}°", 
                           (10, 90), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
                cv2.putText(display_frame, f"Longitud:{self.line_length}px | Buffer:{self.line_buffer}px | {'Invertida' if self.entry_inverted else 'Normal'}", 
                           (10, 120), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        
        # 4. Estado actual y ayuda
        if not self.roi_points:
            cv2.putText(display_frame, "1. CLICK + ARRASTRA para definir ROI", 
                       (10, h-80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        elif not self.line_center:
            cv2.putText(display_frame, "2. CLICK dentro del ROI para centro de linea", 
                       (10, h-80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        else:
            cv2.putText(display_frame, "3. Usa FLECHAS para rotar - S para guardar", 
                       (10, h-80), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        
        # 5. Instrucciones simples
        cv2.putText(display_frame, "FLECHAS=Rotar | SCROLL=Longitud | R=Recentrar | I=Invertir", 
                   (10, h-50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        cv2.putText(display_frame, "S=Guardar | C=Limpiar | Q=Salir", 
                   (10, h-30), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        
        return display_frame
    
    def draw_buffer_zone(self, frame, start_point, end_point):
        """Dibujar zona buffer alrededor de línea"""
        start_x, start_y = start_point
        end_x, end_y = end_point
        
        # Vector perpendicular para buffer
        dx = end_x - start_x
        dy = end_y - start_y
        length = math.sqrt(dx**2 + dy**2)
        
        if length == 0:
            return
            
        perp_dx = -dy / length * self.line_buffer
        perp_dy = dx / length * self.line_buffer
        
        # Líneas buffer paralelas
        start_buf1 = (int(start_x + perp_dx), int(start_y + perp_dy))
        end_buf1 = (int(end_x + perp_dx), int(end_y + perp_dy))
        start_buf2 = (int(start_x - perp_dx), int(start_y - perp_dy))
        end_buf2 = (int(end_x - perp_dx), int(end_y - perp_dy))
        
        cv2.line(frame, start_buf1, end_buf1, (255, 255, 0), 2)
        cv2.line(frame, start_buf2, end_buf2, (255, 255, 0), 2)
    
    def draw_direction_arrow(self, frame, start_point, end_point):
        """Dibujar flecha indicando dirección de entrada"""
        start_x, start_y = start_point
        end_x, end_y = end_point
        
        # Punto medio de la línea
        mid_x = (start_x + end_x) // 2
        mid_y = (start_y + end_y) // 2
        
        # Vector perpendicular (dirección de entrada)
        dx = end_x - start_x
        dy = end_y - start_y
        length = math.sqrt(dx**2 + dy**2)
        
        if length == 0:
            return
            
        normal_dx = -dy / length
        normal_dy = dx / length
        
        # Invertir si está configurado
        if self.entry_inverted:
            normal_dx = -normal_dx
            normal_dy = -normal_dy
        
        # Dibujar flecha
        arrow_length = 30
        arrow_end_x = int(mid_x + normal_dx * arrow_length)
        arrow_end_y = int(mid_y + normal_dy * arrow_length)
        
        cv2.arrowedLine(frame, (mid_x, mid_y), (arrow_end_x, arrow_end_y), 
                       (255, 0, 255), 3, tipLength=0.3)
        
        # Etiqueta
        cv2.putText(frame, "ENTRADA", (arrow_end_x + 10, arrow_end_y), 
                   cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 255), 2)
    
    def calibrate_roi(self):
        """Calibrar ROI y línea en una sola pantalla"""
        rtsp_url = self.config["ffmpeg"]["input_source"]
        print(f"🎥 Conectando a: {rtsp_url}")
        
        cap = cv2.VideoCapture(rtsp_url)
        if not cap.isOpened():
            print(f"❌ No se pudo conectar al stream")
            return False
            
        # Configurar ventana
        window_name = 'ROI + Linea Calibrator'
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 1280, 720)
        cv2.setMouseCallback(window_name, self.mouse_callback)
        
        self.show_instructions()
        
        # Capturar primer frame
        ret, frame = cap.read()
        if not ret:
            print("❌ No se pudo leer frame inicial")
            cap.release()
            return False
            
        resized_frame, orig_w, orig_h = self.resize_frame(frame)
        self.current_frame = resized_frame.copy()
        
        print(f"📐 Frame original: {orig_w}x{orig_h}")
        print(f"📐 Frame procesado: {resized_frame.shape[1]}x{resized_frame.shape[0]}")
        
        while True:
            # Leer nuevo frame
            ret, frame = cap.read()
            if ret:
                resized_frame, _, _ = self.resize_frame(frame)
                self.current_frame = resized_frame.copy()
            
            # Crear frame con todas las anotaciones
            display_frame = self.draw_all_annotations(self.current_frame)
            
            cv2.imshow(window_name, display_frame)
            
            # Manejar teclas
            key = cv2.waitKey(30) & 0xFF
            
            if key == ord('q'):
                print("🚪 Saliendo...")
                break
                
            elif key == ord('c'):
                print("🧹 Limpiando todo...")
                self.roi_points = None
                self.line_center = None
                self.line_angle = 0
                
            elif key == ord('r'):
                # Recentrar línea al ROI
                if self.roi_points:
                    self.auto_center_line_to_roi()
                else:
                    print("❌ Primero define un ROI")
                
            elif key == ord('i'):
                # Invertir dirección
                self.entry_inverted = not self.entry_inverted
                direction = "INVERTIDA" if self.entry_inverted else "NORMAL"
                print(f"🔄 Dirección: {direction}")
                
            elif key == ord('+') or key == ord('='):
                # Aumentar buffer
                self.line_buffer = min(50, self.line_buffer + 5)
                print(f"📏 Buffer: {self.line_buffer}px")
                
            elif key == ord('-'):
                # Disminuir buffer
                self.line_buffer = max(5, self.line_buffer - 5)
                print(f"📏 Buffer: {self.line_buffer}px")
                
            # FLECHAS PARA ROTAR LÍNEA (SÚPER SIMPLE)
            elif key == 81 or key == 0:  # Flecha izquierda
                if self.line_center:
                    self.line_angle = (self.line_angle - 5) % 360
                    print(f"↺ Ángulo: {self.line_angle:.0f}°")
                    
            elif key == 83 or key == 1:  # Flecha derecha  
                if self.line_center:
                    self.line_angle = (self.line_angle + 5) % 360
                    print(f"↻ Ángulo: {self.line_angle:.0f}°")
                    
            elif key == 82 or key == 2:  # Flecha arriba
                if self.line_center:
                    self.line_angle = (self.line_angle - 1) % 360
                    print(f"↺ Ángulo: {self.line_angle:.0f}°")
                    
            elif key == 84 or key == 3:  # Flecha abajo
                if self.line_center:
                    self.line_angle = (self.line_angle + 1) % 360  
                    print(f"↻ Ángulo: {self.line_angle:.0f}°")
                
            elif key == ord('s'):
                # Guardar
                if self.roi_points and self.line_center:
                    success = self.save_config()
                    if success:
                        print("✅ ¡Guardado exitosamente!")
                        break
                elif not self.roi_points:
                    print("❌ Primero define ROI (click + arrastra)")
                elif not self.line_center:
                    print("❌ Primero define línea (click dentro del ROI)")
                
        cap.release()
        cv2.destroyAllWindows()
        return True
    
    def show_instructions(self):
        """Mostrar instrucciones SÚPER SIMPLES"""
        print("\n" + "="*60)
        print("📋 CALIBRADOR SIMPLE - INSTRUCCIONES:")
        print("="*60)
        print("🖱️  CLICK + ARRASTRA - Definir ROI")
        print("🖱️  CLICK (dentro ROI) - Centro de línea")  
        print("🔄 SCROLL - Longitud de línea")
        print()
        print("🔑 ← → - Rotar línea (5°)")
        print("🔑 ↑ ↓ - Rotar línea (1°)")
        print("🔑 'R' - Recentrar línea")
        print("🔑 'I' - Invertir entrada/salida")
        print("🔑 '+/-' - Ajustar buffer")
        print("🔑 'S' - Guardar")
        print("🔑 'Q' - Salir")
        print("="*60)
    
    def save_config(self):
        """Guardar configuración completa (ROI + línea)"""
        try:
            # Guardar ROI
            x1, y1, x2, y2 = self.roi_points
            self.config["roi"] = {
                "x1": int(x1),
                "y1": int(y1),
                "x2": int(x2),
                "y2": int(y2)
            }
            
            # Guardar línea angular
            self.config["counting"].update({
                "line_type": "angular",
                "line_center_x": self.line_center[0],
                "line_center_y": self.line_center[1],
                "line_angle": self.line_angle,
                "line_length": self.line_length,
                "line_buffer": self.line_buffer,
                "entry_inverted": self.entry_inverted
            })
            
            # Escribir archivo
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
                
            print(f"\n✅ Configuración guardada en {self.config_file}")
            print(f"📦 ROI: ({x1},{y1}) -> ({x2},{y2}) | {x2-x1}x{y2-y1}")
            print(f"📐 Línea: Centro{self.line_center} | Ángulo:{self.line_angle:.1f}° | Longitud:{self.line_length}px")
            print(f"🔧 Buffer:{self.line_buffer}px | Entrada:{'Invertida' if self.entry_inverted else 'Normal'}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error guardando configuración: {e}")
            return False

def main():
    """Función principal"""
    print("🚀 Calibrador SIMPLE - ROI + Línea Angular")
    print("="*50)
    
    calibrator = ROICalibrator()
    
    if calibrator.config is None:
        print("❌ No se pudo cargar la configuración")
        return
        
    print(f"📋 Configuración actual:")
    print(f"   Stream: {calibrator.config['ffmpeg']['input_source']}")
    print(f"   Resolución: {calibrator.config['ffmpeg']['resolution']}")
    
    # Mostrar configuración actual
    if "roi" in calibrator.config:
        roi = calibrator.config["roi"]
        print(f"   ROI: ({roi['x1']},{roi['y1']}) -> ({roi['x2']},{roi['y2']})")
    
    if "counting" in calibrator.config and calibrator.config["counting"].get("line_type") == "angular":
        counting = calibrator.config["counting"]
        print(f"   Línea: Centro({counting['line_center_x']},{counting['line_center_y']}) "
              f"Ángulo:{counting['line_angle']}°")
    
    input("\n🔑 Presiona ENTER para calibrar...")
    
    calibrator.calibrate_roi()
    print("\n🏁 ¡Listo!")

if __name__ == "__main__":
    main()