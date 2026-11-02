@preconcurrency import AVFoundation
import Foundation
import Observation
@preconcurrency import Speech

/// Live speech to text, in two layers. The iPhone's dictation shows your words straight away, in grey, in the language you
/// last spoke. Meanwhile the clip so far keeps going to the desk on your Mac, where Whisper works out the language from your
/// voice and reads the words knowing the names this business uses. A word turns dark once two of those readings agree on it.
/// If the language changed, the Mac's own newest reading takes over the grey words, and the phone follows from the next take.
/// The audio goes no further than your Mac and no model is paid for it. If the desk cannot answer, the phone's words stand.
/// Opening and closing audio is slow, so it all happens away from the main thread and the screen never waits for it.
@Observable @MainActor
final class SpeechEngine {
    var settled = ""
    var guess = ""
    var shown = ""                 // The desk's words on screen so far, arriving one at a time.
    var spoken: String?            // The language the desk heard: en, hi or zh.
    var level: Float = 0
    var listening = false
    var preparing = false
    var sample = false
    var problem: String?

    var deskGone = false           // The desk stopped answering, so the phone's own words show instead.
    private(set) var voiced = false     // Someone is speaking. Whisper invents words for silence, so nothing is sent before this.

    /// What is settled, and the newest words still in grey.
    var firm: String { deskGone ? settled : shown }
    var tail: String {
        if deskGone { return guess }
        let phoneRight = spoken == nil || phoneLanguage.hasPrefix(spoken ?? "")
        return SteadyWords.after(phoneRight ? own : steady.latest, SteadyWords.parts(shown).count)
    }
    var text: String { [firm, tail].filter { !$0.isEmpty }.joined(separator: " ") }
    private var own: String { [settled, guess].filter { !$0.isEmpty }.joined(separator: " ") }

    @ObservationIgnored private lazy var audio = AVAudioEngine()
    private var analyzer: SpeechAnalyzer?
    private var input: AsyncStream<AnalyzerInput>.Continuation?
    private var results: Task<Void, Never>?
    private var legacyRequest: SFSpeechAudioBufferRecognitionRequest?
    private var legacyTask: SFSpeechRecognitionTask?
    private var tapped = false
    private var wanted = false
    private var session = 0        // A late result from a finished session must not land in the next one.
    private var closing: Task<Void, Never>?
    private var steady = SteadyWords()
    private var settledLanguage = false
    private var voiceAt = 0.0
    private var sharpening: Task<Void, Never>?
    private var revealing: Task<Void, Never>?
    private let clip = Clip()
    private var phoneLanguage = "en-US"

    func clear() {
        settled = ""
        guess = ""
        shown = ""
        spoken = nil
        deskGone = false
        steady = SteadyWords()
        settledLanguage = false
        voiced = false
        voiceAt = 0
        revealing?.cancel()
        revealing = nil
        problem = nil
        clip.empty()
    }

    func start(vocabulary: [String]) async {
        guard !listening, !preparing else { return }
        preparing = true
        wanted = true
        defer { preparing = false }
        clear()
        await closing?.value
        await choosePhoneLanguage()
        #if targetEnvironment(simulator)
        playSample()
        #else
        guard await permissions() else { return }
        do {
            try await Self.openAudio()
            if !(await startAnalyzerIfPossible(vocabulary: vocabulary)) {
                try await startLegacy(vocabulary: vocabulary)
            }
            listening = true
            sharpen()
        } catch {
            await Self.halt(audio, tapped: tapped)
            tapped = false
            problem = "Speech is not available here. Type the request instead."
        }
        #endif
        if listening, !wanted { await stop() }
    }

