#!/usr/bin/env python3
"""
Módulo de captura de video usando FFmpeg
"""

import os
import subprocess
import threading
import time
from pathlib import Path


class FFmpegCapture:
    def __init__(self, config):
        """Inicializar capturador FFmpeg"""
        self.config = config
        self.running = False
        self.video_queue = []
        self.capture_thread = None
        
    def test_rtsp_connection(self):
        """Probar conexión RTSP antes de iniciar"""
        print("🔍 Probando conexión RTSP...")
        test_cmd = [
            'ffprobe',
            '-v', 'quiet',
            '-rtsp_transport', 'tcp',
            '-timeout', '10000000',  # 10 segundos
            '-i', self.config['ffmpeg']['input_source'],
            '-show_entries', 'format=duration',
            '-of', 'csv=p=0'
        ]
        
        try:
            result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=15)
            if result.returncode == 0:
                print("✅ Conexión RTSP exitosa!")
                return True
            else:
                print(f"❌ Error de conexión RTSP: {result.stderr}")
                return False
        except subprocess.TimeoutExpired:
            print("⏰ Timeout en prueba de conexión RTSP")
            return False
        except Exception as e:
            print(f"❌ Error probando conexión: {e}")
            return False
            
    def start_capture(self):
        """Iniciar captura con FFmpeg usando segmentación continua"""
        def capture_loop():
            while self.running:
                try:
                    print(f"🎬 Iniciando/Reiniciando captura con segmentación...")
                    
                    # Comando FFmpeg
                    ffmpeg_cmd = [
                        'ffmpeg',
                        '-y',
                        '-loglevel', 'error',
                        '-rtsp_transport', 'tcp',
                        '-rtbufsize', '400M',
                        '-i', self.config['ffmpeg']['input_source'],
                        '-c:v', 'libx264',
                        '-preset', 'ultrafast',
                        '-s', self.config['ffmpeg']['resolution'],
                        '-r', str(self.config['ffmpeg']['fps']),
                        '-f', 'segment',
                        '-segment_time', str(self.config['ffmpeg']['segment_duration']),
                        '-segment_format', self.config['ffmpeg']['video_format'],
                        '-segment_list_flags', '+live',
                        '-segment_wrap', '0',
                        '-reset_timestamps', '1',
                        f"{self.config['paths']['videos_dir']}/segment_%09d.{self.config['ffmpeg']['video_format']}"
                    ]
                    
                    print(f"🔧 Ejecutando FFmpeg...")
                    
                    # Ejecutar FFmpeg
                    process = subprocess.Popen(
                        ffmpeg_cmd, 
                        stdout=subprocess.PIPE, 
                        stderr=subprocess.PIPE, 
                        text=True
                    )
                    
                    # Monitorear proceso y archivos
                    processed_files = set()
                    last_check = time.time()
                    process_start_time = time.time()
                    
                    while self.running:
                        # Verificar si el proceso sigue activo
                        if process.poll() is not None:
                            stdout, stderr = process.communicate()
                            print(f"❌ FFmpeg terminó. Reiniciando en 5 segundos...")
                            break
                        
                        # Buscar nuevos archivos cada 10 segundos
                        current_time = time.time()
                        if current_time - last_check >= 10:
                            self._check_for_new_segments(processed_files, process_start_time, current_time)
                            last_check = current_time
                        
                        time.sleep(1)
                    
                    # Terminar proceso si sigue activo
                    if process.poll() is None:
                        process.terminate()
                        try:
                            process.wait(timeout=5)
                        except subprocess.TimeoutExpired:
                            process.kill()
                            
                except Exception as e:
                    print(f"❌ Error en captura: {e}")
                
                # Reiniciar si es necesario
                if self.running:
                    print("🔄 Reiniciando FFmpeg en 5 segundos...")
                    time.sleep(5)
        
        self.running = True
        self.capture_thread = threading.Thread(target=capture_loop)
        self.capture_thread.daemon = True
        self.capture_thread.start()
        
    def _check_for_new_segments(self, processed_files, process_start_time, current_time):
        """Verificar nuevos segmentos de video"""
        try:
            files = os.listdir(self.config['paths']['videos_dir'])
            video_files = [f for f in files if f.startswith('segment_') 
                          and f.endswith(f'.{self.config["ffmpeg"]["video_format"]}')]
            
            # Ordenar archivos por número de segmento (más reciente primero)
            video_files.sort(key=lambda x: int(x.split('_')[1].split('.')[0]), reverse=True)
            
            # Solo procesar si hay al menos 3 archivos (dejar 2 más recientes intactos)
            if len(video_files) >= 3:
                # Tomar el tercer archivo más reciente (índice 2)
                file_to_process = video_files[2]
                full_path = os.path.join(self.config['paths']['videos_dir'], file_to_process)
                
                if full_path not in processed_files and full_path not in self.video_queue:
                    # Verificación simple: solo tamaño mínimo
                    try:
                        file_size = os.path.getsize(full_path)
                        if file_size > 100000:  # 100KB mínimo
                            self.video_queue.append(full_path)
                            processed_files.add(full_path)
                            elapsed = current_time - process_start_time
                            print(f"✅ Segmento listo: {file_to_process} ({file_size} bytes) - Tiempo: {elapsed:.1f}s")
                    except OSError:
                        # Archivo puede estar siendo escrito, ignorar silenciosamente
                        pass
                        
        except Exception as e:
            print(f"⚠️ Error listando archivos: {e}")
            
    def cleanup_old_segments(self, max_files=5):
        """Limpiar segmentos antiguos para evitar acumulación"""
        try:
            files = os.listdir(self.config['paths']['videos_dir'])
            video_files = [f for f in files if f.startswith('segment_') 
                          and f.endswith(f'.{self.config["ffmpeg"]["video_format"]}')]
            
            # Preservar 2 archivos más recientes siempre + max_files
            total_files_to_keep = max_files + 2
            
            if len(video_files) > total_files_to_keep:
                # Ordenar por número de segmento (más antiguos primero)
                video_files.sort(key=lambda x: int(x.split('_')[1].split('.')[0]))
                
                # Calcular cuántos eliminar
                files_to_delete_count = len(video_files) - total_files_to_keep
                to_delete = video_files[:files_to_delete_count]
                
                for file in to_delete:
                    file_path = os.path.join(self.config['paths']['videos_dir'], file)
                    # Solo eliminar si no está en la cola de procesamiento
                    if file_path not in self.video_queue:
                        try:
                            os.remove(file_path)
                            print(f"🗑️ Archivo antiguo eliminado: {file}")
                        except Exception as e:
                            print(f"⚠️ Error eliminando {file}: {e}")
                    else:
                        print(f"⏳ Archivo en cola, no se elimina: {file}")
                
                remaining_count = len(video_files) - len([f for f in to_delete 
                                     if not os.path.exists(os.path.join(self.config['paths']['videos_dir'], f))])
                print(f"🧹 Limpieza completada. Archivos restantes: {remaining_count}")
                
        except Exception as e:
            print(f"⚠️ Error en limpieza: {e}")
            
    def get_next_video(self):
        """Obtener siguiente video de la cola"""
        if self.video_queue:
            return self.video_queue.pop(0)
        return None
        
    def has_videos_in_queue(self):
        """Verificar si hay videos en cola"""
        return len(self.video_queue) > 0
        
    def get_queue_size(self):
        """Obtener tamaño de la cola"""
        return len(self.video_queue)
        
    def stop(self):
        """Detener captura"""
        self.running = False
        if self.capture_thread:
            self.capture_thread.join(timeout=5)
        print("🛑 Captura FFmpeg detenida")
