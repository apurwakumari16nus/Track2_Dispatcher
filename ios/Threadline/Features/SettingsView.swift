import AppIntents
import SwiftUI

struct SettingsView: View {
    @Environment(AppModel.self) private var model
    @State private var address = Shared.serverURL
    @State private var token = Shared.token
    @State private var name = Shared.name
    @State private var health: Health?
    @State private var rulesOn: Int?
    @State private var note: String?
    @AppStorage("appearance") private var appearance = "system"

    var body: some View {
        Form {
            Section("You") {
                TextField("Your name", text: $name).onChange(of: name) { Shared.name = name }
                Picker("Appearance", selection: $appearance) {
                    Text("System").tag("system")
                    Text("Light").tag("light")
                    Text("Dark").tag("dark")
                }
            }
            Section {
                TextField("Desk address", text: $address).keyboardType(.URL).textInputAutocapitalization(.never).autocorrectionDisabled()
                SecureField("Access token", text: $token)
                Button("Connect") {
                    Shared.serverURL = address.trimmingCharacters(in: .whitespaces)
                    Shared.token = token
                    Task { await check() }
                }
            } header: {
                Text("Desk")
            } footer: {
                if let health {
                    Text("Connected. Requests read by \(health.model ?? "rehearsal fixtures"). Workshop replies read by \(health.reader == "model" ? "the model" : "rules"). Telegram \(health.telegram ? "on, \(health.connected.count) chat\(health.connected.count == 1 ? "" : "s")" : "off").")
                } else if let note {
                    Text(note)
                }
            }
            Section {
                Button("The project story") { model.showStory = true }
                NavigationLink(value: Route.automations) {
                    LabeledContent("Automations", value: rulesOn.map { "\($0) on" } ?? "")
                }
                NavigationLink("Voice for the brief", value: Route.voice)
                NavigationLink("What happened, in order", value: Route.trail)
                if model.today?.demo == true {
                    NavigationLink("Rehearse", value: Route.rehearse)
                }
            }
            Section("Hands free") {
                Label("\"Hey Siri, brief me in Threadline\"", systemImage: "sparkles")
                Label("\"Hey Siri, new request in Threadline\"", systemImage: "waveform")
                Label("\"Hey Siri, chase workshops in Threadline\"", systemImage: "bell")
                Label("\"Hey Siri, a batch arrived in Threadline\"", systemImage: "shippingbox")
                Label("Add Talk to Threadline to the Action button or Control Center", systemImage: "button.horizontal.top.press")
            }
            .font(.subheadline)
        }
        .scrollContentBackground(.hidden)
        .background(Backdrop())
        .navigationTitle("Settings")
        .task {
            await check()
            rulesOn = (try? await API.shared.get("/api/automations", as: [Automation].self))?.filter(\.on).count
        }
    }

    private func check() async {
        do {
            health = try await API.shared.get("/api/health")
            note = nil
            await model.refresh()
        } catch {
            health = nil
            note = error.localizedDescription
        }
    }
}

/// Rules the desk runs on its own, and recipes for the Shortcuts app. They ask questions and nothing else.
struct AutomationsView: View {
    @State private var rules: [Automation] = []
    @State private var note: String?

    private let recipes: [(when: String, then: String, symbol: String)] = [
        ("Every morning at 8.30", "Brief me", "sunrise"),
        ("When you arrive at the factory", "Brief me", "location"),
        ("Tap an NFC tag at the goods door", "Batch arrived", "wave.3.right"),
        ("When you leave work", "Chase silent workshops", "figure.walk.departure")
    ]