    func stop() async {
        wanted = false
        guard listening else { return }
        listening = false
        level = 0
        sharpening?.cancel()
        sharpening = nil
        if sample {
            results?.cancel()
            results = nil
        } else {
            let hadTap = tapped
            tapped = false
            await Self.halt(audio, tapped: hadTap)
            input?.finish()
            input = nil
            if let analyzer { await finish(analyzer) }
            analyzer = nil
            legacyRequest?.endAudio()
            legacyRequest = nil
            legacyTask = nil
            closing = Task.detached { try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation) }
        }
        session += 1
        if !guess.isEmpty {
            settled = [settled, guess].filter { !$0.isEmpty }.joined(separator: " ")
            guess = ""
        }
    }

    /// Throws the whole take away. Nothing said so far goes anywhere.
    func discard() async {
        session += 1
        sharpening?.cancel()
        clear()
        await stop()
        clear()
    }

    /// The language first, as soon as there is a moment of speech, then the words, one reading straight after another. The
    /// language is checked until 3 s of speech, by when it was right on every test clip. A desk that cannot answer ends this,
    /// and the phone's words stand.
    private func sharpen() {
        sharpening = Task { [weak self] in
            while !Task.isCancelled {
                try? await Task.sleep(for: .milliseconds(100))
                guard let self, self.listening, !Task.isCancelled else { return }
                guard self.voiced, self.clip.seconds - self.voiceAt > 0.8 else { continue }
                let enough = self.clip.seconds >= 3
                let wav = self.clip.wav
                let started = Date()
                do {
                    if !self.settledLanguage {
                        let found = try await API.shared.language(wav)
                        guard !Task.isCancelled else { return }
                        Probe.shared.mark("desk_language", since: started)
                        self.adopt(found)
                        self.settledLanguage = enough
                    }
                    let reading = try await API.shared.hear(wav, language: self.spoken ?? "en")
                    guard !Task.isCancelled else { return }
                    Probe.shared.mark("desk_heard", since: started)
                    self.steady.read(reading.text)
                    self.reveal()
                } catch {
                    if !Task.isCancelled { self.deskGone = true }
                    return
                }
            }
        }
    }

    /// A change of language means the earlier readings were in the wrong one, so they are dropped.
    private func adopt(_ language: String) {
        if let spoken, spoken != language {
            steady = SteadyWords()
            shown = ""
        }
        spoken = language
    }

    /// Readings arrive a few words at a time. Handing them over one by one is what makes it read like speech and not like jumps.
    private func reveal() {
        guard revealing == nil else { return }
        revealing = Task { [weak self] in
            while let self, !Task.isCancelled, self.shown != self.steady.firm {
                let target = self.steady.firm
                if !target.hasPrefix(self.shown) { self.shown = String(target.commonPrefix(with: self.shown)) }
                if let next = SteadyWords.parts(target).first(where: { $0.end > target.index(target.startIndex, offsetBy: self.shown.count) }) {
                    self.shown = String(target[..<next.end])
                }
                try? await Task.sleep(for: .milliseconds(60))
            }
            self?.revealing = nil
        }
    }

    /// The whole clip, read once more now it is finished, with a last check of the language. Nothing is lost if the desk cannot answer.
    func settle() async {
        var last = steady.latest
        if !sample, voiced, clip.seconds > 0.3, let reading = try? await API.shared.hear(clip.wav) {
            if SteadyWords.parts(reading.text).count * 2 >= SteadyWords.parts(last).count { last = reading.text }
            spoken = reading.language
            UserDefaults.standard.set(reading.language, forKey: "speechLanguage")
        }
        guard !Task.isCancelled else { return }
        revealing?.cancel()
        if last.isEmpty {
            deskGone = true
            return
        }
        shown = last
        deskGone = false
        steady = SteadyWords()
        settled = ""
        guess = ""
    }

    /// The phone listens in the language you last spoke, so the grey words are right from the first one. A language it has not
    /// downloaded yet fetches quietly for next time, and this take stays in English.
    private func choosePhoneLanguage() async {
        phoneLanguage = "en-US"
        let wanted = ["hi": "hi-IN", "zh": "zh-CN"][UserDefaults.standard.string(forKey: "speechLanguage") ?? ""]
        guard let wanted, let locale = await DictationTranscriber.supportedLocale(equivalentTo: Locale(identifier: wanted)) else { return }
        let transcriber = DictationTranscriber(locale: locale, preset: .progressiveShortDictation)
        guard let install = try? await AssetInventory.assetInstallationRequest(supporting: [transcriber]) else {
            phoneLanguage = wanted
            return
        }
        Task.detached { try? await install.downloadAndInstall() }
    }

    /// The last words get a moment to settle. What is on screen is good enough, so this never holds things up for long.
    private func finish(_ analyzer: SpeechAnalyzer) async {
        let (signal, fire) = AsyncStream<Void>.makeStream()
        let waiting = results
        Task {
            try? await analyzer.finalizeAndFinishThroughEndOfInput()
            await waiting?.value
            fire.yield()
        }
        Task {
            try? await Task.sleep(for: .milliseconds(600))
            fire.yield()
        }
        _ = await signal.first { _ in true }
    }

    nonisolated private static func openAudio() async throws {
        let session = AVAudioSession.sharedInstance()
        try session.setCategory(.playAndRecord, mode: .measurement, options: [.duckOthers, .defaultToSpeaker])
        try session.setActive(true, options: .notifyOthersOnDeactivation)
    }

    nonisolated private static func inputFormat(_ engine: AVAudioEngine) async -> AVAudioFormat {
        engine.inputNode.outputFormat(forBus: 0)
    }

    nonisolated private static func run(_ engine: AVAudioEngine) async throws {
        engine.prepare()
        try engine.start()
    }

    nonisolated private static func halt(_ engine: AVAudioEngine, tapped: Bool) async {
        if tapped { engine.inputNode.removeTap(onBus: 0) }
        engine.stop()
    }

    /// The simulator has no dependable microphone, and a stalled audio connection aborts the app, so it plays a labelled sample.
    private func playSample() {
        sample = true
        deskGone = true
        listening = true
        let words = "Order 45, 150 vests for Cotton Club, back by 9 April, fastest please.".split(separator: " ").map(String.init)
        results = Task { [weak self] in
            for count in 1 ... words.count {
                try? await Task.sleep(for: .milliseconds(230))
                guard let self, self.listening, !Task.isCancelled else { return }
                let cut = max(0, count - 3)
                self.settled = words[..<cut].joined(separator: " ")
                self.guess = words[cut ..< count].joined(separator: " ")
                self.level = .random(in: 0.25 ... 0.8)
            }
            self?.level = 0
        }
    }

    private func permissions() async -> Bool {
        let speech = await withCheckedContinuation { continuation in
            SFSpeechRecognizer.requestAuthorization { continuation.resume(returning: $0 == .authorized) }
        }
        let microphone = await AVAudioApplication.requestRecordPermission()
        if !speech || !microphone {
            problem = "Allow the microphone and speech recognition in Settings, or type the request."
            return false
        }
        return true
    }

    /// The newer analyser when this iPhone has it. Any failure leaves things clean for the older recogniser.
    private func startAnalyzerIfPossible(vocabulary: [String]) async -> Bool {
        do {
            return try await startAnalyzer(vocabulary: vocabulary)
        } catch {
            await Self.halt(audio, tapped: tapped)
            tapped = false
            input?.finish()
            input = nil
            analyzer = nil
            return false
        }
    }

    private func startAnalyzer(vocabulary: [String]) async throws -> Bool {
        guard let locale = await DictationTranscriber.supportedLocale(equivalentTo: Locale(identifier: phoneLanguage)) else { return false }
        let transcriber = DictationTranscriber(locale: locale, preset: .progressiveShortDictation)
        if let install = try await AssetInventory.assetInstallationRequest(supporting: [transcriber]) {
            try await install.downloadAndInstall()
        }
        let analyzer = SpeechAnalyzer(modules: [transcriber], options: .init(priority: .userInitiated, modelRetention: .lingering))
        let inputFormat = await Self.inputFormat(audio)
        guard inputFormat.sampleRate > 0,
              let target = await SpeechAnalyzer.bestAvailableAudioFormat(compatibleWith: [transcriber], considering: inputFormat) else { return false }
        try await analyzer.prepareToAnalyze(in: target)      // Loaded before you speak, so the first words are not late.
        let (stream, continuation) = AsyncStream<AnalyzerInput>.makeStream()
        let mine = session
        results = Task { [weak self] in
            do {
                for try await result in transcriber.results {
                    let words = String(result.text.characters).trimmingCharacters(in: .whitespacesAndNewlines)
                    await MainActor.run {
                        guard let self, self.session == mine else { return }
                        if result.isFinal {
                            self.settled = [self.settled, words].filter { !$0.isEmpty }.joined(separator: " ")
                            self.guess = ""
                        } else {
                            self.guess = words
                        }
                    }
                }
            } catch {}
        }
        try await analyzer.start(inputSequence: stream)
        let context = AnalysisContext()
        context.contextualStrings = [.general: vocabulary]
        try? await analyzer.setContext(context)
        let converter = inputFormat == target ? nil : AVAudioConverter(from: inputFormat, to: target)
        let clip = clip
        let clipConverter = AVAudioConverter(from: inputFormat, to: Clip.format)
        audio.inputNode.installTap(onBus: 0, bufferSize: 1024, format: inputFormat) { @Sendable [weak self] buffer, _ in
            let meter = Self.power(buffer)
            let out = Self.convert(buffer, converter, target)
            continuation.yield(AnalyzerInput(buffer: out ?? buffer))
            clip.add(Self.convert(buffer, clipConverter, Clip.format))
            Task { @MainActor in self?.hearing(meter) }
        }
        tapped = true
        try await Self.run(audio)
        self.analyzer = analyzer
        self.input = continuation
        return true
    }

    private func startLegacy(vocabulary: [String]) async throws {
        guard let recogniser = SFSpeechRecognizer(locale: Locale(identifier: phoneLanguage)), recogniser.isAvailable else {
            throw ServerError(message: "Speech is not available.")
        }
        let request = SFSpeechAudioBufferRecognitionRequest()
        request.shouldReportPartialResults = true
        request.contextualStrings = vocabulary
        request.addsPunctuation = true
        legacyRequest = request
        let format = await Self.inputFormat(audio)
        guard format.sampleRate > 0 else { throw ServerError(message: "No microphone.") }
        let clip = clip
        let clipConverter = AVAudioConverter(from: format, to: Clip.format)
        audio.inputNode.installTap(onBus: 0, bufferSize: 1024, format: format) { @Sendable [weak self] buffer, _ in
            request.append(buffer)
            clip.add(Self.convert(buffer, clipConverter, Clip.format))
            let meter = Self.power(buffer)
            Task { @MainActor in self?.hearing(meter) }
        }
        tapped = true
        try await Self.run(audio)
        let mine = session
        legacyTask = recogniser.recognitionTask(with: request) { [weak self] result, _ in
            guard let result else { return }
            let words = result.bestTranscription.formattedString
            Task { @MainActor in
                guard let self, self.session == mine else { return }
                let parts = words.split(separator: " ")
                let cut = max(0, parts.count - 3)    // The last few words are still likely to change.
                self.settled = parts[..<cut].joined(separator: " ")
                self.guess = parts[cut...].joined(separator: " ")
            }
        }
    }

    private func hearing(_ meter: Float) {
        level = meter
        if meter > 0.2, !voiced {
            voiced = true
            voiceAt = clip.seconds
        }
    }

    nonisolated private static func power(_ buffer: AVAudioPCMBuffer) -> Float {
        guard let samples = buffer.floatChannelData?[0], buffer.frameLength > 0 else { return 0 }
        var total: Float = 0
        for index in 0 ..< Int(buffer.frameLength) { total += samples[index] * samples[index] }
        return min(1, sqrt(total / Float(buffer.frameLength)) * 9)
    }

    nonisolated private static func convert(_ buffer: AVAudioPCMBuffer, _ converter: AVAudioConverter?, _ format: AVAudioFormat) -> AVAudioPCMBuffer? {
        guard let converter else { return buffer }
        let ratio = format.sampleRate / buffer.format.sampleRate
        guard let out = AVAudioPCMBuffer(pcmFormat: format, frameCapacity: AVAudioFrameCount(Double(buffer.frameLength) * ratio) + 16) else { return nil }
        var supplied = false
        var failure: NSError?
        converter.convert(to: out, error: &failure) { _, status in
            if supplied {
                status.pointee = .noDataNow
                return nil
            }
            supplied = true
            status.pointee = .haveData
            return buffer
        }
        return failure == nil ? out : nil
    }
}

