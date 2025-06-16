@echo off
setlocal enabledelayedexpansion

:: Configuración
set "timestamp=20250615_080606"
set "rtsp_url=rtsp://admin:usuario1234@192.168.18.13:554/Streaming/channels/101?tcp"
set "output_folder=videos"
set "base_filename=segment_%timestamp%_%%03d.mp4"
set "next_segment=104"
set "max_errors=5"
set "error_count=0"

:: Crear carpeta si no existe
if not exist "%output_folder%" mkdir "%output_folder%"

echo ======================================
echo    GRABACION RTSP CONTINUA
echo ======================================
echo URL: %rtsp_url%
echo Carpeta: %output_folder%
echo Presiona Ctrl+C para detener
echo ======================================
echo.

:main_loop
    :: Obtener el próximo número de segmento
    call :get_next_segment
    
    :: Mostrar información
    for /f "tokens=1-3 delims=:., " %%a in ("%time%") do set "current_time=%%a:%%b:%%c"
    echo [%current_time%] Iniciando desde segmento: !next_segment!
    
    :: Ejecutar FFmpeg
    ffmpeg -y -loglevel error -rtsp_transport tcp -rtbufsize 400M -timeout 30000000 -i "%rtsp_url%" -c:v libx264 -preset ultrafast -s 1280x720 -r 30 -avoid_negative_ts make_zero -f segment -segment_time 10 -segment_format mp4 -reset_timestamps 1 -segment_start_number !next_segment! "%output_folder%/%base_filename%"
    
    :: Verificar el código de salida
    set "exit_code=!errorlevel!"
    for /f "tokens=1-3 delims=:., " %%a in ("%time%") do set "end_time=%%a:%%b:%%c"
    
    if !exit_code! equ 0 (
        echo [!end_time!] Grabacion terminada correctamente
        set "error_count=0"
    ) else (
        set /a "error_count+=1"
        echo [!end_time!] Error en FFmpeg ^(codigo: !exit_code!^) - Intento !error_count!/%max_errors%
        
        if !error_count! geq %max_errors% (
            echo.
            echo Demasiados errores consecutivos. Deteniendo...
            goto :end
        )
    )
    
    :: Pausa antes del siguiente intento
    if !error_count! gtr 0 (
        echo Reintentando en 10 segundos...
        timeout /t 10 /nobreak >nul
    ) else (
        echo Reintentando en 3 segundos...
        timeout /t 3 /nobreak >nul
    )
    
goto :main_loop

:get_next_segment
    :: Buscar el último archivo de segmento
    set "last_segment=0"
    set "found_files=0"
    
    for /f "delims=" %%f in ('dir /b "%output_folder%\segment_%timestamp%_*.mp4" 2^>nul') do (
        set "found_files=1"
        set "filename=%%f"
        
        :: Extraer el número del archivo
        for /f "tokens=2 delims=_" %%n in ("!filename!") do (
            for /f "tokens=3 delims=_." %%s in ("!filename!") do (
                set "segment_num=%%s"
                :: Remover ceros a la izquierda
                for /f "tokens=* delims=0" %%a in ("!segment_num!") do set "segment_num=%%a"
                if "!segment_num!"=="" set "segment_num=0"
                
                if !segment_num! gtr !last_segment! (
                    set "last_segment=!segment_num!"
                )
            )
        )
    )
    
    if !found_files! equ 1 (
        set /a "next_segment=!last_segment!+1"
    ) else (
        set "next_segment=104"
    )
    
goto :eof

:end
echo.
echo ======================================
echo        SCRIPT TERMINADO
echo ======================================
echo Presiona cualquier tecla para salir...
pause >nul