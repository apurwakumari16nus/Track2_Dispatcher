import AppIntents
import Foundation

/// "Hey Siri, brief me in Threadline." Spoken from the same facts the Today screen shows.
struct BriefIntent: AppIntent {
    static let title: LocalizedStringResource = "Brief me"
    static let description = IntentDescription("Hears what needs you today.")

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let today: TodayData = try await API.shared.get("/api/today")
        return .result(dialog: IntentDialog(stringLiteral: today.spoken ?? today.brief))
    }
}

/// "Hey Siri, new request in Threadline." Siri takes the words, the desk decides, and nothing is sent until you say yes.
struct NewRequestIntent: AppIntent {
    static let title: LocalizedStringResource = "New request"
    static let description = IntentDescription("Speak a request and hear the recommendation.")

    @Parameter(title: "Request", requestValueDialog: "What's the request?")
    var request: String

    func perform() async throws -> some IntentResult & ProvidesDialog {
        var card: SpeakCard = try await API.shared.post("/api/speak", ["text": request])
        if card.action == "new_order", let fields = card.fields {
            try await requestConfirmation(actionName: .add, dialog: IntentDialog(stringLiteral: "\(card.text ?? "") Add it?"))
            var body: [String: Any] = ["customer": fields.customer, "product": fields.product, "pieces": fields.pieces, "due": fields.due]
            if let priority = fields.priority { body["priority"] = priority }
            card = try await API.shared.post("/api/requests/new", body)
        }
        switch card.card {
        case "recommendation":
            guard let chosen = card.chosen, let token = card.token else { break }
            let spare = chosen.daysToSpare < 0 ? "\(-chosen.daysToSpare) days late" : "\(chosen.daysToSpare) days to spare"
            guard card.canConfirm == true else {
                return .result(dialog: IntentDialog(stringLiteral: "\(chosen.name), but it cannot be sent yet. \(card.blockReason ?? "")"))
            }
            try await requestConfirmation(actionName: .send, dialog: IntentDialog(stringLiteral: "\(chosen.name), back \(Dates.short(chosen.back)), \(spare). Send it?"))
            let _: Confirmed = try await API.shared.post("/api/decisions/\(token)/confirm")
            return .result(dialog: "Sent to \(chosen.name). It is on the record.")
        case "clarify":
            return .result(dialog: IntentDialog(stringLiteral: "\(card.question ?? "It needs more detail.") Open Threadline to answer."))
        case "answer":
            return .result(dialog: IntentDialog(stringLiteral: card.text ?? "Done."))
        case "draft":
            return .result(dialog: IntentDialog(stringLiteral: "Your message to \(card.name ?? "them") is ready in Threadline."))
        default:
            break
        }
        return .result(dialog: IntentDialog(stringLiteral: card.text ?? "Open Threadline to continue."))
    }
}

/// "Hey Siri, where's a batch in Threadline."
struct WhereIsIntent: AppIntent {
    static let title: LocalizedStringResource = "Where is a batch"
    static let description = IntentDescription("Finds a batch by its order number.")

    @Parameter(title: "Order number", requestValueDialog: "Which order?")
    var order: String

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let card: SpeakCard = try await API.shared.post("/api/speak", ["text": "where is order \(order)"])
        return .result(dialog: IntentDialog(stringLiteral: card.text ?? "I could not find that batch."))
    }
}

/// "Hey Siri, chase workshops in Threadline." Also an action for Shortcuts automations.
struct ChaseIntent: AppIntent {
    static let title: LocalizedStringResource = "Chase silent workshops"
    static let description = IntentDescription("Sends one reminder to any workshop that has not answered an offer.")

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let result: RuleResult = try await API.shared.post("/api/automations/chase_silent/run")
        return .result(dialog: IntentDialog(stringLiteral: result.text))
    }
}

/// Marks a batch received, after asking. Put it on an NFC tag at the goods door.
struct ArrivedIntent: AppIntent {
    static let title: LocalizedStringResource = "Batch arrived"
    static let description = IntentDescription("Marks a batch received. Works well from an NFC tag at the goods door.")

    @Parameter(title: "Order number", requestValueDialog: "Which order arrived?")
    var order: String

    func perform() async throws -> some IntentResult & ProvidesDialog {
        let card: SpeakCard = try await API.shared.post("/api/speak", ["text": "order \(order) arrived"])
        guard card.card == "action", let key = card.key else {
            return .result(dialog: "That order is not out at a workshop.")
        }
        try await requestConfirmation(actionName: .log, dialog: IntentDialog(stringLiteral: "\(card.text ?? "") Mark it received?"))
        let _: Job = try await API.shared.post("/api/batches/\(API.shared.encoded(key))/received")
        return .result(dialog: "Marked received.")
    }
}

struct ThreadlineShortcuts: AppShortcutsProvider {
    static var appShortcuts: [AppShortcut] {
        AppShortcut(intent: BriefIntent(), phrases: ["Brief me in \(.applicationName)", "What needs me in \(.applicationName)"],
                    shortTitle: "Brief me", systemImageName: "sun.max")
        AppShortcut(intent: NewRequestIntent(), phrases: ["New request in \(.applicationName)", "New dispatch in \(.applicationName)"],
                    shortTitle: "New request", systemImageName: "waveform")
        AppShortcut(intent: OpenSpeakIntent(), phrases: ["Talk to \(.applicationName)", "Open \(.applicationName) and listen"],
                    shortTitle: "Talk", systemImageName: "mic")
        AppShortcut(intent: WhereIsIntent(), phrases: ["Where's a batch in \(.applicationName)"], shortTitle: "Where is a batch", systemImageName: "shippingbox")
        AppShortcut(intent: ChaseIntent(), phrases: ["Chase workshops in \(.applicationName)"], shortTitle: "Chase workshops", systemImageName: "bell")
        AppShortcut(intent: ArrivedIntent(), phrases: ["A batch arrived in \(.applicationName)"], shortTitle: "Batch arrived", systemImageName: "shippingbox.and.arrow.backward")
    }
}