/// What you have said so far, in the form Whisper reads. It only exists for this request, and two minutes is more than any request needs.
final class Clip: @unchecked Sendable {
    static let format = AVAudioFormat(commonFormat: .pcmFormatInt16, sampleRate: 16_000, channels: 1, interleaved: true)!
    private static let limit = 16_000 * 2 * 120
    private let lock = NSLock()
    private var samples = Data()

    func empty() {
        lock.withLock { samples.removeAll() }
    }

    func add(_ buffer: AVAudioPCMBuffer?) {
        guard let buffer, let channel = buffer.int16ChannelData?[0] else { return }
        lock.withLock {
            if samples.count < Self.limit { samples.append(UnsafeBufferPointer(start: channel, count: Int(buffer.frameLength))) }
        }
    }

    var seconds: Double {
        lock.withLock { Double(samples.count) / (16_000 * 2) }
    }

    var wav: Data {
        lock.withLock {
            func bytes(_ number: UInt32) -> Data { withUnsafeBytes(of: number.littleEndian) { Data($0) } }
            func short(_ number: UInt16) -> Data { withUnsafeBytes(of: number.littleEndian) { Data($0) } }
            var file = Data("RIFF".utf8) + bytes(UInt32(36 + samples.count)) + Data("WAVEfmt ".utf8) + bytes(16)
            file += short(1) + short(1) + bytes(16_000) + bytes(32_000) + short(2) + short(16) + Data("data".utf8) + bytes(UInt32(samples.count))
            return file + samples
        }
    }
}

