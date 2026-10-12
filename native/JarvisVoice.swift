import AppKit
import AVFoundation
import Speech

let pollSeconds = 0.25
let leaseSeconds = 10.0
let bufferFrames: AVAudioFrameCount = 1024
let app = NSApplication.shared
app.setActivationPolicy(.accessory)
let args = CommandLine.arguments
 guard let index = args.firstIndex(of: "--session"), args.count > index + 1 else { exit(2) }
let directory = URL(fileURLWithPath: args[index + 1])
let heartbeat = directory.appendingPathComponent("heartbeat")
let stateFile = directory.appendingPathComponent("state.json")
var sequence = 0
var engine: AVAudioEngine?
var task: SFSpeechRecognitionTask?
var request: SFSpeechAudioBufferRecognitionRequest?
func publish(_ status: String, _ text: String = "") {
    sequence += 1
    let value: [String: Any] = ["status": status, "text": text, "sequence": sequence]
    if let bytes = try? JSONSerialization.data(withJSONObject: value) {
        try? bytes.write(to: stateFile, options: .atomic)
    }
}
func finish() {
    engine?.stop()
    request?.endAudio()
    task?.cancel()
    app.terminate(nil)
}
func startListening() {
    guard let recognizer = SFSpeechRecognizer(locale: Locale(identifier: "en-US")),
          recognizer.supportsOnDeviceRecognition else {
        publish("error", "Mac speech recognition is not available offline. Enable English Dictation in System Settings, then try Mic again.")
        return
    }
    let audio = AVAudioEngine()
    let input = audio.inputNode
    let format = input.outputFormat(forBus: 0)
    guard format.sampleRate > 0, format.channelCount > 0 else {
        publish("error", "No microphone input is available. Choose an input in System Settings → Sound.")
        return
    }
    let session = SFSpeechAudioBufferRecognitionRequest()
    session.requiresOnDeviceRecognition = true
    session.shouldReportPartialResults = true
    input.installTap(onBus: 0, bufferSize: bufferFrames, format: format) { buffer, _ in session.append(buffer) }
    engine = audio
    request = session
    task = recognizer.recognitionTask(with: session) { result, error in
        DispatchQueue.main.async {
            if let result = result {
                publish(result.isFinal ? "final" : "listening", result.bestTranscription.formattedString)
            } else if let error = error as NSError? {
                publish("error", "Mac speech recognition stopped (\(error.domain) \(error.code)). Click Mic to retry.")
            }
        }
    }
    do { try audio.start(); publish("listening") }
    catch { publish("error", "The Mac microphone could not start. Check microphone permission in System Settings.") }
}
func authorizeSpeech() {
    publish("permission", "Allow Speech Recognition for Jarvis Voice in the macOS permission dialog.")
    SFSpeechRecognizer.requestAuthorization { status in
        DispatchQueue.main.async {
            if status == .authorized { startListening() }
            else { publish("error", "Allow Jarvis Voice under System Settings → Privacy & Security → Speech Recognition.") }
        }
    }
}
let watchdog = Timer.scheduledTimer(withTimeInterval: pollSeconds, repeats: true) { _ in
    let stopped = FileManager.default.fileExists(atPath: directory.appendingPathComponent("stop").path)
    let attributes = try? FileManager.default.attributesOfItem(atPath: heartbeat.path)
    let date = attributes?[.modificationDate] as? Date ?? .distantPast
    if stopped || Date().timeIntervalSince(date) > leaseSeconds { finish() }
}
publish("permission", "Allow Microphone access for Jarvis Voice in the macOS permission dialog.")
AVCaptureDevice.requestAccess(for: .audio) { allowed in
    DispatchQueue.main.async {
        if allowed { authorizeSpeech() }
        else { publish("error", "Allow Jarvis Voice under System Settings → Privacy & Security → Microphone.") }
    }
}
app.run()
