#!/usr/bin/env python3

import argparse
import sys
import nbformat
import os
import random
import pandas as pd
from joblib import Parallel, delayed
from openai import OpenAI
import openai
from dotenv import load_dotenv
import logging
import re

# Definir errores_registro como una variable global
errores_registro = []

def generar_nombres_apellidos(num_nombres):
    nombres = [
        "Carlos", "María", "Javier", "Ana", "Luis", "Sofía", "Fernando", "Laura", "Pablo", "Marta",
        "Alberto", "Clara", "Diego", "Isabel", "Ricardo", "Elena", "Manuel", "Carmen", "Ignacio", "Teresa",
        "Francisco", "Beatriz", "Eduardo", "Lucía", "Antonio", "Patricia", "Miguel", "Silvia", "Raúl", "Cristina",
        "Alejandro", "Sandra", "Roberto", "Victoria", "Gabriel", "Inés", "Álvaro", "Paula", "Daniel", "Eva",
        "José", "Irene", "Adrián", "Nuria", "Ángel", "Mónica", "Jaime", "Gloria", "Jorge", "Rosa"
    ]

    apellidos = [
        "García", "Martínez", "López", "Sánchez", "González", "Pérez", "Rodríguez", "Fernández", "Gómez", "Díaz",
        "Hernández", "Álvarez", "Ruiz", "Jiménez", "Moreno", "Muñoz", "Romero", "Alonso", "Gutiérrez", "Navarro",
        "Torres", "Domínguez", "Vázquez", "Ramos", "Gil", "Serrano", "Blanco", "Molina", "Castro", "Ortiz",
        "Rubio", "Marín", "Sanz", "Núñez", "Iglesias", "Medina", "Garrido", "Cortés", "Castillo", "Santos",
        "Guerrero", "Ortega", "Delgado", "Prieto", "Vega", "Méndez", "Cabrera", "Fuentes", "León", "Herrera"
    ]

    lista_nombres_completos = []
    for _ in range(num_nombres):
        nombre_completo = f"{random.choice(apellidos)}_{random.choice(nombres)}"
        lista_nombres_completos.append(nombre_completo)

    return lista_nombres_completos

def extrae_enunciados_y_soluciones(examen_file):
    enunciados = []
    soluciones = []
    logger = logging.getLogger('extrae_enunciados_y_soluciones')
    log_stream = logging.StreamHandler()
    logger.addHandler(log_stream)
    logger.setLevel(logging.DEBUG)

    try:
        with open(examen_file, 'r', encoding='utf-8') as f:
            notebook = nbformat.read(f, as_version=4)
        logger.info(f"Notebook {examen_file} leído correctamente.")
    except FileNotFoundError:
        error_msg = f"El archivo {examen_file} no se encontró."
        logger.critical(error_msg)
        raise RuntimeError(error_msg)
    except Exception as e:
        error_msg = f"Error al leer el archivo {examen_file}: {e}"
        logger.critical(error_msg)
        raise RuntimeError(error_msg)

    try:
        for cell in notebook.cells:
            if cell.cell_type == 'markdown':
                cell_content = cell['source'].strip()
                if cell_content.startswith("## Ejercicio"):
                    enunciado = cell_content.split("## Ejercicio")[1].strip().split("Criterios:")[0].strip()
                    enunciados.append(enunciado)
            elif cell.cell_type == 'code':
                solucion = cell['source'].strip()
                soluciones.append(solucion)
        logger.info("Enunciados y soluciones extraídos correctamente.")
    except Exception as e:
        error_msg = f"Error inesperado al procesar el archivo {examen_file}: {e}"
        logger.critical(error_msg)
        raise RuntimeError(error_msg)

    return enunciados, soluciones

def leer_tipos_errores(tipos_errores_file):
    tipos_errores = {}
    with open(tipos_errores_file, 'r', encoding='utf-8') as file:
        contenido = file.read().split("---")  # Asume que los bloques están separados por ---
    
    for seccion in contenido:
        lineas = seccion.strip().split("\n")
        if len(lineas) < 3:
            continue
        nombre_error = lineas[0].replace("### ", "").strip()
        descripcion = ""
        ejemplo = ""
        instrucciones_adicionales = ""
        for linea in lineas[1:]:
            if linea.startswith("Descripción:"):
                descripcion = linea.replace("Descripción:", "").strip()
            elif linea.startswith("Ejemplo:"):
                ejemplo = linea.replace("Ejemplo:", "").strip()
            elif linea.startswith("Instrucciones Adicionales:"):
                instrucciones_adicionales = linea.replace("Instrucciones Adicionales:", "").strip()
        tipos_errores[nombre_error] = {
            'descripcion': descripcion,
            'ejemplo': ejemplo,
            'instrucciones_adicionales': instrucciones_adicionales
        }
    return tipos_errores

