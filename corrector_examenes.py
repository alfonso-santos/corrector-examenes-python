#!/usr/bin/env python3

import numpy as np
import pandas as pd
import nbformat
import re
from nbconvert.preprocessors import ExecutePreprocessor, CellExecutionError
import openai
from openpyxl import Workbook
from openpyxl.styles import Font
import os
from dotenv import load_dotenv
from pprint import pprint
from openai import OpenAI
from fpdf import FPDF
from tqdm import tqdm
import sys
from joblib import Parallel, delayed
import argparse


# Cargar las variables de entorno desde el archivo .env
load_dotenv()

# Obtener la clave de API
openai_api_key = os.getenv("OPENAI_API_KEY")

if openai_api_key is None:
    raise ValueError("API key is not set")

# Inicializar la API de OpenAI
openai.api_key = openai_api_key

def listar_notebooks(directory):
    """
    Devuelve una lista con los nombres de todos los archivos con extensión '.ipynb' en un directorio dado,
    excluyendo aquellos que se llamen 'solucion.ipynb'.
    
    Parameters:
        directory (str): La ruta al directorio donde buscar los archivos.
        
    Returns:
        list: Una lista con los nombres de los archivos que cumplen los criterios.
    """
    archivos = []
    for filename in os.listdir(directory):
        if filename.endswith('.ipynb') and filename != 'solucion.ipynb':
            archivos.append(filename)
            
    alumnos = [archivo.replace('.ipynb', '') for archivo in archivos]
    return alumnos, archivos

def extrae_criterios(prompt_file):
    """
    Extrae los nombres de los criterios de un archivo de plantilla de prompt.

    Parámetros:
    prompt_file (str): Ruta al archivo que contiene la plantilla de prompt con los criterios delimitados por '@@'.

    Retorna:
    list: Una lista de cadenas, donde cada cadena es el nombre de un criterio extraído de la plantilla de prompt.
    """
    # Abrir y leer el archivo de plantilla de prompt
    with open(prompt_file, 'r', encoding='utf-8') as file:
        prompt_template = file.read()

    # Buscar los nombres de los criterios usando una expresión regular
    criteria_pattern = re.compile(r'@@(.*?)@@')
    criteria = criteria_pattern.findall(prompt_template)
    
    return criteria

def preprocesa_examen(file_path):
    """
    Procesa un notebook Jupyter para extraer el contexto del examen y los enunciados de los ejercicios.
    
    Parameters:
        file_path (str): Ruta del archivo del notebook de solución.
        
    Returns:
        dict: Un diccionario con las claves 'contexto_examen' y 'enunciados_ejercicios'.
    """
    # Inicialización de variables
    contexto_examen = ""
    enunciados_ejercicios = []

    # Leer el notebook
    with open(file_path, 'r', encoding='utf-8') as f:
        notebook_tmp = nbformat.read(f, as_version=4)
        
        # Procesar las celdas del notebook
        for cell in notebook_tmp.cells:
            if cell.cell_type == 'markdown':
                cell_content = cell['source'].strip()
                
                if cell_content.startswith('Contexto'):
                    # Asignar el contenido de la celda a la variable contexto_examen
                    contexto_examen = cell_content
                
                elif cell_content.startswith('Ejercicio'):
                    # Añadir el contenido de la celda a la lista enunciados_ejercicios
                    enunciados_ejercicios.append(cell_content)
    
    return {
        'contexto_examen': contexto_examen,
        'enunciados_ejercicios': enunciados_ejercicios
    }


