#!/usr/bin/env python3
"""
Script de inicio rápido para el bot de WhatsApp
"""
import os
import sys
import subprocess

def check_python_version():
    """Verifica que la versión de Python sea adecuada"""
    if sys.version_info < (3, 8):
        print("❌ Error: Se requiere Python 3.8 o superior")
        sys.exit(1)
    print(f"✅ Python {sys.version_info.major}.{sys.version_info.minor} detectado")

def check_env_file():
    """Verifica que exista el archivo .env"""
    if not os.path.exists('.env'):
        print("⚠️  Archivo .env no encontrado")
        print("📝 Creando .env desde .env.example...")
        
        if os.path.exists('.env.example'):
            with open('.env.example', 'r', encoding='utf-8') as source:
                with open('.env', 'w', encoding='utf-8') as target:
                    target.write(source.read())
            print("✅ Archivo .env creado")
            print("⚠️  IMPORTANTE: Revisa y actualiza el archivo .env con tus credenciales")
        else:
            print("❌ Error: No se encontró .env.example")
            sys.exit(1)
    else:
        print("✅ Archivo .env encontrado")

def check_dependencies():
    """Verifica que las dependencias estén instaladas"""
    try:
        import fastapi
        import anthropic
        import requests
        print("✅ Dependencias instaladas")
        return True
    except ImportError as e:
        print(f"⚠️  Faltan dependencias: {e.name}")
        print("📦 Instalando dependencias...")
        subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"])
        return False

def start_server():
    """Inicia el servidor FastAPI"""
    print("\n" + "="*50)
    print("🚀 INICIANDO SERVIDOR DE WHATSAPP BOT")
    print("="*50 + "\n")
    
    print("📱 Bot de WhatsApp con IA iniciando...")
    print("🤖 Usando Claude Haiku 3.5 para respuestas inteligentes")
    print("📊 Dashboard disponible en: http://localhost:8000")
    print("🔗 Webhook: http://localhost:8000/webhook")
    print("\n💡 Para exponer el webhook públicamente, usa ngrok:")
    print("   ngrok http 8000\n")
    print("⏹️  Presiona Ctrl+C para detener el servidor")
    print("="*50 + "\n")
    
    try:
        subprocess.run([sys.executable, "-m", "uvicorn", "main:app", "--reload", "--host", "0.0.0.0", "--port", "8000"])
    except KeyboardInterrupt:
        print("\n\n👋 Servidor detenido. ¡Hasta pronto!")
        sys.exit(0)

def main():
    """Función principal"""
    print("\n🤖 ARCOSUM WhatsApp Bot - Inicio Rápido\n")
    
    # Verificaciones
    check_python_version()
    check_env_file()
    
    if not check_dependencies():
        print("\n✅ Dependencias instaladas correctamente")
        print("🔄 Ejecuta el script nuevamente para iniciar el servidor")
        sys.exit(0)
    
    # Iniciar servidor
    start_server()

if __name__ == "__main__":
    main()