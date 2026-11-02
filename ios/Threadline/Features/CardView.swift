import SwiftUI

/// Whatever came back from what you said. Reads, answers and drafts all arrive here, in the same place.
struct CardView: View {
    @Environment(AppModel.self) private var model
    var card: SpeakCard
    var spoken: String
    var finished: () -> Void
    var replaced: (SpeakCard) -> Void

    var body: some View {
        VStack(alignment: .leading, spacing: 14) {
            if !spoken.isEmpty {
                Text(spoken).font(.subheadline).foregroundStyle(Ink.secondary).lineLimit(3)
                    .padding(.top, 6)
                if let reading = card.readAs { Text("Read as: \(reading)").font(.footnote).foregroundStyle(Ink.secondary) }
            }
            switch card.card {
            case "recommendation": RecommendationCard(card: card, replaced: replaced)
            case "clarify": ClarifyCard(card: card, replaced: replaced)
            case "draft": DraftCard(card: card, finished: finished)
            case "action": ActionCard(card: card, finished: finished, replaced: replaced)
            case "answer": AnswerCard(card: card)
            default: PlainCard(title: card.title ?? "Done", text: card.text ?? "", tone: card.card == "error" ? .risk : .info)
            }
        }
    }
}

struct PlainCard: View {
    var title: String
    var text: String
    var tone: Tone

    var body: some View {
        VStack(alignment: .leading, spacing: 6) {
            Text(title).font(.hero(26)).foregroundStyle(tone == .risk ? Ink.coral : Ink.primary)
            Text(text).font(.body).foregroundStyle(Ink.secondary)
        }
        .card(tint: tone)
    }
}

struct AnswerCard: View {
    @Environment(AppModel.self) private var model
    var card: SpeakCard

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(card.title ?? "").font(.label).foregroundStyle(Ink.secondary)
            Text(card.text ?? "").font(.hero(25)).foregroundStyle(Ink.primary).lineSpacing(3)
            ForEach(card.items ?? [], id: \.self) { item in
                Button { model.open(item.target) } label: {
                    HStack {
                        VStack(alignment: .leading, spacing: 2) {
                            Text(item.title).font(.subheadline.weight(.semibold)).foregroundStyle(Ink.primary).multilineTextAlignment(.leading)
                            if !item.detail.isEmpty { Text(item.detail).font(.footnote).foregroundStyle(Ink.secondary).multilineTextAlignment(.leading) }
                        }
                        Spacer()
                        Image(systemName: "chevron.right").font(.footnote.weight(.semibold)).foregroundStyle(Ink.tertiary)
                    }
                    .padding(.vertical, 6)
                }
            }
        }
        .card(tint: .info)
    }
}

struct RecommendationCard: View {
    @Environment(AppModel.self) private var model
    var card: SpeakCard
    var replaced: (SpeakCard) -> Void

    @State private var confirmed: Job?
    @State private var working = false

    /// "150 vests": the same plural rule as the desk.
    private var goods: String {
        let word = (card.product ?? "pieces").lowercased()
        let plural = word.hasSuffix("f") ? word.dropLast() + "ves" : word.hasSuffix("s") ? word : word + "s"
        return "\((card.pieces ?? 0).formatted()) \(plural)"
    }
    @State private var failure: String?
    @State private var choosing = false
    @State private var escalating = false
    @State private var splitting = false

    var body: some View {
        if let job = confirmed {
            sent(job)
        } else if let chosen = card.chosen {
            decision(chosen)
                .sheet(isPresented: $splitting) {
                    SplitSheet(card: card) { job in
                        splitting = false
                        withAnimation(.spring(response: 0.5, dampingFraction: 0.86)) { confirmed = job }
                        Task { await model.refresh() }
                    }
                }
                .sheet(isPresented: $escalating) {
                    EscalateSheet(card: card) {
                        replaced(Self.plain("Escalated to the planner", "Nothing was allocated. The reason is on the record."))
                        Task { await model.refresh() }
                    }
                }
                .sheet(isPresented: $choosing) {
                    OverrideSheet(card: card) { job in
                        choosing = false
                        finish(job)
                    }
                    .presentationDetents([.large])
                }
        }
    }