def generar_solucion_con_error(solucion_correcta, tipo_error, descripcion_error, instrucciones_adicionales):
    logger = logging.getLogger('generar_solucion_con_error')
    logger.setLevel(logging.DEBUG)
    
    prompt = f"""
    Eres un asistente de programación altamente capacitado. Tengo un código que es completamente correcto y quiero que generes una versión de este código que contenga un error específico. 

    **Tipo de error**: {tipo_error}
    **Descripción del error**: {descripcion_error}

    A continuación, te proporciono el código correcto. Tu tarea es introducir el error indicado de manera sutil, asegurándote de que el código aún parezca plausible pero produzca el error descrito. Si ya has generado este tipo de error anteriormente, intenta variarlo de alguna manera (por ejemplo, cambia la ubicación del error, utiliza una sintaxis diferente, altera un parámetro distinto, etc.). Añade un comentario a la línea de código indicando el error que has introducido.

    **Código correcto**:
    ```python
    {solucion_correcta}

    Instrucciones específicas: {instrucciones_adicionales}

    Por favor, genera solo el código con el error ahora: """
    
    try:
        cliente = OpenAI()
        logger.debug("Cliente de OpenAI creado correctamente.")
        response = cliente.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a programming teaching assistant evaluating student code."},
                {"role": "user", "content": prompt}
            ]
        )
        
        codigo_con_error = response.choices[0].message.content.strip()

        codigo_con_error = re.search(r'```python(.*?)```', codigo_con_error, re.DOTALL)
        if codigo_con_error:
            codigo_con_error = codigo_con_error.group(1).strip()

        logger.debug("Código con error generado correctamente.")
    except Exception as e:
        logger.error(f"Error al generar el código con error: {e}")
        codigo_con_error = solucion_correcta
    return codigo_con_error

import nbformat as nbf

def generar_notebook(nombre_alumno, enunciados, soluciones, archivo_salida):
    celdas = []
    celdas.append(nbf.v4.new_markdown_cell(f"# Examen de Finanzas - {nombre_alumno}"))
    for enunciado, solucion in zip(enunciados, soluciones):
        celdas.append(nbf.v4.new_markdown_cell(f"### Ejercicio\n{enunciado}"))
        celdas.append(nbf.v4.new_code_cell(solucion))
    nuevo_notebook = nbf.v4.new_notebook(cells=celdas)
    with open(archivo_salida, 'w', encoding='utf-8') as f:
        nbf.write(nuevo_notebook, f)
    print(f"Notebook {archivo_salida} generado correctamente.")

def crear_notebook_para_alumno(nombre_alumno, enunciados, soluciones_alumno, output_dir):
    nb = nbf.v4.new_notebook()
    cells = []
    for i, (enunciado, solucion) in enumerate(zip(enunciados, soluciones_alumno), start=1):
        cells.append(nbf.v4.new_markdown_cell(f"## Ejercicio {i}\n\n{enunciado}"))
        cells.append(nbf.v4.new_code_cell(solucion))
    nb['cells'] = cells
    archivo_salida = os.path.join(output_dir, f"{nombre_alumno}.ipynb")
    with open(archivo_salida, 'w', encoding='utf-8') as f:
        nbf.write(nb, f)
    print(f"Notebook {archivo_salida} generado correctamente.") 


from joblib import Parallel, delayed

