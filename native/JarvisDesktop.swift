import AppKit
import AVFoundation
import ApplicationServices
import Carbon

let serverBase = "http://127.0.0.1:4700"
let requestTimeout = 120.0
let voicePollSeconds = 0.18
let recordingLimitSeconds = 60.0
let panelWidth = 560.0
let panelHeight = 520.0
let windowTolerance = 8.0
let centeredFraction = 0.75
let shortcutSignature: OSType = 0x4A525653
let talkShortcut: UInt32 = 1
let dictationShortcut: UInt32 = 2
let spaceKey: UInt32 = 49
let dKey: UInt32 = 2

func attribute(_ element: AXUIElement, _ name: String) -> CFTypeRef? {
    var value: CFTypeRef?
    return AXUIElementCopyAttributeValue(element, name as CFString, &value) == .success ? value : nil
}
func windowAction(_ placement: String, _ pid: pid_t) -> Bool {
    guard AXIsProcessTrusted(), NSRunningApplication(processIdentifier: pid) != nil,
          let value = attribute(AXUIElementCreateApplication(pid), kAXFocusedWindowAttribute),
          CFGetTypeID(value) == AXUIElementGetTypeID() else { return false }
    let window = value as! AXUIElement
    var point = CGPoint.zero
    if let raw = attribute(window, kAXPositionAttribute), CFGetTypeID(raw) == AXValueGetTypeID() {
        AXValueGetValue(raw as! AXValue, .cgPoint, &point)
    }
    let top = NSScreen.screens.first?.frame.maxY ?? 0
    let screen = NSScreen.screens.first { screen in
        CGRect(x: screen.frame.minX, y: top-screen.frame.maxY, width: screen.frame.width, height: screen.frame.height).contains(point)
    } ?? NSScreen.main
    guard let screen = screen else { return false }
    let visible = screen.visibleFrame
    var frame = CGRect(x: visible.minX, y: top-visible.maxY, width: visible.width, height: visible.height)
    if placement == "left" { frame.size.width /= 2 }
    else if placement == "right" { frame.origin.x += frame.width/2; frame.size.width /= 2 }
    else if placement == "center" { frame = frame.insetBy(dx: frame.width*(1-centeredFraction)/2, dy: frame.height*(1-centeredFraction)/2) }
    else if placement != "maximize" { return false }
    var origin = frame.origin, size = frame.size
    guard let p = AXValueCreate(.cgPoint, &origin), let s = AXValueCreate(.cgSize, &size),
          AXUIElementSetAttributeValue(window, kAXSizeAttribute as CFString, s) == .success,
          AXUIElementSetAttributeValue(window, kAXPositionAttribute as CFString, p) == .success else { return false }
    var actualOrigin = CGPoint.zero, actualSize = CGSize.zero
    guard let ap = attribute(window, kAXPositionAttribute), let az = attribute(window, kAXSizeAttribute),
          CFGetTypeID(ap) == AXValueGetTypeID(), CFGetTypeID(az) == AXValueGetTypeID(),
          AXValueGetValue(ap as! AXValue, .cgPoint, &actualOrigin), AXValueGetValue(az as! AXValue, .cgSize, &actualSize) else { return false }
    return abs(actualOrigin.x-origin.x)<windowTolerance && abs(actualOrigin.y-origin.y)<windowTolerance && abs(actualSize.width-size.width)<windowTolerance && abs(actualSize.height-size.height)<windowTolerance
}

let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let args = CommandLine.arguments
if let index = args.firstIndex(of: "--action"), args.count > index+2 {
    let kind = args[index+1], value = args[index+2]
    var success = false
    if kind == "window" {
        var pid = NSWorkspace.shared.frontmostApplication?.processIdentifier ?? 0
        if let i = args.firstIndex(of: "--target"), args.count>i+1 { pid = pid_t(args[i+1]) ?? 0 }
        success = windowAction(value, pid)
    } else if kind == "music", ["play", "pause"].contains(value) {
        var error: NSDictionary?
        NSAppleScript(source: "tell application \"Music\" to \(value)")?.executeAndReturnError(&error)
        success = error == nil
    }
    print(success ? "confirmed" : "unconfirmed")
    exit(success ? 0 : 3)
}

