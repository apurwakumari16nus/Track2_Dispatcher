import SwiftUI

extension View {
    /// A tag grows into its batch, rather than the screen sliding in.
    @ViewBuilder func zoomSource(_ id: String) -> some View { modifier(ZoomSource(id: id)) }
    @ViewBuilder func zoomTarget(_ id: String) -> some View { modifier(ZoomTarget(id: id)) }

    /// Every tab can reach every screen, so a card, a banner or Siri lands in the same place.
    func destinations() -> some View {
        navigationDestination(for: Route.self) { route in
            switch route {
            case .incident(let id): IncidentView(id: id)
            case .job(let key): BatchView(key: key)
            case .thread(let party): ConversationView(party: party)
            case .workshop(let id): WorkshopView(id: id)
            case .letter(let id): LetterView(id: id)
            case .requests: RequestsView()
            case .trail: TrailView()
            case .settings: SettingsView()
            case .voice: VoiceView()
            case .automations: AutomationsView()
            case .rehearse: RehearseView()
            }
        }
    }
}

private struct ZoomSource: ViewModifier {
    var id: String
    @Environment(\.zoomSpace) private var space

    func body(content: Content) -> some View {
        if let space { content.matchedTransitionSource(id: id, in: space) } else { content }
    }
}

private struct ZoomTarget: ViewModifier {
    var id: String
    @Environment(\.zoomSpace) private var space

    func body(content: Content) -> some View {
        if let space { content.navigationTransition(.zoom(sourceID: id, in: space)) } else { content }
    }
}

struct RootView: View {
    @Environment(AppModel.self) private var model
    @Namespace private var zoom

    var body: some View {
        @Bindable var model = model
        TabView(selection: $model.tab) {
            Tab("Today", systemImage: "sun.max", value: AppTab.today) { TodayView() }
                .badge((model.today?.attention.filter { $0.kind != "requests" }.count) ?? 0)
            Tab("Work", systemImage: "square.stack.3d.up", value: AppTab.work) { WorkView() }
            Tab("Messages", systemImage: "bubble.left.and.bubble.right", value: AppTab.messages) { MessagesView() }
            Tab("Network", systemImage: "circle.grid.cross", value: AppTab.network) { NetworkView() }
            Tab("Speak", systemImage: "waveform", value: AppTab.speak, role: .search) { SpeakView() }
        }
        .tint(Ink.cobalt)
        .environment(\.zoomSpace, zoom)
        .sheet(isPresented: $model.composing) { NewRequestView().environment(model) }
        .animation(.smooth, value: model.offline)
        .onChange(of: model.tab) { old, _ in
            if old == .speak { Task { await model.speech.stop() } }     // The microphone never outlives the Speak screen.
        }
        .overlay(alignment: .top) {
            if let banner = model.banner {
                BannerView(banner: banner)
                    .padding(.horizontal, 12)
                    .transition(.move(edge: .top).combined(with: .opacity))
            } else if model.today != nil, let offline = model.offline {
                ConnectionBar(text: offline)
                    .padding(.horizontal, 12)
                    .transition(.move(edge: .top).combined(with: .opacity))
            }
        }
    }
}

/// Says plainly when the desk cannot be reached, on every screen. What is showing is the last known picture.
private struct ConnectionBar: View {
    @Environment(AppModel.self) private var model
    var text: String

    var body: some View {
        Button { Task { await model.refresh() } } label: {
            HStack(alignment: .top, spacing: 10) {
                Image(systemName: "wifi.exclamationmark").foregroundStyle(Ink.amber).padding(.top, 2)
                VStack(alignment: .leading, spacing: 2) {
                    Text(text).font(.footnote.weight(.semibold)).foregroundStyle(Ink.primary).multilineTextAlignment(.leading)
                    Text("Showing the last update. Tap to try again.").font(.caption).foregroundStyle(Ink.secondary)
                }
                Spacer(minLength: 0)
            }
            .padding(12)
            .glassEffect(.regular, in: .rect(cornerRadius: 18, style: .continuous))
        }
        .buttonStyle(.plain)
    }
}

