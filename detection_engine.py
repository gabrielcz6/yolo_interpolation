#!/usr/bin/env python3
"""
Motor de detección usando YOLOv8
"""

import cv2
import numpy as np
from ultralytics import YOLO


class DetectionEngine:
    def __init__(self, config):
        """Inicializar motor de detección"""
        self.config = config
        self.model = None
        self.load_model()
        
    def load_model(self):
        """Cargar modelo YOLOv8"""
        print("🧠 Cargando modelo YOLOv8...")
        try:
            self.model = YOLO(self.config["detection"]["model_path"])
            print("✅ Modelo YOLOv8 cargado exitosamente!")
        except Exception as e:
            print(f"❌ Error cargando modelo: {e}")
            raise
            
    def detect_people(self, frame):
        """Detectar personas usando YOLOv8"""
        if self.model is None:
            print("⚠️ Modelo no cargado")
            return []
            
        try:
            results = self.model(
                frame,
                conf=self.config["detection"]["confidence"],
                classes=self.config["detection"]["classes"],
                device=self.config["detection"]["device"],
                verbose=False
            )
            
            detections = []
            if results[0].boxes is not None:
                boxes = results[0].boxes.xyxy.cpu().numpy()
                confidences = results[0].boxes.conf.cpu().numpy()
                
                for box, conf in zip(boxes, confidences):
                    x1, y1, x2, y2 = box.astype(int)
                    detections.append((x1, y1, x2, y2, conf))
                    
            return detections
            
        except Exception as e:
            print(f"⚠️ Error en detección: {e}")
            return []
            
    def crop_frame(self, frame):
        """Recortar frame con coordenadas ROI y aplicar rotación"""
        roi = self.config["roi"]
        # Primero recortar
        cropped_frame = frame[roi["y1"]:roi["y2"], roi["x1"]:roi["x2"]]
        
        # Luego aplicar rotación si está configurada
        if "image" in self.config and self.config["image"]["rotation"] != 0:
            cropped_frame = self._rotate_frame(cropped_frame, self.config["image"]["rotation"])
        
        return cropped_frame
        
    def _rotate_frame(self, frame, angle):
        """Rotar frame según ángulo especificado"""
        if angle == 90:
            return cv2.rotate(frame, cv2.ROTATE_90_CLOCKWISE)
        elif angle == 180:
            return cv2.rotate(frame, cv2.ROTATE_180)
        elif angle == 270:
            return cv2.rotate(frame, cv2.ROTATE_90_COUNTERCLOCKWISE)
        else:
            return frame
            
    def get_roi_dimensions(self):
        """Obtener dimensiones del ROI"""
        roi = self.config["roi"]
        width = roi["x2"] - roi["x1"]
        height = roi["y2"] - roi["y1"]
        return width, height
        
    def is_model_loaded(self):
        """Verificar si el modelo está cargado"""
        return self.model is not None
