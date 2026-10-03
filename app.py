import io
import csv
import re
import unicodedata
from dataclasses import dataclass
from statistics import mean
from datetime import datetime

import pandas as pd
import matplotlib.pyplot as plt
import streamlit as st
from matplotlib.backends.backend_pdf import PdfPages


# ============================================================
# CONFIGURACIÓN
# ============================================================

st.set_page_config(
    page_title="Analizador de estudiantes",
    page_icon="UNAJ.png",
    layout="wide"
)

# Logo de la UNAJ
st.image("UNAJ.png", width=120)

st.title("Analizador de estudiantes")


ASIGNATURAS = (
    "programacion",
    "bases_datos",
    "estadistica",
    "arquitectura_nube",
    "aprendizaje_automatico",
    "captura_informacion",
)

NOMBRE_ASIGNATURA = {
    "programacion": "Programación",
    "bases_datos": "Bases de datos",
    "estadistica": "Análisis estadístico",
    "arquitectura_nube": "Arquitecturas en la nube",
    "aprendizaje_automatico": "Aprendizaje automático",
    "captura_informacion": "Captura de información",
}

NOTA_APROBACION = 6.0


# ============================================================
# CLASE ESTUDIANTE
# ============================================================

@dataclass
class Estudiante:
    nombre: str
    apellido: str
    programacion: float
    bases_datos: float
    estadistica: float
    arquitectura_nube: float
    aprendizaje_automatico: float
    captura_informacion: float

    def __post_init__(self):
        self.nombre = self.nombre.strip()
        self.apellido = self.apellido.strip()

        if not self.nombre or not self.apellido:
            raise ValueError(
                "El nombre y el apellido son obligatorios."
            )

        for asignatura in ASIGNATURAS:
            nota = getattr(self, asignatura)

            if not isinstance(nota, (int, float)) or isinstance(nota, bool):
                raise ValueError(
                    f"La nota de {asignatura} debe ser numérica."
                )

            if not 0 <= float(nota) <= 10:
                raise ValueError(
                    f"La nota de {asignatura} debe estar entre 0 y 10."
                )

            setattr(self, asignatura, float(nota))

    @property
    def nombre_completo(self):
        return f"{self.nombre} {self.apellido}"

    def notas(self):
        return {
            a: getattr(self, a)
            for a in ASIGNATURAS
        }

    def promedio_con_aplazos(self):
        return mean(self.notas().values())

    def promedio_sin_aplazos(self):
        aprobadas = [
            n
            for n in self.notas().values()
            if n >= NOTA_APROBACION
        ]

        return mean(aprobadas) if aprobadas else None

    def asignaturas_desaprobadas(self):
        return [
            a
            for a, n in self.notas().items()
            if n < NOTA_APROBACION
        ]

    def cantidad_de_aplazos(self):
        return len(self.asignaturas_desaprobadas())

    def esta_aprobado(self):
        return self.cantidad_de_aplazos() == 0

    def estado(self):
        return (
            "Aprobado"
            if self.esta_aprobado()
            else "Reprobado"
        )


# ============================================================
# CONVERTIR NOTAS
# ============================================================

def convertir_nota(valor, fila, columna):
    texto = str(valor).strip().replace(",", ".")

    if not texto:
        raise ValueError(
            f"Fila {fila}: la columna {columna} está vacía."
        )

    try:
        return float(texto)
    except ValueError:
        raise ValueError(
            f"Fila {fila}: {columna} debe contener un número."
        )


# ============================================================
# CARGAR Y VALIDAR CSV
# ============================================================