    private func decision(_ chosen: Option) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            VStack(alignment: .leading, spacing: 12) {
                Text(card.headline ?? "Recommended").font(.label).foregroundStyle(card.awkward == true ? Color(hex: 0xFFD98A) : Color(hex: 0x8CF0E2))
                Text(chosen.name).font(.hero(38)).foregroundStyle(Ink.primary)
                Text("\(card.orderId ?? ""), \(goods)\(card.customer.map { " for \($0)" } ?? "")")
                    .font(.subheadline).foregroundStyle(.white.opacity(0.82))
                Stitches(gradient: true).padding(.vertical, 2)
                HStack(alignment: .top) {
                    Fact(label: "Back by", value: Dates.short(chosen.back))
                    Fact(label: chosen.daysToSpare < 0 ? "Days late" : "Days to spare", value: "\(abs(chosen.daysToSpare))")
                    Fact(label: "Cost", value: money(chosen.totalCost))
                    Fact(label: "Defect risk", value: chosen.defect.formatted(.percent.precision(.fractionLength(0))))
                }
                if let why = card.why {
                    Text(why).font(.subheadline).foregroundStyle(Ink.primary).padding(.top, 2).fixedSize(horizontal: false, vertical: true)
                }
            }
            .dyeCard()

            if let other = card.runnerUp, let metrics = card.metrics, !metrics.isEmpty { compare(chosen, other, metrics) }

            ForEach(card.warnings ?? [], id: \.self) { warning in
                Label(warning.replacingOccurrences(of: "DATE CHECK: ", with: "").replacingOccurrences(of: "ALREADY LATE: ", with: ""), systemImage: "exclamationmark.triangle")
                    .font(.footnote).foregroundStyle(Ink.amber)
                    .padding(12).frame(maxWidth: .infinity, alignment: .leading)
                    .background(Ink.amberWash, in: .rect(cornerRadius: 14, style: .continuous))
            }

            evidence

            if card.canConfirm == true {
                SlideToConfirm(label: "Slide to send to \(chosen.name)") { confirm() }.disabled(working)
                HStack {
                    Button("Another workshop") { choosing = true }
                    Spacer()
                    Button("Split") { splitting = true }
                    Spacer()
                    Button("Escalate") { escalating = true }
                }
                .font(.subheadline.weight(.medium))
                .padding(.horizontal, 4)
            } else if let reason = card.blockReason {
                Text(reason).font(.footnote).foregroundStyle(Ink.amber)
            }
            if let failure { Text(failure).font(.footnote).foregroundStyle(Ink.coral) }
        }
    }

    private func compare(_ chosen: Option, _ other: Option, _ metrics: [Metric]) -> some View {
        VStack(alignment: .leading, spacing: 10) {
            Text("Against \(other.name)").font(.label).foregroundStyle(Ink.secondary)
            ForEach(metrics, id: \.self) { metric in
                HStack(alignment: .firstTextBaseline) {
                    Text(metric.label).font(.subheadline).foregroundStyle(Ink.secondary)
                    Spacer()
                    Text(metric.other).font(.subheadline).foregroundStyle(Ink.tertiary).monospacedDigit().strikethrough(metric.better == true, color: Ink.tertiary)
                    Image(systemName: "arrow.right").font(.caption2).foregroundStyle(Ink.tertiary)
                    Text(metric.winner).font(.subheadline.weight(.semibold)).foregroundStyle(metric.better == true ? Ink.teal : Ink.primary).monospacedDigit()
                }
            }
        }
        .card()
    }

    private var evidence: some View {
        HStack(spacing: 6) {
            Image(systemName: "checkmark.seal").foregroundStyle(Ink.teal)
            Text([card.reading == "fixture" ? "Rehearsal reading" : card.reading == "form" ? "From your form" : card.model.map { "Read by \($0)" } ?? "Read",
                  card.checks.map { "\($0) checks run" }, card.numbersVerified == true ? "numbers verified" : nil,
                  card.seconds.map { String(format: "%.1f s", $0) }].compactMap { $0 }.joined(separator: ", "))
        }
        .font(.caption).foregroundStyle(Ink.secondary)
        .padding(.horizontal, 4)
    }

    private func sent(_ job: Job) -> some View {
        let live = model.jobs.first { $0.key == job.key } ?? job
        return VStack(alignment: .leading, spacing: 14) {
            Text(live.stage == "offered" ? "Sent." : live.stageLabel + ".").font(.hero(38)).foregroundStyle(Ink.human).contentTransition(.opacity)
            Text("\(live.order) has gone to \(live.workshop). You are on record as approving it.").font(.body).foregroundStyle(Ink.secondary)
            JourneyView(job: live)
            Button("Open batch") { model.open(Target(type: "job", id: job.key)) }.font(.subheadline.weight(.medium))
        }
        .card(tint: .good)
        .animation(.smooth, value: live.stage)
    }

    private func finish(_ job: Job?) {
        guard let job else { return }
        withAnimation(.spring(response: 0.5, dampingFraction: 0.85)) { confirmed = job }
        model.track(job)
        Task { await model.refresh() }
    }

    private func confirm() {
        guard let token = card.token else { return }
        working = true
        Task {
            defer { working = false }
            do {
                let result: Confirmed = try await API.shared.post("/api/decisions/\(token)/confirm")
                finish(result.job)
            } catch {
                failure = error.localizedDescription
            }
        }
    }

    static func plain(_ title: String, _ text: String) -> SpeakCard {
        let json = #"{"card":"plain","title":"\#(title)","text":"\#(text)"}"#
        return try! JSONDecoder().decode(SpeakCard.self, from: Data(json.utf8))
    }
}

