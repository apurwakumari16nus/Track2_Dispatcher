import SwiftUI

/// Something changed at a workshop. Here is what it does to every batch, and the plan to fix it.
/// Nothing has happened yet: the slide at the bottom is what makes it real.
struct IncidentView: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    var id: String
    @State private var incident: Incident?
    @State private var choices: [String: String] = [:]
    @State private var done: Approved?
    @State private var failure: String?

    var body: some View {
        ScrollView {
            if let done {
                result(done)
            } else if let incident {
                content(incident)
            } else {
                Stitches(running: true, gradient: true).padding(.top, 100).padding(.horizontal, 40)
            }
        }
        .background(Backdrop())
        .navigationBarTitleDisplayMode(.inline)
        .task { incident = try? await API.shared.get("/api/incidents/\(id)") }
    }

    private func content(_ incident: Incident) -> some View {
        VStack(alignment: .leading, spacing: 14) {
            VStack(alignment: .leading, spacing: 8) {
                Text("Nothing has changed yet").font(.label).foregroundStyle(.white.opacity(0.85))
                Text(incident.summary).font(.hero(30)).foregroundStyle(.white)
                if let reason = incident.reason { Text("Reason given: \(reason)").font(.subheadline).foregroundStyle(.white.opacity(0.82)) }
                if let detail = incident.detail, !detail.isEmpty { Text(detail).font(.subheadline).foregroundStyle(.white.opacity(0.82)) }
            }
            .dyeCard(.alarm)
            .padding(.top, 4)
            if incident.status != "open" {
                Text("This has already been handled.").font(.subheadline).foregroundStyle(Ink.secondary)
            } else {
                ForEach(incident.plan.rows) { row in
                    PlanRowView(row: row, choice: Binding(get: { choices[row.job] ?? row.action }, set: { choices[row.job] = $0 }))
                }
                if incident.plan.rows.isEmpty {
                    Text("No batches are affected. Approving updates the workshop's details.").font(.subheadline).foregroundStyle(Ink.secondary).card()
                }
                summary(incident.plan, workshop: incident.workshop)
                if let failure { Text(failure).font(.footnote).foregroundStyle(Ink.coral) }
                SlideToConfirm(label: "Slide to approve the plan") { approve() }
                Button("Dismiss, nothing changes") { dismissIncident() }.font(.subheadline.weight(.medium)).frame(maxWidth: .infinity)
            }
        }
        .padding(.horizontal, 16)
        .padding(.bottom, 30)
    }

    private func summary(_ plan: Plan, workshop: String) -> some View {
        let moves = plan.rows.filter { (choices[$0.job] ?? $0.action) == "move" }.count
        let parts = [moves > 0 ? "moves \(moves) batch\(moves == 1 ? "" : "es")" : nil,
                     plan.clientNotices > 0 ? "drafts \(plan.clientNotices) client notice\(plan.clientNotices == 1 ? "" : "s") for you to review" : nil,
                     plan.changeLabel.map { "marks \(workshop) \($0.prefix(1).lowercased() + $0.dropFirst())" }].compactMap { $0 }
        let cost = plan.costChange == 0 || moves < plan.rows.count ? "" : " Cost goes \(plan.costChange < 0 ? "down" : "up") by \(money(abs(plan.costChange)))."
        let joined = parts.count > 1 ? parts.dropLast().joined(separator: ", ") + ", and " + parts[parts.count - 1] : parts.joined()
        return Text(parts.isEmpty ? "Approving records this." : "Approving \(joined).\(cost)").font(.footnote).foregroundStyle(Ink.secondary).padding(.horizontal, 4)
    }

    private func result(_ result: Approved) -> some View {
        VStack(alignment: .leading, spacing: 12) {
            Text("Plan approved.").font(.hero(38)).foregroundStyle(Ink.human)
            Text("\(result.moved) batch\(result.moved == 1 ? "" : "es") re-offered. \(incident?.workshop ?? "The workshop") has been told.").font(.body).foregroundStyle(Ink.secondary)
            if result.letters > 0, let letter = model.today?.attention.first(where: { $0.kind == "letter" }) {
                Button { model.open(letter.target) } label: {
                    Text("Review the client notice")
                }
                .buttonStyle(DyeButton())
                .padding(.top, 6)
            }
        }
        .padding(16)
    }

    private func approve() {
        let changed = choices.filter { key, value in incident?.plan.rows.first { $0.job == key }?.action != value }
        Task {
            do {
                let result: Approved = try await API.shared.post("/api/incidents/\(id)/approve", changed.isEmpty ? [:] : ["choices": changed])
                await model.refresh()
                withAnimation(.spring(response: 0.5, dampingFraction: 0.85)) { done = result }
            } catch {
                failure = error.localizedDescription
            }
        }
    }

    private func dismissIncident() {
        Task {
            let _: Approved? = try? await API.shared.post("/api/incidents/\(id)/dismiss")
            await model.refresh()
            dismiss()
        }
    }
}

private struct PlanRowView: View {
    var row: PlanRow
    @Binding var choice: String

    private var moving: Bool { choice == "move" && row.move != nil }