final class JarvisDesktop: NSObject, NSApplicationDelegate, NSWindowDelegate {
    let session = URLSession(configuration: .ephemeral)
    let panel = NSPanel(contentRect: NSRect(x: 0, y: 0, width: panelWidth, height: panelHeight), styleMask: [.titled,.closable,.utilityWindow], backing: .buffered, defer: false)
    let input = NSTextField()
    let answer = NSTextView(frame: NSRect(x: 0, y: 0, width: panelWidth-40, height: 150))
    let status = NSTextField(labelWithString: "Ready · Hold ⌃⌥Space to talk, or ⌃⌥D to dictate")
    let mode = NSSegmentedControl(labels: ["Ask Jarvis", "Dictation"], trackingMode: .selectOne, target: nil, action: nil)
    let speaker = AVSpeechSynthesizer()
    var speechVoice: AVSpeechSynthesisVoice?
    var spokenReply = false
    let run = NSButton(title: "Ask Jarvis", target: nil, action: nil)
    let insert = NSButton(title: "Insert reviewed text", target: nil, action: nil)
    var item: NSStatusItem!
    var keys: [EventHotKeyRef?] = []
    var eventHandler: EventHandlerRef?
    var token: String?
    var timer: Timer?
    var limit: Timer?
    var operation = UUID()
    var held = false, starting = false, dictating = false, working = false
    var targetPID: pid_t = 0
    var targetElement: AXUIElement?
    var lastTranscript = ""

