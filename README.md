# Manual de Uso para Evaluación de Notebooks de Python

Este documento te proporciona una guía completa para organizar y ejecutar el proceso de evaluación de notebooks de Python, incluyendo la estructura de directorios, los pasos a seguir, y una descripción de las funciones clave involucradas en el proceso. Para adaptar el sistema a un examen distinto, solo necesitas modificar el archivo `prompt.txt` siguiendo la estructura y requisitos especificados.

## Estructura de Directorios

Para organizar adecuadamente los archivos y directorios necesarios, sigue esta estructura:

![alt text](image.png)


/workspace
│
├── .env
│
├── /entregas
│   └── apellido_nombre.ipynb
│
├── /examenes
│   └── examen.ipynb
│
├── /src
│   ├── corrector_examenes.ipynb
│   ├── corrector_examenes.py
│   ├── prompt.txt
│
└── /reports
    └── * (Generados automáticamente) *

    
### Descripción de Directorios y Archivos

1. **/entregas**: Este directorio contiene los notebooks entregados por los alumnos. Cada archivo debe seguir el formato de nombre `apellido_nombre.ipynb`. Los notebooks deben tener los enunciados en celdas Markdown y deben empezar con "Ejercicio" y el número de ejercicio, por ejemplo, "Ejercicio 1:". Después de cada enunciado, debe haber una o varias celdas con el código. Las celdas de código deben empezar con `# Solución ejercicio` seguido del número del ejercicio, por ejemplo, `# Solución ejercicio 1`.

2. **/examenes**: Este directorio contiene el notebook con el enunciado del examen. El archivo debe llamarse `examen.ipynb`.

3. **/src**: Este directorio contiene los archivos necesarios para ejecutar el proceso de corrección.
   - `corrector_examenes.ipynb`: Notebook principal que contiene el código para preprocesar, evaluar y generar informes.
   - `prompt.txt`: Archivo de texto que define el prompt utilizado para la evaluación de los notebooks.
   - `.env`: Archivo que contiene la API KEY de OpenAI. Debe incluir una línea como `OPENAI_API_KEY=tu_api_key`.

4. **/reports**: Este directorio se genera automáticamente y contendrá los informes en PDF para cada alumno y el archivo Excel con las calificaciones.

## Pasos para Usar el Código

### 1. Cargar los Notebooks

Los notebooks entregados por los alumnos y el notebook con el enunciado del examen se cargan desde los directorios `entregas` y `examenes`, respectivamente. Una vez cargados los ficheros, se utiliza la función `listar_notebooks` para obtener una lista con los nombres de todos los archivos con extensión `.ipynb` en un directorio dado, excluyendo aquellos que se llamen `solucion.ipynb`.

```python
def preprocesa_notebook(file_path):
    """
    Procesa un notebook Jupyter para extraer el contexto del examen, los enunciados de los ejercicios, el código de solución para cada ejercicio y el nombre del alumno.
    
    Parameters:
        file_path (str): Ruta del archivo del notebook de solución.
        
    Returns:
        dict: Un diccionario con las claves 'contexto_examen', 'enunciados_ejercicios', 'codigo_ejercicios', y 'alumno'.
    """

### 2. Preprocesado de los Notebooks

El preprocesado incluye la limpieza y estructuración de los notebooks para asegurar que estén en un formato adecuado para la evaluación. Esto se realiza mediante la función `preprocesa_notebook`.

```python
def preprocesa_notebook(file_path):
    """
    Procesa un notebook Jupyter para extraer el contexto del examen, los enunciados de los ejercicios, el código de solución para cada ejercicio y el nombre del alumno.
    
    Parameters:
        file_path (str): Ruta del archivo del notebook de solución.
        
    Returns:
        dict: Un diccionario con las claves 'contexto_examen', 'enunciados_ejercicios', 'codigo_ejercicios', y 'alumno'.
    """


### 3. Evaluación de los Notebooks

Utilizando el prompt definido en `prompt.txt` y el modelo de OpenAI (ChatGPT-4 o similar), se evalúan cada uno de los notebooks entregados. Esto genera comentarios y puntuaciones para cada ejercicio basado en los criterios definidos en el prompt. Esta evaluación se realiza mediante la función `evaluar_ejercicios`.

```python
def evaluar_ejercicios(diccionario_resultados, prompt_file='prompt.txt'):
    """
    Evalúa los ejercicios utilizando GPT-4 y devuelve las notas y comentarios para cada ejercicio.
    
    Parameters:
        diccionario_resultados (dict): Diccionario con los datos del notebook preprocesado.
        prompt_file (str): Ruta del archivo de texto que contiene el prompt.
    
    Returns:
        dict: Un diccionario con las evaluaciones de cada ejercicio.
    """


### 4. Extracción de Resultados

Una vez evaluados, se extrae la información en un formato más estructurado usando la función extraer_resultados.

```python
def extraer_resultados(resultado):
    """
    Extrae las puntuaciones, comentarios y comentarios generales de un diccionario de resultados.

    Parámetros:
    resultado (dict): Diccionario que contiene los resultados en forma de texto.

    Retorna:
    dict: Un diccionario con las claves originales y sus correspondientes listas de puntuaciones, comentarios y comentarios generales.
    """


### 5. Generación de Informes


Se generan informes en formato PDF para cada alumno, detallando las puntuaciones y comentarios para cada criterio de evaluación. Además, se crea un archivo Excel con las calificaciones de todos los alumnos.


## ADAPTACIÓN A UN EXAMEN DISTINTO

Para adaptar este proceso a un examen diferente, es necesario modificar el archivo prompt.txt para reflejar los nuevos criterios de evaluación. La estructura del prompt debe seguir los requisitos de forma explicados a continuación:

Estructura del Prompt
El archivo prompt.txt debe seguir el siguiente formato:

Eres un asistente de enseñanza de programación evaluando las respuestas de los estudiantes a un examen de Python. 
A continuación se presenta una descripción del ejercicio y el código del estudiante.

**Descripción del Ejercicio:**
{descripcion}

**Código del estudiante:**
{codigo}

1. @@Nombre criterio@@: Breve descripción de lo que se debe fijar.
2. @@Nombre criterio@@: Breve descripción de lo que se debe fijar.
...

Luego, tiene que venir lo que queremos que devuelva. Esto **NO SE PUEDE MODIFICAR** ya que se usa luego para extraer la información que va en los reports. El formato de la devolución debe ser:

Devuelve cuatro listas solo con la lista proporcionada en formato y nada más:
A. **Puntuaciones**: Una lista de puntuaciones (solo los números, de 0 a 10) correspondiente a cada criterio en el orden en que se presentan.
   - Formato: [0, 10, 7, ...]
B. **Comentarios**: Una lista de comentarios correspondiente a cada criterio en el mismo orden.
   - Formato: ["Comentario para exactitud", "Comentario para claridad", ...]
C. **Comentario General**: Un comentario que ofrezca una idea global sobre el ejercicio teniendo en cuenta los criterios definidos. Especifica claramente si el código genera algún error al ejecutarse. 
   - Formato: ["Comentario general sobre el ejercicio"]