def preprocesa_respuesta_alumno(file_path):
    """
    Procesa un notebook Jupyter para extraer el código de solución para cada ejercicio y el nombre del alumno.
    
    Parameters:
        file_path (str): Ruta del archivo del notebook de solución.
        
    Returns:
        dict: Un diccionario con las claves 'codigo_ejercicios' y 'alumno'.
    """
    # Inicialización de variables
    codigo_ejercicios = []

    # Leer el notebook
    with open(file_path, 'r', encoding='utf-8') as f:
        notebook_tmp = nbformat.read(f, as_version=4)
        
        # Procesar las celdas del notebook
        for cell in notebook_tmp.cells:
            if cell.cell_type == 'code':
                # Añadir el código de cada celda de código a codigo_ejercicios
                codigo_ejercicios.append(cell['source'])

    # Separar código en ejercicios utilizando el marcador '# Solucion ejercicio'
    codigo_ejercicios = re.split(r'# Solucion ejercicio \d+', '\n'.join(codigo_ejercicios))
    codigo_ejercicios = [code.strip() for code in codigo_ejercicios if code.strip()]  # Limpiar y filtrar vacíos

    # Extraer el nombre del alumno del nombre del archivo
    nombre_archivo = os.path.basename(file_path)  # Obtener el nombre del archivo con extensión
    alumno, _ = os.path.splitext(nombre_archivo)  # Separar el nombre y la extensión
    
    return {
        'codigo_ejercicios': codigo_ejercicios,
        'alumno': alumno
    }
    


####### ESTA FUNCION NO SE UTILIZA EN ESTE SCRIPT, PERO SE DEJA COMO REFERENCIA ########    
def evaluar_ejecucion_ejercicios(datos_ejercicios):
    """
    Evalúa la ejecución de los ejercicios en el diccionario de datos extraídos del notebook.
    
    Parameters:
        datos_ejercicios (dict): Diccionario con 'contexto_examen', 'enunciados_ejercicios' y 'codigo_ejercicios'.
        
    Returns:
        dict: Un diccionario con los datos originales y el estado de ejecución y los mensajes de error para cada ejercicio.
    """
    resultados = []
    codigo_ejercicios = datos_ejercicios['codigo_ejercicios']
    
    for idx, code in enumerate(codigo_ejercicios):
        resultado = {
            'id_ejercicio': idx + 1,
            'ejecucion': False,
            'mensaje_error': '',
            'calificacion': 0  # Calificación inicial, puede ser actualizada después
        }
        try:
            exec(code)
            resultado['ejecucion'] = True
            resultado['calificacion'] = 1  # Calificación inicial de 1 para ejecuciones exitosas
        except Exception as e:
            resultado['mensaje_error'] = str(e)
        
        resultados.append(resultado)
    
    # Incluir los resultados en la estructura de datos original
    datos_ejercicios_con_resultados = {
        'contexto_examen': datos_ejercicios['contexto_examen'],
        'enunciados_ejercicios': datos_ejercicios['enunciados_ejercicios'],
        'codigo_ejercicios': datos_ejercicios['codigo_ejercicios'],
        'resultados': resultados
    }
    
    return datos_ejercicios_con_resultados    
    
def evaluar_con_chatgpt(codigo, descripcion, prompt_template):
    """
    Evalúa el código de un ejercicio utilizando el modelo GPT-4 de OpenAI.

    Parameters:
        codigo (str): El código del ejercicio a evaluar.
        descripcion (str): Una descripción del ejercicio.
        prompt_template (str): El template del prompt con marcadores para la descripción y el código.

    Returns:
        dict: Un diccionario con la puntuación y comentario del ejercicio.
    """
    # Insertar los valores en el prompt
    prompt = prompt_template.format(descripcion=descripcion, codigo=codigo)

    cliente = OpenAI()
    response = cliente.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": "You are a programming teaching assistant evaluating student code."},
            {"role": "user", "content": prompt}
        ]
    )

    # Extraer la respuesta de ChatGPT
    evaluacion = response.choices[0].message.content
    return evaluacion

