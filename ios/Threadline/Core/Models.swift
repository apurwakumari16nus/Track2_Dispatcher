import SwiftUI

struct Target: Codable, Hashable {
    var type: String
    var id: String
}

struct Attention: Codable, Identifiable, Hashable {
    var id: String
    var kind: String
    var tone: String
    var title: String
    var detail: String
    var action: String
    var target: Target
    var when: String?
}

struct LogEntry: Codable, Hashable {
    var at: String?
    var on: String?
    var label: String
    var detail: String
    var by: String?
}

/// What the Dynamic Island says about a batch, worked out on the desk so the app and a push always agree.
struct IslandState: Codable, Hashable {
    var status: String
    var detail: String
    var step: Int
    var alert: Bool
}

struct Job: Codable, Identifiable, Hashable {
    var key: String
    var orderId: String?
    var customer: String?
    var product: String?
    var pieces: Int
    var workshopId: String
    var workshop: String
    var sent: String?
    var back: String?
    var backWas: String?
    var due: String?
    var daysToSpare: Int?
    var stage: String
    var stageLabel: String
    var health: String
    var healthLabel: String
    var split: Bool
    var override: Bool
    var movedFrom: String?
    var channel: String?
    var confirmedBy: String?
    var rate: Double?
    var totalCost: Double?
    var log: [LogEntry]
    var silent: Bool?
    var island: IslandState?

    var id: String { key }
    var order: String { orderId ?? "Batch" }

    var goods: String {
        let word = (product ?? "pieces").lowercased()
        let plural = word.hasSuffix("f") ? String(word.dropLast()) + "ves" : word.hasSuffix("s") ? word : word + "s"
        return "\(pieces.formatted()) \(plural)"
    }

    var tone: Tone {
        switch health {
        case "overdue": .risk
        case "due_today", "at_risk": .warn
        case "received": .good
        default: .info
        }
    }

    /// Which part of the line it sits in. Everything has a place, including what has gone wrong.
    var lane: Stage {
        switch stage {
        case "booked": .review
        case "offered", "declined": .sent
        case "accepted": .accepted
        case "in_production": .sewing
        case "ready", "shipped": .completed
        default: .back
        }
    }

    /// Anything that will not resolve itself, in words. Nil when the batch is simply moving along.
    var problem: String? {
        if stage == "received" { return nil }
        if stage == "declined" { return "Declined" }
        if stage == "booked" { return "Not sent yet" }
        if silent == true { return "No answer yet" }
        if health == "overdue" { return "Overdue" }
        if let days = daysToSpare, days < 0 { return "\(-days) day\(days == -1 ? "" : "s") late" }
        return health == "due_today" ? "Due back today" : nil
    }

    var alert: Tone? {
        guard problem != nil else { return nil }
        return stage == "declined" || health == "overdue" ? .risk : .warn
    }

    var fill: AnyShapeStyle { alert.map { AnyShapeStyle($0.gradient) } ?? AnyShapeStyle(lane.gradient) }

    var statusColour: Color { alert?.color ?? lane.color }

    /// What the workshop would tap next, for rehearsing.
    var nextTap: (action: String, label: String)? {
        switch stage {
        case "offered": ("accepts", "Accept")
        case "accepted": ("started", "Started")
        case "in_production": ("ready", "Completed")
        case "ready": ("shipped", "Shipped")
        default: nil
        }
    }

    /// Where it has got to on the line, 0 to 4.
    var step: Int {
        switch stage {
        case "booked", "offered", "declined": 0
        case "accepted": 1
        case "in_production": 2
        case "ready", "shipped": 3
        default: 4
        }
    }
}

struct Notice: Codable, Hashable {
    var label: String?
    var until: String?
    var reason: String?
}

struct Workshop: Codable, Identifiable, Hashable {
    var id: String
    var name: String
    var status: String
    var capacity: Int
    var leadDays: Int
    var cost: Double
    var defectRate: Double
    var makes: [String]
    var maxBatch: Int?
    var notes: String
    var queueDays: Double
    var openJobs: Int
    var completed: Int?
    var piecesOut: Int
    var notices: [Notice]
    var reported: String?
    var offers: Int
    var accepted: Int
    var declined: Int
    var connected: Bool
    var lastMessage: String?
    var jobs: [Job]?

