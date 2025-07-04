#!/usr/bin/env python3
"""
Sistema Principal de Conteo de Personas con YOLOv8 + SORT + Watchdog
Versión con procesamiento basado en archivos más antiguos (sin colas)

Ejecución:
    python main_system.py [config_file]
"""

import sys
import time
from datetime import datetime

# Importar módulos del sistema
from config_manager import ConfigManager
from ffmpeg_capture import FFmpegCapture
from detection_engine import DetectionEngine
from people_tracker import PeopleTracker
from video_processor import VideoProcessor
from logger_manager import LoggerManager


class PeopleCounterSystem:
    def __init__(self, config_file="config.json"):
        """Inicializar sistema principal"""
        print("🚀 Inicializando Sistema de Conteo de Personas con Watchdog...")
        
        # Cargar configuración
        self.config_manager = ConfigManager(config_file)
        self.config = self.config_manager.config
        
        # Configurar directorios
        self.config_manager.setup_directories()
        
        # Inicializar componentes
        self.detection_engine = DetectionEngine(self.config)
        self.people_tracker = PeopleTracker(self.config)
        self.ffmpeg_capture = FFmpegCapture(self.config)
        self.video_processor = VideoProcessor(self.config, self.detection_engine, self.people_tracker)
        self.logger = LoggerManager(self.config)
        
        # Variables de control
        self.running = False
        self.session_data = {
            'start_time': datetime.now().isoformat(),
            'videos_processed': 0,
            'runtime_seconds': 0,
            'errors': []
        }
        
    def print_system_info(self):
        """Mostrar información del sistema"""
        print("\n" + "="*60)
        print("📋 CONFIGURACIÓN DEL SISTEMA")
        print("="*60)
        print(f"🎥 Fuente de video: {self.config['ffmpeg']['input_source']}")
        print(f"🧠 Modelo YOLO: {self.config['detection']['model_path']}")
        print(f"📐 ROI: ({self.config['roi']['x1']}, {self.config['roi']['y1']}) -> "
              f"({self.config['roi']['x2']}, {self.config['roi']['y2']})")
        print(f"🎯 Confianza: {self.config['detection']['confidence']}")
        print(f"⚡ Dispositivo: {self.config['detection']['device']}")
        print(f"🔄 Rotación: {self.config['image']['rotation']}°")
        print(f"📏 Línea de conteo: {self.config['counting']['line_position']*100}% de altura ROI")
        print(f"🐕 Watchdog - Límite archivo: {self.config['watchdog']['file_age_limit']}s")
        print(f"🐕 Watchdog - Intervalo: {self.config['watchdog']['check_interval']}s")
        print(f"⏰ Antigüedad mínima para procesar: 30 segundos")
        print("="*60)
        
    def test_system_components(self):
        """Probar componentes del sistema"""
        print("\n🔍 PROBANDO COMPONENTES DEL SISTEMA...")
        
        # Probar modelo de detección
        if not self.detection_engine.is_model_loaded():
            print("❌ Error: Modelo YOLO no cargado correctamente")
            return False
        print("✅ Modelo YOLO: OK")
        
        # Probar conexión RTSP/RTMP
        if not self.ffmpeg_capture.test_rtsp_connection():
            print("❌ Error: No se puede conectar a la fuente de video")
            return False
        print("✅ Conexión de video: OK")
        
        print("✅ Todos los componentes funcionan correctamente")
        return True
        
    def run(self):
        """Ejecutar sistema principal"""
        try:
            self.print_system_info()
             
            if not self.test_system_components():
                print("❌ Error en la inicialización. Revise la configuración.")
                return
                
            print("\n🎬 INICIANDO SISTEMA DE CONTEO CON WATCHDOG...")
            print("❌ Presiona Ctrl+C para salir")
            print("📝 Procesando videos con 30+ segundos de antigüedad")
            
            # Iniciar captura FFmpeg con watchdog
            if not self.ffmpeg_capture.start_capture():
                print("❌ Error iniciando captura")
                return
                
            self.running = True
            
            start_time = time.time()
            cleanup_counter = 0
            last_status_time = time.time()
            last_processing_time = time.time()
            
            print("\n⏳ Esperando videos para procesar...")
            
            while self.running:
                try:
                    current_time = time.time()
                    
                    # Buscar video más antiguo para procesar cada 10 segundos
                    if current_time - last_processing_time >= 10:
                        video_path = self.ffmpeg_capture.get_next_video()
                        
                        if video_path:
                            print(f"\n📹 Procesando video más antiguo: {video_path}")
                            
                            try:
                                success = self.video_processor.process_video(video_path)
                                if success:
                                    self.session_data['videos_processed'] += 1
                                    print(f"✅ Video procesado exitosamente")
                                else:
                                    error_info = {
                                        'type': 'ProcessingError',
                                        'message': 'Error procesando video',
                                        'video_path': video_path,
                                        'context': 'video_processing'
                                    }
                                    self.session_data['errors'].append(error_info)
                                    self.logger.save_error_log(error_info)
                                    
                            except Exception as e:
                                error_info = {
                                    'type': type(e).__name__,
                                    'message': str(e),
                                    'video_path': video_path,
                                    'context': 'video_processing_exception'
                                }
                                self.session_data['errors'].append(error_info)
                                self.logger.save_error_log(error_info)
                                print(f"❌ Error procesando {video_path}: {e}")
                        
                        last_processing_time = current_time
                    
                    # Mostrar estado del sistema cada 30 segundos
                    if current_time - last_status_time >= 30:
                        self._show_system_status()
                        last_status_time = current_time
                        
                    # Limpieza periódica cada 5 minutos
                    cleanup_counter += 1
                    if cleanup_counter >= 300:  # 5 minutos
                        print("\n🧹 Realizando limpieza automática...")
                        self.ffmpeg_capture.cleanup_old_segments()
                        self.logger.cleanup_old_logs()
                        cleanup_counter = 0
                        
                    time.sleep(1)
                    
                except KeyboardInterrupt:
                    break
                except Exception as e:
                    error_info = {
                        'type': type(e).__name__,
                        'message': str(e),
                        'context': 'main_loop'
                    }
                    self.session_data['errors'].append(error_info)
                    self.logger.save_error_log(error_info)
                    print(f"❌ Error en bucle principal: {e}")
                    time.sleep(5)  # Pausa antes de continuar
                    
        except KeyboardInterrupt:
            pass
        finally:
            self._shutdown_system()
            
    def _show_system_status(self):
        """Mostrar estado actual del sistema"""
        counts = self.people_tracker.get_counts()
        processable_videos = self.ffmpeg_capture.get_queue_size()
        
        print(f"\n📊 ESTADO DEL SISTEMA:")
        print(f"   🟢 Entradas: {counts['entries']}")
        print(f"   🔴 Salidas: {counts['exits']}")
        print(f"   👥 Ocupación: {counts['occupancy']}")
        print(f"   📹 Videos procesables: {processable_videos}")
        print(f"   🎬 Videos procesados: {self.session_data['videos_processed']}")
        print(f"   ⚠️ Errores: {len(self.session_data['errors'])}")
        print(f"   🐕 Watchdog: Activo")


    
       
           
    def _shutdown_system(self):
        """Cerrar sistema de forma ordenada"""
        print("\n🛑 CERRANDO SISTEMA...")
        
        self.running = False
        
        # Detener captura FFmpeg y watchdog
        self.ffmpeg_capture.stop()
        
        # Guardar datos de sesión
        runtime = time.time() - time.mktime(datetime.fromisoformat(self.session_data['start_time']).timetuple())
        self.session_data['runtime_seconds'] = runtime
        self.session_data['final_counts'] = self.people_tracker.get_counts()
        
        # Guardar logs finales
        self.logger.save_count_log(self.people_tracker)
        self.logger.save_session_log(self.session_data)
        
        # Mostrar resumen final
        self._show_final_summary()
        
        print("✅ Sistema cerrado correctamente")
        
    def _show_final_summary(self):
        """Mostrar resumen final de la sesión"""
        counts = self.people_tracker.get_counts()
        runtime_minutes = self.session_data['runtime_seconds'] / 60
        
        print("\n" + "="*60)
        print("📈 RESUMEN FINAL DE LA SESIÓN")
        print("="*60)
        print(f"⏱️ Tiempo de ejecución: {runtime_minutes:.1f} minutos")
        print(f"🎬 Videos procesados: {self.session_data['videos_processed']}")
        print(f"🟢 Total entradas: {counts['entries']}")
        print(f"🔴 Total salidas: {counts['exits']}")
        print(f"👥 Ocupación final: {counts['occupancy']}")
        print(f"⚠️ Errores encontrados: {len(self.session_data['errors'])}")
        
        if self.session_data['videos_processed'] > 0:
            avg_entries = counts['entries'] / self.session_data['videos_processed']
            avg_exits = counts['exits'] / self.session_data['videos_processed']
            print(f"📊 Promedio entradas/video: {avg_entries:.1f}")
            print(f"📊 Promedio salidas/video: {avg_exits:.1f}")
            
        print("="*60)


def main():
    """Función principal"""
    # Obtener archivo de configuración desde argumentos
    config_file = sys.argv[1] if len(sys.argv) > 1 else "config.json"
    
    try:
        # Crear e iniciar sistema
        system = PeopleCounterSystem(config_file)
        system.run()
        
    except Exception as e:
        print(f"❌ Error fatal del sistema: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
