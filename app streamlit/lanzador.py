#!/usr/bin/env python3
"""Lanzador para el sistema de Urgencias - ETL y Dashboard"""

import os
import sys
import subprocess

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

def run_etl():
    print("\n🔄 Ejecutando ETL...")
    result = subprocess.run([sys.executable, os.path.join(BASE_DIR, "etl.py")], cwd=BASE_DIR)
    if result.returncode == 0:
        print("✅ ETL completado exitosamente.")
    else:
        print("❌ El ETL terminó con errores.")
    return result.returncode

def run_dashboard():
    print("\n🚀 Iniciando Dashboard Streamlit...")
    print("   Presiona Ctrl+C para detener.\n")
    subprocess.run(["streamlit", "run", os.path.join(BASE_DIR, "dashboard.py")], cwd=BASE_DIR)

def menu():
    print("=" * 45)
    print("   🏥 Sistema de Urgencias - Lanzador")
    print("=" * 45)
    print("  1. Iniciar todo (ETL + Dashboard)")
    print("  2. Solo ETL")
    print("  3. Solo Dashboard")
    print("  0. Salir")
    print("=" * 45)
    return input("  Selecciona una opción: ").strip()

def main():
    opcion = menu()

    if opcion == "1":
        code = run_etl()
        if code == 0:
            run_dashboard()
        else:
            print("\n⚠️  El ETL falló. Revisa los errores antes de lanzar el dashboard.")

    elif opcion == "2":
        run_etl()

    elif opcion == "3":
        db_path = os.path.join(BASE_DIR, "urgencias.db")
        if not os.path.exists(db_path):
            print("\n⚠️  No se encontró urgencias.db. Ejecuta el ETL primero (opción 2).")
        else:
            run_dashboard()

    elif opcion == "0":
        print("\nHasta luego 👋")

    else:
        print("\n❌ Opción no válida.")

if __name__ == "__main__":
    main()
