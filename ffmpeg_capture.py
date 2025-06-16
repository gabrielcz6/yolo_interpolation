#!/usr/bin/env python3
"""
Módulo de captura de video usando FFmpeg con Watchdog integrado
"""

import os
import subprocess
import threading
import time
import glob
from datetime import datetime, timedelta
from pathlib import Path


class FFmpegCapture:
    def __init__(self, config):
        """Inicializar capturador FFmpeg con Watchdog"""
        self.config = config
        self.running = False
        self.process = None
        self.watchdog_thread = None
        self.monitor_thread = None
        
        # Configuración del watchdog
        self.file_age_limit = config.get("watchdog", {}).get("file_age_limit", 45)
        self.check_interval = config.get("watchdog", {}).get("check_interval", 5)
        self.process_timeout = config.get("watchdog", {}).get("process_timeout", 30)
        
        # Log del watchdog
        self.watchdog_log = os.path.join(config["paths"]["videos_dir"], "watchdog_log.txt")
        
        # Variables de control
        self.process_start_time = None
        self.last_restart_time = None
        
    def get_current_timestamp(self):
        """Genera timestamp para el nombre del archivo"""
        return datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def log_watchdog_event(self, event_type, message):
        """Registra eventos del watchdog"""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_entry = f"[{timestamp}] {event_type}: {message}\n"
        
        try:
            with open(self.watchdog_log, "a", encoding="utf-8") as f:
                f.write(log_entry)
            print(f"🐕 Watchdog: {message}")
        except Exception as e:
            print(f"❌ Error escribiendo log watchdog: {e}")
    def is_ffmpeg_healthy(self):
        """Verificar salud basado en log de archivos"""
        current_time = datetime.now()
        
        if not self.process_start_time:
            return False
        
        runtime = (current_time - self.process_start_time).total_seconds()
        
        # Obtener último archivo del log
        filename, file_timestamp = self.get_last_logged_file()
        
        if not file_timestamp:
            # Sin archivos: máximo 20 segundos de gracia
            return runtime <= 20
        
        # Con archivos: máximo 30 segundos de antigüedad
        file_age = (current_time - file_timestamp).total_seconds()
        return file_age <= 30
    
  
    def get_oldest_video_for_processing(self):
        """Obtener video más antiguo que sea procesable (30+ segundos de antigüedad)"""
        try:
            pattern = os.path.join(self.config["paths"]["videos_dir"], "*.mp4")
            video_files = glob.glob(pattern)
            
            if not video_files:
                return None
            
            current_time = datetime.now()
            processable_files = []
            
            for video_path in video_files:
                try:
                    # Obtener tiempo de creación del archivo
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(video_path))
                    age_seconds = (current_time - file_mtime).total_seconds()
                    
                    # Solo archivos con 30+ segundos de antigüedad
                    if age_seconds >= 30:
                        processable_files.append((video_path, file_mtime))
                        
                except Exception as e:
                    print(f"⚠️ Error verificando archivo {video_path}: {e}")
                    continue
            
            if not processable_files:
                return None
            
            # Retornar el más antiguo
            oldest_file = min(processable_files, key=lambda x: x[1])
            return oldest_file[0]
            
        except Exception as e:
            print(f"❌ Error buscando videos procesables: {e}")
            return None
    
    def get_newest_video_timestamp(self):
        """Obtener timestamp del video más reciente"""
        try:
            pattern = os.path.join(self.config["paths"]["videos_dir"], "*.mp4")
            video_files = glob.glob(pattern)
            
            if not video_files:
                return None
            
            newest_time = None
            for video_path in video_files:
                try:
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(video_path))
                    if newest_time is None or file_mtime > newest_time:
                        newest_time = file_mtime
                except:
                    continue
            
            return newest_time
            
        except Exception as e:
            print(f"❌ Error obteniendo timestamp más reciente: {e}")
            return None
    def log_file_created(self, filename):
      """Registra un archivo completado en el log"""
      timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
      log_entry = f"{filename}|{timestamp}\n"
      
      try:
          with open(self.watchdog_log, "a", encoding="utf-8") as f:
              f.write(log_entry)
          print(f"📝 Archivo completado: {filename}")
      except Exception as e:
          print(f"❌ Error escribiendo log: {e}")
   
    def get_last_logged_file(self):
      """Obtiene la última entrada del log"""
      try:
          if not os.path.exists(self.watchdog_log):
              return None, None
              
          with open(self.watchdog_log, "r", encoding="utf-8") as f:
              lines = f.readlines()
          
          if not lines:
              return None, None
          
          # Obtener última línea no vacía
          for line in reversed(lines):
              line = line.strip()
              if line and "|" in line:
                  parts = line.split("|")
                  if len(parts) == 2:
                      filename = parts[0]
                      timestamp_str = parts[1]
                      timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                      return filename, timestamp
          
          return None, None
          
      except Exception as e:
          print(f"❌ Error leyendo log: {e}")
          return None, None
   
    def monitor_output_folder(self):
      """Monitorea carpeta para archivos completados"""
      processed_files = set()
      
      while self.running:
          try:
              pattern = os.path.join(self.config["paths"]["videos_dir"], "*.mp4")
              current_files = set(glob.glob(pattern))
              
              new_files = current_files - processed_files
              
              for filepath in new_files:
                  filename = os.path.basename(filepath)
                  try:
                      # Verificar que el archivo esté completo
                      size1 = os.path.getsize(filepath)
                      time.sleep(1)
                      size2 = os.path.getsize(filepath)
                      
                      if size1 == size2 and size1 > 50000:  # Archivo estable y mínimo
                          self.log_file_created(filename)
                          processed_files.add(filepath)
                  except:
                      continue
              
              time.sleep(2)
              
          except Exception as e:
              print(f"❌ Error monitoreando: {e}")
              time.sleep(2)
              
    def get_oldest_video_for_processing(self):
        """Obtener video más antiguo del log con 30+ segundos"""
        try:
            if not os.path.exists(self.watchdog_log):
                return None
                
            with open(self.watchdog_log, "r", encoding="utf-8") as f:
                lines = f.readlines()
            
            current_time = datetime.now()
            processable_files = []
            
            for line in lines:
                line = line.strip()
                if line and "|" in line:
                    parts = line.split("|")
                    if len(parts) == 2:
                        filename = parts[0]
                        timestamp_str = parts[1]
                        
                        try:
                            file_timestamp = datetime.strptime(timestamp_str, "%Y-%m-%d %H:%M:%S")
                            age_seconds = (current_time - file_timestamp).total_seconds()
                            
                            if age_seconds >= 30:
                                file_path = os.path.join(self.config["paths"]["videos_dir"], filename)
                                if os.path.exists(file_path):
                                    processable_files.append((file_path, file_timestamp))
                        except:
                            continue
            
            if not processable_files:
                return None
            
            # Retornar el más antiguo
            oldest_file = min(processable_files, key=lambda x: x[1])
            return oldest_file[0]
            
        except Exception as e:
            print(f"❌ Error buscando videos procesables: {e}")
            return None
    
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
    
    def start_ffmpeg_process(self):
        """Iniciar proceso FFmpeg con segmentación"""
        timestamp = self.get_current_timestamp()
        base_filename = f"{timestamp}_%d.mp4"
        output_path = os.path.join(self.config["paths"]["videos_dir"], base_filename)
        
        ffmpeg_cmd = [
            'ffmpeg',
            '-y',
            '-loglevel', 'error',
            '-rtsp_transport', 'tcp',
            '-rtbufsize', '400M',
            '-timeout', '30000000',
            '-i', self.config['ffmpeg']['input_source'],
            '-c:v', 'libx264',
            '-preset', 'ultrafast',
            '-s', self.config['ffmpeg']['resolution'],
            '-r', str(self.config['ffmpeg']['fps']),
            '-avoid_negative_ts', 'make_zero',
            '-f', 'segment',
            '-segment_time', str(self.config['ffmpeg']['segment_duration']),
            '-segment_format', self.config['ffmpeg']['video_format'],
            '-reset_timestamps', '1',
            '-segment_start_number', '0',
            output_path
        ]
        
        try:
            self.process = subprocess.Popen(
                ffmpeg_cmd, 
                stdout=subprocess.PIPE, 
                stderr=subprocess.PIPE,
                text=True
            )
            self.process_start_time = datetime.now()
            self.log_watchdog_event("START", f"FFmpeg iniciado con patrón: {base_filename}")
            return True
            
        except Exception as e:
            self.log_watchdog_event("ERROR", f"Error iniciando FFmpeg: {e}")
            return False
    
    def kill_ffmpeg_process(self):
        """Terminar proceso FFmpeg"""
        if self.process:
            try:
                self.process.terminate()
                try:
                    self.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self.process.kill()
                    self.process.wait()
                
                self.log_watchdog_event("STOP", "Proceso FFmpeg terminado")
                
            except Exception as e:
                self.log_watchdog_event("ERROR", f"Error terminando FFmpeg: {e}")
            finally:
                self.process = None
                self.process_start_time = None
    
    def restart_ffmpeg(self):
        """Reiniciar proceso FFmpeg"""
        current_time = datetime.now()
        
        # Evitar reinicios muy frecuentes
        if self.last_restart_time:
            time_since_restart = current_time - self.last_restart_time
            if time_since_restart.total_seconds() < 10:
                self.log_watchdog_event("SKIP", "Evitando reinicio muy frecuente")
                return False
        
        self.log_watchdog_event("RESTART", "Reiniciando FFmpeg...")
        
        self.kill_ffmpeg_process()
        time.sleep(2)  # Pausa antes de reiniciar
        
        if self.start_ffmpeg_process():
            self.last_restart_time = current_time
            self.log_watchdog_event("SUCCESS", "FFmpeg reiniciado exitosamente")
            return True
        else:
            self.log_watchdog_event("FAILED", "Error reiniciando FFmpeg")
            return False
    
    def watchdog_loop(self):
        """Loop principal del watchdog"""
        # Esperar antes de empezar verificaciones
        print("🐕 Esperando 15 segundos antes de iniciar watchdog...")
        time.sleep(10)
        
        while self.running:
            try:
                if not self.is_ffmpeg_healthy():
                    newest_timestamp = self.get_newest_video_timestamp()
                    
                    if newest_timestamp:
                        age = (datetime.now() - newest_timestamp).total_seconds()
                        self.log_watchdog_event("UNHEALTHY", 
                            f"Último archivo muy antiguo ({age:.1f}s)")
                    else:
                        if self.process_start_time:
                            runtime = (datetime.now() - self.process_start_time).total_seconds()
                            self.log_watchdog_event("UNHEALTHY", 
                                f"Sin archivos después de {runtime:.1f}s")
                        else:
                            self.log_watchdog_event("UNHEALTHY", "Sin archivos y sin proceso")
                    
                    self.restart_ffmpeg()
                
                else:
                    # Sistema saludable
                    newest_timestamp = self.get_newest_video_timestamp()
                    if newest_timestamp:
                        age = (datetime.now() - newest_timestamp).total_seconds()
                        if age < 20:  # Solo log si es muy reciente
                            self.log_watchdog_event("HEALTHY", f"Último archivo: {age:.1f}s")
                
                time.sleep(self.check_interval)
                
            except Exception as e:
                self.log_watchdog_event("ERROR", f"Error en watchdog loop: {e}")
                time.sleep(self.check_interval)
    
    def start_capture(self):
        """Iniciar captura con watchdog"""
        print("🎬 Iniciando captura FFmpeg con Watchdog...")
        
        # Limpiar log previo
        try:
            if os.path.exists(self.watchdog_log):
                os.remove(self.watchdog_log)
        except:
            pass
        
        self.log_watchdog_event("INIT", f"Watchdog iniciado - Límite: {self.file_age_limit}s")
        
        # Iniciar proceso FFmpeg
        if not self.start_ffmpeg_process():
            print("❌ Error iniciando FFmpeg")
            return False
        
        # Iniciar watchdog
        self.running = True
        self.watchdog_thread = threading.Thread(target=self.watchdog_loop)
        self.watchdog_thread.daemon = True
        # Iniciar monitor de carpeta
        self.monitor_thread = threading.Thread(target=self.monitor_output_folder)
        self.monitor_thread.daemon = True
        self.monitor_thread.start()
        self.watchdog_thread.start()
        
        print("✅ Captura con watchdog iniciada")
        return True
    
    def cleanup_old_segments(self, max_files=10):
        """Limpiar segmentos antiguos"""
        try:
            pattern = os.path.join(self.config["paths"]["videos_dir"], "*.mp4")
            video_files = glob.glob(pattern)
            
            if len(video_files) <= max_files:
                return
            
            # Ordenar por tiempo de modificación (más antiguos primero)
            video_files.sort(key=lambda x: os.path.getmtime(x))
            
            # Eliminar archivos más antiguos
            files_to_delete = video_files[:-max_files]
            
            for file_path in files_to_delete:
                try:
                    # Verificar que tenga al menos 2 minutos de antigüedad antes de eliminar
                    file_age = (datetime.now() - datetime.fromtimestamp(os.path.getmtime(file_path))).total_seconds()
                    if file_age >= 120:  # 2 minutos
                        os.remove(file_path)
                        filename = os.path.basename(file_path)
                        self.log_watchdog_event("CLEANUP", f"Archivo eliminado: {filename}")
                except Exception as e:
                    print(f"⚠️ Error eliminando {file_path}: {e}")
            
        except Exception as e:
            self.log_watchdog_event("ERROR", f"Error en limpieza: {e}")
    
    def get_next_video(self):
        """Obtener siguiente video para procesar (más antiguo con 30+ segundos)"""
        return self.get_oldest_video_for_processing()
    
    def has_videos_in_queue(self):
        """Verificar si hay videos procesables"""
        return self.get_next_video() is not None
    
    def get_queue_size(self):
        """Obtener número de videos procesables"""
        try:
            pattern = os.path.join(self.config["paths"]["videos_dir"], "*.mp4")
            video_files = glob.glob(pattern)
            
            current_time = datetime.now()
            processable_count = 0
            
            for video_path in video_files:
                try:
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(video_path))
                    age_seconds = (current_time - file_mtime).total_seconds()
                    if age_seconds >= 30:
                        processable_count += 1
                except:
                    continue
            
            return processable_count
            
        except Exception as e:
            return 0
    
    def stop(self):
        """Detener captura y watchdog"""
        print("🛑 Deteniendo captura FFmpeg...")
        
        self.running = False
        
        if self.watchdog_thread:
            self.watchdog_thread.join(timeout=5)
        if self.monitor_thread:
            self.monitor_thread.join(timeout=5)    
        
        self.kill_ffmpeg_process()
        
        self.log_watchdog_event("SHUTDOWN", "Sistema detenido")
        print("✅ Captura FFmpeg detenida")