    func applicationDidFinishLaunching(_ notification: Notification) {
        panel.title = "Jarvis"; panel.isReleasedWhenClosed = false; panel.delegate = self; panel.level = .floating; panel.center()
        let stack = NSStackView(); stack.orientation = .vertical; stack.alignment = .leading; stack.spacing = 12
        stack.translatesAutoresizingMaskIntoConstraints = false; panel.contentView!.addSubview(stack)
        NSLayoutConstraint.activate([stack.leadingAnchor.constraint(equalTo: panel.contentView!.leadingAnchor, constant: 20),stack.trailingAnchor.constraint(equalTo: panel.contentView!.trailingAnchor, constant: -20),stack.topAnchor.constraint(equalTo: panel.contentView!.topAnchor, constant: 20),stack.bottomAnchor.constraint(equalTo: panel.contentView!.bottomAnchor, constant: -20)])
        let heading = NSTextField(labelWithString: "JARVIS"); heading.font = .monospacedSystemFont(ofSize: 18, weight: .semibold); stack.addArrangedSubview(heading)
        mode.selectedSegment = 0; mode.target = self; mode.action = #selector(changeMode); stack.addArrangedSubview(mode)
        speechVoice = AVSpeechSynthesisVoice.speechVoices().first { $0.name.contains("Daniel") }
        input.placeholderString = "Ask a question or type Open Safari"; input.target = self; input.action = #selector(submit); stack.addArrangedSubview(input); input.widthAnchor.constraint(equalTo: stack.widthAnchor).isActive = true
        let scroll = NSScrollView(); scroll.hasVerticalScroller = true; scroll.borderType = .bezelBorder; scroll.documentView = answer; answer.isEditable = true; answer.isVerticallyResizable = true; answer.autoresizingMask = [.width]; answer.font = .systemFont(ofSize: 15); answer.textContainer?.widthTracksTextView = true
        stack.addArrangedSubview(scroll); scroll.widthAnchor.constraint(equalTo: stack.widthAnchor).isActive = true; scroll.heightAnchor.constraint(greaterThanOrEqualToConstant: 150).isActive = true
        status.font = .systemFont(ofSize: 12); status.lineBreakMode = .byWordWrapping; status.maximumNumberOfLines = 3; stack.addArrangedSubview(status); status.widthAnchor.constraint(equalTo: stack.widthAnchor).isActive = true
        let controls = NSStackView(); controls.spacing = 8
        run.target = self; run.action = #selector(submit); controls.addArrangedSubview(run)
        let copy = NSButton(title: "Copy", target: self, action: #selector(copyText)); controls.addArrangedSubview(copy)
        insert.target = self; insert.action = #selector(insertText); insert.isEnabled = false; controls.addArrangedSubview(insert)
        let cancel = NSButton(title: "Cancel", target: self, action: #selector(cancel)); controls.addArrangedSubview(cancel); stack.addArrangedSubview(controls)
        item = NSStatusBar.system.statusItem(withLength: NSStatusItem.variableLength); item.button?.title = "J"
        let menu = NSMenu()
        for (title, selector) in [("Open Jarvis",#selector(show)),("Open dashboard",#selector(dashboard)),("Accessibility permission…",#selector(accessibility)),("Quit Jarvis Desktop",#selector(quit))] { let entry = NSMenuItem(title: title, action: selector, keyEquivalent: ""); entry.target = self; menu.addItem(entry) }; item.menu = menu
        let pointer = Unmanaged.passUnretained(self).toOpaque()
        var eventTypes = [EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyPressed)),EventTypeSpec(eventClass: OSType(kEventClassKeyboard), eventKind: UInt32(kEventHotKeyReleased))]
        InstallEventHandler(GetApplicationEventTarget(), { _, event, context in
            guard let event = event, let context = context else { return OSStatus(eventNotHandledErr) }
            var identifier = EventHotKeyID(); GetEventParameter(event, EventParamName(kEventParamDirectObject), EventParamType(typeEventHotKeyID), nil, MemoryLayout<EventHotKeyID>.size, nil, &identifier)
            let owner = Unmanaged<JarvisDesktop>.fromOpaque(context).takeUnretainedValue()
            if GetEventKind(event) == UInt32(kEventHotKeyPressed) { owner.begin(identifier.id == dictationShortcut) } else { owner.release() }
            return noErr
        }, eventTypes.count, &eventTypes, pointer, &eventHandler)
        var failures = 0
        for (id, key) in [(talkShortcut,spaceKey),(dictationShortcut,dKey)] {
            var ref: EventHotKeyRef?
            if RegisterEventHotKey(key, UInt32(controlKey|optionKey), EventHotKeyID(signature: shortcutSignature,id: id), GetApplicationEventTarget(), 0, &ref) != noErr { failures += 1 }
            keys.append(ref)
        }
        NSEvent.addLocalMonitorForEvents(matching: .keyDown) { [weak self] event in
            if event.keyCode == 53 { self?.cancel(); return nil }; return event
        }
        if failures > 0 { status.stringValue = "A global shortcut is already in use. You can still type here or use dashboard dictation." }
        captureTarget(); show()
    }
    func post(_ path: String, _ body: [String: Any], completion: @escaping ([String: Any]?,String?) -> Void) {
        var request = URLRequest(url: URL(string: serverBase+path)!); request.httpMethod = "POST"; request.timeoutInterval = requestTimeout
        request.setValue("application/json", forHTTPHeaderField: "Content-Type"); request.setValue(serverBase, forHTTPHeaderField: "Origin"); request.httpBody = try? JSONSerialization.data(withJSONObject: body)
        session.dataTask(with: request) { data,response,error in
            let value = data.flatMap { try? JSONSerialization.jsonObject(with: $0) as? [String: Any] }
            let code = (response as? HTTPURLResponse)?.statusCode ?? 0
            DispatchQueue.main.async { completion(value, error != nil ? "Cannot reach Jarvis. Start the local server first." : (code >= 400 ? value?["answer"] as? String ?? "The local request failed." : nil)) }
        }.resume()
    }
    func captureTarget() {
        targetPID = NSWorkspace.shared.frontmostApplication?.processIdentifier ?? 0
        targetElement = nil
        if AXIsProcessTrusted(), let element = attribute(AXUIElementCreateSystemWide(),kAXFocusedUIElementAttribute), CFGetTypeID(element) == AXUIElementGetTypeID() { targetElement = (element as! AXUIElement) }
    }
    func begin(_ dictation: Bool) {
        if held || working || starting { return }
        speaker.stopSpeaking(at: .immediate); spokenReply = false; mode.selectedSegment = dictation ? 1 : 0
        captureTarget(); operation = UUID(); let current = operation
        held = true; starting = true; dictating = dictation; lastTranscript = ""; insert.isEnabled = false; input.stringValue = ""; answer.string = ""; run.isEnabled = false
        panel.orderFrontRegardless(); status.stringValue = "Starting local microphone… Release to finish."
        post("/voice/start",[:]) { value,error in
            let newToken = value?["token"] as? String
            guard self.operation == current else { if let token = newToken { self.post("/voice/stop",["token":token]) { _,_ in } }; return }
            self.starting = false
            guard let token = newToken, error == nil else { self.status.stringValue = error ?? value?["text"] as? String ?? "Microphone unavailable."; self.held = false; self.run.isEnabled = true; return }
            self.token = token
            if !self.held { self.finishVoice(); return }
            self.status.stringValue = dictation ? "Dictating locally. Release to review." : "Listening locally. Release to ask Jarvis."
            self.poll(current)
            self.timer = Timer.scheduledTimer(withTimeInterval: voicePollSeconds, repeats: true) { _ in self.poll(current) }
            self.limit = Timer.scheduledTimer(withTimeInterval: recordingLimitSeconds, repeats: false) { _ in self.held = false; self.finishVoice(forceReview: true) }
        }
    }
    func poll(_ current: UUID) {
        guard let token = token else { return }
        post("/voice/poll",["token":token]) { value,error in
            guard self.operation == current, self.held else { return }
            if let error = error { self.cancel(); self.status.stringValue = error; return }
            if let text = value?["text"] as? String, !text.isEmpty { self.lastTranscript = text; self.input.stringValue = text }
            if value?["status"] as? String == "error" { let text = value?["text"] as? String ?? "Speech unavailable."; self.cancel(); self.status.stringValue = text }
            else if value?["status"] as? String == "permission" { self.status.stringValue = value?["text"] as? String ?? "Allow the requested microphone permission." }
        }
    }
    func release() { guard held else { return }; held = false; if !starting { finishVoice() } }
    func finishVoice(forceReview: Bool = false) {
        timer?.invalidate();limit?.invalidate();guard let token = token else { return };self.token = nil
        let current = operation; working = true; status.stringValue = "Waiting for the final transcript…"
        post("/voice/finish",["token":token]) { value,error in
            guard self.operation == current else { return };self.working = false;self.run.isEnabled = true
            let text = value?["text"] as? String ?? self.lastTranscript; self.input.stringValue = text
            self.show()
            if self.dictating { self.answer.string = text; self.insert.isEnabled = self.targetElement != nil; self.run.title = "Clean up text"; self.status.stringValue = "Review your dictation, then Copy or Insert. Nothing is sent automatically." }
            else if error == nil && value?["confirmed"] as? Bool == true && !text.isEmpty && !forceReview { self.spokenReply = true; self.submit() }
            else { self.status.stringValue = error ?? "Review the transcript and press Ask Jarvis. No command has run." }
        }
    }
    @objc func submit() {
        if working || held || starting { return }
        let text = (dictating ? answer.string : input.stringValue).trimmingCharacters(in: .whitespacesAndNewlines)
        if text.isEmpty { return };working = true;run.isEnabled = false;insert.isEnabled = false;status.stringValue = dictating ? "Cleaning up your text with Codex / ChatGPT…" : "Working…";let current = operation
        if dictating {
            post("/assistant/dictation",["text":text,"cleanup":true]) { value,error in
                guard self.operation == current else { return };self.working = false;self.run.isEnabled = true;self.insert.isEnabled = self.targetElement != nil
                if let cleaned = value?["text"] as? String { self.answer.string = cleaned };self.status.stringValue = error ?? "Review the cleaned text before copying or inserting."
            };return
        }
        var command: [String: Any] = ["question":text,"request_key":UUID().uuidString.replacingOccurrences(of:"-",with:"").lowercased()]
        if targetPID > 0 { command["target_pid"] = Int(targetPID) }
        post("/assistant/command",command) { value,error in
            guard self.operation == current else { return }
            if error != nil || value?["matched"] as? Bool == true { self.display(value,error);return }
            let path = text.range(of:"^(remember that|note to self|log this)\\b",options:.regularExpression) != nil ? "/remember" : "/chat"
            self.post(path,["question":text]) { value,error in guard self.operation == current else { return };self.display(value,error) }
        }
    }
    func display(_ value: [String: Any]?, _ error: String?) {
        working = false;run.isEnabled = true;answer.string = value?["answer"] as? String ?? error ?? "No answer received."
        status.stringValue = error ?? "Ready · Codex / ChatGPT. Background progress is in Work."
        if spokenReply && error == nil { let speech = AVSpeechUtterance(string: answer.string); speech.voice = speechVoice; speaker.speak(speech) }; spokenReply = false
    }
    @objc func changeMode() { cancel(); dictating = mode.selectedSegment == 1; run.title = dictating ? "Clean up text" : "Ask Jarvis"; insert.isEnabled = dictating && targetElement != nil; status.stringValue = dictating ? "Hold ⌃⌥D from a text field to dictate, then review." : "Ready. Type a question or hold ⌃⌥Space." }
    @objc func copyText() { NSPasteboard.general.clearContents();NSPasteboard.general.setString(answer.string,forType:.string);status.stringValue = "Copied. Paste it where you want." }
    @objc func insertText() {
        guard dictating, !working, let element = targetElement, AXIsProcessTrusted() else { status.stringValue = "Use Copy, or enable Accessibility and start dictation from the destination text field."; return }
        var settable = DarwinBoolean(false)
        guard AXUIElementIsAttributeSettable(element,kAXSelectedTextAttribute as CFString,&settable) == .success, settable.boolValue else { status.stringValue = "That text field does not support safe insertion. Use Copy and paste it yourself.";return }
        let result = AXUIElementSetAttributeValue(element,kAXSelectedTextAttribute as CFString,answer.string as CFString)
        status.stringValue = result == .success ? "Inserted into the original text field. Nothing was submitted." : "Insertion could not be confirmed. Check the destination before retrying."
        insert.isEnabled = false
    }
    @objc func cancel() {
        speaker.stopSpeaking(at: .immediate); spokenReply = false; operation = UUID();held = false;starting = false;working = false;timer?.invalidate();limit?.invalidate();run.isEnabled = true
        if let token = token { post("/voice/stop",["token":token]) { _,_ in } };token = nil;status.stringValue = "Microphone stopped. Review text; any task already started remains in Work."
    }
    @objc func show() { panel.makeKeyAndOrderFront(nil);app.activate(ignoringOtherApps:true);if !dictating { run.title = "Ask Jarvis" };panel.makeFirstResponder(input) }
    @objc func dashboard() { NSWorkspace.shared.open(URL(string:serverBase)!) }
    @objc func accessibility() { let options = [kAXTrustedCheckOptionPrompt.takeUnretainedValue() as String:true] as CFDictionary;_ = AXIsProcessTrustedWithOptions(options) }
    @objc func quit() { cancel();app.terminate(nil) }
    func windowShouldClose(_ sender: NSWindow) -> Bool { cancel();return true }
    func applicationWillTerminate(_ notification: Notification) { cancel();for key in keys { if let key = key { UnregisterEventHotKey(key) } } }
}
let delegate = JarvisDesktop()
app.delegate = delegate
app.run()