def cargar_estudiantes(datos):
    muestra = datos[:4096]

    texto_muestra = muestra.decode(
        "utf-8-sig",
        errors="replace"
    )

    try:
        dialecto = csv.Sniffer().sniff(
            texto_muestra,
            delimiters=",;"
        )
    except csv.Error:
        dialecto = csv.excel

    texto = datos.decode("utf-8-sig")

    lector = csv.DictReader(
        io.StringIO(texto),
        dialect=dialecto
    )

    if not lector.fieldnames:
        raise ValueError(
            "El CSV no tiene encabezados."
        )

    alias_columnas = {
        "bases_d_datos": "bases_datos",
        "analisis_estadistico": "estadistica",
        "arq_nube": "arquitectura_nube",
        "arquitectura_en_la_nube": "arquitectura_nube",
        "arquitecturas_en_la_nube": "arquitectura_nube",
        "ap_automatico": "aprendizaje_automatico",
        "captura_de_informacion": "captura_informacion",
        "cap_informacion": "captura_informacion",
    }

    def normalizar_columna(columna):
        texto = unicodedata.normalize(
            "NFKD",
            str(columna)
        )

        texto = "".join(
            c
            for c in texto
            if not unicodedata.combining(c)
        )

        clave = re.sub(
            r"[^a-z0-9]+",
            "_",
            texto.lower()
        ).strip("_")

        return alias_columnas.get(
            clave,
            clave
        )

    originales = list(lector.fieldnames)

    normalizados = [
        normalizar_columna(c)
        for c in originales
    ]

    if len(set(normalizados)) != len(normalizados):
        raise ValueError(
            "Hay encabezados duplicados o equivalentes "
            "luego de normalizarlos."
        )

    requeridas = {
        "nombre",
        "apellido",
        *ASIGNATURAS
    }

    faltantes = (
        requeridas
        - set(normalizados)
    )

    if faltantes:
        raise ValueError(
            "Faltan columnas obligatorias: "
            + ", ".join(sorted(faltantes))
        )

    columna_original = dict(
        zip(
            normalizados,
            originales
        )
    )

    estudiantes = []

    for numero, original in enumerate(
        lector,
        start=2
    ):
        if original and all(
            v is None or not str(v).strip()
            for v in original.values()
        ):
            continue

        if None in original and original[None]:
            raise ValueError(
                f"Fila {numero}: hay más valores "
                "que columnas en el encabezado."
            )

        fila = {
            canonica: (
                original.get(
                    columna_original[canonica]
                )
                or ""
            ).strip()
            for canonica in requeridas
        }

        estudiante = Estudiante(
            nombre=fila["nombre"],
            apellido=fila["apellido"],
            **{
                a: convertir_nota(
                    fila[a],
                    numero,
                    a
                )
                for a in ASIGNATURAS
            }
        )

        estudiantes.append(estudiante)

    if not estudiantes:
        raise ValueError(
            "El archivo no contiene estudiantes."
        )

    return estudiantes


# ============================================================
# TABLA DE DATOS
# ============================================================

def crear_tabla_datos(estudiantes):
    datos_tabla = []

    for e in estudiantes:
        fila = {
            "Estudiante": e.nombre_completo
        }

        for a in ASIGNATURAS:
            fila[
                NOMBRE_ASIGNATURA[a]
            ] = getattr(e, a)

        datos_tabla.append(fila)

    return pd.DataFrame(datos_tabla)


# ============================================================
# ANÁLISIS INDIVIDUAL
# ============================================================

def crear_analisis_individual(estudiantes):
    individual = []

    for e in estudiantes:
        sin = e.promedio_sin_aplazos()

        individual.append({
            "Estudiante": e.nombre_completo,

            "Promedio con aplazos":
                e.promedio_con_aplazos(),

            "Promedio sin aplazos":
                sin,

            "Cantidad de aplazos":
                e.cantidad_de_aplazos(),

            "Asignaturas desaprobadas":
                ", ".join(
                    NOMBRE_ASIGNATURA[a]
                    for a in e.asignaturas_desaprobadas()
                )
                or "Ninguna",

            "Estado":
                e.estado(),
        })

    return pd.DataFrame(individual)


# ============================================================
# ESTADÍSTICAS
# ============================================================

