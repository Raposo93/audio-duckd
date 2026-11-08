# Configuración

Sin `--config` se usan los valores predeterminados de
[config.example.json](../config.example.json). Para personalizarlos, copiar ese
archivo y pasar la ruta explícitamente (también funciona con `--inspect`):

```sh
.venv/bin/python -m audio_duckd --config config.example.json
```

El archivo es JSON UTF-8. Todos los campos son opcionales y los omitidos conservan
su valor predeterminado; no se busca automáticamente ningún archivo ni se recarga
durante la ejecución. Reiniciar el daemon para aplicar cambios. Un archivo ausente,
JSON inválido, claves desconocidas o duplicadas y valores inválidos producen un
mensaje de error y salida con código 2 **antes de conectar o modificar audio**.

| Parámetro | Predeterminado | Significado y validación |
| --- | --- | --- |
| `applications.linphone` | `["linphone"]` | Binarios cuya presencia en reproducción o captura activa el ducking. |
| `applications.discord` | `["Discord"]` | Binarios reservados para Discord, excluidos de los objetivos. |
| `applications.targets` | `["brave"]` | Binarios cuyos streams de reproducción se atenúan. |
| `attenuation_factor` | `0.2` | Multiplicador del volumen original de cada canal, entre 0 y 1 inclusive. 0 silencia por volumen sin cambiar mute; 1 conserva el volumen. |

Cada selector es el nombre exacto y sensible a mayúsculas de
`application.process.binary`, tal como aparece en `--inspect` tras retirar el
sufijo ` (deleted)`. Las tres listas deben ser no vacías, sin duplicados ni
solapamientos entre ellas. No se permiten rutas, espacios ni comodines. Se pueden
incluir varios binarios por aplicación si la instalación usa variantes.
Seleccionar Brave afecta a **todos sus streams coincidentes, sin distinguir
pestañas**, páginas ni perfiles. Solo se modifican streams de reproducción de los
objetivos; los selectores de Linphone y Discord quedan excluidos también en el
backend de escritura.

### Contrato de parámetros de Discord

Estos campos quedan validados y disponibles en `Config.discord` para los futuros
módulos de medida de señal y detección. **Todavía no se mide señal de Discord ni
se activa ducking por Discord**. Su presencia solo sirve para excluirlo de los
objetivos. El sondeo actual de streams sigue siendo de 0,5 segundos.

| Campo dentro de `discord` | Predeterminado | Unidad, semántica y validación |
| --- | --- | --- |
| `activation_threshold_dbfs` | `-40.0` | Nivel RMS en dBFS; activar con nivel >= umbral durante `attack_seconds`. Finito y <= 0. |
| `deactivation_threshold_dbfs` | `-45.0` | Nivel RMS en dBFS; desactivar con nivel <= umbral durante `release_seconds`. Finito y <= umbral de activación. |
| `attack_seconds` | `0.15` | Segundos continuos por encima del umbral de activación; finito y >= 0. |
| `release_seconds` | `0.8` | Segundos continuos por debajo del umbral de desactivación; finito y >= 0. |
| `sample_interval_seconds` | `0.05` | Periodo de medida RMS en segundos; finito y > 0. |

El nivel será `20 * log10(RMS)` con amplitud normalizada a escala completa (1);
el silencio representa nivel -infinito, pero los umbrales configurados deben ser
finitos. Entre los umbrales se conserva el estado y se reinicia el temporizador
de transición pendiente. Los tiempos se medirán con reloj monótono; cero permite
la transición en la primera muestra que cumpla el umbral. Si ambos umbrales son
iguales, se evalúa solo la transición desde el estado actual, una por muestra.
Los booleanos, cadenas y `null` no se aceptan como números en ningún parámetro.
