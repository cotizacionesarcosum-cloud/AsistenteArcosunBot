#!/usr/bin/env python3
"""
Script para agregar conversaciones de ejemplo al bot

Uso:
    python agregar_conversacion.py conversacion.txt

O modo interactivo:
    python agregar_conversacion.py
"""

import json
import sys
from pathlib import Path

def parse_text_conversation(text: str) -> dict:
    """Convierte texto plano a formato JSON"""

    lines = text.strip().split('\n')

    # Valores por defecto
    tipo = "general"
    score = 5
    motivo = ""
    conversacion = []

    current_speaker = None
    current_message = []

    for line in lines:
        line = line.strip()

        if not line:
            continue

        # Detectar metadata
        if line.upper().startswith("TIPO:"):
            tipo = line.split(":", 1)[1].strip()
        elif line.upper().startswith("SCORE:"):
            score = int(line.split(":", 1)[1].strip())
        elif line.upper().startswith("MOTIVO:"):
            motivo = line.split(":", 1)[1].strip()

        # Detectar mensajes
        elif line.upper().startswith("CLIENTE:"):
            # Guardar mensaje anterior si existe
            if current_speaker and current_message:
                mensaje = " ".join(current_message)
                conversacion.append({current_speaker: mensaje})

            current_speaker = "cliente"
            current_message = [line.split(":", 1)[1].strip()]

        elif line.upper().startswith("BOT:"):
            # Guardar mensaje anterior si existe
            if current_speaker and current_message:
                mensaje = " ".join(current_message)
                conversacion.append({current_speaker: mensaje})

            current_speaker = "bot"
            current_message = [line.split(":", 1)[1].strip()]

        # Continuar mensaje actual
        elif current_speaker:
            current_message.append(line)

    # Guardar último mensaje
    if current_speaker and current_message:
        mensaje = " ".join(current_message)
        conversacion.append({current_speaker: mensaje})

    return {
        "tipo": tipo,
        "conversacion": conversacion,
        "lead_score": score,
        "motivo_calificacion": motivo
    }

def add_conversation_to_examples(new_conversation: dict):
    """Agrega la conversación al archivo JSON"""

    examples_file = "conversation_examples.json"

    # Cargar archivo existente
    with open(examples_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Determinar sección según score
    if new_conversation["lead_score"] >= 7:
        section = "ejemplos_cotizaciones_exitosas"
    else:
        section = "ejemplos_consultas_generales"

    # Calcular nuevo ID
    if section in data and data[section]:
        new_id = max(ex.get("id", 0) for ex in data[section]) + 1
    else:
        new_id = 1
        data[section] = []

    # Agregar ID
    new_conversation["id"] = new_id

    # Agregar a la sección
    data[section].append(new_conversation)

    # Guardar archivo
    with open(examples_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"\n✅ Conversación agregada exitosamente!")
    print(f"   ID: {new_id}")
    print(f"   Sección: {section}")
    print(f"   Score: {new_conversation['lead_score']}/10")
    print(f"   Tipo: {new_conversation['tipo']}")
    print(f"\n📝 Total de conversaciones en {section}: {len(data[section])}")

def modo_interactivo():
    """Modo interactivo para crear conversación"""

    print("="*60)
    print("🤖 AGREGAR NUEVA CONVERSACIÓN DE EJEMPLO")
    print("="*60)

    # Tipo
    tipo = input("\n📌 Tipo de conversación (ej: arcotecho_urgente): ").strip()

    # Score
    while True:
        try:
            score = int(input("⭐ Lead score (1-10): ").strip())
            if 1 <= score <= 10:
                break
            print("❌ Score debe estar entre 1 y 10")
        except ValueError:
            print("❌ Ingresa un número válido")

    # Motivo
    motivo = input("💭 Motivo de calificación: ").strip()

    # Conversación
    print("\n💬 CONVERSACIÓN (escribe 'FIN' cuando termines)")
    print("   Formato: CLIENTE: mensaje  o  BOT: mensaje\n")

    conversacion = []
    while True:
        linea = input(">> ").strip()

        if linea.upper() == "FIN":
            break

        if linea.upper().startswith("CLIENTE:"):
            conversacion.append({"cliente": linea.split(":", 1)[1].strip()})
        elif linea.upper().startswith("BOT:"):
            conversacion.append({"bot": linea.split(":", 1)[1].strip()})
        else:
            print("⚠️ Línea debe empezar con CLIENTE: o BOT:")

    # Crear objeto
    nueva = {
        "tipo": tipo,
        "conversacion": conversacion,
        "lead_score": score,
        "motivo_calificacion": motivo
    }

    # Mostrar resumen
    print("\n" + "="*60)
    print("📋 RESUMEN:")
    print("="*60)
    print(json.dumps(nueva, ensure_ascii=False, indent=2))

    # Confirmar
    confirmar = input("\n¿Agregar esta conversación? (s/n): ").strip().lower()

    if confirmar == 's':
        add_conversation_to_examples(nueva)
    else:
        print("❌ Cancelado")

def main():
    if len(sys.argv) > 1:
        # Modo archivo
        file_path = sys.argv[1]

        if not Path(file_path).exists():
            print(f"❌ Archivo no encontrado: {file_path}")
            sys.exit(1)

        with open(file_path, 'r', encoding='utf-8') as f:
            text = f.read()

        conversation = parse_text_conversation(text)
        add_conversation_to_examples(conversation)

    else:
        # Modo interactivo
        modo_interactivo()

if __name__ == "__main__":
    main()