    var body: some View {
        VStack(alignment: .leading, spacing: 11) {
            HStack {
                Text(row.orderId ?? "Batch").font(.headline).foregroundStyle(Ink.primary)
                Text(row.customer ?? "").font(.subheadline).foregroundStyle(Ink.secondary)
                Spacer()
                Text("Due \(Dates.short(row.due))").font(.footnote.weight(.medium)).foregroundStyle(Ink.secondary)
            }
            HStack(alignment: .center, spacing: 10) {
                side(row.was.workshop, row.stay.note ?? "Back \(Dates.short(row.stay.back))", row.stay.back == nil ? "" : spareText(row.stay.daysToSpare), (row.stay.daysToSpare ?? -1) < 0)
                    .opacity(moving ? 0.55 : 1)
                if let move = row.move {
                    Image(systemName: "arrow.right").font(.caption.weight(.bold)).foregroundStyle(Ink.tertiary)
                    side(move.name, "Back \(Dates.short(move.back))", spareText(move.daysToSpare), move.daysToSpare < 0)
                        .opacity(moving ? 1 : 0.55)
                }
            }
            Text(row.why).font(.footnote).foregroundStyle(Ink.secondary)
            if row.move != nil, row.stage != "in_production", row.canKeep != false {
                Picker("Action", selection: $choice) {
                    Text("Move").tag("move")
                    Text("Keep here").tag("wait")
                }
                .pickerStyle(.segmented)
            }
            if row.tellClient {
                Label("The client will need telling", systemImage: "envelope").font(.footnote).foregroundStyle(Ink.amber)
            }
        }
        .card(padding: 14)
    }

    private func side(_ name: String, _ back: String, _ spare: String, _ late: Bool) -> some View {
        VStack(alignment: .leading, spacing: 2) {
            Text(name).font(.subheadline.weight(.semibold)).foregroundStyle(Ink.primary).lineLimit(1)
            Text(back).font(.footnote).foregroundStyle(Ink.secondary)
            if !spare.isEmpty { Text(spare).font(.footnote.weight(.medium)).foregroundStyle(late ? Ink.coral : Ink.teal) }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .accessibilityElement(children: .combine)
    }
}

/// A delay notice to a client. Filled from the record, editable, and checked again before it leaves.
struct LetterView: View {
    @Environment(AppModel.self) private var model
    var id: String
    @State private var letter: Letter?
    @State private var text = ""
    @State private var unmatched: [String] = []
    @State private var sent = false
    @State private var failure: String?
    @FocusState private var editing: Bool

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: 14) {
                if sent {
                    let reached = letter?.connected == true
                    Text("\(reached ? "Sent to" : "Saved for") \(letter?.customer ?? "the client").").font(.hero(34)).foregroundStyle(Ink.human)
                    Text(reached ? "It is on the record, with your name on it." : "It is on the record. They are not on Telegram yet, so they have not received it.").font(.body).foregroundStyle(Ink.secondary)
                } else if let letter {
                    Text("Tell \(letter.customer)").font(.hero(34)).foregroundStyle(Ink.primary)
                    TextField("Notice", text: $text, axis: .vertical).font(.body).lineSpacing(3).focused($editing).card()
                    Label("Numbers and dates are checked against the record", systemImage: "checkmark.seal").font(.footnote).foregroundStyle(Ink.teal)
                    if !letter.connected {
                        Text("\(letter.customer) has not connected Telegram yet, so this stays in the app.").font(.footnote).foregroundStyle(Ink.amber)
                    }
                    if !unmatched.isEmpty {
                        VStack(alignment: .leading, spacing: 8) {
                            Text("Not in the record: \(unmatched.joined(separator: ", "))").font(.footnote.weight(.semibold)).foregroundStyle(Ink.coral)
                            Button("Send it anyway") { send(acknowledged: true) }.font(.footnote.weight(.semibold))
                        }
                        .padding(12).frame(maxWidth: .infinity, alignment: .leading).background(Ink.coralWash, in: .rect(cornerRadius: 14, style: .continuous))
                    }
                    if let failure { Text(failure).font(.footnote).foregroundStyle(Ink.coral) }
                    SlideToConfirm(label: "Slide to send") { send(acknowledged: false) }.id(unmatched.count)
                }
            }
            .padding(.horizontal, 16)
            .padding(.bottom, 24)
        }
        .scrollDismissesKeyboard(.interactively)
        .background(Backdrop())
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItemGroup(placement: .keyboard) {
                Spacer()
                Button("Done") { editing = false }
            }
        }
        .onChange(of: text) { unmatched = [] }
        .task {
            letter = try? await API.shared.get("/api/letters/\(id)")
            text = letter?.text ?? ""
        }
    }

    private func send(acknowledged: Bool) {
        editing = false
        Task {
            do {
                let result: LetterResult = try await API.shared.post("/api/letters/\(id)/send", ["text": text, "acknowledged": acknowledged])
                if result.sent {
                    withAnimation(.smooth) { sent = true }
                    await model.refresh()
                } else {
                    Haptics.warning()
                    unmatched = result.unmatched
                }
            } catch {
                failure = error.localizedDescription
            }
        }
    }
}