def evaluar_ejercicios(diccionario_enunciados, diccionario_resultados, prompt_file='prompt.txt'):
    """
    Evalúa los ejercicios utilizando GPT-4 y devuelve las notas y comentarios para cada ejercicio.
    
    Parameters:
        diccionario_enunciados (dict): Diccionario con los enunciados de los ejercicios preprocesados.
        diccionario_resultados (dict): Diccionario con los datos del notebook preprocesado (código de los ejercicios).
        prompt_file (str): Ruta del archivo de texto que contiene el prompt.

    Returns:
        dict: Un diccionario con las evaluaciones de cada ejercicio.
    """
    # Leer el prompt desde el archivo y cerrar el archivo automáticamente
    with open(prompt_file, 'r', encoding='utf-8') as file:
        prompt_template = file.read()
        
    evaluaciones = {}
    
    # Iterar sobre los enunciados y códigos de los ejercicios
    for i, (enunciado, codigo) in enumerate(zip(diccionario_enunciados['enunciados_ejercicios'], diccionario_resultados['codigo_ejercicios']), start=1):
        # Llamar a la función que evalúa con ChatGPT pasando el prompt template
        resultado = evaluar_con_chatgpt(codigo, enunciado, prompt_template)
        evaluaciones[f'Ejercicio {i}'] = resultado
    
    return evaluaciones

def extraer_resultados(resultado):
    """
    Extrae las puntuaciones, comentarios y comentarios generales de un diccionario de resultados.

    Parámetros:
    resultado (dict): Diccionario que contiene los resultados en forma de texto.

    Retorna:
    dict: Un diccionario con las claves originales y sus correspondientes listas de puntuaciones, comentarios y comentarios generales.
    """
    # Inicializar el diccionario para almacenar los resultados
    res = {}
    
    # Recorrer cada elemento del diccionario 'resultado'
    for key, value in resultado.items():
        # Buscar el patrón para las puntuaciones usando una expresión regular
        puntuaciones_pattern = re.search(r'A\.\s\*\*Puntuaciones\*\*:\s(\[.*?\])', value)
        # Buscar el patrón para los comentarios usando una expresión regular
        comentarios_pattern = re.search(r'B\.\s\*\*Comentarios\*\*:\s(.*?)C\.\s\*\*Comentario General\*\*:', value, re.DOTALL)
        # Buscar el patrón para el comentario general usando una expresión regular
        comentario_general_pattern = re.search(r'C\.\s\*\*Comentario General\*\*:\s(.*)', value, re.DOTALL)
        
        # Si se encuentra el patrón de puntuaciones, evalúa la cadena como una lista
        if puntuaciones_pattern:
            puntuaciones = eval(puntuaciones_pattern.group(1))
        else:
            puntuaciones = []

        # Si se encuentra el patrón de comentarios, evalúa la cadena como una lista
        if comentarios_pattern:
            comentarios_text = comentarios_pattern.group(1).strip()
            # Encuentra todos los comentarios dentro del texto de comentarios
            comentarios = re.findall(r'"\s*(.*?)\s*"', comentarios_text, re.DOTALL)
        else:
            comentarios = []

        # Si se encuentra el patrón de comentario general, evalúa la cadena como una lista
        if comentario_general_pattern:
            comentario_general = eval(comentario_general_pattern.group(1).strip())
        else:
            comentario_general = []

        # Añadir el resultado al diccionario 'res' para la clave actual
        res[key] = {
            'puntuaciones': puntuaciones,
            'comentarios': comentarios,
            'comentario_general': comentario_general
        }

    return res


