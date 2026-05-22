#!/bin/bash
CLASS="ai-assist"

WIN_ADDR=$(hyprctl clients -j | jq -r --arg c "$CLASS" '.[] | select(.class == $c) | .address' | head -1)
WIN_PID=$(hyprctl clients -j | jq -r --arg c "$CLASS" '.[] | select(.class == $c) | .pid' | head -1)
SEL=$(wl-paste 2>/dev/null)

get_geom() {
  read -r MON_W MON_H MON_X MON_Y MON_T <<< "$(
    hyprctl monitors -j | jq -r '.[] | select(.focused == true) | "\(.width) \(.height) \(.x) \(.y) \(.transform)"'
  )"
  case "$MON_T" in 1|3) EFF_W=$MON_H; EFF_H=$MON_W ;; *) EFF_W=$MON_W; EFF_H=$MON_H ;; esac
  WIN_W=$(( EFF_W * 45 / 100 ))
  WIN_H=$(( EFF_H * 35 / 100 ))
  WIN_X=$(( MON_X + (EFF_W - WIN_W) / 2 ))
  WIN_Y=$(( MON_Y + EFF_H - WIN_H ))
}

if [ -n "$SEL" ]; then
  [ -n "$WIN_PID" ] && kill "$WIN_PID" 2>/dev/null
  while hyprctl clients -j | jq -e --arg c "$CLASS" \
    '[.[] | select(.class == $c)] | length > 0' > /dev/null 2>&1; do sleep 0.1; done
  get_geom
  hyprctl keyword windowrule "move $(( (EFF_W - WIN_W) / 2 )) $(( EFF_H - WIN_H )),^($CLASS)$" >/dev/null 2>&1
  python3 ~/scripts/ai-assist.py --width "$WIN_W" --height "$WIN_H" --x "$WIN_X" --y "$WIN_Y" --query "$SEL" &
elif [ -n "$WIN_ADDR" ]; then
  hyprctl dispatch closewindow "address:$WIN_ADDR"
else
  get_geom
  hyprctl keyword windowrule "move $(( (EFF_W - WIN_W) / 2 )) $(( EFF_H - WIN_H )),^($CLASS)$" >/dev/null 2>&1
  python3 ~/scripts/ai-assist.py --width "$WIN_W" --height "$WIN_H" --x "$WIN_X" --y "$WIN_Y" &
fi