/// The voices that sound most like a person first. Better ones are a free download in the iPhone's own Settings.
enum Voices {
    static func english() -> [AVSpeechSynthesisVoice] {
        AVSpeechSynthesisVoice.speechVoices()
            .filter { $0.language.hasPrefix("en") && !$0.voiceTraits.contains(.isNoveltyVoice) && !$0.identifier.contains("eloquence") }
            .sorted { ($0.quality.rawValue, $1.name) > ($1.quality.rawValue, $0.name) }
    }

    static func chosen() -> AVSpeechSynthesisVoice? {
        let voices = english()
        return voices.first { $0.identifier == UserDefaults.standard.string(forKey: "briefVoice") } ?? voices.first
    }

    static func grade(_ voice: AVSpeechSynthesisVoice) -> String {
        switch voice.quality {
        case .premium: "Premium"
        case .enhanced: "Enhanced"
        default: "Standard"
        }
    }

    /// Sentence by sentence with a breath between them, which does more for a natural sound than anything else.
    static func lines(_ text: String, voice: AVSpeechSynthesisVoice?) -> [AVSpeechUtterance] {
        var sentences: [String] = []
        text.enumerateSubstrings(in: text.startIndex..., options: .bySentences) { sentence, _, _, _ in
            if let sentence { sentences.append(sentence.trimmingCharacters(in: .whitespaces)) }
        }
        return sentences.map { sentence in
            let line = AVSpeechUtterance(string: sentence)
            line.voice = voice
            line.rate = 0.49
            line.postUtteranceDelay = 0.28
            return line
        }
    }
}