def calcular_estadisticas(estudiantes):
    promedios = {
        a: mean(
            getattr(e, a)
            for e in estudiantes
        )
        for a in ASIGNATURAS
    }

    aprobacion = {
        a:
            100
            * sum(
                getattr(e, a) >= NOTA_APROBACION
                for e in estudiantes
            )
            / len(estudiantes)
        for a in ASIGNATURAS
    }

    cantidad_aprobados = sum(
        e.esta_aprobado()
        for e in estudiantes
    )

    porcentaje_aprobados = (
        100
        * cantidad_aprobados
        / len(estudiantes)
    )

    df_estadisticas = pd.DataFrame([
        {
            "Asignatura":
                NOMBRE_ASIGNATURA[a],

            "Promedio":
                promedios[a],

            "Aprobación (%)":
                aprobacion[a]
        }
        for a in ASIGNATURAS
    ])

    mayor = max(
        promedios,
        key=promedios.get
    )

    menor = min(
        promedios,
        key=promedios.get
    )

    return (
        promedios,
        aprobacion,
        cantidad_aprobados,
        porcentaje_aprobados,
        df_estadisticas,
        mayor,
        menor
    )


# ============================================================
# GRÁFICO DE PROMEDIOS
# ============================================================

def crear_grafico_promedios(promedios):
    etiquetas = [
        NOMBRE_ASIGNATURA[a]
        for a in ASIGNATURAS
    ]

    valores = [
        promedios[a]
        for a in ASIGNATURAS
    ]

    fig, ax = plt.subplots(
        figsize=(12, 6)
    )

    barras = ax.bar(
        etiquetas,
        valores
    )

    ax.set_title(
        "Promedio del grupo por asignatura"
    )

    ax.set_ylabel(
        "Promedio"
    )

    ax.set_ylim(
        0,
        10
    )

    ax.tick_params(
        axis="x",
        rotation=25
    )

    ax.grid(
        axis="y",
        alpha=0.25
    )

    for barra, valor in zip(
        barras,
        valores
    ):
        ax.text(
            barra.get_x()
            + barra.get_width() / 2,

            valor + 0.1,

            f"{valor:.2f}",

            ha="center"
        )

    fig.tight_layout()

    return fig


# ============================================================
# GRÁFICO DE APROBACIÓN
# ============================================================

def crear_grafico_aprobacion(aprobacion):
    etiquetas = [
        NOMBRE_ASIGNATURA[a]
        for a in ASIGNATURAS
    ]

    valores = [
        aprobacion[a]
        for a in ASIGNATURAS
    ]

    fig, ax = plt.subplots(
        figsize=(12, 6)
    )

    barras = ax.bar(
        etiquetas,
        valores
    )

    ax.set_title(
        "Porcentaje de aprobación por asignatura"
    )

    ax.set_ylabel(
        "Aprobación (%)"
    )

    ax.set_ylim(
        0,
        100
    )

    ax.tick_params(
        axis="x",
        rotation=25
    )

    ax.grid(
        axis="y",
        alpha=0.25
    )

    for barra, valor in zip(
        barras,
        valores
    ):
        ax.text(
            barra.get_x()
            + barra.get_width() / 2,

            valor + 1,

            f"{valor:.1f}%",

            ha="center"
        )

    fig.tight_layout()

    return fig


# ============================================================
# GRÁFICO DE ESTADO
# ============================================================

def crear_grafico_estado(
    cantidad_aprobados,
    cantidad_reprobados
):
    valores = [
        cantidad_aprobados,
        cantidad_reprobados
    ]

    fig, ax = plt.subplots(
        figsize=(7, 5)
    )

    barras = ax.bar(
        [
            "Aprobados",
            "Reprobados"
        ],
        valores
    )

    ax.set_title(
        "Estado académico del grupo"
    )

    ax.set_ylabel(
        "Cantidad de estudiantes"
    )

    ax.grid(
        axis="y",
        alpha=0.25
    )

    for barra, valor in zip(
        barras,
        valores
    ):
        ax.text(
            barra.get_x()
            + barra.get_width() / 2,

            valor + 0.1,

            str(valor),

            ha="center"
        )

    fig.tight_layout()

    return fig


# ============================================================
# GENERAR PDF
# ============================================================