struct OverrideSheet: View {
    @Environment(\.dismiss) private var dismiss
    var card: SpeakCard
    var done: (Job?) -> Void

    @State private var workshop: String?
    @State private var reason: String?
    @State private var note = ""
    @State private var failure: String?

    private var others: [Option] { (card.options ?? []).filter { $0.workshopId != card.chosen?.workshopId } }
    private var ready: Bool { workshop != nil && reason != nil && (reason != "Other" || !note.trimmingCharacters(in: .whitespaces).isEmpty) }

    var body: some View {
        NavigationStack {
            List {
                Section("Workshop") {
                    ForEach(others) { option in
                        Button {
                            workshop = option.workshopId
                        } label: {
                            HStack {
                                VStack(alignment: .leading, spacing: 2) {
                                    Text(option.name).foregroundStyle(Ink.primary)
                                    Text("Back \(Dates.short(option.back)), \(spareText(option.daysToSpare)), cost \(money(option.totalCost))").font(.footnote).foregroundStyle(Ink.secondary)
                                }
                                Spacer()
                                if workshop == option.workshopId { Image(systemName: "checkmark").foregroundStyle(Ink.cobalt) }
                            }
                        }
                    }
                }
                Section("Why") {
                    ForEach(card.overrideReasons ?? [], id: \.self) { item in
                        Button {
                            reason = item
                        } label: {
                            HStack {
                                Text(item).foregroundStyle(Ink.primary)
                                Spacer()
                                if reason == item { Image(systemName: "checkmark").foregroundStyle(Ink.cobalt) }
                            }
                        }
                    }
                    TextField("Add a note", text: $note, axis: .vertical)
                }
                if let failure { Text(failure).foregroundStyle(Ink.coral) }
            }
            .navigationTitle("Another workshop")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) { Button("Send") { send() }.disabled(!ready) }
            }
        }
    }

    private func send() {
        guard let token = card.token, let workshop, let reason else { return }
        Task {
            do {
                let result: Confirmed = try await API.shared.post("/api/decisions/\(token)/override", ["workshop_id": workshop, "reason": reason, "note": note])
                done(result.job)
            } catch {
                failure = error.localizedDescription
            }
        }
    }
}

/// One workshop against two, side by side. The parts run at the same time, so the batch is back when the later part is.
struct SplitSheet: View {
    @Environment(\.dismiss) private var dismiss
    var card: SpeakCard
    var done: (Job?) -> Void

    @State private var option: SplitOption?
    @State private var failure: String?

