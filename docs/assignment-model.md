# Modelo de asignación de FIGUELOVERS

## Fuente única de verdad

El grafo enviado por el editor es la fuente de verdad del problema de
asignación. El endpoint `POST /api/v1/graph/algorithms/assignment` acepta el
campo `graph` y genera la matriz en el backend en cada solicitud. Por tanto,
una modificación de nodos o aristas produce una nueva matriz y no puede dejar
una matriz calculada anteriormente como estado válido.

El endpoint `POST /api/v1/graph/validate` también expone esa representación
como `data.matriz_costos_asignacion`, junto con `forbidden_cells`, para que el
frontend pueda visualizarla sin convertir una ausencia en un costo real.

## Interpretación bipartita

Para un grafo con nodos `N = [n1, ..., nk]` se construye un problema bipartito:

- La fila `i` representa el origen `ni`.
- La columna `j` representa el destino `nj`.
- La arista dirigida `ni -> nj` habilita la celda `(i, j)`.
- El peso de la arista es el costo de `(i, j)`.
- Si no existe `ni -> nj`, `(i, j)` es una asignación prohibida.
- `ni -> nj` no habilita `nj -> ni`.
- Un peso `0` es un costo válido; no significa ausencia.

Con el grafo cuadrado usado por el módulo, una solución perfecta selecciona
exactamente una celda permitida en cada fila y en cada columna. Esto modela
una asignación uno-a-uno entre el conjunto de orígenes y el conjunto de
destinos, aunque ambos conjuntos usen los mismos identificadores del editor.
No significa que un nodo tenga que asignarse a sí mismo.

## Celdas prohibidas y factibilidad

La matriz numérica se acompaña de una máscara booleana:

- `forbidden_cells[i][j] == false`: la arista existe y su costo es real.
- `forbidden_cells[i][j] == true`: la arista no existe y la celda no se puede
  seleccionar.

Internamente, el algoritmo húngaro recibe un costo `M` suficientemente grande
para las celdas prohibidas porque `scipy.optimize.linear_sum_assignment`
requiere una matriz numérica. Después de calcular la asignación, el backend
valida cada par contra la máscara. Si se seleccionó una celda prohibida, la
respuesta no se presenta como óptima: devuelve `status: "infeasible"` y una
lista de asignaciones vacía.

En `initial_cost_matrix` y en `steps[*].matrix`, las posiciones prohibidas se
serializan como JSON `null`. Las reducciones de filas, columnas, ajustes y la
transformación de maximización ignoran esas posiciones; por eso nunca aparece
el costo artificial `M` en el paso a paso.

La respuesta distingue:

- `status: "optimal"`: asignación válida y costo total calculado con los
  pesos originales.
- `status: "infeasible"`: no existe una asignación perfecta usando solo
  aristas existentes.
- Error HTTP `4xx/5xx`: la solicitud es inválida o ocurrió un error de
  ejecución; no es una solución matemática.

La matriz `cost_matrix` sigue aceptándose para compatibilidad con clientes
anteriores. Para el módulo basado en el editor, debe usarse `graph`; el
frontend no debe mantener ni enviar una matriz independiente.

## Demostración

El grafo:

```text
b -> a (1), b -> d (1), c -> a (1), d -> c (1)
```

no tiene una asignación perfecta de cuatro filas por cuatro columnas. El
backend responde `status: "infeasible"` y no devuelve asignaciones ficticias.
Al agregar o modificar aristas para habilitar una permutación completa, la
misma solicitud con el grafo actualizado responde `status: "optimal"` y el
`total_cost` es la suma de los pesos de esas aristas.
