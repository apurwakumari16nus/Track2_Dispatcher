import SwiftUI

/// Your own request: pick an order from the book, or add one that has just come in. Either way it is read and checked
/// like a request from the group chat, and it stays in review until a decision goes out.
struct NewRequestView: View {
    @Environment(AppModel.self) private var model
    @Environment(\.dismiss) private var dismiss
    @State private var book: OrderBook?
    @State private var kind = "book"
    @State private var search = ""
    @State private var picked: BookOrder?
    @State private var customer = ""
    @State private var product = ""
    @State private var pieces = 500
    @State private var due = Date()
    @State private var priority = "Balanced"
    @State private var note = ""
    @State private var card: SpeakCard?
    @State private var working = false
    @State private var failure: String?

    private var earliest: Date { Dates.add(1, to: Dates.day(model.today?.today) ?? .now) }

    private var ready: Bool {
        kind == "book" ? picked != nil : !customer.isEmpty && !product.isEmpty && pieces > 0
    }

    private var found: [BookOrder] {
        let words = search.trimmingCharacters(in: .whitespaces).lowercased()
        let all = book?.open ?? []
        if words.isEmpty { return Array(all.prefix(8)) }
        return all.filter { "\($0.orderId) \($0.customer) \($0.product)".lowercased().contains(words) }
    }

    var body: some View {
        NavigationStack {
            ScrollView {
                VStack(alignment: .leading, spacing: 16) {
                    if let card {
                        CardView(card: card, spoken: "") { dismiss() } replaced: { self.card = $0 }
                        if let order = card.orderId, model.requests.contains(where: { $0.text.contains(order) }) {
                            Text("Close this and it stays in review until you send it.").font(.footnote).foregroundStyle(Ink.secondary)
                        }
                    } else {
                        form
                    }
                }
                .padding(.horizontal, 16)
                .padding(.bottom, 28)
            }
            .scrollDismissesKeyboard(.interactively)
            .background(Backdrop())
            .navigationTitle(card == nil ? "New request" : "Recommendation")
            .navigationBarTitleDisplayMode(.inline)
            .toolbar {
                ToolbarItem(placement: .cancellationAction) { Button("Close") { dismiss() } }
                ToolbarItemGroup(placement: .keyboard) {
                    Spacer()
                    Button("Done") { hideKeyboard() }
                }
            }
        }
        .task {
            book = try? await API.shared.get("/api/orders")
            due = Dates.add(14, to: earliest)
        }
    }

    private var form: some View {
        VStack(alignment: .leading, spacing: 16) {
            Picker("Kind", selection: $kind) {
                Text("From the order book").tag("book")
                Text("A new order").tag("new")
            }
            .pickerStyle(.segmented)
            if kind == "book" { orders } else { newOrder }
            choices
            if let failure { Text(failure).font(.footnote).foregroundStyle(Ink.coral) }
            Button { submit() } label: { Text(working ? "Reading it and checking the workshops" : "Get a recommendation") }
                .buttonStyle(DyeButton())
                .disabled(!ready || working)
                .opacity(ready ? 1 : 0.5)
            if working { Stitches(running: true, gradient: true) }
            Button("Say it instead", systemImage: "waveform") {
                dismiss()
                model.startSpeaking()
            }
            .font(.subheadline.weight(.medium))
            .frame(maxWidth: .infinity)
        }
    }

