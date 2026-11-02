import SwiftUI

struct WorkView: View {
    @Environment(AppModel.self) private var model
    @State private var everyRequest = false

    private var urgent: [Job] {
        model.jobs.filter { $0.problem != nil }.sorted { ($0.alert == .risk ? 0 : 1, $0.back ?? "") < ($1.alert == .risk ? 0 : 1, $1.back ?? "") }
    }

    /// With no filter, problems sit together at the top. Filtered to a stage, everything at that stage shows.
    private func jobs(_ stage: Stage) -> [Job] {
        model.jobs.filter { $0.lane == stage && (model.workFilter != nil || $0.problem == nil) }.sorted { ($0.back ?? "") < ($1.back ?? "") }
    }

    var body: some View {
        NavigationStack(path: model.path(.work)) {
            ScrollView {
                VStack(alignment: .leading, spacing: 24) {
                    StageLine(counts: model.stageCounts, selected: model.workFilter) { stage in
                        Haptics.tick()
                        withAnimation(.smooth) { model.workFilter = model.workFilter == stage ? nil : stage }
                    }
                    .card(padding: 12)
                    if let filter = model.workFilter {
                        Button("Show every stage", systemImage: "xmark.circle.fill") { withAnimation(.smooth) { model.workFilter = nil } }
                            .font(.subheadline.weight(.medium))
                            .accessibilityHint("Now showing \(filter.name)")
                    } else if !urgent.isEmpty {
                        Lane(title: "Needs you", detail: "These will not move on their own", count: urgent.count, colour: Ink.coral) {
                            GlyphBadge(symbol: "exclamationmark", tone: .risk, size: 30)
                        } content: {
                            ForEach(urgent) { tag($0) }
                        }
                    }
                    ForEach(model.workFilter.map { [$0] } ?? Stage.allCases) { stage in
                        if stage == .review {
                            review
                        } else {
                            lane(stage)
                        }
                    }
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 24)
            }
            .scrollEdgeEffectStyle(.soft, for: .top)
            .background(Backdrop())
            .navigationTitle("Work")
            .refreshable { await model.refresh() }
            .toolbar {
                if model.today?.demo == true {
                    ToolbarItem(placement: .topBarTrailing) {
                        NavigationLink(value: Route.rehearse) { Image(systemName: "theatermasks") }.accessibilityLabel("Rehearse")
                    }
                }
                ToolbarItem(placement: .topBarTrailing) {
                    Button { model.composing = true } label: { Image(systemName: "plus") }.accessibilityLabel("New request")
                }
            }
            .destinations()
        }
    }

    private func tag(_ job: Job) -> some View {
        NavigationLink(value: Route.job(job.key)) { JobTag(job: job) }
            .buttonStyle(.plain)
            .zoomSource(job.key)
    }

    @ViewBuilder private func lane(_ stage: Stage) -> some View {
        let shown = jobs(stage)
        if !shown.isEmpty || model.workFilter == stage {
            Lane(title: stage.name, detail: stage.meaning, count: shown.count, colour: stage.color) {
                StageBadge(stage: stage)
            } content: {
                ForEach(shown) { tag($0) }
                if shown.isEmpty {
                    Text("Nothing here right now.").font(.subheadline).foregroundStyle(Ink.secondary).padding(.leading, 44)
                }
            }
        }
    }

    private var review: some View {
        let count = model.requests.count
        return Lane(title: Stage.review.name, detail: Stage.review.meaning, count: count, colour: Stage.review.color) {
            StageBadge(stage: .review)
        } content: {
            ForEach(everyRequest || model.workFilter == .review ? model.requests : Array(model.requests.prefix(2))) { RequestRow(request: $0) }
            if count > 2, !everyRequest, model.workFilter != .review {
                Button("Show all \(count)") { withAnimation(.smooth) { everyRequest = true } }
                    .font(.subheadline.weight(.medium)).padding(.leading, 44)
            }
            if count == 0 {
                Text("Every request has a decision.").font(.subheadline).foregroundStyle(Ink.secondary).padding(.leading, 44)
            }
        }
    }
}

