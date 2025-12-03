#!/usr/bin/env python3
"""
Script para configurar el panel de administración
Crea los archivos necesarios en las ubicaciones correctas
"""
import os
import shutil

def setup_admin_panel():
    """Configura todos los archivos del panel de administración"""
    
    print("🔧 Configurando Panel de Administración...")
    
    # Crear carpeta static si no existe
    if not os.path.exists("static"):
        os.makedirs("static")
        print("✅ Carpeta 'static' creada")
    
    # El HTML del panel se guarda como admin_panel.html en la raíz
    print("✅ Panel HTML configurado")
    
    # El JS se debe guardar en static/admin.js
    print("✅ JavaScript configurado")
    
    # Verificar que existan los archivos necesarios
    required_files = [
        "admin_panel.html",
        "static/admin.js",
        "admin_routes.py",
        "main.py",
        "config.py",
        "whatsapp_client.py",
        "ai_assistant.py",
        "message_handler.py",
        "notification_service.py",
        "database.py"
    ]
    
    missing_files = []
    for file in required_files:
        if not os.path.exists(file):
            missing_files.append(file)
    
    if missing_files:
        print("\n⚠️  Archivos faltantes:")
        for file in missing_files:
            print(f"   - {file}")
        print("\n📝 Asegúrate de crear estos archivos antes de continuar")
    else:
        print("\n✅ Todos los archivos necesarios están presentes")
    
    # Verificar .env
    if not os.path.exists(".env"):
        if os.path.exists(".env.example"):
            shutil.copy(".env.example", ".env")
            print("✅ Archivo .env creado desde .env.example")
        else:
            print("⚠️  Archivo .env no encontrado. Créalo manualmente.")
    else:
        print("✅ Archivo .env encontrado")
    
    print("\n" + "="*50)
    print("✅ PANEL DE ADMINISTRACIÓN CONFIGURADO")
    print("="*50)
    print("\n📋 Próximos pasos:")
    print("1. Inicia el servidor: python main.py")
    print("2. Abre tu navegador en: http://localhost:8000")
    print("3. Configura tus credenciales en el panel")
    print("4. ¡Empieza a recibir mensajes!")
    print("\n💡 Tip: Usa ngrok para exponer tu webhook:")
    print("   ngrok http 8000\n")

if __name__ == "__main__":
    setup_admin_panel()