import SwiftUI

/// One place to say anything: a new request, a question, a message for a workshop, an arrival.
/// The words appear as you say them, and the facts lift out of the sentence as they are heard.
struct SpeakView: View {
    @Environment(AppModel.self) private var model
    @State private var typed = ""
    @State private var typing = false
    @State private var thinking = false
    @State private var card: SpeakCard?
    @State private var failure: String?
    @State private var finishing: Task<Void, Never>?
    @FocusState private var keyboard: Bool

    private let examples = ["What needs me today?", "Where is ORD-041?", "Tell QuickStitch we need it by Friday", "300 hoodies for TrendCart, back by 20 April, fastest please"]
    private let customers = ["Cotton Club", "Harbor Knits", "Loom & Leaf", "TrendCart", "UrbanThread", "Bright Basics", "Maple & Co", "Northwind Apparel"]

    private var speech: SpeechEngine { model.speech }
    private var words: String { typing ? typed : speech.text }

    var body: some View {
        NavigationStack(path: model.path(.speak)) {
            ZStack {
                Backdrop()
                if let card {
                    ScrollView {
                        CardView(card: card, spoken: words) { reset() } replaced: { self.card = $0 }
                            .padding(.horizontal, 16)
                            .padding(.bottom, 24)
                    }
                    .transition(.move(edge: .bottom).combined(with: .opacity))
                } else {
                    capture
                }
            }
            .navigationTitle(card == nil ? "" : "Threadline")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                if card != nil {
                    ToolbarItem(placement: .topBarTrailing) { Button("New", systemImage: "plus") { reset() } }
                }
            }
            .destinations()
        }
        .onChange(of: model.freshSpeak) {
            clean()
            if model.tab == .speak { Task { await begin() } }
        }
        .task(id: model.tab) {
            guard model.tab == .speak else {
                await speech.stop()
                return
            }
            if let seed = model.seedText {
                model.seedText = nil
                typing = true
                typed = seed
                await submit()
            } else if card == nil, !typing, !speech.listening, !thinking {
                try? await Task.sleep(for: .milliseconds(300))      // The tab finishes arriving before the audio starts up.
                if !Task.isCancelled, model.tab == .speak { await begin() }
            }
        }
    }

    private var capture: some View {
        VStack(spacing: 0) {
            Spacer(minLength: 12)
            if words.isEmpty {
                prompt
            } else {
                transcript
            }
            Spacer(minLength: 12)
            if !typing, let name = languageName {
                Text("Hearing \(name)").font(.footnote).foregroundStyle(Ink.tertiary).padding(.bottom, 8)
            }
            FactChips(text: words, workshops: model.workshops.map(\.name), customers: customers)
            if speech.sample, !typing {
                Text("Sample speech. The simulator has no microphone.").font(.footnote).foregroundStyle(Ink.tertiary).padding(.bottom, 8)
            }
            if let problem = failure ?? speech.problem {
                Text(problem).font(.footnote).foregroundStyle(Ink.coral).multilineTextAlignment(.center).padding(.horizontal, 24).padding(.bottom, 8)
            }
            controls
        }
    }

    private var prompt: some View {
        VStack(alignment: .leading, spacing: 18) {
            Text(speech.voiced ? "Hearing you." : speech.listening ? "Listening." : "Say anything.").font(.hero(38)).foregroundStyle(Ink.primary)
            Text(speech.preparing ? "Getting speech ready on this iPhone." : "A new request, a question, or a message for a workshop, in English, Hindi or Mandarin.").font(.body).foregroundStyle(Ink.secondary)
            VStack(alignment: .leading, spacing: 10) {
                ForEach(examples, id: \.self) { example in
                    Button {
                        Task {
                            await speech.stop()
                            typing = true
                            typed = example
                            await submit()
                        }
                    } label: {
                        Text(example).font(.subheadline).foregroundStyle(Ink.secondary).multilineTextAlignment(.leading)
                            .padding(.horizontal, 13).padding(.vertical, 9)
                            .background(Ink.card, in: .rect(cornerRadius: 14, style: .continuous))
                    }
                }
            }
            .padding(.top, 8)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(.horizontal, 22)
    }

    private var transcript: some View {
        ScrollView {
            Text("\(Text(typing ? typed : speech.firm + (speech.firm.isEmpty ? "" : " ")).foregroundStyle(Ink.primary))\(Text(typing ? "" : speech.tail).foregroundStyle(Ink.tertiary))")
                .font(.hero(30))
                .lineSpacing(5)
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, 22)
        }
        .defaultScrollAnchor(.bottom)
        .accessibilityLabel("Heard: \(words)")
    }

    private var controls: some View {
        VStack(spacing: 14) {
            if thinking {
                VStack(spacing: 10) {
                    Stitches(running: true, gradient: true, width: 3).padding(.horizontal, 40)
                    Text("Reading it and checking the workshops").font(.footnote).foregroundStyle(Ink.secondary)
                    Button("Discard", action: discard).font(.footnote.weight(.semibold)).foregroundStyle(Ink.secondary)
                }
                .frame(height: 96)
            } else if typing {
                HStack(spacing: 10) {
                    TextField("Type a request", text: $typed, axis: .vertical)
                        .focused($keyboard)
                        .lineLimit(1 ... 4)
                        .padding(.horizontal, 14).padding(.vertical, 11)
                        .background(Ink.card, in: .rect(cornerRadius: 18, style: .continuous))
                    Button { Task { await submit() } } label: {
                        Image(systemName: "arrow.up").font(.headline.weight(.bold)).foregroundStyle(.white).frame(width: 44, height: 44).background(Ink.cobalt, in: .circle)
                    }
                    .disabled(typed.trimmingCharacters(in: .whitespaces).isEmpty)
                    .accessibilityLabel("Send")
                    Button {
                        typing = false
                        keyboard = false
                        Task { await begin() }
                    } label: {
                        Image(systemName: "mic").font(.headline).foregroundStyle(Ink.secondary).frame(width: 44, height: 44)
                    }
                    .accessibilityLabel("Speak instead")
                }
                .padding(.horizontal, 16)
            } else {
                VStack(spacing: 8) {
                    VoiceThread(speech: speech).frame(height: 40).padding(.horizontal, 24)
                    HStack {
                        Button {
                            Task {
                                await speech.stop()
                                await speech.settle()
                                typed = speech.text
                                typing = true
                                keyboard = true
                            }
                        } label: {
                            Image(systemName: "keyboard").font(.title3).foregroundStyle(Ink.secondary).frame(width: 48, height: 48)
                        }
                        .accessibilityLabel("Type instead")
                        Spacer()
                        Button {
                            if speech.listening {
                                finish()
                            } else {
                                Task { await begin() }
                            }
                        } label: {
                            Image(systemName: speech.listening ? "stop.fill" : "mic.fill")
                                .font(.title2).foregroundStyle(.white)
                                .frame(width: 66, height: 66)
                                .background(Ink.thread, in: .circle)
                                .shadow(color: Ink.cobalt.opacity(0.28), radius: 12, y: 5)
                        }
                        .disabled(speech.preparing)
                        .accessibilityLabel(speech.listening ? "Finish" : "Start listening")
                        Spacer()
                        Button(action: discard) {
                            Image(systemName: "xmark").font(.title3).foregroundStyle(Ink.secondary).frame(width: 48, height: 48)
                        }
                        .opacity(speech.listening ? 1 : 0)
                        .disabled(!speech.listening)
                        .accessibilityLabel("Discard")
                    }
                    .padding(.horizontal, 24)
                }
            }
        }
        .padding(.bottom, 14)
    }

    private func begin() async {
        failure = nil
        let started = Date()
        let vocabulary = model.workshops.map(\.name) + customers + ["ORD", "beanies", "cardigans", "hoodies"]
        await speech.start(vocabulary: vocabulary)
        Probe.shared.mark("speech_ready", since: started)
        if speech.problem != nil, !speech.listening {
            typing = true
        }
    }

    private var languageName: String? {
        switch speech.spoken {
        case "hi": "Hindi"
        case "zh": "Mandarin"
        default: nil
        }
    }

    private func finish() {
        thinking = true         // Straight away, so the press is answered before the audio has closed.
        finishing = Task {
            await speech.stop()
            await speech.settle()
            guard !Task.isCancelled else { return }
            if words.isEmpty {
                thinking = false
                return
            }
            await submit()
        }
    }

    /// Throws away what was said and starts listening again. Nothing has been acted on: a card still needs approving.
    private func discard() {
        finishing?.cancel()
        finishing = nil
        thinking = false
        failure = nil
        Haptics.tick()
        Task {
            await speech.discard()
            clean()
            await begin()
        }
    }

    private func submit() async {
        let text = words.trimmingCharacters(in: .whitespacesAndNewlines)
        guard !text.isEmpty else { return }
        keyboard = false
        failure = nil
        thinking = true
        defer { thinking = false }
        let started = Date()
        do {
            let result: SpeakCard = try await API.shared.post("/api/speak", ["text": text])
            Probe.shared.mark("speak_reply", since: started)
            guard !Task.isCancelled else { return }
            withAnimation(.spring(response: 0.5, dampingFraction: 0.86)) { card = result }
            Haptics.tick()
        } catch {
            if !Task.isCancelled { failure = error.localizedDescription }
        }
    }

    private func clean() {
        withAnimation(.smooth) {
            card = nil
            typed = ""
            typing = false
            speech.clear()
        }
    }

    private func reset() {
        clean()
        Task { await begin() }
    }
}

