#!/usr/bin/env python3
"""
Implementación del algoritmo SORT (Simple Online and Realtime Tracking)
Versión simplificada para tracking de personas
"""

import numpy as np
from scipy.spatial import distance as dist
from collections import OrderedDict


class SortTracker:
    def __init__(self, max_disappeared=20, max_distance=80):
        """
        Inicializar el tracker SORT
        
        Args:
            max_disappeared: Número máximo de frames que un objeto puede estar ausente
            max_distance: Distancia máxima para considerar una asociación válida
        """
        self.next_object_id = 0
        self.objects = OrderedDict()
        self.disappeared = OrderedDict()
        self.max_disappeared = max_disappeared
        self.max_distance = max_distance
        
    def register(self, centroid):
        """Registrar un nuevo objeto"""
        self.objects[self.next_object_id] = centroid
        self.disappeared[self.next_object_id] = 0
        self.next_object_id += 1
        
    def deregister(self, object_id):
        """Desregistrar un objeto"""
        del self.objects[object_id]
        del self.disappeared[object_id]
        
    def update(self, rects):
        """
        Actualizar el tracker con nuevas detecciones
        
        Args:
            rects: Lista de bounding boxes [(x1, y1, x2, y2), ...]
            
        Returns:
            OrderedDict con {object_id: (center_x, center_y)}
        """
        # Si no hay detecciones, marcar todos los objetos como desaparecidos
        if len(rects) == 0:
            for object_id in list(self.disappeared.keys()):
                self.disappeared[object_id] += 1
                
                # Eliminar objetos que han desaparecido por demasiado tiempo
                if self.disappeared[object_id] > self.max_disappeared:
                    self.deregister(object_id)
                    
            return self.objects
            
        # Calcular centroides de las detecciones
        input_centroids = np.zeros((len(rects), 2), dtype="int")
        for (i, (start_x, start_y, end_x, end_y)) in enumerate(rects):
            center_x = int((start_x + end_x) / 2.0)
            center_y = int((start_y + end_y) / 2.0)
            input_centroids[i] = (center_x, center_y)
            
        # Si no hay objetos existentes, registrar todos los centroides
        if len(self.objects) == 0:
            for centroid in input_centroids:
                self.register(centroid)
                
        else:
            # Obtener centroides de objetos existentes
            object_centroids = list(self.objects.values())
            object_ids = list(self.objects.keys())
            
            # Calcular distancias entre objetos existentes y nuevas detecciones
            D = dist.cdist(np.array(object_centroids), input_centroids)
            
            # Encontrar las asociaciones óptimas
            rows = D.min(axis=1).argsort()
            cols = D.argmin(axis=1)[rows]
            
            # Conjuntos para rastrear índices usados
            used_row_idxs = set()
            used_col_idxs = set()
            
            # Asociar objetos existentes con detecciones
            for (row, col) in zip(rows, cols):
                # Si ya hemos usado este índice, ignorar
                if row in used_row_idxs or col in used_col_idxs:
                    continue
                    
                # Si la distancia es demasiado grande, ignorar
                if D[row, col] > self.max_distance:
                    continue
                    
                # Actualizar el centroide del objeto
                object_id = object_ids[row]
                self.objects[object_id] = input_centroids[col]
                self.disappeared[object_id] = 0
                
                # Marcar índices como usados
                used_row_idxs.add(row)
                used_col_idxs.add(col)
                
            # Calcular índices no utilizados
            unused_row_idxs = set(range(0, D.shape[0])).difference(used_row_idxs)
            unused_col_idxs = set(range(0, D.shape[1])).difference(used_col_idxs)
            
            # Si hay más objetos que detecciones, marcar objetos como desaparecidos
            if D.shape[0] >= D.shape[1]:
                for row in unused_row_idxs:
                    object_id = object_ids[row]
                    self.disappeared[object_id] += 1
                    
                    # Eliminar si ha desaparecido demasiado tiempo
                    if self.disappeared[object_id] > self.max_disappeared:
                        self.deregister(object_id)
                        
            # Si hay más detecciones que objetos, registrar nuevos objetos
            else:
                for col in unused_col_idxs:
                    self.register(input_centroids[col])
                    
        return self.objects
        
    def get_object_count(self):
        """Obtener número de objetos actualmente trackeados"""
        return len(self.objects)
        
    def get_disappeared_count(self):
        """Obtener número de objetos marcados como desaparecidos"""
        return sum(1 for count in self.disappeared.values() if count > 0)
        
    def reset(self):
        """Reiniciar el tracker"""
        self.objects.clear()
        self.disappeared.clear()
        self.next_object_id = 0
        
    def get_objects_info(self):
        """Obtener información detallada de todos los objetos"""
        info = {}
        for object_id in self.objects.keys():
            info[object_id] = {
                'centroid': self.objects[object_id],
                'disappeared_frames': self.disappeared[object_id]
            }
        return info