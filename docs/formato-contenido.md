# Formato estándar de documentos Word para el pipeline

Este documento define cómo deben estar estructurados los archivos `.docx` que ingresan al pipeline de Humpy. Seguir este formato garantiza que el extractor procese el contenido de forma confiable y sin intervención manual.

---

## Principio clave

El pipeline lee **estilos de Word** (Heading 1, Heading 2, etc.), no formato visual (colores, negrita manual, tamaño de fuente). Por eso es obligatorio usar los estilos predefinidos, no aplicar formato directo al texto.

> ❌ Incorrecto: escribir "MEMBRANA CELULAR" en rojo y negrita manualmente.  
> ✅ Correcto: escribir "MEMBRANA CELULAR" aplicando el estilo **Heading 2** de Word.

---

## Estructura obligatoria del documento

### Nivel 1 — Título del documento
- **Estilo Word:** `Title`
- **Contenido:** Nombre del curso o tema general.
- **Una sola vez por documento.**

```
Ejemplo: FISIOLOGÍA CELULAR
```

---

### Nivel 2 — Microlección
- **Estilo Word:** `Heading 1`
- **Formato:** `MICROLECCIÓN N: Título de la microlección`
- **Cada microlección es una unidad independiente de contenido.**

```
Ejemplo: MICROLECCIÓN 1: Membrana celular
```

---

### Nivel 3 — Bloque temático
- **Estilo Word:** `Heading 2`
- **Contenido:** El nombre del concepto, sección o subtema dentro de la microlección.

```
Ejemplo: MEMBRANA CELULAR
Ejemplo: Funciones de la membrana
```

---

### Nivel 4 — Subbloque (opcional)
- **Estilo Word:** `Heading 3`
- **Uso:** Solo cuando un bloque temático tiene subsecciones diferenciadas.

```
Ejemplo: Transporte activo
Ejemplo: Transporte pasivo
```

---

### Cuerpo de texto
- **Estilo Word:** `Normal`
- Párrafos de explicación, descripción y desarrollo de conceptos.
- Usar negrita (`Ctrl+N`) para resaltar **términos clave** dentro del párrafo.
- Usar cursiva para *nombres científicos o términos en otro idioma*.
- **No usar colores manuales en el cuerpo de texto.**

---

### Listas
- Usar las listas de Word (`Inicio > Viñetas` o `Inicio > Numeración`), no escribir `A)`, `B)`, `-` manualmente.
- Para listas anidadas, usar `Tab` para aumentar nivel de sangría.

```
✅ Correcto (lista de Word):
  • Delimita y protege a las células.
  • Permeabilidad selectiva.
  • Posee receptores químicos.

❌ Incorrecto:
  A) Delimita y protege a las células.
  B) Permeabilidad selectiva.
  C) Posee receptores químicos.
```

---

### Imágenes
- Insertar imágenes **inline** (no flotantes, no con texto alrededor).
- Inmediatamente debajo de cada imagen, escribir una línea de texto con el estilo `Normal` que comience con la etiqueta `[IMG:` seguida de una descripción breve y `]`.

```
[IMG: Diagrama de la membrana celular con bicapa lipídica]
[IMG: Curva de Frank-Starling mostrando relación longitud-tensión]
```

> Esta descripción se usa como `alt` en el HTML generado y como referencia para ubicar la imagen en el output.

---

### Énfasis de color (conceptos críticos)
No usar colores arbitrarios. Si un concepto es especialmente importante, marcar el texto con el estilo de carácter `Strong` (negrita) o usar corchetes con etiqueta:

| Etiqueta en el texto | Equivalente en HTML generado |
|---|---|
| `[ROJO: texto]` | `<span class="red">texto</span>` |
| `[AMARILLO: texto]` | `<span class="highlight-yellow">texto</span>` |
| `[AZUL: texto]` | `<span style="color:#1976d2;font-weight:bold">texto</span>` |