    private var orders: some View {
        VStack(alignment: .leading, spacing: 8) {
            TextField("Search by order, customer or product", text: $search)
                .textInputAutocapitalization(.never).autocorrectionDisabled()
                .padding(.horizontal, 14).padding(.vertical, 11)
                .background(Ink.well, in: .rect(cornerRadius: 14, style: .continuous))
            VStack(spacing: 0) {
                ForEach(Array(found.enumerated()), id: \.element.id) { index, order in
                    Button { pick(order) } label: {
                        HStack(spacing: 10) {
                            VStack(alignment: .leading, spacing: 1) {
                                Text("\(order.orderId), \(order.goods)").font(.subheadline.weight(.semibold)).foregroundStyle(Ink.primary)
                                Text("\(order.customer), due \(Dates.short(order.due))").font(.footnote).foregroundStyle(Ink.secondary)
                            }
                            Spacer()
                            Image(systemName: picked == order ? "checkmark.circle.fill" : "circle").foregroundStyle(picked == order ? Ink.cobalt : Ink.tertiary)
                        }
                        .padding(.vertical, 9)
                        .contentShape(.rect)
                    }
                    .buttonStyle(.plain)
                    if index < found.count - 1 { Divider().overlay(Ink.line) }
                }
                if found.isEmpty {
                    Text(book == nil ? "Loading the order book." : "Nothing matches. Add it as a new order instead.").font(.subheadline).foregroundStyle(Ink.secondary).padding(.vertical, 8)
                }
            }
            .card(padding: 12)
        }
    }

    private var newOrder: some View {
        VStack(spacing: 12) {
            LabeledContent("Customer") {
                Picker("Customer", selection: $customer) {
                    Text("Choose").tag("")
                    ForEach(book?.customers ?? [], id: \.self) { Text($0).tag($0) }
                }
                .labelsHidden()
            }
            Divider().overlay(Ink.line)
            LabeledContent("Product") {
                Picker("Product", selection: $product) {
                    Text("Choose").tag("")
                    ForEach(book?.products ?? [], id: \.self) { Text($0).tag($0) }
                }
                .labelsHidden()
            }
            Divider().overlay(Ink.line)
            LabeledContent("Pieces") {
                HStack(spacing: 10) {
                    TextField("Pieces", value: $pieces, format: .number).keyboardType(.numberPad).multilineTextAlignment(.trailing).frame(width: 80)
                    Stepper("Pieces", value: $pieces, in: 1 ... 100_000, step: 50).labelsHidden()
                }
            }
            Divider().overlay(Ink.line)
            DatePicker("Back by", selection: $due, in: earliest..., displayedComponents: .date)
        }
        .font(.subheadline)
        .card(padding: 14)
    }

    private var choices: some View {
        VStack(alignment: .leading, spacing: 10) {
            if kind == "book", picked != nil {
                DatePicker("Back by", selection: $due, displayedComponents: .date).font(.subheadline).card(padding: 12)
            }
            Text("What matters most").font(.label).foregroundStyle(Ink.secondary)
            FlowLayout {
                ForEach(book?.priorities ?? [], id: \.self) { item in
                    Button(item) { priority = item; Haptics.tick() }
                        .font(.subheadline.weight(.medium))
                        .foregroundStyle(priority == item ? .white : Ink.primary)
                        .padding(.horizontal, 13).padding(.vertical, 8)
                        .background(priority == item ? AnyShapeStyle(Ink.chosen) : AnyShapeStyle(Ink.well), in: .capsule)
                }
            }
            TextField("Add a note, if there is anything to know", text: $note, axis: .vertical)
                .lineLimit(1 ... 3)
                .padding(.horizontal, 14).padding(.vertical, 11)
                .background(Ink.well, in: .rect(cornerRadius: 14, style: .continuous))
        }
    }

    private func pick(_ order: BookOrder) {
        Haptics.tick()
        picked = order
        due = Dates.day(order.due) ?? due
    }

    private func hideKeyboard() {
        UIApplication.shared.sendAction(#selector(UIResponder.resignFirstResponder), to: nil, from: nil, for: nil)
    }

    private func submit() {
        hideKeyboard()
        var body: [String: Any] = ["due": Dates.key(due), "priority": priority, "note": note]
        if kind == "book", let picked {
            body["order_id"] = picked.orderId
        } else {
            body.merge(["customer": customer, "product": product, "pieces": pieces]) { $1 }
        }
        working = true
        failure = nil
        Task {
            defer { working = false }
            do {
                let result: SpeakCard = try await API.shared.post("/api/requests/new", body)
                withAnimation(.spring(response: 0.5, dampingFraction: 0.86)) { card = result }
                await model.refresh()
            } catch {
                failure = error.localizedDescription
            }
        }
    }
}