    var isOpen: Bool { status == "ACTIVE" }
    var load: Double { min(1, queueDays / 14) }
}

struct TodayData: Codable {
    var today: String
    var headline: String
    var brief: String
    var spoken: String?
    var attention: [Attention]
    var counts: [String: Int]
    var out: Int
    var piecesOut: Int
    var comingBack: [Job]
    var network: [Workshop]
    var requests: Int
    var demo: Bool
}

/// Everything the main screens draw, from one call.
struct DeskSnapshot: Codable {
    var today: TodayData
    var jobs: [Job]
    var threads: [ThreadSummary]
    var requests: [WaitingRequest]
}

struct BookOrder: Codable, Identifiable, Hashable {
    var orderId: String
    var customer: String
    var product: String
    var pieces: Int
    var due: String

    var id: String { orderId }

    var goods: String {
        let word = product.lowercased()
        let plural = word.hasSuffix("f") ? String(word.dropLast()) + "ves" : word.hasSuffix("s") ? word : word + "s"
        return "\(pieces.formatted()) \(plural)"
    }
}

struct OrderBook: Codable {
    var open: [BookOrder]
    var customers: [String]
    var products: [String]
    var priorities: [String]
}

struct OrderFields: Codable, Hashable {
    var customer: String
    var product: String
    var pieces: Int
    var due: String
    var priority: String?
}

struct Automation: Codable, Identifiable, Hashable {
    var name: String
    var title: String
    var detail: String
    var on: Bool

    var id: String { name }
}

struct RuleResult: Codable {
    var done: [String]
    var text: String
}

struct ThreadSummary: Codable, Identifiable, Hashable {
    var party: String
    var name: String
    var type: String
    var connected: Bool
    var status: String?
    var lastText: String?
    var lastAt: String?
    var lastDirection: String?
    var count: Int

    var id: String { party }
}

struct Reading: Codable, Hashable {
    var kind: String
    var orderId: String?
    var date: String?
    var delayDays: Int?
    var capacityPerDay: Int?
    var pricePerPiece: Double?
    var reason: String?
    var source: String?
    var needsPerson: Bool?

    var understood: String {
        switch kind {
        case "accepts": "Accepted the job"
        case "declines": "Cannot take the job"
        case "started": "Work has started"
        case "ready": "Completed"
        case "shipped": "On its way back"
        case "delay": date.map { "New date \(Dates.short($0))" } ?? delayDays.map { "\($0) more days" } ?? "Running late"
        case "closed": date.map { "Closed until \(Dates.short($0))" } ?? "Closed"
        case "reopened": "Working again"
        case "capacity_change": capacityPerDay.map { "\($0.formatted()) a day for now" } ?? "Output has changed"
        case "price_change": pricePerPiece.map { "New rate \($0.formatted())" } ?? "Rate has changed"
        case "quality_problem": "Quality problem"
        case "question": "Asked a question"
        case "agrees": "Agreed to the change"
        case "disagrees": "Objected to the change"
        default: "Needs you to read it"
        }
    }
}

struct Message: Codable, Identifiable, Hashable {
    var id: String
    var at: String
    var direction: String
    var author: String
    var text: String
    var channel: String
    var delivered: Bool?
    var automatic: Bool?
    var tapped: Bool?
    var reading: Reading?

    var isOutgoing: Bool { direction == "out" }
}

struct Suggestion: Codable, Hashable {
    var label: String
    var text: String
}

struct Thread: Codable {
    var party: String
    var name: String
    var type: String
    var connected: Bool
    var messages: [Message]
    var suggestions: [Suggestion]
    var jobs: [Job]
    var telegramUrl: String?
}

struct Option: Codable, Identifiable, Hashable {
    var workshopId: String
    var name: String
    var back: String
    var daysToSpare: Int
    var totalDays: Double
    var totalCost: Double
    var costPerPiece: Double
    var defect: Double

    var id: String { workshopId }
}