    var body: some View {
        NavigationStack {
            List {
                if let option {
                    Section("One workshop") {
                        LabeledContent(option.single.name, value: "Back \(Dates.short(option.single.back))")
                        LabeledContent("Cost", value: money(option.single.cost))
                        LabeledContent("Defect risk", value: option.single.defect.formatted(.percent.precision(.fractionLength(1))))
                    }
                    if option.available, let parts = option.parts {
                        Section("Two workshops") {
                            ForEach(parts) { part in
                                LabeledContent("\(part.name), \(part.pieces.formatted()) pieces", value: "Back \(Dates.short(part.back))")
                            }
                            LabeledContent("All back", value: Dates.short(option.back))
                            LabeledContent("Cost", value: money(option.cost ?? 0))
                            LabeledContent("Defect risk", value: (option.defect ?? 0).formatted(.percent.precision(.fractionLength(1))))
                        }
                        Text((option.savesDays ?? 0) > 0 ? "The split saves \((option.savesDays ?? 0).formatted()) days of production time." : "The split is not faster here.")
                            .font(.footnote).foregroundStyle(Ink.secondary)
                    } else {
                        Text(option.reason ?? "No two workshops can share this batch.").font(.footnote).foregroundStyle(Ink.secondary)
                    }
                } else {
                    Stitches(running: true, gradient: true)
                }
                if let failure { Text(failure).foregroundStyle(Ink.coral) }
            }
            .navigationTitle("Single or split?")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) { Button("Send split") { send() }.disabled(option?.available != true) }
            }
            .task {
                guard let token = card.token else { return }
                do {
                    option = try await API.shared.get("/api/decisions/\(token)/split")
                } catch {
                    failure = error.localizedDescription
                }
            }
        }
    }

    private func send() {
        guard let token = card.token else { return }
        Task {
            do {
                let result: Confirmed = try await API.shared.post("/api/decisions/\(token)/split")
                done(result.job)
            } catch {
                failure = error.localizedDescription
            }
        }
    }
}

/// Sending a request up instead of deciding. Nothing is allocated, and the reason stays on the record.
struct EscalateSheet: View {
    @Environment(\.dismiss) private var dismiss
    var card: SpeakCard
    var done: () -> Void

    @State private var reason: String?
    @State private var note = ""
    @State private var failure: String?

    private var ready: Bool { reason != nil && (reason != "Other" || !note.trimmingCharacters(in: .whitespaces).isEmpty) }

    var body: some View {
        NavigationStack {
            List {
                Section("Why") {
                    ForEach(card.escalateReasons ?? [], id: \.self) { item in
                        Button {
                            reason = item
                        } label: {
                            HStack {
                                Text(item).foregroundStyle(Ink.primary)
                                Spacer()
                                if reason == item { Image(systemName: "checkmark").foregroundStyle(Ink.cobalt) }
                            }
                        }
                    }
                    TextField("Add a note", text: $note, axis: .vertical)
                }
                if let failure { Text(failure).foregroundStyle(Ink.coral) }
            }
            .navigationTitle("Why escalate?")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Cancel") { dismiss() } }
                ToolbarItem(placement: .confirmationAction) { Button("Escalate") { send() }.disabled(!ready) }
            }
        }
    }

    private func send() {
        guard let token = card.token, let reason else { return }
        Task {
            do {
                let _: Confirmed = try await API.shared.post("/api/decisions/\(token)/escalate", ["reason": reason, "note": note])
                dismiss()
                done()
            } catch {
                failure = error.localizedDescription
            }
        }
    }
}