/// One stage of the line. Its thread runs down through the eyelet of every tag in it.
struct Lane<Badge: View, Content: View>: View {
    var title: String
    var detail: String
    var count: Int
    var colour: Color
    @ViewBuilder var badge: Badge
    @ViewBuilder var content: Content

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            HStack(spacing: 0) {
                badge.frame(width: 44)
                VStack(alignment: .leading, spacing: 1) {
                    Text(title).font(.headline).foregroundStyle(Ink.primary)
                    Text(detail).font(.caption).foregroundStyle(Ink.secondary)
                }
                .padding(.leading, 8)
                Spacer()
                Text("\(count)").font(.headline).monospacedDigit().foregroundStyle(colour)
            }
            .accessibilityElement(children: .combine)
            content
        }
        .background(alignment: .topLeading) {
            VStitch(colour: colour.opacity(0.5), width: 2).padding(.leading, 21).padding(.top, 30).padding(.bottom, 24)
        }
    }
}

/// An order as a swing tag: its stage on the stub, then who has it and when it should be back.
struct JobTag: View {
    @Environment(AppModel.self) private var model
    var job: Job

    private var due: String {
        if job.stage == "declined" { return "Needs a new workshop, customer date \(Dates.short(job.due))" }
        if job.health == "overdue", let back = Dates.day(job.back), let today = Dates.day(model.today?.today) {
            let days = Dates.gap(back, today)
            return "Was due back \(Dates.short(job.back)), \(days) day\(days == 1 ? "" : "s") ago"
        }
        return "\(job.stage == "received" ? "Back" : "Expected back") \(Dates.short(job.back)), \(spareText(job.daysToSpare).lowercased())"
    }

    var body: some View {
        TagCard(stage: job.lane, alert: job.alert) {
            VStack(alignment: .leading, spacing: 4) {
                HStack(alignment: .firstTextBaseline) {
                    Text(job.order).font(.headline).foregroundStyle(Ink.primary)
                    Spacer(minLength: 6)
                    Text(job.problem ?? job.lane.name).font(.caption.weight(.semibold)).foregroundStyle(job.statusColour).lineLimit(1)
                }
                Text("\(job.goods)\(job.customer.map { " for \($0)" } ?? "")").font(.subheadline).foregroundStyle(Ink.primary).lineLimit(1)
                HStack {
                    Text(job.workshop).font(.footnote.weight(.medium)).foregroundStyle(Ink.secondary)
                    Spacer()
                    StepDots(step: job.step)
                }
                Text(due).font(.footnote).foregroundStyle(job.alert == nil ? Ink.secondary : job.statusColour).lineLimit(1).minimumScaleFactor(0.85)
            }
        }
        .accessibilityElement(children: .combine)
    }
}

private struct RequestList: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        ForEach(model.requests) { request in
            RequestRow(request: request)
        }
        if model.requests.isEmpty {
            Text("Every request has a decision.").font(.subheadline).foregroundStyle(Ink.secondary).padding(.top, 60)
        }
    }
}

struct RequestsView: View {
    @Environment(AppModel.self) private var model

    var body: some View {
        ScrollView {
            VStack(spacing: 12) { RequestList() }.padding(.horizontal, 16).padding(.bottom, 24)
        }
        .background(Backdrop())
        .navigationTitle("Requests")
    }
}

private struct RequestRow: View {
    var request: WaitingRequest
    @State private var result: SpeakCard?
    @State private var working = false
    @State private var failure: String?

    var body: some View {
        Button { open() } label: {
            TagCard(stage: .review) {
                VStack(alignment: .leading, spacing: 4) {
                    HStack(alignment: .firstTextBaseline) {
                        Text(request.sender).font(.subheadline.weight(.semibold)).foregroundStyle(Ink.primary)
                        Spacer()
                        Text(working ? "Reading" : "\(request.channel), \(request.time)").font(.caption).foregroundStyle(Ink.tertiary)
                    }
                    Text(request.text).font(.subheadline).foregroundStyle(Ink.secondary).lineLimit(2).multilineTextAlignment(.leading)
                    if let failure { Text(failure).font(.footnote).foregroundStyle(Ink.coral) }
                }
            }
        }
        .buttonStyle(.plain)
        .sheet(item: Binding(get: { result.map { Wrapped(card: $0) } }, set: { if $0 == nil { result = nil } })) { wrapped in
            NavigationStack {
                ScrollView {
                    CardView(card: wrapped.card, spoken: request.text) { result = nil } replaced: { result = $0 }
                        .padding(16)
                }
                .background(Backdrop())
                .toolbar { ToolbarItem(placement: .cancellationAction) { Button("Close") { result = nil } } }
            }
            .presentationDetents([.large])
        }
    }