struct Metric: Codable, Hashable {
    var label: String
    var winner: String
    var other: String
    var difference: String
    var better: Bool?
}

struct Answer: Codable, Hashable {
    var label: String
    var field: String
    var value: String
}

struct CardItem: Codable, Hashable {
    var title: String
    var detail: String
    var target: Target
}

/// Everything /api/speak can return. One flat shape, read by `card`.
struct SpeakCard: Codable, Hashable {
    var card: String
    var title: String?
    var text: String?
    var items: [CardItem]?
    var retry: Bool?
    // A decision
    var token: String?
    var orderId: String?
    var customer: String?
    var product: String?
    var pieces: Int?
    var due: String?
    var reading: String?
    var model: String?
    var checksPassed: Int?
    var checks: Int?
    var headline: String?
    var awkward: Bool?
    var chosen: Option?
    var runnerUp: Option?
    var why: String?
    var metrics: [Metric]?
    var options: [Option]?
    var warnings: [String]?
    var canConfirm: Bool?
    var blockReason: String?
    var overrideReasons: [String]?
    var escalateReasons: [String]?
    var readAs: String?
    var numbersVerified: Bool?
    var seconds: Double?
    // A clarification
    var question: String?
    var missing: [String]?
    var answers: [Answer]?
    // A message for review
    var party: String?
    var name: String?
    var connected: Bool?
    // A write that waits for a person
    var action: String?
    var key: String?
    var button: String?
    var fields: OrderFields?

    enum CodingKeys: String, CodingKey {
        case card, title, text, items, retry, token, orderId, customer, product, pieces, due, escalateReasons, readAs, reading, model, checksPassed, checks, headline, awkward, chosen, runnerUp, why, metrics, warnings, canConfirm, blockReason, overrideReasons, numbersVerified, seconds, question, missing, party, name, connected, action, key, button, fields
        case options
    }

    init(from decoder: Decoder) throws {
        let c = try decoder.container(keyedBy: CodingKeys.self)
        card = try c.decode(String.self, forKey: .card)
        title = try c.decodeIfPresent(String.self, forKey: .title)
        text = try c.decodeIfPresent(String.self, forKey: .text)
        items = try c.decodeIfPresent([CardItem].self, forKey: .items)
        retry = try c.decodeIfPresent(Bool.self, forKey: .retry)
        token = try c.decodeIfPresent(String.self, forKey: .token)
        orderId = try c.decodeIfPresent(String.self, forKey: .orderId)
        customer = try c.decodeIfPresent(String.self, forKey: .customer)
        product = try c.decodeIfPresent(String.self, forKey: .product)
        pieces = try c.decodeIfPresent(Int.self, forKey: .pieces)
        due = try c.decodeIfPresent(String.self, forKey: .due)
        reading = try c.decodeIfPresent(String.self, forKey: .reading)
        model = try c.decodeIfPresent(String.self, forKey: .model)
        checksPassed = try c.decodeIfPresent(Int.self, forKey: .checksPassed)
        checks = try c.decodeIfPresent(Int.self, forKey: .checks)
        headline = try c.decodeIfPresent(String.self, forKey: .headline)
        awkward = try c.decodeIfPresent(Bool.self, forKey: .awkward)
        chosen = try c.decodeIfPresent(Option.self, forKey: .chosen)
        runnerUp = try c.decodeIfPresent(Option.self, forKey: .runnerUp)
        why = try c.decodeIfPresent(String.self, forKey: .why)
        metrics = try c.decodeIfPresent([Metric].self, forKey: .metrics)
        warnings = try c.decodeIfPresent([String].self, forKey: .warnings)
        canConfirm = try c.decodeIfPresent(Bool.self, forKey: .canConfirm)
        blockReason = try c.decodeIfPresent(String.self, forKey: .blockReason)
        overrideReasons = try c.decodeIfPresent([String].self, forKey: .overrideReasons)
        escalateReasons = try c.decodeIfPresent([String].self, forKey: .escalateReasons)
        readAs = try c.decodeIfPresent(String.self, forKey: .readAs)
        numbersVerified = try c.decodeIfPresent(Bool.self, forKey: .numbersVerified)
        seconds = try c.decodeIfPresent(Double.self, forKey: .seconds)
        question = try c.decodeIfPresent(String.self, forKey: .question)
        missing = try c.decodeIfPresent([String].self, forKey: .missing)
        party = try c.decodeIfPresent(String.self, forKey: .party)
        name = try c.decodeIfPresent(String.self, forKey: .name)
        connected = try c.decodeIfPresent(Bool.self, forKey: .connected)
        action = try c.decodeIfPresent(String.self, forKey: .action)
        key = try c.decodeIfPresent(String.self, forKey: .key)
        button = try c.decodeIfPresent(String.self, forKey: .button)
        fields = try c.decodeIfPresent(OrderFields.self, forKey: .fields)
        // A clarification's options are answers; a recommendation's options are workshops.
        if card == "clarify" {
            answers = try c.decodeIfPresent([Answer].self, forKey: .options)
        } else {
            options = try c.decodeIfPresent([Option].self, forKey: .options)
        }
    }