/// What the phone can see so far. It only recalculates when the words change.
private struct FactChips: View {
    var text: String
    var workshops: [String]
    var customers: [String]

    var body: some View {
        let facts = LiveFacts.read(text, workshops: workshops, customers: customers)
        Group {
            if !facts.isEmpty {
                FlowLayout {
                    ForEach(facts) { fact in
                        VStack(alignment: .leading, spacing: 1) {
                            Text(fact.label).font(.caption2).foregroundStyle(Ink.tertiary)
                            Text(fact.value).font(.subheadline.weight(.semibold)).foregroundStyle(Ink.primary)
                        }
                        .padding(.horizontal, 12).padding(.vertical, 8)
                        .background(Ink.card, in: .rect(cornerRadius: 14, style: .continuous))
                        .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).strokeBorder(Ink.line, lineWidth: 0.5))
                        .transition(.scale(scale: 0.7).combined(with: .opacity))
                    }
                }
                .padding(.horizontal, 22)
                .padding(.bottom, 14)
            }
        }
        .animation(.spring(response: 0.4, dampingFraction: 0.85), value: facts)
    }
}

/// The voice as a single thread that lifts with your volume. The level changes many times a second, so only this reads it.
private struct VoiceThread: View {
    var speech: SpeechEngine

    var body: some View {
        let active = speech.listening
        TimelineView(.animation(minimumInterval: 1 / 30, paused: !active)) { context in
            let lift = CGFloat(active ? 4 + speech.level * 26 : 0)
            Canvas { canvas, size in
                let time = context.date.timeIntervalSinceReferenceDate
                var path = Path()
                for x in stride(from: 0, through: size.width, by: 5) {
                    let fade = sin(.pi * x / size.width)
                    let y = size.height / 2 + sin(x / 26 + time * 7) * lift * fade + sin(x / 11 - time * 4) * lift * 0.35 * fade
                    if x == 0 { path.move(to: CGPoint(x: x, y: y)) } else { path.addLine(to: CGPoint(x: x, y: y)) }
                }
                canvas.stroke(path, with: .linearGradient(Gradient(colors: [Color(hex: 0x3ACED8), Color(hex: 0x20BFA9), Color(hex: 0x5677F3)]), startPoint: .zero, endPoint: CGPoint(x: size.width, y: 0)),
                              style: StrokeStyle(lineWidth: 2.5, lineCap: .round, lineJoin: .round))
            }
        }
        .opacity(active ? 1 : 0.25)
        .accessibilityHidden(true)
    }
}
