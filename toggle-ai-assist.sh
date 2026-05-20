#!/bin/bash
CLASS="ai-assist"

WIN_ADDR=$(hyprctl clients -j | jq -r --arg c "$CLASS" '.[] | select(.class == $c) | .address' | head -1)
WIN_WS=$(hyprctl clients -j | jq -r --arg c "$CLASS" '.[] | select(.class == $c) | .workspace.name' | head -1)
WIN_PID=$(hyprctl clients -j | jq -r --arg c "$CLASS" '.[] | select(.class == $c) | .pid' | head -1)
SEL=$(wl-paste 2>/dev/null)

if [ -n "$SEL" ]; then
  [ -n "$WIN_PID" ] && kill "$WIN_PID" 2>/dev/null
  while hyprctl clients -j | jq -e --arg c "$CLASS" \
    '[.[] | select(.class == $c)] | length > 0' > /dev/null 2>&1; do sleep 0.1; done

  read -r MON_W MON_H MON_X MON_Y MON_T <<< "$(
    hyprctl monitors -j | jq -r '.[] | select(.focused == true) | "\(.width) \(.height) \(.x) \(.y) \(.transform)"'
  )"

  case "$MON_T" in
    1|3) EFF_W=$MON_H; EFF_H=$MON_W ;;
    *)   EFF_W=$MON_W; EFF_H=$MON_H ;;
  esac

  WIN_W=$(( EFF_W * 35 / 100 ))
  WIN_H=$(( EFF_H * 22 / 100 ))
  WIN_X=$(( MON_X + (EFF_W - WIN_W) / 2 ))
  WIN_Y=$MON_Y

  foot -a "$CLASS" -w "${WIN_W}x${WIN_H}" python3 ~/scripts/ai-assist.py &
  for _ in $(seq 1 20); do
    WIN_ADDR=$(hyprctl clients -j | jq -r --arg c "$CLASS" '.[] | select(.class == $c) | .address' | head -1)
    [ -n "$WIN_ADDR" ] && break
    sleep 0.1
  done

  if [ -n "$WIN_ADDR" ]; then
    hyprctl dispatch movetoworkspace "+0,address:$WIN_ADDR"
    sleep 0.1
    hyprctl dispatch movewindowpixel "exact $WIN_X $WIN_Y, address:$WIN_ADDR"
  fi

elif [ -n "$WIN_ADDR" ]; then
  if [[ "$WIN_WS" == special* ]]; then
    hyprctl dispatch movetoworkspace "+0,address:$WIN_ADDR"
  else
    hyprctl dispatch movetoworkspace "special:ai-assist,address:$WIN_ADDR"
  fi
fi