/// Reads the day's brief aloud, for when your hands are full on the shop floor. It runs on the phone, with the same words Siri uses.
@Observable @MainActor
final class BriefVoice: NSObject, AVSpeechSynthesizerDelegate {
    var speaking = false
    private var left = 0
    @ObservationIgnored private lazy var voice: AVSpeechSynthesizer = {
        let voice = AVSpeechSynthesizer()
        voice.delegate = self
        return voice
    }()

    func toggle(_ text: String) {
        if speaking {
            left = 0
            voice.stopSpeaking(at: .immediate)
            finished()
            return
        }
        speaking = true
        #if targetEnvironment(simulator)
        Task {              // The simulator's voice library stalls the whole app, so it only shows the state.
            try? await Task.sleep(for: .seconds(4))
            speaking = false
        }
        #else
        let voice = voice
        Task.detached {     // Set up away from the main thread, as spoken audio so it plays even with the ring switch on silent.
            let session = AVAudioSession.sharedInstance()
            try? session.setCategory(.playback, mode: .spokenAudio, options: [.duckOthers])
            try? session.setActive(true)
            let lines = Voices.lines(text, voice: Voices.chosen())
            await MainActor.run { self.left = lines.count }
            lines.forEach(voice.speak)
        }
        #endif
    }

    /// A short line in the voice just picked.
    func sample() {
        if speaking { toggle("") }
        toggle("Morning. Two things need you. Quick Stitch can't take order 41. Then, order 40 is two days overdue.")
    }

