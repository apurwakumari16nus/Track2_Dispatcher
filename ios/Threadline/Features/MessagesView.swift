import SwiftUI

struct MessagesView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        NavigationStack(path: model.path(.messages)) {
            ScrollView {
                VStack(alignment: .leading, spacing: 22) {
                    Label("\(model.threads.filter(\.connected).count) of \(model.threads.count) connected on Telegram. Their replies appear here as they happen.", systemImage: "paperplane.fill")
                        .font(.footnote).foregroundStyle(Ink.secondary)
                    section("Workshops", model.threads.filter { $0.type != "client" })
                    section("Clients", model.threads.filter { $0.type == "client" })
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 24)
            }
            .background(Backdrop())
            .navigationTitle("Messages")
            .refreshable { await model.refresh() }
            .destinations()
        }
    }

    @ViewBuilder private func section(_ title: String, _ threads: [ThreadSummary]) -> some View {
        if !threads.isEmpty {
            VStack(alignment: .leading, spacing: 8) {
                Text(title).font(.headline).foregroundStyle(Ink.primary)
                VStack(spacing: 0) {
                    ForEach(Array(threads.enumerated()), id: \.element.id) { index, thread in
                        NavigationLink(value: Route.thread(thread.party)) { ThreadRow(thread: thread) }.buttonStyle(.plain)
                        if index < threads.count - 1 { Divider().overlay(Ink.line).padding(.leading, 56) }
                    }
                }
                .card(padding: 14)
            }
        }
    }
}

private struct ThreadRow: View {
    var thread: ThreadSummary

    var body: some View {
        HStack(spacing: 12) {
            Avatar(name: thread.name, closed: thread.status == "SUSPENDED", client: thread.type == "client")
            VStack(alignment: .leading, spacing: 3) {
                HStack {
                    Text(thread.name).font(.body.weight(.semibold)).foregroundStyle(Ink.primary)
                    if thread.connected { Image(systemName: "paperplane.fill").font(.caption2).foregroundStyle(Ink.cyan).accessibilityLabel("On Telegram") }
                    Spacer()
                    Text(Dates.time(thread.lastAt)).font(.caption).foregroundStyle(Ink.tertiary)
                }
                Text(thread.lastText?.components(separatedBy: "\n").first ?? "No messages yet").font(.subheadline).foregroundStyle(Ink.secondary).lineLimit(2)
            }
        }
        .padding(.vertical, 11)
        .contentShape(.rect)
    }
}

struct Avatar: View {
    var name: String
    var closed = false
    var client = false

    var body: some View {
        Text(String(name.prefix(1)))
            .font(.headline).foregroundStyle(.white)
            .frame(width: 44, height: 44)
            .background((closed ? Tone.risk : client ? Tone.warn : Tone.info).gradient, in: .circle)
            .accessibilityHidden(true)
    }
}

struct ConversationView: View {
    @Environment(AppModel.self) private var model
    var party: String
    @State private var thread: Thread?
    @State private var draft = ""
    @State private var failure: String?
    @FocusState private var typing: Bool

    private var path: String { "/api/threads/\(API.shared.encoded(party))" }

