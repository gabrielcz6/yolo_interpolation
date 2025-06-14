#!/usr/bin/env python3
"""
Gestor de logs para el sistema de conteo de personas
"""

import json
import os
from datetime import datetime


class LoggerManager:
    def __init__(self, config):
        """Inicializar gestor de logs"""
        self.config = config
        self.log_dir = config["paths"]["logs_dir"]
        
    def save_count_log(self, people_tracker):
        """Guardar log de conteos"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        counts = people_tracker.get_counts()
        
        log_data = {
            "timestamp": timestamp,
            "datetime": datetime.now().isoformat(),
            "entry_count": counts['entries'],
            "exit_count": counts['exits'],
            "net_count": counts['occupancy'],
            "active_objects": people_tracker.get_active_objects_count(),
            "config_used": self.config
        }
        
        log_file = f"{self.log_dir}/count_log_{timestamp}.json"
        
        try:
            with open(log_file, 'w') as f:
                json.dump(log_data, f, indent=4)
            print(f"📋 Log guardado en: {log_file}")
            return log_file
        except Exception as e:
            print(f"❌ Error guardando log: {e}")
            return None
            
    def save_session_log(self, session_data):
        """Guardar log de sesión completa"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        session_log = {
            "session_start": session_data.get('start_time'),
            "session_end": datetime.now().isoformat(),
            "total_videos_processed": session_data.get('videos_processed', 0),
            "total_runtime_seconds": session_data.get('runtime_seconds', 0),
            "final_counts": session_data.get('final_counts', {}),
            "errors_encountered": session_data.get('errors', []),
            "config_snapshot": self.config
        }
        
        log_file = f"{self.log_dir}/session_log_{timestamp}.json"
        
        try:
            with open(log_file, 'w') as f:
                json.dump(session_log, f, indent=4)
            print(f"📋 Log de sesión guardado en: {log_file}")
            return log_file
        except Exception as e:
            print(f"❌ Error guardando log de sesión: {e}")
            return None
            
    def save_error_log(self, error_info):
        """Guardar log de errores"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        error_log = {
            "timestamp": timestamp,
            "datetime": datetime.now().isoformat(),
            "error_type": error_info.get('type', 'Unknown'),
            "error_message": str(error_info.get('message', '')),
            "error_context": error_info.get('context', ''),
            "video_path": error_info.get('video_path', ''),
            "config_snapshot": self.config
        }
        
        log_file = f"{self.log_dir}/error_log_{timestamp}.json"
        
        try:
            with open(log_file, 'w') as f:
                json.dump(error_log, f, indent=4)
            print(f"📋 Log de error guardado en: {log_file}")
            return log_file
        except Exception as e:
            print(f"❌ Error guardando log de error: {e}")
            return None
            
    def get_recent_logs(self, log_type="count", limit=10):
        """Obtener logs recientes"""
        try:
            files = os.listdir(self.log_dir)
            log_files = [f for f in files if f.startswith(f"{log_type}_log_") and f.endswith('.json')]
            
            # Ordenar por fecha (más reciente primero)
            log_files.sort(reverse=True)
            
            recent_logs = []
            for log_file in log_files[:limit]:
                try:
                    with open(os.path.join(self.log_dir, log_file), 'r') as f:
                        log_data = json.load(f)
                        recent_logs.append({
                            'filename': log_file,
                            'data': log_data
                        })
                except Exception as e:
                    print(f"⚠️ Error leyendo {log_file}: {e}")
                    
            return recent_logs
            
        except Exception as e:
            print(f"❌ Error obteniendo logs recientes: {e}")
            return []
            
    def cleanup_old_logs(self, days_to_keep=30):
        """Limpiar logs antiguos"""
        try:
            current_time = datetime.now()
            files_removed = 0
            
            for filename in os.listdir(self.log_dir):
                if filename.endswith('.json') and ('_log_' in filename):
                    file_path = os.path.join(self.log_dir, filename)
                    
                    # Verificar antigüedad del archivo
                    file_mtime = datetime.fromtimestamp(os.path.getmtime(file_path))
                    days_old = (current_time - file_mtime).days
                    
                    if days_old > days_to_keep:
                        try:
                            os.remove(file_path)
                            files_removed += 1
                        except Exception as e:
                            print(f"⚠️ Error eliminando {filename}: {e}")
                            
            if files_removed > 0:
                print(f"🧹 Logs limpiados: {files_removed} archivos eliminados")
            else:
                print("🧹 No hay logs antiguos para limpiar")
                
        except Exception as e:
            print(f"❌ Error en limpieza de logs: {e}")
            
    def get_summary_stats(self):
        """Obtener estadísticas resumidas de logs"""
        try:
            count_logs = self.get_recent_logs("count", limit=100)
            
            if not count_logs:
                return None
                
            total_entries = sum(log['data'].get('entry_count', 0) for log in count_logs)
            total_exits = sum(log['data'].get('exit_count', 0) for log in count_logs)
            
            stats = {
                'total_sessions': len(count_logs),
                'total_entries': total_entries,
                'total_exits': total_exits,
                'average_entries_per_session': total_entries / len(count_logs) if count_logs else 0,
                'average_exits_per_session': total_exits / len(count_logs) if count_logs else 0,
                'latest_session': count_logs[0]['data'] if count_logs else None
            }
            
            return stats
            
        except Exception as e:
            print(f"❌ Error calculando estadísticas: {e}")
            return None