struct ClarifyCard: View {
    var card: SpeakCard
    var replaced: (SpeakCard) -> Void
    @State private var reply = ""
    @State private var working = false
    @State private var failure: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("One question first").font(.label).foregroundStyle(Ink.amber)
            Text(card.question ?? "").font(.hero(26)).foregroundStyle(Ink.primary)
            ForEach(card.answers ?? [], id: \.self) { option in
                Button(option.label) { answer(option.field, option.value) }
                    .font(.subheadline.weight(.medium))
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(13)
                    .background(Ink.well, in: .rect(cornerRadius: 14, style: .continuous))
            }
            if (card.answers ?? []).isEmpty {
                Text("Nothing was allocated. Say it again with the missing detail.").font(.subheadline).foregroundStyle(Ink.secondary)
            }
            if working { Stitches(running: true, gradient: true) }
            if let failure { Text(failure).font(.footnote).foregroundStyle(Ink.coral) }
        }
        .card(tint: .warn)
    }

    private func answer(_ field: String, _ value: String) {
        guard let token = card.token else { return }
        working = true
        Task {
            defer { working = false }
            do {
                let next: SpeakCard = try await API.shared.post("/api/decisions/\(token)/answer", ["field": field, "value": value])
                withAnimation(.smooth) { replaced(next) }
            } catch {
                failure = error.localizedDescription
            }
        }
    }
}

struct DraftCard: View {
    @Environment(AppModel.self) private var model
    var card: SpeakCard
    var finished: () -> Void
    @State private var text = ""
    @State private var sent = false
    @State private var failure: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Message for \(card.name ?? "")").font(.label).foregroundStyle(Ink.secondary)
            if sent {
                Text("Sent.").font(.hero(32)).foregroundStyle(Ink.human)
            } else {
                TextField("Message", text: $text, axis: .vertical).font(.hero(23)).lineLimit(2 ... 8)
                if card.connected != true {
                    Text("\(card.name ?? "This party") has not connected Telegram yet, so this stays in the app.").font(.footnote).foregroundStyle(Ink.amber)
                }
                Button {
                    send()
                } label: {
                    Text("Send").font(.headline).frame(maxWidth: .infinity).padding(.vertical, 13)
                }
                .buttonStyle(.borderedProminent)
                .disabled(text.trimmingCharacters(in: .whitespaces).isEmpty)
            }
            if let failure { Text(failure).font(.footnote).foregroundStyle(Ink.coral) }
        }
        .card()
        .onAppear { text = card.text ?? "" }
    }

    private func send() {
        guard let party = card.party else { return }
        Task {
            do {
                let _: Message = try await API.shared.post("/api/threads/\(API.shared.encoded(party))/messages", ["text": text])
                withAnimation(.smooth) { sent = true }
                Haptics.success()
                await model.refresh()
            } catch {
                failure = error.localizedDescription
            }
        }
    }
}

struct ActionCard: View {
    @Environment(AppModel.self) private var model
    var card: SpeakCard
    var finished: () -> Void
    var replaced: (SpeakCard) -> Void
    @State private var done = false
    @State private var failure: String?

    var body: some View {
        VStack(alignment: .leading, spacing: 12) {
            Text(done ? "Marked received." : card.title ?? "").font(.hero(28)).foregroundStyle(done ? Ink.human : Ink.primary)
            Text(card.text ?? "").font(.subheadline).foregroundStyle(Ink.secondary)
            if !done {
                Button {
                    go()
                } label: {
                    Text(card.button ?? "Confirm").font(.headline).frame(maxWidth: .infinity).padding(.vertical, 13)
                }
                .buttonStyle(.borderedProminent)
                .tint(Ink.human)
            }
            if let failure { Text(failure).font(.footnote).foregroundStyle(Ink.coral) }
        }
        .card()
    }

    /// A spoken order is added here, on your tap, and then read like any other request.
    private func addOrder(_ fields: OrderFields) {
        Task {
            do {
                var body: [String: Any] = ["customer": fields.customer, "product": fields.product, "pieces": fields.pieces, "due": fields.due]
                if let priority = fields.priority { body["priority"] = priority }
                let next: SpeakCard = try await API.shared.post("/api/requests/new", body)
                replaced(next)
                await model.refresh()
            } catch {
                failure = error.localizedDescription
            }
        }
    }

    private func go() {
        if card.action == "new_order", let fields = card.fields { return addOrder(fields) }
        guard let key = card.key else { return }
        Task {
            do {
                let _: Job = try await API.shared.post("/api/batches/\(API.shared.encoded(key))/received")
                withAnimation(.smooth) { done = true }
                Haptics.success()
                await model.refresh()
            } catch {
                failure = error.localizedDescription
            }
        }
    }
}