    private func open() {
        working = true
        failure = nil
        Task {
            defer { working = false }
            do {
                result = try await API.shared.post("/api/requests/open", ["line": request.line, "request": request.id])
            } catch {
                failure = error.localizedDescription
            }
        }
    }
}

private struct Wrapped: Identifiable, Equatable {
    var card: SpeakCard
    var id: Int { card.hashValue }
}

/// The batch's journey as one stitched line, with who did what underneath.
struct JourneyView: View {
    var job: Job
    @Environment(\.onCloth) private var onCloth
    private let names = ["Sent", "Accepted", "Sewing", "Completed", "Back"]

    private func done(_ index: Int) -> Color { onCloth ? .white : Stage.allCases[index + 1].color }
    private var todo: Color { onCloth ? .white.opacity(0.28) : .primary.opacity(0.16) }

    var body: some View {
        VStack(spacing: 6) {
            HStack(spacing: 0) {
                ForEach(0 ..< 5, id: \.self) { index in
                    Circle()
                        .fill(index <= job.step ? done(index) : todo)
                        .frame(width: 11, height: 11)
                    if index < 4 {
                        Stitches(running: index == job.step && job.stage != "received", width: 2, colour: index < job.step ? done(index) : todo)
                    }
                }
            }
            HStack {
                ForEach(names, id: \.self) { name in
                    Text(name).font(.caption2).foregroundStyle(onCloth ? .white.opacity(0.82) : Ink.secondary)
                    if name != "Back" { Spacer() }
                }
            }
        }
        .accessibilityElement()
        .accessibilityLabel("\(job.stageLabel)")
    }
}

struct BatchView: View {
    @Environment(AppModel.self) private var model
    var key: String
    @State private var declining = false
    @State private var reasons: [String] = []
    @State private var failure: String?

    private var job: Job? { model.jobs.first { $0.key == key } }

    var body: some View {
        ScrollView {
            if let job {
                VStack(alignment: .leading, spacing: 14) {
                    VStack(alignment: .leading, spacing: 14) {
                        HStack(spacing: 8) {
                            if let alert = job.alert {
                                GlyphBadge(symbol: "exclamationmark", tone: alert, size: 24)
                            } else {
                                StageBadge(stage: job.lane, size: 24)
                            }
                            Text(job.problem ?? job.stageLabel).font(.label).foregroundStyle(.white.opacity(0.9))
                        }
                        Text(job.goods).font(.hero(32)).foregroundStyle(Ink.primary)
                        Text("\(job.customer ?? "No customer on record"), at \(job.workshop)").font(.subheadline).foregroundStyle(.white.opacity(0.82))
                        JourneyView(job: job).padding(.top, 4)
                        HStack(alignment: .top) {
                            Fact(label: job.backWas == nil ? "Back by" : "Back by, was \(Dates.short(job.backWas))", value: Dates.short(job.back))
                            Fact(label: "Customer date", value: Dates.short(job.due))
                            Fact(label: (job.daysToSpare ?? 0) < 0 ? "Late" : "To spare", value: job.daysToSpare.map { "\(abs($0)) day\(abs($0) == 1 ? "" : "s")" } ?? "n/a", tone: (job.daysToSpare ?? 0) < 0 ? Ink.coral : Ink.primary)
                        }
                    }
                    .dyeCard(job.alert == .risk ? .alarm : .thread)
                    actions(job)
                    if let failure { Text(failure).font(.footnote).foregroundStyle(Ink.coral) }
                    VStack(alignment: .leading, spacing: 12) {
                        Text("What happened").font(.headline).foregroundStyle(Ink.primary)
                        ForEach(Array(job.log.enumerated().reversed()), id: \.offset) { _, entry in
                            VStack(alignment: .leading, spacing: 2) {
                                Text(entry.label).font(.subheadline.weight(.semibold)).foregroundStyle(Ink.primary)
                                if !entry.detail.isEmpty { Text(entry.detail).font(.footnote).foregroundStyle(Ink.secondary) }
                                Text([entry.by, Dates.short(entry.on)].compactMap { $0 == "n/a" ? nil : $0 }.joined(separator: ", ")).font(.caption).foregroundStyle(Ink.tertiary)
                            }
                        }
                    }
                    .card()
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 24)
            }
        }
        .background(Backdrop())
        .navigationTitle(job?.order ?? "Batch")
        .navigationBarTitleDisplayMode(.inline)
        .zoomTarget(key)
    }