    var body: some View {
        Form {
            Section {
                ForEach(rules) { rule in
                    VStack(alignment: .leading, spacing: 6) {
                        Toggle(isOn: Binding(get: { rule.on }, set: { flip(rule, $0) })) {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(rule.title).font(.body.weight(.semibold))
                                Text(rule.detail).font(.footnote).foregroundStyle(Ink.secondary)
                            }
                        }
                        Button("Run now") { run(rule) }.font(.footnote.weight(.semibold)).buttonStyle(.borderless)
                    }
                    .padding(.vertical, 3)
                }
            } header: {
                Text("On the desk")
            } footer: {
                Text(note ?? "These only ask questions, using fixed messages. None of them moves a batch or writes to a client.")
            }
            Section {
                ShortcutsLink().shortcutsLinkStyle(.automaticOutline).frame(maxWidth: .infinity)
                ForEach(recipes, id: \.when) { recipe in
                    Label {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(recipe.when).font(.subheadline.weight(.medium))
                            Text(recipe.then).font(.footnote).foregroundStyle(Ink.secondary)
                        }
                    } icon: {
                        Image(systemName: recipe.symbol).foregroundStyle(Ink.cobalt)
                    }
                }
            } header: {
                Text("Ideas for the Shortcuts app")
            } footer: {
                Text("These are not switched on. Apple only lets you add them yourself: open Shortcuts, go to Automation, add one, then pick a Threadline action. For the Action button: Settings, Action Button, Shortcut, Threadline, Talk.")
            }
        }
        .scrollContentBackground(.hidden)
        .background(Backdrop())
        .navigationTitle("Automations")
        .navigationBarTitleDisplayMode(.inline)
        .task { rules = (try? await API.shared.get("/api/automations")) ?? [] }
    }

    private func flip(_ rule: Automation, _ on: Bool) {
        Task {
            Haptics.tick()
            if let next: [Automation] = try? await API.shared.post("/api/automations/\(rule.name)", ["on": on]) { rules = next }
        }
    }

    private func run(_ rule: Automation) {
        Task {
            do {
                let result: RuleResult = try await API.shared.post("/api/automations/\(rule.name)/run")
                note = result.text
            } catch {
                note = error.localizedDescription
            }
        }
    }
}

/// Everything the outside world can do, on one screen, for walking an order through good days and bad ones.
struct RehearseView: View {
    var body: some View {
        Form { DemoDirector() }
            .scrollContentBackground(.hidden)
            .background(Backdrop())
            .navigationTitle("Rehearse")
            .navigationBarTitleDisplayMode(.inline)
    }
}

/// The other side of the conversation, for rehearsing alone. These go down the same path as a real Telegram message,
/// and every one is labelled role-play in the thread.
private struct DemoDirector: View {
    @Environment(AppModel.self) private var model
    @State private var party = "W1"
    @State private var text = ""
    @State private var status: String?
    @State private var sending: String?
    @State private var done: String?

    private struct Beat: Hashable {
        var label: String
        var party: String
        var text: String
    }

    private var beats: [Beat] {
        var out = [Beat(label: "QuickStitch has a power cut", party: "W1", text: "Power cut at the unit, we are closed till Monday. Sorry."),
                   Beat(label: "SteadyHands asks a question", party: "W2", text: "Do you want ORD-096 folded or on hangers?"),
                   Beat(label: "Nimble Needle runs late", party: "W6", text: "ORD-041 needs two more days, machine trouble."),
                   Beat(label: "GiantWeave raises its rate", party: "W5", text: "Our rate goes up to 1.4 per piece from next week.")]
        if let job = model.jobs.first(where: { $0.stage == "offered" }) {
            out.insert(Beat(label: "\(job.workshop) accepts \(job.order)", party: job.workshopId, text: "\(job.order) accepted, thank you."), at: 0)
            out.insert(Beat(label: "\(job.workshop) cannot take \(job.order)", party: job.workshopId, text: "Sorry, cannot take \(job.order), we are too busy."), at: 1)
        }
        if let customer = model.jobs.first(where: { $0.customer != nil })?.customer {
            out.append(Beat(label: "\(customer) asks for a status", party: "client:\(customer)", text: "Hi, where is our order? When will it arrive?"))
        }
        return out
    }

    var body: some View {
        Section {
            if let status {
                Text(status).font(.footnote).foregroundStyle(Ink.secondary)
            }
            ForEach(beats, id: \.self) { beat in
                Button { send(beat.label, beat.party, beat.text) } label: {
                    HStack {
                        Text(beat.label)
                        Spacer()
                        if sending == beat.label {
                            ProgressView()
                        } else if done == beat.label {
                            Image(systemName: "checkmark").foregroundStyle(Ink.teal)
                        }
                    }
                }
                .disabled(sending != nil)
            }
            Picker("As", selection: $party) {
                ForEach(model.workshops) { Text($0.name).tag($0.id) }
            }
            TextField("Write as them", text: $text, axis: .vertical)
            Button(sending == "custom" ? "Reading it" : "Send as them") {
                send("custom", party, text)
                text = ""
            }
            .disabled(text.isEmpty || sending != nil)
        } header: {
            Text("Rehearse the other side")
        } footer: {
            Text("The desk reads each message, which takes a few seconds. Requests from Today or Work are faster.")
        }
        Section {
            Button("Move to the next day") { nextDay() }
            Button("Reset the demo", role: .destructive) { reset() }
        }
    }