def generar_pdf(
    estudiantes,
    nombre_archivo,
    promedios,
    aprobacion,
    cantidad_aprobados,
    porcentaje_aprobados,
    mayor,
    menor
):
    buffer = io.BytesIO()

    with PdfPages(buffer) as pdf:

        fig = plt.figure(
            figsize=(11.69, 8.27)
        )

        fig.patch.set_facecolor(
            "white"
        )

        fig.text(
            0.05,
            0.95,
            "Informe de evaluación estudiantil",
            fontsize=20,
            weight="bold"
        )

        fig.text(
            0.05,
            0.91,
            f"Archivo: {nombre_archivo} | "
            f"Generado: "
            f"{datetime.now().strftime('%d/%m/%Y %H:%M')} | "
            f"Estudiantes: {len(estudiantes)}",
            fontsize=9
        )

        fig.text(
            0.05,
            0.865,
            f"Aprobación global: "
            f"{cantidad_aprobados}/"
            f"{len(estudiantes)} estudiantes "
            f"({porcentaje_aprobados:.1f}%)",
            fontsize=12,
            weight="bold"
        )

        fig.text(
            0.05,
            0.835,
            "Criterio: aprobado si obtiene nota ≥ 6 "
            "en las seis asignaturas. "
            "El promedio sin aplazos excluye notas menores a 6.",
            fontsize=8.5
        )

        ax_tabla = fig.add_axes(
            [
                0.05,
                0.20,
                0.48,
                0.57
            ]
        )

        ax_tabla.axis("off")

        resumen_celdas = [
            [
                NOMBRE_ASIGNATURA[a],
                f"{promedios[a]:.2f}",
                f"{aprobacion[a]:.1f}%"
            ]
            for a in ASIGNATURAS
        ]

        tabla = ax_tabla.table(
            cellText=resumen_celdas,
            colLabels=[
                "Asignatura",
                "Promedio",
                "Aprobación"
            ],
            loc="center",
            cellLoc="left",
            colLoc="left",
            colWidths=[
                0.58,
                0.20,
                0.22
            ]
        )

        tabla.auto_set_font_size(False)
        tabla.set_fontsize(8.5)
        tabla.scale(1, 1.8)

        ax = fig.add_axes(
            [
                0.58,
                0.22,
                0.37,
                0.53
            ]
        )

        etiquetas_cortas = [
            "Prog.",
            "Bases\nde datos",
            "Estadística",
            "Arq. nube",
            "Aprend.\nautomático",
            "Captura\ninformación"
        ]

        valores = [
            promedios[a]
            for a in ASIGNATURAS
        ]

        barras = ax.bar(
            range(len(valores)),
            valores
        )

        ax.set_xticks(
            range(len(valores))
        )

        ax.set_xticklabels(
            etiquetas_cortas,
            fontsize=8
        )

        ax.set_ylim(
            0,
            10
        )

        ax.set_ylabel(
            "Promedio (0–10)"
        )

        ax.set_title(
            "Promedio del grupo por asignatura",
            loc="left",
            fontsize=11,
            weight="bold"
        )

        ax.grid(
            axis="y",
            alpha=0.2
        )

        for barra, valor in zip(
            barras,
            valores
        ):
            ax.text(
                barra.get_x()
                + barra.get_width() / 2,

                min(
                    valor + 0.18,
                    9.75
                ),

                f"{valor:.2f}",

                ha="center",

                fontsize=8
            )

        fig.text(
            0.05,
            0.135,
            f"Mayor rendimiento: "
            f"{NOMBRE_ASIGNATURA[mayor]} "
            f"({promedios[mayor]:.2f})",
            fontsize=9,
            weight="bold"
        )

        fig.text(
            0.05,
            0.105,
            f"Menor rendimiento: "
            f"{NOMBRE_ASIGNATURA[menor]} "
            f"({promedios[menor]:.2f})",
            fontsize=9,
            weight="bold"
        )

        fig.text(
            0.05,
            0.055,
            "La aprobación por asignatura se muestra "
            "en la tabla; la aprobación global requiere "
            "aprobar las seis materias.",
            fontsize=8
        )

        pdf.savefig(
            fig,
            bbox_inches="tight"
        )

        plt.close(fig)

        filas_por_pagina = 22

        encabezados = [
            "Estudiante",
            "Prog.",
            "Bases\nde datos",
            "Estad.",
            "Arq. nube",
            "Aprend.\nautom.",
            "Captura",
            "Prom. con\naplazos",
            "Prom. sin\naplazos",
            "Aplazos",
            "Estado"
        ]

        todas_las_filas = []

        for e in estudiantes:

            promedio_sin = (
                e.promedio_sin_aplazos()
            )

            notas_mostradas = [
                f"{getattr(e, a):.1f}"
                + (
                    "*"
                    if getattr(e, a)
                    < NOTA_APROBACION
                    else ""
                )
                for a in ASIGNATURAS
            ]

            todas_las_filas.append(
                [
                    e.nombre_completo,
                    *notas_mostradas,
                    f"{e.promedio_con_aplazos():.2f}",
                    (
                        "—"
                        if promedio_sin is None
                        else f"{promedio_sin:.2f}"
                    ),
                    str(
                        e.cantidad_de_aplazos()
                    ),
                    e.estado()
                ]
            )

        anchos = [
            0.17
        ] + [
            0.055
        ] * 6 + [
            0.095,
            0.095,
            0.06,
            0.10
        ]

        suma_anchos = sum(
            anchos
        )

        anchos = [
            a / suma_anchos
            for a in anchos
        ]

        for inicio in range(
            0,
            len(todas_las_filas),
            filas_por_pagina
        ):

            pagina = (
                inicio
                // filas_por_pagina
                + 1
            )

            bloque = todas_las_filas[
                inicio:
                inicio + filas_por_pagina
            ]

            fig, ax = plt.subplots(
                figsize=(11.69, 8.27)
            )

            fig.patch.set_facecolor(
                "white"
            )

            ax.axis("off")

            fig.suptitle(
                f"Detalle individual de estudiantes "
                f"— página {pagina}",
                x=0.05,
                y=0.96,
                ha="left",
                fontsize=16,
                weight="bold"
            )

            fig.text(
                0.05,
                0.91,
                "* Nota menor que 6 (aplazo). "
                "El promedio sin aplazos excluye esas notas.",
                fontsize=8
            )

            tabla = ax.table(
                cellText=bloque,
                colLabels=encabezados,
                cellLoc="center",
                colLoc="center",
                colWidths=anchos,
                bbox=[
                    0.02,
                    0.08,
                    0.96,
                    0.79
                ]
            )

            tabla.auto_set_font_size(False)
            tabla.set_fontsize(6.8)

            fig.text(
                0.05,
                0.035,
                f"Reporte académico | "
                f"{len(estudiantes)} estudiante(s)",
                fontsize=7
            )

            pdf.savefig(
                fig,
                bbox_inches="tight"
            )

            plt.close(fig)

    buffer.seek(0)

    return buffer