    var body: some View {
        ScrollView {
            LazyVStack(alignment: .leading, spacing: 8) {
                if let thread {
                    if !thread.connected {
                        Text("\(thread.name) is not on Telegram yet. Run /iam \(thread.name) in their chat to connect.").font(.footnote).foregroundStyle(Ink.secondary)
                            .padding(10).background(Ink.well, in: .rect(cornerRadius: 12, style: .continuous)).padding(.bottom, 6)
                    }
                    if thread.messages.isEmpty {
                        Text("No messages yet.").font(.subheadline).foregroundStyle(Ink.secondary).padding(.top, 40).frame(maxWidth: .infinity)
                    }
                    ForEach(thread.messages) { message in
                        Bubble(message: message).id(message.id)
                    }
                }
            }
            .padding(.horizontal, 14)
            .padding(.vertical, 10)
        }
        .defaultScrollAnchor(.bottom)
        .background(Backdrop())
        .navigationTitle(thread?.name ?? "")
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            if let link = thread?.telegramUrl.flatMap(URL.init(string:)) {
                ToolbarItem(placement: .topBarTrailing) {
                    Link(destination: link) { Image(systemName: "paperplane") }.accessibilityLabel("Open in Telegram")
                }
            }
            if !party.hasPrefix("client:") {
                ToolbarItem(placement: .topBarTrailing) {
                    NavigationLink(value: Route.workshop(party)) { Image(systemName: "info.circle") }.accessibilityLabel("Workshop details")
                }
            }
        }
        .safeAreaInset(edge: .bottom) { composer }
        .task(id: model.version) { thread = try? await API.shared.get(path) }
    }

    private var composer: some View {
        VStack(spacing: 8) {
            if let suggestions = thread?.suggestions, !suggestions.isEmpty, draft.isEmpty {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: 8) {
                        ForEach(suggestions, id: \.self) { item in
                            Button(item.label) { draft = item.text; typing = true }
                                .font(.footnote.weight(.medium))
                                .padding(.horizontal, 12).padding(.vertical, 7)
                                .background(Ink.card, in: .capsule)
                                .overlay(Capsule().strokeBorder(Ink.line, lineWidth: 0.5))
                        }
                    }
                    .padding(.horizontal, 14)
                }
            }
            if let failure { Text(failure).font(.footnote).foregroundStyle(Ink.coral) }
            HStack(spacing: 8) {
                TextField("Message \(thread?.name ?? "")", text: $draft, axis: .vertical)
                    .focused($typing)
                    .lineLimit(1 ... 5)
                    .padding(.horizontal, 14).padding(.vertical, 10)
                    .background(Ink.card, in: .rect(cornerRadius: 20, style: .continuous))
                Button { send() } label: {
                    Image(systemName: "arrow.up").font(.headline.weight(.bold)).foregroundStyle(.white).frame(width: 40, height: 40).background(Ink.cobalt, in: .circle)
                }
                .disabled(draft.trimmingCharacters(in: .whitespaces).isEmpty)
                .accessibilityLabel("Send")
            }
            .padding(.horizontal, 12)
        }
        .padding(.vertical, 8)
        .background(.bar)
    }

    private func send() {
        let text = draft
        draft = ""
        Task {
            do {
                let _: Message = try await API.shared.post(path + "/messages", ["text": text])
                Haptics.tick()
                await model.refresh()
            } catch {
                failure = error.localizedDescription
                draft = text
            }
        }
    }
}

/// A message, and underneath an incoming one, what Threadline understood it to mean.
private struct Bubble: View {
    @Environment(AppModel.self) private var model
    var message: Message

    private var incident: Attention? {
        guard message.reading != nil else { return nil }
        return model.today?.attention.first { $0.kind == "incident" }
    }

    /// A tap on a Telegram job card reads as a status change, in that status's colour.
    private var status: Stage? { message.tapped == true ? Stage(status: message.text) : nil }

    var body: some View {
        VStack(alignment: message.isOutgoing ? .trailing : .leading, spacing: 4) {
            if let status {
                HStack(spacing: 8) {
                    StageBadge(stage: status, size: 24)
                    Text(message.text).font(.subheadline.weight(.medium)).foregroundStyle(status.color)
                }
                .padding(.leading, 6).padding(.trailing, 13).padding(.vertical, 6)
                .background(status.color.opacity(0.12), in: .capsule)
            } else {
            Text(message.text)
                .font(.body)
                .foregroundStyle(message.isOutgoing && message.automatic != true ? .white : Ink.primary)
                .padding(.horizontal, 13).padding(.vertical, 9)
                .background(background, in: .rect(cornerRadius: 18, style: .continuous))
                .shadow(color: .black.opacity(message.isOutgoing ? 0 : 0.04), radius: 6, y: 2)
            }
            HStack(spacing: 4) {
                if message.automatic == true { Text("Sent by Threadline") }
                if message.channel == "telegram" { Text("via Telegram") }
                if message.channel == "roleplay" { Text("role-play") }
                if message.isOutgoing, message.delivered == false { Text("kept in the app") }
                Text(Dates.time(message.at))
            }
            .font(.caption2).foregroundStyle(Ink.tertiary)
            if let reading = message.reading, !message.isOutgoing {
                Button {
                    if let incident, reading.kind != "accepts" { model.open(incident.target) }
                } label: {
                    Label(reading.understood, systemImage: "sparkle").font(.caption.weight(.semibold)).foregroundStyle(Ink.teal)
                        .padding(.horizontal, 10).padding(.vertical, 5)
                        .background(Ink.well, in: .capsule)
                }
                .buttonStyle(.plain)
            }
        }
        .frame(maxWidth: .infinity, alignment: message.isOutgoing ? .trailing : .leading)
        .padding(message.isOutgoing ? .leading : .trailing, 40)
    }

    private var background: AnyShapeStyle {
        if message.automatic == true { return AnyShapeStyle(Ink.well) }
        return message.isOutgoing ? AnyShapeStyle(Ink.press) : AnyShapeStyle(Ink.card)
    }
}