# Clase personalizada para el PDF
class PDF(FPDF):
    """
    Clase personalizada para crear reportes de evaluación de ejercicios en formato PDF.
    
    Atributos:
    alumno (str): Nombre del alumno para el cual se está generando el reporte.

    Métodos:
    __init__(self, alumno): Inicializa la instancia de la clase PDF con el nombre del alumno.
    header(self): Añade un encabezado a cada página del PDF con el nombre del alumno.
    footer(self): Añade un pie de página a cada página del PDF con el número de página.
    add_context(self, contexto_examen): Añade el contexto del examen al PDF.
    add_enunciados(self, enunciados): Añade los enunciados de los ejercicios al PDF.
    add_evaluacion(self, alumno, ejercicios, criterios): Añade la evaluación del estudiante al PDF, incluyendo puntuaciones y comentarios para cada criterio.
    """
    
    def __init__(self, alumno):
        """
        Inicializa la instancia de la clase PDF con el nombre del alumno.
        
        Parámetros:
        alumno (str): Nombre del alumno para el cual se está generando el reporte.
        """
        super().__init__()
        self.alumno = alumno
    
    def header(self):
        """
        Añade un encabezado a cada página del PDF con el nombre del alumno.
        """
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, f'Reporte de Evaluación de Ejercicios de {self.alumno}', 0, 1, 'C')

    def footer(self):
        """
        Añade un pie de página a cada página del PDF con el número de página.
        """
        self.set_y(-15)
        self.set_font('Arial', 'I', 8)
        self.cell(0, 10, f'Página {self.page_no()}', 0, 0, 'C')

    def add_context(self, contexto_examen):
        """
        Añade el contexto del examen al PDF.
        
        Parámetros:
        contexto_examen (str): Contexto general del examen.
        """
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Contexto del Examen:', 0, 1)
        self.set_font('Arial', '', 12)
        self.multi_cell(0, 10, contexto_examen)
        self.ln(10)

    def add_enunciados(self, enunciados):
        """
        Añade los enunciados de los ejercicios al PDF.
        
        Parámetros:
        enunciados (list): Lista de enunciados de los ejercicios del examen.
        """
        self.set_font('Arial', 'B', 12)
        self.cell(0, 10, 'Enunciados de los Ejercicios:', 0, 1)
        self.set_font('Arial', '', 12)
        for i, enunciado in enumerate(enunciados, 1):
            self.cell(0, 10, f'Ejercicio {i}:', 0, 1)
            self.multi_cell(0, 10, enunciado)
            self.ln(5)
        self.ln(10)

    def add_evaluacion(self, alumno, ejercicios, criterios):
        """
        Añade la evaluación del estudiante al PDF, incluyendo puntuaciones y comentarios para cada criterio.
        
        Parámetros:
        alumno (str): Nombre del alumno.
        ejercicios (dict): Diccionario que contiene las evaluaciones de los ejercicios del estudiante.
        criterios (list): Lista de criterios de evaluación.
        """
        self.set_font('Arial', 'B', 16)
        self.cell(0, 10, f'Informe de {alumno}', 0, 1, 'C')
        self.ln(10)
   
        for ejercicio, contenido in ejercicios.items():
            # Título del ejercicio
            self.set_font('Arial', 'B', 12)
            self.cell(0, 10, ejercicio, 0, 1)
            self.ln(5)
            
            # Puntuaciones y comentarios
            for i, criterio in enumerate(criterios):
                self.set_font('Arial', 'B', 12)
                self.cell(0, 10, f'{criterio}:', 0, 1, 'L')
                self.set_font('Arial', '', 12)
                self.multi_cell(0, 10, f'Puntuación: {contenido["puntuaciones"][i]}')
                self.multi_cell(0, 10, f'Comentario: {contenido["comentarios"][i]}')
                self.ln(5)
            
            # Comentario general
            self.set_font('Arial', 'B', 12)
            self.cell(0, 10, 'Comentario General del Ejercicio:', 0, 1, 'L')
            self.set_font('Arial', '', 12)
            self.multi_cell(0, 10, contenido['comentario_general'][0])
            self.ln(10)