private struct BannerView: View {
    @Environment(AppModel.self) private var model
    var banner: Banner

    var body: some View {
        Button {
            if let target = banner.target { model.open(target) }
            withAnimation { model.banner = nil }
        } label: {
            HStack(alignment: .top, spacing: 10) {
                Circle().fill(banner.tone.color).frame(width: 9, height: 9).padding(.top, 5)
                VStack(alignment: .leading, spacing: 2) {
                    Text(banner.title).font(.subheadline.weight(.semibold)).foregroundStyle(Ink.primary)
                    Text(banner.text).font(.footnote).foregroundStyle(Ink.secondary).lineLimit(2).multilineTextAlignment(.leading)
                }
                Spacer(minLength: 0)
            }
            .padding(14)
            .glassEffect(.regular, in: .rect(cornerRadius: 22, style: .continuous))
        }
        .buttonStyle(.plain)
    }
}

struct TodayView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        NavigationStack(path: model.path(.today)) {
            ScrollView {
                VStack(alignment: .leading, spacing: 18) {
                    if let today = model.today {
                        HeroCard(today: today)
                        attention(today)
                        if let day = Dates.day(today.today) { ThreadCalendar(today: day) }
                    } else if let offline = model.offline {
                        ConnectionNotice(text: offline)
                    } else {
                        Stitches(running: true, gradient: true).padding(.top, 120)
                    }
                }
                .padding(.horizontal, 16)
                .padding(.top, 8)
                .padding(.bottom, 30)
            }
            .scrollEdgeEffectStyle(.soft, for: .top)
            .background(Backdrop())
            .refreshable { await model.refresh() }
            .toolbar {
                ToolbarItem(placement: .topBarLeading) {
                    VStack(alignment: .leading, spacing: 3) {
                        Text("Threadline").font(.hero(23)).foregroundStyle(Ink.primary).fixedSize()
                        Stitches(gradient: true, width: 2).frame(width: 118)
                    }
                    .accessibilityAddTraits(.isHeader)
                }
                .sharedBackgroundVisibility(.hidden)
                ToolbarItem(placement: .topBarTrailing) {
                    Button { model.composing = true } label: { Image(systemName: "plus") }.accessibilityLabel("New request")
                }
                ToolbarItem(placement: .topBarTrailing) {
                    NavigationLink(value: Route.settings) { Image(systemName: "person.crop.circle") }.accessibilityLabel("Settings")
                }
            }
            .destinations()
        }
    }

    private func attention(_ today: TodayData) -> some View {
        VStack(spacing: 10) {
            ForEach(today.attention) { item in
                AttentionCard(item: item)
                    .transition(.asymmetric(insertion: .move(edge: .top).combined(with: .opacity), removal: .opacity))
            }
            if today.attention.isEmpty {
                Text("Nothing needs you. Say a request whenever you are ready.").font(.subheadline).foregroundStyle(Ink.secondary).card(tint: .info)
            }
        }
        .animation(.spring(response: 0.45, dampingFraction: 0.85), value: today.attention)
    }
}

/// The day in one sentence, then the whole line beneath it, on the one piece of dyed cloth the screen gets.
private struct HeroCard: View {
    @Environment(AppModel.self) private var model
    var today: TodayData

    private var voice: BriefVoice { model.briefVoice }

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            HStack {
                Text(Dates.weekday(today.today)).font(.subheadline.weight(.medium)).foregroundStyle(.white.opacity(0.82))
                Spacer()
                Button { voice.toggle(today.spoken ?? today.brief) } label: {
                    Label(voice.speaking ? "Stop" : "Listen", systemImage: voice.speaking ? "stop.fill" : "speaker.wave.2.fill")
                        .font(.caption.weight(.semibold))
                        .foregroundStyle(.white)
                        .padding(.horizontal, 11).padding(.vertical, 7)
                        .contentTransition(.symbolEffect(.replace))
                }
                .glassEffect(.clear.interactive(), in: .capsule)
                .accessibilityLabel(voice.speaking ? "Stop the brief" : "Hear the brief")
            }
            Text(today.headline).font(.hero(36)).foregroundStyle(.white).contentTransition(.numericText()).animation(.smooth, value: today.headline).minimumScaleFactor(0.8).lineLimit(1)
            Text("\(today.out) batches out, \(today.piecesOut.formatted()) pieces.").font(.subheadline).foregroundStyle(.white.opacity(0.82))
            StageLine(counts: model.stageCounts, selected: nil) { model.showStage($0) }.padding(.top, 12)
        }
        .dyeCard()
    }
}