    private func finished() {
        speaking = false
        #if !targetEnvironment(simulator)
        Task.detached { try? AVAudioSession.sharedInstance().setActive(false, options: .notifyOthersOnDeactivation) }
        #endif
    }

    nonisolated func speechSynthesizer(_ synthesizer: AVSpeechSynthesizer, didFinish utterance: AVSpeechUtterance) {
        Task { @MainActor in
            left -= 1
            if left == 0 { finished() }
        }
    }
}

/// What the phone can already see in the words, on the device, while you are still talking. Instant and free.
/// It is a preview: the server reads the finished request properly, and only that reading counts.
struct LiveFacts {
    struct Fact: Identifiable, Equatable {
        var id: String
        var label: String
        var value: String
    }

    /// Built once. These run on every word you say.
    private static let order = pattern(#"\b(?:ord|order)(?:\s+number)?[\s#-]*(\d{1,4})\b"#)
    private static let pieces = pattern(#"\b(\d[\d,]*)\s*(pieces?|pcs|hoodies|vests|scarves|beanies|cardigans|sweaters?|polo shirts?|shirts?|tops)\b"#)
    private static let date = pattern(#"\b(\d{1,2}(?:st|nd|rd|th)?\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{1,2}(?:st|nd|rd|th)?)\b"#)

    private static func pattern(_ text: String) -> NSRegularExpression {
        try! NSRegularExpression(pattern: text, options: .caseInsensitive)
    }

    /// The match and its groups, or nil.
    private static func first(_ regex: NSRegularExpression, in text: String) -> [String]? {
        guard let match = regex.firstMatch(in: text, range: NSRange(text.startIndex..., in: text)) else { return nil }
        return (0 ..< match.numberOfRanges).map { Range(match.range(at: $0), in: text).map { String(text[$0]) } ?? "" }
    }

    static func read(_ text: String, workshops: [String], customers: [String]) -> [Fact] {
        guard !text.isEmpty else { return [] }
        var out: [Fact] = []
        let lower = text.lowercased()
        let squeezed = lower.filter { $0.isLetter || $0.isNumber }
        if let match = first(order, in: text), let number = Int(match[1]) {
            out.append(.init(id: "order", label: "Order", value: String(format: "ORD-%03d", number)))
        }
        if let match = first(pieces, in: text) {
            out.append(.init(id: "pieces", label: "Quantity", value: "\(match[1]) \(match[2].lowercased())"))
        }
        if let name = customers.first(where: { squeezed.range(of: $0.lowercased().filter { $0.isLetter || $0.isNumber }) != nil }) {
            out.append(.init(id: "customer", label: "Customer", value: name))
        }
        if let match = first(date, in: text) {
            out.append(.init(id: "date", label: "Date", value: match[1]))
        }
        if let name = workshops.first(where: { squeezed.range(of: $0.lowercased().filter { $0.isLetter || $0.isNumber }) != nil }) {
            out.append(.init(id: "workshop", label: "Workshop", value: name))
        }
        if lower.contains("fastest") || lower.contains("urgent") || lower.contains("asap") || lower.contains("rush") {
            out.append(.init(id: "preference", label: "Priority", value: "Fastest"))
        } else if lower.contains("cheapest") || lower.contains("lowest cost") {
            out.append(.init(id: "preference", label: "Priority", value: "Cheapest"))
        } else if lower.contains("quality") || lower.contains("defect") {
            out.append(.init(id: "preference", label: "Priority", value: "Lowest defects"))
        }
        return out
    }
}
