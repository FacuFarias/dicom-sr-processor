# Guía de implementación Frontend: Definiciones de Variables (DICOM SR)

## 1) Objetivo
Implementar en frontend un módulo de **Definiciones de Variables Canónicas** para administrar el catálogo usado por el motor de mapeo SR.

Este módulo gestiona la tabla `dicom_sr.variable_definition`.

---

## 2) Modelo de datos real (backend actual)
Campos existentes:

- `id: bigint` (autogenerado)
- `canonical_code: text` (**único**, requerido)
- `canonical_name: text` (requerido)
- `unit: text` (opcional)
- `value_type: text` (opcional)
- `description: text` (opcional)
- `active: boolean` (default `true`)
- `created_at: timestamptz` (autogenerado)

Referencia en código:
- `models/variable_definition.py`
- `database/connection.py` (creación de tabla)
- `database/repositories/variable_definition_repository.py`

---

## 3) Alcance UX (MVP)
Implementar exactamente 2 vistas:

1. **Listado de definiciones**
2. **Formulario crear/editar definición**

Sin features extra en esta fase (sin importación masiva, sin versionado, sin drag & drop, sin dashboards).

---

## 4) Contrato API sugerido (para backend)
> Nota: hoy no hay endpoints REST visibles en `nextris-dev-react` para estas tablas. Este contrato es el que frontend debe esperar.

Base path recomendado:

`/api/config/sr-variable-definitions`

### 4.1 Listar
- **GET** `/api/config/sr-variable-definitions?search=&active=true&page=1&per_page=20`
- Respuesta:

```json
{
  "success": true,
  "data": {
    "items": [
      {
        "id": 1,
        "canonical_code": "ica_psv",
        "canonical_name": "ICA Peak Systolic Velocity",
        "unit": "cm/s",
        "value_type": "NUM",
        "description": "Velocidad sistólica pico de carótida interna",
        "active": true,
        "created_at": "2026-03-08T12:00:00Z"
      }
    ],
    "pagination": {
      "page": 1,
      "per_page": 20,
      "total": 1,
      "total_pages": 1
    }
  },
  "message": "OK"
}
```

### 4.2 Crear
- **POST** `/api/config/sr-variable-definitions`
- Body:

```json
{
  "canonical_code": "ica_psv",
  "canonical_name": "ICA Peak Systolic Velocity",
  "unit": "cm/s",
  "value_type": "NUM",
  "description": "Velocidad sistólica pico",
  "active": true
}
```

### 4.3 Obtener detalle
- **GET** `/api/config/sr-variable-definitions/:id`

### 4.4 Actualizar
- **PUT/PATCH** `/api/config/sr-variable-definitions/:id`
- Body parcial permitido para `PATCH`.

### 4.5 Activar/Desactivar (borrado lógico)
- **PATCH** `/api/config/sr-variable-definitions/:id/status`
- Body:

```json
{ "active": false }
```

### 4.6 Errores esperados
- `409` si `canonical_code` ya existe.
- `400` para validaciones.
- `404` si no existe `id`.

---

## 5) Reglas de validación frontend

### `canonical_code`
- Requerido.
- Único (validado por backend; frontend muestra error amigable).
- Normalizar a `lower_snake_case` en UI antes de enviar.
- Longitud recomendada: 3-80.

### `canonical_name`
- Requerido.
- Longitud recomendada: 3-150.

### `unit`
- Opcional.
- Ejemplos: `cm/s`, `mm`, `%`, `bpm`.

### `value_type`
- Opcional en DB, pero en UI sugerir catálogo controlado para consistencia.
- Catálogo recomendado (alineado a SR):
  - `NUM`
  - `TEXT`
  - `DATETIME`
  - `CODE`

### `description`
- Opcional.
- Mostrar contador de caracteres.

### `active`
- Booleano.
- No borrar físicamente desde UI en MVP.

---

## 6) Diseño de pantalla (MVP)

## 6.1 Listado
Columnas:
- Código canónico
- Nombre canónico
- Tipo (`value_type`)
- Unidad
- Estado (`Activo/Inactivo`)
- Fecha creación
- Acciones (`Editar`, `Activar/Desactivar`)

Controles:
- Búsqueda por texto (`canonical_code` o `canonical_name`)
- Filtro por estado (`Todos/Activos/Inactivos`)
- Botón `Nueva definición`

## 6.2 Formulario Crear/Editar
Campos:
- Código canónico
- Nombre
- Tipo
- Unidad
- Descripción
- Activa (switch)

Acciones:
- `Guardar`
- `Cancelar`

Mensajes:
- Toast éxito al guardar.
- Mensaje claro para `409`: “El código canónico ya existe”.

---

## 7) Tipos TypeScript sugeridos

```ts
export type VariableValueType = 'NUM' | 'TEXT' | 'DATETIME' | 'CODE' | string;

export interface VariableDefinition {
  id: number;
  canonical_code: string;
  canonical_name: string;
  unit: string | null;
  value_type: VariableValueType | null;
  description: string | null;
  active: boolean;
  created_at: string;
}

export interface VariableDefinitionPayload {
  canonical_code: string;
  canonical_name: string;
  unit?: string | null;
  value_type?: VariableValueType | null;
  description?: string | null;
  active?: boolean;
}
```

---

## 8) Flujo funcional esperado

1. Usuario entra a Configuración → Variables SR.
2. Front hace `GET` y pinta listado paginado.
3. Usuario crea/edita definición.
4. Front valida campos mínimos.
5. Envía `POST` o `PATCH`.
6. Backend responde y front refresca listado.
7. Usuario desactiva definición (`PATCH status`) en lugar de borrarla.

---

## 9) Integración con mapeos (siguiente fase)
Las definiciones creadas aquí se usarán en `facility_variable_mapping.canonical_variable_definition_id`.

Por eso, en la pantalla de mapeos (fase 2):
- El selector de definición debe consumir **solo definiciones activas**.
- Mostrar en dropdown: `canonical_code — canonical_name`.

## 9.1 Integración con criterios estructurados (infraestructura actual)

La pantalla de criterios estructurados ya usa selector jerárquico de variables (árbol) y no una lista plana.

- Fuente backend: endpoints `/api/structured-reports/.../variables/tree`.
- Selección final: nodo hoja `type=variable`.
- Persistencia de condición:
  - `variable` (legacy)
  - `variable_key`
  - `variable_node_id`
  - `variable_label`

Este módulo (`variable_definition`) sigue siendo el catálogo canónico y no reemplaza el selector de árbol; lo alimenta de forma indirecta vía mappings.

---

## 10) Criterios de aceptación (QA)

- Se puede crear una definición válida y verla en listado.
- No permite guardar `canonical_code` duplicado (muestra error amigable).
- Se puede editar nombre/tipo/unidad/descripción.
- Se puede activar/desactivar sin eliminar registro.
- La búsqueda filtra por código o nombre.
- La UI soporta campos nulos (`unit`, `value_type`, `description`).

---

## 11) Recomendación de rollout
1. Implementar UI con contrato anterior.
2. Si backend aún no expone endpoints, usar mock adapter temporal en frontend.
3. Conectar al endpoint real sin cambiar componentes (solo capa `service/api`).

---

## 12) Referencias técnicas internas
- `models/variable_definition.py`
- `database/repositories/variable_definition_repository.py`
- `database/connection.py`
- `services/variable_mapping_service.py` (consumo posterior en mapeo)
