#!/usr/bin/env python3
"""
Filtro de personas usando modelo ONNX
Para excluir personal de la tienda del conteo
"""

import cv2
import numpy as np
import onnxruntime as ort
import os


class PersonFilter:
    def __init__(self, config):
        """Inicializar filtro de personas"""
        self.config = config
        self.filter_config = config.get("person_filter", {})
        
        # Verificar si el filtro está habilitado
        self.enabled = self.filter_config.get("enabled", False)
        
        if not self.enabled:
            print("🔇 Filtro de personas DESHABILITADO")
            self.session = None
            return
            
        # Configuración del modelo
        self.model_path = self.filter_config.get("model_path", "person_filter.onnx")
        self.confidence_threshold = self.filter_config.get("confidence_threshold", 0.7)
        self.input_size = tuple(self.filter_config.get("input_size", [224, 224]))
        
        # Cargar modelo ONNX
        self.session = None
        self.input_name = None
        self.output_name = None
        self.load_model()
        
    def load_model(self):
        """Cargar modelo ONNX"""
        if not os.path.exists(self.model_path):
            print(f"❌ Modelo ONNX no encontrado: {self.model_path}")
            print("🔇 Filtro de personas DESHABILITADO")
            self.enabled = False
            return False
            
        try:
            print(f"🧠 Cargando modelo de filtro: {self.model_path}")
            
            # Crear sesión ONNX
            providers = ['CPUExecutionProvider']
            if self.filter_config.get("device", "cpu").lower() != "cpu":
                providers.insert(0, 'CUDAExecutionProvider')
                
            self.session = ort.InferenceSession(self.model_path, providers=providers)
            
            # Obtener nombres de entrada y salida
            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name
            
            # Verificar dimensiones
            input_shape = self.session.get_inputs()[0].shape
            print(f"✅ Modelo cargado exitosamente")
            print(f"   Entrada: {input_shape}")
            print(f"   Tamaño procesamiento: {self.input_size}")
            print(f"   Umbral confianza: {self.confidence_threshold}")
            
            return True
            
        except Exception as e:
            print(f"❌ Error cargando modelo ONNX: {e}")
            print("🔇 Filtro de personas DESHABILITADO")
            self.enabled = False
            self.session = None
            return False
    
    def is_store_staff(self, frame, center_x, center_y, bbox_width=100, bbox_height=150):
        """
        Determinar si una persona es personal de la tienda
        
        Args:
            frame: Frame actual (ya recortado por ROI)
            center_x, center_y: Centro de la persona detectada
            bbox_width, bbox_height: Tamaño del recorte alrededor de la persona
            
        Returns:
            tuple: (is_staff, confidence)
        """
        
        # Si el filtro está deshabilitado, considerar que NO es personal
        if not self.enabled or self.session is None:
            return False, 0.0
            
        try:
            # Extraer región de la persona
            person_roi = self._extract_person_roi(frame, center_x, center_y, bbox_width, bbox_height)
            
            if person_roi is None:
                print("⚠️ No se pudo extraer ROI de la persona")
                return False, 0.0
            
            # Preprocesar imagen para el modelo
            processed_image = self._preprocess_image(person_roi)
            
                        # Ejecutar inferencia
            # Ejecutar inferencia
            outputs = self.session.run([self.output_name], {self.input_name: processed_image})
            raw_logits = outputs[0]
            
            # Aplicar softmax manualmente
            probs = self._softmax(raw_logits[0])  # [prob_personal_h, prob_personal_m, prob_seguridad]
            
            # Obtener índice con mayor probabilidad
            pred_index = int(np.argmax(probs))
            
            # Obtener la máxima probabilidad
            max_confidence = float(probs[pred_index])
            
            # Si cualquier clase supera el umbral → es personal de tienda
            is_staff = max_confidence >= self.confidence_threshold
            
            # Para logging
            class_names = ["Personal-H", "Personal-M", "Seguridad"]
            detected_class = class_names[pred_index]
            
            # Para logging, mostrar la probabilidad de la clase predicha
            staff_confidence = float(probs[pred_index])
            
            is_staff = staff_confidence >= self.confidence_threshold
            
            # Log para debugging
            staff_status = "PERSONAL" if is_staff else "CLIENTE"
            print(f"🔍 Filtro: {staff_status} (confianza: {staff_confidence:.3f})")
            
            return is_staff, staff_confidence
            
        except Exception as e:
            print(f"❌ Error en filtro de personas: {e}")
            # En caso de error, asumir que NO es personal (contar normalmente)
            return False, 0.0
    
    def _extract_person_roi(self, frame, center_x, center_y, width, height):
        """Extraer región de interés alrededor de la persona"""
        try:
            frame_height, frame_width = frame.shape[:2]
            
            # Calcular coordenadas del recorte
            x1 = max(0, center_x - width // 2)
            y1 = max(0, center_y - height // 2)
            x2 = min(frame_width, center_x + width // 2)
            y2 = min(frame_height, center_y + height // 2)
            
            # Verificar que el recorte sea válido
            if x2 <= x1 or y2 <= y1:
                return None
                
            # Extraer ROI
            person_roi = frame[y1:y2, x1:x2]
            
            # Verificar que el ROI no esté vacío
            if person_roi.size == 0:
                return None
                
            return person_roi
            
        except Exception as e:
            print(f"❌ Error extrayendo ROI de persona: {e}")
            return None
    
    def _preprocess_image(self, image):
        """Preprocesar imagen para el modelo ONNX"""
        try:
            # Redimensionar a tamaño esperado por el modelo
            resized = cv2.resize(image, self.input_size)
            
            # Convertir BGR a RGB si es necesario
            if len(resized.shape) == 3 and resized.shape[2] == 3:
                resized = cv2.cvtColor(resized, cv2.COLOR_BGR2RGB)
            
            # Normalizar (0-255 -> 0-1)
            normalized = resized.astype(np.float32) / 255.0
            
            # Cambiar dimensiones para el modelo (HWC -> CHW)
            if len(normalized.shape) == 3:
                transposed = np.transpose(normalized, (2, 0, 1))
            else:
                transposed = normalized
            
            # Agregar dimensión de batch
            batched = np.expand_dims(transposed, axis=0)
            
            return batched
            
        except Exception as e:
            print(f"❌ Error preprocesando imagen: {e}")
            return None
    def _softmax(self, logits):
        """Aplicar softmax manualmente (sin torch)"""
        try:
            # Restar el máximo para estabilidad numérica
            exp_logits = np.exp(logits - np.max(logits))
            return exp_logits / np.sum(exp_logits)
        except Exception as e:
            print(f"❌ Error en softmax: {e}")
            return logits  # Fallback
    

    def get_filter_stats(self):
        """Obtener estadísticas del filtro"""
        return {
            "enabled": self.enabled,
            "model_loaded": self.session is not None,
            "model_path": self.model_path,
            "confidence_threshold": self.confidence_threshold,
            "input_size": self.input_size
        }
    
    def set_threshold(self, new_threshold):
        """Cambiar umbral de confianza dinámicamente"""
        if 0.0 <= new_threshold <= 1.0:
            old_threshold = self.confidence_threshold
            self.confidence_threshold = new_threshold
            print(f"🎯 Umbral filtro cambiado: {old_threshold:.2f} -> {new_threshold:.2f}")
            return True
        else:
            print(f"❌ Umbral inválido: {new_threshold} (debe estar entre 0.0 y 1.0)")
            return False
    
    def toggle_filter(self):
        """Activar/desactivar filtro dinámicamente"""
        if self.session is not None:
            self.enabled = not self.enabled
            status = "HABILITADO" if self.enabled else "DESHABILITADO"
            print(f"🔄 Filtro de personas {status}")
            return self.enabled
        else:
            print("❌ No se puede activar: modelo no cargado")
            return False
    
    def test_filter(self, test_image_path):
        """Probar filtro con imagen de prueba"""
        if not self.enabled or self.session is None:
            print("❌ Filtro no disponible para pruebas")
            return None
            
        try:
            # Cargar imagen de prueba
            test_image = cv2.imread(test_image_path)
            if test_image is None:
                print(f"❌ No se pudo cargar imagen: {test_image_path}")
                return None
            
            # Simular detección en el centro de la imagen
            h, w = test_image.shape[:2]
            center_x, center_y = w // 2, h // 2
            
            # Ejecutar filtro
            is_staff, confidence = self.is_store_staff(test_image, center_x, center_y)
            
            result = {
                "image_path": test_image_path,
                "is_staff": is_staff,
                "confidence": confidence,
                "classification": "PERSONAL" if is_staff else "CLIENTE"
            }
            
            print(f"🧪 Prueba filtro:")
            print(f"   Imagen: {test_image_path}")
            print(f"   Resultado: {result['classification']}")
            print(f"   Confianza: {confidence:.3f}")
            
            return result
            
        except Exception as e:
            print(f"❌ Error en prueba de filtro: {e}")
            return None
