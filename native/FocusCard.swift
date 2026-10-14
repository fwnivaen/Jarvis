import AppKit

let pollSeconds = 1.0
let requestTimeout = 2.0
let cardWidth = 240.0
let cardHeight = 96.0
let screenInset = 20.0
let cornerRadius = 16.0
let titleSize = 14.0
let countdownSize = 27.0
let titleHeight = titleSize * 2
let countdownHeight = countdownSize * 1.5
let countdownBottomInset = screenInset / 2
let focusedColor = NSColor.darkGray
let driftColor = NSColor.systemBrown
let secondsPerMinute = 60
let serverURL = URL(string: "http://127.0.0.1:4700/focus")!
let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let panel = NSPanel(contentRect: NSRect(x: 0, y: 0, width: cardWidth, height: cardHeight),
                    styleMask: [.borderless, .nonactivatingPanel], backing: .buffered, defer: false)
panel.level = .floating
panel.collectionBehavior = [.canJoinAllSpaces, .fullScreenAuxiliary]
panel.isOpaque = false
panel.backgroundColor = .clear
panel.hasShadow = true
panel.ignoresMouseEvents = true
let content = NSView(frame: panel.contentView!.bounds)
content.wantsLayer = true
content.layer?.cornerRadius = cornerRadius
panel.contentView = content
let title = NSTextField(labelWithString: "FOCUS")
title.frame = NSRect(x: screenInset, y: cardHeight / 2, width: cardWidth - screenInset * 2, height: titleHeight)
title.font = .systemFont(ofSize: titleSize, weight: .medium)
title.textColor = .white
let countdown = NSTextField(labelWithString: "")
countdown.frame = NSRect(x: screenInset, y: countdownBottomInset, width: cardWidth - screenInset * 2, height: countdownHeight)
countdown.font = .monospacedDigitSystemFont(ofSize: countdownSize, weight: .semibold)
countdown.textColor = .white
content.addSubview(title)
content.addSubview(countdown)
var inFlight = false
func poll() {
    guard !inFlight else { return }
    inFlight = true
    var request = URLRequest(url: serverURL)
    request.timeoutInterval = requestTimeout
    URLSession.shared.dataTask(with: request) { data, _, _ in
        let state = data.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] }
        DispatchQueue.main.async {
            inFlight = false
            guard let state = state else {
                title.stringValue = "FOCUS · DISCONNECTED"
                return
            }
            guard state["active"] as? Bool == true else { panel.orderOut(nil); return }
            if let screen = NSScreen.screens.first {
                panel.setFrameOrigin(NSPoint(x: screen.visibleFrame.maxX - cardWidth - screenInset,
                                             y: screen.visibleFrame.maxY - cardHeight - screenInset))
            }
            let known = state["known"] as? Bool == true
            let home = state["home"] as? Bool == true
            let drift = state["drifting"] as? Bool == true && !home
            title.stringValue = state["lock_deferred"] as? Bool == true ? "WAITING TO LOCK ON" : !known ? "ACTIVITY UNAVAILABLE" : state["paused"] as? Bool == true ? "FOCUS · PAUSED" : home ? "FOCUS · HOME BASE" : state["excused"] as? Bool == true ? "FOCUS · EXCUSED" : drift ? "RETURN TO YOUR TASK" : "FOCUS · ON TARGET"
            let remaining = state["remaining_s"] as? Int ?? 0
            countdown.stringValue = String(format: "%02d:%02d", remaining / secondsPerMinute, remaining % secondsPerMinute)
            content.layer?.backgroundColor = (drift ? driftColor : focusedColor).cgColor
            panel.orderFrontRegardless()
        }
    }.resume()
}
let timer = Timer.scheduledTimer(withTimeInterval: pollSeconds, repeats: true) { _ in poll() }
poll()
app.run()