def procesar_alumno(nombre_alumno, soluciones_correctas, tipos_errores, prob_error, tipo_error_fijo, enunciados, output_dir):
    soluciones_alumno = []
    errores_registro = []  # Mover la variable aquí

    for i, solucion_correcta in enumerate(soluciones_correctas):
        if random.random() <= prob_error:  # Evaluar la probabilidad de introducir un error
            if tipo_error_fijo and tipo_error_fijo in tipos_errores:
                tipo_error = tipo_error_fijo
            else:
                tipo_error = random.choice(list(tipos_errores.keys()))
            
            descripcion_error = tipos_errores[tipo_error]['descripcion']
            instrucciones_adicionales = tipos_errores[tipo_error].get('instrucciones_adicionales', '')
            solucion_con_error = generar_solucion_con_error(solucion_correcta, tipo_error, descripcion_error, instrucciones_adicionales)
            soluciones_alumno.append(solucion_con_error)
            
            # Registrar el error
            errores_registro.append({
                "Alumno": nombre_alumno,
                "Ejercicio": i + 1,
                "Tipo de Error": tipo_error,
                "Descripción": descripcion_error
            })
        else:
            soluciones_alumno.append(solucion_correcta)
    
    # Crear el notebook para este alumno
    crear_notebook_para_alumno(
        nombre_alumno, enunciados, soluciones_alumno, output_dir
    )
    
    return errores_registro  # Devolver los errores registrados

def generar_notebooks_examen(examen_file, tipos_errores_file, output_dir, num_alumnos, errores_output_file, prob_error=0.4, tipo_error_fijo=None):
    enunciados, soluciones_correctas = extrae_enunciados_y_soluciones(examen_file)
    tipos_errores = leer_tipos_errores(tipos_errores_file)
    nombres_alumnos = generar_nombres_apellidos(num_alumnos)

    # Ejecutar la creación de notebooks en paralelo y recopilar errores
    resultados = Parallel(n_jobs=-1, verbose=13)(
        delayed(procesar_alumno)(
            nombre_alumno, soluciones_correctas, tipos_errores, prob_error, tipo_error_fijo, enunciados, output_dir
        ) for nombre_alumno in nombres_alumnos
    )

    # Consolidar todos los registros de errores en una lista maestra
    errores_registro = [error for sublist in resultados for error in sublist]

    # Guardar el registro de errores en un archivo Excel
    df_errores = pd.DataFrame(errores_registro)
    df_errores.to_excel(errores_output_file, index=False)
    print(f"Registro de errores guardado en {errores_output_file}")
    
def main():
    parser = argparse.ArgumentParser(description='Generar notebooks con errores para evaluación.')
    
    # Valores predeterminados
    default_examen_file = "/workspace/examenes/examen_finanzas_gpt.ipynb"
    default_tipos_errores_file = "/workspace/tipos_errores.txt"
    default_output_dir = "/workspace/entregas"
    default_errores_output_file = "/workspace/reports/errores.xlsx"
    default_num_alumnos = 10
    default_prob_error = 2  # Asegúrate de que este sea un valor entre 0 y 1
    default_tipo_error = "Errores Lógicos"
    
    # Cargar las variables de entorno desde el archivo .env
    load_dotenv()

    # Obtener la clave de API
    openai_api_key = os.getenv("OPENAI_API_KEY")

    if openai_api_key is None:
        raise ValueError("API key is not set")

    # Inicializar la API de OpenAI
    openai.api_key = openai_api_key

    parser.add_argument('--examen_file', type=str, default=default_examen_file, help='Ruta del archivo del examen en formato notebook.')
    parser.add_argument('--tipos_errores_file', type=str, default=default_tipos_errores_file, help='Ruta del archivo que contiene los tipos de errores posibles.')
    parser.add_argument('--output_dir', type=str, default=default_output_dir, help='Directorio donde se guardarán los notebooks generados.')
    parser.add_argument('--num_alumnos', type=int, default=default_num_alumnos, help='Número de notebooks de alumnos a generar.')
    parser.add_argument('--errores_output_file', type=str, default=default_errores_output_file, help='Ruta del archivo Excel donde se guardará el registro de errores.')
    parser.add_argument('--prob_error', type=float, default=default_prob_error, help='Probabilidad de que se introduzca un error en cada ejercicio.')
    parser.add_argument('--tipo_error_fijo', type=str, default=default_tipo_error, help='Tipo de error a introducir en los ejercicios. Si es None, se eligen errores aleatorios.')

    args = parser.parse_args()

    # Llamar a la función principal con los argumentos proporcionados
    try:
        generar_notebooks_examen(
            examen_file=args.examen_file,
            tipos_errores_file=args.tipos_errores_file,
            output_dir=args.output_dir,
            num_alumnos=args.num_alumnos,
            errores_output_file=args.errores_output_file,
            prob_error=args.prob_error,
            tipo_error_fijo=args.tipo_error_fijo
        )
    except Exception as e:
        print(f"Error al ejecutar el script: {e}", file=sys.stderr)
        sys.exit(1)

    


if __name__ == "__main__":
    main()

