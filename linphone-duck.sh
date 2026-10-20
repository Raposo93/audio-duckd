#!/usr/bin/env bash

DUCK_VOLUME="20%"
TARGET_APP="brave"
TRIGGER_APP="linphone"

declare -A saved_volume
ducked=0

log() {
    printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*" >&2
}

get_streams() {
    pactl list sink-inputs | awk '
        /^Sink Input #/ {
            id=$3
            sub(/^#/, "", id)
        }
        /application.process.binary = / {
            app=$0
            sub(/.*application\.process\.binary = "/, "", app)
            sub(/".*/, "", app)
            sub(/ \(deleted\)$/, "", app)
            print id, app
        }
    '
}

get_volume() {
    local target="$1"

    pactl list sink-inputs | awk -v target="$target" '
        /^Sink Input #/ {
            id=$3
            sub(/^#/, "", id)
            found=(id == target)
            next
        }

        found && /^[[:space:]]*Volume:/ {
            if (match($0, /[0-9]+%/)) {
                print substr($0, RSTART, RLENGTH)
                exit
            }
        }
    '
}

sink_input_exists() {
    local target="$1"

    pactl list sink-inputs short |
        awk -v target="$target" '
            $1 == target { found=1 }
            END { exit !found }
        '
}

refresh() {
    local trigger_active=0
    local id app current current_id streams original_volume

    streams="$(get_streams)"

    while read -r id app; do
        [[ -z "$id" ]] && continue

        if [[ "$app" == "$TRIGGER_APP" ]]; then
            trigger_active=1
            break
        fi
    done <<< "$streams"

    if (( trigger_active )); then

        while read -r id app; do
            [[ -z "$id" ]] && continue
            [[ "$app" != "$TARGET_APP" ]] && continue

            if [[ -z "${saved_volume[$id]+x}" ]]; then
                original_volume="$(get_volume "$id")"

                if [[ -z "$original_volume" ]]; then
                    log "ERROR: no pude obtener el volumen de $TARGET_APP id=$id"
                    continue
                fi

                saved_volume[$id]="$original_volume"

                if pactl set-sink-input-volume "$id" "$DUCK_VOLUME"; then
                    log "Linphone activo: $TARGET_APP ${saved_volume[$id]} -> $DUCK_VOLUME"
                else
                    log "ERROR: no pude bajar $TARGET_APP id=$id"
                    unset 'saved_volume[$id]'
                    continue
                fi
            else
                current="$(get_volume "$id")"

                # Si algo cambia el volumen durante la llamada, mantener el duck.
                if [[ "$current" != "$DUCK_VOLUME" ]]; then
                    pactl set-sink-input-volume "$id" "$DUCK_VOLUME" ||
                        log "ERROR: no pude mantener $TARGET_APP en $DUCK_VOLUME"
                fi
            fi
        done <<< "$streams"

        if ((${#saved_volume[@]} > 0)); then
            ducked=1
        fi

    elif (( ducked )); then

        for id in "${!saved_volume[@]}"; do
            original_volume="${saved_volume[$id]}"

            if sink_input_exists "$id"; then
                if pactl set-sink-input-volume "$id" "$original_volume"; then
                    log "Linphone finalizado: $TARGET_APP restaurado a $original_volume"
                else
                    log "ERROR: no pude restaurar $TARGET_APP id=$id"
                fi

            else
                log "$TARGET_APP id=$id cambió; buscando stream actual"

                while read -r current_id app; do
                    [[ "$app" != "$TARGET_APP" ]] && continue

                    if pactl set-sink-input-volume "$current_id" "$original_volume"; then
                        log "Linphone finalizado: $TARGET_APP restaurado a $original_volume (nuevo id=$current_id)"
                    else
                        log "ERROR: no pude restaurar $TARGET_APP nuevo id=$current_id"
                    fi
                done <<< "$(get_streams)"
            fi

            unset 'saved_volume[$id]'
        done

        ducked=0
    fi
}

log "linphone-duck iniciado"

until pactl info &>/dev/null; do
    sleep 1
done

refresh

while IFS= read -r event; do
    [[ "$event" != *"sink-input"* ]] && continue

    sleep 0.5
    refresh
done < <(pactl subscribe)