```
Ejemplo de uso en párrafo:
La membrana tiene [ROJO: permeabilidad selectiva], lo que le permite
controlar el paso de sustancias entre el medio intra y extracelular.
```

---

### Fórmulas matemáticas
- Usar el editor de ecuaciones de Word (`Insertar > Ecuación`).
- Inmediatamente debajo, escribir la fórmula también en texto plano entre etiquetas `[FORMULA: ...]` como fallback.

```
[FORMULA: GC = Vol. eyección × Fr. Cardíaca]
```

---

### Separación entre microlecciones
- Insertar un `Salto de página` (`Ctrl+Enter`) antes de cada nuevo `Heading 1`.
- Esto garantiza que el extractor delimite correctamente cada microlección.

---

## Resumen de estilos permitidos

| Elemento | Estilo Word | Notas |
|---|---|---|
| Título del documento | `Title` | Una sola vez |
| Microlección | `Heading 1` | Formato: `MICROLECCIÓN N: Título` |
| Bloque temático | `Heading 2` | Concepto principal |
| Subbloque | `Heading 3` | Opcional |
| Cuerpo | `Normal` | Sin colores manuales |
| Lista | Viñetas / Numeración de Word | No listas manuales con letras |
| Énfasis crítico | `[ROJO:]`, `[AMARILLO:]`, `[AZUL:]` | Etiquetas en texto |
| Descripción de imagen | `Normal` con `[IMG: descripción]` | Debajo de cada imagen |
| Fórmulas | Editor de ecuaciones + `[FORMULA: ...]` | Fallback en texto |

---

## Checklist antes de entregar el documento

- [ ] El título del documento usa el estilo `Title`
- [ ] Cada microlección empieza con `Heading 1` y el formato `MICROLECCIÓN N: Título`
- [ ] Los bloques usan `Heading 2` (y `Heading 3` si aplica)
- [ ] El cuerpo usa estilo `Normal` (sin colores manuales)
- [ ] Las listas son viñetas/numeración de Word (no letras manuales)
- [ ] Cada imagen tiene su línea `[IMG: descripción]` debajo
- [ ] Los énfasis especiales usan las etiquetas `[ROJO:]`, `[AMARILLO:]`, `[AZUL:]`
- [ ] Hay un salto de página antes de cada nueva microlección
- [ ] Las fórmulas tienen su versión en texto `[FORMULA: ...]`

---

## Ejemplo de estructura completa

```
[Estilo: Title]
FISIOLOGÍA CELULAR

[Salto de página]

[Estilo: Heading 1]
MICROLECCIÓN 1: Membrana celular

[Estilo: Heading 2]
¿Qué es la membrana celular?

[Estilo: Normal]
La membrana celular es una bicapa lipídica que delimita la célula y regula
el paso de sustancias. Tiene [ROJO: permeabilidad selectiva], lo que le
permite controlar su medio interno.

[Estilo: Heading 2]
Funciones principales

[Lista de viñetas de Word]
• Delimita y protege a las células.
• Permeabilidad selectiva.
• Posee receptores químicos para señalización.

[Imagen insertada inline]
[IMG: Diagrama esquemático de la bicapa lipídica de la membrana celular]

[Salto de página]

[Estilo: Heading 1]
MICROLECCIÓN 2: Transporte celular

...
```

---

## Por qué este formato

El extractor del pipeline (`src/extractor.py`) usa la librería `python-docx` para leer el documento. Esta librería puede detectar **estilos de párrafo** (Heading 1, Heading 2, Normal) de forma confiable, pero no puede interpretar colores manuales ni tamaños de fuente como estructura semántica. Al seguir este estándar, el pipeline puede:

1. Dividir el documento en microlecciones automáticamente (por Heading 1)
2. Identificar bloques dentro de cada microlección (por Heading 2/3)
3. Mapear énfasis visuales (por etiquetas `[ROJO:]`, etc.)
4. Ubicar imágenes y sus descripciones (por `[IMG:]`)
5. Generar HTML y preguntas con estructura predecible