    func encode(to encoder: Encoder) throws {}
}

struct Confirmed: Codable {
    var card: String
    var key: String?
    var job: Job?
}

struct PlanSide: Codable, Hashable {
    var back: String?
    var daysToSpare: Int?
    var note: String?
}

struct PlanMove: Codable, Hashable {
    var workshopId: String
    var name: String
    var back: String
    var daysToSpare: Int
    var cost: Double
    var costChange: Double
    var defect: Double
}

struct PlanWas: Codable, Hashable {
    var workshop: String
    var back: String?
}

struct PlanRow: Codable, Identifiable, Hashable {
    var canKeep: Bool?
    var job: String
    var orderId: String?
    var customer: String?
    var product: String?
    var pieces: Int
    var stage: String
    var stageLabel: String
    var due: String?
    var was: PlanWas
    var stay: PlanSide
    var move: PlanMove?
    var action: String
    var tellClient: Bool
    var why: String
    var finalBack: String?

    var id: String { job }
}

struct Plan: Codable {
    var rows: [PlanRow]
    var moves: Int
    var stays: Int
    var clientNotices: Int
    var changeLabel: String?
    var costChange: Double
}

struct Incident: Codable {
    var id: String
    var type: String
    var summary: String
    var detail: String?
    var status: String
    var workshop: String
    var workshopId: String
    var reason: String?
    var plan: Plan
}

struct Approved: Codable {
    var moved: Int
    var letters: Int
}

struct NumberCheck: Codable {
    var passed: Bool
    var unmatched: [String]
}

struct Letter: Codable {
    var id: String
    var customer: String
    var orderId: String
    var text: String
    var status: String
    var connected: Bool
    var check: NumberCheck
}

struct LetterResult: Codable {
    var sent: Bool
    var unmatched: [String]
}

struct WaitingRequest: Codable, Identifiable, Hashable {
    var id: String
    var time: String
    var sender: String
    var text: String
    var channel: String
    var line: String
}

struct TrailEntry: Codable, Hashable {
    var at: String?
    var label: String
    var detail: String
    var by: String?
    var orderId: String?
    var key: String?
}

struct Heard: Decodable {
    var text: String
    var language: String
}

struct Found: Decodable {
    var language: String
}

struct Done: Decodable {
    var ok: Bool
}

struct SplitPart: Decodable, Identifiable, Hashable {
    var name: String
    var pieces: Int
    var back: String
    var id: String { name }
}

struct SplitSingle: Decodable {
    var name: String
    var back: String
    var cost: Double
    var defect: Double
}

/// One workshop against the fastest two, as the desk worked it out.
struct SplitOption: Decodable {
    var available: Bool
    var reason: String?
    var single: SplitSingle
    var parts: [SplitPart]?
    var back: String?
    var cost: Double?
    var defect: Double?
    var savesDays: Double?
}

struct Reasons: Decodable {
    var decline: [String]
}

struct Health: Codable {
    var ok: Bool
    var demo: Bool
    var today: String
    var source: String
    var reader: String
    var model: String?
    var telegram: Bool
    var connected: [String]
}
