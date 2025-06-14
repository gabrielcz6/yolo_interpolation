#!/usr/bin/env python3
"""
Gestor de configuración para el sistema de conteo de personas
"""

import json
from pathlib import Path


class ConfigManager:
    def __init__(self, config_file="config.json"):
        """Inicializar gestor de configuración"""
        self.config_file = config_file
        self.config = self.load_config()
        
    def get_default_config(self):
        """Obtener configuración por defecto"""
        return {
            "ffmpeg": {
                "input_source": "rtmp://localhost/live/stream",
                "segment_duration": 15,
                "video_format": "mp4",
                "resolution": "1280x720",
                "fps": 30
            },
            "detection": {
                "model_path": "yolov8n.pt",
                "confidence": 0.5,
                "classes": [0],  # Solo personas (clase 0 en COCO)
                "device": "cpu"  # Cambiar a "0" para GPU
            },
            "roi": {
                "x1": 100,
                "y1": 100, 
                "x2": 1180,
                "y2": 620
            },
            "image": {
                "rotation": 0  # 0, 90, 180, 270 grados
            },
            "counting": {
                "line_position": 0.5,  # 50% de la altura del ROI
                "direction_threshold": 20,  # pixels para determinar dirección
                "tracking_history": 30  # frames para mantener tracking
            },
            "tracking": {
                "max_disappeared": 20,
                "max_distance": 80
            },
            "paths": {
                "videos_dir": "./videos",
                "output_dir": "./output",
                "logs_dir": "./logs"
            }
        }
        
    def load_config(self):
        """Cargar configuración desde archivo JSON"""
        try:
            with open(self.config_file, 'r') as f:
                config = json.load(f)
                print(f"✅ Configuración cargada desde {self.config_file}")
                return config
        except FileNotFoundError:
            print(f"⚠️ Archivo {self.config_file} no encontrado. Creando configuración por defecto...")
            default_config = self.get_default_config()
            self.save_config(default_config)
            return default_config
            
    def save_config(self, config=None):
        """Guardar configuración a archivo"""
        config_to_save = config if config else self.config
        with open(self.config_file, 'w') as f:
            json.dump(config_to_save, f, indent=4)
        print(f"💾 Configuración guardada en {self.config_file}")
        
    def setup_directories(self):
        """Crear directorios necesarios"""
        for dir_path in self.config["paths"].values():
            Path(dir_path).mkdir(parents=True, exist_ok=True)
        print("📁 Directorios configurados")
        
    def get(self, key_path, default=None):
        """Obtener valor de configuración usando notación de punto"""
        keys = key_path.split('.')
        value = self.config
        
        try:
            for key in keys:
                value = value[key]
            return value
        except (KeyError, TypeError):
            return default
            
    def set(self, key_path, value):
        """Establecer valor de configuración usando notación de punto"""
        keys = key_path.split('.')
        config_ref = self.config
        
        for key in keys[:-1]:
            if key not in config_ref:
                config_ref[key] = {}
            config_ref = config_ref[key]
            
        config_ref[keys[-1]] = value