# Función para crear el PDF
def create_pdf(file_path, student_name, contexto_examen, enunciados, ejercicios, criterios):
    """
    Crea un archivo PDF con la evaluación del estudiante.

    Parámetros:
    file_path (str): Ruta donde se guardará el archivo PDF.
    student_name (str): Nombre del estudiante.
    contexto_examen (str): Contexto general del examen.
    enunciados (list): Lista de enunciados de los ejercicios del examen.
    ejercicios (dict): Diccionario que contiene las evaluaciones de los ejercicios del estudiante. La estructura del diccionario es:
        {
            'Ejercicio 1': {
                'puntuaciones': [listado de puntuaciones],
                'comentarios': [listado de comentarios],
                'comentario_general': [comentario general]
            },
            'Ejercicio 2': {...},
            ...
        }
    criterios (list): Lista de criterios de evaluación.

    Procedimiento:
    1. Crea una instancia de la clase PDF con el nombre del estudiante.
    2. Añade una página al PDF.
    3. Agrega el contexto del examen al PDF.
    4. Agrega los enunciados de los ejercicios al PDF.
    5. Agrega la evaluación del estudiante al PDF, incluyendo puntuaciones y comentarios para cada criterio.
    6. Guarda el archivo PDF en la ruta especificada.

    Retorna:
    Ninguno
    """
    
    pdf = PDF(student_name)
    pdf.add_page()
    
    # Agregar contexto del examen
    pdf.add_context(contexto_examen)
    
    # Agregar enunciados de los ejercicios (comentado porque no está en uso)
    # pdf.add_enunciados(enunciados)
    
    # Agregar evaluación del estudiante
    pdf.add_evaluacion(student_name, ejercicios, criterios)
    
    # Guardar el PDF con el nombre del estudiante
    pdf.output(file_path)
    
def generar_pdfs_para_estudiantes(examen_preprocesado, directorio_reports, resultados):
    """
    Genera archivos PDF de evaluación para cada estudiante basado en los resultados del examen.

    Parámetros:
    examen_preprocesado (dict): Diccionario con los datos del examen preprocesado que incluye el contexto y los enunciados de los ejercicios.
    directorio_reports (str): Ruta al directorio donde se guardarán los archivos PDF generados.
    resultados (dict): Diccionario que contiene las evaluaciones de los estudiantes. La estructura del diccionario es:
        {
            'nombre_estudiante': {
                'Ejercicio 1': {
                    'puntuaciones': [listado de puntuaciones],
                    'comentarios': [listado de comentarios],
                    'comentario_general': [comentario general]
                },
                'Ejercicio 2': {...},
                ...
            },
            ...
            'criterios': [listado de criterios]
        }

    Precondiciones:
    - El archivo del examen debe existir en la ruta especificada.
    - Las funciones `preprocesa_notebook` y `create_pdf` deben estar definidas previamente.

    Procedimiento:
    1. Crea el directorio para guardar los archivos PDF si no existe.
    2. Para cada estudiante en los resultados, genera un archivo PDF con las evaluaciones y comentarios.
    """

    # Crear directorio para guardar los PDFs
    if not os.path.exists(directorio_reports):
        os.makedirs(directorio_reports)
    
    # Generar el PDF para cada estudiante
    for student_name, ejercicios in resultados.items():
        if student_name != 'criterios':  # Ignorar la clave de criterios
            file_path = os.path.join(directorio_reports, f'{student_name}.pdf')
            create_pdf(file_path, student_name, examen_preprocesado['contexto_examen'], examen_preprocesado['enunciados_ejercicios'], ejercicios, resultados['criterios'])
    
    
def generar_excel_resultados(resultados, filename='resultados_evaluacion.xlsx'):
    filas = []

    for alumno, ejercicios in resultados.items():
        if alumno == 'criterios':  # Ignorar la clave de criterios
            continue
        fila = {'Alumno': alumno}
        notas = []
        for ejercicio, contenido in ejercicios.items():
            media = np.mean(contenido['puntuaciones'])
            fila[ejercicio] = media
            notas.append(media)
        
        # Calcular la nota final como la media ponderada de las notas de los ejercicios
        nota_final = np.mean(notas)
        fila['NOTA FINAL'] = nota_final
        
        filas.append(fila)

    df = pd.DataFrame(filas)
    df.to_excel(filename, index=False)
    
    
