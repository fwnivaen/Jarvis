import AppKit

let pollSeconds = 1.0
let requestTimeout = 2.0
let cardWidth = 360.0
let cardHeight = 136.0
let screenInset = 20.0
let cornerRadius = 16.0
let titleSize = 14.0
let countdownSize = 27.0
let titleHeight = titleSize * 2
let countdownHeight = countdownSize * 1.5
let countdownBottomInset = 42.0
let controlHeight = 26.0
let controlBottom = 10.0
let controlGap = 8.0
let lockWidth = 140.0
let otherWidth = 80.0
let controlFontSize = 11.0
let lockedFlashSeconds = 1.0
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
panel.ignoresMouseEvents = false
let content = NSView(frame: panel.contentView!.bounds)
content.wantsLayer = true
content.layer?.cornerRadius = cornerRadius
panel.contentView = content
let title = NSTextField(labelWithString: "FOCUS")
title.frame = NSRect(x: screenInset, y: cardHeight - titleHeight - screenInset, width: cardWidth - screenInset * 2, height: titleHeight)
title.font = .systemFont(ofSize: titleSize, weight: .medium)
title.textColor = .white
let countdown = NSTextField(labelWithString: "")
countdown.frame = NSRect(x: screenInset, y: countdownBottomInset, width: cardWidth - screenInset * 2, height: countdownHeight)
countdown.font = .monospacedDigitSystemFont(ofSize: countdownSize, weight: .semibold)
countdown.textColor = .white
content.addSubview(title)
content.addSubview(countdown)
var paused = false
var commandInFlight = false
final class Controls: NSObject {
    @objc func lockTarget(_ sender: NSButton) { post("retarget", sender) }
    @objc func pause(_ sender: NSButton) { post(paused ? "resume" : "pause", sender) }
    @objc func abort(_ sender: NSButton) { post("abort", sender) }
    func post(_ action: String, _ sender: NSButton) {
        guard !commandInFlight else { return }
        commandInFlight = true
        var request = URLRequest(url: serverURL)
        request.httpMethod = "POST"
        request.timeoutInterval = requestTimeout
        request.setValue("application/json", forHTTPHeaderField: "Content-Type")
        request.setValue("http://127.0.0.1:4700", forHTTPHeaderField: "Origin")
        request.httpBody = try? JSONSerialization.data(withJSONObject: ["action": action, "from_card": true])
        URLSession.shared.dataTask(with: request) { data, response, _ in
            let result = data.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] }
            DispatchQueue.main.async {
                commandInFlight = false
                guard let http = response as? HTTPURLResponse, http.statusCode == 200 else {
                    title.stringValue = "REQUEST UNCONFIRMED"
                    return
                }
                if action == "retarget" {
                    let state = result?["state"] as? [String: Any]
                    sender.title = state?["lock_deferred"] as? Bool == true ? "ARMED" : "LOCKED"
                    sender.isEnabled = false
                    DispatchQueue.main.asyncAfter(deadline: .now() + lockedFlashSeconds) {
                        sender.title = "LOCK THIS TAB"
                        sender.isEnabled = true
                    }
                }
                poll()
            }
        }.resume()
    }
}
let controls = Controls()
func control(_ label: String, _ x: Double, _ width: Double, _ action: Selector) -> NSButton {
    let button = NSButton(title: label, target: controls, action: action)
    button.bezelStyle = .rounded
    button.font = .systemFont(ofSize: controlFontSize, weight: .semibold)
    button.frame = NSRect(x: x, y: controlBottom, width: width, height: controlHeight)
    content.addSubview(button)
    return button
}
let lockButton = control("LOCK THIS TAB", screenInset, lockWidth, #selector(Controls.lockTarget(_:)))
let pauseButton = control("PAUSE", screenInset + lockWidth + controlGap, otherWidth, #selector(Controls.pause(_:)))
let abortButton = control("ABORT", screenInset + lockWidth + otherWidth + controlGap * 2, otherWidth, #selector(Controls.abort(_:)))
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
            paused = state["paused"] as? Bool == true
            pauseButton.title = paused ? "RESUME" : "PAUSE"
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