    @ViewBuilder private func actions(_ job: Job) -> some View {
        VStack(spacing: 10) {
            if job.stage == "declined", let plan = model.today?.attention.first(where: { $0.kind == "incident" && $0.title.contains(job.order) }) {
                Button("See the plan") { model.open(plan.target) }.buttonStyle(DyeButton())
            }
            if job.stage == "booked" {
                Button { post("offer") } label: { wide("Send to \(job.workshop)") }.buttonStyle(.glassProminent)
            }
            if job.stage != "received" {
                if ["ready", "shipped"].contains(job.stage) {
                    Button { post("received") } label: { wide("Mark received") }.buttonStyle(.glassProminent).tint(Ink.human)
                }
                HStack(spacing: 10) {
                    Button { post("chase") } label: { wide("Chase") }.buttonStyle(.glass)
                    Button { model.open(Target(type: "thread", id: job.workshopId)) } label: { wide("Message") }.buttonStyle(.glass)
                }
                if ["accepted", "in_production"].contains(job.stage) {
                    Button("It has arrived early") { post("received") }.font(.footnote.weight(.medium)).frame(maxWidth: .infinity)
                }
                if model.today?.demo == true, let next = job.nextTap {
                    Button { tap(next.action, job) } label: {
                        Label("Rehearse: \(job.workshop) taps \(next.label)", systemImage: "theatermasks").font(.footnote.weight(.medium)).frame(maxWidth: .infinity)
                    }
                    if job.stage == "offered" {
                        Button { declining = true } label: {
                            Label("Rehearse: \(job.workshop) cannot take it", systemImage: "theatermasks").font(.footnote.weight(.medium)).frame(maxWidth: .infinity)
                        }
                        .confirmationDialog("Why can \(job.workshop) not take it?", isPresented: $declining, titleVisibility: .visible) {
                            ForEach(reasons, id: \.self) { reason in
                                Button(reason) { tap("declines", job, reason: reason) }
                            }
                        }
                        .task { reasons = (try? await API.shared.get("/api/reasons", as: Reasons.self))?.decline ?? [] }
                    }
                }
                if (job.daysToSpare ?? 0) < 0, job.customer != nil {
                    Button { tell() } label: { wide("Tell \(job.customer ?? "the client")") }.buttonStyle(.glass).tint(Ink.amber)
                }
            }
        }
    }

    /// The workshop's button, pressed from here. It takes the same path as Telegram and is labelled role-play on the record.
    private func tap(_ action: String, _ job: Job, reason: String? = nil) {
        Task {
            do {
                var body: [String: Any] = ["action": action, "key": key, "by": job.workshop]
                if let reason { body["reason"] = reason }
                let _: String = try await API.shared.post("/api/roleplay/tap", body)
                Haptics.tick()
                await model.refresh()
            } catch {
                failure = error.localizedDescription
            }
        }
    }

    private func wide(_ text: String) -> some View {
        Text(text).font(.subheadline.weight(.semibold)).frame(maxWidth: .infinity).padding(.vertical, 7)
    }

    private func post(_ action: String) {
        Task {
            do {
                let path = "/api/batches/\(API.shared.encoded(key))/\(action)"
                if action == "received" {
                    let _: Job = try await API.shared.post(path)
                    Haptics.success()
                } else {
                    let _: Message = try await API.shared.post(path)
                    Haptics.tick()
                }
                await model.refresh()
            } catch {
                failure = error.localizedDescription
            }
        }
    }

    private func tell() {
        Task {
            let letter: LetterRow? = try? await API.shared.post("/api/batches/\(API.shared.encoded(key))/letter")
            await model.refresh()
            if let id = letter?.id { model.open(Target(type: "letter", id: id)) }
        }
    }
}