# ============================================================
# INTERFAZ
# ============================================================

st.write(
    "Subí un archivo CSV para analizar el rendimiento "
    "académico de los estudiantes."
)

st.info(
    "El archivo debe contener las columnas "
    "Nombre, Apellido y las seis asignaturas."
)


# ============================================================
# SUBIR ARCHIVO
# ============================================================

archivo = st.file_uploader(
    "📂 Seleccioná el archivo CSV",
    type=["csv"]
)


if archivo is not None:

    st.success(
        f"Archivo recibido: {archivo.name}"
    )

    try:

        contenido = archivo.getvalue()

        estudiantes = cargar_estudiantes(
            contenido
        )

        st.success(
            f"✅ Validación completada. "
            f"Se encontraron {len(estudiantes)} estudiantes."
        )

        df_datos = crear_tabla_datos(
            estudiantes
        )

        df_individual = crear_analisis_individual(
            estudiantes
        )

        (
            promedios,
            aprobacion,
            cantidad_aprobados,
            porcentaje_aprobados,
            df_estadisticas,
            mayor,
            menor
        ) = calcular_estadisticas(
            estudiantes
        )

        # ====================================================
        # RESUMEN
        # ====================================================

        st.header("📌 Resumen")

        col1, col2, col3, col4 = st.columns(4)

        with col1:
            st.metric(
                "Estudiantes",
                len(estudiantes)
            )

        with col2:
            st.metric(
                "Aprobados",
                cantidad_aprobados
            )

        with col3:
            st.metric(
                "Reprobados",
                len(estudiantes)
                - cantidad_aprobados
            )

        with col4:
            st.metric(
                "Aprobación global",
                f"{porcentaje_aprobados:.1f}%"
            )

        # ====================================================
        # DATOS CARGADOS
        # ====================================================

        st.header("📋 Datos cargados")

        st.dataframe(
            df_datos.style.format(
                {
                    c: "{:.2f}"
                    for c in df_datos.columns[1:]
                }
            ),
            use_container_width=True
        )

        # ====================================================
        # ANÁLISIS INDIVIDUAL
        # ====================================================

        st.header("👩‍🎓 Análisis individual")

        st.dataframe(
            df_individual.style.format(
                {
                    "Promedio con aplazos":
                        "{:.2f}",

                    "Promedio sin aplazos":
                        lambda x:
                        "No disponible"
                        if pd.isna(x)
                        else f"{x:.2f}"
                }
            ),
            use_container_width=True
        )

        # ====================================================
        # ESTADÍSTICAS
        # ====================================================

        st.header("📊 Estadísticas del grupo")

        st.dataframe(
            df_estadisticas.style.format(
                {
                    "Promedio":
                        "{:.2f}",

                    "Aprobación (%)":
                        "{:.2f}%"
                }
            ),
            use_container_width=True
        )

        col1, col2 = st.columns(2)

        with col1:
            st.info(
                f"📈 Mayor promedio: "
                f"{NOMBRE_ASIGNATURA[mayor]} "
                f"({promedios[mayor]:.2f})"
            )

        with col2:
            st.warning(
                f"📉 Menor promedio: "
                f"{NOMBRE_ASIGNATURA[menor]} "
                f"({promedios[menor]:.2f})"
            )

        # ====================================================
        # GRÁFICOS
        # ====================================================

        st.header("📈 Gráficos")

        grafico_promedios = crear_grafico_promedios(
            promedios
        )

        st.pyplot(
            grafico_promedios
        )

        plt.close(
            grafico_promedios
        )

        grafico_aprobacion = crear_grafico_aprobacion(
            aprobacion
        )

        st.pyplot(
            grafico_aprobacion
        )

        plt.close(
            grafico_aprobacion
        )

        reprobados = (
            len(estudiantes)
            - cantidad_aprobados
        )

        grafico_estado = crear_grafico_estado(
            cantidad_aprobados,
            reprobados
        )

        st.pyplot(
            grafico_estado
        )

        plt.close(
            grafico_estado
        )

        # ====================================================
        # DESCARGAS
        # ====================================================

        st.header("📥 Descargar resultados")

        csv_individual = df_individual.to_csv(
            index=False,
            encoding="utf-8-sig"
        ).encode("utf-8-sig")

        csv_estadisticas = df_estadisticas.to_csv(
            index=False,
            encoding="utf-8-sig"
        ).encode("utf-8-sig")

        pdf = generar_pdf(
            estudiantes,
            archivo.name,
            promedios,
            aprobacion,
            cantidad_aprobados,
            porcentaje_aprobados,
            mayor,
            menor
        )

        col1, col2, col3 = st.columns(3)

        with col1:
            st.download_button(
                label="📄 Descargar PDF",
                data=pdf,
                file_name="reporte_academico.pdf",
                mime="application/pdf"
            )

        with col2:
            st.download_button(
                label="📊 Descargar análisis individual",
                data=csv_individual,
                file_name="reporte_individual.csv",
                mime="text/csv"
            )

        with col3:
            st.download_button(
                label="📊 Descargar estadísticas",
                data=csv_estadisticas,
                file_name="estadisticas_asignaturas.csv",
                mime="text/csv"
            )

        st.success(
            "✅ Análisis terminado. "
            "Podés descargar los resultados desde los botones."
        )

    except Exception as e:

        st.error(
            f"❌ No se pudo analizar el archivo: {e}"
        )