def evaluar_notebook(fich, directorio_entregas, examen_procesado, prompt_file):
    """
    Procesa y evalúa un notebook de un alumno.
    
    Parameters:
        fich (str): Nombre del archivo del notebook del alumno.
        directorio_entregas (str): Ruta del directorio de entregas.
        examen_procesado (dict): Datos preprocesados del examen.
        prompt_file (str): Ruta del archivo de texto que contiene el prompt.
    
    Returns:
        tuple: Nombre del alumno y resultado de la evaluación extraída.
    """
    try:
        nb_preprocesado = preprocesa_respuesta_alumno(os.path.join(directorio_entregas, fich))
        res_eval_tmp = evaluar_ejercicios(examen_procesado, nb_preprocesado, prompt_file=prompt_file)
        res_extraido = extraer_resultados(res_eval_tmp)
        alumno, _ = os.path.splitext(fich)
        return alumno, res_extraido
    except Exception as e:
        print(f"Error procesando el notebook {fich}: {e}", file=sys.stderr)
        return None

def main(directorio_raiz, nombre_fich_examen):
    """
    Función principal para evaluar los notebooks entregados por los estudiantes.
    
    Parameters:
        directorio_raiz (str): Ruta del directorio raíz que contiene los subdirectorios y archivos necesarios.
        nombre_fich_examen (str): Nombre del archivo del examen.
    """
    try:
        # Construir las rutas basadas en el directorio raíz
        directorio_entregas = os.path.join(directorio_raiz, "entregas")
        prompt_file = os.path.join(directorio_raiz, 'prompt.txt')
        directorio_examen = os.path.join(directorio_raiz, "examenes")
        directorio_reports = os.path.join(directorio_raiz, "reports")
        fichero_res = 'resultados_evaluacion.xlsx'
        fichero_examen = os.path.join(directorio_examen, nombre_fich_examen)

        # Preprocesar el examen
        if not os.path.exists(fichero_examen):
            raise FileNotFoundError(f"El archivo de examen {fichero_examen} no existe.")
        examen_procesado = preprocesa_examen(fichero_examen)

        # Listar los notebooks entregados por los alumnos
        if not os.path.exists(directorio_entregas):
            raise FileNotFoundError(f"El directorio de entregas {directorio_entregas} no existe.")
        alumnos, ficheros = listar_notebooks(directorio_entregas)
        if not ficheros:
            raise FileNotFoundError("No se encontraron notebooks de alumnos en el directorio de entregas.")

        # Extraer los criterios de evaluación del prompt
        if not os.path.exists(prompt_file):
            raise FileNotFoundError(f"El archivo de prompt {prompt_file} no existe.")
        criterios = extrae_criterios(prompt_file)

        # Inicializar el diccionario de resultados
        resultados = {}
        resultados['criterios'] = criterios

        # Procesar y evaluar cada notebook en paralelo
        resultados_alumnos = Parallel(n_jobs=-1)(
            delayed(evaluar_notebook)(fich, directorio_entregas, examen_procesado, prompt_file) 
            for fich in tqdm(ficheros, desc="Procesando notebooks")
        )

        # Filtrar resultados exitosos y agregar al diccionario de resultados
        for result in resultados_alumnos:
            if result is not None:
                alumno, res_extraido = result
                resultados[alumno] = res_extraido

        # Generar los informes en PDF para cada estudiante
        generar_pdfs_para_estudiantes(examen_procesado, directorio_reports, resultados)

        # Generar el archivo Excel con los resultados de la evaluación
        generar_excel_resultados(resultados, filename=os.path.join(directorio_reports, fichero_res))
        
        print("Proceso completado con éxito.")

    except Exception as e:
        print(f"Error en el proceso: {e}", file=sys.stderr)


##################################################################################

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Evaluar notebooks de Python.')
    parser.add_argument('-dir', '--directorio_raiz', type=str, required=True, help='Directorio raíz que contiene los subdirectorios y archivos necesarios')
    parser.add_argument('-ex', '--nombre_fich_examen', type=str, required=True, help='Nombre del archivo del examen')

    args = parser.parse_args()

    main(args.directorio_raiz, args.nombre_fich_examen)