    /// One at a time, and answered at the touch: the reading itself takes a few seconds.
    private func send(_ label: String, _ party: String, _ text: String) {
        Haptics.tick()
        sending = label
        done = nil
        status = nil
        Task {
            defer { sending = nil }
            do {
                let reading: Reading = try await API.shared.post("/api/roleplay/inbound", ["party": party, "text": text])
                done = label
                status = "Understood: \(reading.understood)"
                Haptics.success()
            } catch {
                status = error.localizedDescription
            }
        }
    }

    private func nextDay() {
        guard let today = model.today?.today, let date = ISO8601DateFormatter.day.date(from: today),
              let next = Calendar(identifier: .gregorian).date(byAdding: .day, value: 1, to: date) else { return }
        Task {
            let _: Empty? = try? await API.shared.post("/api/clock", ["today": ISO8601DateFormatter.day.string(from: next)])
            await model.refresh()
        }
    }

    private func reset() {
        Task {
            let _: Empty? = try? await API.shared.post("/api/demo/reset")
            await model.refresh()
            model.freshSpeak += 1
            model.paths = [:]
            model.tab = .today
        }
    }
}

struct Empty: Codable {}

extension ISO8601DateFormatter {
    static let day: ISO8601DateFormatter = {
        let f = ISO8601DateFormatter()
        f.formatOptions = [.withFullDate]
        return f
    }()
}

struct TrailView: View {
    @State private var entries: [TrailEntry] = []

    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 14) {
                ForEach(Array(entries.enumerated()), id: \.offset) { _, entry in
                    HStack(alignment: .top, spacing: 12) {
                        Circle().fill(entry.label == "Decision confirmed" || entry.label == "Plan approved" || entry.label == "Client told" ? Ink.human : Ink.line).frame(width: 9, height: 9).padding(.top, 6)
                        VStack(alignment: .leading, spacing: 2) {
                            Text([entry.orderId, entry.label].compactMap { $0 }.joined(separator: ": ")).font(.subheadline.weight(.semibold)).foregroundStyle(Ink.primary)
                            if !entry.detail.isEmpty { Text(entry.detail).font(.footnote).foregroundStyle(Ink.secondary) }
                            Text([entry.by, Dates.time(entry.at)].compactMap { $0 }.joined(separator: ", ")).font(.caption).foregroundStyle(Ink.tertiary)
                        }
                    }
                }
            }
            .padding(16)
        }
        .background(Backdrop())
        .navigationTitle("What happened")
        .navigationBarTitleDisplayMode(.inline)
        .task { entries = (try? await API.shared.get("/api/trail")) ?? [] }
    }
}

/// Picks who reads the brief. Tapping a voice plays a line in it.
struct VoiceView: View {
    private struct Option: Identifiable, Sendable {
        var id: String
        var name: String
        var grade: String
    }

    @Environment(AppModel.self) private var model
    @AppStorage("briefVoice") private var chosen = ""
    @State private var voices: [Option] = []
    @State private var loaded = false

    var body: some View {
        List {
            Section {
                ForEach(voices) { voice in
                    Button {
                        chosen = voice.id
                        model.briefVoice.sample()
                    } label: {
                        HStack {
                            VStack(alignment: .leading, spacing: 2) {
                                Text(voice.name).foregroundStyle(Ink.primary)
                                Text(voice.grade).font(.caption).foregroundStyle(Ink.tertiary)
                            }
                            Spacer()
                            if voice.id == chosen || (chosen.isEmpty && voice.id == voices.first?.id) {
                                Image(systemName: "checkmark").foregroundStyle(Ink.cobalt)
                            }
                        }
                    }
                }
                if loaded, voices.isEmpty {
                    Text("Voices are only listed on a real iPhone.").font(.subheadline).foregroundStyle(Ink.secondary)
                }
            } footer: {
                Text("The best voices are a free download. On this iPhone, open Settings, Accessibility, Read & Speak, Voices, English, and pick one marked Premium. It then appears here at the top.")
            }
        }
        .scrollContentBackground(.hidden)
        .background(Backdrop())
        .navigationTitle("Voice for the brief")
        .navigationBarTitleDisplayMode(.inline)
        .task {
            #if !targetEnvironment(simulator)     // The simulator's voice library stalls the whole app.
            voices = await Task.detached { Voices.english().map { Option(id: $0.identifier, name: $0.name, grade: Voices.grade($0)) } }.value
            #endif
            loaded = true
        }
    }
}
