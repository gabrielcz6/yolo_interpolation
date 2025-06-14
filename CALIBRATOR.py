#!/usr/bin/env python3
"""
Calibrador de ROI - Redimensiona primero - VERSIÓN FUNCIONAL
"""

import cv2
import json

class ROICalibrator:
    def __init__(self, config_file="config.json"):
        """Inicializar calibrador"""
        self.config_file = config_file
        self.config = self.load_config()
        
        # Variables para dibujo del ROI
        self.drawing = False
        self.ix, self.iy = -1, -1
        self.roi_points = None
        self.current_frame = None
        
    def load_config(self):
        """Cargar configuración actual"""
        try:
            with open(self.config_file, 'r') as f:
                return json.load(f)
        except FileNotFoundError:
            print(f"❌ No se encontró {self.config_file}")
            return None
            
    def draw_rectangle(self, event, x, y, flags, param):
        """Función para dibujar rectángulo ROI"""
        if event == cv2.EVENT_LBUTTONDOWN:
            self.drawing = True
            self.ix, self.iy = x, y
            print(f"🖱️ Inicio ROI: ({x}, {y})")
            
        elif event == cv2.EVENT_MOUSEMOVE:
            if self.drawing and self.current_frame is not None:
                # Hacer copia del frame para dibujar
                img_copy = self.current_frame.copy()
                cv2.rectangle(img_copy, (self.ix, self.iy), (x, y), (0, 255, 0), 2)
                cv2.imshow('ROI Calibrator', img_copy)
                
        elif event == cv2.EVENT_LBUTTONUP:
            self.drawing = False
            # Guardar coordenadas finales
            x1, y1 = min(self.ix, x), min(self.iy, y)
            x2, y2 = max(self.ix, x), max(self.iy, y)
            self.roi_points = (x1, y1, x2, y2)
            print(f"🖱️ ROI completo: ({x1}, {y1}) -> ({x2}, {y2})")
            
    def resize_frame(self, frame):
        """Redimensionar frame según configuración FFmpeg"""
        target_resolution = self.config["ffmpeg"]["resolution"]
        target_width, target_height = map(int, target_resolution.split('x'))
        
        original_height, original_width = frame.shape[:2]
        
        # Redimensionar exactamente como lo hace FFmpeg
        resized_frame = cv2.resize(frame, (target_width, target_height))
        return resized_frame, original_width, original_height
        
    def calibrate_roi(self):
        """Calibrar ROI desde el stream RTSP"""
        rtsp_url = self.config["ffmpeg"]["input_source"]
        print(f"🎥 Conectando a: {rtsp_url}")
        
        # Conectar al stream
        cap = cv2.VideoCapture(rtsp_url)
        if not cap.isOpened():
            print(f"❌ No se pudo conectar al stream")
            return False
            
        # Configurar ventana
        window_name = 'ROI Calibrator'
        cv2.namedWindow(window_name, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(window_name, 1280, 720)
        cv2.setMouseCallback(window_name, self.draw_rectangle)
        
        print("\n" + "="*60)
        print("📋 INSTRUCCIONES:")
        print("="*60)
        print("🖱️  CLICK y ARRASTRA para dibujar ROI")
        print("🔑 'S' - Guardar ROI seleccionado")
        print("🔑 'C' - Limpiar selección")
        print("🔑 'Q' - Salir sin guardar")
        print("="*60)
        
        # Capturar primer frame y redimensionar
        ret, frame = cap.read()
        if not ret:
            print("❌ No se pudo leer frame inicial")
            cap.release()
            return False
            
        resized_frame, orig_w, orig_h = self.resize_frame(frame)
        self.current_frame = resized_frame.copy()
        
        print(f"📐 Frame original: {orig_w}x{orig_h}")
        print(f"📐 Frame redimensionado: {resized_frame.shape[1]}x{resized_frame.shape[0]}")
        
        while True:
            # Leer nuevo frame cada cierto tiempo
            ret, frame = cap.read()
            if ret:
                resized_frame, _, _ = self.resize_frame(frame)
                self.current_frame = resized_frame.copy()
            
            # Crear frame de display
            display_frame = self.current_frame.copy()
            h, w = display_frame.shape[:2]
            
            # Añadir información del frame
            cv2.putText(display_frame, f"Frame: {w}x{h}", 
                       (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            # Dibujar ROI si existe
            if self.roi_points:
                x1, y1, x2, y2 = self.roi_points
                # Dibujar rectángulo ROI
                cv2.rectangle(display_frame, (x1, y1), (x2, y2), (0, 255, 0), 3)
                
                # Información del ROI
                roi_w, roi_h = x2 - x1, y2 - y1
                cv2.putText(display_frame, f"ROI: ({x1},{y1})->({x2},{y2})", 
                           (10, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                cv2.putText(display_frame, f"Tamaño: {roi_w}x{roi_h}", 
                           (10, 85), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                
                # Línea de conteo
                line_pos = self.config["counting"]["line_position"]
                line_y = y1 + int(roi_h * line_pos)
                cv2.line(display_frame, (x1, line_y), (x2, line_y), (255, 0, 0), 2)
                cv2.putText(display_frame, "COUNTING LINE", (x1 + 10, line_y - 10), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 2)
            
            # Instrucciones
            cv2.putText(display_frame, "CLICK y ARRASTRA para ROI", 
                       (10, h-60), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            cv2.putText(display_frame, "S=Guardar | C=Limpiar | Q=Salir", 
                       (10, h-30), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            
            cv2.imshow(window_name, display_frame)
            
            # Manejar teclas
            key = cv2.waitKey(30) & 0xFF
            
            if key == ord('q'):
                print("🚪 Saliendo sin guardar...")
                break
                
            elif key == ord('c'):
                print("🧹 Limpiando selección...")
                self.roi_points = None
                
            elif key == ord('s'):
                if self.roi_points:
                    x1, y1, x2, y2 = self.roi_points
                    if x2 > x1 and y2 > y1:
                        success = self.save_roi_config(x1, y1, x2, y2)
                        if success:
                            print("✅ ROI guardado exitosamente!")
                            break
                    else:
                        print("❌ ROI inválido")
                else:
                    print("❌ Primero selecciona un ROI")
                
        cap.release()
        cv2.destroyAllWindows()
        return True
        
    def save_roi_config(self, x1, y1, x2, y2):
        """Guardar configuración ROI actualizada"""
        try:
            # Actualizar ROI en config
            self.config["roi"] = {
                "x1": int(x1),
                "y1": int(y1),
                "x2": int(x2),
                "y2": int(y2)
            }
            
            # Guardar archivo
            with open(self.config_file, 'w') as f:
                json.dump(self.config, f, indent=4)
                
            print(f"\n✅ Configuración guardada en {self.config_file}")
            print("🎯 Nuevo ROI:")
            print(f"   \"roi\": {{")
            print(f"       \"x1\": {int(x1)},")
            print(f"       \"y1\": {int(y1)},")
            print(f"       \"x2\": {int(x2)},")
            print(f"       \"y2\": {int(y2)}")
            print(f"   }}")
            print(f"📏 Dimensiones: {int(x2-x1)}x{int(y2-y1)}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error guardando configuración: {e}")
            return False

def main():
    """Función principal"""
    print("🚀 ROI Calibrator - FUNCIONAL")
    print("="*50)
    
    calibrator = ROICalibrator()
    
    if calibrator.config is None:
        print("❌ No se pudo cargar la configuración")
        return
        
    print(f"📋 Configuración actual:")
    print(f"   Stream: {calibrator.config['ffmpeg']['input_source']}")
    print(f"   Resolución objetivo: {calibrator.config['ffmpeg']['resolution']}")
    print(f"   ROI actual: {calibrator.config['roi']}")
    
    input("\n🔑 Presiona ENTER para iniciar calibración...")
    
    calibrator.calibrate_roi()
    print("\n🏁 Calibración completada")

if __name__ == "__main__":
    main()