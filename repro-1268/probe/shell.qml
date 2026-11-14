import QtQuick
import Quickshell
import Quickshell.Hyprland

ShellRoot {
  Connections {
    target: Hyprland
    function onRawEvent(event) {
      if (String(event.name) === "fullscreen") Hyprland.refreshToplevels()
    }
  }

  Timer {
    interval: 100
    running: true
    repeat: true
    onTriggered: {
      var list = Hyprland.toplevels.values, out = []
      for (var i = 0; i < list.length; i++) out.push(list[i].address)
      console.log("REPRO_TOPLEVELS [" + out.sort().join(",") + "]")
    }
  }
}