/// Five stitches: sent, accepted, sewing, completed, back.
struct StepDots: View {
    var step: Int

    var body: some View {
        HStack(spacing: 3) {
            ForEach(0 ..< 5, id: \.self) { index in
                Capsule().fill(index <= step ? AnyShapeStyle(Stage.allCases[index + 1].gradient) : AnyShapeStyle(.primary.opacity(0.14))).frame(width: 9, height: 3)
            }
        }
        .accessibilityLabel("Stage \(step + 1) of 5")
    }
}

struct AttentionCard: View {
    @Environment(AppModel.self) private var model
    var item: Attention
    @State private var working = false

    private var tone: Tone { Tone(rawValue: item.tone) ?? .info }

    private var symbol: String {
        switch item.kind {
        case "incident": "exclamationmark.triangle.fill"
        case "letter": "envelope.fill"
        case "question": "questionmark.bubble.fill"
        case "declined": "xmark.circle.fill"
        case "unsent": "paperplane.fill"
        case "overdue": "clock.badge.exclamationmark.fill"
        case "due": "shippingbox.fill"
        case "silent": "bell.fill"
        case "late": "calendar.badge.exclamationmark"
        default: "tray.full.fill"
        }
    }

    var body: some View {
        Button { Task { await act() } } label: {
            HStack(alignment: .top, spacing: 12) {
                GlyphBadge(symbol: symbol, tone: tone)
                VStack(alignment: .leading, spacing: 3) {
                    Text(item.title).font(.body.weight(.semibold)).foregroundStyle(Ink.primary).multilineTextAlignment(.leading)
                    Text(item.detail).font(.subheadline).foregroundStyle(Ink.secondary).multilineTextAlignment(.leading).lineLimit(2)
                    HStack(spacing: 4) {
                        Text(working ? "Working" : item.action)
                        Image(systemName: "arrow.right").font(.caption.weight(.bold))
                    }
                    .font(.subheadline.weight(.semibold)).foregroundStyle(Ink.cobalt).padding(.top, 3)
                }
                Spacer(minLength: 0)
            }
            .card(padding: 13, tint: tone)
        }
        .buttonStyle(.plain)
        .accessibilityHint(item.action)
    }

    /// The obvious next step happens straight away where it is safe; anything going outside opens for review.
    private func act() async {
        let key = API.shared.encoded(item.target.id)
        switch item.kind {
        case "silent", "overdue":
            working = true
            let _: Message? = try? await API.shared.post("/api/batches/\(key)/chase")
            Haptics.tick()
            await model.refresh()
            working = false
        case "unsent":
            working = true
            let _: Message? = try? await API.shared.post("/api/batches/\(key)/offer")
            Haptics.tick()
            await model.refresh()
            working = false
        case "late":
            working = true
            let letter: LetterRow? = try? await API.shared.post("/api/batches/\(key)/letter")
            await model.refresh()
            working = false
            if let id = letter?.id { model.open(Target(type: "letter", id: id)) }
        default:
            model.open(item.target)
        }
    }
}

struct LetterRow: Codable { var id: String }

struct ConnectionNotice: View {
    var text: String

    var body: some View {
        VStack(alignment: .leading, spacing: 8) {
            Text("Not connected").font(.hero(32)).foregroundStyle(Ink.primary)
            Text(text).font(.subheadline).foregroundStyle(Ink.secondary)
            NavigationLink("Open Settings", value: Route.settings).font(.subheadline.weight(.semibold))
        }
        .padding(.top, 60)
    }
}
