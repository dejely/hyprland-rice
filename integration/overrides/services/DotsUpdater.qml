pragma Singleton
import QtQuick
import Quickshell
Singleton {
    function runSystemUpdate() {
        Quickshell.execDetached(["kitty", "--hold", "python3", Quickshell.shellPath("integration/host.py"), "update"])
    }
    function runUpdateDots() {
        Quickshell.execDetached(["notify-send", "Pinned shell", "Update the integration checkout and rebuild with scripts/install.py. Your rollback profile is retained."])
    }
}
